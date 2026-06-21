"""
Camada de leitura do audit trail para o dashboard (somente leitura).

Esta e a BASE do dashboard: le as execucoes registradas no audit
(reusando ``audit.query()``), devolve-as de forma estruturada e tipada
(``AuditEntry``), resume por status (``AuditSummary``) e oferece a
verificacao do input_hash registrado (``verify_input_hash``).

NAO toca o nucleo: nao altera ``audit.py``, ``base.py`` nem as tasks.
Apenas le, atraves da API publica ``audit.query()``.

Sobre integridade: o audit registra o HMAC-SHA256 do INPUT da task
(o campo ``input_hash``) — e NAO uma assinatura da linha inteira.
Portanto, ``verify_input_hash`` confirma que um input fornecido
corresponde ao que foi registrado; ela nao detecta edicao manual da
linha no banco (isso exigiria evoluir o audit com assinatura por linha).

Destino deste arquivo:
    src/autotarefas/dashboard/reader.py
"""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from autotarefas.core.audit import audit
from autotarefas.core.security import hash_string
from autotarefas.core.settings import settings

if TYPE_CHECKING:
    from collections.abc import Sequence


# ============================================================
# Estruturas de dados
# ============================================================


@dataclass(frozen=True)
class AuditEntry:
    """Uma execucao registrada no audit trail (somente leitura)."""

    task_name: str
    status: str
    timestamp: datetime | None
    duration_ms: int | None
    rows_affected: int
    rows_failed: int
    error_message: str | None
    user: str
    environment: str
    input_hash: str


@dataclass(frozen=True)
class AuditSummary:
    """Resumo agregado de um conjunto de execucoes."""

    total: int
    by_status: dict[str, int]


# ============================================================
# Conversao defensiva (linha do banco -> AuditEntry)
# ============================================================


def _parse_timestamp(value: Any) -> datetime | None:
    """Converte o timestamp ISO do audit em datetime (None se invalido)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _to_int(value: Any, default: int = 0) -> int:
    """Converte para int de forma defensiva (campos podem vir None)."""
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _row_to_entry(row: dict[str, Any]) -> AuditEntry:
    """Converte uma linha (dict de ``audit.query``) em ``AuditEntry``."""
    duration = row.get("duration_ms")
    return AuditEntry(
        task_name=str(row.get("task_name", "")),
        status=str(row.get("status", "")),
        timestamp=_parse_timestamp(row.get("timestamp")),
        duration_ms=duration if isinstance(duration, int) else None,
        rows_affected=_to_int(row.get("rows_affected")),
        rows_failed=_to_int(row.get("rows_failed")),
        error_message=row.get("error_message"),
        user=str(row.get("user", "")),
        environment=str(row.get("environment", "")),
        input_hash=str(row.get("input_hash", "")),
    )


# ============================================================
# API publica de leitura
# ============================================================


def read_entries(
    *,
    task_name: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[AuditEntry]:
    """
    Le execucoes do audit (read-only), mais recentes primeiro.

    Reusa ``audit.query()``; se o banco nao existir ou estiver
    indisponivel, ``audit.query`` devolve ``[]`` e esta funcao tambem.

    Args:
        task_name: filtra por nome de task.
        status: filtra por status.
        limit: maximo de execucoes (default 100).
    """
    rows = audit.query(task_name=task_name, status=status, limit=limit)
    return [_row_to_entry(row) for row in rows]


def summarize(entries: Sequence[AuditEntry]) -> AuditSummary:
    """Resume execucoes: total e contagem por status."""
    by_status: dict[str, int] = {}
    for entry in entries:
        by_status[entry.status] = by_status.get(entry.status, 0) + 1
    return AuditSummary(total=len(entries), by_status=by_status)


def verify_input_hash(entry: AuditEntry, input_data: Any) -> bool:
    """
    Confirma se ``input_data`` corresponde ao ``input_hash`` registrado.

    Recalcula o HMAC-SHA256 (mesma chave do audit) sobre ``input_data`` e
    compara, em tempo constante, com ``entry.input_hash``.

    Retorna ``False`` se a entrada nao tem ``input_hash``. Veja a nota do
    modulo: isto verifica o INPUT, nao a integridade da linha de auditoria.
    """
    if not entry.input_hash:
        return False
    secret = settings.audit_secret_key.get_secret_value()
    data_str = (
        input_data
        if isinstance(input_data, str)
        else json.dumps(input_data, default=str, sort_keys=True)
    )
    expected = hash_string(data_str, secret)
    return hmac.compare_digest(expected, entry.input_hash)


__all__ = [
    "AuditEntry",
    "AuditSummary",
    "read_entries",
    "summarize",
    "verify_input_hash",
]
