"""
CLI principal do AutoTarefas.

Define o grupo ``cli`` raiz com opções globais aplicáveis a todos os
subcomandos:

- ``--verbose, -v`` (cumulativo: -v, -vv, -vvv)
- ``--quiet, -q`` (cumulativo: -q, -qq)
- ``--dry-run`` (simula sem mudanças reais)
- ``--yes, -y`` (assume "sim" em confirmações)
- ``--version``

Uso:
    autotarefas --version
    autotarefas info
    autotarefas --dry-run --verbose info
    python -m autotarefas info
"""

from __future__ import annotations

import click

from autotarefas import __version__
from autotarefas.cli.commands.info import info
from autotarefas.cli.context import CLIContext


@click.group(
    name="autotarefas",
    help="Robo de automacao operacional para tarefas planilhas/web.",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Aumenta a verbosidade (-v=info, -vv=debug, -vvv=trace).",
)
@click.option(
    "-q",
    "--quiet",
    count=True,
    help="Diminui a verbosidade (-q=warning, -qq=error).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Simula a execucao sem fazer mudancas reais.",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    default=False,
    help="Assume 'sim' em todas as confirmacoes interativas.",
)
@click.version_option(version=__version__, prog_name="autotarefas")
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: int,
    quiet: int,
    dry_run: bool,
    yes: bool,
) -> None:
    """Robo de automacao operacional do AutoTarefas."""
    ctx.obj = CLIContext(
        verbose=verbose,
        quiet=quiet,
        dry_run=dry_run,
        yes=yes,
    )


# Registra os subcomandos
cli.add_command(info)


if __name__ == "__main__":
    cli()
