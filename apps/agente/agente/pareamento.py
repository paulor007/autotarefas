"""Pareamento visto do lado do Agente: da maquina para o Live.

O que sai daqui: a chave **publica**, o nome da maquina, o sistema e a versao
do Agente. O que nunca sai: a chave privada.

Se o pareamento falhar depois de o servidor ter criado o dispositivo, a
configuracao local nao e gravada — e a proxima tentativa esbarra em "esta
maquina ja esta pareada". E o desfecho certo: melhor exigir que alguem olhe do
que deixar dois registros da mesma maquina, um deles orfao.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass

import httpx

from . import identidade as ident
from .config import Configuracao, Local

#: Versao do Agente. Vai ao servidor no pareamento e aparece na tela de
#: dispositivos: saber qual maquina esta velha e o primeiro passo para
#: atualizar.
VERSAO = "0.1.0"

#: Tempo maximo esperando o servidor responder ao pareamento.
TIMEOUT_S = 20.0


class PareamentoFalhou(Exception):
    """O servidor recusou, ou nao foi possivel falar com ele."""


@dataclass(frozen=True)
class Pareado:
    """O que o servidor devolveu."""

    dispositivo_id: str
    organizacao_id: str
    nome: str
    impressao: str


def descrever_maquina() -> tuple[str, str]:
    """(nome sugerido, descricao do sistema) desta maquina."""
    nome = platform.node() or "Dispositivo"
    sistema = f"{platform.system()} {platform.release()}".strip()
    return nome, sistema


def parear(
    *,
    servidor: str,
    codigo: str,
    guarda: ident.Guarda,
    local: Local,
    nome: str = "",
    cliente: httpx.Client | None = None,
) -> Pareado:
    """
    Registra esta maquina numa organizacao e grava a configuracao local.

    A identidade e criada **antes** da chamada e sobrevive a uma falha de
    rede: repetir o comando reaproveita o mesmo par de chaves, em vez de
    deixar chaves orfas espalhadas a cada tentativa.
    """
    identidade, _ = ident.obter_ou_criar(guarda)
    sugerido, sistema = descrever_maquina()
    base = servidor.rstrip("/")

    http = cliente or httpx.Client(timeout=TIMEOUT_S)
    try:
        resposta = http.post(
            f"{base}/api/dispositivos/parear",
            json={
                "codigo": codigo,
                "chave_publica": identidade.publica_em_base64,
                "nome": nome.strip() or sugerido,
                "sistema": sistema,
                "versao_agente": VERSAO,
            },
        )
    except httpx.HTTPError as erro:
        msg = f"nao foi possivel falar com o servidor: {erro}"
        raise PareamentoFalhou(msg) from erro

    if resposta.status_code != httpx.codes.OK:
        detalhe = _detalhe(resposta)
        msg = f"o servidor recusou o pareamento: {detalhe}"
        raise PareamentoFalhou(msg)

    dados = resposta.json()
    resultado = Pareado(
        dispositivo_id=str(dados.get("dispositivo_id", "")),
        organizacao_id=str(dados.get("organizacao_id", "")),
        nome=str(dados.get("nome", "")),
        impressao=str(dados.get("impressao", "")),
    )
    if not resultado.dispositivo_id:
        msg = "o servidor respondeu sem identificador de dispositivo"
        raise PareamentoFalhou(msg)

    atual = local.carregar()
    local.gravar(
        Configuracao(
            servidor=base,
            dispositivo_id=resultado.dispositivo_id,
            nome=resultado.nome,
            raizes=atual.raizes,
            pareado_em=_agora_iso(),
        )
    )
    return resultado


def _detalhe(resposta: httpx.Response) -> str:
    """Mensagem do servidor, ou o codigo HTTP quando nao houver."""
    try:
        corpo = resposta.json()
    except ValueError:
        return f"HTTP {resposta.status_code}"
    return str(corpo.get("detail") or f"HTTP {resposta.status_code}")


def _agora_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="seconds")


__all__ = ["TIMEOUT_S", "VERSAO", "Pareado", "PareamentoFalhou", "descrever_maquina", "parear"]
