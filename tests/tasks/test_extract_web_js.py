"""
Testes do modo JS (Playwright) da ExtractWebTask.

ESTRATEGIA:
- Mocka autotarefas.core.browser.BrowserSession por uma FakeSession
  configuravel (serve {url: html}, conta sessoes abertas, registra
  navegacao e esperas, e pode levantar erros REAIS do Playwright).
- O modo httpx continua coberto por test_extract_web.py; aqui so o --js.
- Retry mocka tenacity.nap.sleep (sem esperar).

Cobertura:
- Validacao do construtor (wait_for exige use_js; timeout_s; defaults)
- Fetch via navegador: reuso de UMA sessao na paginacao, wait_for,
  propagacao de headless/timeout_ms
- execute: sucesso, paginacao, dry-run, 0 itens
- Erros: navegador nao instalado, timeout (esgota e recupera)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.extract_web import ExtractWebTask

if TYPE_CHECKING:
    from pathlib import Path

URL = "http://test.local/catalogo"
URL2 = "http://test.local/catalogo/p2"
ROW = "tr.produto"
FIELDS = {"id": "td.id", "nome": "td.nome", "preco": "td.preco"}
NEXT = "a.next"


# ============================================================
# Helpers
# ============================================================


def make_html(produtos: list[dict[str, Any]], next_href: str | None = None) -> str:
    linhas = "".join(
        f'<tr class="produto">'
        f'<td class="id">{p["id"]}</td>'
        f'<td class="nome">{p["nome"]}</td>'
        f'<td class="preco">{p["preco"]}</td>'
        f"</tr>"
        for p in produtos
    )
    nav = f'<a class="next" href="{next_href}">Proxima</a>' if next_href else ""
    return (
        f'<html><body><table class="produtos"><tbody>{linhas}</tbody>'
        f"</table><nav>{nav}</nav></body></html>"
    )


def produtos(*ids: int) -> list[dict[str, Any]]:
    return [{"id": i, "nome": f"Produto {i}", "preco": f"{i}.00"} for i in ids]


def make_task(tmp_path: Path, **kw: Any) -> ExtractWebTask:
    defaults: dict[str, Any] = {
        "url": URL,
        "output_path": tmp_path / "out.csv",
        "row_selector": ROW,
        "fields": FIELDS,
        "next_selector": NEXT,
        "use_js": True,
    }
    defaults.update(kw)
    return ExtractWebTask(**defaults)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_browser(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """
    Mocka BrowserSession. Configure:
      state["pages"]: dict {url: html} servido por content()
      state["enter_raises"]: excecao no __enter__ (ex: navegador ausente)
      state["goto_raises"]: excecao sempre que go_to e chamado
      state["goto_fail_times"] + state["goto_fail_exc"]: falha N vezes e
        depois funciona (testa recuperacao por retry)
      state["wait_raises"]: excecao no wait_for
    Inspecione: state["sessions"] (sessoes abertas), state["calls"] (urls
    navegadas), state["waited"] (seletores), state["headless"]/["timeout_ms"].
    """
    state: dict[str, Any] = {
        "pages": {},
        "enter_raises": None,
        "goto_raises": None,
        "goto_fail_times": 0,
        "goto_fail_exc": None,
        "wait_raises": None,
        "sessions": 0,
        "calls": [],
        "waited": [],
        "headless": None,
        "timeout_ms": None,
    }

    class FakeSession:
        def __init__(
            self,
            *,
            headless: bool = True,
            timeout_ms: int = 30000,
            **_kw: Any,
        ) -> None:
            state["sessions"] += 1
            state["headless"] = headless
            state["timeout_ms"] = timeout_ms
            self._cur: str | None = None

        def __enter__(self) -> FakeSession:
            if state["enter_raises"] is not None:
                raise state["enter_raises"]
            return self

        def __exit__(self, *_a: object) -> Literal[False]:
            return False

        def go_to(self, url: str) -> None:
            state["calls"].append(url)
            if state["goto_raises"] is not None:
                raise state["goto_raises"]
            if state["goto_fail_times"] > 0:
                state["goto_fail_times"] -= 1
                raise state["goto_fail_exc"]
            self._cur = url

        def wait_for(self, selector: str, *, timeout_ms: int | None = None) -> None:
            state["waited"].append(selector)
            if state["wait_raises"] is not None:
                raise state["wait_raises"]

        def content(self) -> str:
            return str(state["pages"].get(self._cur, ""))

    monkeypatch.setattr("autotarefas.core.browser.BrowserSession", FakeSession)
    return state


@pytest.fixture
def _fast_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tenacity.nap.sleep", lambda _seconds: None)


# ============================================================
# Construtor
# ============================================================


class TestConstrutorJS:
    def test_wait_for_sem_js_levanta(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractWebTask(
                url=URL,
                output_path=tmp_path / "o.csv",
                row_selector=ROW,
                fields=FIELDS,
                use_js=False,
                wait_for="div.x",
            )

    def test_timeout_invalido_levanta(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            make_task(tmp_path, timeout_s=0)

    def test_wait_for_com_js_ok(self, tmp_path: Path) -> None:
        task = make_task(tmp_path, wait_for="table.produtos")
        assert task.wait_for == "table.produtos"
        assert task.use_js is True

    def test_use_js_default_false(self, tmp_path: Path) -> None:
        task = ExtractWebTask(
            url=URL,
            output_path=tmp_path / "o.csv",
            row_selector=ROW,
            fields=FIELDS,
        )
        assert task.use_js is False
        assert task.headless is True


# ============================================================
# Fetch via navegador
# ============================================================


@pytest.mark.usefixtures("_fast_retry")
class TestFetchJS:
    def test_reusa_uma_sessao_na_paginacao(
        self,
        tmp_path: Path,
        mock_browser: dict[str, Any],
    ) -> None:
        mock_browser["pages"] = {
            URL: make_html(produtos(1, 2), next_href=URL2),
            URL2: make_html(produtos(3)),
        }
        result = make_task(tmp_path).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 3
        # uma unica sessao de navegador, duas paginas navegadas
        assert mock_browser["sessions"] == 1
        assert mock_browser["calls"] == [URL, URL2]

    def test_wait_for_e_chamado(
        self,
        tmp_path: Path,
        mock_browser: dict[str, Any],
    ) -> None:
        mock_browser["pages"] = {URL: make_html(produtos(1))}
        make_task(tmp_path, wait_for="table.produtos", next_selector=None).run()
        assert mock_browser["waited"] == ["table.produtos"]

    def test_sem_wait_for_nao_espera(
        self,
        tmp_path: Path,
        mock_browser: dict[str, Any],
    ) -> None:
        mock_browser["pages"] = {URL: make_html(produtos(1))}
        make_task(tmp_path, next_selector=None).run()
        assert mock_browser["waited"] == []

    def test_propaga_headless_e_timeout(
        self,
        tmp_path: Path,
        mock_browser: dict[str, Any],
    ) -> None:
        mock_browser["pages"] = {URL: make_html(produtos(1))}
        make_task(tmp_path, headless=False, timeout_s=10, next_selector=None).run()
        assert mock_browser["headless"] is False
        assert mock_browser["timeout_ms"] == 10000


# ============================================================
# execute
# ============================================================


@pytest.mark.usefixtures("_fast_retry")
class TestExecuteJS:
    def test_sucesso_salva_csv(
        self,
        tmp_path: Path,
        mock_browser: dict[str, Any],
    ) -> None:
        mock_browser["pages"] = {URL: make_html(produtos(1, 2, 3))}
        out = tmp_path / "saida.csv"
        result = make_task(tmp_path, output_path=out, next_selector=None).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 3
        assert out.exists()
        assert result.data["use_js"] is True

    def test_dry_run_nao_salva(
        self,
        tmp_path: Path,
        mock_browser: dict[str, Any],
    ) -> None:
        mock_browser["pages"] = {URL: make_html(produtos(1, 2), next_href=URL2)}
        out = tmp_path / "saida.csv"
        result = make_task(tmp_path, output_path=out, dry_run=True).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.data["would_extract_first_page"] == 2
        assert result.data["has_next"] is True
        assert not out.exists()
        assert mock_browser["sessions"] == 1

    def test_zero_itens_sucesso_sem_salvar(
        self,
        tmp_path: Path,
        mock_browser: dict[str, Any],
    ) -> None:
        mock_browser["pages"] = {URL: make_html([])}
        out = tmp_path / "saida.csv"
        result = make_task(tmp_path, output_path=out, next_selector=None).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 0
        assert result.data["saved"] is False
        assert not out.exists()


# ============================================================
# Erros do navegador
# ============================================================


@pytest.mark.usefixtures("_fast_retry")
class TestErrosJS:
    def test_navegador_nao_instalado(
        self,
        tmp_path: Path,
        mock_browser: dict[str, Any],
    ) -> None:
        mock_browser["enter_raises"] = PlaywrightError(
            "Executable doesn't exist at /root/.cache/ms-playwright/chromium-1/chrome",
        )
        result = make_task(tmp_path).run()
        assert result.status == TaskStatus.FAILURE
        assert result.error_message is not None
        assert "playwright install chromium" in result.error_message

    def test_timeout_esgota_retries(
        self,
        tmp_path: Path,
        mock_browser: dict[str, Any],
    ) -> None:
        mock_browser["goto_raises"] = PlaywrightTimeoutError("Timeout 30000ms exceeded")
        result = make_task(tmp_path, max_retries=3, next_selector=None).run()
        assert result.status == TaskStatus.FAILURE
        assert result.error_message is not None
        assert "Tempo esgotado" in result.error_message
        # tentou max_retries vezes (a 1a pagina) antes de desistir
        assert len(mock_browser["calls"]) == 3

    def test_timeout_recupera(
        self,
        tmp_path: Path,
        mock_browser: dict[str, Any],
    ) -> None:
        # falha 1x com timeout, depois funciona
        mock_browser["goto_fail_times"] = 1
        mock_browser["goto_fail_exc"] = PlaywrightTimeoutError("Timeout")
        mock_browser["pages"] = {URL: make_html(produtos(1, 2))}
        result = make_task(tmp_path, max_retries=3, next_selector=None).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 2
        assert len(mock_browser["calls"]) == 2  # 1 falha + 1 sucesso

    def test_timeout_message_inclui_wait_for(
        self,
        tmp_path: Path,
        mock_browser: dict[str, Any],
    ) -> None:
        mock_browser["wait_raises"] = PlaywrightTimeoutError("Timeout")
        mock_browser["pages"] = {URL: make_html(produtos(1))}
        result = make_task(
            tmp_path,
            max_retries=1,
            wait_for="table.produtos",
            next_selector=None,
        ).run()
        assert result.status == TaskStatus.FAILURE
        assert result.error_message is not None
        assert "table.produtos" in result.error_message
