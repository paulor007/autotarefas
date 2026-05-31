"""
Sistema de Audit Trail do AutoTarefas (SQLite local).

Registra TODA execução de task em um banco SQLite append-only. Cada
entrada inclui timestamp, task_name, usuário, status, duração e dados
agregados. Senhas e dados sensíveis NUNCA vão pro audit — apenas hash
HMAC-SHA256 do input.

Uso:
    from autotarefas.core.audit import audit
    from datetime import UTC, datetime

    audit.record(
        task_name="validate",
        status="success",
        started_at=datetime.now(UTC),
        duration_ms=1234,
        rows_affected=42,
    )

    # Consulta
    entries = audit.query(task_name="validate", limit=10)
    for entry in entries:
        print(entry["timestamp"], entry["status"])

Princípios:
- **Append-only** — nunca UPDATE ou DELETE
- **Falhas não propagam** — audit é "best effort", task continua
- **Sem dados sensíveis** — só hash de input
- **Imutável por design** — histórico real
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from autotarefas.core.logger import logger
from autotarefas.core.settings import settings

# ============================================================
# Schema SQL
# ============================================================

CREATE_AUDIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    task_name TEXT NOT NULL,
    user TEXT NOT NULL,
    input_hash TEXT NOT NULL DEFAULT '',
    args TEXT,
    status TEXT NOT NULL,
    duration_ms INTEGER,
    rows_affected INTEGER DEFAULT 0,
    rows_failed INTEGER DEFAULT 0,
    error_message TEXT,
    environment TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_task ON audit(task_name);
CREATE INDEX IF NOT EXISTS idx_audit_status ON audit(status);
"""


# ============================================================
# Helpers privados
# ============================================================


def _get_current_user() -> str:
    """Retorna o usuário do SO. ``'unknown'`` se não achar."""
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def _hash_input(data: Any, secret: str | None = None) -> str:
    """
    Calcula hash do input pra audit trail.

    Args:
        data: Dado a ser hasheado (qualquer tipo serializável).
        secret: Chave HMAC opcional. Se None/vazio, usa SHA-256 puro.

    Returns:
        Hash hexadecimal (64 caracteres).
        Retorna string vazia se ``data`` for None.
    """
    if data is None:
        return ""

    # Ternário substitui if/else (SIM108)
    data_str = data if isinstance(data, str) else json.dumps(data, default=str, sort_keys=True)

    # Cada branch retorna direto — evita conflito de tipos HMAC vs HASH
    if secret:
        return hmac.new(
            secret.encode("utf-8"),
            data_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    return hashlib.sha256(data_str.encode("utf-8")).hexdigest()


# ============================================================
# AuditTrail
# ============================================================


class AuditTrail:
    """
    Sistema de audit trail em SQLite.

    - **Append-only**: nunca UPDATE ou DELETE.
    - **Falhas não propagam**: erros gravam warning no log, não interrompem
      a task que estava sendo auditada.
    - **Sem dados sensíveis**: só hash HMAC-SHA256 do input.
    - **Conexões fechadas corretamente**: usa ``contextlib.closing()`` em
      todos os ``sqlite3.connect()`` (o ``with`` do sqlite3 NÃO fecha
      automaticamente — só faz commit/rollback).

    Pra uso normal, importe a instância global ``audit``:

        from autotarefas.core.audit import audit

        audit.record(task_name="...", status="success", ...)
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Inicializa AuditTrail.

        Args:
            db_path: Caminho do SQLite. Default: ``settings.audit_db_path``.
        """
        self.db_path = db_path if db_path is not None else settings.audit_db_path
        self._init_db()

    def _init_db(self) -> None:
        """Cria tabela e índices se ainda não existirem."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.db_path)) as conn:
                conn.executescript(CREATE_AUDIT_TABLE_SQL)
                conn.commit()
        except (sqlite3.Error, OSError) as e:
            logger.warning(
                "Falha ao inicializar audit DB em '{path}': {err}",
                path=str(self.db_path),
                err=str(e),
            )

    def record(  # noqa: PLR0913
        self,
        *,
        task_name: str,
        status: str,
        started_at: datetime,
        duration_ms: int,
        rows_affected: int = 0,
        rows_failed: int = 0,
        error_message: str | None = None,
        args: dict[str, Any] | None = None,
        input_data: Any = None,
        user: str | None = None,
    ) -> None:
        """
        Registra execução de uma task no audit DB.

        **Esse método NUNCA propaga exceções** — falhas no audit são
        logadas como warning, mas não quebram a task que estava sendo
        auditada.

        Args:
            task_name: Nome da task (ex: 'validate', 'backup').
            status: Status final (success/failure/partial/dry_run/skipped).
            started_at: Timestamp de início (UTC).
            duration_ms: Duração em ms.
            rows_affected: Linhas processadas com sucesso.
            rows_failed: Linhas que falharam.
            error_message: Mensagem de erro (se status=failure).
            args: Argumentos passados (vão pro DB como JSON).
            input_data: Dados de input (apenas o HASH vai pro DB).
            user: Usuário (default: pega do SO).
        """
        try:
            user = user or _get_current_user()
            args_json = json.dumps(args or {}, default=str)

            secret = settings.audit_secret_key.get_secret_value()
            input_hash = _hash_input(input_data, secret) if input_data else ""

            with closing(sqlite3.connect(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO audit (
                        timestamp, task_name, user, input_hash, args, status,
                        duration_ms, rows_affected, rows_failed, error_message,
                        environment
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        started_at.isoformat(),
                        task_name,
                        user,
                        input_hash,
                        args_json,
                        status,
                        duration_ms,
                        rows_affected,
                        rows_failed,
                        error_message,
                        settings.environment,
                    ),
                )
                conn.commit()
        except (sqlite3.Error, OSError) as e:  # pragma: no cover
            logger.warning(
                "Falha ao gravar audit pra task '{name}': {err}",
                name=task_name,
                err=str(e),
            )

    def query(
        self,
        *,
        task_name: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Consulta o audit (read-only).

        Args:
            task_name: Filtrar por task específica.
            status: Filtrar por status.
            limit: Máximo de resultados (default 100).

        Returns:
            Lista de dicts com os campos. Mais recente primeiro.
            Retorna ``[]`` se falhar ou não houver entradas.
        """
        sql = "SELECT * FROM audit WHERE 1=1"
        params: list[Any] = []

        if task_name:
            sql += " AND task_name = ?"
            params.append(task_name)
        if status:
            sql += " AND status = ?"
            params.append(status)

        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(sql, params).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:  # pragma: no cover
            logger.warning("Falha ao consultar audit: {err}", err=str(e))
            return []


# ============================================================
# Singleton global
# ============================================================

#: Instância global usada em todo o projeto.
audit = AuditTrail()


__all__ = ["AuditTrail", "audit"]
