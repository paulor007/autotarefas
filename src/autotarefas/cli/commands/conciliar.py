"""
Comando ``conciliar``: das diferencas para a decisao (RF-REC-002).

O ``comparar`` diz o que mudou. O ``conciliar`` responde **qual valor
vale** — sempre por regra declarada por quem conhece o negocio:

- ``--principal a|b``  qual base manda;
- ``--atualizar COL``  quais campos a outra base pode atualizar (repetivel);
- ``--tolerancia``     o que nao conta como diferenca (1 centavo, 1%, 2 dias);
- ``--manter-novos/--revisar-novos`` o que fazer com registro que so existe
  na base complementar.

Divergencia em campo NAO autorizado nunca e resolvida sozinha: o valor da
fonte principal e preservado e o caso vai para `conflitos_para_revisao.xlsx`.

Uso:
    autotarefas conciliar sistema.xlsx planilha.xlsx --chave codigo \\
        --principal a --atualizar valor --tolerancia "valor=0,01" \\
        --out-dir out/

Leitura pura: as duas fontes sao apenas lidas; a base conciliada e um
arquivo NOVO.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.markup import escape

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.reconcile.compare import NORMALIZATION_OPTIONS
from autotarefas.reconcile.errors import CompareError
from autotarefas.reconcile.merge import ReconcilePolicy
from autotarefas.reconcile.merge_artifacts import (
    generate_summary,
    write_reconciliation_artifacts,
)
from autotarefas.reconcile.task import ReconciliationTask, SourceSelection
from autotarefas.reconcile.tolerance import parse_tolerances

_EXIT_USAGE = 2

_ARQUIVO = click.Path(exists=True, dir_okay=False, readable=True, path_type=Path)


@click.command(name="conciliar")
@click.argument("arquivo_a", type=_ARQUIVO)
@click.argument("arquivo_b", type=_ARQUIVO)
@click.option(
    "--chave",
    "-k",
    "chaves",
    multiple=True,
    required=True,
    help="Coluna que identifica o registro (repita para chave composta).",
)
@click.option(
    "--principal",
    type=click.Choice(["a", "b"]),
    default="a",
    show_default=True,
    help="Qual fonte manda quando as duas tem o registro.",
)
@click.option(
    "--atualizar",
    "atualizaveis",
    multiple=True,
    help=(
        "Coluna que a fonte complementar PODE atualizar na principal (repetivel). "
        "Fora desta lista, nada e alterado automaticamente."
    ),
)
@click.option(
    "--tolerancia",
    "tolerancias",
    multiple=True,
    help=(
        "O que nao conta como diferenca: 'coluna=0,01' (absoluta), "
        "'coluna=1%' (percentual) ou 'coluna=2d' (dias)."
    ),
)
@click.option(
    "--normalizar",
    "normalizacoes",
    multiple=True,
    type=click.Choice(NORMALIZATION_OPTIONS),
    help="Ignora diferencas de forma na comparacao: espacos | caixa | digitos.",
)
@click.option(
    "--manter-novos/--revisar-novos",
    "manter_novos",
    default=True,
    show_default=True,
    help=(
        "Registro que so existe na fonte complementar entra na base conciliada "
        "(--manter-novos) ou vai para revisao (--revisar-novos)."
    ),
)
@click.option(
    "--out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=(
        "Diretorio dos artefatos: base_conciliada.xlsx, base_conciliada.csv, "
        "conflitos_para_revisao.xlsx e reconciliacao_report.json."
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
    help="Maximo de itens listados por bloco no terminal.",
)
@click.option(
    "--falhar-se-revisao",
    is_flag=True,
    default=False,
    help="Sai com codigo 1 se sobrar qualquer caso para revisao (para pipelines).",
)
@click.pass_obj
def conciliar(
    ctx: CLIContext,
    arquivo_a: Path,
    arquivo_b: Path,
    chaves: tuple[str, ...],
    principal: str,
    atualizaveis: tuple[str, ...],
    tolerancias: tuple[str, ...],
    normalizacoes: tuple[str, ...],
    manter_novos: bool,
    out_dir: Path | None,
    sheet_a: str | None,
    sheet_b: str | None,
    header_row_a: int | None,
    header_row_b: int | None,
    max_linhas: int,
    falhar_se_revisao: bool,
) -> None:
    """Reconcilia duas planilhas por regras declaradas e gera a base conciliada."""
    console = Console(ctx)

    try:
        tolerancias_lidas = parse_tolerances(list(tolerancias))
    except CompareError as exc:
        console.error(str(exc))
        raise click.exceptions.Exit(_EXIT_USAGE) from exc

    # click.Choice garante o literal 'a'/'b' esperado pela politica.
    policy = ReconcilePolicy(
        primary=principal,  # type: ignore[arg-type]
        updatable_columns=tuple(dict.fromkeys(atualizaveis)),
        include_new=manter_novos,
    )

    task = ReconciliationTask(
        SourceSelection(path=arquivo_a, sheet=sheet_a, header_row=header_row_a),
        SourceSelection(path=arquivo_b, sheet=sheet_b, header_row=header_row_b),
        key_columns=chaves,
        policy=policy,
        normalizations=normalizacoes,
        tolerances=tolerancias_lidas,
        dry_run=ctx.dry_run,
    )
    console.info(f"Conciliando: {arquivo_a.name}  x  {arquivo_b.name}")
    console.info(f"Politica: {policy.describe()}")
    console.info("")

    result = task.run()
    conciliacao = task.reconciliation
    if result.is_failure or conciliacao is None:
        console.error(str(result.error_message or "nao foi possivel conciliar os arquivos"))
        raise click.exceptions.Exit(_EXIT_USAGE)

    console.info(escape(generate_summary(conciliacao, max_rows=max_linhas)))
    console.info("")

    if out_dir is not None:
        if ctx.dry_run:
            console.warning(f"[DRY-RUN] Geraria os artefatos da conciliacao em: {out_dir}")
        else:
            meta = {
                "task_name": result.task_name,
                "status": str(result.status),
                "started_at": result.started_at.isoformat(),
                "finished_at": result.finished_at.isoformat(),
                "duration_ms": result.duration_ms,
            }
            try:
                caminhos = write_reconciliation_artifacts(conciliacao, out_dir, meta)
            except OSError as exc:
                console.error(f"Erro ao gerar artefatos: {exc}")
                raise click.exceptions.Exit(1) from exc
            for caminho in caminhos:
                console.success(f"Artefato: {caminho}")
            console.info("")

    pendentes = len(conciliacao.review)
    if pendentes == 0:
        console.success("Base conciliada sem pendencias: todas as decisoes couberam nas regras.")
        return

    if falhar_se_revisao:
        console.error(f"{pendentes} caso(s) exigem revisao humana.")
        raise click.exceptions.Exit(1)
    console.warning(f"{pendentes} caso(s) exigem revisao humana (veja o arquivo de revisao).")


__all__ = ["conciliar"]
