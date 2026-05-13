"""
Comando ``info``: mostra informações do sistema AutoTarefas.

Uso:
    autotarefas info
    autotarefas --dry-run info
    autotarefas -vv info
"""

from __future__ import annotations

import click

from autotarefas import __version__
from autotarefas.cli.context import CLIContext
from autotarefas.core import settings


@click.command(name="info")
@click.pass_obj
def info(ctx: CLIContext) -> None:
    """Mostra informacoes do sistema (versao, ambiente, configs)."""
    click.echo(f"AutoTarefas v{__version__}")
    click.echo(f"Environment: {settings.environment}")
    click.echo(f"Log level:   {ctx.log_level}")
    click.echo(f"Dry-run:     {ctx.dry_run}")
    click.echo(f"Yes (auto):  {ctx.yes}")
    click.echo(f"Audit DB:    {settings.audit_db_path}")
    click.echo(f"Logs dir:    {settings.logs_dir}")


__all__ = ["info"]
