"""
Testes da ExtractWebTask.

ESTRATEGIA:
- Mocka httpx.Client por um FakeClient que serve um dicionario
  {url: html} e devolve httpx.Response REAIS (raise_for_status funciona).
- Paginacao testada com hrefs RELATIVOS (exercita o urljoin).
- Testes de retry mockam tenacity.nap.sleep (sem esperar).
- Sem rede real.

Cobertura:
- Validacao do construtor
- Parsing por seletores CSS (campos, campo ausente)
- Paginacao (segue next, sem next, max_pages, anti-loop)
- dry-run; 0 itens; formatos CSV/JSON
- Retry (recupera de 5xx; esgota; nao retenta 4xx); _is_retryable
- Callback de progresso
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, Literal

import httpx
import pandas as pd
import pytest

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.extract_web import ExtractWebTask

if TYPE_CHECKING:
    from pathlib import Path

web_module = importlib.import_module("autotarefas.tasks.extract_web")

URL = "http://test.local/catalogo"
ROW = "tr.produto"
FIELDS = {"id": "td.id", "nome": "td.nome", "preco": "td.preco"}
NEXT = "a.next"


# ============================================================
# Helpers
# ============================================================


def make_html(produtos: list[dict[str, Any]], next_href: str | None = None) -> str:
    """Monta uma pagina HTML com a tabela de produtos (e link opcional)."""
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


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_http(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """
    Mocka httpx.Client. Configure:
      state["pages"]: {url: html}
      state["status_queue"]: lista de status codes (p/ retry); None = sempre 200
    Inspecione:
      state["calls"]
    """
    state: dict[str, Any] = {"pages": {}, "status_queue": None, "calls": 0}

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> Literal[False]:
            return False

        def get(self, url: str, **kwargs: Any) -> httpx.Response:
            state["calls"] += 1
            html = state["pages"].get(url, "")
            queue = state["status_queue"]
            code = queue.pop(0) if queue else 200
            return httpx.Response(
                code,
                text=html or "<html><body></body></html>",
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(httpx, "Client", FakeClient)
    return state


@pytest.fixture
def _fast_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tenacity.nap.sleep", lambda _seconds: None)


# ============================================================
# Construtor
# ============================================================


class TestConstrutor:
    def test_url_vazia(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractWebTask(url="", output_path=tmp_path / "p.csv", row_selector=ROW, fields=FIELDS)

    def test_output_invalido(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractWebTask(url=URL, output_path=tmp_path / "p.txt", row_selector=ROW, fields=FIELDS)

    def test_row_selector_vazio(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractWebTask(url=URL, output_path=tmp_path / "p.csv", row_selector="", fields=FIELDS)

    def test_fields_vazio(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractWebTask(url=URL, output_path=tmp_path / "p.csv", row_selector=ROW, fields={})

    def test_max_pages_zero(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractWebTask(
                url=URL,
                output_path=tmp_path / "p.csv",
                row_selector=ROW,
                fields=FIELDS,
                max_pages=0,
            )

    def test_delay_negativo(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractWebTask(
                url=URL,
                output_path=tmp_path / "p.csv",
                row_selector=ROW,
                fields=FIELDS,
                delay_s=-1.0,
            )


# ============================================================
# Parsing
# ============================================================


class TestParsing:
    def test_extrai_campos(self, mock_http: dict[str, Any], tmp_path: Path) -> None:
        mock_http["pages"] = {URL: make_html(produtos(1, 2))}
        out = tmp_path / "p.csv"
        result = ExtractWebTask(
            url=URL,
            output_path=out,
            row_selector=ROW,
            fields=FIELDS,
        ).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 2
        df = pd.read_csv(out)
        assert list(df.columns) == ["id", "nome", "preco"]
        assert df.iloc[0]["nome"] == "Produto 1"

    def test_campo_ausente_vira_vazio(
        self,
        mock_http: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        # HTML sem td.preco -> coluna preco vazia
        html = (
            '<table class="produtos"><tbody>'
            '<tr class="produto"><td class="id">1</td><td class="nome">X</td></tr>'
            "</tbody></table>"
        )
        mock_http["pages"] = {URL: html}
        out = tmp_path / "p.csv"
        result = ExtractWebTask(
            url=URL,
            output_path=out,
            row_selector=ROW,
            fields=FIELDS,
        ).run()
        assert result.rows_affected == 1
        df = pd.read_csv(out, dtype=str, keep_default_na=False)
        assert df.iloc[0]["preco"] == ""


# ============================================================
# Paginacao
# ============================================================


class TestPaginacao:
    def test_segue_paginacao(self, mock_http: dict[str, Any], tmp_path: Path) -> None:
        mock_http["pages"] = {
            URL: make_html(produtos(1), next_href="?page=2"),
            f"{URL}?page=2": make_html(produtos(2), next_href="?page=3"),
            f"{URL}?page=3": make_html(produtos(3)),
        }
        out = tmp_path / "p.csv"
        result = ExtractWebTask(
            url=URL,
            output_path=out,
            row_selector=ROW,
            fields=FIELDS,
            next_selector=NEXT,
        ).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 3

    def test_sem_next_selector_uma_pagina(
        self,
        mock_http: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_http["pages"] = {URL: make_html(produtos(1, 2), next_href="?page=2")}
        out = tmp_path / "p.csv"
        result = ExtractWebTask(
            url=URL,
            output_path=out,
            row_selector=ROW,
            fields=FIELDS,
            next_selector=None,
        ).run()
        # sem next_selector, ignora o link -> so 1 pagina
        assert result.rows_affected == 2
        assert mock_http["calls"] == 1

    def test_max_pages_limita(
        self,
        mock_http: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_http["pages"] = {
            URL: make_html(produtos(1), next_href="?page=2"),
            f"{URL}?page=2": make_html(produtos(2), next_href="?page=3"),
            f"{URL}?page=3": make_html(produtos(3)),
        }
        out = tmp_path / "p.csv"
        result = ExtractWebTask(
            url=URL,
            output_path=out,
            row_selector=ROW,
            fields=FIELDS,
            next_selector=NEXT,
            max_pages=2,
        ).run()
        assert result.rows_affected == 2  # parou na 2a pagina
        assert mock_http["calls"] == 2

    def test_anti_loop(self, mock_http: dict[str, Any], tmp_path: Path) -> None:
        # next aponta para a propria pagina -> nao entra em loop
        mock_http["pages"] = {URL: make_html(produtos(1), next_href=URL)}
        out = tmp_path / "p.csv"
        result = ExtractWebTask(
            url=URL,
            output_path=out,
            row_selector=ROW,
            fields=FIELDS,
            next_selector=NEXT,
        ).run()
        assert result.rows_affected == 1
        assert mock_http["calls"] == 1


# ============================================================
# Dry-run / vazio / formatos
# ============================================================


class TestDryRun:
    def test_nao_salva(self, mock_http: dict[str, Any], tmp_path: Path) -> None:
        mock_http["pages"] = {URL: make_html(produtos(1, 2), next_href="?page=2")}
        out = tmp_path / "p.csv"
        result = ExtractWebTask(
            url=URL,
            output_path=out,
            row_selector=ROW,
            fields=FIELDS,
            next_selector=NEXT,
            dry_run=True,
        ).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.data["dry_run"] is True
        assert result.data["would_extract_first_page"] == 2
        assert result.data["has_next"] is True
        assert not out.exists()


class TestVazio:
    def test_zero_itens(self, mock_http: dict[str, Any], tmp_path: Path) -> None:
        mock_http["pages"] = {URL: "<html><body><p>nada aqui</p></body></html>"}
        out = tmp_path / "p.csv"
        result = ExtractWebTask(
            url=URL,
            output_path=out,
            row_selector=ROW,
            fields=FIELDS,
        ).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 0
        assert not out.exists()


class TestFormatos:
    def test_json(self, mock_http: dict[str, Any], tmp_path: Path) -> None:
        mock_http["pages"] = {URL: make_html(produtos(1, 2, 3))}
        out = tmp_path / "p.json"
        result = ExtractWebTask(
            url=URL,
            output_path=out,
            row_selector=ROW,
            fields=FIELDS,
        ).run()
        assert result.status == TaskStatus.SUCCESS
        assert out.exists()
        assert out.read_text(encoding="utf-8").strip().startswith("[")


# ============================================================
# Retry
# ============================================================


@pytest.mark.usefixtures("_fast_retry")
class TestRetry:
    def test_recupera_de_5xx(self, mock_http: dict[str, Any], tmp_path: Path) -> None:
        mock_http["pages"] = {URL: make_html(produtos(1))}
        mock_http["status_queue"] = [500, 200]  # falha 1x, depois ok
        out = tmp_path / "p.csv"
        result = ExtractWebTask(
            url=URL,
            output_path=out,
            row_selector=ROW,
            fields=FIELDS,
        ).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 1
        assert mock_http["calls"] == 2

    def test_esgota_retries(self, mock_http: dict[str, Any], tmp_path: Path) -> None:
        mock_http["pages"] = {URL: make_html(produtos(1))}
        mock_http["status_queue"] = [500, 500, 500]
        out = tmp_path / "p.csv"
        result = ExtractWebTask(
            url=URL,
            output_path=out,
            row_selector=ROW,
            fields=FIELDS,
            max_retries=3,
        ).run()
        assert result.status == TaskStatus.FAILURE
        assert mock_http["calls"] == 3

    def test_nao_retenta_4xx(self, mock_http: dict[str, Any], tmp_path: Path) -> None:
        mock_http["pages"] = {URL: make_html(produtos(1))}
        mock_http["status_queue"] = [404]
        out = tmp_path / "p.csv"
        result = ExtractWebTask(
            url=URL,
            output_path=out,
            row_selector=ROW,
            fields=FIELDS,
        ).run()
        assert result.status == TaskStatus.FAILURE
        assert mock_http["calls"] == 1  # nao retentou


class TestIsRetryable:
    def test_transport_error(self) -> None:
        exc = httpx.ConnectError("falha")
        assert web_module._is_retryable(exc) is True

    def test_timeout(self) -> None:
        exc = httpx.ReadTimeout("timeout")
        assert web_module._is_retryable(exc) is True

    def test_5xx(self) -> None:
        req = httpx.Request("GET", URL)
        exc = httpx.HTTPStatusError(
            "erro",
            request=req,
            response=httpx.Response(503, request=req),
        )
        assert web_module._is_retryable(exc) is True

    def test_4xx(self) -> None:
        req = httpx.Request("GET", URL)
        exc = httpx.HTTPStatusError(
            "erro",
            request=req,
            response=httpx.Response(404, request=req),
        )
        assert web_module._is_retryable(exc) is False

    def test_outra_excecao(self) -> None:
        assert web_module._is_retryable(ValueError("x")) is False


# ============================================================
# Progresso
# ============================================================


class TestProgresso:
    def test_callback_por_pagina(
        self,
        mock_http: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_http["pages"] = {
            URL: make_html(produtos(1), next_href="?page=2"),
            f"{URL}?page=2": make_html(produtos(2)),
        }
        chamadas: list[dict[str, object]] = []
        ExtractWebTask(
            url=URL,
            output_path=tmp_path / "p.csv",
            row_selector=ROW,
            fields=FIELDS,
            next_selector=NEXT,
            on_progress=chamadas.append,
        ).run()
        assert len(chamadas) == 2
        assert chamadas[0]["page"] == 1
        assert chamadas[1]["total"] == 2

    def test_callback_com_erro_nao_quebra(
        self,
        mock_http: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_http["pages"] = {URL: make_html(produtos(1))}

        def quebra(_info: dict[str, object]) -> None:
            raise RuntimeError("boom")

        result = ExtractWebTask(
            url=URL,
            output_path=tmp_path / "p.csv",
            row_selector=ROW,
            fields=FIELDS,
            on_progress=quebra,
        ).run()
        # callback quebrou, mas a task concluiu
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 1
