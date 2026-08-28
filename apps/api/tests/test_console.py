"""
A prova de acesso à máquina, e a chave de reentrada emitida com o serviço no ar.

O que se protege aqui é a equivalência: pedir uma chave por HTTP não pode ser
mais fácil do que lê-la no console. Se fosse, o link de reentrada — que dá
acesso de dono a uma organização inteira — passaria a valer menos do que a
frase que o descreve.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.app.config import settings
from apps.api.app.db import repositorio as repo
from apps.api.app.db.atual import definir_banco
from apps.api.app.db.models import Papel
from apps.api.app.db.sessao import Banco
from apps.api.app.identidade import console, reentrada
from apps.api.app.identidade.rotas import CABECALHO_DO_CONSOLE
from apps.api.app.main import app

HTTP_OK = 200
HTTP_PROIBIDO = 403
HTTP_CONFLITO = 409


def _ajustar(**valores: object) -> dict[str, object]:
    """Troca campos do `settings`, que é um dataclass congelado."""
    anteriores = {nome: getattr(settings, nome) for nome in valores}
    for nome, valor in valores.items():
        object.__setattr__(settings, nome, valor)
    return anteriores


@pytest.fixture
def raiz(tmp_path: Path) -> object:
    """O token vai para uma pasta de teste, nunca para a do repositório."""
    anteriores = _ajustar(repo_root=tmp_path, oidc_issuer="", oidc_client_id="")
    yield tmp_path
    console.descartar()
    _ajustar(**anteriores)


@pytest.fixture
def banco_com_dono(raiz: Path) -> object:
    del raiz
    banco = Banco("sqlite:///:memory:")
    banco.criar_esquema()
    definir_banco(banco)
    with banco.sessao() as sessao:
        organizacao = repo.criar_organizacao(
            sessao, nome="Padaria Sol", dominio="padariasol.com.br"
        )
        usuario = repo.criar_usuario(
            sessao,
            email="dono@padariasol.com.br",
            nome="Ana",
            emissor="bootstrap",
            assunto="Padaria Sol",
        )
        repo.vincular(sessao, organizacao=organizacao, usuario=usuario, papel=Papel.DONO)
    yield banco
    reentrada.descartar()
    definir_banco(None)


class TestOToken:
    def test_cada_partida_sorteia_outro(self, raiz: Path) -> None:
        del raiz
        primeiro = console.gerar()
        segundo = console.gerar()

        assert primeiro != segundo
        # E o antigo para de valer na hora: uma copia guardada nao serve.
        assert console.confere(primeiro) is False
        assert console.confere(segundo) is True

    def test_sem_arquivo_nada_confere(self, raiz: Path) -> None:
        del raiz
        console.descartar()

        assert console.ler() == ""
        assert console.confere("") is False
        assert console.confere("qualquer-coisa") is False

    def test_o_arquivo_mora_na_pasta_de_runtime(self, raiz: Path) -> None:
        console.gerar()

        assert console.caminho().parent.name == ".autotarefas"
        assert console.caminho().is_relative_to(raiz)


class TestEmitirComOServicoNoAr:
    def test_com_a_prova_certa_sai_uma_chave_que_funciona(self, banco_com_dono: Banco) -> None:
        """
        O teste inteiro do recurso: pedir, receber, entrar.

        Conferir só o 200 provaria que a rota responde, e não que a chave
        devolvida serve para alguma coisa — que é a única pergunta que importa
        para quem está trancado do lado de fora.
        """
        del banco_com_dono
        token = console.gerar()
        cliente = TestClient(app)

        resposta = cliente.post(
            "/api/auth/reentrar/emitir",
            headers={CABECALHO_DO_CONSOLE: token},
        )

        assert resposta.status_code == HTTP_OK, resposta.text
        corpo = resposta.json()
        assert corpo["email"] == "dono@padariasol.com.br"
        assert "/api/auth/reentrar?chave=" in corpo["url"]

        chave = corpo["url"].split("chave=", 1)[1]
        entrada = cliente.get(f"/api/auth/reentrar?chave={chave}", follow_redirects=False)
        assert entrada.status_code in {302, 303}
        assert entrada.headers["location"] == "/app"

    def test_sem_a_prova_recusa(self, banco_com_dono: Banco) -> None:
        del banco_com_dono
        console.gerar()
        cliente = TestClient(app)

        assert cliente.post("/api/auth/reentrar/emitir").status_code == HTTP_PROIBIDO

    def test_com_a_prova_errada_recusa(self, banco_com_dono: Banco) -> None:
        del banco_com_dono
        console.gerar()
        cliente = TestClient(app)

        resposta = cliente.post(
            "/api/auth/reentrar/emitir",
            headers={CABECALHO_DO_CONSOLE: "token-de-outra-partida"},
        )

        assert resposta.status_code == HTTP_PROIBIDO

    def test_o_token_nunca_volta_na_resposta(self, banco_com_dono: Banco) -> None:
        """
        A chave de reentrada pode viajar; a prova do console, não.

        Ela vale para TODAS as emissões desta partida. Devolvê-la num corpo
        HTTP a transformaria de "arquivo local" em "coisa que circula".
        """
        del banco_com_dono
        token = console.gerar()
        cliente = TestClient(app)

        resposta = cliente.post(
            "/api/auth/reentrar/emitir",
            headers={CABECALHO_DO_CONSOLE: token},
        )

        assert token not in resposta.text

    def test_com_provedor_configurado_recusa_e_diz_por_que(self, banco_com_dono: Banco) -> None:
        """Com OIDC no ar, a porta dos fundos não pode continuar aberta."""
        del banco_com_dono
        token = console.gerar()
        anteriores = _ajustar(oidc_issuer="https://provedor.exemplo", oidc_client_id="abc")
        try:
            cliente = TestClient(app)
            resposta = cliente.post(
                "/api/auth/reentrar/emitir",
                headers={CABECALHO_DO_CONSOLE: token},
            )
        finally:
            _ajustar(**anteriores)

        assert resposta.status_code == HTTP_CONFLITO
        assert "provedor" in resposta.json()["detail"]

    def test_sem_organizacao_recusa_e_manda_usar_o_convite(self, raiz: Path) -> None:
        del raiz
        banco = Banco("sqlite:///:memory:")
        banco.criar_esquema()
        definir_banco(banco)
        try:
            token = console.gerar()
            cliente = TestClient(app)
            resposta = cliente.post(
                "/api/auth/reentrar/emitir",
                headers={CABECALHO_DO_CONSOLE: token},
            )
        finally:
            definir_banco(None)

        assert resposta.status_code == HTTP_CONFLITO
        assert "convite" in resposta.json()["detail"]
