"""
AutoTarefas - Sistema de Automação de Tarefas

Um sistema modular para automatizar tarefas repetitivas do computador:
- Backup automático de arquivos
- Limpeza de arquivos temporários
- Organização de downloads
- Monitoramento do sistema
- Agendamento de tarefas
- Notificações por email

Uso básico:
    from autotarefas import __version__
    from autotarefas.core import BaseTask, TaskResult, TaskStatus
    from autotarefas.config import settings
"""

__version__ = "0.1.0"
__author__ = "AutoTarefas Team"
__email__ = ""
__license__ = "MIT"

# Imports principais para facilitar uso
from autotarefas.config import settings
from autotarefas.core import BaseTask, TaskResult, TaskStatus, logger

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    # Config
    "settings",
    # Core
    "BaseTask",
    "TaskResult",
    "TaskStatus",
    "logger",
]
