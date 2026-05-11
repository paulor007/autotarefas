"""
Módulo Core do AutoTarefas.

Componentes fundamentais usados por todos os outros módulos:

- ``exceptions`` — hierarquia de exceções customizadas
- ``settings`` — configurações via .env (pydantic-settings)
- ``logger`` — logging com mascaramento automático

Uso:
    from autotarefas.core import logger, settings, ValidationError

    logger.info("Iniciando aplicação no ambiente {env}", env=settings.environment)

    if invalid:
        raise ValidationError("Campo obrigatório faltando", field="email")
"""

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
from autotarefas.core.settings import Settings, settings

__all__ = [
    "AuditError",
    "AutoTarefasError",
    "ConfigError",
    "LoginError",
    "RPAError",
    "RPATimeoutError",
    "SecurityError",
    "SelectorNotFoundError",
    "Settings",
    "ValidationError",
    "configure_logger",
    "logger",
    "mask_sensitive",
    "settings",
]
