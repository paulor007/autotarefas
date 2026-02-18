"""
Comandos de Backup do AutoTarefas.

Gerencia backups de arquivos e diretórios.

Uso:
    $ autotarefas backup run /home/user/docs
    $ autotarefas backup run /home/user/docs -d /backups --compression tar.gz
    $ autotarefas backup list
    $ autotarefas backup restore backup_20240115.zip
    $ autotarefas backup cleanup
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from autotarefas.cli.utils.click_utils import get_console, is_dry_run
from autotarefas.config import settings
from autotarefas.core.logger import logger
from autotarefas.tasks.backup import (
    BackupManager,
    BackupTask,
    CompressionType,
    RestoreTask,
)
from autotarefas.utils.helpers import safe_path

# =============================================================================
# Helpers
# =============================================================================


def _print_header(console: Console, title: str) -> None:
    """Imprime um cabeçalho padrão para os comandos de backup."""
    console.print()
    console.print(
        Panel.fit(f"[bold blue]AutoTarefas[/] - {title}", border_style="blue")
    )
    console.print()


def _print_dry_run(console: Console, hint: str | None = None) -> None:
    """Mensagem padrão para modo dry-run."""
    console.print("[yellow]🔍 Modo dry-run: nenhuma alteração será feita.[/]")
    if hint:
        console.print(f"[dim]{hint}[/]")
    console.print()


def _normalize_excludes(exclude: tuple[str, ...]) -> list[str]:
    """Normaliza exclusões (remove vazios e espaços)."""
    out: list[str] = []
    for e in exclude:
        e = (e or "").strip()
        if e:
            out.append(e)
    return out


# =============================================================================
# Grupo
# =============================================================================


@click.group()
@click.pass_context
def backup(ctx: click.Context) -> None:
    """
    📦 Gerencia backups de arquivos e diretórios.

    Comandos para criar, listar, restaurar e limpar backups.
    """
    ctx.ensure_object(dict)


# =============================================================================
# backup run
# =============================================================================


@backup.command("run")
@click.argument(
    "source",
    type=click.Path(exists=True, path_type=Path, file_okay=True, dir_okay=True),
)
@click.argument(
    "dest",
    required=False,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option(
    "-d",
    "--dest",
    "dest_opt",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=None,
    help=f"Diretório de destino (default: {settings.backup.path})",
)
@click.option(
    "-c",
    "--compression",
    type=click.Choice([ct.value for ct in CompressionType], case_sensitive=False),
    default=CompressionType.ZIP.value,
    show_default=True,
    help="Tipo de compressão",
)
@click.option(
    "-e",
    "--exclude",
    multiple=True,
    help="Padrões a excluir (pode ser usado múltiplas vezes)",
)
@click.pass_context
def backup_run(
    ctx: click.Context,
    source: Path,
    dest: Path | None,
    dest_opt: Path | None,
    compression: str,
    exclude: tuple[str, ...],
) -> None:
    """
    🚀 Cria um backup.

    SOURCE: Arquivo ou diretório para fazer backup.

    Exemplos:
        autotarefas backup run ~/Documents
        autotarefas backup run ~/Documents -d /backups
        autotarefas backup run ~/project -c tar.gz -e __pycache__ -e .git
    """
    console = get_console(ctx)
    dry = is_dry_run(ctx)

    _print_header(console, "Backup")

    source_path = safe_path(source)
    dest_path = safe_path(dest_opt or dest or settings.backup.path)
    exclude_patterns = _normalize_excludes(exclude)

    # Validação amigável de compressão (evita traceback).
    try:
        compression_type = CompressionType.from_string(compression)
    except ValueError as e:
        raise click.ClickException(f"Compressão inválida: {compression}\n{e}") from None

    console.print(f"[bold]Origem:[/] {source_path}")
    console.print(f"[bold]Destino:[/] {dest_path}")
    console.print(f"[bold]Compressão:[/] {compression_type.value}")
    if exclude_patterns:
        console.print(f"[bold]Excluindo:[/] {', '.join(exclude_patterns)}")
    console.print()

    if dry:
        _print_dry_run(
            console, "Dica: rode sem --dry-run para criar o arquivo de backup."
        )
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Criando backup...", total=None)

        result = BackupTask().run(
            source=source_path,
            dest=dest_path,
            compression=compression_type.value,
            exclude_patterns=exclude_patterns,
        )

    if result.is_success:
        data = result.data or {}
        removed = int(data.get("old_backups_removed", 0) or 0)

        console.print()
        console.print(
            Panel(
                f"[green]✅ Backup criado com sucesso![/]\n\n"
                f"[bold]Arquivo:[/] {data.get('backup_path', 'N/A')}\n"
                f"[bold]Tamanho:[/] {data.get('size_formatted', 'N/A')}\n"
                f"[bold]Arquivos:[/] {data.get('files_count', 0)}\n"
                f"[bold]Duração:[/] {result.duration_formatted}",
                title="[bold]Backup Concluído[/]",
                border_style="green",
            )
        )

        if removed > 0:
            console.print(f"[dim]ℹ️  {removed} backup(s) antigo(s) removido(s).[/]")

        console.print()
        return

    console.print()
    console.print(
        Panel(
            f"[red]❌ Falha ao criar backup[/]\n\n[bold]Erro:[/] {result.message}",
            title="[bold]Erro[/]",
            border_style="red",
        )
    )
    logger.error(f"[cli][backup] Falha ao criar backup: {result.message}")
    console.print()


# =============================================================================
# backup list
# =============================================================================


@backup.command("list")
@click.argument(
    "backup_dir",
    type=click.Path(exists=True, path_type=Path, file_okay=False, dir_okay=True),
    default=None,
    required=False,
)
@click.option(
    "-n",
    "--name",
    default=None,
    help="Filtrar por nome do source",
)
@click.option(
    "-l",
    "--limit",
    default=20,
    help="Número máximo de backups a listar",
)
@click.pass_context
def backup_list(
    ctx: click.Context,
    backup_dir: Path | None,
    name: str | None,
    limit: int,
) -> None:
    """
    📋 Lista backups existentes.

    BACKUP_DIR: Diretório onde os backups estão armazenados (opcional).

    \b
    Exemplos:
        autotarefas backup list
        autotarefas backup list C:\\Temp\\backups
        autotarefas backup list /backups -n documents
    """
    console = get_console(ctx)

    _print_header(console, "Backups")

    backup_dir_path = safe_path(backup_dir or settings.backup.path)
    manager = BackupManager(backup_dir_path)
    backups = manager.list_backups(name)

    if not backups:
        console.print("[yellow]Nenhum backup encontrado.[/]")
        console.print()
        return

    table = Table(title=f"Backups em {backup_dir_path}")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Arquivo", style="cyan")
    table.add_column("Tamanho", justify="right")
    table.add_column("Data", style="green")
    table.add_column("Idade", justify="right")
    table.add_column("Tipo", justify="center")

    for i, b in enumerate(backups[: max(limit, 1)], 1):
        table.add_row(
            str(i),
            b.path.name,
            b.size_formatted,
            b.created_at.strftime("%d/%m/%Y %H:%M"),
            f"{b.age_days}d",
            b.compression.value,
        )

    console.print(table)

    if len(backups) > limit:
        console.print(f"[dim]... e mais {len(backups) - limit} backup(s)[/]")

    console.print()
    console.print(f"[bold]Total:[/] {len(backups)} backup(s)")
    console.print()


# =============================================================================
# backup restore
# =============================================================================


@backup.command("restore")
@click.argument(
    "backup_file",
    type=click.Path(exists=True, path_type=Path, dir_okay=False, file_okay=True),
)
@click.option(
    "-d",
    "--dest",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=None,
    help="Diretório de destino (default: diretório atual)",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Sobrescreve arquivos existentes",
)
@click.pass_context
def backup_restore(
    ctx: click.Context,
    backup_file: Path,
    dest: Path | None,
    force: bool,
) -> None:
    """
    ♻️  Restaura um backup.

    BACKUP_FILE: Arquivo de backup a restaurar.

    Exemplos:
        autotarefas backup restore backup_20240115.zip
        autotarefas backup restore backup.tar.gz -d ~/restored
        autotarefas backup restore backup.zip -f
    """
    console = get_console(ctx)
    dry = is_dry_run(ctx)

    _print_header(console, "Restauração de Backup")

    backup_path = safe_path(backup_file)
    dest_path = safe_path(dest or Path.cwd())

    console.print(f"[bold]Backup:[/] {backup_path}")
    console.print(f"[bold]Destino:[/] {dest_path}")
    console.print(f"[bold]Sobrescrever:[/] {'Sim' if force else 'Não'}")
    console.print()

    if dry:
        _print_dry_run(console)
        return

    # ✅ Correção: --force sobrescreve sem perguntar.
    # A confirmação (se existir) deve ser controlada por outra flag (ex.: --yes).

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Restaurando backup...", total=None)

        result = RestoreTask().run(
            backup_path=backup_path,
            dest=dest_path,
            overwrite=force,
        )

    if result.is_success:
        data = result.data or {}
        console.print()
        console.print(
            Panel(
                f"[green]✅ Backup restaurado com sucesso![/]\n\n"
                f"[bold]Destino:[/] {data.get('dest', str(dest_path))}\n"
                f"[bold]Arquivos:[/] {data.get('files_count', 0)}\n"
                f"[bold]Duração:[/] {result.duration_formatted}",
                title="[bold]Restauração Concluída[/]",
                border_style="green",
            )
        )
        console.print()
        return

    console.print()
    console.print(
        Panel(
            f"[red]❌ Falha ao restaurar backup[/]\n\n[bold]Erro:[/] {result.message}",
            title="[bold]Erro[/]",
            border_style="red",
        )
    )
    logger.error(f"[cli][backup] Falha ao restaurar backup: {result.message}")
    console.print()


# =============================================================================
# backup cleanup
# =============================================================================


@backup.command("cleanup")
@click.argument(
    "backup_dir",
    required=False,
    type=click.Path(exists=True, path_type=Path, file_okay=False, dir_okay=True),
)
@click.option(
    "-d",
    "--dir",
    "backup_dir_opt",
    type=click.Path(exists=True, path_type=Path, file_okay=False, dir_okay=True),
    default=None,
    help="Diretório de backups",
)
@click.option(
    "-n",
    "--name",
    default=None,
    help="Filtrar por nome do source",
)
@click.option(
    "-k",
    "--keep",
    type=int,
    default=None,
    help="Número de versões a manter (default: settings.backup.max_versions)",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    default=False,
    help="Não pede confirmação",
)
@click.pass_context
def backup_cleanup(
    ctx: click.Context,
    backup_dir: Path | None,
    backup_dir_opt: Path | None,
    name: str | None,
    keep: int | None,
    yes: bool,
) -> None:
    """
    🧹 Remove backups antigos.

    Mantém apenas as N versões mais recentes.

    Exemplos:
        autotarefas backup cleanup
        autotarefas backup cleanup -k 3
        autotarefas backup cleanup -n documents -k 5
    """
    console = get_console(ctx)
    dry = is_dry_run(ctx)

    _print_header(console, "Limpeza de Backups")

    max_versions = (
        keep if (keep is not None and keep >= 0) else settings.backup.max_versions
    )

    backup_dir_path = safe_path(backup_dir_opt or backup_dir or settings.backup.path)
    manager = BackupManager(
        backup_dir_path,
        max_versions=max_versions,
    )

    backups = manager.list_backups(name)
    to_remove = backups[manager.max_versions :]

    if not to_remove:
        console.print("[green]✅ Nenhum backup antigo para remover.[/]")
        console.print(
            f"[dim]Total de backups: {len(backups)} (mantendo {manager.max_versions}).[/]"
        )
        console.print()
        return

    console.print(
        f"[bold]Backups a remover:[/] {len(to_remove)} (mantendo {manager.max_versions})"
    )
    for b in to_remove[:50]:
        console.print(f"  - {b.path.name} ({b.size_formatted})")
    if len(to_remove) > 50:
        console.print(f"[dim]... e mais {len(to_remove) - 50} item(ns).[/]")
    console.print()

    if dry:
        _print_dry_run(console)
        return

    if (not yes) and (
        not Confirm.ask("Confirmar remoção dos backups antigos?", default=False)
    ):
        console.print("[dim]Operação cancelada.[/]")
        console.print()
        return

    removed = manager.cleanup_old_backups(name)

    console.print(f"[green]✅ {removed} backup(s) removido(s).[/]")
    console.print()


__all__ = ["backup"]
