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
    """
    Remove a espera entre tentativas.

    tenacity.nap.sleep delega a time.sleep — e o Retrying captura a
    funcao default no import, entao patchear tenacity.nap.sleep depois
    NAO tem efeito. O patch efetivo e em time.sleep.
    """
    monkeypatch.setattr("time.sleep", lambda _seconds: None)


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

    def test_timeout_invalido(self, tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        with pytest.raises(ValidationError):
            SendApiTask(planilha_path=csv, url=URL, timeout_s=0)

    def test_max_retries_invalido(self, tmp_path: Path) -> None:
        csv = tmp_path / "c.csv"
        criar_csv(csv, linhas_ok(1))
        with pytest.raises(ValidationError):
            SendApiTask(planilha_path=csv, url=URL, max_retries=0)


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

    def test_429_retentavel(self) -> None:
        # rate limit e temporario: o servidor pediu calma, nao recusou o dado
        assert send_api_module._is_retryable(make_status_error(429)) is True

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


# ============================================================
# Resultado estruturado por item (Cadastro automatico)
# ============================================================


class TestItensEstruturados:
    def test_sucesso_captura_id_externo(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(1))
        mock_post["responder"] = lambda _p: (201, {"status": "ok", "data": {"id": 42}})

        result = SendApiTask(planilha_path=csv, url=URL).run()

        item = result.data["items"][0]
        assert item["sucesso"] is True
        assert item["status_http"] == 201
        assert item["categoria"] == "sucesso"
        assert item["id_externo"] == "42"
        assert item["tentativas"] == 1
        assert item["pode_reenviar"] is False
        assert "id 42" in item["mensagem"]

    def test_linha_fisica_como_na_auditoria(
        self, tmp_path: Path, mock_post: dict[str, Any]
    ) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(3))
        result = SendApiTask(planilha_path=csv, url=URL).run()
        # cabecalho = 1 -> primeira linha de dados = 2
        assert [i["linha"] for i in result.data["items"]] == [2, 3, 4]

    def test_422_vira_validacao_sem_reenvio(
        self, tmp_path: Path, mock_post: dict[str, Any]
    ) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(1))
        mock_post["responder"] = lambda _p: (
            422,
            {"error": "Validacao falhou", "detalhes": ["cpf invalido"]},
        )

        result = SendApiTask(planilha_path=csv, url=URL).run()

        item = result.data["items"][0]
        assert item["categoria"] == "validacao"
        assert item["status_http"] == 422
        assert item["pode_reenviar"] is False
        assert "cpf invalido" in item["mensagem"]

    def test_409_vira_duplicado(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(1))
        mock_post["responder"] = lambda _p: (409, {"error": "CPF ja cadastrado"})

        result = SendApiTask(planilha_path=csv, url=URL).run()

        item = result.data["items"][0]
        assert item["categoria"] == "duplicado"
        assert item["pode_reenviar"] is False

    @pytest.mark.usefixtures("_fast_retry")
    def test_429_vira_rate_limit_reenviavel(
        self, tmp_path: Path, mock_post: dict[str, Any]
    ) -> None:
        # 429 e retentado (fase 3); se persistir ate esgotar as tentativas,
        # a linha fica como rate_limit e reenviavel.
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(1))
        mock_post["responder"] = lambda _p: (429, {"error": "muitas requisicoes"})

        result = SendApiTask(planilha_path=csv, url=URL, max_retries=2).run()

        item = result.data["items"][0]
        assert item["categoria"] == "rate_limit"
        assert item["pode_reenviar"] is True
        assert item["tentativas"] == 2
        assert result.data["reenviaveis"] == 1

    @pytest.mark.usefixtures("_fast_retry")
    def test_5xx_esgotado_vira_temporario_com_tentativas(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(1))

        def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            return make_response(503, {"error": "instavel"})

        monkeypatch.setattr(httpx, "post", fake_post)

        result = SendApiTask(planilha_path=csv, url=URL, max_retries=3).run()

        item = result.data["items"][0]
        assert item["categoria"] == "temporario"
        assert item["status_http"] == 503
        assert item["tentativas"] == 3
        assert item["pode_reenviar"] is True

    @pytest.mark.usefixtures("_fast_retry")
    def test_recupera_na_segunda_tentativa_registra_tentativas(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(1))
        chamadas = {"n": 0}

        def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                return make_response(503, {"error": "instavel"})
            return make_response(201, {"status": "ok", "data": {"id": 5}})

        monkeypatch.setattr(httpx, "post", fake_post)

        result = SendApiTask(planilha_path=csv, url=URL).run()

        item = result.data["items"][0]
        assert item["sucesso"] is True
        assert item["tentativas"] == 2
        assert item["id_externo"] == "5"

    def test_conexao_sem_status(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(1))

        def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            raise httpx.ConnectError("sem rede", request=httpx.Request("POST", URL))

        monkeypatch.setattr(httpx, "post", fake_post)
        monkeypatch.setattr("time.sleep", lambda _s: None)

        result = SendApiTask(planilha_path=csv, url=URL).run()

        item = result.data["items"][0]
        assert item["categoria"] == "conexao"
        assert item["status_http"] is None
        assert item["pode_reenviar"] is True

    def test_falhas_por_categoria_no_data(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(
            csv,
            [
                {"nome": "A", "email": "a@x.com", "cpf": "ok"},
                {"nome": "B", "email": "b@x.com", "cpf": "invalido"},
                {"nome": "C", "email": "c@x.com", "cpf": "duplicado"},
            ],
        )

        def responder(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
            if payload["cpf"] == "invalido":
                return 422, {"error": "Validacao falhou"}
            if payload["cpf"] == "duplicado":
                return 409, {"error": "CPF ja cadastrado"}
            return 201, {"status": "ok", "data": {"id": 1}}

        mock_post["responder"] = responder

        result = SendApiTask(planilha_path=csv, url=URL).run()

        assert result.data["falhas_por_categoria"] == {"validacao": 1, "duplicado": 1}
        assert result.data["reenviaveis"] == 0
        assert result.data["enviados"] == 1

    def test_relatorio_legado_ganha_colunas_novas(
        self, tmp_path: Path, mock_post: dict[str, Any]
    ) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(1))
        report = tmp_path / "rel.csv"

        SendApiTask(planilha_path=csv, url=URL, report_path=report).run()

        df = pd.read_csv(report)
        for coluna in (
            "_status_http",
            "_categoria",
            "_id_externo",
            "_tentativas",
            "_pode_reenviar",
        ):
            assert coluna in df.columns


# ============================================================
# Retry inteligente (Retry-After) e idempotencia — fase 3
# ============================================================


def make_response_with_headers(
    status_code: int,
    json_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request("POST", URL)
    return httpx.Response(status_code, json=json_data or {}, headers=headers, request=request)


class TestRetryInteligente:
    def test_429_respeita_retry_after(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(1))
        esperas: list[float] = []
        monkeypatch.setattr("time.sleep", esperas.append)
        chamadas = {"n": 0}

        def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                return make_response_with_headers(
                    429, {"error": "calma"}, headers={"Retry-After": "2"}
                )
            return make_response(201, {"status": "ok", "data": {"id": 8}})

        monkeypatch.setattr(httpx, "post", fake_post)

        result = SendApiTask(planilha_path=csv, url=URL).run()

        item = result.data["items"][0]
        assert item["sucesso"] is True
        assert item["tentativas"] == 2
        # a espera foi EXATAMENTE o que a API pediu (2s), nao o backoff
        assert esperas == [2.0]

    def test_429_sem_retry_after_usa_backoff(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(1))
        esperas: list[float] = []
        monkeypatch.setattr("time.sleep", esperas.append)
        chamadas = {"n": 0}

        def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                return make_response(429, {"error": "calma"})
            return make_response(201, {"status": "ok", "data": {"id": 8}})

        monkeypatch.setattr(httpx, "post", fake_post)

        result = SendApiTask(planilha_path=csv, url=URL).run()

        assert result.data["items"][0]["sucesso"] is True
        # backoff com jitter: uma espera, positiva e dentro do teto do fallback
        assert len(esperas) == 1
        assert 0 < esperas[0] <= 5.5

    def test_retry_after_exagerado_respeita_teto(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(1))
        esperas: list[float] = []
        monkeypatch.setattr("time.sleep", esperas.append)
        chamadas = {"n": 0}

        def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                return make_response_with_headers(
                    429, {"error": "calma"}, headers={"Retry-After": "9999"}
                )
            return make_response(201, {"status": "ok", "data": {"id": 8}})

        monkeypatch.setattr(httpx, "post", fake_post)

        SendApiTask(planilha_path=csv, url=URL).run()

        assert esperas == [30.0]  # _RETRY_AFTER_CAP_S


class TestIdempotencia:
    def test_header_enviado_e_estavel_entre_tentativas(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(1))
        monkeypatch.setattr("time.sleep", lambda _s: None)
        keys: list[str] = []

        def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            keys.append(kwargs["headers"]["Idempotency-Key"])
            if len(keys) == 1:
                return make_response(503, {"error": "instavel"})
            return make_response(201, {"status": "ok", "data": {"id": 3}})

        monkeypatch.setattr(httpx, "post", fake_post)

        result = SendApiTask(planilha_path=csv, url=URL).run()

        # duas tentativas do MESMO registro -> a MESMA chave nas duas
        assert len(keys) == 2
        assert keys[0] == keys[1]
        assert result.data["items"][0]["idempotency_key"] == keys[0]

    def test_registros_diferentes_chaves_diferentes(
        self, tmp_path: Path, mock_post: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(2))
        keys: list[str] = []

        def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            keys.append(kwargs["headers"]["Idempotency-Key"])
            return make_response(201, {"status": "ok", "data": {"id": 1}})

        monkeypatch.setattr(httpx, "post", fake_post)

        SendApiTask(planilha_path=csv, url=URL).run()

        assert len(keys) == 2
        assert keys[0] != keys[1]

    def test_reexecucao_gera_as_mesmas_chaves(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # a MESMA planilha enviada duas vezes produz as MESMAS chaves:
        # e isso que permite reenviar sem duplicar.
        csv = tmp_path / "d.csv"
        criar_csv(csv, linhas_ok(2))
        keys: list[str] = []

        def fake_post(url: str, **kwargs: Any) -> httpx.Response:
            keys.append(kwargs["headers"]["Idempotency-Key"])
            return make_response(201, {"status": "ok", "data": {"id": 1}})

        monkeypatch.setattr(httpx, "post", fake_post)

        SendApiTask(planilha_path=csv, url=URL).run()
        SendApiTask(planilha_path=csv, url=URL).run()

        assert keys[:2] == keys[2:]
