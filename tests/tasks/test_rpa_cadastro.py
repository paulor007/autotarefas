"""
Testes do RPACadastroTask.

ESTRATEGIA:
- Prioriza testes via execute() (interface publica) - robustos a refactor
- Health check: monkeypatch em httpx.get (fixtures _health_ok/_health_offline)
- BrowserSession: monkeypatch (mock como context manager)
- Planilhas: CSV/XLSX reais em tmp_path

NOTA sobre fixtures side-effect:
- _health_ok e _health_offline so fazem monkeypatch (retornam None).
  Por isso tem prefixo _ (PT004) e sao injetadas via
  @pytest.mark.usefixtures (PT019), nao como parametro.
- mock_browser RETORNA um valor (o mock), entao continua como parametro.

Cobertura:
- __init__: validacoes
- execute: server offline (SKIPPED), planilha invalida (FAILURE),
  schema invalido (FAILURE), dry-run, execucao real
- Cenarios por linha: success, skip (CPF invalido / duplicado), error
- Callback on_progress
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pandas as pd
import pytest

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks import rpa_cadastro as rpa_module
from autotarefas.tasks.rpa_cadastro import RPACadastroTask

# CPFs validos reais (passam no algoritmo modulo 11)
CPF_ANA = "529.982.247-25"
CPF_BRUNO = "111.444.777-35"
CPF_INVALIDO = "000.000.000-00"

BASE_URL = "http://localhost:5555"

# ============================================================
# Fixtures de planilha
# ============================================================


@pytest.fixture
def csv_validos(tmp_path: Path) -> Path:
    """CSV com 2 cadastros validos."""
    path = tmp_path / "validos.csv"
    path.write_text(
        "nome,email,cpf,telefone\n"
        f"Ana Silva,ana@x.com,{CPF_ANA},(11) 98765-4321\n"
        f"Bruno Costa,bruno@x.com,{CPF_BRUNO},\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def csv_misto(tmp_path: Path) -> Path:
    """CSV com mix: 2 validos, 1 CPF invalido, 1 sem nome."""
    path = tmp_path / "misto.csv"
    path.write_text(
        "nome,email,cpf,telefone\n"
        f"Ana Silva,ana@x.com,{CPF_ANA},(11) 98765-4321\n"
        f"Bruno Costa,bruno@x.com,{CPF_BRUNO},\n"
        f"Carlos Inv,carlos@x.com,{CPF_INVALIDO},\n"
        f",vazio@x.com,{CPF_ANA},\n",  # nome vazio
        encoding="utf-8",
    )
    return path


@pytest.fixture
def csv_sem_colunas(tmp_path: Path) -> Path:
    """CSV sem as colunas obrigatorias."""
    path = tmp_path / "ruim.csv"
    path.write_text(
        "coluna_a,coluna_b\nvalor1,valor2\n",
        encoding="utf-8",
    )
    return path


# ============================================================
# Fixtures de mock (httpx e BrowserSession)
# ============================================================


@pytest.fixture
def _health_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mocka httpx.get para retornar 200 (servidor online)."""

    def fake_get(url: str, timeout: float | None = None) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        return resp

    monkeypatch.setattr(rpa_module.httpx, "get", fake_get)  # type: ignore[attr-defined]


@pytest.fixture
def _health_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mocka httpx.get para simular servidor offline (ConnectError)."""

    def fake_get(url: str, timeout: float | None = None) -> MagicMock:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(rpa_module.httpx, "get", fake_get)  # type: ignore[attr-defined]


@pytest.fixture
def mock_browser(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """
    Mocka BrowserSession como context manager.

    Por default configura cenario de SUCESSO:
    - wait_for nao levanta
    - text("#record-id") retorna "1"

    Testes podem reconfigurar o mock retornado para outros cenarios.
    """
    mock_session_class = MagicMock(name="BrowserSession")
    mock_browser_obj = MagicMock(name="browser")

    # Context manager
    mock_session_class.return_value.__enter__.return_value = mock_browser_obj
    mock_session_class.return_value.__exit__.return_value = False

    # Cenario sucesso default: text retorna record_id
    mock_browser_obj.text.return_value = "1"

    monkeypatch.setattr(rpa_module, "BrowserSession", mock_session_class)
    return mock_browser_obj


# ============================================================
# Testes de __init__
# ============================================================


class TestInit:
    """Validacoes no construtor."""

    def test_planilha_inexistente_levanta(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="nao encontrada"):
            RPACadastroTask(
                planilha_path=tmp_path / "nao_existe.csv",
                base_url=BASE_URL,
            )

    def test_base_url_vazio_levanta(self, csv_validos: Path) -> None:
        with pytest.raises(ValidationError, match="base_url"):
            RPACadastroTask(planilha_path=csv_validos, base_url="")

    def test_base_url_so_espacos_levanta(self, csv_validos: Path) -> None:
        with pytest.raises(ValidationError, match="base_url"):
            RPACadastroTask(planilha_path=csv_validos, base_url="   ")

    def test_base_url_rstrip_barra(self, csv_validos: Path) -> None:
        """base_url tem barra final removida."""
        task = RPACadastroTask(
            planilha_path=csv_validos,
            base_url="http://localhost:5555/",
        )
        assert task.base_url == "http://localhost:5555"

    def test_defaults(self, csv_validos: Path) -> None:
        task = RPACadastroTask(planilha_path=csv_validos, base_url=BASE_URL)
        assert task.headless is True
        assert task.screenshot_on_error is True
        assert task.dry_run is False


# ============================================================
# Testes de execute - servidor offline
# ============================================================


@pytest.mark.usefixtures("_health_offline")
class TestExecuteServerOffline:
    """Quando o health check falha."""

    def test_servidor_offline_retorna_skipped(self, csv_validos: Path) -> None:
        task = RPACadastroTask(planilha_path=csv_validos, base_url=BASE_URL)
        result = task.run()
        assert result.status == TaskStatus.SKIPPED

    def test_skipped_inclui_base_url_no_data(self, csv_validos: Path) -> None:
        task = RPACadastroTask(planilha_path=csv_validos, base_url=BASE_URL)
        result = task.run()
        assert result.data["base_url"] == BASE_URL


# ============================================================
# Testes de execute - erros de planilha/schema
# ============================================================


@pytest.mark.usefixtures("_health_ok")
class TestExecuteErrors:
    """Erros de leitura e schema."""

    def test_formato_invalido_retorna_failure(self, tmp_path: Path) -> None:
        """Arquivo .txt nao eh CSV nem Excel."""
        txt = tmp_path / "dados.txt"
        txt.write_text("nao eh planilha", encoding="utf-8")
        task = RPACadastroTask(planilha_path=txt, base_url=BASE_URL)
        result = task.run()
        assert result.status == TaskStatus.FAILURE

    def test_schema_invalido_retorna_failure(
        self,
        csv_sem_colunas: Path,
    ) -> None:
        """CSV sem colunas obrigatorias."""
        task = RPACadastroTask(planilha_path=csv_sem_colunas, base_url=BASE_URL)
        result = task.run()
        assert result.status == TaskStatus.FAILURE

    def test_schema_invalido_menciona_colunas(
        self,
        csv_sem_colunas: Path,
    ) -> None:
        task = RPACadastroTask(planilha_path=csv_sem_colunas, base_url=BASE_URL)
        result = task.run()
        assert result.error_message is not None
        # Menciona alguma coluna obrigatoria que faltou
        assert "nome" in result.error_message.lower()


# ============================================================
# Testes de dry-run (pula health check e browser)
# ============================================================


class TestDryRun:
    """
    Dry-run NAO abre browser e (apos correcao do usuario) PULA o
    health check.
    """

    def test_dry_run_nao_chama_httpx(
        self,
        csv_validos: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Dry-run nao deve nem tentar health check."""
        chamado = {"get": False}

        def fake_get(url: str, timeout: float | None = None) -> MagicMock:
            chamado["get"] = True  # pragma: no cover
            resp = MagicMock()
            resp.status_code = 200
            return resp

        monkeypatch.setattr(rpa_module.httpx, "get", fake_get)  # type: ignore[attr-defined]

        task = RPACadastroTask(
            planilha_path=csv_validos,
            base_url=BASE_URL,
            dry_run=True,
        )
        task.run()
        assert chamado["get"] is False

    def test_dry_run_nao_abre_browser(
        self,
        csv_validos: Path,
        mock_browser: MagicMock,
    ) -> None:
        """Dry-run nao instancia BrowserSession."""
        task = RPACadastroTask(
            planilha_path=csv_validos,
            base_url=BASE_URL,
            dry_run=True,
        )
        task.run()
        # O context manager nao deve ter sido usado
        rpa_module.BrowserSession.return_value.__enter__.assert_not_called()  # type: ignore[attr-defined]

    def test_dry_run_validos_would_create(self, csv_validos: Path) -> None:
        task = RPACadastroTask(
            planilha_path=csv_validos,
            base_url=BASE_URL,
            dry_run=True,
        )
        result = task.run()
        assert result.data["success_count"] == 2
        assert result.data["skipped_count"] == 0
        assert result.data["error_count"] == 0

    def test_dry_run_misto_conta_certo(self, csv_misto: Path) -> None:
        """2 validos (would_create), 2 invalidos (would_skip)."""
        task = RPACadastroTask(
            planilha_path=csv_misto,
            base_url=BASE_URL,
            dry_run=True,
        )
        result = task.run()
        assert result.data["total"] == 4
        assert result.data["success_count"] == 2  # would_create
        assert result.data["skipped_count"] == 2  # CPF invalido + nome vazio
        assert result.data["error_count"] == 0

    def test_dry_run_status_success(self, csv_misto: Path) -> None:
        """Dry-run sem erros tecnicos = SUCCESS."""
        task = RPACadastroTask(
            planilha_path=csv_misto,
            base_url=BASE_URL,
            dry_run=True,
        )
        result = task.run()
        assert result.data["skipped_count"] == 2
        assert result.data["error_count"] == 0
        assert result.status == TaskStatus.SUCCESS


# ============================================================
# Testes de execucao real (browser mockado)
# ============================================================


@pytest.mark.usefixtures("_health_ok")
class TestExecuteReal:
    """Execucao real com BrowserSession mockado."""

    def test_validos_todos_sucesso(
        self,
        csv_validos: Path,
        mock_browser: MagicMock,
    ) -> None:
        task = RPACadastroTask(planilha_path=csv_validos, base_url=BASE_URL)
        result = task.run()
        assert result.status == TaskStatus.SUCCESS
        assert result.data["success_count"] == 2
        assert result.data["error_count"] == 0

    def test_cpf_invalido_eh_skipped_sem_browser(
        self,
        tmp_path: Path,
        mock_browser: MagicMock,
    ) -> None:
        """CPF invalido pula a linha ANTES de usar o browser."""
        csv = tmp_path / "um_invalido.csv"
        csv.write_text(
            f"nome,email,cpf,telefone\nCarlos,c@x.com,{CPF_INVALIDO},\n",
            encoding="utf-8",
        )
        task = RPACadastroTask(planilha_path=csv, base_url=BASE_URL)
        result = task.run()
        assert result.data["skipped_count"] == 1
        # Browser nunca navegou (CPF invalido pulado antes)
        mock_browser.go_to.assert_not_called()

    def test_cpf_duplicado_eh_skipped(
        self,
        csv_validos: Path,
        mock_browser: MagicMock,
    ) -> None:
        """Quando servidor retorna 'ja cadastrado', linha eh skipped."""
        # Reconfigura mock: wait_for levanta (sem #record-id), .errors visivel
        mock_browser.wait_for.side_effect = Exception("timeout")
        mock_browser.is_visible.return_value = True
        mock_browser.text.return_value = "CPF ja cadastrado"

        task = RPACadastroTask(planilha_path=csv_validos, base_url=BASE_URL)
        result = task.run()
        # Ambas as linhas viram skipped (duplicata)
        assert result.data["skipped_count"] == 2
        assert result.data["error_count"] == 0
        assert result.status == TaskStatus.SUCCESS

    def test_erro_tecnico_vira_error(
        self,
        csv_validos: Path,
        mock_browser: MagicMock,
    ) -> None:
        """Excecao inesperada (ex: go_to falha) marca linha como error."""
        mock_browser.go_to.side_effect = RuntimeError("browser crashed")

        task = RPACadastroTask(
            planilha_path=csv_validos,
            base_url=BASE_URL,
            screenshot_on_error=False,  # evita tentar screenshot
        )
        result = task.run()
        assert result.data["error_count"] == 2
        # Status: tudo erro = FAILURE
        assert result.status == TaskStatus.FAILURE

    def test_mix_sucesso_erro_vira_partial(
        self,
        tmp_path: Path,
        mock_browser: MagicMock,
    ) -> None:
        """1 sucesso + 1 erro = PARTIAL."""
        csv = tmp_path / "dois.csv"
        csv.write_text(
            f"nome,email,cpf,telefone\nAna,ana@x.com,{CPF_ANA},\nBruno,bruno@x.com,{CPF_BRUNO},\n",
            encoding="utf-8",
        )

        # go_to falha apenas na SEGUNDA chamada
        call_count = {"n": 0}

        def go_to_side_effect(url: str) -> None:
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("crash na segunda")

        mock_browser.go_to.side_effect = go_to_side_effect

        task = RPACadastroTask(
            planilha_path=csv,
            base_url=BASE_URL,
            screenshot_on_error=False,
        )
        result = task.run()
        assert result.data["success_count"] == 1
        assert result.data["error_count"] == 1
        assert result.status == TaskStatus.PARTIAL


# ============================================================
# Testes de audit (a task grava no audit via BaseTask)
# ============================================================


@pytest.mark.usefixtures("_health_ok")
class TestAudit:
    """Confirma que execucao eh registrada no audit (via BaseTask)."""

    def test_execucao_grava_no_audit(
        self,
        csv_validos: Path,
        mock_browser: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A task chama audit.record (via _record_audit do BaseTask)."""
        from autotarefas.core import base as base_module

        gravado: list[dict[str, Any]] = []

        def fake_record(**kwargs: Any) -> None:
            gravado.append(kwargs)

        monkeypatch.setattr(base_module.audit, "record", fake_record)  # type: ignore[attr-defined]

        task = RPACadastroTask(planilha_path=csv_validos, base_url=BASE_URL)
        task.run()

        assert len(gravado) == 1
        assert gravado[0]["task_name"] == "rpa_cadastro"


# ============================================================
# Testes de callback on_progress
# ============================================================


@pytest.mark.usefixtures("_health_ok")
class TestCallback:
    """Callback on_progress no modo real."""

    def test_callback_chamado_por_linha(
        self,
        csv_validos: Path,
        mock_browser: MagicMock,
    ) -> None:
        """on_progress eh chamado uma vez por linha processada."""
        chamadas: list[dict[str, Any]] = []

        task = RPACadastroTask(
            planilha_path=csv_validos,
            base_url=BASE_URL,
            on_progress=lambda op: chamadas.append(op),
        )
        task.run()

        # 2 linhas no CSV -> 2 chamadas
        assert len(chamadas) == 2
        # Cada chamada recebe um dict com 'status'
        assert all("status" in op for op in chamadas)

    def test_callback_excecao_nao_quebra_task(
        self,
        csv_validos: Path,
        mock_browser: MagicMock,
    ) -> None:
        """Se o callback levantar, a task continua normalmente."""

        def callback_ruim(op: dict[str, Any]) -> None:
            raise RuntimeError("callback explodiu")

        task = RPACadastroTask(
            planilha_path=csv_validos,
            base_url=BASE_URL,
            on_progress=callback_ruim,
        )
        # Nao deve propagar a excecao do callback
        result = task.run()
        assert result.status == TaskStatus.SUCCESS


# ============================================================
# Teste de leitura XLSX
# ============================================================


@pytest.mark.usefixtures("_health_ok")
class TestReadXlsx:
    """Leitura de planilha Excel."""

    def test_le_xlsx(self, tmp_path: Path, mock_browser: MagicMock) -> None:
        """Task le arquivo .xlsx corretamente."""
        xlsx = tmp_path / "clientes.xlsx"
        df = pd.DataFrame(
            {
                "nome": ["Ana Silva", "Bruno Costa"],
                "email": ["ana@x.com", "bruno@x.com"],
                "cpf": [CPF_ANA, CPF_BRUNO],
                "telefone": ["(11) 98765-4321", ""],
            }
        )
        df.to_excel(xlsx, index=False)

        task = RPACadastroTask(planilha_path=xlsx, base_url=BASE_URL)
        result = task.run()
        assert result.data["total"] == 2
        assert result.data["success_count"] == 2
