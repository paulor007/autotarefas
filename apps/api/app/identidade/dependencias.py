"""Dependencias do FastAPI: sessao de banco e contexto da organizacao.

`contexto_atual` e o portao de toda rota que toca dado de cliente. Ele le o
cookie, confere o vinculo no banco e devolve o `Contexto` — o mesmo objeto que
o repositorio exige para montar qualquer consulta. Uma rota que esqueca de
pedir o contexto nao consegue consultar nada: nao ha funcao de leitura que
aceite consulta sem ele.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..db import repositorio as repo
from ..db.atual import banco
from ..db.repositorio import Contexto
from .sessao_web import COOKIE_SESSAO, ler_sessao


def sessao_de_banco() -> Iterator[Session]:
    """Sessao de banco por requisicao, com commit no fim e rollback no erro."""
    with banco().sessao() as sessao:
        yield sessao


SessaoBanco = Annotated[Session, Depends(sessao_de_banco)]


def contexto_atual(request: Request, sessao: SessaoBanco) -> Contexto:
    """
    Contexto de quem esta pedindo. 401 sem sessao, 403 sem vinculo.

    A separacao entre 401 e 403 e util para a tela: "entre" e diferente de
    "voce nao faz parte desta empresa".
    """
    dados = ler_sessao(request.cookies.get(COOKIE_SESSAO))
    if dados is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="sessao ausente ou expirada"
        )
    try:
        return repo.abrir_contexto(
            sessao, usuario_id=dados.usuario_id, organizacao_id=dados.organizacao_id
        )
    except repo.SemAcesso as erro:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(erro)) from erro


ContextoAtual = Annotated[Contexto, Depends(contexto_atual)]


def exigir_administracao(contexto: ContextoAtual) -> Contexto:
    """Portao das rotas de configuracao: parear, autorizar pasta, criar politica."""
    try:
        contexto.exigir_administracao()
    except repo.SemAcesso as erro:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(erro)) from erro
    return contexto


def exigir_operacao(contexto: ContextoAtual) -> Contexto:
    """Portao das rotas que disparam execucao."""
    try:
        contexto.exigir_operacao()
    except repo.SemAcesso as erro:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(erro)) from erro
    return contexto


ContextoAdministrador = Annotated[Contexto, Depends(exigir_administracao)]
ContextoOperador = Annotated[Contexto, Depends(exigir_operacao)]


__all__ = [
    "ContextoAdministrador",
    "ContextoAtual",
    "ContextoOperador",
    "SessaoBanco",
    "contexto_atual",
    "sessao_de_banco",
]
