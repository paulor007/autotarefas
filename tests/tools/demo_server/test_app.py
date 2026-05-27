"""
Testes do app Flask do servidor demo.

Usa o test_client do Flask para fazer requests sem subir servidor real.
Storage eh substituido por uma instancia isolada em tmp_path.

Cobertura:
- GET /, /cadastro, /cadastros, /health, /sucesso/<id>
- POST /cadastro: validacoes + criacao + duplicata
- POST /limpar
"""

from __future__ import annotations

import importlib
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from flask.testing import FlaskClient

from tools.demo_server.storage import Storage

app_module = importlib.import_module("tools.demo_server.app")

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[FlaskClient, None, None]:
    """
    Cliente Flask de teste com storage isolado em tmp_path.

    Cada teste recebe storage limpo, sem efeito colateral no real.
    """
    test_storage = Storage(data_dir=tmp_path / "data")
    monkeypatch.setattr(app_module, "storage", test_storage)

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def _post_cadastro(
    client: FlaskClient,
    *,
    nome: str = "Ana Silva",
    email: str = "ana@exemplo.com",
    cpf: str = "529.982.247-25",
    telefone: str = "(11) 98765-4321",
) -> Any:
    """Helper para POST /cadastro com dados default validos."""
    return client.post(
        "/cadastro",
        data={
            "nome": nome,
            "email": email,
            "cpf": cpf,
            "telefone": telefone,
        },
    )


# ============================================================
# GET /
# ============================================================


class TestIndex:
    """Landing page."""

    def test_get_index_retorna_200(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert response.status_code == 200

    def test_index_mostra_total_zero_inicial(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert b"0" in response.data

    def test_index_mostra_total_apos_cadastros(self, client: FlaskClient) -> None:
        _post_cadastro(client)
        response = client.get("/")
        assert b"1" in response.data


# ============================================================
# GET /cadastro
# ============================================================


class TestCadastroGet:
    """Formulario."""

    def test_get_cadastro_retorna_200(self, client: FlaskClient) -> None:
        response = client.get("/cadastro")
        assert response.status_code == 200

    def test_get_cadastro_contem_form_fields(self, client: FlaskClient) -> None:
        response = client.get("/cadastro")
        body = response.data.decode("utf-8")
        assert 'name="nome"' in body
        assert 'name="email"' in body
        assert 'name="cpf"' in body
        assert 'name="telefone"' in body
        assert 'id="btn-cadastrar"' in body


# ============================================================
# POST /cadastro - validacoes
# ============================================================


class TestCadastroPostValidacoes:
    """Validacoes server-side do POST /cadastro."""

    def test_nome_vazio_rejeita(self, client: FlaskClient) -> None:
        response = _post_cadastro(client, nome="")
        body = response.data.decode("utf-8")
        assert "Nome" in body
        assert "obrigatorio" in body

    def test_nome_curto_rejeita(self, client: FlaskClient) -> None:
        """Nome com menos de 3 chars eh invalido."""
        response = _post_cadastro(client, nome="An")
        body = response.data.decode("utf-8")
        assert "Nome" in body

    def test_email_vazio_rejeita(self, client: FlaskClient) -> None:
        response = _post_cadastro(client, email="")
        body = response.data.decode("utf-8")
        assert "Email" in body
        assert "obrigatorio" in body

    def test_email_invalido_rejeita(self, client: FlaskClient) -> None:
        response = _post_cadastro(client, email="naoeumemail")
        body = response.data.decode("utf-8")
        assert "Email" in body
        assert "invalido" in body

    def test_cpf_vazio_rejeita(self, client: FlaskClient) -> None:
        response = _post_cadastro(client, cpf="")
        body = response.data.decode("utf-8")
        assert "CPF" in body
        assert "obrigatorio" in body

    def test_cpf_formato_invalido_rejeita(self, client: FlaskClient) -> None:
        """CPF deve estar no formato XXX.XXX.XXX-XX."""
        response = _post_cadastro(client, cpf="12345678900")
        body = response.data.decode("utf-8")
        assert "CPF" in body

    def test_telefone_invalido_rejeita(self, client: FlaskClient) -> None:
        """Telefone, se preenchido, deve estar no formato (XX) XXXXX-XXXX."""
        response = _post_cadastro(client, telefone="11999998888")
        body = response.data.decode("utf-8")
        assert "Telefone" in body

    def test_telefone_vazio_aceita(self, client: FlaskClient) -> None:
        """Telefone eh opcional - vazio nao gera erro."""
        response = _post_cadastro(client, telefone="")
        # Sucesso eh um redirect para /sucesso/<id>
        assert response.status_code in (200, 302)

    def test_cpf_duplicado_rejeita(self, client: FlaskClient) -> None:
        """POST com mesmo CPF retorna erro."""
        _post_cadastro(client)
        response = _post_cadastro(client)
        body = response.data.decode("utf-8")
        assert "CPF" in body
        assert "cadastrado" in body


# ============================================================
# POST /cadastro - sucesso
# ============================================================


class TestCadastroPostSucesso:
    """Criacao bem-sucedida."""

    def test_post_valido_retorna_redirect(self, client: FlaskClient) -> None:
        response = _post_cadastro(client)
        assert response.status_code == 302
        assert "/sucesso/" in response.headers["Location"]

    def test_post_valido_cria_registro(self, client: FlaskClient) -> None:
        _post_cadastro(client, nome="Bruno Costa")

        response = client.get("/cadastros")
        records = response.get_json()
        assert len(records) == 1
        assert records[0]["nome"] == "Bruno Costa"


# ============================================================
# GET /sucesso/<id>
# ============================================================


class TestSucessoPage:
    """Pagina de sucesso."""

    def test_sucesso_id_existente_retorna_200(self, client: FlaskClient) -> None:
        _post_cadastro(client)
        response = client.get("/sucesso/1")
        assert response.status_code == 200
        body = response.data.decode("utf-8")
        assert 'id="record-id"' in body
        assert "1" in body

    def test_sucesso_id_inexistente_retorna_404(self, client: FlaskClient) -> None:
        response = client.get("/sucesso/999")
        assert response.status_code == 404


# ============================================================
# GET /cadastros e POST /limpar
# ============================================================


class TestCadastrosListAndClear:
    """List/clear via API JSON."""

    def test_cadastros_vazio_retorna_lista_vazia(
        self,
        client: FlaskClient,
    ) -> None:
        response = client.get("/cadastros")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_cadastros_retorna_todos(self, client: FlaskClient) -> None:
        _post_cadastro(client, cpf="529.982.247-25", nome="Ana")
        _post_cadastro(client, cpf="111.444.777-35", nome="Bruno")
        response = client.get("/cadastros")
        records = response.get_json()
        assert len(records) == 2
        nomes = {r["nome"] for r in records}
        assert nomes == {"Ana", "Bruno"}

    def test_limpar_apaga_tudo(self, client: FlaskClient) -> None:
        _post_cadastro(client)
        response = client.post("/limpar")
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"

        # Verifica que esta vazio
        list_resp = client.get("/cadastros")
        assert list_resp.get_json() == []


# ============================================================
# GET /health
# ============================================================


class TestHealth:
    """Health check."""

    def test_health_retorna_status_ok(self, client: FlaskClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "autotarefas-demo"

    def test_health_inclui_total_cadastros(self, client: FlaskClient) -> None:
        _post_cadastro(client)
        response = client.get("/health")
        assert response.get_json()["total_cadastros"] == 1
