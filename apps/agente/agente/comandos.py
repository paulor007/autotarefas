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


def registro_padrao() -> Registro:
    """Executores que todo Agente conhece."""
    registro = Registro()
    registro.registrar("estado", executar_estado)
    return registro


__all__ = [
    "LEMBRAR_ULTIMOS",
    "Contexto",
    "Executor",
    "Registro",
    "atender",
    "executar_estado",
    "registro_padrao",
]
