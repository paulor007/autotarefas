"""Canal do Agente visto da maquina: conecta, prova quem e, e se mantem.

A conexao e sempre **de saida**: o Agente liga para o Live. Ninguem precisa
abrir porta no roteador da empresa, e nao ha servico escutando na rede interna.

Reconexao com espera crescente. Rede de empresa pequena cai — troca de
provedor, roteador reiniciado, notebook que dorme. Tentar de novo a cada
segundo transformaria uma queda de dez minutos em dez mil tentativas; esperar
sempre o maximo faria uma queda de dois segundos custar um minuto de ausencia.

Nem toda recusa merece nova tentativa. Dispositivo revogado nao volta a valer
por insistencia: nesse caso o Agente para e diz o motivo, em vez de ficar
batendo na porta para sempre.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from websockets.asyncio.client import connect as conectar_ws
from websockets.exceptions import ConnectionClosed

from . import comandos as mod_comandos
from . import identidade as ident
from .config import Configuracao

#: Espera inicial e teto da espera entre tentativas, em segundos.
ESPERA_INICIAL_S = 1.0
ESPERA_MAXIMA_S = 60.0

#: Fracao de aleatoriedade na espera. Sem isso, cem Agentes que caem juntos
#: (queda de energia num predio) voltam juntos e derrubam o servidor de novo.
JITTER = 0.25

#: Codigos que o servidor usa para dizer "nao adianta tentar de novo".
NAO_INSISTIR = frozenset({4002, 4003})

#: Quanto tempo esperar pelo aperto de mao antes de desistir da tentativa.
TIMEOUT_APERTO_S = 20.0


class CanalRecusado(Exception):
    """O servidor recusou de um jeito que nao melhora com insistencia."""


@dataclass
class Estado:
    """O que o Agente sabe sobre a propria conexao. Vai para o `estado`."""

    conectado: bool = False
    tentativas: int = 0
    ultimo_erro: str = ""


def _codigo_de_fechamento(fechada: ConnectionClosed) -> int:
    """
    Codigo com que o servidor fechou.

    `ConnectionClosed.code` foi descontinuado; o codigo agora mora no quadro
    recebido. Sem isto, a distincao entre "tente de novo" e "pare e peca
    ajuda" se perderia — e o Agente insistiria para sempre num dispositivo
    revogado.
    """
    recebido = getattr(fechada, "rcvd", None)
    if recebido is not None and getattr(recebido, "code", None) is not None:
        return int(recebido.code)
    return 1006


def _espera(tentativa: int) -> float:
    """Espera crescente com aleatoriedade, limitada pelo teto."""
    dobras = float(2 ** max(0, tentativa - 1))
    base = min(ESPERA_INICIAL_S * dobras, ESPERA_MAXIMA_S)
    # Aleatoriedade aqui e para ESPALHAR reconexoes no tempo, nao para
    # proteger nada: um gerador previsivel so permitiria adivinhar quando
    # um Agente tentaria de novo, o que nao abre porta nenhuma.
    sorteio: float = random.uniform(-JITTER, JITTER)  # noqa: S311  # nosec B311
    return base * (1 + sorteio)


def url_do_canal(servidor: str) -> str:
    """
    Endereco do canal a partir do endereco do Live.

    `https` vira `wss` e `http` vira `ws`: um Agente configurado com HTTPS nao
    pode cair para texto claro sem ninguem perceber.
    """
    base = servidor.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :] + "/api/agente/canal"
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :] + "/api/agente/canal"
    return base + "/api/agente/canal"


async def apertar_maos(
    conexao: object, configuracao: Configuracao, identidade: ident.Identidade
) -> dict[str, object]:
    """
    Responde ao desafio do servidor e espera o `pronto`.

    A assinatura e do desafio DAQUELA conexao. Uma assinatura antiga nao serve
    — e por isso que capturar o trafego uma vez nao da acesso depois.
    """
    bruto = await asyncio.wait_for(conexao.recv(), timeout=TIMEOUT_APERTO_S)  # type: ignore[attr-defined]
    desafio = json.loads(bruto)
    if desafio.get("tipo") != "desafio" or not desafio.get("nonce"):
        msg = "o servidor nao mandou desafio"
        raise CanalRecusado(msg)

    await conexao.send(  # type: ignore[attr-defined]
        json.dumps(
            {
                "tipo": "identificacao",
                "dispositivo_id": configuracao.dispositivo_id,
                "assinatura": identidade.assinar(str(desafio["nonce"]).encode("ascii")),
            }
        )
    )

    resposta = json.loads(await asyncio.wait_for(conexao.recv(), timeout=TIMEOUT_APERTO_S))  # type: ignore[attr-defined]
    if resposta.get("tipo") != "pronto":
        msg = f"o servidor nao aceitou a identificacao: {resposta}"
        raise CanalRecusado(msg)
    return dict(resposta)


async def bater_coracao(conexao: object, intervalo_s: float) -> None:
    """
    Manda batidas ate a conexao cair.

    Sem elas, uma conexao morta por NAT ou firewall silencioso continuaria
    "aberta" dos dois lados, e a tela mostraria um Agente conectado que nao
    responde a comando nenhum.
    """
    while True:
        await asyncio.sleep(intervalo_s)
        await conexao.send(json.dumps({"tipo": "batida"}))  # type: ignore[attr-defined]


async def atender_comandos(
    conexao: object,
    configuracao: Configuracao,
    registro: mod_comandos.Registro,
) -> None:
    """
    Le mensagens do servidor e executa os comandos, ate a conexao cair.

    Cada comando roda em sequencia. Paralelismo aqui seria facil e errado: dois
    backups simultaneos sobre as mesmas pastas disputariam disco e produziriam
    pacotes que se contradizem.
    """

    async def relatar(dados: dict[str, object]) -> None:
        await conexao.send(json.dumps({**dados, "tipo": "progresso"}))  # type: ignore[attr-defined]

    contexto = mod_comandos.Contexto(configuracao=configuracao, relatar=relatar)

    async for bruto in conexao:  # type: ignore[attr-defined]
        try:
            mensagem = json.loads(bruto)
        except json.JSONDecodeError:
            continue
        if not isinstance(mensagem, dict) or mensagem.get("tipo") != "comando":
            continue
        resultado = await mod_comandos.atender(mensagem, registro, contexto)
        await conexao.send(json.dumps(resultado))  # type: ignore[attr-defined]


async def manter_conectado(
    configuracao: Configuracao,
    identidade: ident.Identidade,
    *,
    estado: Estado | None = None,
    ao_conectar: Callable[[dict[str, object]], Awaitable[None]] | None = None,
    tentativas_maximas: int | None = None,
    registro: mod_comandos.Registro | None = None,
) -> Estado:
    """
    Conecta e reconecta enquanto for util tentar.

    `tentativas_maximas` existe para a suite: em producao o Agente insiste para
    sempre, porque desistir significaria parar de fazer backup em silencio.
    """
    situacao = estado or Estado()
    endereco = url_do_canal(configuracao.servidor)
    # O registro sobrevive as reconexoes de proposito: a memoria de comandos ja
    # atendidos e o que impede uma reentrega, depois de a rede voltar, de virar
    # um segundo backup.
    conhecidos = registro if registro is not None else mod_comandos.registro_padrao()

    while True:
        situacao.tentativas += 1
        try:
            async with conectar_ws(endereco) as conexao:
                pronto = await apertar_maos(conexao, configuracao, identidade)
                situacao.conectado = True
                situacao.ultimo_erro = ""
                if ao_conectar is not None:
                    await ao_conectar(pronto)

                intervalo = float(str(pronto.get("intervalo_batida_s") or 20.0))
                batidas = asyncio.create_task(bater_coracao(conexao, intervalo))
                try:
                    await atender_comandos(conexao, configuracao, conhecidos)
                finally:
                    batidas.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await batidas
        except ConnectionClosed as fechada:
            situacao.conectado = False
            codigo = _codigo_de_fechamento(fechada)
            situacao.ultimo_erro = f"conexao fechada ({codigo})"
            if codigo in NAO_INSISTIR:
                # Revogado ou assinatura invalida: insistir nao resolve, e
                # ficar tentando esconderia o problema de quem precisa agir.
                situacao.ultimo_erro = (
                    f"o servidor recusou este dispositivo ({codigo}); pareie novamente pelo Live"
                )
                return situacao
        except (OSError, CanalRecusado, TimeoutError, json.JSONDecodeError) as erro:
            situacao.conectado = False
            situacao.ultimo_erro = str(erro)

        if tentativas_maximas is not None and situacao.tentativas >= tentativas_maximas:
            return situacao
        await asyncio.sleep(_espera(situacao.tentativas))


__all__ = [
    "ESPERA_MAXIMA_S",
    "NAO_INSISTIR",
    "CanalRecusado",
    "Estado",
    "apertar_maos",
    "atender_comandos",
    "bater_coracao",
    "manter_conectado",
    "url_do_canal",
]
