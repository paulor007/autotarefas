"""
Entry point da CLI do AutoTarefas.

Esta é a versão inicial mínima da Fase 0 — apenas:
    autotarefas --version
    autotarefas --help

Subcomandos (init, validate, backup, etc.) e opções globais
(--verbose, --quiet, --dry-run, --yes) serão adicionados na Fase 2.
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel

from autotarefas import __version__

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="AutoTarefas")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """AutoTarefas — Robô de Automação Operacional em Python.

    Automatiza tarefas operacionais repetitivas em empresas e
    profissionais autônomos: validação de planilhas, organização de
    arquivos, backups, cadastro automático em sistemas web (RPA),
    extração de dados e sincronização planilha vs sistema.

    \b
    Exemplos (em construção):
        autotarefas validate run produtos.xlsx -c codigo,nome,preco
        autotarefas backup run ~/dados -d ~/backups
        autotarefas rpa cadastrar --arquivo produtos.xlsx --config x.yml

    Para mais informações:
        https://github.com/paulor007/autotarefas
    """
    if ctx.invoked_subcommand is None:
        _print_welcome()


def _print_welcome() -> None:
    """Imprime banner de boas-vindas quando rodado sem subcomandos."""
    console.print(
        Panel.fit(
            f"[bold blue]AutoTarefas v{__version__}[/]\n"
            "[dim]Robô de Automação Operacional em Python[/]\n\n"
            "[yellow]Em desenvolvimento - Fase 0[/]\n\n"
            "[cyan]Uso:[/] [bold]autotarefas[/] [italic]<comando>[/] [italic]<argumentos>[/]\n"
            "[cyan]Ajuda:[/] [bold]autotarefas --help[/]",
            border_style="blue",
            padding=(1, 2),
            title="🤖 AutoTarefas",
        )
    )


if __name__ == "__main__":
    cli()
