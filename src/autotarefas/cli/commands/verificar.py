"""
Comando ``verificar``: confere um backup sem precisar dos arquivos originais.

Backup que ninguem confere e fe, nao garantia. E a conferencia tem que
funcionar no dia em que o original ja nao existe — por isso ela le o
`MANIFESTO.csv` que esta DENTRO do pacote, e nao a pasta de origem.

Uso:
    autotarefas verificar backups/contabilidade_2026-08-20_1730.zip
"""

from __future__ import annotations

from pathlib import Path

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.tasks.backup import VerifyReport, verify_backup

#: Quantos arquivos com problema listar antes de resumir.
_PREVIEW = 10

#: Saida 1 = o pacote abriu, mas ha algo errado com o conteudo.
_EXIT_PROBLEMA = 1

#: Saida 2 = nem deu para conferir (nao abriu, sem manifesto).
_EXIT_FALHA = 2


def _listar(console: Console, titulo: str, itens: tuple[str, ...]) -> None:
    """Mostra ate `_PREVIEW` itens de uma lista de problemas."""
    if not itens:
        return
    console.error(f"{titulo}: {len(itens)}")
    for item in itens[:_PREVIEW]:
        console.error(f"  - {item}")
    restantes = len(itens) - _PREVIEW
    if restantes > 0:
        console.error(f"  ... e mais {restantes}.")


def _relatar(console: Console, relatorio: VerifyReport) -> None:
    """Traduz o relatorio para o que a pessoa precisa saber."""
    console.info(f"Arquivos conferidos: {relatorio.checked}")

    _listar(console, "Conteudo diferente do declarado", relatorio.corrupted)
    _listar(console, "Declarados no manifesto e ausentes do pacote", relatorio.missing)
    _listar(console, "Presentes no pacote e fora do manifesto", relatorio.unexpected)

    # Isto NAO e defeito do pacote: e memoria do que ficou de fora no dia em
    # que o backup foi feito. Aparece aqui porque quem confere precisa saber
    # que esses arquivos nunca estiveram la.
    if relatorio.unreadable_at_origin:
        console.info("")
        console.warning(
            f"{len(relatorio.unreadable_at_origin)} arquivo(s) nao entraram quando "
            "este backup foi feito (estavam abertos ou sem permissao):"
        )
        for item in relatorio.unreadable_at_origin[:_PREVIEW]:
            console.warning(f"  - {item}")
        restantes = len(relatorio.unreadable_at_origin) - _PREVIEW
        if restantes > 0:
            console.warning(f"  ... e mais {restantes}.")


@click.command(name="verificar")
@click.argument(
    "pacote",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
)
@click.pass_obj
def verificar(ctx: CLIContext, pacote: Path) -> None:
    """Confere a integridade de um backup gerado pelo AutoTarefas."""
    console = Console(ctx)
    console.info(f"Conferindo {pacote.name}...")

    relatorio = verify_backup(pacote)

    if relatorio.problem:
        console.error(f"Nao foi possivel conferir: {relatorio.problem}")
        raise click.exceptions.Exit(_EXIT_FALHA)

    _relatar(console, relatorio)

    if relatorio.ok:
        console.info("")
        console.success(
            f"Pacote integro: os {relatorio.checked} arquivos conferem com o manifesto."
        )
        return

    console.info("")
    console.error("Pacote com problemas — NAO confie nele para restaurar.")
    raise click.exceptions.Exit(_EXIT_PROBLEMA)


__all__ = ["verificar"]
