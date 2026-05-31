"""
Testes da ExtractApiTask.

ESTRATEGIA:
- Mocka httpx.get retornando httpx.Response REAIS (paginacao simulada),
  para que raise_for_status() e .json() funcionem de verdade.
- Testes de retry mockam tenacity.nap.sleep (sem esperar de fato).
- Sem rede real.

Cobertura:
- Validacao do construtor
- Paginacao automatica (segue has_next, max_pages)
- Formatos de saida (CSV/XLSX/JSON)
- dry-run (preview, nao salva)
- Retry (recupera de erro temporario; esgota; nao retenta 4xx)
- _is_retryable
- Auth (header X-API-Key)
- Callback de progresso
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

import httpx
import pandas as pd
import pytest

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.extract_api import ExtractApiTask

if TYPE_CHECKING:
    from pathlib import Path

# Modulo (para acessar a funcao privada _is_retryable)
extract_api_module = importlib.import_module("autotarefas.tasks.extract_api")

URL = "http://test.local/api/clientes"


# ============================================================
# Helpers
# ============================================================


def make_response(status_code: int, json_data: dict[str, Any]) -> httpx.Response:
    """Cria um httpx.Response real (raise_for_status/json funcionam)."""
    request = httpx.Request("GET", URL)
    return httpx.Response(status_code, json=json_data, request=request)


def make_payload(page: int, per_page: int, total: int) -> dict[str, Any]:
    """Monta o payload paginado no formato do demo."""
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    data = [
        {"id": i, "nome": f"Cliente {i}", "email": f"c{i}@x.com"}
        for i in range(start + 1, min(end, total) + 1)
    ]
    return {
        "data": data,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
    }


def make_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Cria um httpx.HTTPStatusError com o status indicado."""
    request = httpx.Request("GET", URL)
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("erro", request=request, response=response)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_api(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """
    Mocka httpx.get simulando a API. Por default 47 registros.
    Retorna um state dict: ajuste state["total"] para mudar.
    Tambem captura os ultimos headers em state["headers"].
    """
    state: dict[str, Any] = {"total": 47, "headers": None}

    def fake_get(url: str, **kwargs: Any) -> httpx.Response:
        state["headers"] = kwargs.get("headers")
        params = kwargs.get("params", {})
        return make_response(
            200,
            make_payload(params["page"], params["per_page"], state["total"]),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    return state


@pytest.fixture
def _fast_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove a espera entre tentativas do tenacity (testes rapidos)."""
    monkeypatch.setattr("tenacity.nap.sleep", lambda _seconds: None)


# ============================================================
# Construtor / validacao
# ============================================================


class TestConstrutor:
    """Validacoes do __init__ (falham cedo com ValidationError)."""

    def test_url_vazia(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractApiTask(url="", output_path=tmp_path / "o.csv")

    def test_url_so_espacos(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractApiTask(url="   ", output_path=tmp_path / "o.csv")

    def test_extensao_invalida(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractApiTask(url=URL, output_path=tmp_path / "o.txt")

    def test_per_page_zero(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractApiTask(url=URL, output_path=tmp_path / "o.csv", per_page=0)

    def test_max_pages_zero(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractApiTask(url=URL, output_path=tmp_path / "o.csv", max_pages=0)

    def test_delay_negativo(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ExtractApiTask(url=URL, output_path=tmp_path / "o.csv", delay_s=-1.0)

    @pytest.mark.parametrize("ext", [".csv", ".xlsx", ".json"])
    def test_extensoes_validas(self, tmp_path: Path, ext: str) -> None:
        # Nao deve levantar
        task = ExtractApiTask(url=URL, output_path=tmp_path / f"o{ext}")
        assert task.output_path.suffix == ext


# ============================================================
# Paginacao
# ============================================================


class TestPaginacao:
    """Percorre paginas seguindo has_next."""

    def test_extrai_todas_as_paginas(
        self,
        mock_api: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_api["total"] = 47
        task = ExtractApiTask(
            url=URL,
            output_path=tmp_path / "o.csv",
            per_page=10,
        )
        result = task.run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 47

    def test_max_pages_limita(
        self,
        mock_api: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_api["total"] = 47
        task = ExtractApiTask(
            url=URL,
            output_path=tmp_path / "o.csv",
            per_page=10,
            max_pages=2,
        )
        result = task.run()
        assert result.rows_affected == 20  # 2 paginas de 10

    def test_zero_registros(
        self,
        mock_api: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_api["total"] = 0
        out = tmp_path / "o.csv"
        task = ExtractApiTask(url=URL, output_path=out, per_page=10)
        result = task.run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 0
        assert result.data["saved"] is False
        assert not out.exists()  # nao salva quando vazio


# ============================================================
# Formatos de saida
# ============================================================


class TestOutputFormats:
    """CSV / XLSX / JSON pela extensao."""

    def test_csv(self, mock_api: dict[str, Any], tmp_path: Path) -> None:
        mock_api["total"] = 25
        out = tmp_path / "dados.csv"
        ExtractApiTask(url=URL, output_path=out, per_page=10).run()
        assert out.exists()
        df = pd.read_csv(out)
        assert len(df) == 25

    def test_json(self, mock_api: dict[str, Any], tmp_path: Path) -> None:
        mock_api["total"] = 25
        out = tmp_path / "dados.json"
        ExtractApiTask(url=URL, output_path=out, per_page=10).run()
        assert out.exists()
        df = pd.read_json(out)
        assert len(df) == 25

    def test_xlsx(self, mock_api: dict[str, Any], tmp_path: Path) -> None:
        mock_api["total"] = 25
        out = tmp_path / "dados.xlsx"
        ExtractApiTask(url=URL, output_path=out, per_page=10).run()
        assert out.exists()
        df = pd.read_excel(out)
        assert len(df) == 25


# ============================================================
# Dry-run
# ============================================================


class TestDryRun:
    """dry-run busca so a primeira pagina e nao salva."""

    def test_preview_sem_salvar(
        self,
        mock_api: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_api["total"] = 47
        out = tmp_path / "nao_criar.csv"
        task = ExtractApiTask(
            url=URL,
            output_path=out,
            per_page=10,
            dry_run=True,
        )
        result = task.run()
        assert result.status == TaskStatus.SUCCESS
        assert result.data["would_extract"] == 47
        assert result.data["total_pages"] == 5
        assert not out.exists()


# ============================================================
# Retry
# ============================================================


@pytest.mark.usefixtures("_fast_retry")
class TestRetry:
    """Retry em erros temporarios; nao retenta 4xx."""

    def test_recupera_de_erro_temporario(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        calls = {"n": 0}

        def fake_get(url: str, **kwargs: Any) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] <= 2:
                raise httpx.ConnectError("falha temporaria")
            params = kwargs["params"]
            return make_response(
                200,
                make_payload(params["page"], params["per_page"], 10),
            )

        monkeypatch.setattr(httpx, "get", fake_get)

        task = ExtractApiTask(
            url=URL,
            output_path=tmp_path / "o.csv",
            per_page=10,
            max_retries=3,
        )
        result = task.run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 10
        assert calls["n"] == 3  # 2 falhas + 1 sucesso

    def test_esgota_retries(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        def fake_get(url: str, **kwargs: Any) -> httpx.Response:
            raise httpx.ConnectError("sempre falha")

        monkeypatch.setattr(httpx, "get", fake_get)

        task = ExtractApiTask(
            url=URL,
            output_path=tmp_path / "o.csv",
            per_page=10,
            max_retries=3,
        )
        result = task.run()
        assert result.status == TaskStatus.FAILURE
        assert result.error_message is not None

    def test_nao_retenta_4xx(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        calls = {"n": 0}

        def fake_get(url: str, **kwargs: Any) -> httpx.Response:
            calls["n"] += 1
            return make_response(404, {})  # raise_for_status -> 404

        monkeypatch.setattr(httpx, "get", fake_get)

        task = ExtractApiTask(
            url=URL,
            output_path=tmp_path / "o.csv",
            per_page=10,
            max_retries=3,
        )
        result = task.run()
        assert result.status == TaskStatus.FAILURE
        assert calls["n"] == 1  # nao tentou de novo (4xx)


# ============================================================
# _is_retryable
# ============================================================


class TestIsRetryable:
    """Predicado de retry."""

    def test_transport_error_retenta(self) -> None:
        exc = httpx.ConnectError("x")  # subclasse de TransportError
        assert extract_api_module._is_retryable(exc) is True

    def test_timeout_retenta(self) -> None:
        exc = httpx.ReadTimeout("x")
        assert extract_api_module._is_retryable(exc) is True

    def test_http_5xx_retenta(self) -> None:
        assert extract_api_module._is_retryable(make_status_error(500)) is True
        assert extract_api_module._is_retryable(make_status_error(503)) is True

    def test_http_4xx_nao_retenta(self) -> None:
        assert extract_api_module._is_retryable(make_status_error(404)) is False
        assert extract_api_module._is_retryable(make_status_error(403)) is False

    def test_outra_excecao_nao_retenta(self) -> None:
        assert extract_api_module._is_retryable(ValueError("x")) is False


# ============================================================
# Auth
# ============================================================


class TestAuth:
    """Header X-API-Key."""

    def test_api_key_vai_no_header(
        self,
        mock_api: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_api["total"] = 5
        task = ExtractApiTask(
            url=URL,
            output_path=tmp_path / "o.csv",
            per_page=10,
            api_key="segredo123",  # pragma: allowlist secret
        )
        task.run()
        headers = mock_api["headers"]
        assert headers is not None
        assert headers.get("X-API-Key") == "segredo123"  # pragma: allowlist secret

    def test_sem_api_key_sem_header(
        self,
        mock_api: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_api["total"] = 5
        task = ExtractApiTask(
            url=URL,
            output_path=tmp_path / "o.csv",
            per_page=10,
        )
        task.run()
        headers = mock_api["headers"]
        assert "X-API-Key" not in headers


# ============================================================
# Progresso
# ============================================================


class TestProgress:
    """Callback de progresso."""

    def test_callback_chamado_por_pagina(
        self,
        mock_api: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_api["total"] = 47  # 5 paginas
        chamadas: list[dict[str, Any]] = []
        task = ExtractApiTask(
            url=URL,
            output_path=tmp_path / "o.csv",
            per_page=10,
            on_progress=chamadas.append,
        )
        task.run()
        assert len(chamadas) == 5
        assert chamadas[0]["page"] == 1
        assert chamadas[-1]["page"] == 5

    def test_callback_com_erro_nao_quebra(
        self,
        mock_api: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_api["total"] = 10

        def callback_ruim(_info: dict[str, Any]) -> None:
            msg = "callback falhou"
            raise RuntimeError(msg)

        task = ExtractApiTask(
            url=URL,
            output_path=tmp_path / "o.csv",
            per_page=10,
            on_progress=callback_ruim,
        )
        result = task.run()
        # erro no callback nao quebra a extracao
        assert result.status == TaskStatus.SUCCESS
