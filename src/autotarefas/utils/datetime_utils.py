"""
Utilitários de data/hora do AutoTarefas.

Centraliza funções repetidas para:
- UTC timezone-aware
- serialização ISO8601
- parsing robusto
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# ✅ PADRÃO: um único "UTC" do projeto inteiro
UTC = UTC


def utc_now() -> datetime:
    """Retorna datetime timezone-aware em UTC."""
    return datetime.now(UTC)


def dt_to_iso(dt: datetime | None) -> str | None:
    """Serializa datetime para ISO8601 (mantendo/forçando UTC)."""
    if dt is None:
        return None

    # ✅ garante timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    return dt.isoformat()


def parse_dt(value: Any) -> datetime | None:
    """
    Converte string ISO8601 (ou datetime) para datetime timezone-aware em UTC.
    Aceita None.
    """
    if not value:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    if isinstance(value, str):
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)

    raise ValueError(f"Formato inválido para datetime: {type(value)!r}")
