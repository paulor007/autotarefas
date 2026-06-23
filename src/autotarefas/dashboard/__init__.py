"""
Dashboard local do AutoTarefas (visualizacao do audit trail).

Subetapa 1: camada de leitura (``reader``).
Subetapa 2: renderizacao HTML estatica (``renderer``).
Sem servidor e sem dependencias novas — a base do dashboard visual.
"""

from __future__ import annotations

from .reader import (
    AuditEntry,
    AuditSummary,
    read_entries,
    summarize,
    verify_input_hash,
)
from .renderer import render_dashboard

__all__ = [
    "AuditEntry",
    "AuditSummary",
    "read_entries",
    "render_dashboard",
    "summarize",
    "verify_input_hash",
]
