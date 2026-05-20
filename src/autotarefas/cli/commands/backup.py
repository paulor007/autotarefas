"""
Comando ``backup``: compacta arquivos/pastas em ZIP com hash SHA-256.

Uso:
    # Backup simples
    autotarefas backup pasta --output backup.zip

    # Multiplas fontes
    autotarefas backup pasta1 pasta2 arquivo.txt --output full.zip

    # Excludes adicionais
    autotarefas backup projeto --output proj.zip \\
        --exclude "*.log" --exclude "tmp/*"

    # Sem excludes padrao (inclui __pycache__, .git, etc)
    autotarefas backup projeto --output proj.zip --no-default-excludes

    # Modo simulacao (nao cria ZIP)
    autotarefas --dry-run backup projeto --output proj.zip
"""

from __future__ import annotations

from pathlib import Path

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.core.base import TaskStatus
from autotarefas.tasks.backup import BackupTask

# ============================================================
# Helpers de formatacao
# ============================================================

#: Quantos arquivos do preview mostrar em dry-run.
_DRY_RUN_PREVIEW_COUNT = 5

#: Limites para formatacao de tamanho.
_KB = 1024
_MB = _KB * 1024
_GB = _MB * 1024


def _format_size(bytes_count: int) -> str:
    """
    Formata bytes em unidade legivel (B, KB, MB, GB).

    Examples:
        >>> _format_size(500)
        '500 B'
        >>> _format_size(2048)
        '2.0 KB'
        >>> _format_size(5_242_880)
        '5.0 MB'
    """
    if bytes_count < _KB:
        return f"{bytes_count} B"
    if bytes_count < _MB:
        return f"{bytes_count / _KB:.1f} KB"
    if bytes_count < _GB:
        return f"{bytes_count / _MB:.1f} MB"
    return f"{bytes_count / _GB:.2f} GB"


# ============================================================
# Comando
# ============================================================


@click.command(name="backup")
@click.argument(
    "sources",
    nargs=-1,
    required=True,
    type=click.Path(
        exists=True,
        readable=True,
        path_type=Path,
    ),
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Caminho do arquivo ZIP de saida.",
)
@click.option(
    "--exclude",
    "-e",
    multiple=True,
    help="Padrao adicional de exclusao (fnmatch). Pode repetir.",
)
@click.option(
    "--no-default-excludes",
    is_flag=True,
    default=False,
    help=("Desabilita os padroes de exclusao default (__pycache__, .git, node_modules, etc)."),
)
@click.pass_obj
def backup(
    ctx: CLIContext,
    sources: tuple[Path, ...],
    output: Path,
    exclude: tuple[str, ...],
    no_default_excludes: bool,
) -> None:
    """Compacta SOURCES em um ZIP com hash SHA-256."""
    console = Console(ctx)

    # ============================================================
    # 1. Resumo da operacao
    # ============================================================
    n_sources = len(sources)
    plural_s = "s" if n_sources > 1 else ""
    console.info(f"Backup de {n_sources} source{plural_s} -> {output}")

    if exclude:
        console.info(f"Excludes adicionais: {', '.join(exclude)}")

    if no_default_excludes:
        console.warning(
            "Excludes padrao DESABILITADOS (__pycache__, .git, node_modules serao incluidos)."
        )

    console.info("")

    # ============================================================
    # 2. Executa a task (BaseTask faz audit automatico)
    # ============================================================
    task = BackupTask(
        sources=list(sources),
        destination=output,
        exclude_patterns=list(exclude) if exclude else None,
        include_default_excludes=not no_default_excludes,
        dry_run=ctx.dry_run,
    )
    result = task.run()

    # ============================================================
    # 3. Reporta resultado por status
    # ============================================================

    # 3a. SKIPPED — nada pra fazer (aviso, nao erro)
    if result.status == TaskStatus.SKIPPED:
        console.warning(f"Nada para fazer backup: {result.error_message or 'lista vazia'}")
        return  # exit 0

    # 3b. FAILURE — algo deu errado (source inexistente, I/O error)
    if result.is_failure:
        console.error(f"Backup falhou: {result.error_message}")
        raise click.exceptions.Exit(1)

    # 3c. DRY_RUN — mostra preview sem criar
    file_count = result.data["file_count"]
    skipped_count = result.data["skipped_count"]

    if result.status == TaskStatus.DRY_RUN:
        console.warning(f"[DRY-RUN] Backup NAO criado: {output}")
        console.info(f"Arquivos a incluir: {file_count}")
        console.info(f"Arquivos a excluir: {skipped_count}")

        files_preview = result.data.get("files_preview", [])
        if files_preview:
            console.info("")
            console.info("Preview dos primeiros arquivos:")
            for file_path in files_preview[:_DRY_RUN_PREVIEW_COUNT]:
                console.info(f"  - {file_path}")

            remaining = file_count - min(file_count, _DRY_RUN_PREVIEW_COUNT)
            if remaining > 0:
                console.info(f"  ... e mais {remaining}.")
        return  # exit 0

    # 3d. SUCCESS — backup criado
    size_str = _format_size(result.data["size_bytes"])
    sha256 = result.data["sha256"]

    console.success(f"Backup criado: {output}")
    console.info(f"Arquivos incluidos: {file_count}")
    if skipped_count > 0:
        console.info(f"Arquivos excluidos: {skipped_count}")
    console.info(f"Tamanho: {size_str}")
    console.info(f"SHA-256: {sha256}")


__all__ = ["backup"]
