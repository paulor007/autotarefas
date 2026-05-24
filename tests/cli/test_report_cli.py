"""Testes para autotarefas.cli.commands.report."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from autotarefas.cli.commands.report import report
from autotarefas.cli.main import cli
from autotarefas.core.audit import AuditTrail

# ============================================================
# Helpers
# ============================================================


def _setup_audit_db(db_path: Path) -> None:
    """
    Popula audit DB simplificado pra testes CLI.

    Cria 4 registros:
    - 2 validate success
    - 1 backup success
    - 1 organize failure

    Total: 4 execuções, todas recentes (últimas horas).
    """
    audit = AuditTrail(db_path=db_path)
    base_time = datetime.now(UTC) - timedelta(hours=3)

    audit.record(
        task_name="validate",
        status="success",
        started_at=base_time,
        duration_ms=100,
        rows_affected=10,
    )
    audit.record(
        task_name="validate",
        status="success",
        started_at=base_time + timedelta(hours=1),
        duration_ms=120,
        rows_affected=12,
    )
    audit.record(
        task_name="backup",
        status="success",
        started_at=base_time + timedelta(hours=2),
        duration_ms=500,
        rows_affected=50,
    )
    audit.record(
        task_name="organize",
        status="failure",
        started_at=base_time + timedelta(hours=3),
        duration_ms=80,
        error_message="path traversal bloqueado",
    )


class _FakeSettings:
    """Stub de Settings — contorna computed property (sem setter)."""

    def __init__(self, audit_db_path: Path) -> None:
        self.audit_db_path = audit_db_path


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(autouse=True)
def _registrar_report_no_cli() -> None:
    """
    Garante que 'report' esta registrado no cli durante os testes.

    Necessario porque main.py so registra 'report' na Etapa 5 do
    release v0.4.0. Fixture eh idempotente: se ja estiver registrado,
    nao faz nada.
    """
    if "report" not in cli.commands:
        cli.add_command(report)


@pytest.fixture
def runner() -> CliRunner:
    """CliRunner padrão."""
    return CliRunner()


@pytest.fixture
def audit_db_para_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Audit DB temporário + substitui settings no modulo report_audit.

    Como settings.audit_db_path eh computed property (sem setter),
    substituimos o objeto 'settings' inteiro dentro do modulo
    autotarefas.tasks.report_audit por um fake.
    """
    db_path = tmp_path / "test_audit.db"
    _setup_audit_db(db_path)

    monkeypatch.setattr(
        "autotarefas.tasks.report_audit.settings",
        _FakeSettings(audit_db_path=db_path),
    )
    return db_path


@pytest.fixture
def audit_db_inexistente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Settings (no modulo report_audit) aponta pra DB que NAO existe."""
    db_path = tmp_path / "nao_existe.db"
    monkeypatch.setattr(
        "autotarefas.tasks.report_audit.settings",
        _FakeSettings(audit_db_path=db_path),
    )
    return db_path


# ============================================================
# Tests: Básico
# ============================================================


class TestReportCommandBasico:
    """Cenarios basicos do comando."""

    def test_help_funciona(self, runner: CliRunner) -> None:
        """--help nao quebra."""
        result = runner.invoke(cli, ["report", "--help"])
        assert result.exit_code == 0
        assert "report" in result.output.lower()

    def test_executa_sem_args_default_24h(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """Sem args: summary das ultimas 24h."""
        result = runner.invoke(cli, ["report"])
        assert result.exit_code == 0
        assert "Relatorio" in result.output
        assert "execucoes" in result.output

    def test_skipped_quando_db_inexistente(
        self, runner: CliRunner, audit_db_inexistente: Path
    ) -> None:
        """DB inexistente: warning, exit 0."""
        result = runner.invoke(cli, ["report"])
        assert result.exit_code == 0
        assert "nao encontrado" in result.output.lower() or "skipped" in result.output.lower()

    def test_mostra_total_execucoes(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """Summary mostra total."""
        result = runner.invoke(cli, ["report"])
        assert result.exit_code == 0
        assert "4" in result.output

    def test_mostra_por_task(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """Summary mostra cada task."""
        result = runner.invoke(cli, ["report"])
        assert result.exit_code == 0
        assert "validate" in result.output
        assert "backup" in result.output
        assert "organize" in result.output


# ============================================================
# Tests: Filtros
# ============================================================


class TestReportCommandFiltros:
    """Cada flag de filtro do comando."""

    def test_filtro_task(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """--task valida: mostra so validate."""
        result = runner.invoke(cli, ["report", "--task", "validate"])
        assert result.exit_code == 0
        assert "validate" in result.output
        assert "2" in result.output  # 2 validates

    def test_filtro_status_failure(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """--status failure: mostra so falhas."""
        result = runner.invoke(cli, ["report", "--status", "failure"])
        assert result.exit_code == 0
        assert "organize" in result.output

    def test_filtro_days_muitos(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """--days 30: pega tudo."""
        result = runner.invoke(cli, ["report", "--days", "30"])
        assert result.exit_code == 0
        assert "4" in result.output

    def test_filtro_since_data(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """--since aceita formato YYYY-MM-DD."""
        result = runner.invoke(cli, ["report", "--since", "2020-01-01"])
        assert result.exit_code == 0

    def test_filtro_days_zero_levanta_erro(
        self, runner: CliRunner, audit_db_para_cli: Path
    ) -> None:
        """--days 0 cria janela vazia, mas comando aceita."""
        result = runner.invoke(cli, ["report", "--days", "0"])
        assert result.exit_code == 0

    def test_filtro_limit_zero_falha(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """--limit 0 invalido (validacao do ReportFilters)."""
        result = runner.invoke(cli, ["report", "--limit", "0"])
        assert result.exit_code == 2


# ============================================================
# Tests: Tipos de relatório
# ============================================================


class TestReportCommandTipos:
    """--type summary/list/errors."""

    def test_type_list_mostra_execucoes(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """--type list mostra tabela detalhada."""
        result = runner.invoke(cli, ["report", "--type", "list"])
        assert result.exit_code == 0
        assert "Timestamp" in result.output or "Task" in result.output

    def test_type_errors_mostra_so_falhas(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """--type errors mostra so failures."""
        result = runner.invoke(cli, ["report", "--type", "errors"])
        assert result.exit_code == 0
        assert "organize" in result.output

    def test_type_case_insensitive(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """--type SUMMARY (uppercase) tambem funciona."""
        result = runner.invoke(cli, ["report", "--type", "SUMMARY"])
        assert result.exit_code == 0


# ============================================================
# Tests: Formatos de saída
# ============================================================


class TestReportCommandFormatos:
    """--format table/json/csv."""

    def test_format_json_e_valido(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """--format json gera JSON parseavel."""
        result = runner.invoke(cli, ["report", "--format", "json"])
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert "total_executions" in data
        assert data["total_executions"] >= 1

    def test_format_json_inclui_filters(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """JSON inclui metadados de filtros."""
        result = runner.invoke(cli, ["report", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "filters" in data
        assert "report_type" in data

    def test_format_csv_em_list(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """--format csv com --type list gera CSV valido."""
        result = runner.invoke(cli, ["report", "--type", "list", "--format", "csv"])
        assert result.exit_code == 0
        assert "task_name" in result.output

    def test_format_csv_em_summary_avisa(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """--format csv com summary mostra aviso (CSV nao faz sentido)."""
        result = runner.invoke(cli, ["report", "--type", "summary", "--format", "csv"])
        assert result.exit_code == 0
        assert "CSV" in result.output or "summary" in result.output.lower()


# ============================================================
# Tests: Output em arquivo
# ============================================================


class TestReportCommandOutput:
    """--output salva em arquivo."""

    def test_output_salva_arquivo(
        self,
        runner: CliRunner,
        audit_db_para_cli: Path,
        tmp_path: Path,
    ) -> None:
        """--output PATH salva relatorio."""
        output = tmp_path / "rel.txt"
        result = runner.invoke(cli, ["report", "--output", str(output)])

        assert result.exit_code == 0
        assert output.exists()
        assert "Relatorio" in output.read_text(encoding="utf-8")

    def test_output_json_salva(
        self,
        runner: CliRunner,
        audit_db_para_cli: Path,
        tmp_path: Path,
    ) -> None:
        """--output com --format json salva JSON valido."""
        output = tmp_path / "rel.json"
        result = runner.invoke(cli, ["report", "--format", "json", "--output", str(output)])

        assert result.exit_code == 0
        assert output.exists()
        data = json.loads(output.read_text(encoding="utf-8"))
        assert "total_executions" in data

    def test_output_cria_pasta(
        self,
        runner: CliRunner,
        audit_db_para_cli: Path,
        tmp_path: Path,
    ) -> None:
        """Pasta inexistente eh criada com parents=True."""
        output = tmp_path / "nova_pasta" / "sub" / "rel.txt"
        result = runner.invoke(cli, ["report", "--output", str(output)])

        assert result.exit_code == 0
        assert output.exists()

    def test_output_dry_run_nao_salva(
        self,
        runner: CliRunner,
        audit_db_para_cli: Path,
        tmp_path: Path,
    ) -> None:
        """--dry-run + --output: NAO salva arquivo, mostra no terminal."""
        output = tmp_path / "rel.txt"
        result = runner.invoke(
            cli,
            ["--dry-run", "report", "--output", str(output)],
        )

        assert result.exit_code == 0
        assert not output.exists()
        assert "DRY-RUN" in result.output or "dry-run" in result.output.lower()


# ============================================================
# Tests: Exit codes
# ============================================================


class TestReportCommandExitCodes:
    """Exit codes diferenciados."""

    def test_exit_0_sucesso(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        result = runner.invoke(cli, ["report"])
        assert result.exit_code == 0

    def test_exit_0_skipped(self, runner: CliRunner, audit_db_inexistente: Path) -> None:
        """Skipped (DB inexistente) tambem eh exit 0."""
        result = runner.invoke(cli, ["report"])
        assert result.exit_code == 0

    def test_exit_2_filtros_invalidos(self, runner: CliRunner, audit_db_para_cli: Path) -> None:
        """--limit 0 eh erro de filtro (exit 2)."""
        result = runner.invoke(cli, ["report", "--limit", "0"])
        assert result.exit_code == 2
