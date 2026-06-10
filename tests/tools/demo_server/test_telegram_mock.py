"""
Testes do mock da Bot API do Telegram (servidor demo).

Usa o test_client do Flask, sem subir servidor real.
Destino: tests/tools/demo_server/test_telegram_mock.py
"""

from __future__ import annotations

import importlib
from collections.abc import Generator

import pytest
from flask.testing import FlaskClient

app_module = importlib.import_module("tools.demo_server.app")

TOKEN = "123456:TEST-TOKEN"
URL = f"/bot{TOKEN}/sendMessage"


@pytest.fixture
def client() -> Generator[FlaskClient, None, None]:
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_inbox() -> None:
    """Cada teste começa com a inbox do mock vazia."""
    app_module._telegram_inbox.clear()


class TestSendMessage:
    def test_sucesso(self, client: FlaskClient) -> None:
        resp = client.post(URL, json={"chat_id": "42", "text": "Olá!"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert body["result"]["text"] == "Olá!"
        assert body["result"]["chat"]["id"] == "42"
        assert body["result"]["message_id"] == 1

    def test_chat_id_numerico(self, client: FlaskClient) -> None:
        # chat_id como int no JSON também funciona
        resp = client.post(URL, json={"chat_id": 42, "text": "oi"})
        assert resp.status_code == 200
        assert resp.get_json()["result"]["chat"]["id"] == "42"

    def test_sem_chat_id(self, client: FlaskClient) -> None:
        resp = client.post(URL, json={"text": "sem destino"})
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False

    def test_sem_text(self, client: FlaskClient) -> None:
        resp = client.post(URL, json={"chat_id": "42"})
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False

    def test_aceita_form(self, client: FlaskClient) -> None:
        # fallback para form-encoded
        resp = client.post(URL, data={"chat_id": "7", "text": "via form"})
        assert resp.status_code == 200
        assert resp.get_json()["result"]["text"] == "via form"


class TestInbox:
    def test_registra_mensagem(self, client: FlaskClient) -> None:
        client.post(URL, json={"chat_id": "42", "text": "primeira"})
        resp = client.get("/telegram/mensagens")
        body = resp.get_json()
        assert body["total"] == 1
        assert body["mensagens"][0]["text"] == "primeira"
        assert body["mensagens"][0]["chat_id"] == "42"

    def test_message_id_incrementa(self, client: FlaskClient) -> None:
        client.post(URL, json={"chat_id": "1", "text": "a"})
        r2 = client.post(URL, json={"chat_id": "1", "text": "b"})
        assert r2.get_json()["result"]["message_id"] == 2
        assert client.get("/telegram/mensagens").get_json()["total"] == 2

    def test_token_nao_vaza_inteiro(self, client: FlaskClient) -> None:
        client.post(URL, json={"chat_id": "1", "text": "x"})
        msg = client.get("/telegram/mensagens").get_json()["mensagens"][0]
        # guarda só um prefixo do token, não o token inteiro
        assert msg["token_prefix"] == TOKEN[:8]
        assert TOKEN not in str(msg)

    def test_limpar(self, client: FlaskClient) -> None:
        client.post(URL, json={"chat_id": "1", "text": "x"})
        client.post("/telegram/limpar")
        assert client.get("/telegram/mensagens").get_json()["total"] == 0
