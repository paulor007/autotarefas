"""
Testes do comando CLI `autotarefas send telegram`.

ESTRATEGIA:
- CliRunner via grupo `cli` principal.
- Mocka SendTelegramTask (holder) para inspecionar os kwargs e o resultado
  (nao toca em rede; o envio real e testado na suite da task).
- Token: mock de env var (monkeypatch.setenv) e de getpass.getpass.

Cobertura:
- --help
- Texto (--text / --text-file / ausente -> exit 2)
- Destino (--chat-id / --chat-id-column / nenhum / ambos -> exit 2)
- Exit codes (success/partial/failure/dry-run/ValidationError)
- TOKEN: via env var, via prompt, e nunca aparece na saida
- Propagacao de flags (base-url, parse-mode, delay, timeout, max-retries, report, dry-run)
- dry-run exibe exemplo efemero; aviso de http sem TLS em host externo
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

tg_module = importlib.import_module("autotarefas.cli.commands.send.telegram")

ENV_TOKEN = "AUTOTAREFAS_TELEGRAM_TOKEN"
TOKEN_FAKE = "123456:FAKE-TOKEN"


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
        task_name="send_telegram",
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
    """Args minimos validos (texto inline, destino por coluna)."""
    return [
        "send",
        "telegram",
        "-p",
        str(csv),
        "--text",
        "Ola {nome}!",
        "--chat-id-column",
        "chat_id",
    ]


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    path = tmp_path / "contatos.csv"
    path.write_text("nome,chat_id\nAna,111\nBruno,222\n", encoding="utf-8")
    return path


@pytest.fixture
def mock_task(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    holder: dict[str, Any] = {
        "result": make_result(
            TaskStatus.SUCCESS,
            data={"total": 2, "enviados": 2, "falhas": 0, "report_path": None},
            rows_affected=2,
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

    monkeypatch.setattr(tg_module, "SendTelegramTask", FakeTask)
    return holder


@pytest.fixture(autouse=True)
def _token_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Token via env por padrao (evita bloquear no getpass nos testes)."""
    monkeypatch.setenv(ENV_TOKEN, TOKEN_FAKE)


# ============================================================
# --help
# ============================================================


class TestHelp:
    def test_send_help_lista_telegram(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["send", "--help"])
        assert result.exit_code == 0
        assert "telegram" in result.output

    def test_telegram_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["send", "telegram", "--help"])
        assert result.exit_code == 0
        assert "--text" in result.output
        assert "--chat-id" in result.output


# ============================================================
# Texto
# ============================================================


class TestTexto:
    def test_sem_texto_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            ["send", "telegram", "-p", str(csv_path), "--chat-id-column", "chat_id"],
        )
        assert result.exit_code == 2

    def test_text_inline(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(cli, base_args(csv_path))
        assert mock_task["init_kwargs"]["text_template"] == "Ola {nome}!"

    def test_text_file(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
        tmp_path: Path,
    ) -> None:
        tf = tmp_path / "msg.txt"
        tf.write_text("Mensagem de arquivo {nome}", encoding="utf-8")
        runner.invoke(
            cli,
            [
                "send",
                "telegram",
                "-p",
                str(csv_path),
                "--text-file",
                str(tf),
                "--chat-id-column",
                "chat_id",
            ],
        )
        assert mock_task["init_kwargs"]["text_template"] == "Mensagem de arquivo {nome}"


# ============================================================
# Destino
# ============================================================


class TestDestino:
    def test_sem_destino_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            ["send", "telegram", "-p", str(csv_path), "--text", "oi"],
        )
        assert result.exit_code == 2

    def test_ambos_destinos_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            [
                "send",
                "telegram",
                "-p",
                str(csv_path),
                "--text",
                "oi",
                "--chat-id",
                "1",
                "--chat-id-column",
                "chat_id",
            ],
        )
        assert result.exit_code == 2

    def test_chat_id_fixo_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(
            cli,
            [
                "send",
                "telegram",
                "-p",
                str(csv_path),
                "--text",
                "oi",
                "--chat-id",
                "999",
            ],
        )
        assert mock_task["init_kwargs"]["chat_id"] == "999"
        assert mock_task["init_kwargs"]["chat_id_column"] is None

    def test_chat_id_column_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(cli, base_args(csv_path))
        assert mock_task["init_kwargs"]["chat_id_column"] == "chat_id"


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
        assert runner.invoke(cli, base_args(csv_path)).exit_code == 0

    def test_partial_exit_0(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.PARTIAL,
            data={"total": 2, "enviados": 1, "falhas": 1, "report_path": None},
            rows_affected=1,
            rows_failed=1,
        )
        assert runner.invoke(cli, base_args(csv_path)).exit_code == 0

    def test_failure_exit_1(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.FAILURE,
            data={"total": 2, "enviados": 0, "falhas": 2, "report_path": None},
            rows_failed=2,
        )
        assert runner.invoke(cli, base_args(csv_path)).exit_code == 1

    def test_dry_run_exit_0(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"dry_run": True, "would_send": 2, "exemplo_texto": "Ola Ana!"},
        )
        assert runner.invoke(cli, ["--dry-run", *base_args(csv_path)]).exit_code == 0

    def test_validation_error_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["raise_on_init"] = ValidationError("config invalida")
        assert runner.invoke(cli, base_args(csv_path)).exit_code == 2

    def test_parse_mode_invalido_exit_2(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        # Choice do click rejeita antes de chegar a task
        result = runner.invoke(cli, [*base_args(csv_path), "--parse-mode", "Latex"])
        assert result.exit_code == 2


# ============================================================
# Token (o destaque de seguranca)
# ============================================================


class TestToken:
    def test_token_via_env(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(ENV_TOKEN, "888:DO-ENV")
        runner.invoke(cli, base_args(csv_path))
        assert mock_task["init_kwargs"]["token"] == "888:DO-ENV"

    def test_token_via_prompt(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv(ENV_TOKEN, raising=False)
        monkeypatch.setattr("getpass.getpass", lambda _p="": "777:DO-PROMPT")
        runner.invoke(cli, base_args(csv_path))
        assert mock_task["init_kwargs"]["token"] == "777:DO-PROMPT"

    def test_token_nunca_aparece_na_saida(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        segredo = "SECRETO-12345:AAH-token"
        monkeypatch.setenv(ENV_TOKEN, segredo)
        result = runner.invoke(cli, base_args(csv_path))
        assert segredo not in result.output


# ============================================================
# Flags
# ============================================================


class TestFlags:
    def test_base_url_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(cli, [*base_args(csv_path), "--base-url", "http://localhost:5555"])
        assert mock_task["init_kwargs"]["base_url"] == "http://localhost:5555"

    def test_parse_mode_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(cli, [*base_args(csv_path), "--parse-mode", "HTML"])
        assert mock_task["init_kwargs"]["parse_mode"] == "HTML"

    def test_delay_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(cli, [*base_args(csv_path), "--delay", "1.5"])
        assert mock_task["init_kwargs"]["delay_s"] == 1.5

    def test_timeout_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(cli, [*base_args(csv_path), "--timeout", "10"])
        assert mock_task["init_kwargs"]["timeout_s"] == 10.0

    def test_max_retries_propaga(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        runner.invoke(cli, [*base_args(csv_path), "--max-retries", "5"])
        assert mock_task["init_kwargs"]["max_retries"] == 5

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
            data={"dry_run": True, "would_send": 2, "exemplo_texto": "x"},
        )
        runner.invoke(cli, ["--dry-run", *base_args(csv_path)])
        assert mock_task["init_kwargs"]["dry_run"] is True


# ============================================================
# Saida do dry-run e avisos
# ============================================================


class TestDryRunOutput:
    def test_mostra_quantidade_e_exemplo(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"dry_run": True, "would_send": 2, "exemplo_texto": "Ola Ana!"},
        )
        result = runner.invoke(cli, ["--dry-run", *base_args(csv_path)])
        assert "Enviaria 2" in result.output
        assert "Ola Ana!" in result.output  # exemplo efemero exibido


class TestAvisoHttps:
    def test_http_externo_avisa(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            [*base_args(csv_path), "--base-url", "http://api.externa.com"],
        )
        assert "Aviso" in result.output

    def test_http_localhost_nao_avisa(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            [*base_args(csv_path), "--base-url", "http://localhost:5555"],
        )
        assert "Aviso" not in result.output

    def test_https_nao_avisa(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
        csv_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            [*base_args(csv_path), "--base-url", "https://api.telegram.org"],
        )
        assert "Aviso" not in result.output
