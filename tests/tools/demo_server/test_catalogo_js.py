"""
Testes da pagina de catalogo renderizada por JavaScript (alvo do
'extract web --js').

Usa o test_client do Flask. Verifica o CONTRASTE na origem: o HTML cru
servido NAO contem os produtos (eles so passam a existir depois que o JS
roda e o fetch resolve), enquanto a rota de dados (/catalogo-js/dados)
entrega o JSON fixo. A prova E2E real (modo --js com navegador) vive nos
testes de integracao, separada e com skip automatico sem browser.

Cobertura:
- GET /catalogo-js: 200, tabela vazia no HTML cru, script de fetch presente
- GET /catalogo-js/dados: 200, JSON com os 3 produtos fixos e deterministicos
"""

from __future__ import annotations

import importlib
from collections.abc import Generator

import pytest
from flask.testing import FlaskClient

app_module = importlib.import_module("tools.demo_server.app")


@pytest.fixture
def client() -> Generator[FlaskClient, None, None]:
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


class TestPaginaJS:
    def test_get_200(self, client: FlaskClient) -> None:
        assert client.get("/catalogo-js").status_code == 200

    def test_html_cru_nao_tem_produtos(self, client: FlaskClient) -> None:
        # A prova do contraste na origem: sem rodar o JS, nenhuma linha existe.
        html = client.get("/catalogo-js").get_data(as_text=True)
        assert 'class="produto"' not in html
        # ...e nenhum dos nomes fixos aparece no HTML servido
        assert "Teclado Mecanico ABNT2" not in html

    def test_tem_tabela_vazia_e_script(self, client: FlaskClient) -> None:
        html = client.get("/catalogo-js").get_data(as_text=True)
        assert 'class="produtos"' in html  # a tabela existe (cabecalho)
        assert 'id="corpo-produtos"' in html  # o tbody alvo existe, porem vazio
        assert "/catalogo-js/dados" in html  # o fetch aponta pra rota de dados
        assert "DOMContentLoaded" in html  # injecao ocorre no carregamento


class TestDadosJSON:
    def test_get_200_json(self, client: FlaskClient) -> None:
        resp = client.get("/catalogo-js/dados")
        assert resp.status_code == 200
        assert resp.is_json

    def test_tres_produtos_fixos(self, client: FlaskClient) -> None:
        dados = client.get("/catalogo-js/dados").get_json()
        assert isinstance(dados, list)
        assert len(dados) == 3
        assert dados[0] == {
            "id": "1",
            "nome": "Teclado Mecanico ABNT2",
            "preco": "349.90",
        }

    def test_todos_tem_os_campos(self, client: FlaskClient) -> None:
        dados = client.get("/catalogo-js/dados").get_json()
        for produto in dados:
            assert set(produto) == {"id", "nome", "preco"}

    def test_deterministico(self, client: FlaskClient) -> None:
        a = client.get("/catalogo-js/dados").get_json()
        b = client.get("/catalogo-js/dados").get_json()
        assert a == b
