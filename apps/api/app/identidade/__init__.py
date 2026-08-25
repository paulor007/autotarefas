"""Identidade da plataforma: sessao, provedor OIDC e primeira execucao."""

from .dependencias import (
    ContextoAdministrador,
    ContextoAtual,
    ContextoOperador,
    SessaoBanco,
    contexto_atual,
    sessao_de_banco,
)
from .rotas import roteador
from .sessao_web import COOKIE_SESSAO, SessaoWeb

__all__ = [
    "COOKIE_SESSAO",
    "ContextoAdministrador",
    "ContextoAtual",
    "ContextoOperador",
    "SessaoBanco",
    "SessaoWeb",
    "contexto_atual",
    "roteador",
    "sessao_de_banco",
]
