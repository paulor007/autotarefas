"""
Testes do módulo de histórico de execuções (run_history).

Testa:
    - RunStatus: Estados de uma execução
    - RunRecord: Representação de uma execução
    - RunStats: Estatísticas agregadas
    - RunHistory: Gerenciador de histórico em SQLite

O módulo run_history é responsável por REGISTRAR todas as execuções de jobs
em um banco SQLite, permitindo auditoria, análise e estatísticas de performance.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

# ============================================================================
# Testes de RunStatus
# ============================================================================


class TestRunStatus:
    """Testes do enum RunStatus."""

    def test_status_values(self) -> None:
        """Deve ter todos os status esperados."""
        from autotarefas.core.storage.run_history import RunStatus

        assert RunStatus.PENDING.value == "pending"
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.SUCCESS.value == "success"
        assert RunStatus.FAILED.value == "failed"
        assert RunStatus.CANCELLED.value == "cancelled"
        assert RunStatus.TIMEOUT.value == "timeout"
        assert RunStatus.SKIPPED.value == "skipped"

    def test_status_from_string(self) -> None:
        """Deve converter string para enum."""
        from autotarefas.core.storage.run_history import RunStatus

        assert RunStatus("success") == RunStatus.SUCCESS
        assert RunStatus("failed") == RunStatus.FAILED
        assert RunStatus("running") == RunStatus.RUNNING

    def test_status_invalid_value(self) -> None:
        """Deve falhar com valor inválido."""
        from autotarefas.core.storage.run_history import RunStatus

        with pytest.raises(ValueError):
            RunStatus("invalid_status")


# ============================================================================
# Testes de RunRecord
# ============================================================================


class TestRunRecord:
    """Testes da dataclass RunRecord."""

    def test_record_creation_minimal(self) -> None:
        """Deve criar registro com campos mínimos."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        record = RunRecord(
            id="run-123",
            job_id="job-456",
            job_name="backup_diario",
            task="backup",
        )

        assert record.id == "run-123"
        assert record.job_id == "job-456"
        assert record.job_name == "backup_diario"
        assert record.task == "backup"
        assert record.status == RunStatus.PENDING

    def test_record_creation_full(self) -> None:
        """Deve criar registro com todos os campos."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        record = RunRecord(
            id="run-full",
            job_id="job-789",
            job_name="limpeza",
            task="cleaner",
            status=RunStatus.SUCCESS,
            duration=45.5,
            error=None,
            output="Cleaned 100 files",
            params={"path": "/tmp"},
            trigger="manual",
            retry_count=0,
            metadata={"user": "admin"},
        )

        assert record.status == RunStatus.SUCCESS
        assert record.duration == 45.5
        assert record.output == "Cleaned 100 files"
        assert record.params["path"] == "/tmp"
        assert record.trigger == "manual"

    def test_record_defaults(self) -> None:
        """Deve ter valores padrão corretos."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        record = RunRecord(id="t", job_id="j", job_name="n", task="t")

        assert record.status == RunStatus.PENDING
        assert record.duration == 0.0
        assert record.error is None
        assert record.output is None
        assert record.params == {}
        assert record.trigger == "scheduled"
        assert record.retry_count == 0
        assert record.metadata == {}

    def test_record_status_from_string(self) -> None:
        """Deve aceitar status como string e converter para enum."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        record = RunRecord(
            id="t",
            job_id="j",
            job_name="n",
            task="t",
            status="running",  # type: ignore
        )

        assert record.status == RunStatus.RUNNING

    def test_record_timestamps_auto_set(self) -> None:
        """started_at deve ser definido automaticamente."""
        from autotarefas.core.storage.run_history import RunRecord

        record = RunRecord(id="t", job_id="j", job_name="n", task="t")

        assert record.started_at is not None
        assert isinstance(record.started_at, datetime)


class TestRunRecordProperties:
    """Testes das propriedades de RunRecord."""

    def test_is_finished_pending(self) -> None:
        """PENDING não é finalizado."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        record = RunRecord(
            id="t", job_id="j", job_name="n", task="t", status=RunStatus.PENDING
        )
        assert record.is_finished is False

    def test_is_finished_running(self) -> None:
        """RUNNING não é finalizado."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        record = RunRecord(
            id="t", job_id="j", job_name="n", task="t", status=RunStatus.RUNNING
        )
        assert record.is_finished is False

    def test_is_finished_success(self) -> None:
        """SUCCESS é finalizado."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        record = RunRecord(
            id="t", job_id="j", job_name="n", task="t", status=RunStatus.SUCCESS
        )
        assert record.is_finished is True

    def test_is_finished_failed(self) -> None:
        """FAILED é finalizado."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        record = RunRecord(
            id="t", job_id="j", job_name="n", task="t", status=RunStatus.FAILED
        )
        assert record.is_finished is True

    def test_is_success_true(self) -> None:
        """is_success deve ser True para SUCCESS."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        record = RunRecord(
            id="t", job_id="j", job_name="n", task="t", status=RunStatus.SUCCESS
        )
        assert record.is_success is True

    def test_is_success_false(self) -> None:
        """is_success deve ser False para outros status."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        record = RunRecord(
            id="t", job_id="j", job_name="n", task="t", status=RunStatus.FAILED
        )
        assert record.is_success is False


class TestRunRecordSerialization:
    """Testes de to_dict e from_dict."""

    def test_to_dict(self) -> None:
        """to_dict deve retornar dicionário serializável."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        record = RunRecord(
            id="serial-123",
            job_id="job-456",
            job_name="backup",
            task="backup",
            status=RunStatus.SUCCESS,
            duration=30.5,
            params={"source": "/data"},
            metadata={"version": "1.0"},
        )

        data = record.to_dict()

        assert isinstance(data, dict)
        assert data["id"] == "serial-123"
        assert data["status"] == "success"
        assert data["duration"] == 30.5
        assert data["params"] == {"source": "/data"}

    def test_from_dict(self) -> None:
        """from_dict deve recriar registro."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        data = {
            "id": "from-dict-123",
            "job_id": "job-789",
            "job_name": "monitor",
            "task": "monitor",
            "status": "failed",
            "duration": 15.0,
            "error": "Connection timeout",
            "retry_count": 2,
        }

        record = RunRecord.from_dict(data)

        assert record.id == "from-dict-123"
        assert record.status == RunStatus.FAILED
        assert record.error == "Connection timeout"
        assert record.retry_count == 2

    def test_roundtrip(self) -> None:
        """to_dict -> from_dict deve preservar dados."""
        from autotarefas.core.storage.run_history import RunRecord, RunStatus

        original = RunRecord(
            id="roundtrip",
            job_id="job-rt",
            job_name="relatorio",
            task="reporter",
            status=RunStatus.SUCCESS,
            duration=120.0,
            output="Report generated",
            params={"format": "pdf"},
        )

        data = original.to_dict()
        restored = RunRecord.from_dict(data)

        assert restored.id == original.id
        assert restored.job_name == original.job_name
        assert restored.status == original.status
        assert restored.duration == original.duration


# ============================================================================
# Testes de RunStats
# ============================================================================


class TestRunStats:
    """Testes da dataclass RunStats."""

    def test_stats_defaults(self) -> None:
        """Deve ter defaults zerados."""
        from autotarefas.core.storage.run_history import RunStats

        stats = RunStats()

        assert stats.total_runs == 0
        assert stats.success_count == 0
        assert stats.failed_count == 0
        assert stats.success_rate == 0.0
        assert stats.avg_duration == 0.0

    def test_stats_with_values(self) -> None:
        """Deve aceitar valores."""
        from autotarefas.core.storage.run_history import RunStats

        stats = RunStats(
            total_runs=100,
            success_count=85,
            failed_count=15,
            success_rate=0.85,
            avg_duration=45.5,
            min_duration=10.0,
            max_duration=120.0,
        )

        assert stats.total_runs == 100
        assert stats.success_rate == 0.85


# ============================================================================
# Testes de RunHistory
# ============================================================================


class TestRunHistory:
    """Testes da classe RunHistory."""

    def test_history_creation(self, temp_dir: Path) -> None:
        """Deve criar histórico com banco."""
        from autotarefas.core.storage.run_history import RunHistory

        db_path = temp_dir / "test_history.db"
        history = RunHistory(db_path)

        assert history is not None
        assert history.db_path == db_path
        assert db_path.exists()

    def test_history_creates_table(self, temp_dir: Path) -> None:
        """Deve criar tabela runs no banco."""
        import sqlite3

        from autotarefas.core.storage.run_history import RunHistory

        db_path = temp_dir / "table_test.db"
        RunHistory(db_path)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
        )
        table = cursor.fetchone()
        conn.close()

        assert table is not None
        assert table[0] == "runs"


class TestRunHistoryStartFinish:
    """Testes de start_run e finish_run."""

    def test_start_run(self, temp_dir: Path) -> None:
        """start_run deve criar registro RUNNING."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "start_test.db")

        record = history.start_run(
            job_id="job-123",
            job_name="backup_diario",
            task="backup",
            params={"source": "/data"},
        )

        assert record.id is not None
        assert record.job_id == "job-123"
        assert record.status == RunStatus.RUNNING
        assert record.params["source"] == "/data"

    def test_start_run_with_trigger(self, temp_dir: Path) -> None:
        """start_run deve aceitar trigger."""
        from autotarefas.core.storage.run_history import RunHistory

        history = RunHistory(temp_dir / "trigger_test.db")

        record = history.start_run(
            job_id="j",
            job_name="n",
            task="t",
            trigger="manual",
        )

        assert record.trigger == "manual"

    def test_start_run_with_retry(self, temp_dir: Path) -> None:
        """start_run deve aceitar retry_count."""
        from autotarefas.core.storage.run_history import RunHistory

        history = RunHistory(temp_dir / "retry_test.db")

        record = history.start_run(
            job_id="j",
            job_name="n",
            task="t",
            retry_count=2,
        )

        assert record.retry_count == 2

    def test_finish_run_success(self, temp_dir: Path) -> None:
        """finish_run deve atualizar para SUCCESS."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "finish_success.db")

        record = history.start_run(job_id="j", job_name="n", task="t")
        result = history.finish_run(record.id, RunStatus.SUCCESS, duration=30.5)

        assert result is True

        updated = history.get(record.id)
        assert updated is not None
        assert updated.status == RunStatus.SUCCESS
        assert updated.duration == 30.5
        assert updated.finished_at is not None

    def test_finish_run_failed(self, temp_dir: Path) -> None:
        """finish_run deve atualizar para FAILED com erro."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "finish_failed.db")

        record = history.start_run(job_id="j", job_name="n", task="t")
        result = history.finish_run(
            record.id,
            RunStatus.FAILED,
            duration=5.0,
            error="Connection timeout",
        )

        assert result is True

        updated = history.get(record.id)
        assert updated is not None
        assert updated.status == RunStatus.FAILED
        assert updated.error == "Connection timeout"

    def test_finish_run_with_output(self, temp_dir: Path) -> None:
        """finish_run deve aceitar output."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "finish_output.db")

        record = history.start_run(job_id="j", job_name="n", task="t")
        history.finish_run(record.id, RunStatus.SUCCESS, output="Processed 100 files")

        updated = history.get(record.id)
        assert updated is not None
        assert updated.output == "Processed 100 files"

    def test_finish_run_nonexistent(self, temp_dir: Path) -> None:
        """finish_run deve retornar False para ID inexistente."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "finish_nonexistent.db")

        result = history.finish_run("fake-id", RunStatus.SUCCESS)
        assert result is False


class TestRunHistoryGet:
    """Testes de métodos get."""

    def test_get_existing(self, temp_dir: Path) -> None:
        """get deve retornar registro existente."""
        from autotarefas.core.storage.run_history import RunHistory

        history = RunHistory(temp_dir / "get_test.db")

        record = history.start_run(job_id="j", job_name="n", task="t")
        retrieved = history.get(record.id)

        assert retrieved is not None
        assert retrieved.id == record.id

    def test_get_nonexistent(self, temp_dir: Path) -> None:
        """get deve retornar None para ID inexistente."""
        from autotarefas.core.storage.run_history import RunHistory

        history = RunHistory(temp_dir / "get_none.db")

        result = history.get("nonexistent-id")
        assert result is None

    def test_get_by_job(self, temp_dir: Path) -> None:
        """get_by_job deve retornar execuções do job."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "get_by_job.db")

        # Criar execuções de dois jobs
        for _ in range(3):
            r = history.start_run(job_id="job-A", job_name="Job A", task="backup")
            history.finish_run(r.id, RunStatus.SUCCESS)

        for _ in range(2):
            r = history.start_run(job_id="job-B", job_name="Job B", task="cleaner")
            history.finish_run(r.id, RunStatus.SUCCESS)

        runs_a = history.get_by_job("job-A")
        runs_b = history.get_by_job("job-B")

        assert len(runs_a) == 3
        assert len(runs_b) == 2
        assert all(r.job_id == "job-A" for r in runs_a)

    def test_get_by_job_with_status_filter(self, temp_dir: Path) -> None:
        """get_by_job deve filtrar por status."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "get_by_job_status.db")

        r1 = history.start_run(job_id="j", job_name="n", task="t")
        history.finish_run(r1.id, RunStatus.SUCCESS)

        r2 = history.start_run(job_id="j", job_name="n", task="t")
        history.finish_run(r2.id, RunStatus.FAILED)

        success_runs = history.get_by_job("j", status=RunStatus.SUCCESS)
        failed_runs = history.get_by_job("j", status=RunStatus.FAILED)

        assert len(success_runs) == 1
        assert len(failed_runs) == 1

    def test_get_by_job_with_limit(self, temp_dir: Path) -> None:
        """get_by_job deve respeitar limit."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "get_limit.db")

        for _ in range(10):
            r = history.start_run(job_id="j", job_name="n", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS)

        runs = history.get_by_job("j", limit=5)
        assert len(runs) == 5

    def test_get_recent(self, temp_dir: Path) -> None:
        """get_recent deve retornar execuções recentes."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "get_recent.db")

        for i in range(5):
            r = history.start_run(job_id=f"job-{i}", job_name=f"Job {i}", task="backup")
            history.finish_run(r.id, RunStatus.SUCCESS)

        recent = history.get_recent(limit=3)
        assert len(recent) == 3

    def test_get_recent_with_status(self, temp_dir: Path) -> None:
        """get_recent deve filtrar por status."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "get_recent_status.db")

        r1 = history.start_run(job_id="j", job_name="n", task="t")
        history.finish_run(r1.id, RunStatus.SUCCESS)

        r2 = history.start_run(job_id="j", job_name="n", task="t")
        history.finish_run(r2.id, RunStatus.FAILED)

        failed = history.get_recent(status=RunStatus.FAILED)
        assert len(failed) == 1
        assert failed[0].status == RunStatus.FAILED


class TestRunHistoryDateRange:
    """Testes de get_by_date_range."""

    def test_get_by_date_range(self, temp_dir: Path) -> None:
        """get_by_date_range deve filtrar por período."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "date_range.db")

        # Criar algumas execuções
        for _ in range(5):
            r = history.start_run(job_id="j", job_name="n", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS)

        now = datetime.now(UTC)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        runs = history.get_by_date_range(start, end)
        assert len(runs) == 5

    def test_get_by_date_range_empty(self, temp_dir: Path) -> None:
        """get_by_date_range deve retornar vazio fora do período."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "date_range_empty.db")

        r = history.start_run(job_id="j", job_name="n", task="t")
        history.finish_run(r.id, RunStatus.SUCCESS)

        # Período no passado distante
        start = datetime(2020, 1, 1, tzinfo=UTC)
        end = datetime(2020, 1, 2, tzinfo=UTC)

        runs = history.get_by_date_range(start, end)
        assert len(runs) == 0


class TestRunHistoryStats:
    """Testes de get_stats."""

    def test_get_stats_empty(self, temp_dir: Path) -> None:
        """get_stats em histórico vazio deve ter zeros."""
        from autotarefas.core.storage.run_history import RunHistory

        history = RunHistory(temp_dir / "stats_empty.db")

        stats = history.get_stats()

        assert stats.total_runs == 0
        assert stats.success_rate == 0.0

    def test_get_stats_with_data(self, temp_dir: Path) -> None:
        """get_stats deve calcular estatísticas corretas."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "stats_data.db")

        # 7 sucessos, 3 falhas
        for _ in range(7):
            r = history.start_run(job_id="j", job_name="n", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS, duration=10.0)

        for _ in range(3):
            r = history.start_run(job_id="j", job_name="n", task="t")
            history.finish_run(r.id, RunStatus.FAILED, duration=5.0)

        stats = history.get_stats()

        assert stats.total_runs == 10
        assert stats.success_count == 7
        assert stats.failed_count == 3
        assert stats.success_rate == 0.7

    def test_get_stats_by_job(self, temp_dir: Path) -> None:
        """get_stats deve filtrar por job_id."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "stats_job.db")

        # Job A: 5 execuções
        for _ in range(5):
            r = history.start_run(job_id="job-A", job_name="A", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS)

        # Job B: 3 execuções
        for _ in range(3):
            r = history.start_run(job_id="job-B", job_name="B", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS)

        stats_a = history.get_stats(job_id="job-A")
        stats_b = history.get_stats(job_id="job-B")

        assert stats_a.total_runs == 5
        assert stats_b.total_runs == 3

    def test_get_stats_duration(self, temp_dir: Path) -> None:
        """get_stats deve calcular métricas de duração."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "stats_duration.db")

        durations = [10.0, 20.0, 30.0, 40.0, 50.0]
        for d in durations:
            r = history.start_run(job_id="j", job_name="n", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS, duration=d)

        stats = history.get_stats()

        assert stats.min_duration == 10.0
        assert stats.max_duration == 50.0
        assert stats.avg_duration == 30.0


class TestRunHistoryCount:
    """Testes de count."""

    def test_count_all(self, temp_dir: Path) -> None:
        """count deve contar todas as execuções."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "count_all.db")

        for _ in range(5):
            r = history.start_run(job_id="j", job_name="n", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS)

        assert history.count() == 5

    def test_count_by_job(self, temp_dir: Path) -> None:
        """count deve filtrar por job_id."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "count_job.db")

        for _ in range(3):
            r = history.start_run(job_id="job-A", job_name="A", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS)

        for _ in range(2):
            r = history.start_run(job_id="job-B", job_name="B", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS)

        assert history.count(job_id="job-A") == 3
        assert history.count(job_id="job-B") == 2

    def test_count_by_status(self, temp_dir: Path) -> None:
        """count deve filtrar por status."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "count_status.db")

        for _ in range(4):
            r = history.start_run(job_id="j", job_name="n", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS)

        for _ in range(2):
            r = history.start_run(job_id="j", job_name="n", task="t")
            history.finish_run(r.id, RunStatus.FAILED)

        assert history.count(status=RunStatus.SUCCESS) == 4
        assert history.count(status=RunStatus.FAILED) == 2


class TestRunHistoryDelete:
    """Testes de delete_old, delete_by_job e clear."""

    def test_delete_by_job(self, temp_dir: Path) -> None:
        """delete_by_job deve remover execuções do job."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "delete_job.db")

        for _ in range(5):
            r = history.start_run(job_id="job-A", job_name="A", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS)

        for _ in range(3):
            r = history.start_run(job_id="job-B", job_name="B", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS)

        removed = history.delete_by_job("job-A")

        assert removed == 5
        assert history.count(job_id="job-A") == 0
        assert history.count(job_id="job-B") == 3

    def test_clear(self, temp_dir: Path) -> None:
        """clear deve remover todo o histórico."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "clear.db")

        for _ in range(10):
            r = history.start_run(job_id="j", job_name="n", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS)

        removed = history.clear()

        assert removed == 10
        assert history.count() == 0


class TestRunHistoryEdgeCases:
    """Testes de casos extremos."""

    def test_unicode_in_fields(self, temp_dir: Path) -> None:
        """Deve tratar caracteres especiais."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "unicode.db")

        record = history.start_run(
            job_id="job-ação",
            job_name="Relatório_日本語",
            task="backup",
            params={"descrição": "Conteúdo com ção, ñ, ü"},
        )
        history.finish_run(record.id, RunStatus.SUCCESS, output="Processado: ação")

        retrieved = history.get(record.id)
        assert retrieved is not None
        assert "ação" in retrieved.job_id
        assert "ção" in retrieved.params["descrição"]

    def test_large_output(self, temp_dir: Path) -> None:
        """Deve tratar output grande."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "large_output.db")

        large_output = "x" * 100000  # 100KB

        record = history.start_run(job_id="j", job_name="n", task="t")
        history.finish_run(record.id, RunStatus.SUCCESS, output=large_output)

        retrieved = history.get(record.id)
        assert retrieved is not None
        assert len(retrieved.output or "") == 100000

    def test_concurrent_writes(self, temp_dir: Path) -> None:
        """Deve suportar múltiplas escritas."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        db_path = temp_dir / "concurrent.db"

        # Simular escritas de múltiplas instâncias
        h1 = RunHistory(db_path)
        h2 = RunHistory(db_path)

        r1 = h1.start_run(job_id="j1", job_name="n1", task="t")
        r2 = h2.start_run(job_id="j2", job_name="n2", task="t")

        h1.finish_run(r1.id, RunStatus.SUCCESS)
        h2.finish_run(r2.id, RunStatus.SUCCESS)

        # Verificar que ambos foram salvos
        h3 = RunHistory(db_path)
        assert h3.count() == 2

    def test_vacuum(self, temp_dir: Path) -> None:
        """vacuum deve otimizar o banco."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(temp_dir / "vacuum.db")

        # Criar e deletar registros
        for _ in range(100):
            r = history.start_run(job_id="j", job_name="n", task="t")
            history.finish_run(r.id, RunStatus.SUCCESS)

        history.clear()

        # Não deve explodir
        history.vacuum()
        assert history.count() == 0
