"""
Testes do BrowserSession.

ESTRATEGIA: mockar 100% do Playwright. Os testes NAO abrem browser
real - cada teste configura mocks encadeados e verifica chamadas.

Cobertura:
- __init__: validacoes de timeout_ms, browser_type, screenshot_dir
- Context manager: enter/exit + ordem de inicializacao
- Navegacao: go_to, fill, click, wait_for
- Inspecao: text, is_visible, current_url
- Screenshots: normal e com mascaramento
- Cleanup robusto: exit tolera erros em close()
- _ensure_page: levanta antes do __enter__
- verify_playwright_installed: ok e falha
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from autotarefas.core import browser as browser_module
from autotarefas.core.browser import BrowserSession, verify_playwright_installed

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mocks(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """
    Configura mocks encadeados para sync_playwright.

    Retorna dict com referencias para verificacoes nos testes:
        - sync_playwright_factory: mock substituto de sync_playwright
        - playwright: instancia retornada por .start()
        - browser, context, page: tres niveis de mocks
    """
    sync_playwright_factory = MagicMock(name="sync_playwright")
    playwright_inst = MagicMock(name="playwright_instance")
    browser = MagicMock(name="browser")
    context = MagicMock(name="context")
    page = MagicMock(name="page")

    # Chain: sync_playwright().start() -> playwright
    sync_playwright_factory.return_value.start.return_value = playwright_inst

    # Cada browser type retorna o mesmo browser mock (simplifica)
    playwright_inst.chromium.launch.return_value = browser
    playwright_inst.firefox.launch.return_value = browser
    playwright_inst.webkit.launch.return_value = browser

    browser.new_context.return_value = context
    context.new_page.return_value = page

    # page.url precisa retornar string (nao MagicMock)
    page.url = "http://localhost:5555/"

    monkeypatch.setattr(
        browser_module,
        "sync_playwright",
        sync_playwright_factory,
    )

    return {
        "sync_playwright_factory": sync_playwright_factory,
        "playwright": playwright_inst,
        "browser": browser,
        "context": context,
        "page": page,
    }


@pytest.fixture
def screenshot_dir(tmp_path: Path) -> Path:
    """Pasta de screenshots isolada por teste."""
    return tmp_path / "screenshots"


# ============================================================
# Testes de __init__
# ============================================================


class TestInit:
    """Validacoes no construtor."""

    def test_timeout_ms_zero_levanta(self, screenshot_dir: Path) -> None:
        with pytest.raises(ValueError, match="timeout_ms"):
            BrowserSession(timeout_ms=0, screenshot_dir=screenshot_dir)

    def test_timeout_ms_negativo_levanta(self, screenshot_dir: Path) -> None:
        with pytest.raises(ValueError, match="timeout_ms"):
            BrowserSession(timeout_ms=-1, screenshot_dir=screenshot_dir)

    def test_browser_type_invalido_levanta(self, screenshot_dir: Path) -> None:
        with pytest.raises(ValueError, match="browser_type"):
            BrowserSession(
                browser_type="opera",  # type: ignore[arg-type]
                screenshot_dir=screenshot_dir,
            )

    def test_screenshot_dir_custom_eh_respeitado(
        self,
        screenshot_dir: Path,
    ) -> None:
        session = BrowserSession(screenshot_dir=screenshot_dir)
        assert session.screenshot_dir == screenshot_dir

    def test_defaults(self, screenshot_dir: Path) -> None:
        """Defaults: headless=True, timeout=30000, browser=chromium."""
        session = BrowserSession(screenshot_dir=screenshot_dir)
        assert session.headless is True
        assert session.timeout_ms == 30_000
        assert session.browser_type == "chromium"


# ============================================================
# Testes do context manager (__enter__ / __exit__)
# ============================================================


class TestContextManager:
    """Inicializacao e cleanup."""

    def test_enter_inicia_playwright_browser_context_page(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        with BrowserSession(screenshot_dir=screenshot_dir) as session:
            assert session is not None

        # Verificou que iniciou os 4 niveis
        mocks["sync_playwright_factory"].assert_called_once()
        mocks["playwright"].chromium.launch.assert_called_once()
        mocks["browser"].new_context.assert_called_once()
        mocks["context"].new_page.assert_called_once()

    def test_enter_respeita_headless_true(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        with BrowserSession(headless=True, screenshot_dir=screenshot_dir):
            pass
        mocks["playwright"].chromium.launch.assert_called_once_with(headless=True)

    def test_enter_respeita_headless_false(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        with BrowserSession(headless=False, screenshot_dir=screenshot_dir):
            pass
        mocks["playwright"].chromium.launch.assert_called_once_with(headless=False)

    def test_enter_seta_default_timeout(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        with BrowserSession(timeout_ms=5000, screenshot_dir=screenshot_dir):
            pass
        mocks["page"].set_default_timeout.assert_called_once_with(5000)

    def test_enter_usa_browser_type_firefox(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        with BrowserSession(
            browser_type="firefox",
            screenshot_dir=screenshot_dir,
        ):
            pass
        # Firefox foi chamado, chromium nao
        mocks["playwright"].firefox.launch.assert_called_once()
        mocks["playwright"].chromium.launch.assert_not_called()

    def test_enter_cria_screenshot_dir(
        self,
        mocks: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "nova_pasta"
        assert not target.exists()
        with BrowserSession(screenshot_dir=target):
            pass
        assert target.exists()

    def test_exit_fecha_tudo_em_ordem(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        with BrowserSession(screenshot_dir=screenshot_dir):
            pass
        mocks["page"].close.assert_called_once()
        mocks["context"].close.assert_called_once()
        mocks["browser"].close.assert_called_once()
        mocks["playwright"].stop.assert_called_once()

    def test_exit_tolera_erro_em_close(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        """Erro em page.close() nao impede browser.close()."""
        mocks["page"].close.side_effect = RuntimeError("boom")

        # Nao deve levantar
        with BrowserSession(screenshot_dir=screenshot_dir):
            pass

        # Mesmo com erro em page, browser/playwright foram fechados
        mocks["browser"].close.assert_called_once()
        mocks["playwright"].stop.assert_called_once()


# ============================================================
# Testes de navegacao
# ============================================================


class TestNavigation:
    """go_to, fill, click, wait_for."""

    def test_go_to(self, mocks: dict[str, Any], screenshot_dir: Path) -> None:
        with BrowserSession(screenshot_dir=screenshot_dir) as session:
            session.go_to("http://localhost:5555/cadastro")
        mocks["page"].goto.assert_called_once_with(
            "http://localhost:5555/cadastro",
            wait_until="domcontentloaded",
        )

    def test_fill(self, mocks: dict[str, Any], screenshot_dir: Path) -> None:
        with BrowserSession(screenshot_dir=screenshot_dir) as session:
            session.fill("#nome", "Ana Silva")
        mocks["page"].locator.assert_called_once_with("#nome")
        mocks["page"].locator.return_value.fill.assert_called_once_with("Ana Silva")

    def test_click(self, mocks: dict[str, Any], screenshot_dir: Path) -> None:
        with BrowserSession(screenshot_dir=screenshot_dir) as session:
            session.click("#btn-cadastrar")
        mocks["page"].locator.assert_called_once_with("#btn-cadastrar")
        mocks["page"].locator.return_value.click.assert_called_once()

    def test_wait_for_usa_timeout_default(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        with BrowserSession(timeout_ms=15000, screenshot_dir=screenshot_dir) as s:
            s.wait_for("#record-id")

        locator = mocks["page"].locator.return_value
        mocks["page"].locator.assert_called_once_with("#record-id")
        locator.nth.assert_called_once_with(0)
        locator.nth.return_value.wait_for.assert_called_once_with(
            timeout=15000,
            state="visible",
        )

    def test_wait_for_usa_timeout_custom(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        with BrowserSession(screenshot_dir=screenshot_dir) as s:
            s.wait_for("#x", timeout_ms=1000)

        locator = mocks["page"].locator.return_value
        mocks["page"].locator.assert_called_once_with("#x")
        locator.nth.assert_called_once_with(0)
        locator.nth.return_value.wait_for.assert_called_once_with(
            timeout=1000,
            state="visible",
        )


# ============================================================
# Testes de inspecao
# ============================================================


class TestInspection:
    """text, is_visible, current_url."""

    def test_text_retorna_text_content(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        mocks["page"].locator.return_value.text_content.return_value = "Ana Silva"
        with BrowserSession(screenshot_dir=screenshot_dir) as s:
            result = s.text("#nome")
        assert result == "Ana Silva"

    def test_text_retorna_vazio_se_text_content_none(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        mocks["page"].locator.return_value.text_content.return_value = None
        with BrowserSession(screenshot_dir=screenshot_dir) as s:
            result = s.text("#vazio")
        assert result == ""

    def test_is_visible_true(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        mocks["page"].locator.return_value.is_visible.return_value = True
        with BrowserSession(screenshot_dir=screenshot_dir) as s:
            assert s.is_visible("#x") is True

    def test_is_visible_false(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        mocks["page"].locator.return_value.is_visible.return_value = False
        with BrowserSession(screenshot_dir=screenshot_dir) as s:
            assert s.is_visible("#x") is False

    def test_current_url(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        mocks["page"].url = "http://localhost:5555/sucesso/42"
        with BrowserSession(screenshot_dir=screenshot_dir) as s:
            assert s.current_url() == "http://localhost:5555/sucesso/42"

    def test_content_retorna_html_renderizado(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        html = "<html><body><table><tr><td>Ana</td></tr></table></body></html>"
        mocks["page"].content.return_value = html
        with BrowserSession(screenshot_dir=screenshot_dir) as s:
            assert s.content() == html


# ============================================================
# Testes de screenshots
# ============================================================


class TestScreenshots:
    """screenshot e screenshot_safe."""

    def test_screenshot_adiciona_png_no_nome(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        with BrowserSession(screenshot_dir=screenshot_dir) as s:
            path = s.screenshot("teste")
        assert path.name == "teste.png"
        mocks["page"].screenshot.assert_called_once()

    def test_screenshot_mantem_png_existente(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        with BrowserSession(screenshot_dir=screenshot_dir) as s:
            path = s.screenshot("ja_tem.png")
        assert path.name == "ja_tem.png"

    def test_screenshot_safe_filtra_selectors_existentes(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        """Apenas selectors com count > 0 entram na mask."""

        # Configura page.locator pra retornar contagens diferentes
        # baseado no selector
        def locator_side_effect(selector: str) -> MagicMock:
            mock_locator = MagicMock()
            # password e cpf existem; secret e token nao
            if "password" in selector or "cpf" in selector:
                mock_locator.count.return_value = 1
            else:
                mock_locator.count.return_value = 0
            return mock_locator

        mocks["page"].locator.side_effect = locator_side_effect

        with BrowserSession(screenshot_dir=screenshot_dir) as s:
            s.screenshot_safe(
                "test",
                sensitive_selectors=[
                    "input[type='password']",
                    "input[name*='cpf']",
                    "input[name*='secret']",
                    "input[name*='token']",
                ],
            )

        # page.screenshot foi chamado com mask nao-vazia
        call_args = mocks["page"].screenshot.call_args
        masks = call_args.kwargs.get("mask")
        assert masks is not None
        assert len(masks) == 2  # apenas password + cpf

    def test_screenshot_safe_sem_selectors_passa_mask_none(
        self,
        mocks: dict[str, Any],
        screenshot_dir: Path,
    ) -> None:
        """Se nenhum selector sensivel existe na pagina, mask=None."""
        mocks["page"].locator.return_value.count.return_value = 0

        with BrowserSession(screenshot_dir=screenshot_dir) as s:
            s.screenshot_safe("test", sensitive_selectors=["#nao-existe"])

        call_args = mocks["page"].screenshot.call_args
        assert call_args.kwargs.get("mask") is None


# ============================================================
# Testes de _ensure_page (uso incorreto)
# ============================================================


class TestEnsurePage:
    """Uso fora do context manager."""

    def test_page_property_fora_de_with_levanta(
        self,
        screenshot_dir: Path,
    ) -> None:
        session = BrowserSession(screenshot_dir=screenshot_dir)
        with pytest.raises(RuntimeError, match="nao foi iniciada"):
            _ = session.page

    def test_go_to_fora_de_with_levanta(
        self,
        screenshot_dir: Path,
    ) -> None:
        session = BrowserSession(screenshot_dir=screenshot_dir)
        with pytest.raises(RuntimeError, match="nao foi iniciada"):
            session.go_to("http://x.com")

    def test_content_fora_de_with_levanta(
        self,
        screenshot_dir: Path,
    ) -> None:
        session = BrowserSession(screenshot_dir=screenshot_dir)
        with pytest.raises(RuntimeError, match="nao foi iniciada"):
            session.content()


# ============================================================
# Testes de verify_playwright_installed
# ============================================================


class TestVerifyPlaywrightInstalled:
    """Helper de troubleshooting."""

    def test_retorna_ok_quando_funcional(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Mock pra sucesso."""
        # Patch direto do sync_playwright no modulo
        mock_factory = MagicMock()
        mock_playwright_cm = MagicMock()
        mock_factory.return_value = mock_playwright_cm

        # Context manager: __enter__ retorna playwright
        mock_playwright = MagicMock()
        mock_playwright_cm.__enter__.return_value = mock_playwright
        mock_playwright_cm.__exit__.return_value = False

        # chromium.launch().close() encadeado
        mock_browser = MagicMock()
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.chromium.executable_path = "/fake/chromium"

        monkeypatch.setattr(browser_module, "sync_playwright", mock_factory)

        result = verify_playwright_installed()
        assert result["ok"] is True
        assert result["error"] is None
        assert result["browser_executable"] == "/fake/chromium"

    def test_retorna_erro_quando_falha(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Mock pra erro."""
        mock_factory = MagicMock()
        mock_factory.side_effect = RuntimeError("Playwright nao instalado")
        monkeypatch.setattr(browser_module, "sync_playwright", mock_factory)

        result = verify_playwright_installed()
        assert result["ok"] is False
        assert result["error"] is not None
        assert "Playwright nao instalado" in result["error"]
        assert result["browser_executable"] is None
