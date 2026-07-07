"""
Testes do comando CLI `autotarefas send api`.

ESTRATEGIA:
- CliRunner via grupo `cli` principal (ctx.obj correto).
- Mocka SendApiTask inteira (holder): testa a logica do CLI
  (validacao de URL, exit codes, output, propagacao de flags).

Cobertura:
- --help
- Validacao de URL (exit 2) e planilha inexistente (exit 2)
- Exit codes (success=0, partial=0, failure=1, dry-run=0)
- ValidationError no init -> exit 2
- Output (header, "Enviados", dry-run)
- Propagacao de flags
- Aviso de seguranca (credencial sobre http externo)
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

api_module = importlib.import_module("autotarefas.cli.commands.send.api")

URL = "http://localhost:5555/api/clientes"


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
        task_name="send_api",
        status=status,
        started_at=now,
        finished_at=now,
        duration_ms=100,
        rows_affected=rows_affected,
        rows_failed=rows_failed,
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
def csv_path(tmp_path: Path) -> Path:
    """Planilha valida (Click exige exists=True)."""
    path = tmp_path / "clientes.csv"
    path.write_text(
        "nome,email,cpf,telefone\nAna,a@x.com,111.222.333-44,\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def mock_task(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mocka SendApiTask. holder configura resultado / inspeciona kwargs."""
    holder: dict[str, Any] = {
        "result": make_result(
            TaskStatus.SUCCESS,
            data={"total": 3, "enviados": 3, "falhas": 0, "report_path": None},
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
            self.processed_dataframe = holder.get("processed_dataframe")

        def run(self) -> TaskResult:
            return cast("TaskResult", holder["result"])

    monkeypatch.setattr(api_module, "SendApiTask", FakeTask)
    return holder


# ============================================================
# --help
# ============================================================


class TestHelp:
    def test_send_help_lista_api(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["send", "--help"])
        assert result.exit_code == 0
        assert "api" in result.output

    def test_api_help_mostra_opcoes(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["send", "api", "--help"])
        assert result.exit_code == 0
        assert "--planilha" in result.output
        assert "--url" in result.output
        assert "--report" in result.output


# ============================================================
# Validacao
# ============================================================


class TestValidation:
    def test_url_invalida_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            ["send", "api", "-p", str(csv_path), "-u", "ftp://x"],
        )
        assert result.exit_code == 2

    def test_planilha_inexistente_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        result = runner.invoke(
            cli,
            ["send", "api", "-p", "nao_existe.csv", "-u", URL],
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
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            ["send", "api", "-p", str(csv_path), "-u", URL],
        )
        assert result.exit_code == 0

    def test_partial_exit_0(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.PARTIAL,
            data={"total": 3, "enviados": 2, "falhas": 1, "report_path": None},
            rows_affected=2,
            rows_failed=1,
        )
        result = runner.invoke(
            cli,
            ["send", "api", "-p", str(csv_path), "-u", URL],
        )
        assert result.exit_code == 0  # parcial nao e falha do comando

    def test_failure_exit_1(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.FAILURE,
            data={"total": 3, "enviados": 0, "falhas": 3, "report_path": None},
            rows_failed=3,
        )
        result = runner.invoke(
            cli,
            ["send", "api", "-p", str(csv_path), "-u", URL],
        )
        assert result.exit_code == 1

    def test_dry_run_exit_0(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"dry_run": True, "would_send": 3},
        )
        result = runner.invoke(
            cli,
            ["--dry-run", "send", "api", "-p", str(csv_path), "-u", URL],
        )
        assert result.exit_code == 0

    def test_validation_error_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["raise_on_init"] = ValidationError("relatorio invalido")
        result = runner.invoke(
            cli,
            ["send", "api", "-p", str(csv_path), "-u", URL],
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
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            ["send", "api", "-p", str(csv_path), "-u", URL],
        )
        assert URL in result.output

    def test_mostra_enviados(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            ["send", "api", "-p", str(csv_path), "-u", URL],
        )
        assert "Enviados" in result.output

    def test_dry_run_mostra_enviaria(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"dry_run": True, "would_send": 3},
        )
        result = runner.invoke(
            cli,
            ["--dry-run", "send", "api", "-p", str(csv_path), "-u", URL],
        )
        assert "Enviaria" in result.output


# ============================================================
# Flags
# ============================================================


class TestFlags:
    def test_api_key_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(
            cli,
            [
                "send",
                "api",
                "-p",
                str(csv_path),
                "-u",
                URL,
                "--api-key",
                "k1",  # pragma: allowlist secret
            ],
        )
        assert mock_task["init_kwargs"]["api_key"] == "k1"  # pragma: allowlist secret

    def test_bearer_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(
            cli,
            [
                "send",
                "api",
                "-p",
                str(csv_path),
                "-u",
                URL,
                "--bearer",
                "t1",  # pragma: allowlist secret
            ],
        )
        assert mock_task["init_kwargs"]["bearer_token"] == "t1"  # pragma: allowlist secret

    def test_delay_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(
            cli,
            ["send", "api", "-p", str(csv_path), "-u", URL, "--delay", "0.3"],
        )
        assert mock_task["init_kwargs"]["delay_s"] == 0.3

    def test_report_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
        tmp_path: Path,
    ) -> None:
        rep = tmp_path / "rel.csv"
        runner.invoke(
            cli,
            ["send", "api", "-p", str(csv_path), "-u", URL, "-r", str(rep)],
        )
        assert mock_task["init_kwargs"]["report_path"] == rep

    def test_dry_run_global_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(
            cli,
            ["--dry-run", "send", "api", "-p", str(csv_path), "-u", URL],
        )
        assert mock_task["init_kwargs"]["dry_run"] is True


# ============================================================
# Seguranca
# ============================================================


class TestSecurity:
    def test_aviso_credencial_http_externo(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            [
                "send",
                "api",
                "-p",
                str(csv_path),
                "-u",
                "http://api.externa.com/clientes",
                "--api-key",
                "k1",  # pragma: allowlist secret
            ],
        )
        assert "Aviso" in result.output
        assert result.exit_code == 0  # nao bloqueia

    def test_sem_aviso_em_localhost(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            [
                "send",
                "api",
                "-p",
                str(csv_path),
                "-u",
                URL,
                "--api-key",
                "k1",  # pragma: allowlist secret
            ],
        )
        assert "Aviso" not in result.output


# ============================================================
# --out-dir (4 artefatos)
# ============================================================


def _data_com_items() -> dict[str, Any]:
    return {
        "total": 2,
        "enviados": 1,
        "falhas": 1,
        "reenviaveis": 0,
        "falhas_por_categoria": {"validacao": 1},
        "url": URL,
        "planilha": "leads.csv",
        "report_path": None,
        "items": [
            {
                "linha": 2,
                "status_http": 201,
                "categoria": "sucesso",
                "sucesso": True,
                "mensagem": "criado (id 7)",
                "id_externo": "7",
                "idempotency_key": "k1",
                "tentativas": 1,
                "pode_reenviar": False,
            },
            {
                "linha": 3,
                "status_http": 422,
                "categoria": "validacao",
                "sucesso": False,
                "mensagem": "HTTP 422: Validacao falhou",
                "id_externo": None,
                "idempotency_key": "k2",
                "tentativas": 1,
                "pode_reenviar": False,
            },
        ],
    }


class TestOutDir:
    def test_out_dir_gera_os_quatro_artefatos(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        import pandas as pd

        mock_task["processed_dataframe"] = pd.DataFrame(
            [
                {"nome": "Ana", "email": "a@x.com"},
                {"nome": "Bruno", "email": "b@x.com"},
            ]
        )
        mock_task["result"] = make_result(
            TaskStatus.PARTIAL, data=_data_com_items(), rows_affected=1, rows_failed=1
        )
        out = tmp_path / "saida"

        result = runner.invoke(
            cli,
            ["send", "api", "-p", str(csv_path), "-u", URL, "--out-dir", str(out)],
        )

        assert result.exit_code == 0, result.output
        assert (out / "registros_enviados.csv").exists()
        assert (out / "registros_falhos.csv").exists()
        assert (out / "importacao_resultado.xlsx").exists()
        assert (out / "importacao_report.json").exists()
        assert "Registros enviados:" in result.output

    def test_dry_run_nao_gera_artefatos(
        self,
        runner: CliRunner,
        csv_path: Path,
        mock_task: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        mock_task["result"] = make_result(TaskStatus.SUCCESS, data={"would_send": 2})
        out = tmp_path / "saida"

        result = runner.invoke(
            cli,
            ["--dry-run", "send", "api", "-p", str(csv_path), "-u", URL, "--out-dir", str(out)],
        )

        assert result.exit_code == 0, result.output
        assert "Geraria os 4 artefatos" in result.output
        assert not out.exists()
