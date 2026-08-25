"""
Comando ``restaurar``: tira os arquivos de volta do pacote.

É o momento em que o backup prova que serviu. Por isso a saída é explícita
sobre o que foi restaurado, o que foi preservado e — principalmente — o que
faltou: uma restauração parcial que se anuncia como sucesso é pior do que uma
que falha.

Uso:
    # Ver o que há dentro antes de mexer em qualquer coisa
    autotarefas restaurar backup.zip --listar

    # Restaurar tudo numa pasta nova (não sobrescreve nada por padrão)
    autotarefas restaurar backup.zip --para C:\\recuperado

    # Restaurar uma amostra, para testar o backup sem tocar no que roda
    autotarefas restaurar backup.zip --para C:\\amostra --apenas dados/contrato.txt

    # Pacote incremental: informe os anteriores da corrente
    autotarefas restaurar p3.zip --para C:\\rec --anterior p2.zip --anterior p1.zip
"""

from __future__ import annotations

from pathlib import Path

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.tasks.hooks import ProtecaoBloqueou
from autotarefas.tasks.restauracao import (
    Relatorio,
    RestauracaoRecusada,
    listar_conteudo,
)
from autotarefas.tasks.restauracao import (
    restaurar as executar_restauracao,
)

#: Quantos itens listar antes de resumir.
_PREVIEW = 20

#: Saída 1 = restaurou, mas faltou coisa. Saída 2 = não deu para restaurar.
_EXIT_INCOMPLETA = 1
_EXIT_FALHA = 2


def _listar(console: Console, pacote: Path) -> None:
    conteudo = listar_conteudo(pacote)
    console.info(f"{len(conteudo)} arquivo(s) declarados em {pacote.name}:")
    for item in conteudo[:_PREVIEW]:
        onde = "" if item["neste_pacote"] == "sim" else f"  (esta em {item['onde']})"
        console.info(f"  - {item['arquivo']}{onde}")
    restantes = len(conteudo) - _PREVIEW
    if restantes > 0:
        console.info(f"  ... e mais {restantes}.")


def _relatar(console: Console, relatorio: Relatorio) -> None:
    """Diz o que aconteceu, sem arredondar."""
    console.info(f"Restaurados: {len(relatorio.restaurados)}")

    if relatorio.protecao:
        console.info(f"Protecao: {relatorio.protecao}")

    if relatorio.ja_existiam:
        console.info("")
        console.info(
            f"{len(relatorio.ja_existiam)} arquivo(s) JA EXISTIAM e foram preservados. "
            "Use --sobrescrever se quiser substituir."
        )
        for item in relatorio.ja_existiam[:_PREVIEW]:
            console.info(f"  - {item}")

    if relatorio.recusados:
        console.info("")
        console.error(
            f"{len(relatorio.recusados)} caminho(s) do pacote tentaram sair da pasta "
            "de destino e foram RECUSADOS:"
        )
        for item in relatorio.recusados[:_PREVIEW]:
            console.error(f"  - {item}")

    if relatorio.faltando:
        console.info("")
        console.error(
            f"{len(relatorio.faltando)} arquivo(s) estao em pacotes ANTERIORES que "
            "nao foram informados:"
        )
        for item in relatorio.faltando[:_PREVIEW]:
            console.error(f"  - {item}")
        console.info("  Informe os pacotes com --anterior para completar a restauracao.")

    if relatorio.corrompidos:
        console.info("")
        console.error(
            f"{len(relatorio.corrompidos)} arquivo(s) sairam diferentes do que o "
            "manifesto declarou e foram descartados:"
        )
        for item in relatorio.corrompidos[:_PREVIEW]:
            console.error(f"  - {item}")


@click.command(name="restaurar")
@click.argument(
    "pacote", type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path)
)
@click.option(
    "--para",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Pasta onde os arquivos serao escritos.",
)
@click.option("--listar", is_flag=True, default=False, help="So mostra o conteudo do pacote.")
@click.option(
    "--apenas",
    multiple=True,
    help="Restaura somente estes arquivos (pode repetir). Util para testar o backup.",
)
@click.option(
    "--anterior",
    "anteriores",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Pacote anterior da corrente, quando o backup e incremental. Pode repetir.",
)
@click.option(
    "--sobrescrever",
    is_flag=True,
    default=False,
    help="Substitui arquivos que ja existirem no destino. Por padrao, preserva.",
)
@click.option(
    "--protecao",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=(
        "Pasta de pacotes do DESTINO. Com --sobrescrever, a substituicao so "
        "acontece se houver ali backup recente e conferido."
    ),
)
@click.option(
    "--dispensar-protecao",
    "dispensar_protecao",
    default="",
    metavar="MOTIVO",
    help=(
        "Sobrescreve sem apresentar backup. Exige o motivo, que fica registrado "
        "no relatorio da restauracao."
    ),
)
@click.pass_obj
def restaurar(
    ctx: CLIContext,
    pacote: Path,
    para: Path | None,
    listar: bool,
    apenas: tuple[str, ...],
    anteriores: tuple[Path, ...],
    sobrescrever: bool,
    protecao: Path | None,
    dispensar_protecao: str,
) -> None:
    """Restaura os arquivos de um pacote gerado pelo AutoTarefas."""
    console = Console(ctx)

    if listar:
        try:
            _listar(console, pacote)
        except RestauracaoRecusada as erro:
            console.error(str(erro))
            raise click.exceptions.Exit(_EXIT_FALHA) from None
        return

    if para is None:
        console.error("Informe a pasta de destino com --para, ou use --listar.")
        raise click.exceptions.Exit(_EXIT_FALHA)

    console.info(f"Restaurando {pacote.name} em {para}...")
    try:
        relatorio = executar_restauracao(
            pacote,
            para,
            anteriores=list(anteriores),
            apenas=list(apenas) or None,
            sobrescrever=sobrescrever,
            protecao=protecao,
            dispensar_protecao=dispensar_protecao,
        )
    except ProtecaoBloqueou as erro:
        console.error(str(erro))
        console.info(
            "Nada foi alterado. Aponte a pasta de pacotes do destino com --protecao, "
            "ou use --dispensar-protecao MOTIVO para assumir a substituicao."
        )
        raise click.exceptions.Exit(_EXIT_FALHA) from None
    except RestauracaoRecusada as erro:
        console.error(str(erro))
        raise click.exceptions.Exit(_EXIT_FALHA) from None

    _relatar(console, relatorio)

    console.info("")
    if relatorio.completa:
        console.success(
            f"Restauracao concluida: {len(relatorio.restaurados)} arquivo(s) conferem "
            "com o manifesto."
        )
        return

    console.error("Restauracao INCOMPLETA: veja acima o que ficou de fora.")
    raise click.exceptions.Exit(_EXIT_INCOMPLETA)


__all__ = ["restaurar"]
