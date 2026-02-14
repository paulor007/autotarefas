"""
Módulo core do AutoTarefas.

Contém as classes e funções fundamentais do sistema:
    - BaseTask: Classe base para todas as tasks
    - TaskResult: Resultado de execução
    - TaskStatus: Status de execução
    - logger: Sistema de logging
    - Scheduler: Sistema de agendamento (Fase 5)

Uso:
    from autotarefas.core import BaseTask, TaskResult, TaskStatus
    from autotarefas.core import logger
    from autotarefas.core import Scheduler, get_scheduler
"""

from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.core.logger import (
    LoggerContext,
    configure_from_settings,
    get_logger,
    logger,
    setup_logger,
)
from autotarefas.core.scheduler import (
    ScheduledExecution,
    Scheduler,
    ScheduleType,
    TaskRegistry,
    get_scheduler,
    reset_scheduler,
)

__all__ = [
    # Base
    "BaseTask",
    "TaskResult",
    "TaskStatus",
    # Logger
    "logger",
    "setup_logger",
    "get_logger",
    "configure_from_settings",
    "LoggerContext",
    # Scheduler (Fase 5.1)
    "ScheduleType",
    "TaskRegistry",
    "ScheduledExecution",
    "Scheduler",
    "get_scheduler",
    "reset_scheduler",
]
