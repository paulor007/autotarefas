"""
Testes da SendApiTask.

ESTRATEGIA:
- Mocka httpx.post com um responder configuravel por payload
  (retorna httpx.Response reais, p/ raise_for_status/json autenticos).
- Testes de retry mockam tenacity.nap.sleep.
- Planilhas reais em tmp_path.

Cobertura:
- Validacao do construtor
- Envio (sucesso, planilha vazia)
- Parcial / falha total
- dry-run
- Retry (recupera/esgota/nao-retenta-4xx)
- _is_retryable
- Relatorio (salvo, conteudo)
- Auth (X-API-Key, Bearer)
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
from autotarefas.tasks.send_api import SendApiTask

if TYPE_CHECKING:
    from pathlib import Path

send_api_module = importlib.import_module("autotarefas.tasks.send_api")

URL = "http://test.local/api/clientes"


# ============================================================
# Helpers
# ============================================================


def make_response(status_code: int, json_data: dict[str, Any] | None = None) -> httpx.Response:
    """httpx.Response real (raise_for_status/json funcionam)."""
    request = httpx.Request("POST", URL)
    return httpx.Response(status_code, json=json_data or {}, request=request)


def criar_csv(path: Path, linhas: list[dict[str, str]]) -> None:
    """Cria um CSV a partir de uma lista de dicts."""
    pd.DataFrame(linhas).to_csv(path, index=False)


def linhas_ok(n: int) -> list[dict[str, str]]:
    """Gera n linhas validas."""
    return [
        {"nome": f"Cliente {i}", "email": f"c{i}@x.com", "cpf": f"cpf-{i}"} for i in range(1, n + 1)
    ]


def make_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", URL)
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("erro", request=request, response=response)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_post(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """
    Mocka httpx.post. Por default responde 201 a tudo.

    Configure state["responder"] = lambda payload: (status, body_dict)
    Inspecione state["calls"] e state["headers"].
    """
    state: dict[str, Any] = {
        "responder": lambda _payload: (201, {"status": "ok", "data": {"id": 1}}),
        "calls": 0,
        "headers": None,
    }

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        state["calls"] += 1
        state["headers"] = kwargs.get("headers")
        payload = kwargs.get("json", {})
        status, body = state["responder"](payload)
        return make_response(status, body)

    monkeypatch.setattr(httpx, "post", fake_post)
    return state


@pytest.fixture
def _fast_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove a espera entre tentativas do tenacity."""
    monkeypatch.setattr("tenacity.nap.sleep", lambda _seconds: None)


# ============================================================
# Construtor
# ============================================================


class TestConstrutor:
    def test_url_vazia(self, tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        with pytest.raises(ValidationError):
            SendApiTask(planilha_path=csv, url="")

    def test_planilha_extensao_invalida(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            SendApiTask(planilha_path=tmp_path / "c.txt", url=URL)

    def test_report_extensao_invalida(self, tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        with pytest.raises(ValidationError):
            SendApiTask(
                planilha_path=csv,
                url=URL,
                report_path=tmp_path / "r.txt",
            )

    def test_delay_negativo(self, tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        with pytest.raises(ValidationError):
            SendApiTask(planilha_path=csv, url=URL, delay_s=-1.0)


# ============================================================
# Envio
# ============================================================


class TestEnvio:
    def test_todas_sucesso(
        self,
        mock_post: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(3))
        result = SendApiTask(planilha_path=csv, url=URL).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 3
        assert result.rows_failed == 0
        assert mock_post["calls"] == 3

    def test_planilha_vazia(
        self,
        mock_post: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        csv.write_text("nome,email,cpf\n", encoding="utf-8")
        result = SendApiTask(planilha_path=csv, url=URL).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 0
        assert mock_post["calls"] == 0  # nada enviado


# ============================================================
# Parcial / falha
# ============================================================


class TestParcialFalha:
    def test_parcial(
        self,
        mock_post: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        """1 linha com cpf 'BAD' falha (422); resto OK -> PARTIAL."""

        def responder(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
            if payload.get("cpf") == "BAD":
                return 422, {"error": "Validacao falhou", "detalhes": ["cpf"]}
            return 201, {"status": "ok"}

        mock_post["responder"] = responder

        csv = tmp_path / "c.csv"
        criar_csv(
            csv,
            [
                {"nome": "A", "email": "a@x.com", "cpf": "ok-1"},
                {"nome": "B", "email": "b@x.com", "cpf": "BAD"},
                {"nome": "C", "email": "c@x.com", "cpf": "ok-2"},
            ],
        )
        result = SendApiTask(planilha_path=csv, url=URL).run()
        assert result.status == TaskStatus.PARTIAL
        assert result.rows_affected == 2
        assert result.rows_failed == 1

    def test_falha_total(
        self,
        mock_post: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        """Todas 409 -> FAILURE."""
        mock_post["responder"] = lambda _p: (409, {"error": "CPF ja cadastrado"})
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(3))
        result = SendApiTask(planilha_path=csv, url=URL).run()
        assert result.status == TaskStatus.FAILURE
        assert result.rows_affected == 0
        assert result.rows_failed == 3


# ============================================================
# Dry-run
# ============================================================


class TestDryRun:
    def test_nao_envia(
        self,
        mock_post: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(5))
        result = SendApiTask(planilha_path=csv, url=URL, dry_run=True).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.data["would_send"] == 5
        assert mock_post["calls"] == 0  # nada enviado


# ============================================================
# Retry
# ============================================================


@pytest.mark.usefixtures("_fast_retry")
class TestRetry:
    def test_recupera_de_erro_temporario(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        calls = {"n": 0}

        def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] <= 2:
                raise httpx.ConnectError("temp")
            return make_response(201, {"status": "ok"})

        monkeypatch.setattr(httpx, "post", fake_post)

        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        result = SendApiTask(
            planilha_path=csv,
            url=URL,
            max_retries=3,
        ).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 1
        assert calls["n"] == 3  # 2 falhas + 1 sucesso

    def test_5xx_esgota_vira_falha_da_linha(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            return make_response(503, {"error": "indisponivel"})

        monkeypatch.setattr(httpx, "post", fake_post)

        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        result = SendApiTask(
            planilha_path=csv,
            url=URL,
            max_retries=2,
        ).run()
        assert result.status == TaskStatus.FAILURE
        assert result.rows_failed == 1

    def test_4xx_nao_retenta(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        calls = {"n": 0}

        def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            calls["n"] += 1
            return make_response(409, {"error": "dup"})

        monkeypatch.setattr(httpx, "post", fake_post)

        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        SendApiTask(planilha_path=csv, url=URL, max_retries=3).run()
        assert calls["n"] == 1  # nao retentou 4xx


# ============================================================
# _is_retryable
# ============================================================


class TestIsRetryable:
    def test_transport_error(self) -> None:
        assert send_api_module._is_retryable(httpx.ConnectError("x")) is True

    def test_5xx(self) -> None:
        assert send_api_module._is_retryable(make_status_error(503)) is True

    def test_4xx(self) -> None:
        assert send_api_module._is_retryable(make_status_error(409)) is False
        assert send_api_module._is_retryable(make_status_error(422)) is False

    def test_outra(self) -> None:
        assert send_api_module._is_retryable(ValueError("x")) is False


# ============================================================
# Relatorio
# ============================================================


class TestRelatorio:
    def test_salva_relatorio(
        self,
        mock_post: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(2))
        report = tmp_path / "rel.csv"
        result = SendApiTask(
            planilha_path=csv,
            url=URL,
            report_path=report,
        ).run()
        assert report.exists()
        assert result.data["report_path"] == str(report)
        df = pd.read_csv(report)
        assert "_resultado" in df.columns
        assert "_mensagem" in df.columns
        assert len(df) == 2

    def test_sem_relatorio(
        self,
        mock_post: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(2))
        result = SendApiTask(planilha_path=csv, url=URL).run()
        assert result.data["report_path"] is None


# ============================================================
# Auth
# ============================================================


class TestAuth:
    def test_api_key(
        self,
        mock_post: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        SendApiTask(
            planilha_path=csv,
            url=URL,
            api_key="k123",  # pragma: allowlist secret
        ).run()
        assert mock_post["headers"].get("X-API-Key") == "k123"  # pragma: allowlist secret

    def test_bearer(
        self,
        mock_post: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        SendApiTask(
            planilha_path=csv,
            url=URL,
            bearer_token="t456",  # pragma: allowlist secret
        ).run()
        assert mock_post["headers"].get("Authorization") == "Bearer t456"


# ============================================================
# Progresso
# ============================================================


class TestProgress:
    def test_callback_por_linha(
        self,
        mock_post: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(3))
        chamadas: list[dict[str, Any]] = []
        SendApiTask(
            planilha_path=csv,
            url=URL,
            on_progress=chamadas.append,
        ).run()
        assert len(chamadas) == 3
        assert chamadas[0]["linha"] == 1
        assert chamadas[-1]["linha"] == 3

    def test_callback_com_erro_nao_quebra(
        self,
        mock_post: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(2))

        def ruim(_info: dict[str, Any]) -> None:
            msg = "falhou"
            raise RuntimeError(msg)

        result = SendApiTask(
            planilha_path=csv,
            url=URL,
            on_progress=ruim,
        ).run()
        assert result.status == TaskStatus.SUCCESS
