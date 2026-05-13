"""
Módulo Core do AutoTarefas.

Componentes fundamentais usados por todos os outros módulos:

- ``exceptions`` — hierarquia de exceções customizadas
- ``settings`` — configurações via .env (pydantic-settings)
- ``logger`` — logging com mascaramento automático
- ``base`` — BaseTask, TaskResult, TaskStatus (abstrações de task)
- ``audit`` — sistema de audit trail SQLite
- ``security`` — helpers de segurança (safe_path, validate_url, hash_string)

Uso:
    from autotarefas.core import (
        BaseTask, TaskResult, TaskStatus,
        logger, settings, audit,
        safe_path, validate_url,
        ValidationError,
    )
"""

from autotarefas.core.audit import AuditTrail, audit
from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.core.exceptions import (
    AuditError,
    AutoTarefasError,
    ConfigError,
    LoginError,
    RPAError,
    RPATimeoutError,
    SecurityError,
    SelectorNotFoundError,
    ValidationError,
)
from autotarefas.core.logger import configure_logger, logger, mask_sensitive
from autotarefas.core.security import hash_string, safe_path, validate_url
from autotarefas.core.settings import Settings, settings

__all__ = [
    "AuditError",
    "AuditTrail",
    "AutoTarefasError",
    "BaseTask",
    "ConfigError",
    "LoginError",
    "RPAError",
    "RPATimeoutError",
    "SecurityError",
    "SelectorNotFoundError",
    "Settings",
    "TaskResult",
    "TaskStatus",
    "ValidationError",
    "audit",
    "configure_logger",
    "hash_string",
    "logger",
    "mask_sensitive",
    "safe_path",
    "settings",
    "validate_url",
]
