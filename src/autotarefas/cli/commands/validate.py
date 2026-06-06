"""
Comando ``validate``: valida planilha CSV/Excel contra schema YAML.

Conecta todos os componentes da Fase 3:
- ``load_schema()`` carrega as regras do YAML
- ``ValidateTask`` executa a validacao (com audit automatico via BaseTask)
- ``write_json_report()`` / ``write_csv_report()`` salvam os relatorios
- ``generate_summary()`` mostra resumo no terminal
- ``Console`` (Rich) da feedback colorido

Uso:
    # Basico — so terminal
    autotarefas validate dados.csv --schema schema.yaml

    # Com relatorios em arquivo
    autotarefas validate dados.csv --schema schema.yaml \\
        --report-json out/rel.json --report-csv out/rel.csv

    # CI/CD: tratar warnings como erros
    autotarefas validate dados.csv --schema schema.yaml --strict-warnings

    # Modo simulacao (nao salva relatorios)
    autotarefas --dry-run validate dados.csv --schema schema.yaml
"""

from __future__ import annotations

from pathlib import Path

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.core.exceptions import AutoTarefasError
from autotarefas.tasks.report import (
    generate_summary,
    write_csv_report,
    write_json_report,
)
from autotarefas.tasks.validate import ValidateTask, load_schema


@click.command(name="validate")
@click.argument(
    "arquivo",
    type=click.Path(
        exists=True,
        dir_okay=False,
        readable=True,
        path_type=Path,
    ),
)
@click.option(
    "--schema",
    "-s",
    required=True,
    type=click.Path(
        exists=True,
        dir_okay=False,
        readable=True,
        path_type=Path,
    ),
    help="Schema YAML com as regras de validacao.",
)
@click.option(
    "--report-json",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Salva relatorio detalhado em JSON.",
)
@click.option(
    "--report-csv",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Salva relatorio compacto em CSV (Excel-friendly).",
)
@click.option(
    "--max-issues",
    "-m",
    type=click.IntRange(min=0),
    default=10,
    show_default=True,
    help="Maximo de issues a listar no terminal.",
)
@click.option(
    "--strict-warnings",
    is_flag=True,
    default=False,
    help="Trata warnings como erros (exit 1 mesmo so com warnings).",
)
@click.pass_obj
def validate(  # noqa: PLR0912
    ctx: CLIContext,
    arquivo: Path,
    schema: Path,
    report_json: Path | None,
    report_csv: Path | None,
    max_issues: int,
    strict_warnings: bool,
) -> None:
    """Valida planilha CSV/Excel contra schema YAML."""
    console = Console(ctx)

    # ============================================================
    # 1. Carrega o schema
    # ============================================================
    console.info(f"Carregando schema: {schema}")
    try:
        schema_obj = load_schema(schema)
    except AutoTarefasError as e:
        console.error(f"Erro ao carregar schema: {e}")
        raise click.exceptions.Exit(2) from e

    n_cols = len(schema_obj.columns)
    console.info(f"Schema carregado: {n_cols} coluna(s) declarada(s).")
    console.info("")

    # ============================================================
    # 2. Executa a validacao
    # ============================================================
    console.info(f"Validando arquivo: {arquivo}")

    task = ValidateTask(
        file_path=arquivo,
        schema=schema_obj,
        dry_run=ctx.dry_run,
    )
    # BaseTask.run() ja registra audit automaticamente — nao precisamos
    # chamar audit.record() manualmente aqui.
    result = task.run()
    console.info("")

    # ============================================================
    # 3. Gera relatorios em arquivo (se solicitado)
    # ============================================================
    if report_json is not None:
        if ctx.dry_run:
            console.warning(f"[DRY-RUN] Salvaria JSON em: {report_json}")
        else:
            try:
                write_json_report(result, report_json)
                console.success(f"Relatorio JSON salvo: {report_json}")
            except OSError as e:
                console.error(f"Erro ao salvar JSON: {e}")

    if report_csv is not None:
        if ctx.dry_run:
            console.warning(f"[DRY-RUN] Salvaria CSV em: {report_csv}")
        else:
            try:
                write_csv_report(result, report_csv)
                console.success(f"Relatorio CSV salvo: {report_csv}")
            except OSError as e:
                console.error(f"Erro ao salvar CSV: {e}")

    if report_json is not None or report_csv is not None:
        console.info("")

    # ============================================================
    # 4. Mostra resumo no terminal
    # ============================================================
    summary = generate_summary(result, max_issues_shown=max_issues)
    console.info(summary)
    console.info("")

    # ============================================================
    # 5. Status final + exit code
    # ============================================================
    total_errors = result.data.get("total_errors", 0)
    total_warnings = result.data.get("total_warnings", 0)

    if result.is_success and total_warnings == 0:
        console.success("Validacao OK!")
        return  # exit 0

    if result.is_success and total_warnings > 0:
        # Tem warnings mas nao errors
        if strict_warnings:
            console.error(f"Validacao falhou: {total_warnings} aviso(s) (strict-warnings ativo).")
            raise click.exceptions.Exit(1)

        console.warning(f"Validacao OK com {total_warnings} aviso(s).")
        return  # exit 0

    # Falha — tem errors
    console.error(f"Validacao falhou: {total_errors} erro(s).")
    raise click.exceptions.Exit(1)


__all__ = ["validate"]
