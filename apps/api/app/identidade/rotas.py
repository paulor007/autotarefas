"""Rotas de identidade: estado, entrada, retorno do provedor, saida, bootstrap.

Nenhuma rota aqui inventa capacidade. `GET /api/auth/estado` diz a verdade
sobre o que existe: se nao ha provedor configurado, a tela mostra isso em vez
de um botao que levaria a lugar nenhum.
"""

from __future__ import annotations

import secrets
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from ..config import settings
from ..db.models import Usuario
from . import bootstrap, oidc, reentrada
from .dependencias import SessaoBanco
from .entrada import acolher, organizacoes_do_usuario
from .oidc import ErroDeIdentidade
from .sessao_web import (
    COOKIE_FLUXO,
    COOKIE_SESSAO,
    FLUXO_MINUTOS,
    SessaoWeb,
    atributos_do_cookie,
    escrever_fluxo,
    escrever_sessao,
    ler_fluxo,
    ler_sessao,
)

roteador = APIRouter(prefix="/api/auth", tags=["identidade"])

#: Cliente HTTP usado para falar com o provedor. E uma variavel de modulo para
#: a suite trocar por um cliente ligado ao provedor de teste — sem isso, testar
#: OIDC exigiria um provedor real e uma credencial do proprietario.
cliente_http: httpx.Client | None = None


def _redirect_uri() -> str:
    return f"{settings.public_base_url.rstrip('/')}/api/auth/retorno"


def _provedor() -> oidc.Provedor:
    if not settings.oidc_configurado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="nenhum provedor de identidade configurado",
        )
    try:
        return oidc.descobrir(settings.oidc_issuer, cliente=cliente_http)
    except ErroDeIdentidade as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro


def _gravar_sessao(resposta: Response, sessao: SessaoWeb) -> None:
    resposta.set_cookie(
        COOKIE_SESSAO,
        escrever_sessao(sessao),
        **atributos_do_cookie(duracao_s=settings.session_hours * 3600),  # type: ignore[arg-type]
    )


# ============================================================
# Estado
# ============================================================


@roteador.get("/estado")
def estado(request: Request, sessao: SessaoBanco) -> dict[str, Any]:
    """
    O que a tela precisa saber antes de desenhar qualquer botao.

    `precisa_bootstrap` so e verdadeiro com o banco vazio; `provedor` so e
    verdadeiro com issuer, client_id e segredo presentes. A tela nao adivinha
    nada a partir daqui.
    """
    dados = ler_sessao(request.cookies.get(COOKIE_SESSAO))
    corpo: dict[str, Any] = {
        "autenticado": False,
        "provedor_configurado": settings.oidc_configurado,
        "precisa_bootstrap": bootstrap.esta_vazio(sessao),
        "usuario": None,
        "organizacao": None,
        "organizacoes": [],
    }
    if dados is None:
        return corpo

    usuario = sessao.get(Usuario, dados.usuario_id)
    if usuario is None:
        return corpo

    vinculo = next((v for v in usuario.vinculos if v.organizacao_id == dados.organizacao_id), None)
    if vinculo is None:
        return corpo

    corpo["autenticado"] = True
    corpo["usuario"] = {"id": usuario.id, "nome": usuario.nome, "email": usuario.email}
    corpo["organizacao"] = {
        "id": vinculo.organizacao.id,
        "nome": vinculo.organizacao.nome,
        "papel": vinculo.papel.value,
    }
    corpo["organizacoes"] = [
        {"id": org.id, "nome": org.nome} for org in organizacoes_do_usuario(sessao, usuario.id)
    ]
    return corpo


# ============================================================
# Login pelo provedor
# ============================================================


@roteador.get("/entrar")
def entrar() -> RedirectResponse:
    """Manda a pessoa ao provedor, guardando state, nonce e verificador PKCE."""
    provedor = _provedor()
    estado_ = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    verificador, desafio = oidc.novo_verificador()

    destino = oidc.url_de_autorizacao(
        provedor,
        client_id=settings.oidc_client_id,
        redirect_uri=_redirect_uri(),
        state=estado_,
        nonce=nonce,
        desafio=desafio,
    )
    resposta = RedirectResponse(destino, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    resposta.set_cookie(
        COOKIE_FLUXO,
        escrever_fluxo({"state": estado_, "nonce": nonce, "verificador": verificador}),
        **atributos_do_cookie(duracao_s=FLUXO_MINUTOS * 60),  # type: ignore[arg-type]
    )
    return resposta


@roteador.get("/retorno")
def retorno(request: Request, sessao: SessaoBanco, code: str = "", state: str = "") -> Response:
    """
    Volta do provedor: confere state, troca o codigo, valida o token, cria a sessao.

    O cookie de fluxo e apagado em qualquer desfecho. Deixa-lo vivo permitiria
    reapresentar o mesmo `state` numa segunda tentativa.
    """
    fluxo = ler_fluxo(request.cookies.get(COOKIE_FLUXO))
    if fluxo is None or not code or not secrets.compare_digest(state, fluxo.get("state", "")):
        resposta_erro = JSONResponse(
            {"detail": "retorno de login invalido"}, status_code=status.HTTP_400_BAD_REQUEST
        )
        resposta_erro.delete_cookie(COOKIE_FLUXO, path="/")
        return resposta_erro

    provedor = _provedor()
    try:
        tokens = oidc.trocar_codigo(
            provedor,
            codigo=code,
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            redirect_uri=_redirect_uri(),
            verificador=fluxo.get("verificador", ""),
            cliente=cliente_http,
        )
        identidade = oidc.conferir_id_token(
            str(tokens["id_token"]),
            provedor,
            client_id=settings.oidc_client_id,
            nonce=fluxo.get("nonce", ""),
            cliente=cliente_http,
        )
        acolhida = acolher(sessao, identidade)
    except ErroDeIdentidade as erro:
        resposta_erro = JSONResponse({"detail": str(erro)}, status_code=status.HTTP_400_BAD_REQUEST)
        resposta_erro.delete_cookie(COOKIE_FLUXO, path="/")
        return resposta_erro

    resposta = RedirectResponse(
        settings.public_base_url or "/", status_code=status.HTTP_303_SEE_OTHER
    )
    resposta.delete_cookie(COOKIE_FLUXO, path="/")
    _gravar_sessao(
        resposta,
        SessaoWeb(usuario_id=acolhida.usuario_id, organizacao_id=acolhida.organizacao_id),
    )
    return resposta


@roteador.post("/sair")
def sair() -> Response:
    """Encerra a sessao no navegador."""
    resposta = JSONResponse({"ok": True})
    resposta.delete_cookie(COOKIE_SESSAO, path="/")
    return resposta


# ============================================================
# Primeira execucao
# ============================================================


class PedidoDeBootstrap(BaseModel):
    """Dados do primeiro acesso."""

    convite: str = Field(min_length=8)
    organizacao: str = Field(min_length=1, max_length=200)
    email: EmailStr
    nome: str = Field(default="", max_length=200)


@roteador.post("/bootstrap")
def primeiro_acesso(pedido: PedidoDeBootstrap, sessao: SessaoBanco) -> Response:
    """Cria a primeira organizacao e o primeiro dono, uma unica vez."""
    try:
        criado = bootstrap.criar_primeira_organizacao(
            sessao,
            token=pedido.convite,
            nome_organizacao=pedido.organizacao,
            email=str(pedido.email),
            nome=pedido.nome,
            agora_s=time.time(),
        )
    except bootstrap.BootstrapIndisponivel as erro:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(erro)) from erro

    resposta = JSONResponse({"ok": True, "organizacao": criado.organizacao_id})
    _gravar_sessao(
        resposta,
        SessaoWeb(usuario_id=criado.usuario_id, organizacao_id=criado.organizacao_id),
    )
    return resposta


@roteador.get("/reentrar")
def reentrar(request: Request, chave: str = "") -> Response:
    """
    Entrada pelo link impresso no console, quando nao ha provedor.

    Existe porque a alternativa e pior que qualquer risco que ela traga: um
    servidor sem OIDC perde o dono quando a sessao vence, e os dados ficam
    trancados sem ninguem para abrir.

    Quem tem o console da maquina ja controla o servico — o link nao concede
    nada que essa pessoa nao pudesse tomar de outro jeito. Com OIDC no ar, esta
    rota nao serve para nada: nenhuma chave chega a ser emitida.
    """
    del request
    try:
        usada = reentrada.usar(chave, agora_s=time.time())
    except reentrada.ReentradaIndisponivel as erro:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(erro)) from erro

    resposta = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    _gravar_sessao(
        resposta,
        SessaoWeb(usuario_id=usada.usuario_id, organizacao_id=usada.organizacao_id),
    )
    return resposta


__all__ = ["roteador"]
