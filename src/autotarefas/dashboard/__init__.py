"""
Dashboard local do AutoTarefas (visualizacao do audit trail).

Subetapa 1: apenas a camada de leitura (``reader``). Sem HTML, sem
servidor e sem dependencias novas — a base sobre a qual o dashboard
visual sera construido nas proximas subetapas.
"""

from __future__ import annotations

from .reader import (
    AuditEntry,
    AuditSummary,
    read_entries,
    summarize,
    verify_input_hash,
)

__all__ = [
    "AuditEntry",
    "AuditSummary",
    "read_entries",
    "summarize",
    "verify_input_hash",
]
