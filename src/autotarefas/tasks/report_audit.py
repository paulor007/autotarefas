"""
Task de geração de relatórios consolidados do audit trail.

Quarta subclasse real de BaseTask. Consulta o SQLite do audit (criado
por ``autotarefas.core.audit``) e gera **estatísticas agregadas** sobre
as execuções de tasks no projeto.

A task é **read-only** — apenas SELECTs no audit DB. O princípio
append-only do audit é preservado.

Tipos de relatório:
- ``summary`` (default): contagens, médias, falhas recentes
- ``list``: lista detalhada de execuções (com filtros)
- ``errors``: apenas execuções com status failure/partial

Filtros disponíveis (via ``ReportFilters``):
- ``task_name``: filtra por nome de task específica
- ``status``: filtra por status (success/failure/etc)
- ``since``: datetime inicial (UTC) — inclusivo
- ``until``: datetime final (UTC) — exclusivo
- ``limit``: número máximo de execuções em list/errors

Uso:
    from datetime import UTC, datetime, timedelta
    from autotarefas.tasks.report_audit import (
        ReportAuditTask, ReportFilters,
    )

    # Últimas 24h, todos os tipos
    filters = ReportFilters(
        since=datetime.now(UTC) - timedelta(days=1),
    )
    result = ReportAuditTask(filters=filters).run()

    if result.is_success:
        print(f"Total: {result.data['total_executions']}")
        print(f"Por task: {result.data['by_task']}")
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.core.settings import settings

# Type alias pros tipos de relatório
ReportType = Literal["summary", "list", "errors"]

# Statuses considerados "falha" (pra recent_failures e errors report)
_FAILURE_STATUSES: tuple[str, ...] = ("failure", "partial")


# ============================================================
# ReportFilters
# ============================================================


@dataclass(frozen=True, slots=True)
class ReportFilters:
    """
    Filtros para consulta do audit trail.

    Todos os campos são opcionais. Quando ``None``, o filtro
    correspondente não é aplicado (passa-tudo).

    Attributes:
        task_name: Filtra por uma task específica.
        status: Filtra por status (success, failure, partial, etc).
        since: Data inicial (UTC, inclusivo).
        until: Data final (UTC, exclusivo).
        limit: Máximo de execuções em list/errors (default 100).
    """

    task_name: str | None = None
    status: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 100

    def __post_init__(self) -> None:
        """Validações pos-construção."""
        if self.limit <= 0:
            raise ValidationError(
                f"limit deve ser > 0, recebeu: {self.limit}",
                field="limit",
                value=self.limit,
            )

        if self.since is not None and self.until is not None and self.since >= self.until:
            raise ValidationError(
                f"since ({self.since}) deve ser anterior a until ({self.until})",
                field="since",
                value=self.since,
            )


# ============================================================
# ReportAuditTask
# ============================================================


class ReportAuditTask(BaseTask):
    """
    Consulta o audit trail e gera estatísticas agregadas.

    Read-only: apenas SELECTs no SQLite do audit. Não modifica
    o histórico.

    Se o audit DB não existir (nenhuma task rodou ainda), a task
    retorna status SKIPPED sem erro.
    """

    name = "report_audit"
    description = "Gera relatorios do audit trail"

    #: Número de falhas recentes mostradas no summary.
    _RECENT_FAILURES_LIMIT: ClassVar[int] = 5

    def __init__(
        self,
        filters: ReportFilters | None = None,
        *,
        report_type: ReportType = "summary",
        dry_run: bool = False,
        audit_db_path: Path | None = None,
    ) -> None:
        """
        Inicializa ReportAuditTask.

        Args:
            filters: Filtros aplicados. Se None, usa defaults (sem filtro).
            report_type: Tipo de relatório. 'summary' (default) retorna
                estatísticas. 'list' retorna execuções detalhadas. 'errors'
                retorna apenas falhas.
            dry_run: Em report_audit, dry_run não muda comportamento
                (operação já é read-only). Mantido por consistência com
                BaseTask.
        """
        super().__init__(dry_run=dry_run)
        self.filters = filters if filters is not None else ReportFilters()
        self.report_type: ReportType = report_type
        self.audit_db_path: Path = (
            audit_db_path if audit_db_path is not None else settings.audit_db_path
        )

    def execute(self) -> TaskResult:
        """Executa as queries e monta o resultado."""
        started_at = datetime.now(UTC)

        # Audit DB pode não existir (nenhuma task rodou ainda)
        if not self.audit_db_path.exists():
            return self._make_result(
                status=TaskStatus.SKIPPED,
                started_at=started_at,
                error_message=(
                    f"Audit DB nao encontrado em '{self.audit_db_path}'. "
                    "Nenhuma task foi registrada ainda."
                ),
                data={
                    "audit_db_path": str(self.audit_db_path),
                    "report_type": self.report_type,
                },
            )

        # Abre conexão e executa queries conforme report_type
        with closing(sqlite3.connect(self.audit_db_path)) as conn:
            conn.row_factory = sqlite3.Row

            data: dict[str, Any] = {
                "audit_db_path": str(self.audit_db_path),
                "report_type": self.report_type,
                "filters": {
                    "task_name": self.filters.task_name,
                    "status": self.filters.status,
                    "since": self.filters.since.isoformat() if self.filters.since else None,
                    "until": self.filters.until.isoformat() if self.filters.until else None,
                    "limit": self.filters.limit,
                },
            }

            # Sempre coleta o total (barato e útil)
            data["total_executions"] = self._count_total(conn)

            if self.report_type == "summary":
                data.update(self._build_summary(conn))
            elif self.report_type == "list":
                data["executions"] = self._list_executions(conn)
            elif self.report_type == "errors":
                data["executions"] = self._list_errors(conn)

        return self._make_result(
            status=TaskStatus.SUCCESS,
            started_at=started_at,
            rows_affected=data["total_executions"],
            data=data,
        )

    # ========================================================
    # Builders por report_type
    # ========================================================

    def _build_summary(self, conn: sqlite3.Connection) -> dict[str, Any]:
        """Constrói dict do summary (estatísticas agregadas)."""
        return {
            "by_task": self._count_by_task(conn),
            "by_status": self._count_by_status(conn),
            "by_task_and_status": self._count_by_task_and_status(conn),
            "avg_duration_ms_by_task": self._avg_duration_by_task(conn),
            "total_rows_affected": self._sum_rows_affected(conn),
            "total_rows_failed": self._sum_rows_failed(conn),
            "recent_failures": self._recent_failures(conn),
        }

    # ========================================================
    # Queries SQL — auxiliares
    # ========================================================

    def _apply_filters(self, base_sql: str, params: list[Any]) -> tuple[str, list[Any]]:
        """
        Aplica filtros do ReportFilters numa query SQL.

        Modifica ``base_sql`` adicionando ``AND ...`` conforme filtros
        ativos. Modifica ``params`` adicionando os valores.

        Args:
            base_sql: SQL base, deve já conter "WHERE 1=1" pra facilitar.
            params: Lista de parâmetros (será modificada in-place).

        Returns:
            Tupla (sql_modificado, params_modificado).
        """
        if self.filters.task_name is not None:
            base_sql += " AND task_name = ?"
            params.append(self.filters.task_name)

        if self.filters.status is not None:
            base_sql += " AND status = ?"
            params.append(self.filters.status)

        if self.filters.since is not None:
            base_sql += " AND timestamp >= ?"
            params.append(self.filters.since.isoformat())

        if self.filters.until is not None:
            base_sql += " AND timestamp < ?"
            params.append(self.filters.until.isoformat())

        return base_sql, params

    # ========================================================
    # Queries SQL — agregadas
    # ========================================================

    def _count_total(self, conn: sqlite3.Connection) -> int:
        """Total de execuções (aplicando filtros)."""
        sql = "SELECT COUNT(*) AS n FROM audit WHERE 1=1"
        sql, params = self._apply_filters(sql, [])
        row = conn.execute(sql, params).fetchone()
        return int(row["n"])

    def _count_by_task(self, conn: sqlite3.Connection) -> dict[str, int]:
        """Contagem por task. Ordenada por count desc."""
        sql = "SELECT task_name, COUNT(*) AS n FROM audit WHERE 1=1"
        sql, params = self._apply_filters(sql, [])
        sql += " GROUP BY task_name ORDER BY n DESC"

        rows = conn.execute(sql, params).fetchall()
        return {row["task_name"]: int(row["n"]) for row in rows}

    def _count_by_status(self, conn: sqlite3.Connection) -> dict[str, int]:
        """Contagem por status. Ordenada por count desc."""
        sql = "SELECT status, COUNT(*) AS n FROM audit WHERE 1=1"
        sql, params = self._apply_filters(sql, [])
        sql += " GROUP BY status ORDER BY n DESC"

        rows = conn.execute(sql, params).fetchall()
        return {row["status"]: int(row["n"]) for row in rows}

    def _count_by_task_and_status(self, conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
        """
        Cross-tab: dict[task_name][status] = count.

        Útil pra mostrar quantos sucessos e falhas por task.
        """
        sql = "SELECT task_name, status, COUNT(*) AS n FROM audit WHERE 1=1"
        sql, params = self._apply_filters(sql, [])
        sql += " GROUP BY task_name, status"

        rows = conn.execute(sql, params).fetchall()
        result: dict[str, dict[str, int]] = {}
        for row in rows:
            task = row["task_name"]
            status = row["status"]
            count = int(row["n"])

            if task not in result:
                result[task] = {}
            result[task][status] = count

        return result

    def _avg_duration_by_task(self, conn: sqlite3.Connection) -> dict[str, float]:
        """
        Duração média (ms) por task.

        Ignora linhas com duration_ms NULL.
        """
        sql = (
            "SELECT task_name, AVG(duration_ms) AS avg_ms FROM audit "
            "WHERE 1=1 AND duration_ms IS NOT NULL"
        )
        sql, params = self._apply_filters(sql, [])
        sql += " GROUP BY task_name ORDER BY avg_ms DESC"

        rows = conn.execute(sql, params).fetchall()
        return {row["task_name"]: round(float(row["avg_ms"]), 2) for row in rows}

    def _sum_rows_affected(self, conn: sqlite3.Connection) -> int:
        """Soma total de rows_affected (linhas processadas com sucesso)."""
        sql = "SELECT COALESCE(SUM(rows_affected), 0) AS total " "FROM audit WHERE 1=1"
        sql, params = self._apply_filters(sql, [])
        row = conn.execute(sql, params).fetchone()
        return int(row["total"])

    def _sum_rows_failed(self, conn: sqlite3.Connection) -> int:
        """Soma total de rows_failed."""
        sql = "SELECT COALESCE(SUM(rows_failed), 0) AS total " "FROM audit WHERE 1=1"
        sql, params = self._apply_filters(sql, [])
        row = conn.execute(sql, params).fetchone()
        return int(row["total"])

    def _recent_failures(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        """
        Últimas N falhas (default 5).

        Inclui apenas status em _FAILURE_STATUSES.
        """
        # Placeholders para os statuses (?, ?, ?...)
        placeholders = ",".join("?" * len(_FAILURE_STATUSES))
        sql = (
            f"SELECT timestamp, task_name, status, duration_ms, error_message "  # noqa: S608  # nosec B608
            f"FROM audit WHERE 1=1 AND status IN ({placeholders})"
        )
        params: list[Any] = list(_FAILURE_STATUSES)
        sql, params = self._apply_filters(sql, params)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(self._RECENT_FAILURES_LIMIT)

        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    # ========================================================
    # Queries SQL — listas detalhadas
    # ========================================================

    def _list_executions(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        """Lista detalhada de execuções (com filtros, mais recente primeiro)."""
        sql = "SELECT * FROM audit WHERE 1=1"
        sql, params = self._apply_filters(sql, [])
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(self.filters.limit)

        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def _list_errors(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        """Lista apenas execuções com status de falha."""
        placeholders = ",".join("?" * len(_FAILURE_STATUSES))
        sql = f"SELECT * FROM audit WHERE 1=1 AND status IN ({placeholders})"  # noqa: S608  # nosec B608
        params: list[Any] = list(_FAILURE_STATUSES)
        sql, params = self._apply_filters(sql, params)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(self.filters.limit)

        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


__all__ = [
    "ReportAuditTask",
    "ReportFilters",
    "ReportType",
]
