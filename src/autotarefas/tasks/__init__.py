"""
Módulo de Tasks do AutoTarefas.

Cada task herda de ``BaseTask`` e implementa um caso de uso específico:

- ``ValidateTask`` — valida planilhas CSV/Excel contra schema YAML

Próximas (futuras fases):
- ``BackupTask`` — backup de arquivos
- ``OrganizeTask`` — organizador de arquivos
- ``RPACadastroTask`` — RPA de cadastro web
"""

from autotarefas.tasks.extract_api import ExtractApiTask
from autotarefas.tasks.extract_web import ExtractWebTask
from autotarefas.tasks.send_api import SendApiTask
from autotarefas.tasks.send_email import SendEmailTask, SmtpConfig
from autotarefas.tasks.send_telegram import SendTelegramTask
from autotarefas.tasks.sync_api import SyncApiTask
from autotarefas.tasks.validate import (
    ColumnSchema,
    ColumnType,
    Schema,
    ValidateTask,
    load_schema,
)

__all__ = [
    "ColumnSchema",
    "ColumnType",
    "ExtractApiTask",
    "ExtractWebTask",
    "Schema",
    "SendApiTask",
    "SendEmailTask",
    "SendTelegramTask",
    "SmtpConfig",
    "SyncApiTask",
    "ValidateTask",
    "load_schema",
]
