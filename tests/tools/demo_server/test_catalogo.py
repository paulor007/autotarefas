"""
Testes da pagina de catalogo do servidor demo (alvo de web scraping).

Usa o test_client do Flask. O catalogo e deterministico (nao usa storage),
entao a fixture so liga o modo TESTING.

Cobertura:
- GET /catalogo: 200, estrutura da tabela
- Paginacao: itens por pagina, links prev/next, clamp de pagina
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


class TestCatalogoBasico:
    def test_get_200(self, client: FlaskClient) -> None:
        resp = client.get("/catalogo")
        assert resp.status_code == 200

    def test_tem_tabela_produtos(self, client: FlaskClient) -> None:
        html = client.get("/catalogo").get_data(as_text=True)
        assert 'class="produtos"' in html
        assert 'class="produto"' in html

    def test_tem_colunas_esperadas(self, client: FlaskClient) -> None:
        html = client.get("/catalogo").get_data(as_text=True)
        for classe in ("id", "nome", "categoria", "preco", "estoque"):
            assert f'class="{classe}"' in html


class TestCatalogoPaginacao:
    def test_primeira_pagina_tem_per_page_itens(self, client: FlaskClient) -> None:
        html = client.get("/catalogo?per_page=10").get_data(as_text=True)
        assert html.count('class="produto"') == 10

    def test_tem_link_proxima_na_primeira(self, client: FlaskClient) -> None:
        html = client.get("/catalogo?page=1&per_page=10").get_data(as_text=True)
        assert 'class="next"' in html
        assert 'class="prev"' not in html

    def test_ultima_pagina_sem_next(self, client: FlaskClient) -> None:
        # 48 itens / 10 por pagina = 5 paginas; a 5a nao tem next
        html = client.get("/catalogo?page=5&per_page=10").get_data(as_text=True)
        assert 'class="next"' not in html
        assert 'class="prev"' in html

    def test_per_page_customizado(self, client: FlaskClient) -> None:
        html = client.get("/catalogo?per_page=5").get_data(as_text=True)
        assert html.count('class="produto"') == 5

    def test_page_acima_do_total_faz_clamp(self, client: FlaskClient) -> None:
        # page=999 deve cair na ultima pagina valida (sem erro)
        resp = client.get("/catalogo?page=999&per_page=10")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'class="next"' not in html  # ja e a ultima

    def test_resumo_mostra_total(self, client: FlaskClient) -> None:
        html = client.get("/catalogo").get_data(as_text=True)
        assert "48 produtos" in html


class TestCatalogoDeterminismo:
    def test_mesma_pagina_mesmo_conteudo(self, client: FlaskClient) -> None:
        a = client.get("/catalogo?page=2&per_page=10").get_data(as_text=True)
        b = client.get("/catalogo?page=2&per_page=10").get_data(as_text=True)
        assert a == b
