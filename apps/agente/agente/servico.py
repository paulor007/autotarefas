"""O serviço do Agente: canal e agendador rodando juntos, para sempre.

Duas coisas acontecem ao mesmo tempo, e nenhuma pode derrubar a outra:

- o **canal** mantém a conexão de saída com o Live, para receber comandos e
  políticas;
- o **agendador** dispara os backups no horário, lendo a política gravada no
  disco.

A independência é o ponto. Se o agendador dependesse do canal, o backup pararia
sempre que a internet caísse — justamente quando ninguém está olhando. Se o
canal dependesse do agendador, um backup de duas horas deixaria a máquina
"desligada" na tela desse tempo todo.

O que este módulo NÃO faz: decidir o que copiar. Isso é da política, e a
política passa pela guarda de pastas autorizadas como qualquer outro pedido.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from . import canal as mod_canal
from . import comandos as mod_comandos
from . import identidade as ident
from .agendador import Agendador, PoliticaLocal
from .backup import executar_politica
from .config import Local
from .diario import Diario, Execucao, agora_iso


class Servico:
    """Amarra canal, agendador e execução numa coisa só."""

    def __init__(self, local: Local, guarda: ident.Guarda) -> None:
        self.local = local
        self.guarda = guarda
        self.agendador = Agendador(local=local, executar=self._executar_politica)
        self.registro = mod_comandos.registro_padrao()
        self.estado_do_canal = mod_canal.Estado()
        self.diario = Diario(pasta=local.pasta)

    async def _executar_politica(self, item: PoliticaLocal) -> dict[str, Any]:
        """
        Roda uma política agendada, lendo a configuração do disco a cada vez.

        Reler importa: a política pode ter sido alterada entre o agendamento e
        a execução — alguém autorizou outra pasta, mudou o destino. Usar a
        cópia em memória copiaria o que era verdade horas atrás.

        O resultado é gravado no diário **antes** de qualquer tentativa de
        avisar o servidor. A internet costuma estar caída de madrugada, que é
        justamente quando o agendamento roda; se o registro dependesse do
        envio, esse backup não existiria no histórico do Live.
        """
        comecou = agora_iso()
        try:
            # A identidade da politica viaja junto: e ela que define em qual
            # pasta o pacote cai, e portanto quais pacotes a retencao desta
            # politica pode alcancar. Sem isso, duas politicas nesta maquina
            # dividiriam o mesmo monte e apagariam pacote uma da outra.
            ficha = await executar_politica(
                item.politica,
                self.local.carregar(),
                self._relatar_do_agendamento(item),
                politica_id=item.id,
                politica_nome=item.nome,
            )
        except Exception as erro:
            self._anotar(item, comecou, {"ok": False, "erro": f"{type(erro).__name__}: {erro}"})
            raise
        self._anotar(item, comecou, ficha)
        return ficha

    def _relatar_do_agendamento(self, item: PoliticaLocal) -> Any:
        """
        Como contar as fases de um backup do horario, quando ha canal.

        O backup disparado da tela ja reporta: o comando traz o proprio
        `relatar`. O do agendamento nao tinha por onde — e quem estivesse
        olhando a tela as 03:00 veria uma linha aparecer pronta, sem nada
        entre o silencio e o resultado.

        Duas regras, e as duas existem para isto continuar sendo enfeite:

        **Nao segura o backup.** Se nao ha canal, `relatar` e `None` e o
        backup roda igual — que e o caso normal de uma madrugada com a
        internet caida.

        **Nao derruba o backup.** Qualquer erro ao enviar e engolido. Um
        socket que fechou no meio da copia nao pode transformar um backup que
        ia dar certo numa falha registrada.
        """

        async def relatar(dados: dict[str, Any]) -> None:
            enviar = self.estado_do_canal.relatar
            if enviar is None:
                return
            with contextlib.suppress(Exception):
                await enviar(
                    {
                        **dados,
                        # O servidor guarda progresso POR COMANDO. Um backup do
                        # horario nao tem comando; a politica faz esse papel, e
                        # o prefixo evita colisao com um id de comando.
                        "comando": f"politica:{item.id}",
                        "politica_id": item.id,
                        "politica_nome": item.nome,
                        "origem": "agendamento",
                    }
                )

        return relatar

    def _anotar(self, item: PoliticaLocal, comecou: str, ficha: dict[str, Any]) -> None:
        """Escreve no diário o que esta execução produziu."""
        deu_certo = bool(ficha.get("ok", False))
        artefato = (
            {
                "nome": str(ficha.get("pacote", "")),
                "tamanho_bytes": int(ficha.get("tamanho_bytes", 0) or 0),
                "sha256": str(ficha.get("sha256", "")),
                # Onde o pacote está do ponto de vista do DISPOSITIVO. Nunca o
                # caminho local do cliente: a estrutura de pastas da empresa
                # não é assunto do servidor.
                "localizacao": "dispositivo",
            }
            if deu_certo and ficha.get("pacote")
            else None
        )
        self.diario.registrar(
            Execucao(
                politica_id=item.id,
                politica_nome=item.nome,
                iniciada_em=comecou,
                terminada_em=agora_iso(),
                resultado=_resultado(deu_certo, ficha),
                arquivos=int(ficha.get("arquivos", 0) or 0),
                bytes_copiados=int(ficha.get("tamanho_bytes", 0) or 0),
                ressalva=_ressalva(ficha, item.tentativa),
                artefato=artefato,
                nuvem_pendente=bool(ficha.get("nuvem_pendente", False)) and artefato is not None,
            )
        )

    async def _canal(self) -> None:
        """Mantém a conexão de saída, reconectando enquanto valer a pena."""
        identidade = ident.carregar(self.guarda)
        await mod_canal.manter_conectado(
            self.local.carregar(),
            identidade,
            estado=self.estado_do_canal,
            registro=self.registro,
            diario=self.diario,
        )

    async def rodar(self, *, passadas_do_agendador: int | None = None) -> None:
        """
        Sobe as duas tarefas e espera.

        Uma exceção numa não cancela a outra: `gather` com `return_exceptions`
        deixa a que sobreviveu continuar. Um canal que caiu não pode levar o
        agendamento junto — é exatamente aí que o backup mais importa.
        """
        # O executor de comandos precisa alcançar o agendador para gravar as
        # políticas que o servidor manda.
        self._ensinar_o_agendador_ao_canal()

        canal = asyncio.create_task(self._canal())
        agendamento = asyncio.create_task(self.agendador.rodar(passadas=passadas_do_agendador))
        tarefas = [canal, agendamento]

        try:
            if passadas_do_agendador is None:
                # Producao: as duas rodam para sempre, e uma que morra nao
                # cancela a outra.
                await asyncio.gather(*tarefas, return_exceptions=True)
            else:
                # Execucao limitada (suite): espera o agendador terminar as
                # passadas pedidas. O canal, por desenho, tentaria reconectar
                # para sempre — esperar por ele seria esperar sem fim.
                await asyncio.wait({agendamento}, return_when=asyncio.ALL_COMPLETED)
        finally:
            for tarefa in tarefas:
                tarefa.cancel()
            for tarefa in tarefas:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await tarefa

    def _ensinar_o_agendador_ao_canal(self) -> None:
        """
        Faz o `Contexto` dos comandos carregar este agendador.

        O canal monta o contexto por conexão; envolver os executores aqui é o
        que liga um ao outro sem o canal precisar conhecer o agendador.
        """
        agendador = self.agendador
        originais = dict(self.registro.executores)

        def com_agendador(executor: mod_comandos.Executor) -> mod_comandos.Executor:
            async def envolvido(
                parametros: dict[str, Any], contexto: mod_comandos.Contexto
            ) -> dict[str, Any]:
                contexto.agendador = agendador
                return await executor(parametros, contexto)

            return envolvido

        for acao, executor in originais.items():
            self.registro.registrar(acao, com_agendador(executor))


def _ressalva(ficha: dict[str, Any], tentativa: int) -> str:
    """
    O que deu errado, e em qual tentativa.

    O numero nao e detalhe tecnico: "falhou" e "falhou na 2a tentativa" pedem
    coisas diferentes de quem le. A segunda diz que o Agente insistiu — e que o
    problema nao foi um tropeco.

    Cada tentativa vira uma linha propria no historico. Juntar as tres numa so
    esconderia justamente o que prova que o retry aconteceu.
    """
    texto = str(ficha.get("ressalva") or ficha.get("erro") or "")
    if tentativa > 1:
        return f"tentativa {tentativa}: {texto}".strip()
    return texto


def _resultado(deu_certo: bool, ficha: dict[str, Any]) -> str:
    """O nome que o Live usa. "com_ressalva" nao e sucesso nem falha."""
    if not deu_certo:
        return "falha"
    return "com_ressalva" if ficha.get("com_ressalva") else "sucesso"


async def rodar_servico(local: Local, guarda: ident.Guarda) -> None:
    """Ponto de entrada do serviço. Em produção, não retorna."""
    servico = Servico(local=local, guarda=guarda)
    servico.agendador.carregar()
    await servico.rodar()


__all__ = ["Servico", "rodar_servico"]
