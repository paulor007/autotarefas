"""
Comando ``transferir``: o PROCV com evidencia (RF-REC-003).

Preenche colunas de uma planilha com dados de outra — **so os campos que
voce autorizar**, em um arquivo NOVO, com relatorio de tudo o que foi
preenchido, atualizado e nao encontrado.

Uso:
    # Completa e-mail e telefone do cadastro a partir da base de origem
    autotarefas transferir cadastro.xlsx --de base_rh.xlsx --chave cpf \\
        --campo email --campo telefone --out-dir out/

    # So preenche o que estiver vazio (nunca sobrescreve o destino)
    autotarefas transferir cadastro.xlsx --de base_rh.xlsx --chave cpf \\
        --campo email --somente-vazios

    # Marca de onde veio cada valor (coluna _origem_<campo>)
    autotarefas transferir cadastro.xlsx --de base_rh.xlsx --chave cpf \\
        --campo email --marcar-origem --out-dir out/

Para juntar duas bases em uma so (consolidacao com coluna de origem), use
`autotarefas conciliar --manter-novos`.

O arquivo de destino nunca e sobrescrito.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.markup import escape

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.reconcile.compare import NORMALIZATION_OPTIONS
from autotarefas.reconcile.task import SourceSelection, TransferTask
from autotarefas.reconcile.tolerance import parse_tolerances
from autotarefas.reconcile.transfer import TransferPolicy, source_field_warnings
from autotarefas.reconcile.transfer_artifacts import generate_summary, write_transfer_artifacts

_EXIT_USAGE = 2

_ARQUIVO = click.Path(exists=True, dir_okay=False, readable=True, path_type=Path)


@click.command(name="transferir")
@click.argument("destino", type=_ARQUIVO)
@click.option(
    "--de",
    "fonte",
    required=True,
    type=_ARQUIVO,
    help="Planilha de ONDE os valores vem (a fonte).",
)
@click.option(
    "--chave",
    "-k",
    "chaves",
    multiple=True,
    required=True,
    help="Coluna que identifica o registro nos dois lados (repita para chave composta).",
)
@click.option(
    "--campo",
    "-c",
    "campos",
    multiple=True,
    required=True,
    help="Coluna AUTORIZADA a receber valor da fonte (repita). Nada fora desta lista muda.",
)
@click.option(
    "--somente-vazios",
    is_flag=True,
    default=False,
    help="So preenche onde o destino estiver vazio (nunca sobrescreve valor existente).",
)
@click.option(
    "--marcar-origem",
    is_flag=True,
    default=False,
    help="Acrescenta a coluna _origem_<campo> com o arquivo de onde veio o valor.",
)
@click.option(
    "--normalizar",
    "normalizacoes",
    multiple=True,
    type=click.Choice(NORMALIZATION_OPTIONS),
    help="Normaliza a chave para parear: espacos | caixa | digitos.",
)
@click.option(
    "--out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=(
        "Diretorio dos artefatos: planilha_enriquecida.xlsx, "
        "planilha_enriquecida.csv, nao_encontrados.csv e transferencia_report.json."
    ),
)
@click.option("--sheet-destino", type=str, default=None, help="Aba do destino (XLSX).")
@click.option("--sheet-fonte", type=str, default=None, help="Aba da fonte (XLSX).")
@click.option(
    "--max-linhas",
    "-m",
    type=click.IntRange(min=0),
    default=10,
    show_default=True,
    help="Maximo de itens listados por bloco no terminal.",
)
@click.option(
    "--falhar-se-nao-encontrado",
    is_flag=True,
    default=False,
    help="Sai com codigo 1 se algum registro do destino ficar sem correspondente.",
)
@click.pass_obj
def transferir(
    ctx: CLIContext,
    destino: Path,
    fonte: Path,
    chaves: tuple[str, ...],
    campos: tuple[str, ...],
    somente_vazios: bool,
    marcar_origem: bool,
    normalizacoes: tuple[str, ...],
    out_dir: Path | None,
    sheet_destino: str | None,
    sheet_fonte: str | None,
    max_linhas: int,
    falhar_se_nao_encontrado: bool,
) -> None:
    """Copia campos autorizados de uma planilha para outra, em arquivo novo."""
    console = Console(ctx)

    policy = TransferPolicy(
        fields=tuple(dict.fromkeys(campos)),
        only_empty=somente_vazios,
        mark_origin=marcar_origem,
    )

    task = TransferTask(
        SourceSelection(path=destino, sheet=sheet_destino),
        SourceSelection(path=fonte, sheet=sheet_fonte),
        key_columns=chaves,
        policy=policy,
        normalizations=normalizacoes,
        tolerances=parse_tolerances([]),
        dry_run=ctx.dry_run,
    )
    console.info(f"Transferindo de {fonte.name} para {destino.name}")
    console.info(f"Campos autorizados: {', '.join(policy.fields)}")
    console.info("")

    result = task.run()
    transferencia = task.transfer
    if result.is_failure or transferencia is None or task.table_b is None:
        console.error(str(result.error_message or "nao foi possivel transferir"))
        raise click.exceptions.Exit(_EXIT_USAGE)

    for aviso in source_field_warnings(task.table_b, policy):
        console.warning(aviso)

    console.info(escape(generate_summary(transferencia, max_rows=max_linhas)))
    console.info("")

    if out_dir is not None:
        if ctx.dry_run:
            console.warning(f"[DRY-RUN] Geraria os artefatos da transferencia em: {out_dir}")
        else:
            meta = {
                "task_name": result.task_name,
                "status": str(result.status),
                "started_at": result.started_at.isoformat(),
                "finished_at": result.finished_at.isoformat(),
                "duration_ms": result.duration_ms,
            }
            try:
                caminhos = write_transfer_artifacts(transferencia, out_dir, task.table_b, meta)
            except OSError as exc:
                console.error(f"Erro ao gerar artefatos: {exc}")
                raise click.exceptions.Exit(1) from exc
            for caminho in caminhos:
                console.success(f"Artefato: {caminho}")
            console.info("")

    faltando = len(transferencia.not_found)
    if faltando == 0:
        console.success(
            f"{transferencia.changed_count} campo(s) preenchido(s)/atualizado(s); "
            "todos os registros tinham correspondente."
        )
        return

    if falhar_se_nao_encontrado:
        console.error(f"{faltando} registro(s) do destino sem correspondente na fonte.")
        raise click.exceptions.Exit(1)
    console.warning(
        f"{faltando} registro(s) do destino sem correspondente na fonte (veja nao_encontrados.csv)."
    )


__all__ = ["transferir"]
