"""
Testes do comando CLI `autotarefas extract api`.

ESTRATEGIA:
- CliRunner invocando via o grupo `cli` principal (ctx.obj correto).
- Mocka ExtractApiTask inteira (holder), testa a logica do CLI:
  validacao de URL, exit codes, formatacao, propagacao de flags.

Cobertura:
- --help (grupo e comando)
- Validacao de URL (exit 2)
- Exit codes (success=0, failure=1, dry-run=0, 0 registros=0)
- ValidationError no init -> exit 2
- Output (header, sucesso, dry-run)
- Propagacao de flags
- Aviso de seguranca (api-key sobre http externo)
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

# Modulo do comando (para monkeypatch da task)
api_module = importlib.import_module("autotarefas.cli.commands.extract.api")

URL = "http://localhost:5555/api/clientes"
_EXIT_USAGE_TEST = 2


# ============================================================
# Helpers
# ============================================================


def make_result(
    status: TaskStatus,
    *,
    data: dict[str, Any] | None = None,
    rows_affected: int = 0,
    error_message: str | None = None,
) -> TaskResult:
    """TaskResult fake para configurar o retorno da task mockada."""
    now = datetime.now(UTC)
    return TaskResult(
        task_name="extract_api",
        status=status,
        started_at=now,
        finished_at=now,
        duration_ms=100,
        rows_affected=rows_affected,
        data=data or {},
        error_message=error_message,
    )


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_task(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """
    Mocka ExtractApiTask no modulo do comando.

    holder permite:
    - configurar resultado: holder["result"] = make_result(...)
    - inspecionar kwargs: holder["init_kwargs"]
    - forcar erro no init: holder["raise_on_init"] = ValidationError(...)
    """
    holder: dict[str, Any] = {
        "result": make_result(
            TaskStatus.SUCCESS,
            data={"saved": True, "output_path": "saida.csv"},
            rows_affected=47,
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
            self.extracted_records = holder.get("extracted_records", [])

        def run(self) -> TaskResult:
            return cast("TaskResult", holder["result"])

    monkeypatch.setattr(api_module, "ExtractApiTask", FakeTask)
    return holder


# ============================================================
# --help
# ============================================================


class TestHelp:
    def test_extract_help_lista_api(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["extract", "--help"])
        assert result.exit_code == 0
        assert "api" in result.output

    def test_api_help_mostra_opcoes(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["extract", "api", "--help"])
        assert result.exit_code == 0
        assert "--url" in result.output
        assert "--output" in result.output
        assert "--per-page" in result.output
        assert "--delay" in result.output
        assert "--api-key" in result.output


# ============================================================
# Validacao de URL
# ============================================================


class TestUrlValidation:
    def test_url_sem_schema_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            ["extract", "api", "-u", "localhost:5555", "-o", str(tmp_path / "o.csv")],
        )
        assert result.exit_code == 2

    def test_url_ftp_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            ["extract", "api", "-u", "ftp://x", "-o", str(tmp_path / "o.csv")],
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
        tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            ["extract", "api", "-u", URL, "-o", str(tmp_path / "o.csv")],
        )
        assert result.exit_code == 0

    def test_failure_exit_1(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.FAILURE,
            error_message="erro de conexao",
        )
        result = runner.invoke(
            cli,
            ["extract", "api", "-u", URL, "-o", str(tmp_path / "o.csv")],
        )
        assert result.exit_code == 1

    def test_dry_run_exit_0(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"dry_run": True, "would_extract": 47, "total_pages": 5},
        )
        result = runner.invoke(
            cli,
            ["--dry-run", "extract", "api", "-u", URL, "-o", str(tmp_path / "o.csv")],
        )
        assert result.exit_code == 0

    def test_zero_registros_exit_0(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"saved": False},
            rows_affected=0,
        )
        result = runner.invoke(
            cli,
            ["extract", "api", "-u", URL, "-o", str(tmp_path / "o.csv")],
        )
        assert result.exit_code == 0

    def test_validation_error_no_init_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_task["raise_on_init"] = ValidationError("formato invalido")
        result = runner.invoke(
            cli,
            ["extract", "api", "-u", URL, "-o", str(tmp_path / "o.txt")],
        )
        assert result.exit_code == 2


# ============================================================
# Output
# ============================================================


class TestOutput:
    def test_header_mostra_url(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            ["extract", "api", "-u", URL, "-o", str(tmp_path / "o.csv")],
        )
        assert URL in result.output

    def test_sucesso_mostra_extraidos(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            ["extract", "api", "-u", URL, "-o", str(tmp_path / "o.csv")],
        )
        assert "Extraidos" in result.output

    def test_dry_run_mostra_extrairia(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"dry_run": True, "would_extract": 47, "total_pages": 5},
        )
        result = runner.invoke(
            cli,
            ["--dry-run", "extract", "api", "-u", URL, "-o", str(tmp_path / "o.csv")],
        )
        assert "Extrairia" in result.output


# ============================================================
# Propagacao de flags
# ============================================================


class TestFlags:
    def test_per_page_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        runner.invoke(
            cli,
            [
                "extract",
                "api",
                "-u",
                URL,
                "-o",
                str(tmp_path / "o.csv"),
                "--per-page",
                "20",
            ],
        )
        assert mock_task["init_kwargs"]["per_page"] == 20

    def test_delay_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        runner.invoke(
            cli,
            [
                "extract",
                "api",
                "-u",
                URL,
                "-o",
                str(tmp_path / "o.csv"),
                "--delay",
                "0.5",
            ],
        )
        assert mock_task["init_kwargs"]["delay_s"] == 0.5

    def test_max_pages_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        runner.invoke(
            cli,
            [
                "extract",
                "api",
                "-u",
                URL,
                "-o",
                str(tmp_path / "o.csv"),
                "--max-pages",
                "3",
            ],
        )
        assert mock_task["init_kwargs"]["max_pages"] == 3

    def test_api_key_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        runner.invoke(
            cli,
            [
                "extract",
                "api",
                "-u",
                URL,
                "-o",
                str(tmp_path / "o.csv"),
                "--api-key",
                "k123",  # pragma: allowlist secret
            ],
        )
        assert mock_task["init_kwargs"]["api_key"] == "k123"  # pragma: allowlist secret

    def test_dry_run_global_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        runner.invoke(
            cli,
            ["--dry-run", "extract", "api", "-u", URL, "-o", str(tmp_path / "o.csv")],
        )
        assert mock_task["init_kwargs"]["dry_run"] is True


# ============================================================
# Seguranca
# ============================================================


class TestSecurity:
    def test_aviso_api_key_http_externo(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        """api-key sobre http:// externo deve gerar aviso."""
        result = runner.invoke(
            cli,
            [
                "extract",
                "api",
                "-u",
                "http://api.externa.com/itens",
                "-o",
                str(tmp_path / "o.csv"),
                "--api-key",
                "k123",  # pragma: allowlist secret
            ],
        )
        assert "Aviso" in result.output
        # mas nao bloqueia: a task roda (exit 0)
        assert result.exit_code == 0

    def test_sem_aviso_em_localhost(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        """api-key em localhost nao gera aviso."""
        result = runner.invoke(
            cli,
            [
                "extract",
                "api",
                "-u",
                URL,
                "-o",
                str(tmp_path / "o.csv"),
                "--api-key",
                "k123",  # pragma: allowlist secret
            ],
        )
        assert "Aviso" not in result.output


# ============================================================
# --out-dir (3 artefatos)
# ============================================================


class TestOutDir:
    def test_out_dir_gera_os_tres_artefatos(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_task["extracted_records"] = [
            {"id": 1, "nome": "Ana", "email": "ana@x.com"},
            {"id": 2, "nome": "Bruno", "email": "bruno@x.com"},
        ]
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"saved": True, "total_pages": 1, "url": URL},
            rows_affected=2,
        )
        out = tmp_path / "saida"

        result = runner.invoke(cli, ["extract", "api", "-u", URL, "--out-dir", str(out)])

        assert result.exit_code == 0, result.output
        assert (out / "dados_extraidos.csv").exists()
        assert (out / "dados_extraidos.xlsx").exists()
        assert (out / "extracao_report.json").exists()
        assert "Dados (CSV):" in result.output

    def test_sem_destino_erro_de_uso(self, runner: CliRunner, mock_task: dict[str, Any]) -> None:
        # nem --output nem --out-dir -> exit 2
        result = runner.invoke(cli, ["extract", "api", "-u", URL])
        assert result.exit_code == _EXIT_USAGE_TEST
        assert "pelo menos um destino" in result.output

    def test_output_sozinho_continua_funcionando(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        # compatibilidade: -o sem --out-dir mantem o comportamento legado
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"saved": True, "output_path": str(tmp_path / "d.csv")},
            rows_affected=3,
        )
        result = runner.invoke(cli, ["extract", "api", "-u", URL, "-o", str(tmp_path / "d.csv")])
        assert result.exit_code == 0, result.output
        assert "Arquivo:" in result.output

    def test_dry_run_nao_gera_artefatos(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"dry_run": True, "would_extract": 47, "total_pages": 5},
        )
        out = tmp_path / "saida"
        result = runner.invoke(
            cli, ["--dry-run", "extract", "api", "-u", URL, "--out-dir", str(out)]
        )
        assert result.exit_code == 0, result.output
        assert "Geraria os artefatos" in result.output
        assert not out.exists()
