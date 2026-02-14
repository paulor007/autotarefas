"""
Configurações globais do AutoTarefas.

Este módulo centraliza todas as configurações do sistema,
carregando valores do arquivo .env e definindo defaults.

Uso:
    from autotarefas.config import settings

    print(settings.APP_NAME)
    print(settings.LOG_LEVEL)
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeVar, cast

from dotenv import find_dotenv, load_dotenv

# -----------------------------------------------------------------------------
# .env loading (robusto e seguro para testes)
# -----------------------------------------------------------------------------
# find_dotenv() permite achar o .env mesmo se rodar o comando fora da pasta do projeto


def _running_under_pytest() -> bool:
    """
    Detecta execução sob pytest.

    Evita carregar `.env` durante testes, o que torna defaults não-determinísticos
    (ex.: APP_NAME vindo do seu ambiente local).
    """
    return ("PYTEST_CURRENT_TEST" in os.environ) or ("pytest" in sys.modules)


if not _running_under_pytest():
    env_file = find_dotenv(usecwd=True)
    if env_file:
        load_dotenv(env_file, override=False)


def _get_app_name() -> str:
    """
    Resolve o nome da aplicação de forma determinística nos testes e flexível fora deles.

    Motivação:
        Em Windows/VS Code é comum existir `APP_NAME` setado no ambiente global (ou herdado),
        o que quebra testes de defaults (fica não-determinístico).

    Regras:
        - Em testes (pytest): usa SOMENTE `AUTOTAREFAS_APP_NAME`.
          (ignora `APP_NAME` genérico de propósito)
        - Fora de testes (inclui deploy): aceita `AUTOTAREFAS_APP_NAME` e,
          se não existir, cai para `APP_NAME` por compatibilidade.

    Returns:
        str: Nome da aplicação.
    """
    default = "AutoTarefas"

    if _running_under_pytest():
        return os.getenv("AUTOTAREFAS_APP_NAME", default)

    return os.getenv("AUTOTAREFAS_APP_NAME", os.getenv("APP_NAME", default))


# -----------------------------------------------------------------------------
# Tipos / constantes
# -----------------------------------------------------------------------------
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
BackupCompression = Literal["zip", "tar", "tar.gz"]

_ALLOWED_LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_ALLOWED_BACKUP_COMPRESSION: tuple[str, ...] = ("zip", "tar", "tar.gz")

T = TypeVar("T", bound=str)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _get_env(key: str, default: str = "") -> str:
    """Obtém variável de ambiente com valor padrão."""
    return os.getenv(key, default)


def _get_env_bool(key: str, default: bool = False) -> bool:
    """Obtém variável de ambiente como booleano."""
    value = os.getenv(key, str(default)).strip().lower()
    return value in ("true", "1", "yes", "sim", "on")


def _get_env_int(key: str, default: int = 0) -> int:
    """Obtém variável de ambiente como inteiro."""
    raw = os.getenv(key, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _get_env_path(key: str, default: str = "") -> Path:
    """
    Obtém variável de ambiente como Path, expandindo ~ e variáveis.

    - Expande ~ e $VARS
    - Resolve paths relativos de forma consistente
    """
    raw = os.getenv(key, default).strip()
    if not raw:
        raw = default

    if not raw:
        return Path.cwd()

    expanded = os.path.expandvars(os.path.expanduser(raw))
    p = Path(expanded)

    # Resolve sem strict para não explodir se o path ainda não existir.
    return p.resolve(strict=False)


def _coerce_choice(value: str, allowed: Iterable[str], default: str) -> str:
    """
    Garante que value pertence ao conjunto allowed; caso contrário, retorna default.
    """
    v = (value or "").strip()
    return v if v in allowed else default


# -----------------------------------------------------------------------------
# Configs agrupadas
# -----------------------------------------------------------------------------


@dataclass
class EmailSettings:
    """Configurações de email/SMTP."""

    enabled: bool = field(default_factory=lambda: _get_env_bool("EMAIL_ENABLED", False))
    host: str = field(default_factory=lambda: _get_env("EMAIL_HOST", "smtp.gmail.com"))
    port: int = field(default_factory=lambda: _get_env_int("EMAIL_PORT", 587))
    user: str = field(default_factory=lambda: _get_env("EMAIL_USER", ""))
    password: str = field(default_factory=lambda: _get_env("EMAIL_PASSWORD", ""))

    # Compat: muitos setups usam EMAIL_FROM como "Nome <email@...>".
    # O parsing disso deve ficar no core/email.py; aqui só armazenamos.
    from_addr: str = field(default_factory=lambda: _get_env("EMAIL_FROM", ""))
    from_name: str = field(
        default_factory=lambda: _get_env("EMAIL_FROM_NAME", "AutoTarefas")
    )

    # Destinatário padrão (opcional). No envio, pode ser sobrescrito.
    to_addr: str = field(default_factory=lambda: _get_env("EMAIL_TO", ""))

    use_tls: bool = field(default_factory=lambda: _get_env_bool("EMAIL_USE_TLS", True))
    use_ssl: bool = field(default_factory=lambda: _get_env_bool("EMAIL_USE_SSL", False))
    timeout_seconds: int = field(
        default_factory=lambda: _get_env_int("EMAIL_TIMEOUT", 15)
    )

    def __post_init__(self) -> None:
        # Evita combinações confusas: SSL direto (465) normalmente não usa STARTTLS.
        # Não bloqueia (não muda lógica), só “normaliza” se vier incoerente.
        if self.use_ssl and self.use_tls:
            # Prioriza SSL direto se o usuário marcou ambos.
            self.use_tls = False


@dataclass
class MonitorSettings:
    """Configurações de monitoramento do sistema."""

    disk_threshold: int = field(
        default_factory=lambda: _get_env_int("DISK_USAGE_THRESHOLD", 80)
    )
    memory_threshold: int = field(
        default_factory=lambda: _get_env_int("MEMORY_USAGE_THRESHOLD", 75)
    )
    cpu_threshold: int = field(
        default_factory=lambda: _get_env_int("CPU_USAGE_THRESHOLD", 85)
    )


@dataclass
class BackupSettings:
    """Configurações de backup."""

    path: Path = field(
        default_factory=lambda: _get_env_path("BACKUP_PATH", "./backups")
    )
    compression: BackupCompression = field(
        default_factory=lambda: cast(
            BackupCompression,
            _coerce_choice(
                _get_env("BACKUP_COMPRESSION", "zip"),
                _ALLOWED_BACKUP_COMPRESSION,
                "zip",
            ),
        )
    )
    max_versions: int = field(
        default_factory=lambda: _get_env_int("BACKUP_MAX_VERSIONS", 5)
    )


@dataclass
class CleanerSettings:
    """Configurações do limpador de arquivos."""

    days_to_keep: int = field(
        default_factory=lambda: _get_env_int("CLEANER_DAYS_TO_KEEP", 30)
    )


@dataclass
class SchedulerSettings:
    """Configurações do agendador."""

    enabled: bool = field(
        default_factory=lambda: _get_env_bool("SCHEDULE_ENABLED", True)
    )
    timezone: str = field(
        default_factory=lambda: _get_env("SCHEDULE_TIMEZONE", "America/Sao_Paulo")
    )


# -----------------------------------------------------------------------------
# Settings principal
# -----------------------------------------------------------------------------


@dataclass
class Settings:
    """
    Configurações centralizadas do AutoTarefas.

    Carrega automaticamente valores do arquivo .env
    e fornece defaults sensatos para cada configuração.

    Exemplo:
        >>> from autotarefas.config import settings
        >>> print(settings.APP_NAME)
        'AutoTarefas'
        >>> print(settings.email.host)
        'smtp.gmail.com'
    """

    # === Configurações Gerais ===
    APP_NAME: str = field(default_factory=_get_app_name)
    APP_ENV: str = field(default_factory=lambda: _get_env("APP_ENV", "development"))
    DEBUG: bool = field(default_factory=lambda: _get_env_bool("DEBUG", True))

    # === Logging ===
    LOG_LEVEL: LogLevel = field(
        default_factory=lambda: cast(
            LogLevel,
            _coerce_choice(_get_env("LOG_LEVEL", "INFO"), _ALLOWED_LOG_LEVELS, "INFO"),
        )
    )
    LOG_PATH: Path = field(default_factory=lambda: _get_env_path("LOG_PATH", "./logs"))

    # === Caminhos ===
    TEMP_PATH: Path = field(
        default_factory=lambda: _get_env_path("TEMP_PATH", "./temp")
    )
    REPORTS_PATH: Path = field(
        default_factory=lambda: _get_env_path("REPORTS_PATH", "./reports")
    )

    # === Data dir (opcional, útil p/ históricos, cache, jobs etc.) ===
    DATA_DIR: Path = field(
        default_factory=lambda: _get_env_path("DATA_DIR", "./.autotarefas")
    )

    # === Configurações Agrupadas ===
    email: EmailSettings = field(default_factory=EmailSettings)
    monitor: MonitorSettings = field(default_factory=MonitorSettings)
    backup: BackupSettings = field(default_factory=BackupSettings)
    cleaner: CleanerSettings = field(default_factory=CleanerSettings)
    scheduler: SchedulerSettings = field(default_factory=SchedulerSettings)

    def __post_init__(self) -> None:
        """Cria diretórios necessários se não existirem."""
        for path in (
            self.LOG_PATH,
            self.TEMP_PATH,
            self.REPORTS_PATH,
            self.DATA_DIR,
            self.backup.path,
        ):
            path.mkdir(parents=True, exist_ok=True)

    # === Ambiente ===
    @property
    def is_production(self) -> bool:
        """Retorna True se estiver em ambiente de produção."""
        return self.APP_ENV.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Retorna True se estiver em ambiente de desenvolvimento."""
        return self.APP_ENV.lower() == "development"

    # === Compat: algumas partes do projeto podem usar settings.data_dir ===
    @property
    def data_dir(self) -> Path:
        """Alias/compat para DATA_DIR."""
        return self.DATA_DIR

    # === Propriedades de conveniência para SMTP ===
    @property
    def smtp_host(self) -> str:
        """Host SMTP."""
        return self.email.host

    @property
    def smtp_port(self) -> int:
        """Porta SMTP."""
        return self.email.port

    @property
    def smtp_user(self) -> str:
        """Usuário SMTP."""
        return self.email.user

    @property
    def smtp_password(self) -> str:
        """Senha SMTP."""
        return self.email.password

    @property
    def smtp_from(self) -> str:
        """Endereço de envio."""
        return self.email.from_addr or self.email.user

    @property
    def smtp_from_name(self) -> str:
        """Nome de exibição do remetente."""
        return self.email.from_name

    @property
    def smtp_tls(self) -> bool:
        """Usar TLS."""
        return self.email.use_tls

    @property
    def smtp_ssl(self) -> bool:
        """Usar SSL direto."""
        return self.email.use_ssl

    @property
    def smtp_timeout_seconds(self) -> int:
        """Timeout de conexão SMTP em segundos."""
        return self.email.timeout_seconds

    def __repr__(self) -> str:
        return (
            f"Settings(APP_NAME='{self.APP_NAME}', "
            f"APP_ENV='{self.APP_ENV}', "
            f"DEBUG={self.DEBUG}, "
            f"LOG_LEVEL='{self.LOG_LEVEL}')"
        )


# Instância global de configurações
settings = Settings()


# Exports
__all__ = [
    "settings",
    "Settings",
    "EmailSettings",
    "MonitorSettings",
    "BackupSettings",
    "CleanerSettings",
    "SchedulerSettings",
]
