"""
Jornada de planilhas com NAVEGADOR REAL (Chromium via Playwright).

Os testes de componente provam o React isolado; os de API provam o
backend. Nenhum dos dois prova o que o proprietario faz: abrir o
navegador, escolher um arquivo e ver o resultado. Este teste faz isso —
subindo o Live de verdade e clicando na tela.

Usa SOMENTE fixture sintetica (`A_vendas_com_anomalias.xlsx`): nenhum
arquivo privado entra aqui.

Rodar:
    playwright install chromium
    npm --prefix live_demo/frontend run build
    python -m pytest tests/e2e/test_jornada_planilhas_e2e.py

O backend serve o `dist/` na propria origem, como em producao — sem dev
server e sem proxy no meio. Pula sozinho (sem falhar a suite) quando
faltar Chromium ou o build do frontend.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import closing, suppress
from pathlib import Path
from urllib.parse import urljoin

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright nao instalado")
from playwright.sync_api import Page, sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE = RAIZ / "tests" / "fixtures" / "homologacao" / "A_vendas_com_anomalias.xlsx"
FRONTEND = RAIZ / "live_demo" / "frontend"

#: A jornada sobe dois processos; 60 s cobre npm frio em maquina lenta.
TIMEOUT_SUBIDA_S = 60
TIMEOUT_UI_MS = 30_000

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def _porta_livre() -> int:
    with closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _esperar_porta(porta: int, *, limite_s: int = TIMEOUT_SUBIDA_S) -> bool:
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        with closing(socket.socket()) as s, suppress(OSError):
            s.settimeout(1)
            s.connect(("127.0.0.1", porta))
            return True
        time.sleep(0.5)
    return False


def _encerrar(processo: subprocess.Popen[bytes]) -> None:
    processo.terminate()
    with suppress(subprocess.TimeoutExpired):
        processo.wait(timeout=10)
    if processo.poll() is None:  # pragma: no cover - so em travamento
        processo.kill()


@pytest.fixture(scope="module")
def sistema() -> Iterator[str]:
    """
    Sobe o Live inteiro em UM processo e devolve a URL da interface.

    O backend serve o `dist/` do Vite na propria origem — do mesmo jeito que
    em producao. Isso evita depender do dev server (e do proxy dele) e testa
    a combinacao que o usuario final recebe. Sem o build, o teste pula com a
    instrucao de como gera-lo.
    """
    if not (FRONTEND / "dist" / "index.html").is_file():
        pytest.skip("frontend nao buildado: rode `npm --prefix live_demo/frontend run build`")

    porta = _porta_livre()
    backend = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "live_demo.backend.app.main:app",
            "--port",
            str(porta),
        ],
        cwd=RAIZ,
        # Os servidores de demonstracao (mocks) escutam portas FIXAS. Se ja
        # houver um Live rodando na maquina, subir os mocks de novo falha e o
        # backend morre no berco. A jornada de planilhas nao usa mock nenhum.
        env={**os.environ, "DEMO_SERVERS_AUTOSTART": "0"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        if not _esperar_porta(porta):
            pytest.skip("o Live nao subiu a tempo")
        yield f"http://127.0.0.1:{porta}"
    finally:
        _encerrar(backend)


@pytest.fixture(scope="module")
def pagina(sistema: str) -> Iterator[Page]:
    with sync_playwright() as playwright:
        try:
            navegador = playwright.chromium.launch()
        except Exception as exc:  # noqa: BLE001 - navegador ausente e ambiente
            pytest.skip(f"Chromium indisponivel: {str(exc)[:120]}")
        contexto = navegador.new_context(viewport={"width": 1280, "height": 900})
        page = contexto.new_page()
        page.set_default_timeout(TIMEOUT_UI_MS)
        page.goto(sistema)
        try:
            yield page
        finally:
            contexto.close()
            navegador.close()


def test_jornada_completa_no_navegador(pagina: Page) -> None:
    """
    Percorre a jornada inteira como o proprietario percorre.

    Cada `expect` implicito aqui e uma etapa da homologacao: diagnostico,
    regras, revisao com as duas confirmacoes, execucao real e artefatos.
    """
    # 1. Selecionar o card
    cartao = pagina.get_by_role("heading", name="Análise e organização de planilhas").first
    cartao.scroll_into_view_if_needed()
    pagina.get_by_role("button", name="Selecionar").first.click()

    # 2. Enviar o arquivo (fixture sintetica)
    pagina.set_input_files("input[type=file]", str(FIXTURE))
    pagina.get_by_role("button", name="Analisar meus dados").click()

    # 3. Diagnostico com os dados REAIS da leitura. Espera o BOTAO da proxima
    # etapa, nao o titulo: o titulo aparece enquanto ainda le o arquivo.
    proxima = pagina.get_by_role("button", name="Escolher como validar")
    proxima.wait_for(state="visible")
    corpo = pagina.locator("#execucao").inner_text()
    assert "A_vendas_com_anomalias.xlsx" in corpo
    assert "Vendas" in corpo  # a aba detectada

    # 4. Regras: schema sugerido (analise geral)
    proxima.click()
    pagina.get_by_role("button", name="Confirmar schema sugerido").click()

    # 5. Revisao: as duas confirmacoes aparecem
    pagina.get_by_role("button", name="Revisar configuração").click()
    pagina.get_by_text("Revise antes de executar").wait_for()

    correcoes = pagina.get_by_role("checkbox", name="Aplicar as correções seguras")
    assert correcoes.is_checked() is False, "correções devem começar desligadas"
    correcoes.check()

    repetidas = pagina.get_by_role("checkbox", name="Sinalizar as 1 linha")
    assert repetidas.is_checked() is True, "repetidas encontradas vêm marcadas"

    # 6. Executar de verdade e esperar o desfecho
    pagina.get_by_role("button", name="Executar validação").click()
    pagina.get_by_text("Arquivos desta execução").wait_for(timeout=TIMEOUT_UI_MS)

    resultado = pagina.locator("#execucao").inner_text()

    # 7. O resultado distingue repetidas de linhas envolvidas
    assert "1 linha(s) repetida(s)" in resultado
    assert "2 linha(s) envolvida(s)" in resultado

    # 8. Os artefatos reais estao la, com rotulo legivel
    assert "Planilha tratada" in resultado
    assert "Registros válidos" in resultado
    assert "Pacote completo de evidências" in resultado

    # 9. E o download responde de verdade (nao e link decorativo)
    link = pagina.get_by_role("link", name="Baixar").first
    href = link.get_attribute("href")
    assert href is not None
    assert href.startswith("/api/download/")
    resposta = pagina.request.get(urljoin(pagina.url, href))
    assert resposta.status == 200
    assert resposta.body()
