"""Configuracoes do backend do Live System (lidas de variaveis de ambiente).

Tudo tem default seguro para rodar local sem configurar nada. Em producao,
ajuste via env (PORT, limites, CORS, etc.).
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Parametros do servico."""

    app_name: str = "AutoTarefas - Live System"
    version: str = field(default_factory=lambda: os.environ.get("LIVE_VERSION", "0.1.0"))

    # rede
    port: int = field(default_factory=lambda: _env_int("PORT", 7860))

    # servidores de demonstracao (mocks internos)
    autostart_demo_servers: bool = field(
        default_factory=lambda: _env_bool("DEMO_SERVERS_AUTOSTART", True)
    )
    demo_primary_port: int = field(default_factory=lambda: _env_int("DEMO_PRIMARY_PORT", 5555))
    demo_secondary_port: int = field(default_factory=lambda: _env_int("DEMO_SECONDARY_PORT", 5556))
    smtp_port: int = field(default_factory=lambda: _env_int("DEMO_SMTP_PORT", 8025))

    # limites de execucao (aplicados de fato na Live-2/3)
    max_upload_mb: int = field(default_factory=lambda: _env_int("MAX_UPLOAD_MB", 10))
    max_upload_files: int = field(default_factory=lambda: _env_int("MAX_UPLOAD_FILES", 50))
    run_timeout_s: int = field(default_factory=lambda: _env_int("RUN_TIMEOUT_S", 60))
    rate_limit_per_min: int = field(default_factory=lambda: _env_int("RATE_LIMIT_PER_MIN", 12))

    # diretorios
    workspaces_root: Path = field(
        default_factory=lambda: Path(
            os.environ.get("WORKSPACES_ROOT", str(Path(tempfile.gettempdir()) / "autotarefas-live"))
        )
    )
    # raiz do repo (para subir os mocks e localizar as fixtures)
    repo_root: Path = field(
        default_factory=lambda: Path(
            os.environ.get("REPO_ROOT", str(Path(__file__).resolve().parents[3]))
        )
    )

    # CORS para desenvolvimento (Vite). Em producao o front e servido pelo mesmo host.
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.environ.get(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if o.strip()
        )
    )


settings = Settings()
