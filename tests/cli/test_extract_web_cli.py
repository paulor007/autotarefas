"""
Testes do comando CLI `autotarefas extract web`.

ESTRATEGIA:
- CliRunner via grupo `cli` principal.
- Mocka ExtractWebTask (holder) para inspecionar kwargs e resultado.
- Testa em especial o parse de --field (coluna=seletor).

Cobertura:
- --help
- Validacao: URL invalida e --field mal formatado -> exit 2
- Exit codes (success/failure/dry-run/ValidationError)
- Parse de --field; --field obrigatorio
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
    pass

web_module = importlib.import_module("autotarefas.cli.commands.extract.web")

URL = "http://localhost:5555/catalogo"


def make_result(
    status: TaskStatus,
    *,
    data: dict[str, Any] | None = None,
    rows_affected: int = 0,
    error_message: str | None = None,
) -> TaskResult:
    now = datetime.now(UTC)
    return TaskResult(
        task_name="extract_web",
        status=status,
        started_at=now,
        finished_at=now,
        duration_ms=10,
        rows_affected=rows_affected,
        data=data or {},
        error_message=error_message,
    )


def base_args() -> list[str]:
    return [
        "extract",
        "web",
        "-u",
        URL,
        "-o",
        "p.csv",
        "-r",
        "tr.produto",
        "-f",
        "nome=td.nome",
    ]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_task(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    holder: dict[str, Any] = {
        "result": make_result(
            TaskStatus.SUCCESS,
            data={"saved": True, "output_path": "p.csv", "extracted": 5},
            rows_affected=5,
        ),
        "init_kwargs": None,
        "raise_on_init": None,
    }

    class FakeTask:
        def __init__(self, **kwargs: Any) -> None:
            if holder["raise_on_init"] is not None:
                raise holder["raise_on_init"]
            holder["init_kwargs"] = kwargs

        def run(self) -> TaskResult:
            return cast("TaskResult", holder["result"])

    monkeypatch.setattr(web_module, "ExtractWebTask", FakeTask)
    return holder


class TestHelp:
    def test_extract_help_lista_web(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["extract", "--help"])
        assert result.exit_code == 0
        assert "web" in result.output

    def test_web_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["extract", "web", "--help"])
        assert result.exit_code == 0
        assert "--row-selector" in result.output
        assert "--field" in result.output


class TestValidation:
    def test_url_invalida(self, runner: CliRunner, mock_task: dict[str, Any]) -> None:
        result = runner.invoke(
            cli,
            [
                "extract",
                "web",
                "-u",
                "ftp://x",
                "-o",
                "p.csv",
                "-r",
                "tr.produto",
                "-f",
                "nome=td.nome",
            ],
        )
        assert result.exit_code == 2

    def test_field_sem_igual(self, runner: CliRunner, mock_task: dict[str, Any]) -> None:
        result = runner.invoke(
            cli,
            [
                "extract",
                "web",
                "-u",
                URL,
                "-o",
                "p.csv",
                "-r",
                "tr.produto",
                "-f",
                "semIgual",
            ],
        )
        assert result.exit_code == 2

    def test_field_obrigatorio(self, runner: CliRunner, mock_task: dict[str, Any]) -> None:
        # sem -f, o Click rejeita (required)
        result = runner.invoke(
            cli,
            [
                "extract",
                "web",
                "-u",
                URL,
                "-o",
                "p.csv",
                "-r",
                "tr.produto",
            ],
        )
        assert result.exit_code == 2


class TestExitCodes:
    def test_sucesso(self, runner: CliRunner, mock_task: dict[str, Any]) -> None:
        result = runner.invoke(cli, base_args())
        assert result.exit_code == 0

    def test_failure(self, runner: CliRunner, mock_task: dict[str, Any]) -> None:
        mock_task["result"] = make_result(
            TaskStatus.FAILURE,
            error_message="Erro ao acessar a pagina",
        )
        result = runner.invoke(cli, base_args())
        assert result.exit_code == 1

    def test_dry_run(self, runner: CliRunner, mock_task: dict[str, Any]) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"dry_run": True, "would_extract_first_page": 10, "has_next": True},
        )
        result = runner.invoke(cli, ["--dry-run", *base_args()])
        assert result.exit_code == 0

    def test_validation_error(self, runner: CliRunner, mock_task: dict[str, Any]) -> None:
        mock_task["raise_on_init"] = ValidationError("config invalida")
        result = runner.invoke(cli, base_args())
        assert result.exit_code == 2

    def test_zero_itens(self, runner: CliRunner, mock_task: dict[str, Any]) -> None:
        mock_task["result"] = make_result(
            TaskStatus.SUCCESS,
            data={"saved": False, "extracted": 0},
        )
        result = runner.invoke(cli, base_args())
        assert result.exit_code == 0  # 0 itens nao eh erro


class TestFields:
    def test_um_field(self, runner: CliRunner, mock_task: dict[str, Any]) -> None:
        runner.invoke(cli, base_args())
        assert mock_task["init_kwargs"]["fields"] == {"nome": "td.nome"}

    def test_varios_fields(self, runner: CliRunner, mock_task: dict[str, Any]) -> None:
        runner.invoke(
            cli,
            [
                "extract",
                "web",
                "-u",
                URL,
                "-o",
                "p.csv",
                "-r",
                "tr.produto",
                "-f",
                "id=td.id",
                "-f",
                "nome=td.nome",
                "-f",
                "preco=td.preco",
            ],
        )
        assert mock_task["init_kwargs"]["fields"] == {
            "id": "td.id",
            "nome": "td.nome",
            "preco": "td.preco",
        }

    def test_field_com_espacos(self, runner: CliRunner, mock_task: dict[str, Any]) -> None:
        runner.invoke(
            cli,
            [
                "extract",
                "web",
                "-u",
                URL,
                "-o",
                "p.csv",
                "-r",
                "tr.produto",
                "-f",
                " nome = td.nome ",
            ],
        )
        assert mock_task["init_kwargs"]["fields"] == {"nome": "td.nome"}

    def test_url_e_selectors_propagam(
        self,
        runner: CliRunner,
        mock_task: dict[str, Any],
    ) -> None:
        runner.invoke(
            cli,
            [
                *base_args(),
                "-n",
                "a.next",
                "--max-pages",
                "3",
            ],
        )
        kw = mock_task["init_kwargs"]
        assert kw["url"] == URL
        assert kw["row_selector"] == "tr.produto"
        assert kw["next_selector"] == "a.next"
        assert kw["max_pages"] == 3
