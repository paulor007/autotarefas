"""Testes para autotarefas.tasks.report_audit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from autotarefas.core.audit import AuditTrail
from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.report_audit import (
    ReportAuditTask,
    ReportFilters,
)

# ============================================================
# Helpers
# ============================================================


def _populate_audit_db(db_path: Path) -> None:
    """
    Popula audit DB com dados variados pra testes.

    Cria 12 registros:
    - 4 validate (3 success, 1 failure)
    - 3 backup (todos success)
    - 3 organize (2 success, 1 partial)
    - 2 init (1 success, 1 dry_run)

    Total: 12 execuções, distribuidas no tempo.
    """
    audit = AuditTrail(db_path=db_path)
    base_time = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)

    records = [
        # validate
        ("validate", "success", base_time, 100, 10, 0),
        ("validate", "success", base_time + timedelta(hours=1), 150, 15, 0),
        ("validate", "success", base_time + timedelta(hours=2), 120, 12, 0),
        ("validate", "failure", base_time + timedelta(hours=3), 80, 0, 5),
        # backup
        ("backup", "success", base_time + timedelta(hours=4), 500, 50, 0),
        ("backup", "success", base_time + timedelta(hours=5), 600, 60, 0),
        ("backup", "success", base_time + timedelta(hours=6), 550, 55, 0),
        # organize
        ("organize", "success", base_time + timedelta(hours=7), 200, 20, 0),
        ("organize", "success", base_time + timedelta(hours=8), 250, 25, 0),
        ("organize", "partial", base_time + timedelta(hours=9), 180, 18, 2),
        # init
        ("init", "success", base_time + timedelta(hours=10), 30, 0, 0),
        ("init", "dry_run", base_time + timedelta(hours=11), 25, 0, 0),
    ]

    for task_name, status, started_at, duration_ms, rows_aff, rows_fail in records:
        error_message = "fake error" if status in ("failure", "partial") else None
        audit.record(
            task_name=task_name,
            status=status,
            started_at=started_at,
            duration_ms=duration_ms,
            rows_affected=rows_aff,
            rows_failed=rows_fail,
            error_message=error_message,
        )


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def audit_db_populado(tmp_path: Path) -> Path:
    """Audit DB temporário pré-populado com dados de teste."""
    db_path = tmp_path / "test_audit.db"
    _populate_audit_db(db_path)
    return db_path


@pytest.fixture
def audit_db_vazio(tmp_path: Path) -> Path:
    """Audit DB temporário sem registros (so tabela criada)."""
    db_path = tmp_path / "empty_audit.db"
    AuditTrail(db_path=db_path)  # so cria tabela
    return db_path


# ============================================================
# Tests: ReportFilters (dataclass)
# ============================================================


class TestReportFilters:
    """Validações do dataclass ReportFilters."""

    def test_filtros_default_validos(self) -> None:
        """Filtros padrão (tudo None) sao validos."""
        f = ReportFilters()
        assert f.task_name is None
        assert f.status is None
        assert f.since is None
        assert f.until is None
        assert f.limit == 100

    def test_limit_zero_falha(self) -> None:
        with pytest.raises(ValidationError, match="limit"):
            ReportFilters(limit=0)

    def test_limit_negativo_falha(self) -> None:
        with pytest.raises(ValidationError, match="limit"):
            ReportFilters(limit=-1)

    def test_since_apos_until_falha(self) -> None:
        """since posterior a until: erro."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="anterior"):
            ReportFilters(
                since=now,
                until=now - timedelta(hours=1),
            )

    def test_since_igual_until_falha(self) -> None:
        """since == until: erro (intervalo vazio)."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="anterior"):
            ReportFilters(since=now, until=now)

    def test_filtros_validos_passam(self) -> None:
        """Configuração realista passa."""
        now = datetime.now(UTC)
        f = ReportFilters(
            task_name="validate",
            status="success",
            since=now - timedelta(days=7),
            until=now,
            limit=50,
        )
        assert f.task_name == "validate"
        assert f.limit == 50


# ============================================================
# Tests: ReportAuditTask básico
# ============================================================


class TestReportAuditTaskBasico:
    """Cenarios basicos de execucao."""

    def test_skipped_quando_db_nao_existe(self, tmp_path: Path) -> None:
        """DB inexistente: SKIPPED, exit 0."""
        nao_existe = tmp_path / "nao_existe.db"
        task = ReportAuditTask(audit_db_path=nao_existe)
        result = task.run()

        assert result.status == TaskStatus.SKIPPED
        assert "nao encontrado" in (result.error_message or "")

    def test_success_com_db_existente(self, audit_db_populado: Path) -> None:
        """DB com dados: SUCCESS."""
        task = ReportAuditTask(audit_db_path=audit_db_populado)
        result = task.run()
        assert result.is_success

    def test_total_executions_correto(self, audit_db_populado: Path) -> None:
        """Total bate com fixture (12 registros)."""
        result = ReportAuditTask(audit_db_path=audit_db_populado).run()
        assert result.data["total_executions"] == 12

    def test_db_vazio_total_zero(self, audit_db_vazio: Path) -> None:
        """DB com tabela mas sem registros: SUCCESS com total=0."""
        result = ReportAuditTask(audit_db_path=audit_db_vazio).run()
        assert result.is_success
        assert result.data["total_executions"] == 0

    def test_result_inclui_metadados(self, audit_db_populado: Path) -> None:
        """data inclui filters, report_type, paths."""
        result = ReportAuditTask(audit_db_path=audit_db_populado).run()
        for key in (
            "audit_db_path",
            "report_type",
            "filters",
            "total_executions",
        ):
            assert key in result.data

    def test_default_report_type_e_summary(self, audit_db_populado: Path) -> None:
        result = ReportAuditTask(audit_db_path=audit_db_populado).run()
        assert result.data["report_type"] == "summary"


# ============================================================
# Tests: Filtros
# ============================================================


class TestReportAuditTaskFiltros:
    """Filtros aplicados em queries."""

    def test_filtro_task_name(self, audit_db_populado: Path) -> None:
        """Filtra por task_name='validate' (4 registros na fixture)."""
        filters = ReportFilters(task_name="validate")
        result = ReportAuditTask(filters=filters, audit_db_path=audit_db_populado).run()
        assert result.data["total_executions"] == 4

    def test_filtro_status_success(self, audit_db_populado: Path) -> None:
        """Filtra por status='success' (8 registros: 3 validate + 3 backup + 2 organize)."""
        filters = ReportFilters(status="success")
        result = ReportAuditTask(filters=filters, audit_db_path=audit_db_populado).run()
        assert result.data["total_executions"] == 9

    def test_filtro_status_failure(self, audit_db_populado: Path) -> None:
        """Filtra por status='failure' (1 registro na fixture)."""
        filters = ReportFilters(status="failure")
        result = ReportAuditTask(filters=filters, audit_db_path=audit_db_populado).run()
        assert result.data["total_executions"] == 1

    def test_filtro_since(self, audit_db_populado: Path) -> None:
        """since posterior aos primeiros registros: total reduzido."""
        # Fixture comeca em 2026-05-20 12:00. Filtrando >= 18:00 (h+6)
        filters = ReportFilters(
            since=datetime(2026, 5, 20, 18, 0, 0, tzinfo=UTC),
        )
        result = ReportAuditTask(filters=filters, audit_db_path=audit_db_populado).run()
        # 6 registros depois de 18:00 (h+6 até h+11)
        assert result.data["total_executions"] == 6

    def test_filtro_until(self, audit_db_populado: Path) -> None:
        """until: pega so registros antes."""
        # < 15:00 (h+3): pega 3 registros (h+0, h+1, h+2)
        filters = ReportFilters(
            until=datetime(2026, 5, 20, 15, 0, 0, tzinfo=UTC),
        )
        result = ReportAuditTask(filters=filters, audit_db_path=audit_db_populado).run()
        assert result.data["total_executions"] == 3

    def test_filtro_periodo(self, audit_db_populado: Path) -> None:
        """Janela since-until reduz total."""
        filters = ReportFilters(
            since=datetime(2026, 5, 20, 14, 0, 0, tzinfo=UTC),
            until=datetime(2026, 5, 20, 18, 0, 0, tzinfo=UTC),
        )
        result = ReportAuditTask(filters=filters, audit_db_path=audit_db_populado).run()
        # h+2, h+3, h+4, h+5 = 4 registros
        assert result.data["total_executions"] == 4

    def test_filtros_combinados(self, audit_db_populado: Path) -> None:
        """task + status combinados."""
        filters = ReportFilters(
            task_name="validate",
            status="success",
        )
        result = ReportAuditTask(filters=filters, audit_db_path=audit_db_populado).run()
        # validate success: 3 registros
        assert result.data["total_executions"] == 3


# ============================================================
# Tests: Summary
# ============================================================


class TestReportAuditTaskSummary:
    """Conteudo do summary."""

    def test_by_task_correto(self, audit_db_populado: Path) -> None:
        """by_task tem contagem por task."""
        result = ReportAuditTask(audit_db_path=audit_db_populado).run()
        by_task = result.data["by_task"]
        assert by_task["validate"] == 4
        assert by_task["backup"] == 3
        assert by_task["organize"] == 3
        assert by_task["init"] == 2

    def test_by_status_correto(self, audit_db_populado: Path) -> None:
        result = ReportAuditTask(audit_db_path=audit_db_populado).run()
        by_status = result.data["by_status"]
        assert by_status["success"] == 9
        assert by_status["failure"] == 1
        assert by_status["partial"] == 1
        assert by_status["dry_run"] == 1

    def test_by_task_and_status_cross_tab(self, audit_db_populado: Path) -> None:
        """Cross-tab: dict[task][status] = count."""
        result = ReportAuditTask(audit_db_path=audit_db_populado).run()
        cross = result.data["by_task_and_status"]

        assert cross["validate"]["success"] == 3
        assert cross["validate"]["failure"] == 1
        assert cross["backup"]["success"] == 3
        assert cross["organize"]["partial"] == 1
        assert cross["init"]["dry_run"] == 1

    def test_avg_duration_by_task(self, audit_db_populado: Path) -> None:
        """Duração média por task."""
        result = ReportAuditTask(audit_db_path=audit_db_populado).run()
        avg = result.data["avg_duration_ms_by_task"]

        # backup: (500 + 600 + 550) / 3 = 550.0
        assert avg["backup"] == 550.0
        # init: (30 + 25) / 2 = 27.5
        assert avg["init"] == 27.5

    def test_total_rows_affected(self, audit_db_populado: Path) -> None:
        """Soma de rows_affected."""
        result = ReportAuditTask(audit_db_path=audit_db_populado).run()
        # 10 + 15 + 12 + 0 + 50 + 60 + 55 + 20 + 25 + 18 + 0 + 0 = 265
        assert result.data["total_rows_affected"] == 265

    def test_total_rows_failed(self, audit_db_populado: Path) -> None:
        """Soma de rows_failed."""
        result = ReportAuditTask(audit_db_path=audit_db_populado).run()
        # 0 + 0 + 0 + 5 + 0 + 0 + 0 + 0 + 0 + 2 + 0 + 0 = 7
        assert result.data["total_rows_failed"] == 7

    def test_recent_failures_inclui_failure_e_partial(self, audit_db_populado: Path) -> None:
        """recent_failures inclui status failure E partial."""
        result = ReportAuditTask(audit_db_path=audit_db_populado).run()
        failures = result.data["recent_failures"]

        # Fixture tem 1 failure (validate) + 1 partial (organize) = 2
        assert len(failures) == 2

        statuses = {f["status"] for f in failures}
        assert "failure" in statuses
        assert "partial" in statuses

    def test_recent_failures_limit_5(self, tmp_path: Path) -> None:
        """recent_failures limita a 5 mesmo com 10 falhas."""
        db_path = tmp_path / "many_failures.db"
        audit = AuditTrail(db_path=db_path)

        # Cria 10 falhas
        base_time = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)
        for i in range(10):
            audit.record(
                task_name="x",
                status="failure",
                started_at=base_time + timedelta(minutes=i),
                duration_ms=100,
            )

        result = ReportAuditTask(audit_db_path=db_path).run()
        # Limitado a 5
        assert len(result.data["recent_failures"]) == 5


# ============================================================
# Tests: report_type='list'
# ============================================================


class TestReportAuditTaskList:
    """report_type='list' retorna lista de execucoes."""

    def test_list_inclui_executions(self, audit_db_populado: Path) -> None:
        """data contem 'executions' (e nao 'by_task' etc)."""
        result = ReportAuditTask(
            audit_db_path=audit_db_populado,
            report_type="list",
        ).run()

        assert "executions" in result.data
        # summary fields NAO devem estar (so na summary)
        assert "by_task" not in result.data

    def test_list_retorna_todas_executions(self, audit_db_populado: Path) -> None:
        """Sem filtro: retorna todas (até limit)."""
        result = ReportAuditTask(
            audit_db_path=audit_db_populado,
            report_type="list",
        ).run()
        assert len(result.data["executions"]) == 12

    def test_list_respeita_limit(self, audit_db_populado: Path) -> None:
        """limit=5 retorna no maximo 5."""
        result = ReportAuditTask(
            filters=ReportFilters(limit=5),
            audit_db_path=audit_db_populado,
            report_type="list",
        ).run()
        assert len(result.data["executions"]) == 5

    def test_list_ordem_decrescente(self, audit_db_populado: Path) -> None:
        """Mais recente primeiro (ORDER BY id DESC)."""
        result = ReportAuditTask(
            audit_db_path=audit_db_populado,
            report_type="list",
        ).run()
        executions = result.data["executions"]
        # Primeiro deve ser o ultimo inserido (init dry_run, h+11)
        assert executions[0]["task_name"] == "init"
        assert executions[0]["status"] == "dry_run"


# ============================================================
# Tests: report_type='errors'
# ============================================================


class TestReportAuditTaskErrors:
    """report_type='errors' retorna so failures e partials."""

    def test_errors_so_failures_e_partials(self, audit_db_populado: Path) -> None:
        result = ReportAuditTask(
            audit_db_path=audit_db_populado,
            report_type="errors",
        ).run()

        executions = result.data["executions"]
        # 1 failure + 1 partial = 2
        assert len(executions) == 2

        statuses = {e["status"] for e in executions}
        assert "failure" in statuses
        assert "partial" in statuses

    def test_errors_nao_inclui_success(self, audit_db_populado: Path) -> None:
        """Success nao aparece em errors."""
        result = ReportAuditTask(
            audit_db_path=audit_db_populado,
            report_type="errors",
        ).run()

        statuses = {e["status"] for e in result.data["executions"]}
        assert "success" not in statuses

    def test_errors_respeita_limit(self, tmp_path: Path) -> None:
        """limit limita as falhas retornadas."""
        db_path = tmp_path / "many.db"
        audit = AuditTrail(db_path=db_path)

        for i in range(15):
            audit.record(
                task_name="x",
                status="failure",
                started_at=datetime(2026, 5, 20, tzinfo=UTC) + timedelta(minutes=i),
                duration_ms=100,
            )

        result = ReportAuditTask(
            filters=ReportFilters(limit=3),
            audit_db_path=db_path,
            report_type="errors",
        ).run()

        assert len(result.data["executions"]) == 3


# ============================================================
# Tests: Atributos da classe
# ============================================================


class TestReportAuditTaskAtributos:
    """Atributos de classe da task."""

    def test_name(self) -> None:
        assert ReportAuditTask.name == "report_audit"

    def test_description(self) -> None:
        assert ReportAuditTask.description

    def test_recent_failures_limit_constante(self) -> None:
        """_RECENT_FAILURES_LIMIT e ClassVar."""
        assert ReportAuditTask._RECENT_FAILURES_LIMIT == 5
