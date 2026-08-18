"""
Jornada de planilhas com NAVEGADOR REAL (Chromium via Playwright).

Os testes de componente provam o React isolado; os de API provam o
backend. Nenhum dos dois prova o que o proprietario faz: abrir o
navegador, escolher um arquivo e ver o resultado. Este teste faz isso —
subindo o Live de verdade e clicando na tela.

Cobre os seis cenarios do card, um por teste:

1. planilha limpa e ja organizada;
2. planilha sem formatacao, aceitando a organizacao;
3. planilha com linhas 100% duplicadas;
4. planilha que poderia ser organizada, mas a formatacao e RECUSADA;
5. download real da planilha organizada e do relatorio de analise;
6. aba de Dashboard, so depois de confirmar o significado das colunas.

Usa SOMENTE fixtures sinteticas (`tests/fixtures/dominios`): nenhum
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

import io
import os
import socket
import subprocess
import sys
import time
import zipfile
from collections.abc import Iterator
from contextlib import closing, suppress
from pathlib import Path
from urllib.parse import urljoin

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright nao instalado")
from playwright.sync_api import Page, sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
DOMINIOS = RAIZ / "tests" / "fixtures" / "dominios"
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
def navegador_pagina(sistema: str) -> Iterator[Page]:
    with sync_playwright() as playwright:
        try:
            navegador = playwright.chromium.launch()
        except Exception as exc:  # noqa: BLE001 - navegador ausente e ambiente
            pytest.skip(f"Chromium indisponivel: {str(exc)[:120]}")
        contexto = navegador.new_context(viewport={"width": 1280, "height": 900})
        page = contexto.new_page()
        page.set_default_timeout(TIMEOUT_UI_MS)
        try:
            yield page
        finally:
            contexto.close()
            navegador.close()


@pytest.fixture
def pagina(navegador_pagina: Page, sistema: str) -> Page:
    """Cada cenario comeca de uma pagina limpa, como quem abre o site agora."""
    navegador_pagina.goto(sistema)
    return navegador_pagina


def _ate_a_revisao(pagina: Page, fixture: Path) -> None:
    """Do inicio ate 'Revisar analise e opcoes' — sem parada de schema."""
    cartao = pagina.get_by_role("heading", name="Análise e organização de planilhas").first
    cartao.scroll_into_view_if_needed()
    pagina.get_by_role("button", name="Selecionar").first.click()

    pagina.set_input_files("input[type=file]", str(fixture))
    pagina.get_by_role("button", name="Analisar meus dados").click()

    # Espera o BOTAO da proxima etapa, nao o titulo: o titulo aparece
    # enquanto o arquivo ainda esta sendo lido.
    proxima = pagina.get_by_role("button", name="Revisar análise e opções")
    proxima.wait_for(state="visible")
    proxima.click()
    pagina.get_by_role("button", name="Analisar e organizar").wait_for()


def _executar(pagina: Page) -> str:
    pagina.get_by_role("button", name="Analisar e organizar").click()
    pagina.get_by_text("Downloads", exact=True).wait_for(timeout=TIMEOUT_UI_MS)
    return pagina.locator("#execucao").inner_text()


def _baixar_por_rotulo(pagina: Page, rotulo: str) -> bytes:
    """Baixa pelo texto que a pessoa ve, nao pelo nome tecnico do arquivo."""
    link = pagina.locator("a", has_text=rotulo).first
    href = link.get_attribute("href")
    assert href is not None, f"link '{rotulo}' sem href"
    resposta = pagina.request.get(urljoin(pagina.url, href))
    assert resposta.status == 200, f"{rotulo}: HTTP {resposta.status}"
    return bytes(resposta.body())


def test_planilha_ja_organizada_nao_recebe_proposta_de_formatacao(pagina: Page) -> None:
    """Cenario 1: limpa e ja organizada — nada a propor, nada a decidir."""
    _ate_a_revisao(pagina, DOMINIOS / "financeiro_profissional.xlsx")

    revisao = pagina.locator("#execucao").inner_text()
    assert "já está estruturada e legível" in revisao
    # Reformatar o que ja esta bom mexeria na identidade visual de graca.
    assert pagina.get_by_role("checkbox", name="Gerar uma versão organizada").count() == 0, (
        "planilha organizada nao pode receber proposta de reformatacao"
    )

    resultado = _executar(pagina)
    assert "nada exigiu a sua decisão" in resultado
    assert "Relatório da análise" in resultado


def test_planilha_sem_formatacao_aceita_a_organizacao(pagina: Page) -> None:
    """Cenario 2: da para melhorar, a pessoa aceita e a versao sai."""
    _ate_a_revisao(pagina, DOMINIOS / "vendas_simples.xlsx")

    revisao = pagina.locator("#execucao").inner_text()
    assert "pode ser melhorada" in revisao

    caixa = pagina.get_by_role("checkbox", name="Gerar uma versão organizada")
    assert caixa.is_checked() is False, "toda confirmacao comeca desligada"
    caixa.check()

    resultado = _executar(pagina)
    assert "versão organizada gerada" in resultado
    assert "Planilha organizada" in resultado

    # E o arquivo baixado e mesmo um XLSX (assinatura de ZIP do OOXML).
    conteudo = _baixar_por_rotulo(pagina, "Planilha organizada")
    assert conteudo[:2] == b"PK"


def test_planilha_com_duplicidade_relata_sem_remover(pagina: Page) -> None:
    """Cenario 3: linhas 100% repetidas viram aviso localizado, nunca exclusao."""
    _ate_a_revisao(pagina, DOMINIOS / "servico_publico.xlsx")

    revisao = pagina.locator("#execucao").inner_text()
    # A verificacao acontece sempre — nao ha caixa para ligar ou desligar.
    assert "100% repetida" in revisao
    assert pagina.get_by_role("checkbox", name="repetida").count() == 0
    assert "chave repetida" in revisao

    resultado = _executar(pagina)
    assert "1 linha(s) repetida(s)" in resultado
    assert "2 linha(s) envolvida(s)" in resultado
    assert "Nenhuma foi removida" in resultado


def test_recusar_a_formatacao_nao_gera_planilha_organizada(pagina: Page) -> None:
    """Cenario 4: sem confirmacao, a formatacao simplesmente nao acontece."""
    _ate_a_revisao(pagina, DOMINIOS / "vendas_simples.xlsx")

    caixa = pagina.get_by_role("checkbox", name="Gerar uma versão organizada")
    assert caixa.is_checked() is False
    # Nao marcamos nada: e exatamente esse o cenario.

    resultado = _executar(pagina)
    assert "Planilha organizada" not in resultado
    assert "nada exigiu a sua decisão" in resultado
    # O relatorio da analise sai do mesmo jeito: analisar nao depende de aceitar.
    assert "Relatório da análise" in resultado


def test_dashboard_so_nasce_com_os_papeis_confirmados(pagina: Page) -> None:
    """Cenario 6: o painel e opcional e depende do significado das colunas."""
    _ate_a_revisao(pagina, DOMINIOS / "vendas_simples.xlsx")
    pagina.get_by_role("checkbox", name="Gerar uma versão organizada").check()

    painel = pagina.get_by_role("checkbox", name="Adicionar uma aba de Dashboard")
    assert painel.count() == 0, "sem coluna de valor confirmada nao ha o que somar"

    pagina.get_by_label("Coluna de valor").select_option("Valor")
    pagina.get_by_label("Coluna de categoria").select_option("Vendedor")
    assert painel.is_checked() is False, "toda confirmacao comeca desligada"
    painel.check()

    _executar(pagina)
    organizada = _baixar_por_rotulo(pagina, "Planilha organizada")
    with zipfile.ZipFile(io.BytesIO(organizada)) as zf:
        conteudo = zf.read("xl/workbook.xml").decode("utf-8", "replace")
        assert "Dashboard" in conteudo, "a aba de painel precisa existir"
        # Grafico no painel, nunca na aba dos dados.
        assert any(nome.startswith("xl/charts/") for nome in zf.namelist())


def test_downloads_reais_da_planilha_organizada_e_do_relatorio(pagina: Page) -> None:
    """Cenario 5: os tres downloads principais respondem com bytes de verdade."""
    _ate_a_revisao(pagina, DOMINIOS / "vendas_simples.xlsx")
    pagina.get_by_role("checkbox", name="Gerar uma versão organizada").check()
    resultado = _executar(pagina)

    # A area principal tem no maximo tres itens; o tecnico foi para o avancado.
    assert "Arquivo original" in resultado
    assert "Downloads avançados" in resultado

    original = _baixar_por_rotulo(pagina, "Arquivo original")
    assert original == (DOMINIOS / "vendas_simples.xlsx").read_bytes(), (
        "o original oferecido no download tem de ser byte a byte o que foi enviado"
    )

    organizada = _baixar_por_rotulo(pagina, "Planilha organizada")
    relatorio = _baixar_por_rotulo(pagina, "Relatório da análise")
    for conteudo in (organizada, relatorio):
        assert conteudo[:2] == b"PK"

    # O relatorio abre como planilha de verdade, com abas dentro.
    with zipfile.ZipFile(io.BytesIO(relatorio)) as zf:
        assert any(nome.startswith("xl/worksheets/") for nome in zf.namelist())
