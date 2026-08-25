"""Cliente OIDC: o AutoTarefas entra como Relying Party, nunca como provedor.

Fluxo Authorization Code com PKCE, cliente confidencial. Tres protecoes que
nao sao opcionais e cada uma cobre um ataque diferente:

- **state**: amarra a volta do provedor ao pedido que saiu daqui. Sem ele,
  alguem induz a vitima a completar um login que o atacante comecou.
- **nonce**: amarra o `id_token` a esta tentativa. Sem ele, um token valido
  capturado antes pode ser reapresentado.
- **PKCE**: amarra a troca do codigo a quem o pediu. Sem ele, um codigo
  interceptado no retorno vira sessao na mao de outro.

O `id_token` e conferido por assinatura contra o JWKS do provedor, e depois em
`iss`, `aud`, `exp` e `nonce`. Aceitar o conteudo do token sem conferir a
assinatura seria confiar em qualquer um que saiba montar um JSON.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from authlib.jose import JsonWebKey, JsonWebToken
from authlib.jose.errors import JoseError

#: Folga na conferencia de expiracao, para relogio levemente adiantado entre
#: o provedor e este servidor. Trinta segundos e o costume; mais que isso
#: comeca a aceitar token realmente vencido.
_FOLGA_S = 30

#: Tempo maximo esperando o provedor. Um provedor lento nao pode segurar um
#: worker do servidor indefinidamente.
_TIMEOUT_S = 10.0

_ALGORITMOS = ["RS256", "ES256", "RS384", "RS512", "ES384", "ES512"]


class ErroDeIdentidade(Exception):
    """Algo no fluxo de login nao fecha. A mensagem vai para o log, nao para a tela."""


@dataclass(frozen=True)
class Provedor:
    """Endereços do provedor, lidos do documento de descoberta."""

    emissor: str
    autorizacao: str
    token: str
    jwks: str


@dataclass(frozen=True)
class Identidade:
    """O que o provedor afirma sobre a pessoa, ja conferido."""

    emissor: str
    assunto: str
    email: str
    nome: str
    email_verificado: bool


def _cliente(cliente: httpx.Client | None) -> httpx.Client:
    return cliente or httpx.Client(timeout=_TIMEOUT_S, follow_redirects=False)


def descobrir(emissor: str, *, cliente: httpx.Client | None = None) -> Provedor:
    """
    Le `.well-known/openid-configuration` do provedor.

    Descoberta em vez de endereços fixos e o que faz Google, Entra, Keycloak e
    Authentik funcionarem trocando uma variavel de ambiente, sem codigo novo.
    """
    base = emissor.rstrip("/")
    http = _cliente(cliente)
    try:
        resposta = http.get(f"{base}/.well-known/openid-configuration")
        resposta.raise_for_status()
        documento = resposta.json()
    except (httpx.HTTPError, ValueError) as erro:
        msg = f"nao foi possivel ler a configuracao do provedor: {erro}"
        raise ErroDeIdentidade(msg) from erro

    faltando = [
        campo
        for campo in ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")
        if not documento.get(campo)
    ]
    if faltando:
        msg = f"provedor sem {', '.join(faltando)} na configuracao"
        raise ErroDeIdentidade(msg)

    return Provedor(
        emissor=str(documento["issuer"]),
        autorizacao=str(documento["authorization_endpoint"]),
        token=str(documento["token_endpoint"]),
        jwks=str(documento["jwks_uri"]),
    )


def novo_verificador() -> tuple[str, str]:
    """
    Par PKCE: (verificador, desafio) com S256.

    O verificador fica com quem pediu o login; so o desafio viaja. Quem
    interceptar o desafio nao consegue voltar ao verificador.
    """
    verificador = secrets.token_urlsafe(64)[:96]
    digesto = hashlib.sha256(verificador.encode("ascii")).digest()
    desafio = base64.urlsafe_b64encode(digesto).decode("ascii").rstrip("=")
    return verificador, desafio


def url_de_autorizacao(
    provedor: Provedor,
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    desafio: str,
) -> str:
    """Monta o endereco para onde a pessoa e enviada."""
    parametros = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": desafio,
        "code_challenge_method": "S256",
    }
    separador = "&" if "?" in provedor.autorizacao else "?"
    return f"{provedor.autorizacao}{separador}{urlencode(parametros)}"


def trocar_codigo(
    provedor: Provedor,
    *,
    codigo: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    verificador: str,
    cliente: httpx.Client | None = None,
) -> dict[str, Any]:
    """Troca o codigo de autorizacao pelos tokens, no canal servidor-a-servidor."""
    http = _cliente(cliente)
    try:
        resposta = http.post(
            provedor.token,
            data={
                "grant_type": "authorization_code",
                "code": codigo,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
                "code_verifier": verificador,
            },
            headers={"Accept": "application/json"},
        )
        resposta.raise_for_status()
        corpo: dict[str, Any] = resposta.json()
    except (httpx.HTTPError, ValueError) as erro:
        msg = f"o provedor recusou a troca do codigo: {erro}"
        raise ErroDeIdentidade(msg) from erro

    if not corpo.get("id_token"):
        msg = "resposta do provedor sem id_token"
        raise ErroDeIdentidade(msg)
    return corpo


def conferir_id_token(
    id_token: str,
    provedor: Provedor,
    *,
    client_id: str,
    nonce: str,
    cliente: httpx.Client | None = None,
    agora_s: float | None = None,
) -> Identidade:
    """
    Confere assinatura e conteudo do `id_token` e devolve a identidade.

    A ordem importa: primeiro a assinatura, depois o conteudo. Ler o `email`
    antes de saber se o token e autentico e o erro classico — e o que permite
    entrar como qualquer pessoa mandando um JSON montado a mao.
    """
    http = _cliente(cliente)
    try:
        resposta = http.get(provedor.jwks)
        resposta.raise_for_status()
        chaves = JsonWebKey.import_key_set(resposta.json())
    except (httpx.HTTPError, ValueError) as erro:
        msg = f"nao foi possivel ler as chaves do provedor: {erro}"
        raise ErroDeIdentidade(msg) from erro

    try:
        afirmacoes = JsonWebToken(_ALGORITMOS).decode(id_token, chaves)
    except (JoseError, ValueError) as erro:
        msg = f"id_token com assinatura invalida: {erro}"
        raise ErroDeIdentidade(msg) from erro

    instante = time.time() if agora_s is None else agora_s

    if str(afirmacoes.get("iss", "")).rstrip("/") != provedor.emissor.rstrip("/"):
        msg = "id_token emitido por outro provedor"
        raise ErroDeIdentidade(msg)

    audiencia = afirmacoes.get("aud")
    audiencias = audiencia if isinstance(audiencia, list) else [audiencia]
    if client_id not in audiencias:
        msg = "id_token destinado a outro cliente"
        raise ErroDeIdentidade(msg)

    expira = afirmacoes.get("exp")
    if not isinstance(expira, int | float) or instante > float(expira) + _FOLGA_S:
        msg = "id_token vencido"
        raise ErroDeIdentidade(msg)

    if str(afirmacoes.get("nonce", "")) != nonce:
        msg = "id_token nao corresponde a esta tentativa de login"
        raise ErroDeIdentidade(msg)

    email = str(afirmacoes.get("email", "")).strip().lower()
    if not email:
        msg = "provedor nao devolveu e-mail"
        raise ErroDeIdentidade(msg)

    return Identidade(
        emissor=provedor.emissor,
        assunto=str(afirmacoes.get("sub", "")),
        email=email,
        nome=str(afirmacoes.get("name", "") or email.split("@")[0]),
        email_verificado=bool(afirmacoes.get("email_verified", False)),
    )


__all__ = [
    "ErroDeIdentidade",
    "Identidade",
    "Provedor",
    "conferir_id_token",
    "descobrir",
    "novo_verificador",
    "trocar_codigo",
    "url_de_autorizacao",
]
