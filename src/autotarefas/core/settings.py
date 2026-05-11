"""
Configurações do AutoTarefas (lidas de .env e variáveis de ambiente).

Usa ``pydantic-settings`` para validação automática e type safety.

Uso:
    from autotarefas.core.settings import settings

    print(settings.environment)
    print(settings.email_host)

    # Senhas são SecretStr — precisa get_secret_value() pra acessar
    senha = settings.email_password.get_secret_value()
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default home directory: ~/.autotarefas
DEFAULT_HOME = Path.home() / ".autotarefas"


class Settings(BaseSettings):
    """
    Configurações da aplicação.

    Carrega valores em ordem de prioridade:

    1. Variáveis de ambiente (prioridade alta)
    2. Arquivo ``.env`` na raiz do projeto
    3. Defaults definidos abaixo (prioridade baixa)
    """

    # Configuração do pydantic-settings
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============================================================
    # Ambiente
    # ============================================================
    environment: Literal["dev", "demo", "homolog", "prod"] = Field(
        default="dev",
        description="Ambiente de execução. 'prod' impõe restrições extras.",
    )

    # ============================================================
    # Configurações básicas
    # ============================================================
    autotarefas_home: Path = Field(
        default_factory=lambda: DEFAULT_HOME,
        description="Pasta raiz dos dados do AutoTarefas.",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Nível mínimo de log.",
    )

    # ============================================================
    # Email (Fase 8+)
    # ============================================================
    email_host: str = Field(default="smtp.gmail.com")
    email_port: int = Field(default=587, ge=1, le=65535)
    email_user: str = Field(default="")
    email_password: SecretStr = Field(default=SecretStr(""))
    email_from: str = Field(default="")

    # ============================================================
    # Sistema demo (Fase 8.0)
    # ============================================================
    demo_sistema_usuario: str = Field(default="admin@demo.local")
    demo_sistema_senha: SecretStr = Field(default=SecretStr(""))
    demo_sistema_url: str = Field(default="http://localhost:8000")

    # ============================================================
    # RPA (Fase 8+)
    # ============================================================
    rpa_default_timeout: int = Field(default=10, ge=1, le=300)
    rpa_max_retries: int = Field(default=3, ge=0, le=10)
    rpa_headless: bool = Field(default=True)

    # ============================================================
    # Audit Trail (Fase 1.3)
    # ============================================================
    audit_secret_key: SecretStr = Field(
        default=SecretStr(""),
        description="Chave para HMAC-SHA256 do audit trail.",
    )

    # ============================================================
    # Screenshots (Fase 8+)
    # ============================================================
    screenshot_retention_days: int = Field(default=30, ge=1, le=365)
    screenshots_mask_sensitive: bool = Field(default=True)

    # ============================================================
    # Limites de segurança
    # ============================================================
    max_file_size_mb: int = Field(default=100, ge=1, le=10000)
    max_records_per_run: int = Field(default=10000, ge=1, le=1000000)

    # ============================================================
    # Properties derivadas (paths)
    # ============================================================

    @property
    def logs_dir(self) -> Path:
        """Pasta de logs (criada automaticamente se não existir)."""
        return self.autotarefas_home / "logs"

    @property
    def audit_db_path(self) -> Path:
        """Caminho do banco SQLite de audit trail."""
        return self.autotarefas_home / "audit.db"

    @property
    def screenshots_dir(self) -> Path:
        """Pasta de screenshots do RPA."""
        return self.autotarefas_home / "screenshots"

    @property
    def reports_dir(self) -> Path:
        """Pasta de relatórios gerados."""
        return self.autotarefas_home / "reports"

    @property
    def is_production(self) -> bool:
        """True se ambiente é produção."""
        return self.environment == "prod"

    # ============================================================
    # Validators
    # ============================================================

    @field_validator("autotarefas_home")
    @classmethod
    def expand_home(cls, v: Path | str) -> Path:
        """Expande ``~`` no caminho do home."""
        return Path(v).expanduser()


# Instância singleton — usar em todo lugar
settings = Settings()
