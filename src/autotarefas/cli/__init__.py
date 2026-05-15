"""
Módulo CLI do AutoTarefas.

Exports principais:
- ``cli`` — grupo Click raiz
- ``CLIContext`` — contexto compartilhado entre comandos
- ``Console`` — wrapper Rich pra UX com cores
- ``confirm`` / ``confirm_bulk`` — helpers de confirmação
"""

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.cli.helpers import confirm, confirm_bulk
from autotarefas.cli.main import cli

__all__ = [
    "CLIContext",
    "Console",
    "cli",
    "confirm",
    "confirm_bulk",
]
