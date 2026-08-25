"""Provedor OIDC de mentira, para a suite — e so para a suite.

Existe porque testar login de verdade contra o Google exigiria uma credencial
do proprietario, e um caminho que so e testado a mao nao e testado. Este
provedor e **real no protocolo**: assina o `id_token` com uma chave RSA de
verdade, publica JWKS de verdade e confere o PKCE de verdade. O que ele nao
tem e gente.

Nunca e oferecido ao cliente: nao ha configuracao do produto que aponte para
ele, e ele nao existe fora de `apps/api/tests`.
"""

from __future__ import annotations

import secrets
import time
from typing import Any

from authlib.jose import JsonWebKey, JsonWebToken
from fastapi import FastAPI, Form, HTTPException

#: Endereco pelo qual o backend enxerga este provedor. Qualquer host serve:
#: o transporte da suite entrega direto ao aplicativo, sem rede.
EMISSOR = "http://provedor.teste"


class ProvedorDeTeste:
    """Um provedor OIDC minimo, com estado em memoria."""

    def __init__(self, *, emissor: str = EMISSOR, client_id: str = "cliente-de-teste") -> None:
        self.emissor = emissor
        self.client_id = client_id
        # `kid` sai nas opcoes: no authlib ele e propriedade so de leitura,
        # derivada da chave, e atribuir depois levanta.
        self.chave = JsonWebKey.generate_key(
            "RSA", 2048, options={"kid": "chave-de-teste"}, is_private=True
        )
        #: codigo -> dados da autorizacao (nonce, desafio PKCE, pessoa).
        self.autorizacoes: dict[str, dict[str, Any]] = {}
        #: Pessoa que o provedor vai afirmar no proximo login.
        self.email = "ana@padariasol.com.br"
        self.nome = "Ana Souza"
        self.assunto = "sub-ana"
        self.email_verificado = True
        #: Ligado por um teste para provar que assinatura de outro emissor cai.
        self.emissor_declarado: str | None = None
        self.app = self._montar()

    # --------------------------------------------------------
    # Endpoints
    # --------------------------------------------------------

    def _montar(self) -> FastAPI:
        app = FastAPI()

        @app.get("/.well-known/openid-configuration")
        def descoberta() -> dict[str, str]:
            return {
                "issuer": self.emissor,
                "authorization_endpoint": f"{self.emissor}/authorize",
                "token_endpoint": f"{self.emissor}/token",
                "jwks_uri": f"{self.emissor}/jwks",
            }

        @app.get("/jwks")
        def jwks() -> dict[str, Any]:
            publica = self.chave.as_dict(is_private=False)
            publica["kid"] = self.chave.kid
            return {"keys": [publica]}

        @app.post("/token")
        def token(
            grant_type: str = Form(...),
            code: str = Form(...),
            code_verifier: str = Form(""),
            client_id: str = Form(""),
            client_secret: str = Form(""),
            redirect_uri: str = Form(""),
        ) -> dict[str, Any]:
            del grant_type, redirect_uri
            dados = self.autorizacoes.pop(code, None)
            if dados is None:
                raise HTTPException(status_code=400, detail="codigo desconhecido")
            if client_id != self.client_id or not client_secret:
                raise HTTPException(status_code=401, detail="cliente invalido")
            if self._desafio(code_verifier) != dados["desafio"]:
                raise HTTPException(status_code=400, detail="PKCE nao confere")
            return {
                "access_token": secrets.token_urlsafe(16),
                "token_type": "Bearer",
                "id_token": self.assinar(nonce=dados["nonce"]),
            }

        return app

    # --------------------------------------------------------
    # Apoio
    # --------------------------------------------------------

    @staticmethod
    def _desafio(verificador: str) -> str:
        import base64
        import hashlib

        digesto = hashlib.sha256(verificador.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digesto).decode("ascii").rstrip("=")

    def autorizar(self, *, nonce: str, desafio: str) -> str:
        """Registra uma autorizacao e devolve o codigo, como faria a tela dele."""
        codigo = secrets.token_urlsafe(16)
        self.autorizacoes[codigo] = {"nonce": nonce, "desafio": desafio}
        return codigo

    def assinar(
        self,
        *,
        nonce: str,
        expira_em: int = 600,
        audiencia: str | None = None,
        emissor: str | None = None,
    ) -> str:
        """Assina um `id_token`. Os parametros existem para testar recusa."""
        agora = int(time.time())
        afirmacoes = {
            "iss": emissor or self.emissor_declarado or self.emissor,
            "sub": self.assunto,
            "aud": audiencia or self.client_id,
            "iat": agora,
            "exp": agora + expira_em,
            "nonce": nonce,
            "email": self.email,
            "email_verified": self.email_verificado,
            "name": self.nome,
        }
        assinado = JsonWebToken(["RS256"]).encode(
            {"alg": "RS256", "kid": self.chave.kid}, afirmacoes, self.chave
        )
        return assinado.decode("ascii")


__all__ = ["EMISSOR", "ProvedorDeTeste"]
