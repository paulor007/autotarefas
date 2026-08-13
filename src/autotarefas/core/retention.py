"""Retencao e expurgo de dados gerenciados no modo real privado.

O servico monta primeiro um plano imutavel. A exclusao so acontece quando
o comando de manutencao confirma esse plano. Arquivos de entrada e artefatos
escolhidos pelo operador nunca sao incluidos automaticamente.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autotarefas.core.audit import AuditTrail


@dataclass(frozen=True)
class PurgePlan:
    """Itens expirados encontrados antes de qualquer exclusao."""

    created_at: datetime
    log_retention_days: int
    screenshot_retention_days: int
    audit_retention_days: int | None
    log_files: tuple[Path, ...]
    screenshot_files: tuple[Path, ...]
    audit_cutoff: datetime | None
    audit_rows: int

    @property
    def total_items(self) -> int:
        """Quantidade total prevista para remocao."""
        return len(self.log_files) + len(self.screenshot_files) + self.audit_rows


@dataclass(frozen=True)
class PurgeResult:
    """Resultado efetivo da exclusao confirmada."""

    removed_logs: int
    removed_screenshots: int
    removed_audit_rows: int
    failed_files: tuple[Path, ...]
    audit_failed: bool

    @property
    def partial(self) -> bool:
        """True quando algum item planejado nao pode ser removido."""
        return bool(self.failed_files) or self.audit_failed


def _managed_log(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith("autotarefas_") and (name.endswith((".log", ".log.zip")))


def _managed_screenshot(path: Path) -> bool:
    return path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}


def _expired_files(
    root: Path,
    cutoff: datetime,
    predicate: Callable[[Path], bool],
) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()

    found: list[Path] = []
    for path in root.rglob("*"):
        try:
            if path.is_symlink() or not path.is_file() or not predicate(path):
                continue
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        except OSError:
            continue

        if modified_at < cutoff:
            found.append(path)

    return tuple(sorted(found, key=lambda item: str(item).casefold()))


def build_purge_plan(  # noqa: PLR0913
    *,
    audit: AuditTrail,
    logs_dir: Path,
    screenshots_dir: Path,
    log_retention_days: int,
    screenshot_retention_days: int,
    audit_retention_days: int | None,
    now: datetime | None = None,
) -> PurgePlan:
    """Identifica exatamente o que esta expirado, sem excluir nada."""
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("now precisa possuir timezone")

    moment = moment.astimezone(UTC)
    log_cutoff = moment - timedelta(days=log_retention_days)
    screenshot_cutoff = moment - timedelta(days=screenshot_retention_days)
    audit_cutoff = (
        moment - timedelta(days=audit_retention_days) if audit_retention_days is not None else None
    )
    audit_rows = audit.count_before(audit_cutoff) if audit_cutoff is not None else 0

    return PurgePlan(
        created_at=moment,
        log_retention_days=log_retention_days,
        screenshot_retention_days=screenshot_retention_days,
        audit_retention_days=audit_retention_days,
        log_files=_expired_files(logs_dir, log_cutoff, _managed_log),
        screenshot_files=_expired_files(
            screenshots_dir,
            screenshot_cutoff,
            _managed_screenshot,
        ),
        audit_cutoff=audit_cutoff,
        audit_rows=audit_rows,
    )


def _remove_files(paths: tuple[Path, ...]) -> tuple[int, tuple[Path, ...]]:
    removed = 0
    failed: list[Path] = []

    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            failed.append(path)
        else:
            removed += 1

    return removed, tuple(failed)


def execute_purge(plan: PurgePlan, *, audit: AuditTrail) -> PurgeResult:
    """Executa um plano confirmado e registra o resultado no audit."""
    started_at = datetime.now(UTC)
    started = time.monotonic()

    removed_logs, failed_logs = _remove_files(plan.log_files)
    removed_screenshots, failed_screenshots = _remove_files(plan.screenshot_files)

    removed_audit_rows = 0
    audit_failed = False
    if plan.audit_cutoff is not None:
        try:
            removed_audit_rows = audit.purge_before(plan.audit_cutoff)
        except (OSError, sqlite3.Error):
            audit_failed = True

    failed_files = failed_logs + failed_screenshots
    status = "partial" if failed_files or audit_failed else "success"
    duration_ms = max(0, int((time.monotonic() - started) * 1000))

    audit.record(
        task_name="manutencao.expurgar",
        status=status,
        started_at=started_at,
        duration_ms=duration_ms,
        rows_affected=(removed_logs + removed_screenshots + removed_audit_rows),
        rows_failed=len(failed_files) + int(audit_failed),
        args={
            "log_retention_days": plan.log_retention_days,
            "screenshot_retention_days": plan.screenshot_retention_days,
            "audit_retention_days": plan.audit_retention_days,
            "logs_removed": removed_logs,
            "screenshots_removed": removed_screenshots,
            "audit_rows_removed": removed_audit_rows,
            "file_failures": len(failed_files),
            "audit_failure": audit_failed,
        },
    )

    return PurgeResult(
        removed_logs=removed_logs,
        removed_screenshots=removed_screenshots,
        removed_audit_rows=removed_audit_rows,
        failed_files=failed_files,
        audit_failed=audit_failed,
    )


__all__ = [
    "PurgePlan",
    "PurgeResult",
    "build_purge_plan",
    "execute_purge",
]
