from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def brl(value: float) -> str:
    """Formata moeda em BRL no estilo 'R$ 1.234,56' (sem depender de locale)."""
    s = f"{value:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def safe_int(value: Any, default: int = 0) -> int:
    """Converte para int com fallback seguro."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Converte para float com fallback seguro."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_iso_dt(value: str | None) -> datetime | None:
    """Tenta parsear data ISO (YYYY-MM-DD ou ISO datetime). Retorna timezone-aware em UTC quando possível."""
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None

    # normaliza para UTC (se vier naive, assume UTC)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
