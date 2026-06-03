"""
Testes do comando CLI `autotarefas send email`.

ESTRATEGIA:
- CliRunner via grupo `cli` principal.
- Mocka SendEmailTask (holder) para inspecionar os kwargs e o resultado.
- Senha: mock de env var (monkeypatch.setenv) e de getpass.getpass.

Cobertura:
- --help
- Corpo (--body / --body-file / ausente -> exit 2)
- Exit codes (success/partial/failure/dry-run/ValidationError)
- SENHA: via env var, via prompt, ausente quando sem --user
- Propagacao de flags (smtp, html, no-tls, email-column, delay, report)
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

email_module = importlib.import_module("autotarefas.cli.commands.send.email")

ENV_SENHA = "AUTOTAREFAS_SMTP_PASSWORD"


# ============================================================
# Helpers
# ============================================================


def make_result(
    status: TaskStatus,
    *,
    data: dict[str, Any] | None = None,
    rows_affected: int = 0,
    rows_failed: int = 0,
) -> TaskResult:
    now = datetime.now(UTC)
    return TaskResult(
        task_name="send_email",
        status=status,
        started_at=now,
        finished_at=now,
        duration_ms=100,
        rows_affected=rows_affected,
        rows_failed=rows_failed,
        data=data or {},
        error_message=None,
    )


def base_args(csv: Path) -> list[str]:
    """Args minimos validos (corpo inline, sem login, sem TLS)."""
    return [
        "send",
        "email",
        "-p",
        str(csv),
        "--smtp-host",
        "smtp.x.com",
        "--from",
        "robo@x.com",
        "--subject",
        "Ola {nome}",
        "--body",
        "Oi {nome}",
        "--no-tls",
    ]


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    path = tmp_path / "destinatarios.csv"
    path.write_text(
        "nome,email\nAna,ana@destino.local\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def mock_task(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    holder: dict[str, Any] = {
        "result": make_result(
            TaskStatus.SUCCESS,
            data={"total": 1, "enviados": 1, "falhas": 0, "report_path": None},
            rows_affected=1,
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

    monkeypatch.setattr(email_module, "SendEmailTask", FakeTask)
    return holder


@pytest.fixture(autouse=True)
def _sem_env_senha(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garante que a env var de senha nao vaze entre testes."""
    monkeypatch.delenv(ENV_SENHA, raising=False)


# ============================================================
# --help
# ============================================================


class TestHelp:
    def test_send_help_lista_email(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["send", "--help"])
        assert result.exit_code == 0
        assert "email" in result.output

    def test_email_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["send", "email", "--help"])
        assert result.exit_code == 0
        assert "--smtp-host" in result.output
        assert "--subject" in result.output


# ============================================================
# Corpo
# ============================================================


class TestCorpo:
    def test_sem_corpo_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            [
                "send",
                "email",
                "-p",
                str(csv_path),
                "--smtp-host",
                "x",
                "--from",
                "a@x",
                "--subject",
                "S",
                "--no-tls",
            ],
        )
        assert result.exit_code == 2

    def test_body_inline(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(cli, base_args(csv_path))
        assert mock_task["init_kwargs"]["corpo"] == "Oi {nome}"

    def test_body_file(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
        tmp_path: Path,
    ) -> None:
        bf = tmp_path / "corpo.txt"
        bf.write_text("Corpo de arquivo {nome}", encoding="utf-8")
        runner.invoke(
            cli,
            [
                "send",
                "email",
                "-p",
                str(csv_path),
                "--smtp-host",
                "x",
                "--from",
                "a@x",
                "--subject",
                "S",
                "--body-file",
                str(bf),
                "--no-tls",
            ],
        )
        assert mock_task["init_kwargs"]["corpo"] == "Corpo de arquivo {nome}"


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
        result = runner.invoke(cli, base_args(csv_path))
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
        result = runner.invoke(cli, base_args(csv_path))
        assert result.exit_code == 0

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
        result = runner.invoke(cli, base_args(csv_path))
        assert result.exit_code == 1

    def test_dry_run_exit_0(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"dry_run": True, "would_send": 1, "preview": []},
        )
        result = runner.invoke(cli, ["--dry-run", *base_args(csv_path)])
        assert result.exit_code == 0

    def test_validation_error_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["raise_on_init"] = ValidationError("config invalida")
        result = runner.invoke(cli, base_args(csv_path))
        assert result.exit_code == 2


# ============================================================
# Senha (o destaque)
# ============================================================


class TestSenha:
    def test_senha_via_env_var(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(ENV_SENHA, "segredo-env")
        runner.invoke(cli, [*base_args(csv_path), "--user", "u@x.com"])
        smtp = mock_task["init_kwargs"]["smtp"]
        assert smtp.usuario == "u@x.com"
        assert smtp.senha == "segredo-env"

    def test_senha_via_prompt(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # sem env var -> cai no getpass (mockado)
        monkeypatch.setattr("getpass.getpass", lambda _prompt="": "segredo-prompt")
        runner.invoke(cli, [*base_args(csv_path), "--user", "u@x.com"])
        assert mock_task["init_kwargs"]["smtp"].senha == "segredo-prompt"

    def test_sem_user_sem_senha_sem_prompt(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        chamou = {"v": False}

        def fake_getpass(_prompt: str = "") -> str:
            chamou["v"] = True
            return "x"

        monkeypatch.setattr("getpass.getpass", fake_getpass)
        runner.invoke(cli, base_args(csv_path))  # sem --user
        assert mock_task["init_kwargs"]["smtp"].senha is None
        assert chamou["v"] is False  # prompt nao foi chamado


# ============================================================
# Flags
# ============================================================


class TestFlags:
    def test_smtp_host_port(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(
            cli,
            [
                "send",
                "email",
                "-p",
                str(csv_path),
                "--smtp-host",
                "smtp.example.com",
                "--smtp-port",
                "2525",
                "--from",
                "a@x",
                "--subject",
                "S",
                "--body",
                "B",
                "--no-tls",
            ],
        )
        smtp = mock_task["init_kwargs"]["smtp"]
        assert smtp.host == "smtp.example.com"
        assert smtp.port == 2525

    def test_no_tls_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(cli, base_args(csv_path))  # base usa --no-tls
        assert mock_task["init_kwargs"]["smtp"].usar_tls is False

    def test_html_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(cli, [*base_args(csv_path), "--html"])
        assert mock_task["init_kwargs"]["is_html"] is True

    def test_email_column_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(cli, [*base_args(csv_path), "--email-column", "contato"])
        assert mock_task["init_kwargs"]["coluna_email"] == "contato"

    def test_report_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
        tmp_path: Path,
    ) -> None:
        rep = tmp_path / "rel.csv"
        runner.invoke(cli, [*base_args(csv_path), "-r", str(rep)])
        assert mock_task["init_kwargs"]["report_path"] == rep

    def test_dry_run_global_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"dry_run": True, "would_send": 1, "preview": []},
        )
        runner.invoke(cli, ["--dry-run", *base_args(csv_path)])
        assert mock_task["init_kwargs"]["dry_run"] is True
