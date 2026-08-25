"""
Comando ``verificar``: confere um backup sem precisar dos arquivos originais.

Backup que ninguem confere e fe, nao garantia. E a conferencia tem que
funcionar no dia em que o original ja nao existe — por isso ela le o
`MANIFESTO.csv` que esta DENTRO do pacote, e nao a pasta de origem.

Duas perguntas diferentes, e as duas sao respondidas:

- **integridade** — o conteudo bate com o que o manifesto declarou?
- **autenticidade** — a assinatura do manifesto confere com a chave externa?

Sem assinatura, so a primeira tem resposta, e isso e dito em voz alta: quem
alterar um arquivo e recalcular o manifesto passa pela conferencia de
integridade, porque a chave dela viaja dentro do proprio pacote.

Uso:
    autotarefas verificar backups/contabilidade_2026-08-20_1730.zip
"""

from __future__ import annotations

from pathlib import Path

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.tasks.assinatura import Autenticidade
from autotarefas.tasks.backup import VerifyReport, verify_backup

#: Quantos arquivos com problema listar antes de resumir.
_PREVIEW = 10

#: Saida 1 = o pacote abriu, mas ha algo errado com o conteudo.
_EXIT_PROBLEMA = 1

#: Saida 2 = nem deu para conferir (nao abriu, sem manifesto).
_EXIT_FALHA = 2


#: O que dizer sobre a assinatura, em texto de terminal (sem acento e sem
#: travessao: o console do Windows abre em cp1252 e estraga os dois).
_AUTENTICIDADE: dict[Autenticidade, str] = {
    Autenticidade.NAO_ASSINADO: (
        "Pacote NAO assinado: isto confere corrupcao e alteracao acidental, "
        "nao adulteracao intencional."
    ),
    Autenticidade.AUTENTICO: (
        "Assinatura confere: o pacote saiu de quem tem a chave e nao foi alterado depois."
    ),
    Autenticidade.ADULTERADO: (
        "ASSINATURA NAO CONFERE: o pacote foi alterado depois de assinado, ou "
        "a assinatura foi forjada."
    ),
    Autenticidade.SEM_CHAVE: (
        "Pacote assinado, mas sem a chave aqui para conferir. Integridade "
        "conferida; autenticidade, nao. Defina AUTOTAREFAS_BACKUP_KEY."
    ),
    Autenticidade.OUTRA_CHAVE: (
        "Pacote assinado com OUTRA chave. Confira qual chave estava em uso quando ele foi gerado."
    ),
}


def _relatar_assinatura(console: Console, relatorio: VerifyReport) -> None:
    """
    Diz o que a assinatura permite (ou nao permite) concluir.

    Sempre aparece, inclusive no caso bom: um "integro" sozinho promete mais
    do que foi provado quando o pacote nem assinado esta.
    """
    frase = _AUTENTICIDADE[relatorio.authenticity]
    console.info("")
    if relatorio.authenticity is Autenticidade.AUTENTICO:
        console.success(frase)
    elif relatorio.authenticity in {Autenticidade.ADULTERADO, Autenticidade.OUTRA_CHAVE}:
        console.error(frase)
    else:
        console.warning(frase)


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

    _relatar_assinatura(console, relatorio)

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
    console.error("Pacote com problemas: NAO confie nele para restaurar.")
    raise click.exceptions.Exit(_EXIT_PROBLEMA)


__all__ = ["verificar"]
