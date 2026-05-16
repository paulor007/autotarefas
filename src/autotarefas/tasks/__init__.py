"""
Módulo de Tasks do AutoTarefas.

Cada task herda de ``BaseTask`` e implementa um caso de uso específico:

- ``ValidateTask`` — valida planilhas CSV/Excel contra schema YAML

Próximas (futuras fases):
- ``BackupTask`` — backup de arquivos
- ``OrganizeTask`` — organizador de arquivos
- ``RPACadastroTask`` — RPA de cadastro web
"""

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
    "Schema",
    "ValidateTask",
    "load_schema",
]
