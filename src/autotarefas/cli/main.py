"""
Ponto de entrada da CLI do AutoTarefas.

Define o grupo raiz ``cli`` com as opcoes globais (verbose, quiet, dry-run,
yes) e registra todos os subcomandos disponiveis.

Adicionar um novo comando:
1. Crie em ``autotarefas/cli/commands/SEU_COMANDO.py``
2. Importe aqui: ``from autotarefas.cli.commands.SEU_COMANDO import SEU_COMANDO``
3. Registre: ``cli.add_command(SEU_COMANDO)``
"""

from __future__ import annotations

import click

from autotarefas import __version__
from autotarefas.cli.commands.backup import backup
from autotarefas.cli.commands.extract import extract
from autotarefas.cli.commands.info import info
from autotarefas.cli.commands.init import init
from autotarefas.cli.commands.organize import organize
from autotarefas.cli.commands.report import report
from autotarefas.cli.commands.rpa import rpa
from autotarefas.cli.commands.send import send
from autotarefas.cli.commands.validate import validate
from autotarefas.cli.context import CLIContext


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="autotarefas")
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Aumenta a verbosidade (pode repetir: -v, -vv, -vvv).",
)
@click.option(
    "--quiet",
    "-q",
    count=True,
    help="Reduz a verbosidade (pode repetir: -q, -qq).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Simula a operacao sem fazer mudancas reais.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Assume 'sim' em todas as confirmacoes.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: int,
    quiet: int,
    dry_run: bool,
    yes: bool,
) -> None:
    """AutoTarefas - Robo de automacao operacional."""
    ctx.obj = CLIContext(
        verbose=verbose,
        quiet=quiet,
        dry_run=dry_run,
        yes=yes,
    )


# ============================================================
# Registro dos subcomandos
# ============================================================

cli.add_command(backup)
cli.add_command(info)
cli.add_command(init)
cli.add_command(organize)
cli.add_command(report)
cli.add_command(rpa)
cli.add_command(extract)
cli.add_command(send)
cli.add_command(validate)


__all__ = ["cli"]
