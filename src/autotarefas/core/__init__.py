"""
Módulo Core do AutoTarefas.

Componentes fundamentais usados por todos os outros módulos:

- ``exceptions`` — hierarquia de exceções customizadas
- ``settings`` — configurações via .env (pydantic-settings)
- ``logger`` — logging com mascaramento automático
- ``base`` — BaseTask, TaskResult, TaskStatus (abstrações de task)

Uso:
    from autotarefas.core import BaseTask, TaskResult, TaskStatus
    from autotarefas.core import logger, settings, ValidationError

    class MyTask(BaseTask):
        name = "my_task"
        description = "..."

        def execute(self) -> TaskResult:
            ...
"""

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
from autotarefas.core.settings import Settings, settings

__all__ = [
    "AuditError",
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
    "configure_logger",
    "logger",
    "mask_sensitive",
    "settings",
]
