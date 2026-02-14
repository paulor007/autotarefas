"""
Módulo de Persistência do AutoTarefas.

Fornece armazenamento para jobs agendados e histórico de execuções:
    - JobStore: Persistência de jobs em JSON
    - RunHistory: Histórico de execuções em SQLite

Uso:
    from autotarefas.core.storage import JobStore, Job, JobStatus
    from autotarefas.core.storage import RunHistory, RunRecord, RunStatus

    # Jobs
    store = JobStore()
    job = store.create("backup_diario", "backup", "0 2 * * *")
    store.save(job)

    # Histórico
    history = RunHistory()
    record = history.start_run("job123", "backup_diario", "backup")
    history.finish_run(record.id, RunStatus.SUCCESS, duration=45.2)
"""

from autotarefas.core.storage.job_store import Job, JobStatus, JobStore
from autotarefas.core.storage.run_history import (
    RunHistory,
    RunRecord,
    RunStats,
    RunStatus,
)

__all__ = [
    # Job Store
    "JobStore",
    "Job",
    "JobStatus",
    # Run History
    "RunHistory",
    "RunRecord",
    "RunStats",
    "RunStatus",
]
