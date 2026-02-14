"""
Comandos de Limpeza do AutoTarefas.

Gerencia limpeza de arquivos temporários e “lixo” com perfis configuráveis.

Uso:
    $ autotarefas clean run /tmp
    $ autotarefas clean run ~/Downloads --profile downloads --days 90
    $ autotarefas clean preview /tmp
    $ autotarefas clean profiles
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from autotarefas.cli.utils.click_utils import get_console, is_dry_run
from autotarefas.core.logger import logger
from autotarefas.tasks.cleaner import CleanerTask, CleaningProfiles
from autotarefas.utils.helpers import safe_path

type PathArg = str | Path


# =============================================================================
# Helpers
# =============================================================================


def _normalize_paths(paths: tuple[Path, ...]) -> list[Path]:
    """
    Normaliza uma sequência de paths.

    - Expande "~"
    - Expande variáveis de ambiente
    - Resolve relativo (strict=False)
    """
    return [safe_path(p) for p in paths]


def _paths_for_task(paths: Iterable[Path]) -> list[PathArg]:
    """Converte Iterable[Path] em list[str|Path] (compatível com CleanerTask)."""
    return list(paths)


def _normalize_extensions(exts: tuple[str, ...]) -> list[str] | None:
    """
    Normaliza extensões (override de perfil).

    - Remove vazios
    - Garante "." no início
    - Remove duplicadas preservando ordem

    Retorna None se não houver extensões válidas.
    """
    seen: set[str] = set()
    out: list[str] = []

    for e in exts:
        e = (e or "").strip()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        e = e.lower()

        if e in seen:
            continue
        seen.add(e)
        out.append(e)

    return out or None


def _print_header(console: Console, title: str) -> None:
    """Header padrão dos comandos CLI."""
    console.print()
    console.print(
        Panel.fit(f"[bold blue]AutoTarefas[/] - {title}", border_style="blue")
    )
    console.print()


def _show_preview(console: Console, preview: dict[str, Any]) -> None:
    """
    Exibe resultado do preview.

    Espera que `preview` contenha:
      - files (list[dict])
      - files_count (int)
      - total_size_formatted (str)
      - profile (str | None)
    """
    files = preview.get("files", []) or []
    count = int(preview.get("files_count", 0) or 0)
    total_size = str(preview.get("total_size_formatted", "0 B"))
    profile = preview.get("profile")

    if count <= 0 or not files:
        console.print("[green]✅ Nenhum arquivo encontrado para limpeza.[/]")
        console.print()
        return

    if profile:
        console.print(f"[bold]Perfil:[/] {profile}")
    console.print(f"[bold]Arquivos encontrados:[/] {count}")
    console.print(f"[bold]Espaço a liberar (estimado):[/] {total_size}")
    console.print()

    table = Table(
        title="Arquivos a Remover (amostra)", show_header=True, header_style="bold cyan"
    )
    table.add_column("#", style="dim", justify="right")
    table.add_column("Arquivo", style="cyan", overflow="fold")
    table.add_column("Tamanho", justify="right")

    for i, item in enumerate(files[:20], 1):
        table.add_row(
            str(i),
            str(item.get("path", "")),
            str(item.get("size_formatted", "?")),
        )

    console.print(table)

    if count > 20:
        console.print(f"[dim]... e mais {count - 20} arquivo(s).[/]")

    console.print()
    console.print("[dim]Use 'autotarefas clean run ...' para executar a remoção.[/]")
    console.print()


def _confirm_run(console: Console, preview: dict[str, Any]) -> bool:
    """
    Confirma execução baseada no preview (padrão seguro).

    Se não houver nada para limpar, retorna False.
    """
    count = int(preview.get("files_count", 0) or 0)
    total = str(preview.get("total_size_formatted", "0 B"))

    if count <= 0:
        console.print("[green]✅ Nada para limpar.[/]")
        console.print()
        return False

    console.print(
        Panel(
            f"[bold]Preview da limpeza[/]\n"
            f"• Arquivos: [cyan]{count}[/]\n"
            f"• Espaço estimado: [cyan]{total}[/]\n\n"
            "Deseja executar a limpeza agora?",
            title="[bold]Confirmação[/]",
            border_style="yellow",
        )
    )
    return click.confirm("Confirmar limpeza?", default=False)


# =============================================================================
# Grupo
# =============================================================================


@click.group()
@click.pass_context
def clean(ctx: click.Context) -> None:
    """
    🧹 Limpa arquivos temporários e lixo.

    Comandos para limpeza de arquivos com perfis configuráveis.
    """
    ctx.ensure_object(dict)


# =============================================================================
# clean run
# =============================================================================


@clean.command("run")
@click.argument(
    "paths",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, path_type=Path, file_okay=False, dir_okay=True),
)
@click.option(
    "-p",
    "--profile",
    type=click.Choice(CleaningProfiles.list_profiles(), case_sensitive=False),
    default="temp_files",
    show_default=True,
    help="Perfil de limpeza",
)
@click.option(
    "-d",
    "--days",
    "min_age_days",
    type=int,
    default=None,
    help="Idade mínima em dias para limpeza (override do perfil)",
)
@click.option(
    "-e",
    "--extension",
    "extensions",
    multiple=True,
    help="Extensões a remover (ex: -e .tmp -e .log). Override do perfil.",
)
@click.option(
    "--no-recursive", is_flag=True, default=False, help="Não limpa subdiretórios"
)
@click.option(
    "--keep-empty-dirs",
    is_flag=True,
    default=False,
    help="Não remove diretórios vazios",
)
@click.option(
    "--max-files",
    type=int,
    default=200_000,
    show_default=True,
    help="Limite de arquivos inspecionados por diretório (proteção)",
)
@click.pass_context
def clean_run(
    ctx: click.Context,
    paths: tuple[Path, ...],
    profile: str,
    min_age_days: int | None,
    extensions: tuple[str, ...],
    no_recursive: bool,
    keep_empty_dirs: bool,
    max_files: int,
) -> None:
    """
    🚀 Executa limpeza de arquivos.

    PATHS: Diretórios para limpar (um ou mais).

    Exemplos:
        autotarefas clean run /tmp
        autotarefas clean run /tmp ~/.cache --profile cache_files
        autotarefas clean run ~/Downloads --profile downloads --days 30
        autotarefas clean run /var/log -e .log -e .log.1 --days 7
    """
    console = get_console(ctx)
    dry = is_dry_run(ctx)

    _print_header(console, "Limpeza")

    norm_paths = _normalize_paths(paths)
    norm_paths_for_task = _paths_for_task(norm_paths)
    norm_exts = _normalize_extensions(extensions)

    console.print(f"[bold]Diretórios:[/] {', '.join(str(p) for p in norm_paths)}")
    console.print(f"[bold]Perfil:[/] {profile}")
    if min_age_days is not None:
        console.print(f"[bold]Idade mínima (override):[/] {min_age_days} dias")
    if norm_exts:
        console.print(f"[bold]Extensões (override):[/] {', '.join(norm_exts)}")
    console.print(f"[bold]Recursivo:[/] {'Não' if no_recursive else 'Sim'}")
    console.print(
        f"[bold]Remover dirs vazios:[/] {'Não' if keep_empty_dirs else 'Sim'}"
    )
    console.print(f"[bold]Max files:[/] {max_files:,}")
    console.print()

    task = CleanerTask()

    # Dry-run: faz preview e sai (sem alterações)
    if dry:
        console.print(
            "[yellow]🔍 Modo dry-run: executando preview (nada será removido).[/]"
        )
        console.print()

        preview = task.preview(paths=norm_paths_for_task, profile=profile)
        _show_preview(console, preview)
        return

    # Preview + confirmação
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Calculando preview...", total=None)
        preview = task.preview(paths=norm_paths_for_task, profile=profile)

    _show_preview(console, preview)

    if not _confirm_run(console, preview):
        console.print("[dim]Operação cancelada.[/]")
        console.print()
        return

    # Execução real
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Limpando arquivos...", total=None)
        result = task.run(
            paths=norm_paths_for_task,
            profile=profile,
            min_age_days=min_age_days,
            extensions=norm_exts,  # None se não houver override
            recursive=not no_recursive,
            remove_empty_dirs=not keep_empty_dirs,
            max_files=max_files,
        )

    console.print()

    if result.is_success:
        data = result.data or {}
        console.print(
            Panel(
                f"[green]✅ Limpeza concluída![/]\n\n"
                f"[bold]Arquivos removidos:[/] {int(data.get('files_removed', 0) or 0)}\n"
                f"[bold]Diretórios removidos:[/] {int(data.get('dirs_removed', 0) or 0)}\n"
                f"[bold]Espaço liberado:[/] {data.get('bytes_freed_formatted', '0 B')}\n"
                f"[bold]Duração:[/] {result.duration_formatted}",
                title="[bold]Limpeza Concluída[/]",
                border_style="green",
            )
        )

        skipped_count = int(data.get("skipped_count", 0) or 0)
        errors_count = int(data.get("errors_count", 0) or 0)
        if skipped_count > 0:
            console.print(f"[yellow]⚠️  {skipped_count} item(ns) foram pulados.[/]")
        if errors_count > 0:
            console.print(
                f"[yellow]⚠️  {errors_count} erro(s) ocorreram durante a limpeza.[/]"
            )
    else:
        console.print(
            Panel(
                f"[red]❌ Falha na limpeza[/]\n\n[bold]Erro:[/] {result.message}",
                title="[bold]Erro[/]",
                border_style="red",
            )
        )
        logger.error(f"[cli][cleaner] Falha na limpeza: {result.message}")

    console.print()


# =============================================================================
# clean preview
# =============================================================================


@clean.command("preview")
@click.argument(
    "paths",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, path_type=Path, file_okay=False, dir_okay=True),
)
@click.option(
    "-p",
    "--profile",
    type=click.Choice(CleaningProfiles.list_profiles(), case_sensitive=False),
    default="temp_files",
    show_default=True,
    help="Perfil de limpeza",
)
@click.pass_context
def clean_preview(ctx: click.Context, paths: tuple[Path, ...], profile: str) -> None:
    """
    🔍 Visualiza o que seria limpo (sem remover).

    Exemplos:
        autotarefas clean preview /tmp
        autotarefas clean preview ~/Downloads --profile downloads
    """
    console = get_console(ctx)

    _print_header(console, "Preview de Limpeza")

    norm_paths = _normalize_paths(paths)
    norm_paths_for_task = _paths_for_task(norm_paths)

    console.print(f"[bold]Diretórios:[/] {', '.join(str(p) for p in norm_paths)}")
    console.print(f"[bold]Perfil:[/] {profile}")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Analisando arquivos...", total=None)
        task = CleanerTask()
        preview = task.preview(paths=norm_paths_for_task, profile=profile)

    _show_preview(console, preview)


# =============================================================================
# clean profiles
# =============================================================================


@clean.command("profiles")
@click.pass_context
def clean_profiles(ctx: click.Context) -> None:
    """
    📋 Lista perfis de limpeza disponíveis.
    """
    console = get_console(ctx)

    _print_header(console, "Perfis de Limpeza")

    table = Table(
        title="Perfis Disponíveis", show_header=True, header_style="bold cyan"
    )
    table.add_column("Nome", style="cyan")
    table.add_column("Descrição")

    for name in CleaningProfiles.list_profiles():
        # Se você tiver descrição no seu CleaningProfiles, substitua aqui.
        table.add_row(name, "Perfil de limpeza")

    console.print(table)
    console.print()
    console.print("[bold]Uso:[/]")
    console.print("  autotarefas clean run /path --profile [nome_do_perfil]")
    console.print()


__all__ = ["clean"]
