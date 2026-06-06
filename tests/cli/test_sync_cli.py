"""
Testes do comando CLI `autotarefas sync api`.

ESTRATEGIA:
- CliRunner via grupo `cli` principal.
- Mocka SyncApiTask (holder) para inspecionar kwargs e resultado.

Cobertura:
- --help
- Validacao de URLs (source/dest) -> exit 2
- Exit codes (success/partial/failure/dry-run/ValidationError)
- Falha na extracao (stage extract)
- Propagacao de flags
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import pytest
from click.testing import CliRunner

from autotarefas.cli.main import cli
from autotarefas.core.base import TaskResult, TaskStatus
from autotarefas.core.exceptions import ValidationError

if TYPE_CHECKING:
    from pathlib import Path

api_module = importlib.import_module("autotarefas.cli.commands.sync.api")

SOURCE = "http://localhost:5555/api/clientes"
DEST = "http://localhost:5555/api/clientes"


# ============================================================
# Helpers
# ============================================================


def make_result(
    status: TaskStatus,
    *,
    data: dict[str, Any] | None = None,
    rows_affected: int = 0,
    rows_failed: int = 0,
    error_message: str | None = None,
) -> TaskResult:
    now = datetime.now(UTC)
    return TaskResult(
        task_name="sync_api",
        status=status,
        started_at=now,
        finished_at=now,
        duration_ms=100,
        rows_affected=rows_affected,
        rows_failed=rows_failed,
        data=data or {},
        error_message=error_message,
    )


def base_args() -> list[str]:
    return ["sync", "api", "-s", SOURCE, "-d", DEST]


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_task(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    holder: dict[str, Any] = {
        "result": make_result(
            TaskStatus.SUCCESS,
            data={"extraidos": 3, "enviados": 3, "falhas": 0, "report_path": None},
            rows_affected=3,
        ),
        "init_kwargs": None,
        "raise_on_init": None,
    }

    class FakeTask:
        def __init__(self, **kwargs: Any) -> None:
            if holder["raise_on_init"] is not None:
                raise holder["raise_on_init"]
            holder["init_kwargs"] = kwargs
            self.on_progress = kwargs.get("on_progress")

        def run(self) -> TaskResult:
            return cast("TaskResult", holder["result"])

    monkeypatch.setattr(api_module, "SyncApiTask", FakeTask)
    return holder


# ============================================================
# --help
# ============================================================


class TestHelp:
    def test_sync_help_lista_api(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["sync", "--help"])
        assert result.exit_code == 0
        assert "api" in result.output

    def test_api_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["sync", "api", "--help"])
        assert result.exit_code == 0
        assert "--source-url" in result.output
        assert "--dest-url" in result.output


# ============================================================
# Validacao de URLs
# ============================================================


class TestValidation:
    def test_source_url_invalida(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        result = runner.invoke(
            cli,
            ["sync", "api", "-s", "ftp://x", "-d", DEST],
        )
        assert result.exit_code == 2

    def test_dest_url_invalida(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        result = runner.invoke(
            cli,
            ["sync", "api", "-s", SOURCE, "-d", "ftp://y"],
        )
        assert result.exit_code == 2


# ============================================================
# Exit codes
# ============================================================


class TestExitCodes:
    def test_sucesso_exit_0(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        result = runner.invoke(cli, base_args())
        assert result.exit_code == 0

    def test_partial_exit_0(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.PARTIAL,
            data={"extraidos": 3, "enviados": 2, "falhas": 1, "report_path": None},
            rows_affected=2,
            rows_failed=1,
        )
        result = runner.invoke(cli, base_args())
        assert result.exit_code == 0

    def test_failure_exit_1(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.FAILURE,
            data={"extraidos": 3, "enviados": 0, "falhas": 3, "report_path": None},
            rows_failed=3,
        )
        result = runner.invoke(cli, base_args())
        assert result.exit_code == 1

    def test_falha_extracao_exit_1(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.FAILURE,
            data={"stage": "extract"},
            error_message="Extracao da origem falhou: timeout",
        )
        result = runner.invoke(cli, base_args())
        assert result.exit_code == 1
        assert "Extracao" in result.output or "Extracao" in (result.stderr or "")

    def test_dry_run_exit_0(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"dry_run": True, "nota": "..."},
        )
        result = runner.invoke(cli, ["--dry-run", *base_args()])
        assert result.exit_code == 0

    def test_validation_error_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        mock_task["raise_on_init"] = ValidationError("config invalida")
        result = runner.invoke(cli, base_args())
        assert result.exit_code == 2


# ============================================================
# Flags
# ============================================================


class TestFlags:
    def test_urls_propagam(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        runner.invoke(cli, base_args())
        kw = mock_task["init_kwargs"]
        assert kw["source_url"] == SOURCE
        assert kw["dest_url"] == DEST

    def test_api_keys_propagam(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        runner.invoke(
            cli,
            [
                *base_args(),
                "--source-api-key",
                "ks",  # pragma: allowlist secret
                "--dest-api-key",
                "kd",  # pragma: allowlist secret
            ],
        )
        kw = mock_task["init_kwargs"]
        assert kw["source_api_key"] == "ks"  # pragma: allowlist secret
        assert kw["dest_api_key"] == "kd"  # pragma: allowlist secret

    def test_per_page_e_format(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        runner.invoke(cli, [*base_args(), "--per-page", "10", "--format", "xlsx"])
        kw = mock_task["init_kwargs"]
        assert kw["per_page"] == 10
        assert kw["intermediate_format"] == "xlsx"

    def test_report_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        rep = tmp_path / "rel.csv"
        runner.invoke(cli, [*base_args(), "-r", str(rep)])
        assert mock_task["init_kwargs"]["report_path"] == rep

    def test_dry_run_global_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"dry_run": True, "nota": "..."},
        )
        runner.invoke(cli, ["--dry-run", *base_args()])
        assert mock_task["init_kwargs"]["dry_run"] is True

    def test_format_invalido_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        # click.Choice rejeita valor fora de csv/xlsx
        result = runner.invoke(cli, [*base_args(), "--format", "json"])
        assert result.exit_code == 2
