"""
Comando ``comparar``: diferencas entre duas planilhas, por chave (RF-REC-001).

Responde a pergunta que hoje se responde abrindo as duas planilhas lado a
lado: **o que mudou da versao A para a versao B?**

Uso:
    # Basico — so o resumo no terminal
    autotarefas comparar base_janeiro.xlsx base_fevereiro.xlsx --chave codigo

    # Chave composta (a ordem das colunas nao importa)
    autotarefas comparar a.xlsx b.xlsx --chave codigo --chave filial

    # Comparando so o que interessa, ignorando espacos e caixa
    autotarefas comparar a.xlsx b.csv --chave codigo \\
        --coluna valor --coluna status --normalizar espacos --normalizar caixa

    # Com os quatro artefatos em disco
    autotarefas comparar a.xlsx b.xlsx --chave codigo --out-dir out/

    # Em pipeline: falha se as bases nao estiverem iguais
    autotarefas comparar a.xlsx b.xlsx --chave codigo --falhar-se-diferente

Leitura pura: nenhum dos dois arquivos e aberto para escrita.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.markup import escape

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.reconcile.artifacts import generate_summary, write_comparison_artifacts
from autotarefas.reconcile.compare import NORMALIZATION_OPTIONS
from autotarefas.reconcile.task import ComparisonTask, SourceSelection

#: Erro de uso: chave inexistente, arquivo ilegivel, aba impossivel.
#: Distinto do exit 1, que (com --falhar-se-diferente) significa
#: 'a comparacao rodou e as bases diferem'.
_EXIT_USAGE = 2

_ARQUIVO = click.Path(exists=True, dir_okay=False, readable=True, path_type=Path)


@click.command(name="comparar")
@click.argument("arquivo_a", type=_ARQUIVO)
@click.argument("arquivo_b", type=_ARQUIVO)
@click.option(
    "--chave",
    "-k",
    "chaves",
    multiple=True,
    required=True,
    help=(
        "Coluna que identifica o registro. Repita para chave composta "
        "(a ordem em que voce declara nao afeta o pareamento)."
    ),
)
@click.option(
    "--coluna",
    "-c",
    "colunas",
    multiple=True,
    default=None,
    help="Coluna a comparar. Sem isto, todas as colunas comuns as duas fontes.",
)
@click.option(
    "--normalizar",
    "normalizacoes",
    multiple=True,
    type=click.Choice(NORMALIZATION_OPTIONS),
    help=(
        "Ignora diferencas de forma na COMPARACAO (os valores do relatorio "
        "continuam sendo os do arquivo): espacos | caixa | digitos "
        "('digitos' vale so para a chave)."
    ),
)
@click.option(
    "--out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=(
        "Diretorio dos 4 artefatos: comparacao_report.json, divergencias.xlsx, "
        "somente_a.csv e somente_b.csv."
    ),
)
@click.option("--sheet-a", type=str, default=None, help="Aba da fonte A (XLSX).")
@click.option("--sheet-b", type=str, default=None, help="Aba da fonte B (XLSX).")
@click.option(
    "--header-row-a",
    type=click.IntRange(min=1),
    default=None,
    help="Linha do cabecalho em A (numeracao do Excel).",
)
@click.option(
    "--header-row-b",
    type=click.IntRange(min=1),
    default=None,
    help="Linha do cabecalho em B (numeracao do Excel).",
)
@click.option(
    "--max-linhas",
    "-m",
    type=click.IntRange(min=0),
    default=10,
    show_default=True,
    help="Maximo de registros listados por categoria no terminal.",
)
@click.option(
    "--falhar-se-diferente",
    is_flag=True,
    default=False,
    help="Sai com codigo 1 se houver qualquer diferenca ou conflito (para pipelines).",
)
@click.pass_obj
def comparar(
    ctx: CLIContext,
    arquivo_a: Path,
    arquivo_b: Path,
    chaves: tuple[str, ...],
    colunas: tuple[str, ...],
    normalizacoes: tuple[str, ...],
    out_dir: Path | None,
    sheet_a: str | None,
    sheet_b: str | None,
    header_row_a: int | None,
    header_row_b: int | None,
    max_linhas: int,
    falhar_se_diferente: bool,
) -> None:
    """Compara duas planilhas por chave e mostra o que difere entre elas."""
    console = Console(ctx)

    task = ComparisonTask(
        SourceSelection(path=arquivo_a, sheet=sheet_a, header_row=header_row_a),
        SourceSelection(path=arquivo_b, sheet=sheet_b, header_row=header_row_b),
        key_columns=chaves,
        columns=list(colunas) if colunas else None,
        normalizations=normalizacoes,
        dry_run=ctx.dry_run,
    )
    console.info(f"Comparando: {arquivo_a.name}  x  {arquivo_b.name}")
    console.info(f"Chave: {', '.join(sorted(dict.fromkeys(chaves)))}")
    console.info("")

    # BaseTask.run() converte CompareError em resultado de falha (e registra
    # no audit). Aqui isso e sempre erro de USO: o pedido nao se aplica a
    # estes arquivos, e nenhum artefato deve ser gerado.
    result = task.run()
    comparacao = task.comparison
    tabela_a, tabela_b = task.table_a, task.table_b
    if result.is_failure or comparacao is None or tabela_a is None or tabela_b is None:
        console.error(str(result.error_message or "nao foi possivel comparar os arquivos"))
        raise click.exceptions.Exit(_EXIT_USAGE)

    console.info(escape(generate_summary(comparacao, max_rows=max_linhas)))
    console.info("")

    if out_dir is not None:
        if ctx.dry_run:
            console.warning(f"[DRY-RUN] Geraria os 4 artefatos em: {out_dir}")
        else:
            meta = {
                "task_name": result.task_name,
                "status": str(result.status),
                "started_at": result.started_at.isoformat(),
                "finished_at": result.finished_at.isoformat(),
                "duration_ms": result.duration_ms,
            }
            try:
                caminhos = write_comparison_artifacts(
                    comparacao,
                    tabela_a,
                    tabela_b,
                    out_dir,
                    meta,
                )
            except OSError as exc:
                console.error(f"Erro ao gerar artefatos: {exc}")
                raise click.exceptions.Exit(1) from exc
            for caminho in caminhos:
                console.success(f"Artefato: {caminho}")
            console.info("")

    if not comparacao.has_differences:
        console.success("As bases estao equivalentes sob a chave informada.")
        return

    contagem = comparacao.counts
    resumo = (
        f"{contagem['divergente']} divergente(s), "
        f"{contagem['somente_a']} so em A, "
        f"{contagem['somente_b']} so em B, "
        f"{contagem['conflitos']} conflito(s) de chave."
    )
    if falhar_se_diferente:
        console.error(f"As bases diferem: {resumo}")
        raise click.exceptions.Exit(1)
    console.warning(f"As bases diferem: {resumo}")


__all__ = ["comparar"]
