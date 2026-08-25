"""Execucao de comandos vindos do Live, na maquina do cliente.

O servidor pede; o Agente decide se pode e executa. Essa direcao importa: o
Live nunca alcanca o disco por conta propria, e nenhum comando ganha acesso a
pasta que nao foi autorizada **nesta maquina**.

Duas garantias que fazem o protocolo aguentar rede ruim:

1. **Idempotencia.** Cada comando tem identificador. Se o mesmo chegar de novo
   — reconexao, reentrega, servidor que nao viu a resposta — o Agente devolve
   o resultado guardado em vez de executar outra vez. Sem isso, uma queda de
   rede no momento errado viraria dois backups, duas rotacoes de retencao, dois
   arquivos apagados.
2. **Acao desconhecida nao derruba nada.** Um servidor mais novo pode pedir
   algo que este Agente ainda nao sabe fazer. A resposta e "nao sei fazer
   isso", com o nome da acao — e nao uma conexao que cai em laco.
"""

from __future__ import annotations

import traceback
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .config import Configuracao

#: Quantos resultados guardar para reconhecer reentrega. Um Agente domestico
#: nao executa milhares de comandos por sessao; o teto existe so para a memoria
#: nao crescer sem limite num servico que fica meses no ar.
LEMBRAR_ULTIMOS = 200

#: Assinatura de um executor: recebe parametros e o contexto, devolve o corpo
#: do resultado.
Executor = Callable[[dict[str, Any], "Contexto"], Awaitable[dict[str, Any]]]


@dataclass
class Contexto:
    """O que um executor pode usar. Nada alem disto."""

    configuracao: Configuracao
    #: Manda progresso para o servidor. Nao e obrigatorio usar.
    relatar: Callable[[dict[str, Any]], Awaitable[None]]
    #: Agendador desta maquina, quando ha um. `None` em execucao avulsa (a
    #: linha de comando, por exemplo), e os executores que dependem dele
    #: precisam dizer isso em vez de fingir que guardaram a politica.
    agendador: Any = None


@dataclass
class Registro:
    """Executores conhecidos e memoria dos comandos ja atendidos."""

    executores: dict[str, Executor] = field(default_factory=dict)
    _resultados: dict[str, dict[str, Any]] = field(default_factory=dict)
    _ordem: list[str] = field(default_factory=list)

    def registrar(self, acao: str, executor: Executor) -> None:
        self.executores[acao] = executor

    def conhecidas(self) -> list[str]:
        return sorted(self.executores)

    def ja_atendido(self, identificador: str) -> dict[str, Any] | None:
        return self._resultados.get(identificador)

    def lembrar(self, identificador: str, resultado: dict[str, Any]) -> None:
        """Guarda o resultado, descartando os mais antigos quando encher."""
        if identificador in self._resultados:
            return
        self._resultados[identificador] = resultado
        self._ordem.append(identificador)
        while len(self._ordem) > LEMBRAR_ULTIMOS:
            self._resultados.pop(self._ordem.pop(0), None)


async def atender(
    mensagem: dict[str, Any],
    registro: Registro,
    contexto: Contexto,
) -> dict[str, Any]:
    """
    Executa um comando e devolve a mensagem de resultado, pronta para enviar.

    Nunca levanta: uma falha do executor vira um resultado com `ok=False` e a
    explicacao. Deixar a excecao subir derrubaria o canal e, com ele, todos os
    outros comandos daquela maquina.
    """
    identificador = str(mensagem.get("id", ""))
    acao = str(mensagem.get("acao", ""))
    parametros = mensagem.get("parametros") or {}

    guardado = registro.ja_atendido(identificador)
    if guardado is not None:
        # Reentrega: devolve o mesmo resultado. Executar de novo poderia
        # significar um segundo backup — ou uma segunda rotacao de retencao,
        # que APAGA arquivo.
        return {**guardado, "reentregue": True}

    executor = registro.executores.get(acao)
    if executor is None:
        return {
            "tipo": "resultado",
            "comando": identificador,
            "ok": False,
            "erro": f"acao desconhecida: {acao}",
            "acoes_conhecidas": registro.conhecidas(),
        }

    try:
        corpo = await executor(dict(parametros), contexto)
        resultado = {"tipo": "resultado", "comando": identificador, "ok": True, **corpo}
    except Exception as erro:  # noqa: BLE001 — executor de terceiro nao pode derrubar o canal
        resultado = {
            "tipo": "resultado",
            "comando": identificador,
            "ok": False,
            "erro": f"{type(erro).__name__}: {erro}",
            # O rastro vai para o log do Agente, na maquina. Ele nao sobe para
            # o servidor: pode conter caminho local, e caminho local do cliente
            # nao e assunto do Live.
            "detalhe": "",
        }
        traceback.print_exc()

    registro.lembrar(identificador, resultado)
    return resultado


# ============================================================
# Executores que ja existem
# ============================================================


async def executar_estado(_parametros: dict[str, Any], contexto: Contexto) -> dict[str, Any]:
    """
    Conta ao Live o que este dispositivo sabe sobre si.

    E a base da tela de saude: pastas autorizadas, versao e se ha algo
    autorizado. Um dispositivo pareado sem pasta autorizada nao copia nada, e
    isso precisa aparecer como fato, nao como suposicao.
    """
    from .pareamento import VERSAO

    return {
        "versao_agente": VERSAO,
        "raizes": list(contexto.configuracao.raizes),
        "pode_copiar": bool(contexto.configuracao.raizes),
    }


async def executar_politicas(parametros: dict[str, Any], contexto: Contexto) -> dict[str, Any]:
    """
    Recebe as politicas do servidor e as grava NESTA maquina.

    Gravar em disco e o ponto: a partir daqui o agendamento funciona com o
    navegador fechado, com o servidor fora do ar e depois de a maquina
    reiniciar. Guardar so em memoria transformaria "backup agendado" em
    "backup enquanto tudo estiver bem".
    """
    from autotarefas.tasks.politica import Politica

    from .agendador import PoliticaLocal

    if contexto.agendador is None:
        msg = "este Agente esta rodando sem agendador; nao ha onde guardar politica"
        raise RuntimeError(msg)

    brutas = parametros.get("politicas") or []
    politicas = [
        PoliticaLocal(
            id=str(item.get("id", "")),
            nome=str(item.get("nome", "")),
            politica=Politica.model_validate(item.get("configuracao") or {}),
        )
        for item in brutas
    ]
    contexto.agendador.substituir(politicas)

    return {
        "politicas": len(politicas),
        "proximas": [
            {
                "id": item.id,
                "proxima": item.proxima.isoformat() if item.proxima else "",
            }
            for item in contexto.agendador.politicas
        ],
    }


async def executar_situacao(_parametros: dict[str, Any], contexto: Contexto) -> dict[str, Any]:
    """
    Conta como foi a ultima execucao de cada politica.

    E o que o Live mostra no historico quando a maquina reconecta. Sem isto, um
    backup que rodou de madrugada com a internet caida ficaria invisivel.
    """
    if contexto.agendador is None:
        return {"politicas": []}

    return {
        "politicas": [
            {
                "id": item.id,
                "nome": item.nome,
                "proxima": item.proxima.isoformat() if item.proxima else "",
                "ultima_execucao": item.ultima_execucao,
                "ultimo_resultado": item.ultimo_resultado,
                "ultima_ressalva": item.ultima_ressalva,
            }
            for item in contexto.agendador.politicas
        ]
    }


async def executar_listar_pacote(parametros: dict[str, Any], contexto: Contexto) -> dict[str, Any]:
    """
    Lista o que ha dentro de um pacote, para a tela mostrar antes de restaurar.

    O pacote precisa estar numa pasta autorizada NESTA maquina, como qualquer
    outro caminho: o Live nao ganha o direito de ler um ZIP arbitrario do
    disco do cliente so porque a operacao se chama "restaurar".
    """
    from pathlib import Path as Caminho

    from autotarefas.tasks.restauracao import listar_conteudo

    from . import raizes

    pacote = raizes.exigir_autorizacao(
        contexto.configuracao, Caminho(str(parametros.get("pacote", "")))
    )
    return {"pacote": pacote.name, "conteudo": listar_conteudo(pacote)}


async def executar_restaurar(parametros: dict[str, Any], contexto: Contexto) -> dict[str, Any]:
    """
    Restaura arquivos de um pacote para uma pasta desta maquina.

    Origem E destino passam pela guarda de pastas autorizadas. Restaurar e
    escrever no disco do cliente — a operacao mais perigosa que o Agente faz —,
    e nao pode ter uma porta mais larga que a de ler.

    Quando o pedido inclui `sobrescrever`, a substituicao passa ainda pela
    guarda de acao destrutiva: `protecao` aponta a pasta de pacotes do
    DESTINO, e sem backup recente e conferido ali a operacao nao acontece. A
    saida explicita e `dispensar_protecao`, com o motivo — que volta no
    relatorio para virar registro no servidor.
    """
    import asyncio as _asyncio
    from pathlib import Path as Caminho

    from autotarefas.tasks.restauracao import restaurar

    from . import raizes

    configuracao = contexto.configuracao
    pacote = raizes.exigir_autorizacao(configuracao, Caminho(str(parametros.get("pacote", ""))))
    destino = raizes.exigir_autorizacao(configuracao, Caminho(str(parametros.get("destino", ""))))
    anteriores = [
        raizes.exigir_autorizacao(configuracao, Caminho(str(item)))
        for item in parametros.get("anteriores") or []
    ]

    # A pasta de protecao tambem e uma pasta desta maquina, e por isso passa
    # pela mesma guarda. Sem isso, o Live poderia apontar para qualquer lugar
    # do disco e usar a resposta para descobrir o que existe la.
    dito = str(parametros.get("protecao") or "")
    protecao = raizes.exigir_autorizacao(configuracao, Caminho(dito)) if dito else None

    await contexto.relatar({"etapa": "restaurando", "pacote": pacote.name})
    relatorio = await _asyncio.to_thread(
        restaurar,
        pacote,
        destino,
        anteriores=anteriores,
        apenas=list(parametros.get("apenas") or []) or None,
        sobrescrever=bool(parametros.get("sobrescrever", False)),
        protecao=protecao,
        dispensar_protecao=str(parametros.get("dispensar_protecao") or ""),
    )
    return dict(relatorio.as_dict())


def registro_padrao() -> Registro:
    """Executores que todo Agente conhece."""
    # Import tardio: `backup` importa este modulo para o `Contexto`, e um
    # import no topo fecharia o ciclo.
    from .backup import executar_backup

    registro = Registro()
    registro.registrar("estado", executar_estado)
    registro.registrar("backup", executar_backup)
    registro.registrar("politicas", executar_politicas)
    registro.registrar("situacao", executar_situacao)
    registro.registrar("listar_pacote", executar_listar_pacote)
    registro.registrar("restaurar", executar_restaurar)
    return registro


__all__ = [
    "LEMBRAR_ULTIMOS",
    "Contexto",
    "Executor",
    "Registro",
    "atender",
    "executar_estado",
    "executar_listar_pacote",
    "executar_politicas",
    "executar_restaurar",
    "executar_situacao",
    "registro_padrao",
]
