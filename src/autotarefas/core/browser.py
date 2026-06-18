"""
Wrapper Playwright para automacao web no AutoTarefas.

Abstracao limpa sobre o Playwright que encapsula:

- ``sync_playwright()`` em context manager
- Modo headless (default) ou headful (debug)
- Timeouts seguros (30s default)
- Helpers de navegacao (``go_to``, ``fill``, ``click``, ``wait_for``)
- Helpers de inspecao (``text``, ``is_visible``, ``current_url``)
- Screenshots com mascaramento automatico de campos sensiveis
- Logging de cada acao
- Cleanup garantido (browser fecha mesmo em erro)

Uso:
    from autotarefas.core.browser import BrowserSession

    with BrowserSession() as browser:
        browser.go_to("http://localhost:5555/cadastro")
        browser.fill("#nome", "Ana Silva")
        browser.click("#btn-cadastrar")
        browser.wait_for("#record-id")
        record_id = browser.text("#record-id")
        browser.screenshot_safe("ana.png")

Dependencias: requer ``playwright`` instalado via extra ``[rpa]``:

    pip install -e ".[rpa]"
    playwright install chromium

Aviso: a importacao deste modulo FALHA se playwright nao estiver
instalado. Importe apenas em codigo que faz parte do fluxo RPA.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any, ClassVar, Literal

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    sync_playwright,
)

from autotarefas.core.logger import logger
from autotarefas.core.settings import settings

BrowserTypeName = Literal["chromium", "firefox", "webkit"]

# ============================================================
# Constantes
# ============================================================

#: Timeout padrao (ms) para acoes do Playwright.
_DEFAULT_TIMEOUT_MS: int = 30_000

#: Selectors CSS de elementos considerados sensiveis.
_DEFAULT_SENSITIVE_SELECTORS: tuple[str, ...] = (
    "input[type='password']",
    "input[name*='cpf' i]",
    "input[name*='cnpj' i]",
    "input[name*='senha' i]",
    "input[name*='password' i]",
    "input[name*='token' i]",
    "input[name*='secret' i]",
    "input[name*='card' i]",
    "input[name*='cartao' i]",
    "input[name*='credit' i]",
    "input[name*='credito' i]",
)

#: Cor da mascara em screenshots.
_MASK_COLOR: str = "#FF00FF"


class BrowserSession:
    """
    Context manager para sessao de browser Playwright.

    Args:
        headless: Se True, navegador sem janela. Se False, mostra a janela.
        timeout_ms: Timeout default em ms para todas as acoes.
        screenshot_dir: Pasta onde salvar screenshots.
        browser_type: ``"chromium"``, ``"firefox"`` ou ``"webkit"``.

    Atributos:
        page: Acesso direto ao Page do Playwright.
    """

    DEFAULT_TIMEOUT_MS: ClassVar[int] = _DEFAULT_TIMEOUT_MS
    DEFAULT_SENSITIVE_SELECTORS: ClassVar[tuple[str, ...]] = _DEFAULT_SENSITIVE_SELECTORS

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = _DEFAULT_TIMEOUT_MS,
        screenshot_dir: Path | None = None,
        browser_type: BrowserTypeName = "chromium",
    ) -> None:
        if timeout_ms <= 0:
            raise ValueError(f"timeout_ms deve ser > 0, recebeu: {timeout_ms}")

        if browser_type not in ("chromium", "firefox", "webkit"):
            raise ValueError(
                f"browser_type deve ser chromium/firefox/webkit, recebeu: {browser_type}"
            )

        self.headless = headless
        self.timeout_ms = timeout_ms
        self.browser_type = browser_type
        self.screenshot_dir: Path = (
            screenshot_dir
            if screenshot_dir is not None
            else settings.autotarefas_home / "screenshots"
        )

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self) -> BrowserSession:
        """Inicia Playwright, abre browser/context/page."""
        logger.debug(
            "Iniciando BrowserSession (browser={browser}, headless={hl})",
            browser=self.browser_type,
            hl=self.headless,
        )

        playwright = sync_playwright().start()
        self._playwright = playwright

        if self.browser_type == "chromium":
            browser = playwright.chromium.launch(headless=self.headless)
        elif self.browser_type == "firefox":
            browser = playwright.firefox.launch(headless=self.headless)
        else:
            browser = playwright.webkit.launch(headless=self.headless)

        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(self.timeout_ms)

        self._browser = browser
        self._context = context
        self._page = page

        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Cleanup: fecha page, context, browser e playwright."""
        logger.debug("Fechando BrowserSession")

        if self._page is not None:
            try:
                self._page.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Erro fechando page: {err}", err=str(exc))
            self._page = None

        if self._context is not None:
            try:
                self._context.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Erro fechando context: {err}", err=str(exc))
            self._context = None

        if self._browser is not None:
            try:
                self._browser.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Erro fechando browser: {err}", err=str(exc))
            self._browser = None

        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Erro parando playwright: {err}", err=str(exc))
            self._playwright = None

    @property
    def page(self) -> Page:
        """Acesso direto ao Page do Playwright."""
        return self._ensure_page()

    def _ensure_page(self) -> Page:
        """Garante que ha uma Page ativa."""
        if self._page is None:
            raise RuntimeError(
                "BrowserSession nao foi iniciada. Use 'with BrowserSession() as ...'"
            )
        return self._page

    def go_to(self, url: str) -> None:
        """Navega para uma URL e espera a pagina carregar."""
        logger.debug("go_to: {url}", url=url)
        page = self._ensure_page()
        page.goto(url, wait_until="domcontentloaded")

    def fill(self, selector: str, value: str) -> None:
        """Preenche um campo de input."""
        logger.debug("fill: {sel} = '{val}'", sel=selector, val=value)
        page = self._ensure_page()
        page.locator(selector).fill(value)

    def click(self, selector: str) -> None:
        """Clica em um elemento."""
        logger.debug("click: {sel}", sel=selector)
        page = self._ensure_page()
        page.locator(selector).click()

    def wait_for(
        self,
        selector: str,
        *,
        timeout_ms: int | None = None,
    ) -> None:
        """Espera ate que pelo menos um elemento do seletor fique visivel."""
        actual_timeout = timeout_ms if timeout_ms is not None else self.timeout_ms
        logger.debug(
            "wait_for: {sel} (timeout={timeout}ms)",
            sel=selector,
            timeout=actual_timeout,
        )

        page = self._ensure_page()
        page.locator(selector).nth(0).wait_for(
            timeout=actual_timeout,
            state="visible",
        )

    def text(self, selector: str) -> str:
        """Retorna o texto de um elemento."""
        page = self._ensure_page()
        content = page.locator(selector).text_content()
        return content or ""

    def is_visible(self, selector: str) -> bool:
        """Retorna True se elemento existe e esta visivel."""
        page = self._ensure_page()
        visible: bool = page.locator(selector).is_visible()
        return visible

    def current_url(self) -> str:
        """Retorna URL atual da pagina."""
        page = self._ensure_page()
        url: str = page.url
        return url

    def content(self) -> str:
        """Retorna o HTML renderizado da pagina inteira (apos o JavaScript)."""
        page = self._ensure_page()
        html: str = page.content()
        return html

    def screenshot(self, name: str) -> Path:
        """
        Tira screenshot sem mascaramento.

        Use apenas em paginas confirmadas sem dados sensiveis.
        """
        path = self._resolve_screenshot_path(name)
        logger.debug("screenshot: {path}", path=str(path))

        page = self._ensure_page()
        page.screenshot(path=str(path), full_page=True)

        return path

    def screenshot_safe(
        self,
        name: str,
        *,
        sensitive_selectors: list[str] | None = None,
    ) -> Path:
        """Tira screenshot mascarando campos sensiveis."""
        selectors = (
            sensitive_selectors
            if sensitive_selectors is not None
            else list(self.DEFAULT_SENSITIVE_SELECTORS)
        )

        path = self._resolve_screenshot_path(name)
        page = self._ensure_page()

        masks: list[Locator] = []

        for selector in selectors:
            locator = page.locator(selector)
            count = locator.count()

            if count > 0:
                masks.append(locator)
                logger.debug(
                    "screenshot_safe: mascarando {count} elemento(s) com '{sel}'",
                    count=count,
                    sel=selector,
                )

        logger.debug(
            "screenshot_safe: {path} ({count} mascaras)",
            path=str(path),
            count=len(masks),
        )

        page.screenshot(
            path=str(path),
            full_page=True,
            mask=masks or None,
            mask_color=_MASK_COLOR,
        )

        return path

    def _resolve_screenshot_path(self, name: str) -> Path:
        """Resolve path absoluto para screenshot."""
        if not name.lower().endswith(".png"):
            name = f"{name}.png"

        return self.screenshot_dir / name


def verify_playwright_installed() -> dict[str, Any]:
    """
    Verifica se Playwright esta instalado e funcional.

    Returns:
        Dict com:
        - ok: True se tudo estiver funcionando.
        - error: mensagem de erro, se houver.
        - browser_executable: path do navegador, se disponivel.
    """
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            executable = playwright.chromium.executable_path
            browser.close()

            return {
                "ok": True,
                "error": None,
                "browser_executable": executable,
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc),
            "browser_executable": None,
        }


__all__ = [
    "BrowserSession",
    "verify_playwright_installed",
]
