"""Registro em memoria dos jobs de execucao (Live-1.3).

Cada POST /api/run cria um Job com uma fila de linhas (stdout ao vivo) e o
resultado consolidado. O registro e efemero por design: reiniciar o servidor
zera tudo, e os jobs expiram junto com o TTL do workspace.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import RunResult


def _new_queue() -> asyncio.Queue[str | None]:
    """Fila de linhas do stdout; o sentinela None marca o fim do stream."""
    return asyncio.Queue()


@dataclass
class Job:
    """Estado de uma execucao em andamento ou concluida."""

    token: str
    automation_id: str
    workspace: Path
    status: str = "running"  # running | ok | caught_issue | error | timeout
    created_at: float = field(default_factory=time.time)
    queue: asyncio.Queue[str | None] = field(default_factory=_new_queue)
    lines: list[str] = field(default_factory=list)
    result: RunResult | None = None


_jobs: dict[str, Job] = {}


def create(token: str, automation_id: str, workspace: Path) -> Job:
    """Registra um novo job e o devolve."""
    job = Job(token=token, automation_id=automation_id, workspace=workspace)
    _jobs[token] = job
    return job


def get(token: str) -> Job | None:
    """Recupera um job pelo token (None se nao existir)."""
    return _jobs.get(token)


def active_count() -> int:
    """Quantos jobs ainda estao executando."""
    return sum(1 for job in _jobs.values() if job.status == "running")


def sweep_expired(ttl_min: int) -> int:
    """Remove jobs mais velhos que o TTL. Retorna quantos sairam."""
    ttl_seconds = ttl_min * 60
    now = time.time()
    expired = [token for token, job in _jobs.items() if now - job.created_at > ttl_seconds]
    for token in expired:
        _jobs.pop(token, None)
    return len(expired)
