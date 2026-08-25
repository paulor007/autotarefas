"""Sessao do navegador: cookie proprio, assinado, com validade.

O token do provedor de identidade **nunca** chega ao frontend. O que o
navegador guarda e um cookie assinado com dois campos — quem e a pessoa e em
qual organizacao ela esta trabalhando. Se o cookie for adulterado, a assinatura
nao fecha e a sessao simplesmente nao existe.

`HttpOnly` para JavaScript nao conseguir ler; `SameSite=Lax` para o cookie nao
viajar em requisicao disparada por outro site; `Secure` quando ha HTTPS.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..config import settings

#: Nome do cookie. Prefixo do produto para nao colidir com outro servico no
#: mesmo dominio durante o desenvolvimento.
COOKIE_SESSAO = "autotarefas_sessao"

#: Cookie curto que guarda state, nonce e verificador PKCE entre a ida ao
#: provedor e a volta. Separado da sessao porque morre assim que o login
#: termina — e porque ele existe justamente quando ainda nao ha sessao.
COOKIE_FLUXO = "autotarefas_fluxo"

#: Minutos de vida do cookie de fluxo. Login que demora mais que isso e login
#: abandonado, ou tentativa de reaproveitar um `state` antigo.
FLUXO_MINUTOS = 10

_SAL_SESSAO = "autotarefas.sessao"  # nosec B105 — sal de assinatura, nao senha
_SAL_FLUXO = "autotarefas.fluxo"  # nosec B105 — idem

#: Segredo sorteado quando `SESSION_SECRET` nao vem do ambiente. Nao ha valor
#: padrao no codigo: um segredo publicado no repositorio nao assina nada.
_SEGREDO_SORTEADO = secrets.token_urlsafe(32)


def segredo() -> str:
    """Segredo de assinatura em uso."""
    return settings.session_secret or _SEGREDO_SORTEADO


def segredo_e_efemero() -> bool:
    """True quando o segredo foi sorteado: a sessao morre no reinicio."""
    return not settings.session_secret


@dataclass(frozen=True)
class SessaoWeb:
    """Quem esta logado, e por qual organizacao."""

    usuario_id: str
    organizacao_id: str


def _serializador(sal: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(segredo(), salt=sal)


def escrever_sessao(sessao: SessaoWeb) -> str:
    """Valor assinado do cookie de sessao."""
    return _serializador(_SAL_SESSAO).dumps(
        {"usuario": sessao.usuario_id, "organizacao": sessao.organizacao_id}
    )


def ler_sessao(valor: str | None) -> SessaoWeb | None:
    """
    Le e confere o cookie. Qualquer problema vira `None`, nunca excecao.

    Cookie invalido nao e erro do servidor: e visitante sem sessao. Levantar
    excecao aqui transformaria um cookie velho num 500 na cara da pessoa.
    """
    if not valor:
        return None
    try:
        dados = _serializador(_SAL_SESSAO).loads(valor, max_age=settings.session_hours * 3600)
    except (BadSignature, SignatureExpired):
        return None
    usuario = str(dados.get("usuario") or "")
    organizacao = str(dados.get("organizacao") or "")
    if not usuario or not organizacao:
        return None
    return SessaoWeb(usuario_id=usuario, organizacao_id=organizacao)


def escrever_fluxo(dados: dict[str, str]) -> str:
    """Valor assinado do cookie de fluxo de login."""
    return _serializador(_SAL_FLUXO).dumps(dados)


def ler_fluxo(valor: str | None) -> dict[str, str] | None:
    """Le o cookie de fluxo, ou `None` se estiver ausente, velho ou torto."""
    if not valor:
        return None
    try:
        dados = _serializador(_SAL_FLUXO).loads(valor, max_age=FLUXO_MINUTOS * 60)
    except (BadSignature, SignatureExpired):
        return None
    return {str(chave): str(item) for chave, item in dict(dados).items()}


def atributos_do_cookie(*, duracao_s: int) -> dict[str, object]:
    """Atributos de seguranca comuns aos dois cookies."""
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "max_age": duracao_s,
        "path": "/",
    }


__all__ = [
    "COOKIE_FLUXO",
    "COOKIE_SESSAO",
    "FLUXO_MINUTOS",
    "SessaoWeb",
    "atributos_do_cookie",
    "escrever_fluxo",
    "escrever_sessao",
    "ler_fluxo",
    "ler_sessao",
    "segredo_e_efemero",
]
