"""
Teste E2E (integracao) do modo 'extract web --js'.

PROVA POR CONTRASTE
===================
Roda a MESMA ExtractWebTask contra a MESMA pagina (/catalogo-js do demo,
cujo conteudo so existe apos o JavaScript):

- SEM --js  -> o HTML cru vem vazio          -> extrai 0 itens
- COM --js  -> o navegador renderiza o JS     -> extrai os 3 produtos

O contraste 0 vs N e a prova de que e a renderizacao do JavaScript (e nao
o parser) que traz o conteudo.

ISOLAMENTO E CI
===============
- Marcado com @pytest.mark.integration (sobe um servidor HTTP real).
- O teste COM navegador tem skip automatico se o Chromium nao estiver
  instalado (verify_playwright_installed), entao o CI NAO precisa instalar
  navegador: ele simplesmente pula esse teste.
- O servidor demo sobe numa porta livre, em thread, via werkzeug.make_server
  (sem dependencia nova) e e encerrado no fim.
- Determinismo sem sleep fragil: o modo --js usa wait_for="tr.produto",
  esperando o JS injetar as linhas.

Destino deste arquivo:
    tests/e2e/test_extract_web_js_e2e.py

Para rodar a prova real (com navegador), no ambiente preparado:
    playwright install chromium
    pytest -m integration
"""

from __future__ import annotations

import csv
import threading
import time
from typing import TYPE_CHECKING

import httpx
import pytest
from werkzeug.serving import make_server

from autotarefas.core.base import TaskStatus
from autotarefas.core.browser import verify_playwright_installed
from autotarefas.tasks.extract_web import ExtractWebTask

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

# O modulo inteiro toca mais de um componente (servidor + Task): integracao.
pytestmark = pytest.mark.integration

# Avaliado uma vez: o teste COM navegador so roda se o Chromium existir.
_SEM_NAVEGADOR = not verify_playwright_installed()["ok"]
_MOTIVO_SKIP = "navegador do Playwright nao instalado (rode: playwright install chromium)"

# Mesmos seletores do /catalogo (e do /catalogo-js): config reaproveitada.
ROW_SELECTOR = "tr.produto"
FIELDS = {"id": "td.id", "nome": "td.nome", "preco": "td.preco"}


def _esperar_online(base_url: str) -> None:
    """
    Aguarda o servidor responder ao /health.

    Readiness por polling curto (nao e um sleep fixo): retorna assim que o
    servidor responde 200, ou levanta se nao subir dentro do limite.
    """
    ultimo_erro: Exception | None = None
    for _ in range(100):
        try:
            if httpx.get(f"{base_url}/health", timeout=0.2).status_code == 200:
                return
        except httpx.HTTPError as exc:  # ainda subindo
            ultimo_erro = exc
            time.sleep(0.05)
    msg = f"servidor demo nao respondeu a tempo: {ultimo_erro}"
    raise RuntimeError(msg)


@pytest.fixture(scope="module")
def servidor_demo() -> Generator[str, None, None]:
    """
    Sobe o servidor demo (Flask) numa porta livre, em thread, e devolve a
    URL base. Sem dependencia nova (werkzeug.make_server). Encerra no fim.
    """
    from tools.demo_server.app import app

    app.config["TESTING"] = True
    servidor = make_server("127.0.0.1", 0, app)  # porta 0 = livre
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{servidor.server_port}"
    try:
        _esperar_online(base_url)
        yield base_url
    finally:
        servidor.shutdown()
        thread.join(timeout=5)


class TestExtractWebJsE2E:
    def test_sem_js_extrai_zero(self, servidor_demo: str, tmp_path: Path) -> None:
        """Sem --js o HTML cru vem vazio: 0 itens (a metade do contraste)."""
        result = ExtractWebTask(
            url=f"{servidor_demo}/catalogo-js",
            output_path=tmp_path / "httpx.csv",
            row_selector=ROW_SELECTOR,
            fields=FIELDS,
            use_js=False,
        ).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 0

    @pytest.mark.skipif(_SEM_NAVEGADOR, reason=_MOTIVO_SKIP)
    def test_com_js_extrai_os_produtos(self, servidor_demo: str, tmp_path: Path) -> None:
        """Com --js o navegador renderiza o JS: extrai os 3 produtos fixos."""
        saida = tmp_path / "js.csv"
        result = ExtractWebTask(
            url=f"{servidor_demo}/catalogo-js",
            output_path=saida,
            row_selector=ROW_SELECTOR,
            fields=FIELDS,
            use_js=True,
            wait_for="tr.produto",  # espera o JS injetar as linhas (sem sleep)
        ).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 3

        linhas = list(csv.DictReader(saida.open(encoding="utf-8")))
        nomes = [linha["nome"] for linha in linhas]
        assert "Teclado Mecanico ABNT2" in nomes
        assert "Mouse Optico USB" in nomes
        assert "Monitor LED 24 polegadas" in nomes
