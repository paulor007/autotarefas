"""
Grupo de comandos `sync` — sincronizacao entre sistemas.

Subcomandos:
    sync api  -> sincroniza de uma API origem para uma API destino

Destino deste arquivo:
    src/autotarefas/cli/commands/sync/__init__.py
"""

from __future__ import annotations

import click

from autotarefas.cli.commands.sync.api import api_command


@click.group(name="sync")
def sync() -> None:
    """Sincroniza dados entre sistemas (origem -> destino)."""


sync.add_command(api_command)


__all__ = ["sync"]
