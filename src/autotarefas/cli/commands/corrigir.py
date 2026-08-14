"""
Comando ``corrigir``: correcoes por regras confirmadas (RF-PLA-010).

A limpeza (`validate --mode limpeza`) corrige o que e seguro corrigir sem
perguntar. Este comando aplica o que **voce declarou** em um arquivo de
regras — e nada alem disso.

Arquivo de regras (YAML)::

    correcoes:
      - coluna: uf
        tipo: de_para
        mapa: {"sao paulo": SP, "rio de janeiro": RJ}
        fora_da_regra: revisao        # ou 'manter'
      - coluna: situacao
        tipo: padronizar
        valores: [Ativo, Inativo]
      - coluna: origem
        tipo: preencher
        valor: planilha

Uso:
    autotarefas corrigir base.xlsx --regras regras.yaml --out-dir out/

    # So conferir o que aconteceria
    autotarefas --dry-run corrigir base.xlsx --regras regras.yaml --out-dir out/

Valor que nao casa com a regra NAO e alterado: vai para
`itens_para_revisao.csv`. O arquivo de entrada nunca e modificado.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.markup import escape

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.core.exceptions import AutoTarefasError
from autotarefas.reader import read_workbook
from autotarefas.tasks.correction_artifacts import (
    corrected_frame,
    generate_summary,
    write_correction_artifacts,
)
from autotarefas.tasks.corrections import apply_rules, load_rules

_EXIT_USAGE = 2


@click.command(name="corrigir")
@click.argument(
    "arquivo",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
)
@click.option(
    "--regras",
    "-r",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    help="Arquivo YAML com as regras confirmadas (de_para, padronizar, preencher).",
)
@click.option(
    "--out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=(
        "Diretorio dos artefatos: planilha_corrigida.xlsx, planilha_corrigida.csv, "
        "itens_para_revisao.csv e correcoes_report.json."
    ),
)
@click.option("--sheet", type=str, default=None, help="Aba a corrigir (XLSX).")
@click.option(
    "--header-row",
    type=click.IntRange(min=1),
    default=None,
    help="Linha do cabecalho (numeracao do Excel).",
)
@click.option(
    "--max-linhas",
    "-m",
    type=click.IntRange(min=0),
    default=10,
    show_default=True,
    help="Maximo de itens listados por bloco no terminal.",
)
@click.option(
    "--falhar-se-revisao",
    is_flag=True,
    default=False,
    help="Sai com codigo 1 se algum valor ficar fora das regras declaradas.",
)
@click.pass_obj
def corrigir(
    ctx: CLIContext,
    arquivo: Path,
    regras: Path,
    out_dir: Path | None,
    sheet: str | None,
    header_row: int | None,
    max_linhas: int,
    falhar_se_revisao: bool,
) -> None:
    """Aplica correcoes declaradas em um arquivo de regras, sem inventar nada."""
    console = Console(ctx)

    try:
        catalogo = load_rules(regras)
    except AutoTarefasError as exc:
        console.error(f"Regras invalidas: {exc}")
        raise click.exceptions.Exit(_EXIT_USAGE) from exc

    leitura = read_workbook(arquivo, sheet=sheet, header_row=header_row)
    if not leitura.ok or leitura.original_dataframe is None:
        console.error(str(leitura.rejected_reason or "arquivo nao processado"))
        raise click.exceptions.Exit(_EXIT_USAGE)

    frame_original = leitura.original_dataframe
    colunas = [str(c) for c in frame_original.columns]
    linhas: list[dict[str, str]] = [
        {coluna: str(frame_original.iloc[posicao][coluna]) for coluna in colunas}
        for posicao in range(len(frame_original))
    ]

    corrigidas, resultado = apply_rules(linhas, catalogo, first_data_row=leitura.data_start_row)
    frame_corrigido = corrected_frame(corrigidas, colunas)

    console.info(f"Arquivo: {arquivo.name}  |  regras: {regras.name}")
    console.info("")
    console.info(escape(generate_summary(resultado, max_rows=max_linhas)))
    console.info("")

    if out_dir is not None:
        if ctx.dry_run:
            console.warning(f"[DRY-RUN] Geraria os artefatos das correcoes em: {out_dir}")
        else:
            try:
                caminhos = write_correction_artifacts(
                    arquivo,
                    out_dir,
                    resultado,
                    frame_corrigido,
                    header_row=leitura.header_row or 1,
                    sheet=leitura.selected_sheet if arquivo.suffix.lower() != ".csv" else None,
                    reader_conversions=len(leitura.conversions),
                )
            except (OSError, ValueError) as exc:
                console.error(f"Erro ao gerar artefatos: {exc}")
                raise click.exceptions.Exit(1) from exc
            for caminho in caminhos:
                console.success(f"Artefato: {caminho}")
            console.info("")

    pendentes = len(resultado.review)
    if pendentes == 0:
        console.success(
            f"{len(resultado.changes)} correcao(oes) aplicada(s); nada ficou fora das regras."
        )
        return

    if falhar_se_revisao:
        console.error(f"{pendentes} valor(es) fora das regras declaradas.")
        raise click.exceptions.Exit(1)
    console.warning(
        f"{pendentes} valor(es) fora das regras declaradas (veja itens_para_revisao.csv)."
    )


__all__ = ["corrigir"]
