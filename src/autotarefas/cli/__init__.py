"""
Módulo CLI do AutoTarefas.

Exports principais:
- ``cli`` — grupo Click raiz
- ``CLIContext`` — contexto compartilhado entre comandos
"""

from autotarefas.cli.context import CLIContext
from autotarefas.cli.main import cli

__all__ = ["CLIContext", "cli"]
