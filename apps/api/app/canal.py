"""Canal do Agente: conexao de SAIDA, autenticada por assinatura.

Quem conecta e o Agente, da maquina do cliente para o Live. Isso nao e um
detalhe de implementacao — e o que evita pedir a uma micro empresa que abra
porta no roteador, exponha um servico na internet e mantenha isso seguro. Nao
ha nada escutando na rede interna do cliente.

Como a conexao prova quem e:

1. o servidor manda um **desafio** aleatorio, valido para aquela conexao;
2. o Agente devolve o `dispositivo_id` e a assinatura Ed25519 do desafio;
3. o servidor confere com a chave **publica** que guardou no pareamento.

Nao ha segredo compartilhado em lugar nenhum. Um vazamento do banco do servidor
entrega chaves publicas, que nao servem para se passar por dispositivo algum.

O desafio e por conexao e some ao ser usado: sem isso, uma assinatura capturada
uma vez valeria para sempre.

Depois do aperto de mao, o canal transporta **comandos**. Quem pede e sempre o
servidor; quem executa e sempre o Agente, na maquina. Cada comando leva um
identificador proprio, e a resposta o devolve — sem isso, duas respostas que
chegam fora de ordem seriam trocadas uma pela outra.

Comando tem prazo. Um Agente que trava no meio de uma tarefa nao pode deixar a
tela esperando para sempre: passado o prazo, a espera termina com "sem resposta
do dispositivo", que e uma informacao util, e nao um carregando eterno.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.agente.agente.identidade import conferir_assinatura

from .db.atual import banco
from .db.models import Dispositivo, EstadoDispositivo, agora
from .db.repositorio import Contexto, escopo
from .identidade.dependencias import ContextoAtual, SessaoBanco

#: Segundos entre batidas do coracao. Curto o bastante para a tela nao mostrar
#: "conectado" por minutos depois de a maquina cair; longo o bastante para nao
#: virar trafego constante em rede de empresa pequena.
INTERVALO_BATIDA_S = 20.0

#: Quanto tempo sem noticia ate considerar a conexao morta. Duas batidas e meia
#: de folga: uma perdida por congestionamento nao pode derrubar o canal.
TOLERANCIA_S = 50.0

#: Tempo maximo esperando o Agente se identificar depois de conectar. Conexao
#: que abre e nao se identifica e varredura de porta, nao cliente.
TIMEOUT_IDENTIFICACAO_S = 15.0

#: Motivos de fechamento. Codigos proprios (4000+) para o Agente saber se deve
#: tentar de novo ou parar e pedir ajuda.
FECHAR_NAO_IDENTIFICADO = 4001
FECHAR_ASSINATURA_INVALIDA = 4002
FECHAR_DISPOSITIVO_INATIVO = 4003
FECHAR_PROTOCOLO = 4004


#: Prazo padrao de um comando. Generoso: backup de pasta grande demora, e
#: cortar cedo demais transformaria um trabalho em andamento em falha.
PRAZO_COMANDO_S = 600.0


class SemResposta(Exception):
    """O dispositivo nao respondeu ao comando dentro do prazo."""


class DispositivoDesconectado(Exception):
    """Nao ha canal aberto com este dispositivo agora."""


@dataclass
class Conexao:
    """Um Agente conectado agora."""

    dispositivo_id: str
    organizacao_id: str
    nome: str
    socket: WebSocket
    conectado_em: datetime = field(default_factory=agora)
    ultima_batida: datetime = field(default_factory=agora)
    #: Comandos aguardando resposta, por identificador.
    pendentes: dict[str, asyncio.Future[dict[str, Any]]] = field(default_factory=dict)
    #: Ultimo progresso recebido de cada comando. A tela le daqui.
    progresso: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def pedir(
        self,
        acao: str,
        parametros: dict[str, Any] | None = None,
        *,
        prazo_s: float = PRAZO_COMANDO_S,
    ) -> dict[str, Any]:
        """
        Manda um comando e espera o resultado.

        O identificador vai junto e volta na resposta. Ele tambem e o que
        permite ao Agente reconhecer uma reentrega — comando repetido depois
        de uma reconexao nao pode virar backup executado duas vezes.
        """
        identificador = uuid.uuid4().hex
        espera: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.pendentes[identificador] = espera
        try:
            await self.socket.send_json(
                {
                    "tipo": "comando",
                    "id": identificador,
                    "acao": acao,
                    "parametros": parametros or {},
                }
            )
            return await asyncio.wait_for(espera, timeout=prazo_s)
        except TimeoutError as erro:
            msg = f"o dispositivo nao respondeu a '{acao}' em {prazo_s:.0f}s"
            raise SemResposta(msg) from erro
        finally:
            self.pendentes.pop(identificador, None)
            self.progresso.pop(identificador, None)

    def resolver(self, identificador: str, resultado: dict[str, Any]) -> bool:
        """Entrega o resultado a quem estava esperando. False se ninguem estava."""
        espera = self.pendentes.get(identificador)
        if espera is None or espera.done():
            return False
        espera.set_result(resultado)
        return True

    def anotar_progresso(self, identificador: str, dados: dict[str, Any]) -> None:
        """Guarda o ultimo progresso de um comando em andamento."""
        if identificador in self.pendentes:
            self.progresso[identificador] = dados


class Presenca:
    """
    Quem esta conectado neste processo.

    Em memoria de proposito: presenca e um fato do **agora**, e um registro em
    banco sobreviveria a uma queda do servidor dizendo que o Agente esta online
    quando ninguem esta. Com varios processos, cada um conhece os seus — e o
    proximo passo (G.4.2) resolve o roteamento entre eles.
    """

    def __init__(self) -> None:
        self._por_dispositivo: dict[str, Conexao] = {}

    def entrar(self, conexao: Conexao) -> Conexao | None:
        """
        Registra a conexao. Devolve a anterior do mesmo dispositivo, se havia.

        A nova ganha: um Agente que reconecta depois de a rede cair nao pode
        ficar de fora porque o servidor ainda acha que a conexao velha vive.
        """
        anterior = self._por_dispositivo.get(conexao.dispositivo_id)
        self._por_dispositivo[conexao.dispositivo_id] = conexao
        return anterior

    def sair(self, conexao: Conexao) -> None:
        """
        Remove a conexao, se ela ainda for a atual daquele dispositivo.

        Quem estava esperando resposta e avisado na hora. Sem isto, um comando
        enviado a uma maquina que caiu ficaria pendurado ate o prazo — e a
        tela mostraria "executando" para um dispositivo que ja foi embora.
        """
        atual = self._por_dispositivo.get(conexao.dispositivo_id)
        if atual is conexao:
            del self._por_dispositivo[conexao.dispositivo_id]
        for espera in conexao.pendentes.values():
            if not espera.done():
                espera.set_exception(
                    DispositivoDesconectado("o dispositivo desconectou durante o comando")
                )

    def de(self, dispositivo_id: str) -> Conexao | None:
        return self._por_dispositivo.get(dispositivo_id)

    def da_organizacao(self, organizacao_id: str) -> list[Conexao]:
        return [
            conexao
            for conexao in self._por_dispositivo.values()
            if conexao.organizacao_id == organizacao_id
        ]

    def quantos(self) -> int:
        return len(self._por_dispositivo)

    def limpar(self) -> None:
        """Esquece todo mundo. Usado no encerramento e entre testes."""
        self._por_dispositivo.clear()


#: Presenca do processo. Um so, como o registry de jobs.
presenca = Presenca()


# ============================================================
# Aperto de mao
# ============================================================


class ApertoRecusado(Exception):
    """A conexao nao provou ser um dispositivo valido."""

    def __init__(self, mensagem: str, codigo: int) -> None:
        super().__init__(mensagem)
        self.codigo = codigo


def _dispositivo_ativo(sessao: Session, dispositivo_id: str) -> Dispositivo:
    dispositivo = sessao.execute(
        select(Dispositivo).where(Dispositivo.id == dispositivo_id)
    ).scalar_one_or_none()
    if dispositivo is None:
        msg = "dispositivo desconhecido"
        raise ApertoRecusado(msg, FECHAR_ASSINATURA_INVALIDA)
    if dispositivo.estado is not EstadoDispositivo.ATIVO:
        # Revogado ou suspenso continua com a chave privada na maquina. Se o
        # estado nao fosse conferido aqui, revogar seria so um enfeite na tela.
        msg = f"dispositivo {dispositivo.estado.value}"
        raise ApertoRecusado(msg, FECHAR_DISPOSITIVO_INATIVO)
    return dispositivo


async def apertar_maos(socket: WebSocket) -> Conexao:
    """
    Faz o desafio, confere a assinatura e devolve a conexao autenticada.

    Levanta `ApertoRecusado` com o codigo de fechamento apropriado. Quem chama
    fecha o socket: assim o motivo chega ao Agente, que decide entre tentar de
    novo e parar para pedir ajuda.
    """
    desafio = secrets.token_hex(32)
    await socket.send_json({"tipo": "desafio", "nonce": desafio})

    try:
        resposta = await asyncio.wait_for(socket.receive_json(), timeout=TIMEOUT_IDENTIFICACAO_S)
    except (TimeoutError, ValueError) as erro:
        msg = "nao se identificou a tempo"
        raise ApertoRecusado(msg, FECHAR_NAO_IDENTIFICADO) from erro

    if not isinstance(resposta, dict) or resposta.get("tipo") != "identificacao":
        msg = "primeira mensagem nao e identificacao"
        raise ApertoRecusado(msg, FECHAR_PROTOCOLO)

    dispositivo_id = str(resposta.get("dispositivo_id", ""))
    assinatura = str(resposta.get("assinatura", ""))
    if not dispositivo_id or not assinatura:
        msg = "identificacao incompleta"
        raise ApertoRecusado(msg, FECHAR_PROTOCOLO)

    with banco().sessao() as sessao:
        dispositivo = _dispositivo_ativo(sessao, dispositivo_id)
        if not conferir_assinatura(dispositivo.chave_publica, desafio.encode("ascii"), assinatura):
            msg = "assinatura nao confere"
            raise ApertoRecusado(msg, FECHAR_ASSINATURA_INVALIDA)

        dispositivo.ultimo_contato = agora()
        return Conexao(
            dispositivo_id=dispositivo.id,
            organizacao_id=dispositivo.organizacao_id,
            nome=dispositivo.nome,
            socket=socket,
        )


# ============================================================
# Rotas
# ============================================================

roteador = APIRouter(tags=["agente"])


@roteador.websocket("/api/agente/canal")
async def canal(socket: WebSocket) -> None:
    """
    Canal permanente com um Agente.

    O servidor nunca inicia conexao com a maquina do cliente: quem liga e o
    Agente, e esta rota so responde.
    """
    await socket.accept()

    try:
        conexao = await apertar_maos(socket)
    except ApertoRecusado as recusa:
        await socket.close(code=recusa.codigo, reason=str(recusa))
        return
    except WebSocketDisconnect:
        return

    anterior = presenca.entrar(conexao)
    if anterior is not None:
        # Conexao velha do mesmo dispositivo: fecha sem barulho. O Agente que
        # acabou de entrar e o que vale.
        with contextlib.suppress(Exception):
            await anterior.socket.close(code=FECHAR_PROTOCOLO, reason="substituida")

    await socket.send_json(
        {
            "tipo": "pronto",
            "dispositivo_id": conexao.dispositivo_id,
            "nome": conexao.nome,
            "intervalo_batida_s": INTERVALO_BATIDA_S,
        }
    )

    try:
        await _conversar(conexao)
    except WebSocketDisconnect:
        pass
    finally:
        presenca.sair(conexao)
        with contextlib.suppress(Exception), banco().sessao() as sessao:
            dispositivo = sessao.get(Dispositivo, conexao.dispositivo_id)
            if dispositivo is not None:
                dispositivo.ultimo_contato = agora()


async def _conversar(conexao: Conexao) -> None:
    """
    Fica ouvindo o Agente ate a conexao cair.

    Mensagem que nao se reconhece e ignorada, e nao derruba o canal: um Agente
    mais novo pode mandar algo que este servidor ainda nao entende, e derrubar
    a conexao por isso quebraria a atualizacao gradual da frota.
    """
    while True:
        mensagem = await conexao.socket.receive_json()
        if not isinstance(mensagem, dict):
            continue
        tipo = mensagem.get("tipo")

        if tipo == "batida":
            conexao.ultima_batida = agora()
            await conexao.socket.send_json({"tipo": "batida", "eco": True})
        elif tipo == "progresso":
            conexao.ultima_batida = agora()
            conexao.anotar_progresso(str(mensagem.get("comando", "")), mensagem)
        elif tipo == "resultado":
            conexao.ultima_batida = agora()
            conexao.resolver(str(mensagem.get("comando", "")), mensagem)
        elif tipo == "execucoes":
            conexao.ultima_batida = agora()
            await _receber_execucoes(conexao, mensagem)


async def _receber_execucoes(conexao: Conexao, mensagem: dict[str, Any]) -> None:
    """
    Grava o que o Agente executou sozinho e confirma o que entrou.

    A confirmacao e o que autoriza o Agente a parar de reenviar. Sem ela, um
    backup feito com a internet caida ficaria no diario da maquina para sempre
    — ou, pior, seria descartado por idade antes de virar historico.

    A gravacao acontece na organizacao do DISPOSITIVO, e nao na que a mensagem
    disser. Uma maquina nao pode pendurar execucao no historico de outra
    empresa, nem por engano nem de proposito.
    """
    from . import historico

    itens = mensagem.get("itens")
    if not isinstance(itens, list):
        return

    with banco().sessao() as sessao:
        dispositivo = sessao.get(Dispositivo, conexao.dispositivo_id)
        if dispositivo is None:
            return
        aceitos = historico.registrar_do_agente(
            sessao, dispositivo, [item for item in itens if isinstance(item, dict)]
        )
        dispositivo.ultimo_contato = agora()

    await conexao.socket.send_json({"tipo": "execucoes_recebidas", "ids": aceitos})


async def pedir_ao_dispositivo(
    dispositivo_id: str,
    acao: str,
    parametros: dict[str, Any] | None = None,
    *,
    prazo_s: float = PRAZO_COMANDO_S,
) -> dict[str, Any]:
    """
    Manda um comando ao dispositivo e devolve o resultado.

    `DispositivoDesconectado` quando nao ha canal aberto — e diferente de
    "falhou": a maquina pode estar simplesmente desligada, e a tela precisa
    dizer isso em vez de acusar erro de execucao.
    """
    conexao = presenca.de(dispositivo_id)
    if conexao is None:
        msg = "nao ha canal aberto com este dispositivo"
        raise DispositivoDesconectado(msg)
    return await conexao.pedir(acao, parametros, prazo_s=prazo_s)


@roteador.get("/api/agente/conectados")
def conectados(contexto: ContextoAtual, sessao: SessaoBanco) -> dict[str, Any]:
    """
    Quem desta organizacao esta conectado AGORA.

    A tela usa isto para dizer "conectado" apenas quando ha canal aberto. O
    estado no banco diz que o dispositivo existe; so a presenca diz que ele
    esta la.
    """
    abertos = {c.dispositivo_id: c for c in presenca.da_organizacao(contexto.organizacao_id)}
    registros = sessao.execute(escopo(Dispositivo, contexto)).scalars()
    return {
        "conectados": [
            {
                "dispositivo_id": item.id,
                "nome": item.nome,
                "conectado": item.id in abertos,
                "desde": abertos[item.id].conectado_em.isoformat() if item.id in abertos else "",
            }
            for item in registros
        ],
        "total_conectados": len(abertos),
    }


def ha_agente_conectado(organizacao_id: str | None = None) -> bool:
    """
    Ha ao menos um Agente no ar?

    E a fonte da capacidade `agent_connected` anunciada em `/api/health`. Ela
    nunca pode ser declarada por antecipacao: dizer que o modo agente existe
    sem agente nenhum e o tipo de mentira que o produto recusa.
    """
    if organizacao_id is None:
        return presenca.quantos() > 0
    return bool(presenca.da_organizacao(organizacao_id))


__all__ = [
    "FECHAR_ASSINATURA_INVALIDA",
    "FECHAR_DISPOSITIVO_INATIVO",
    "FECHAR_NAO_IDENTIFICADO",
    "FECHAR_PROTOCOLO",
    "INTERVALO_BATIDA_S",
    "PRAZO_COMANDO_S",
    "ApertoRecusado",
    "Conexao",
    "Contexto",
    "DispositivoDesconectado",
    "Presenca",
    "SemResposta",
    "apertar_maos",
    "ha_agente_conectado",
    "pedir_ao_dispositivo",
    "presenca",
    "roteador",
]
