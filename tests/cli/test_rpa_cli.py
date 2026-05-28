"""
Testes do comando CLI `autotarefas rpa cadastro`.

ESTRATEGIA:
- Usa CliRunner do Click, invocando via o grupo `cli` principal
  (necessario pra ter ctx.obj corretamente inicializado).
- Mocka RPACadastroTask inteira: testa a LOGICA do CLI (validacao de
  URL, exit codes, formatacao) sem depender da task real.
- Planilhas reais em tmp_path (Click valida exists=True).

Cobertura:
- --help (grupo e comando)
- Validacao de URL: sem schema, nao-local sem --allow-remote
- Planilha inexistente (Click rejeita)
- Exit codes: success=0, failure=1, skipped=0, partial=0
- Output: header e sumario
- --allow-remote
- --dry-run global propaga pra task
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from click.testing import CliRunner

from autotarefas.cli.main import cli
from autotarefas.core.base import TaskResult, TaskStatus

cadastro_module = importlib.import_module("autotarefas.cli.commands.rpa.cadastro")

BASE_URL = "http://localhost:5555"


# ============================================================
# Helpers
# ============================================================


def make_result(
    status: TaskStatus,
    *,
    data: dict[str, Any] | None = None,
    error_message: str | None = None,
    duration_ms: int = 1000,
) -> TaskResult:
    """Cria um TaskResult fake para configurar o retorno da task mockada."""
    now = datetime.now(UTC)
    payload = data or {
        "total": 2,
        "success_count": 2,
        "skipped_count": 0,
        "error_count": 0,
        "base_url": BASE_URL,
        "planilha_path": "fake.csv",
        "operations": [],
    }
    return TaskResult(
        task_name="rpa_cadastro",
        status=status,
        started_at=now,
        finished_at=now,
        duration_ms=duration_ms,
        rows_affected=payload.get("success_count", 0),
        rows_failed=payload.get("error_count", 0),
        data=payload,
        error_message=error_message,
    )


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def runner() -> CliRunner:
    """CliRunner do Click."""
    return CliRunner()


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    """CSV valido minimo em tmp_path."""
    path = tmp_path / "clientes.csv"
    path.write_text(
        "nome,email,cpf,telefone\nAna Silva,ana@x.com,529.982.247-25,(11) 98765-4321\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def mock_task(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """
    Mocka RPACadastroTask no modulo do comando.

    Retorna um 'holder' dict para:
    - configurar o resultado: holder["result"] = make_result(...)
    - inspecionar os kwargs do construtor: holder["init_kwargs"]

    Por default, retorna SUCCESS.
    """
    holder: dict[str, Any] = {
        "result": make_result(TaskStatus.SUCCESS),
        "init_kwargs": None,
    }

    class FakeTask:
        def __init__(self, **kwargs: Any) -> None:
            holder["init_kwargs"] = kwargs
            # Permite o CLI fazer task.on_progress = ...
            self.on_progress = kwargs.get("on_progress")

        def run(self) -> TaskResult:
            return cast(TaskResult, holder["result"])

    monkeypatch.setattr(cadastro_module, "RPACadastroTask", FakeTask)
    return holder


# ============================================================
# Testes de --help
# ============================================================


class TestHelp:
    """Saida de --help."""

    def test_rpa_help_lista_cadastro(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["rpa", "--help"])
        assert result.exit_code == 0
        assert "cadastro" in result.output

    def test_cadastro_help_mostra_opcoes(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["rpa", "cadastro", "--help"])
        assert result.exit_code == 0
        assert "--planilha" in result.output
        assert "--site" in result.output
        assert "--allow-remote" in result.output
        assert "--show-browser" in result.output


# ============================================================
# Testes de validacao de URL
# ============================================================


class TestUrlValidation:
    """Regras de seguranca de URL."""

    def test_url_sem_schema_exit_2(
        self,
        runner: CliRunner,
        csv_path: Path,
    ) -> None:
        """URL sem http:// ou https:// eh rejeitada."""
        result = runner.invoke(
            cli,
            ["rpa", "cadastro", "-p", str(csv_path), "-s", "localhost:5555"],
        )
        assert result.exit_code == 2

    def test_url_ftp_exit_2(
        self,
        runner: CliRunner,
        csv_path: Path,
    ) -> None:
        """Schema ftp:// nao eh aceito."""
        result = runner.invoke(
            cli,
            ["rpa", "cadastro", "-p", str(csv_path), "-s", "ftp://localhost"],
        )
        assert result.exit_code == 2

    def test_url_nao_local_sem_allow_remote_exit_2(
        self,
        runner: CliRunner,
        csv_path: Path,
    ) -> None:
        """URL nao-local sem --allow-remote eh bloqueada."""
        result = runner.invoke(
            cli,
            [
                "rpa",
                "cadastro",
                "-p",
                str(csv_path),
                "-s",
                "https://producao.empresa.com",
            ],
        )
        assert result.exit_code == 2
        assert "allow-remote" in result.output.lower()

    def test_planilha_inexistente_exit_2(self, runner: CliRunner) -> None:
        """Click rejeita planilha que nao existe (exists=True)."""
        result = runner.invoke(
            cli,
            [
                "rpa",
                "cadastro",
                "-p",
                "nao_existe_xyz.csv",
                "-s",
                BASE_URL,
            ],
        )
        assert result.exit_code == 2


# ============================================================
# Testes de exit codes
# ============================================================


class TestExitCodes:
    """Exit codes por TaskStatus."""

    def test_sucesso_exit_0(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
    ) -> None:
        mock_task["result"] = make_result(TaskStatus.SUCCESS)
        result = runner.invoke(
            cli,
            ["rpa", "cadastro", "-p", str(csv_path), "-s", BASE_URL],
        )
        assert result.exit_code == 0

    def test_failure_exit_1(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.FAILURE,
            error_message="algo deu errado",
        )
        result = runner.invoke(
            cli,
            ["rpa", "cadastro", "-p", str(csv_path), "-s", BASE_URL],
        )
        assert result.exit_code == 1

    def test_skipped_exit_0(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
    ) -> None:
        """Servidor offline (SKIPPED) nao eh erro -> exit 0."""
        mock_task["result"] = make_result(
            TaskStatus.SKIPPED,
            data={"base_url": BASE_URL},
            error_message="servidor offline",
        )
        result = runner.invoke(
            cli,
            ["rpa", "cadastro", "-p", str(csv_path), "-s", BASE_URL],
        )
        assert result.exit_code == 0

    def test_partial_exit_0(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
    ) -> None:
        """PARTIAL termina com exit 0 mas avisa."""
        mock_task["result"] = make_result(
            TaskStatus.PARTIAL,
            data={
                "total": 2,
                "success_count": 1,
                "skipped_count": 0,
                "error_count": 1,
                "base_url": BASE_URL,
            },
        )
        result = runner.invoke(
            cli,
            ["rpa", "cadastro", "-p", str(csv_path), "-s", BASE_URL],
        )
        assert result.exit_code == 0


# ============================================================
# Testes de output
# ============================================================


class TestOutput:
    """Conteudo do output."""

    def test_header_mostra_site(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
    ) -> None:
        result = runner.invoke(
            cli,
            ["rpa", "cadastro", "-p", str(csv_path), "-s", BASE_URL],
        )
        assert BASE_URL in result.output

    def test_sumario_mostra_contagens(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={
                "total": 5,
                "success_count": 3,
                "skipped_count": 2,
                "error_count": 0,
                "base_url": BASE_URL,
            },
        )
        result = runner.invoke(
            cli,
            ["rpa", "cadastro", "-p", str(csv_path), "-s", BASE_URL],
        )
        assert "Total" in result.output
        assert "Sucesso" in result.output
        assert "Skipped" in result.output


# ============================================================
# Testes de --allow-remote
# ============================================================


class TestAllowRemote:
    """Flag --allow-remote."""

    def test_allow_remote_aceita_url_remota(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
    ) -> None:
        """Com --allow-remote, URL remota passa da validacao."""
        mock_task["result"] = make_result(TaskStatus.SUCCESS)
        result = runner.invoke(
            cli,
            [
                "rpa",
                "cadastro",
                "-p",
                str(csv_path),
                "-s",
                "https://homolog.empresa.com",
                "--allow-remote",
            ],
        )
        # Passou da validacao e rodou (exit 0)
        assert result.exit_code == 0
        # A task foi criada com a URL remota
        assert mock_task["init_kwargs"]["base_url"] == "https://homolog.empresa.com"


# ============================================================
# Testes de flags propagadas pra task
# ============================================================


class TestFlagsPropagation:
    """Flags do CLI viram parametros da task."""

    def test_show_browser_vira_headless_false(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
    ) -> None:
        """--show-browser faz headless=False na task."""
        runner.invoke(
            cli,
            [
                "rpa",
                "cadastro",
                "-p",
                str(csv_path),
                "-s",
                BASE_URL,
                "--show-browser",
            ],
        )
        assert mock_task["init_kwargs"]["headless"] is False

    def test_sem_show_browser_headless_true(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
    ) -> None:
        """Sem --show-browser, headless=True (default)."""
        runner.invoke(
            cli,
            ["rpa", "cadastro", "-p", str(csv_path), "-s", BASE_URL],
        )
        assert mock_task["init_kwargs"]["headless"] is True

    def test_no_screenshot_vira_screenshot_on_error_false(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
    ) -> None:
        """--no-screenshot faz screenshot_on_error=False."""
        runner.invoke(
            cli,
            [
                "rpa",
                "cadastro",
                "-p",
                str(csv_path),
                "-s",
                BASE_URL,
                "--no-screenshot",
            ],
        )
        assert mock_task["init_kwargs"]["screenshot_on_error"] is False

    def test_dry_run_global_propaga(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
    ) -> None:
        """--dry-run global faz dry_run=True na task."""
        runner.invoke(
            cli,
            ["--dry-run", "rpa", "cadastro", "-p", str(csv_path), "-s", BASE_URL],
        )
        assert mock_task["init_kwargs"]["dry_run"] is True
