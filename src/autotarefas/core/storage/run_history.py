"""
Histórico de Execuções do AutoTarefas.

Persiste histórico de execuções em SQLite para análise e auditoria:
    - RunStatus: Status de uma execução
    - RunRecord: Representa uma execução
    - RunHistory: Gerencia histórico em SQLite

Uso:
    from autotarefas.core.storage.run_history import RunHistory, RunRecord, RunStatus

    history = RunHistory()

    # Registrar execução
    record = history.start_run("job123", "backup_diario", "backup")
    # ... executa task ...
    history.finish_run(record.id, RunStatus.SUCCESS, duration=45.2)

    # Consultar histórico
    runs = history.get_by_job("job123")
    stats = history.get_stats("job123")
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Final

from autotarefas.core.logger import logger
from autotarefas.utils.datetime_utils import dt_to_iso, parse_dt, utc_now

# =============================================================================
# Modelos
# =============================================================================


class RunStatus(Enum):
    """
    Status de uma execução.

    Valores:
        PENDING: Aguardando início
        RUNNING: Em execução
        SUCCESS: Concluído com sucesso
        FAILED: Falhou com erro
        CANCELLED: Cancelado pelo usuário
        TIMEOUT: Excedeu tempo limite
        SKIPPED: Pulado (job desabilitado)
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass(slots=True)
class RunRecord:
    """
    Representa uma execução de job.

    Attributes:
        id: Identificador único da execução
        job_id: ID do job executado
        job_name: Nome do job
        task: Nome da task
        status: Status da execução
        started_at: Início da execução (UTC)
        finished_at: Fim da execução (UTC)
        duration: Duração em segundos
        error: Mensagem de erro se houver
        output: Saída/resultado da execução
        params: Parâmetros usados
        trigger: O que disparou (scheduled, manual, retry)
        retry_count: Número da tentativa (0 = primeira)
        metadata: Dados adicionais
    """

    id: str
    job_id: str
    job_name: str
    task: str
    status: RunStatus = RunStatus.PENDING

    # Observação: usamos Any aqui para aceitar str/datetime quando vier do banco
    started_at: Any = field(default_factory=utc_now)
    finished_at: Any = None

    duration: float = 0.0
    error: str | None = None
    output: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    trigger: str = "scheduled"
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """
        Normaliza campos após criação:

        - Converte status para enum
        - Garante datetimes timezone-aware em UTC
        """
        if isinstance(self.status, str):
            self.status = RunStatus(self.status)

        self.started_at = parse_dt(self.started_at) or utc_now()
        self.finished_at = parse_dt(self.finished_at)

    def to_dict(self) -> dict[str, Any]:
        """
        Converte para dicionário serializável.

        Returns:
            Dicionário pronto para JSON/logging
        """
        return {
            "id": self.id,
            "job_id": self.job_id,
            "job_name": self.job_name,
            "task": self.task,
            "status": self.status.value,
            "started_at": dt_to_iso(self.started_at),
            "finished_at": dt_to_iso(self.finished_at),
            "duration": self.duration,
            "error": self.error,
            "output": self.output,
            "params": self.params,
            "trigger": self.trigger,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunRecord:
        """
        Cria RunRecord a partir de dicionário.

        Args:
            data: Dicionário com campos do registro

        Returns:
            Instância de RunRecord
        """
        status_raw = data.get("status", RunStatus.PENDING.value)
        status = RunStatus(status_raw) if isinstance(status_raw, str) else status_raw

        return cls(
            id=str(data["id"]),
            job_id=str(data["job_id"]),
            job_name=str(data["job_name"]),
            task=str(data["task"]),
            status=status,
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            duration=float(data.get("duration", 0.0)),
            error=data.get("error"),
            output=data.get("output"),
            params=dict(data.get("params", {})),
            trigger=str(data.get("trigger", "scheduled")),
            retry_count=int(data.get("retry_count", 0)),
            metadata=dict(data.get("metadata", {})),
        )

    @property
    def is_finished(self) -> bool:
        """
        Indica se a execução terminou.

        Returns:
            True se status não for PENDING/RUNNING
        """
        return self.status not in (RunStatus.PENDING, RunStatus.RUNNING)

    @property
    def is_success(self) -> bool:
        """
        Indica se a execução foi bem sucedida.

        Returns:
            True se status == SUCCESS
        """
        return self.status == RunStatus.SUCCESS


@dataclass(slots=True)
class RunStats:
    """
    Estatísticas de execuções.

    Attributes:
        total_runs: Total de execuções
        success_count: Execuções com sucesso
        failed_count: Execuções com falha
        cancelled_count: Execuções canceladas
        timeout_count: Execuções com timeout
        success_rate: Taxa de sucesso (0.0 a 1.0)
        avg_duration: Duração média em segundos
        min_duration: Menor duração
        max_duration: Maior duração
        last_run: Data da última execução
        last_success: Data do último sucesso
        last_failure: Data da última falha
    """

    total_runs: int = 0
    success_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    timeout_count: int = 0

    success_rate: float = 0.0
    avg_duration: float = 0.0
    min_duration: float = 0.0
    max_duration: float = 0.0

    last_run: datetime | None = None
    last_success: datetime | None = None
    last_failure: datetime | None = None


# =============================================================================
# Histórico (SQLite)
# =============================================================================


class RunHistory:
    """
    Gerenciador de histórico de execuções em SQLite.

    Armazena todas as execuções de jobs para análise,
    auditoria e estatísticas.
    """

    DEFAULT_FILENAME: Final[str] = "run_history.db"

    def __init__(self, db_path: str | Path | None = None) -> None:
        """
        Inicializa o RunHistory.

        Args:
            db_path: Caminho do banco SQLite (opcional)
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            from autotarefas.config import settings

            data_dir = getattr(settings, "DATA_DIR", None)
            if data_dir is None:
                data_dir = Path(settings.data_dir)

            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / self.DEFAULT_FILENAME

        self._init_db()

    def _init_db(self) -> None:
        """
        Inicializa o banco de dados (tabela e índices).

        Observações:
            - Timestamps são armazenados como ISO string
            - params/metadata são JSON string
            - índices otimizam consultas por job/status/data
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    job_name TEXT NOT NULL,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    duration REAL DEFAULT 0,
                    error TEXT,
                    output TEXT,
                    params TEXT,
                    trigger TEXT DEFAULT 'scheduled',
                    retry_count INTEGER DEFAULT 0,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_job_id ON runs(job_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task)")

            conn.commit()

        logger.debug(f"Banco de histórico inicializado: {self.db_path}")

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Obtém conexão com o banco.

        Observações:
            - timeout ajuda em cenários concorrentes
            - pragmas melhoram estabilidade e performance básica

        Yields:
            Conexão SQLite
        """
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            # Pragmas úteis e seguros (sem “mexer demais”)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            yield conn
        finally:
            conn.close()

    def _row_to_record(self, row: sqlite3.Row) -> RunRecord:
        """
        Converte uma linha do banco para RunRecord.

        Args:
            row: sqlite3.Row

        Returns:
            RunRecord normalizado
        """
        return RunRecord(
            id=row["id"],
            job_id=row["job_id"],
            job_name=row["job_name"],
            task=row["task"],
            status=RunStatus(row["status"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            duration=float(row["duration"] or 0.0),
            error=row["error"],
            output=row["output"],
            params=json.loads(row["params"]) if row["params"] else {},
            trigger=row["trigger"] or "scheduled",
            retry_count=int(row["retry_count"] or 0),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    # -------------------------------------------------------------------------
    # API pública
    # -------------------------------------------------------------------------

    def start_run(
        self,
        job_id: str,
        job_name: str,
        task: str,
        params: dict[str, Any] | None = None,
        trigger: str = "scheduled",
        retry_count: int = 0,
    ) -> RunRecord:
        """
        Registra início de uma execução.

        Args:
            job_id: ID do job
            job_name: Nome do job
            task: Nome da task
            params: Parâmetros usados
            trigger: Tipo de disparo (scheduled, manual, retry)
            retry_count: Número da tentativa

        Returns:
            RunRecord criado
        """
        record = RunRecord(
            id=str(uuid.uuid4())[:12],
            job_id=job_id,
            job_name=job_name,
            task=task,
            status=RunStatus.RUNNING,
            started_at=utc_now(),
            params=params or {},
            trigger=trigger,
            retry_count=retry_count,
        )

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO runs (id, job_id, job_name, task, status, started_at, params, trigger, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.job_id,
                    record.job_name,
                    record.task,
                    record.status.value,
                    dt_to_iso(record.started_at),
                    json.dumps(record.params, ensure_ascii=False),
                    record.trigger,
                    record.retry_count,
                ),
            )
            conn.commit()

        logger.debug(f"Execução iniciada: {record.id} ({job_name})")
        return record

    def finish_run(
        self,
        run_id: str,
        status: RunStatus,
        duration: float = 0.0,
        error: str | None = None,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Registra fim de uma execução.

        Args:
            run_id: ID da execução
            status: Status final
            duration: Duração em segundos
            error: Mensagem de erro se houver
            output: Saída/resultado
            metadata: Dados adicionais

        Returns:
            True se atualizado com sucesso
        """
        finished_at = utc_now()

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE runs
                SET status = ?, finished_at = ?, duration = ?, error = ?, output = ?, metadata = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    dt_to_iso(finished_at),
                    float(duration),
                    error,
                    output,
                    json.dumps(metadata, ensure_ascii=False) if metadata else None,
                    run_id,
                ),
            )
            conn.commit()

            if cursor.rowcount > 0:
                logger.debug(f"Execução finalizada: {run_id} ({status.value})")
                return True

        return False

    def get(self, run_id: str) -> RunRecord | None:
        """
        Obtém uma execução pelo ID.

        Args:
            run_id: ID da execução

        Returns:
            RunRecord ou None
        """
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            return self._row_to_record(row) if row else None

    def get_by_job(
        self,
        job_id: str,
        limit: int = 100,
        offset: int = 0,
        status: RunStatus | None = None,
    ) -> list[RunRecord]:
        """
        Obtém execuções de um job.

        Args:
            job_id: ID do job
            limit: Máximo de registros
            offset: Pular registros
            status: Filtrar por status

        Returns:
            Lista de RunRecord
        """
        with self._get_connection() as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT * FROM runs
                    WHERE job_id = ? AND status = ?
                    ORDER BY started_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (job_id, status.value, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM runs
                    WHERE job_id = ?
                    ORDER BY started_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (job_id, limit, offset),
                ).fetchall()

            return [self._row_to_record(r) for r in rows]

    def get_recent(
        self, limit: int = 50, status: RunStatus | None = None
    ) -> list[RunRecord]:
        """
        Obtém execuções recentes.

        Args:
            limit: Máximo de registros
            status: Filtrar por status

        Returns:
            Lista de RunRecord
        """
        with self._get_connection() as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT * FROM runs
                    WHERE status = ?
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (status.value, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM runs
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            return [self._row_to_record(r) for r in rows]

    def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        job_id: str | None = None,
    ) -> list[RunRecord]:
        """
        Obtém execuções em um período.

        Args:
            start_date: Data inicial
            end_date: Data final
            job_id: Filtrar por job (opcional)

        Returns:
            Lista de RunRecord
        """
        start_iso = dt_to_iso(parse_dt(start_date) or start_date)
        end_iso = dt_to_iso(parse_dt(end_date) or end_date)

        with self._get_connection() as conn:
            if job_id:
                rows = conn.execute(
                    """
                    SELECT * FROM runs
                    WHERE job_id = ? AND started_at BETWEEN ? AND ?
                    ORDER BY started_at DESC
                    """,
                    (job_id, start_iso, end_iso),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM runs
                    WHERE started_at BETWEEN ? AND ?
                    ORDER BY started_at DESC
                    """,
                    (start_iso, end_iso),
                ).fetchall()

            return [self._row_to_record(r) for r in rows]

    def get_stats(self, job_id: str | None = None) -> RunStats:
        """
        Obtém estatísticas de execuções.

        Args:
            job_id: Filtrar por job (opcional)

        Returns:
            RunStats com estatísticas
        """
        with self._get_connection() as conn:
            where = "WHERE job_id = ?" if job_id else ""
            params: tuple[Any, ...] = (job_id,) if job_id else ()

            row = conn.execute(
                f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                    SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) as timeout,
                    AVG(CASE WHEN duration > 0 THEN duration END) as avg_duration,
                    MIN(CASE WHEN duration > 0 THEN duration END) as min_duration,
                    MAX(duration) as max_duration
                FROM runs {where}
                """,
                params,
            ).fetchone()

            stats = RunStats(
                total_runs=int(row["total"] or 0),
                success_count=int(row["success"] or 0),
                failed_count=int(row["failed"] or 0),
                cancelled_count=int(row["cancelled"] or 0),
                timeout_count=int(row["timeout"] or 0),
                avg_duration=float(row["avg_duration"] or 0.0),
                min_duration=float(row["min_duration"] or 0.0),
                max_duration=float(row["max_duration"] or 0.0),
            )

            if stats.total_runs > 0:
                stats.success_rate = stats.success_count / stats.total_runs

            row_last = conn.execute(
                f"SELECT started_at FROM runs {where} ORDER BY started_at DESC LIMIT 1",
                params,
            ).fetchone()
            if row_last:
                stats.last_run = parse_dt(row_last["started_at"])

            where_success = f"{where} {'AND' if where else 'WHERE'} status = 'success'"
            row_s = conn.execute(
                f"SELECT started_at FROM runs {where_success} ORDER BY started_at DESC LIMIT 1",
                params,
            ).fetchone()
            if row_s:
                stats.last_success = parse_dt(row_s["started_at"])

            where_failed = f"{where} {'AND' if where else 'WHERE'} status = 'failed'"
            row_f = conn.execute(
                f"SELECT started_at FROM runs {where_failed} ORDER BY started_at DESC LIMIT 1",
                params,
            ).fetchone()
            if row_f:
                stats.last_failure = parse_dt(row_f["started_at"])

        return stats

    def count(self, job_id: str | None = None, status: RunStatus | None = None) -> int:
        """
        Conta execuções.

        Args:
            job_id: Filtrar por job
            status: Filtrar por status

        Returns:
            Número de execuções
        """
        conditions: list[str] = []
        params: list[Any] = []

        if job_id:
            conditions.append("job_id = ?")
            params.append(job_id)

        if status:
            conditions.append("status = ?")
            params.append(status.value)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self._get_connection() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) as count FROM runs {where}", params
            ).fetchone()
            return int(row["count"] or 0)

    def delete_old(self, days: int = 30) -> int:
        """
        Remove execuções antigas.

        Args:
            days: Manter apenas execuções dos últimos N dias

        Returns:
            Número de registros removidos
        """
        cutoff = utc_now() - timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM runs WHERE started_at < ?", (dt_to_iso(cutoff),)
            )
            conn.commit()

            removed = int(cursor.rowcount or 0)
            if removed > 0:
                logger.info(f"Removidas {removed} execuções antigas (> {days} dias)")

            return removed

    def delete_by_job(self, job_id: str) -> int:
        """
        Remove todas as execuções de um job.

        Args:
            job_id: ID do job

        Returns:
            Número de registros removidos
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM runs WHERE job_id = ?", (job_id,))
            conn.commit()

            removed = int(cursor.rowcount or 0)
            if removed > 0:
                logger.info(f"Removidas {removed} execuções do job {job_id}")

            return removed

    def clear(self) -> int:
        """
        Remove todo o histórico.

        Returns:
            Número de registros removidos
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM runs")
            conn.commit()

            removed = int(cursor.rowcount or 0)
            logger.warning(f"Histórico limpo: {removed} execuções removidas")

            return removed

    def vacuum(self) -> None:
        """
        Otimiza o banco de dados.
        """
        with self._get_connection() as conn:
            conn.execute("VACUUM")
        logger.debug("Banco de dados otimizado")


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "RunStatus",
    "RunRecord",
    "RunStats",
    "RunHistory",
]
