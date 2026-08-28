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
    workspace_ttl_min: int = field(default_factory=lambda: _env_int("WORKSPACE_TTL_MIN", 15))
    max_workspaces: int = field(default_factory=lambda: _env_int("MAX_WORKSPACES", 40))
    # Live-1.3: streaming, concorrencia e egress
    max_concurrent_runs: int = field(default_factory=lambda: _env_int("MAX_CONCURRENT_RUNS", 4))
    max_stream_lines: int = field(default_factory=lambda: _env_int("MAX_STREAM_LINES", 2000))
    max_stream_bytes: int = field(default_factory=lambda: _env_int("MAX_STREAM_BYTES", 256 * 1024))
    egress_lockdown: bool = field(default_factory=lambda: _env_bool("EGRESS_LOCKDOWN", True))
    allowed_upload_extensions: tuple[str, ...] = (
        ".csv",
        ".tsv",
        ".txt",
        ".pdf",
        ".docx",
        ".xlsx",
        ".jpg",
        ".jpeg",
        ".png",
        ".json",
        ".yaml",
        ".yml",
    )

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

    # ============================================================
    # Plataforma (G.2): banco, sessao e identidade
    # ============================================================

    #: Onde os dados moram. PostgreSQL em producao, SQLite no resto.
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", "").strip())
    #: Segredo que assina o cookie de sessao. Sem ele o servico sorteia um a
    #: cada partida — a sessao nao sobrevive ao reinicio, e isso e avisado no
    #: console. Nunca ha um segredo fixo embutido no codigo: um valor padrao
    #: publicado no repositorio seria o mesmo que nao assinar nada.
    session_secret: str = field(
        default_factory=lambda: os.environ.get("SESSION_SECRET", "").strip()
    )
    #: Quanto tempo a sessao vale, em horas.
    session_hours: int = field(default_factory=lambda: _env_int("SESSION_HOURS", 12))
    #: `Secure` no cookie. Desligado so em desenvolvimento local, porque
    #: `Secure` sem HTTPS impede o navegador de guardar o cookie.
    cookie_secure: bool = field(default_factory=lambda: _env_bool("COOKIE_SECURE", False))
    #: Endereco publico do Live: retorno do provedor OIDC e os links que o
    #: console imprime.
    #:
    #: O padrao era `http://localhost:5173` — a porta do servidor de
    #: DESENVOLVIMENTO do front. Ela nunca e onde o backend escuta. Quem subia
    #: so o backend, que e o caminho de qualquer instalacao real, recebia no
    #: console um link para uma porta onde nao havia nada. Foi o que aconteceu:
    #: `--port 8000`, link impresso apontando para `:5173`.
    #:
    #: Agora o padrao e a propria porta do servico. Continua sendo uma
    #: suposicao — o `--port` do uvicorn nao chega ate aqui — e por isso o
    #: console DIZ que supos, e como corrigir.
    public_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "PUBLIC_BASE_URL", f"http://localhost:{_env_int('PORT', 7860)}"
        ).strip()
    )
    #: Alguem definiu `PUBLIC_BASE_URL`, ou o valor acima foi suposto? O
    #: console usa isto para nao apresentar um palpite como se fosse fato.
    base_url_suposta: bool = field(
        default_factory=lambda: not os.environ.get("PUBLIC_BASE_URL", "").strip()
    )

    #: Provedor OIDC. Vazio = nenhum provedor configurado; a tela de entrada
    #: diz isso em vez de mostrar um botao que nao funciona.
    oidc_issuer: str = field(default_factory=lambda: os.environ.get("OIDC_ISSUER", "").strip())
    oidc_client_id: str = field(
        default_factory=lambda: os.environ.get("OIDC_CLIENT_ID", "").strip()
    )
    oidc_client_secret: str = field(
        default_factory=lambda: os.environ.get("OIDC_CLIENT_SECRET", "").strip()
    )
    #: Minutos de validade do link de bootstrap de primeira execucao.
    bootstrap_minutes: int = field(default_factory=lambda: _env_int("BOOTSTRAP_MINUTES", 30))

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

    @property
    def oidc_configurado(self) -> bool:
        """Ha provedor de identidade utilizavel?"""
        return bool(self.oidc_issuer and self.oidc_client_id and self.oidc_client_secret)


settings = Settings()
