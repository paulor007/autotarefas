"""
Comandos CLI para organização de arquivos.

O QUE ESTE MÓDULO FAZ:
======================
Fornece comandos de terminal para organizar arquivos em pastas por tipo.

COMANDOS DISPONÍVEIS:
=====================
    autotarefas organize run <path>      - Organiza arquivos
    autotarefas organize preview <path>  - Mostra o que seria feito (dry-run)
    autotarefas organize rules           - Lista regras de organização

EXEMPLOS:
=========
    # Organizar pasta Downloads
    autotarefas organize run ~/Downloads

    # Ver preview antes de organizar
    autotarefas organize preview ~/Downloads

    # Organizar por data
    autotarefas organize run ~/Downloads --profile by_date

    # Incluir subpastas
    autotarefas organize run ~/Downloads --recursive
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# =============================================================================
# HELPERS
# =============================================================================


def get_console(ctx: click.Context) -> Console:
    """Obtém console do contexto."""
    return ctx.obj.get("console", Console()) if ctx.obj else Console()


def is_dry_run(ctx: click.Context) -> bool:
    """Verifica se está em modo dry-run."""
    return ctx.obj.get("dry_run", False) if ctx.obj else False


def _help_callback(
    ctx: click.Context,
    _param: click.Parameter,
    value: bool,
) -> None:
    """Callback para opção --help."""
    if value:
        click.echo(ctx.get_help())
        ctx.exit()


def _format_size(size: int | float) -> str:
    """Formata tamanho em bytes para exibição."""
    size_float = float(size)
    for unit in ["B", "KB", "MB", "GB"]:
        if size_float < 1024:
            return f"{size_float:.1f} {unit}"
        size_float /= 1024
    return f"{size_float:.1f} TB"


# =============================================================================
# GRUPO PRINCIPAL
# =============================================================================


@click.group("organize")
@click.pass_context
def organize(ctx: click.Context) -> None:
    """
    🗂️ Organiza arquivos em pastas por tipo.

    Separa automaticamente arquivos por categoria:
    Imagens, Documentos, Vídeos, Áudio, etc.

    \b
    Exemplos:
        autotarefas organize run ~/Downloads
        autotarefas organize preview ~/Downloads
        autotarefas organize rules
    """
    pass  # noqa: PIE790


# =============================================================================
# COMANDO: organize run
# =============================================================================


@organize.command("run")
@click.argument(
    "source",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
)
@click.option(
    "-d",
    "--dest",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Diretório de destino (default: mesmo que source)",
)
@click.option(
    "-p",
    "--profile",
    type=click.Choice(["default", "by_date", "by_extension", "custom"]),
    default="default",
    help="Perfil de organização",
)
@click.option(
    "-c",
    "--conflict",
    type=click.Choice(["skip", "overwrite", "rename"]),
    default="rename",
    help="Estratégia para arquivos duplicados",
)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help="Incluir subdiretórios",
)
@click.option(
    "--include-hidden",
    is_flag=True,
    help="Incluir arquivos ocultos (começam com .)",
)
@click.option(
    "-n",
    "--notify",
    is_flag=True,
    help="Enviar notificação após organização",
)
@click.option(
    "-h",
    "--help",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_help_callback,
    help="Mostra esta mensagem de ajuda",
)
@click.pass_context
def organize_run(
    ctx: click.Context,
    source: str,
    dest: str | None,
    profile: str,
    conflict: str,
    recursive: bool,
    include_hidden: bool,
    notify: bool,
) -> None:
    """
    🚀 Organiza arquivos em pastas por tipo.

    SOURCE: Diretório a ser organizado.

    \b
    Exemplos:
        autotarefas organize run ~/Downloads
        autotarefas organize run ~/Downloads -d ~/Organized
        autotarefas organize run ~/Downloads --profile by_date
        autotarefas organize run ~/Downloads --recursive
        autotarefas organize run ~/Downloads --notify
    """
    console = get_console(ctx)
    dry_run = is_dry_run(ctx)

    try:
        from autotarefas.tasks.organizer import OrganizerTask
    except ImportError as e:
        raise click.ClickException(f"Erro ao importar OrganizerTask: {e}") from e

    source_path = Path(source)

    # Header
    console.print()
    if dry_run:
        console.print(
            Panel(
                f"[yellow]DRY-RUN:[/] Simulando organização de [cyan]{source_path}[/]",
                title="🗂️ Organizar Arquivos",
                border_style="yellow",
            )
        )
    else:
        console.print(
            Panel(
                f"Organizando [cyan]{source_path}[/]",
                title="🗂️ Organizar Arquivos",
                border_style="blue",
            )
        )
    console.print()

    # Info
    console.print(f"[dim]Perfil:[/] {profile}")
    console.print(f"[dim]Conflitos:[/] {conflict}")
    console.print(f"[dim]Recursivo:[/] {'Sim' if recursive else 'Não'}")
    console.print(f"[dim]Notificar:[/] {'Sim' if notify else 'Não'}")
    if dest:
        console.print(f"[dim]Destino:[/] {dest}")
    console.print()

    # Executar
    task = OrganizerTask()

    with console.status("[cyan]Organizando arquivos...[/]"):
        result = task.run(
            source=source,
            dest=dest,
            profile=profile,
            conflict_strategy=conflict,
            recursive=recursive,
            include_hidden=include_hidden,
            dry_run=dry_run,
        )

    # Resultado
    if result.is_success or result.status.value == "skipped":
        data = result.data or {}

        # Tabela de categorias
        if data.get("categories_used"):
            table = Table(title="📁 Arquivos por Categoria", show_header=True)
            table.add_column("Categoria", style="cyan")
            table.add_column("Quantidade", justify="right", style="green")

            for category, count in sorted(data["categories_used"].items()):
                table.add_row(category, str(count))

            console.print(table)
            console.print()

        # Resumo
        moved = data.get("files_moved", 0)
        skipped = data.get("files_skipped", 0)
        renamed = data.get("files_renamed", 0)

        if dry_run:
            console.print(f"[yellow]DRY-RUN:[/] {moved} arquivos seriam organizados")
        else:
            console.print(f"[green]✅ {moved} arquivos organizados[/]")

        if skipped:
            console.print(f"[dim]   {skipped} arquivos pulados (já existiam)[/]")
        if renamed:
            console.print(f"[dim]   {renamed} arquivos renomeados (conflito)[/]")

        # Erros
        if data.get("errors"):
            console.print()
            console.print("[yellow]⚠️ Alguns erros ocorreram:[/]")
            for error in data["errors"][:5]:
                console.print(f"   [red]• {error}[/]")
            if len(data["errors"]) > 5:
                console.print(f"   [dim]... e mais {len(data['errors']) - 5} erros[/]")

        # Enviar notificação se solicitado
        if notify and not dry_run:
            _send_organize_notification(console, source_path, data)
    else:
        console.print(f"[red]❌ Erro: {result.message}[/]")
        raise click.ClickException(result.message)

    console.print()


def _send_organize_notification(
    console: Console,
    source_path: Path,
    data: dict,
) -> None:
    """Envia notificação após organização."""
    try:
        from autotarefas.core.notifier import NotificationLevel, get_notifier

        notifier = get_notifier()

        # Montar mensagem
        moved = data.get("files_moved", 0)
        categories = len(data.get("categories_used", {}))

        message = (
            f"Organização concluída: {moved} arquivos organizados "
            f"em {categories} categorias\n"
            f"Diretório: {source_path}"
        )

        # Detalhes das categorias
        if data.get("categories_used"):
            details = ", ".join(
                f"{cat}: {count}"
                for cat, count in sorted(data["categories_used"].items())
            )
            message += f"\n\nDetalhes: {details}"

        notifier.notify(
            message=message,
            title="🗂️ Organização Concluída",
            level=NotificationLevel.SUCCESS,
        )

        console.print("[dim]📧 Notificação enviada[/]")

    except Exception as e:
        console.print(f"[yellow]⚠️ Não foi possível enviar notificação: {e}[/]")


# =============================================================================
# COMANDO: organize preview
# =============================================================================


@organize.command("preview")
@click.argument(
    "source",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
)
@click.option(
    "-p",
    "--profile",
    type=click.Choice(["default", "by_date", "by_extension"]),
    default="default",
    help="Perfil de organização",
)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help="Incluir subdiretórios",
)
@click.option(
    "-h",
    "--help",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_help_callback,
    help="Mostra esta mensagem de ajuda",
)
@click.pass_context
def organize_preview(
    ctx: click.Context,
    source: str,
    profile: str,
    recursive: bool,
) -> None:
    """
    👁️ Mostra preview da organização (não move arquivos).

    SOURCE: Diretório a ser analisado.

    \b
    Exemplos:
        autotarefas organize preview ~/Downloads
        autotarefas organize preview ~/Downloads --profile by_date
    """
    console = get_console(ctx)

    try:
        from autotarefas.tasks.organizer import DEFAULT_EXTENSION_MAP, FileCategory
    except ImportError as e:
        raise click.ClickException(f"Erro ao importar: {e}") from e

    source_path = Path(source)

    # Header
    console.print()
    console.print(
        Panel(
            f"Preview de organização de [cyan]{source_path}[/]",
            title="👁️ Preview",
            border_style="blue",
        )
    )
    console.print()

    # Listar arquivos
    pattern = "**/*" if recursive else "*"
    files = [
        f
        for f in source_path.glob(pattern)
        if f.is_file() and not f.name.startswith(".")
    ]

    if not files:
        console.print("[yellow]Nenhum arquivo encontrado para organizar.[/]")
        console.print()
        return

    # Agrupar por categoria
    by_category: dict[str, list[Path]] = {}

    for file_path in files:
        ext = file_path.suffix.lower()

        if profile == "by_date":
            try:
                mtime = file_path.stat().st_mtime
                dt = datetime.fromtimestamp(mtime)
                category = f"{dt.year}/{dt.month:02d}"
            except Exception:
                category = "sem_data"
        elif profile == "by_extension":
            category = ext.lstrip(".") if ext else "sem_extensao"
        else:
            # Default - por tipo
            cat = DEFAULT_EXTENSION_MAP.get(ext, FileCategory.OTHERS)
            category = cat.value

        if category not in by_category:
            by_category[category] = []
        by_category[category].append(file_path)

    # Tabela de preview
    table = Table(
        title=f"📋 {len(files)} arquivos seriam organizados", show_header=True
    )
    table.add_column("Destino", style="cyan")
    table.add_column("Arquivos", justify="right", style="green")
    table.add_column("Exemplos", style="dim")

    for category in sorted(by_category.keys()):
        files_in_cat = by_category[category]
        examples = ", ".join(f.name for f in files_in_cat[:3])
        if len(files_in_cat) > 3:
            examples += f" ... (+{len(files_in_cat) - 3})"

        table.add_row(
            f"📁 {category}/",
            str(len(files_in_cat)),
            examples,
        )

    console.print(table)
    console.print()

    # Dica
    console.print("[dim]Para executar a organização, use:[/]")
    console.print(f"[dim]  autotarefas organize run {source}[/]")
    console.print()


# =============================================================================
# COMANDO: organize rules
# =============================================================================


@organize.command("rules")
@click.option(
    "-c",
    "--category",
    type=str,
    default=None,
    help="Filtrar por categoria (ex: Imagens, Documentos)",
)
@click.option(
    "-h",
    "--help",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_help_callback,
    help="Mostra esta mensagem de ajuda",
)
@click.pass_context
def organize_rules(
    ctx: click.Context,
    category: str | None,
) -> None:
    """
    📋 Lista regras de organização (extensões → pastas).

    Mostra quais extensões vão para quais pastas.

    \b
    Exemplos:
        autotarefas organize rules
        autotarefas organize rules --category Imagens
    """
    console = get_console(ctx)

    try:
        from autotarefas.tasks.organizer import DEFAULT_EXTENSION_MAP, FileCategory
    except ImportError as e:
        raise click.ClickException(f"Erro ao importar: {e}") from e

    # Header
    console.print()
    console.print(
        Panel(
            "Regras de organização de arquivos",
            title="📋 Regras",
            border_style="blue",
        )
    )
    console.print()

    # Agrupar por categoria
    by_category: dict[str, list[str]] = {}

    for ext, cat in DEFAULT_EXTENSION_MAP.items():
        cat_name = cat.value
        if category and cat_name.lower() != category.lower():
            continue

        if cat_name not in by_category:
            by_category[cat_name] = []
        by_category[cat_name].append(ext)

    if not by_category:
        if category:
            console.print(f"[yellow]Categoria '{category}' não encontrada.[/]")
            console.print()
            console.print("[dim]Categorias disponíveis:[/]")
            for cat in FileCategory:
                console.print(f"  • {cat.value}")
        else:
            console.print("[yellow]Nenhuma regra encontrada.[/]")
        console.print()
        return

    # Tabela de regras
    table = Table(show_header=True)
    table.add_column("📁 Categoria", style="cyan", width=15)
    table.add_column("Extensões", style="green")

    for cat_name in sorted(by_category.keys()):
        extensions = sorted(by_category[cat_name])
        ext_str = ", ".join(extensions)
        table.add_row(cat_name, ext_str)

    console.print(table)
    console.print()

    # Total
    total_ext = sum(len(exts) for exts in by_category.values())
    console.print(
        f"[dim]Total: {total_ext} extensões em {len(by_category)} categorias[/]"
    )
    console.print()


# =============================================================================
# COMANDO: organize stats
# =============================================================================


@organize.command("stats")
@click.argument(
    "source",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
)
@click.option(
    "-h",
    "--help",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_help_callback,
    help="Mostra esta mensagem de ajuda",
)
@click.pass_context
def organize_stats(
    ctx: click.Context,
    source: str,
) -> None:
    """
    📊 Mostra estatísticas de um diretório.

    SOURCE: Diretório a ser analisado.

    \b
    Exemplos:
        autotarefas organize stats ~/Downloads
    """
    console = get_console(ctx)

    try:
        from autotarefas.tasks.organizer import DEFAULT_EXTENSION_MAP, FileCategory
    except ImportError as e:
        raise click.ClickException(f"Erro ao importar: {e}") from e

    source_path = Path(source)

    # Header
    console.print()
    console.print(
        Panel(
            f"Estatísticas de [cyan]{source_path}[/]",
            title="📊 Estatísticas",
            border_style="blue",
        )
    )
    console.print()

    # Analisar arquivos
    files = list(source_path.glob("*"))
    files = [f for f in files if f.is_file()]

    if not files:
        console.print("[yellow]Nenhum arquivo encontrado.[/]")
        console.print()
        return

    # Estatísticas
    total_size = 0
    by_category: dict[str, dict[str, int]] = {}
    unknown_extensions: list[str] = []

    for file_path in files:
        try:
            size = file_path.stat().st_size
        except Exception:
            size = 0

        total_size += size
        ext = file_path.suffix.lower()

        cat = DEFAULT_EXTENSION_MAP.get(ext, FileCategory.OTHERS)
        cat_name = cat.value

        if cat_name not in by_category:
            by_category[cat_name] = {"count": 0, "size": 0}

        by_category[cat_name]["count"] += 1
        by_category[cat_name]["size"] += size

        if cat == FileCategory.OTHERS and ext and ext not in unknown_extensions:
            unknown_extensions.append(ext)

    # Tabela
    table = Table(title=f"📁 {len(files)} arquivos", show_header=True)
    table.add_column("Categoria", style="cyan")
    table.add_column("Arquivos", justify="right", style="green")
    table.add_column("Tamanho", justify="right", style="blue")
    table.add_column("%", justify="right", style="dim")

    for cat_name in sorted(by_category.keys()):
        stats = by_category[cat_name]
        pct = (stats["size"] / total_size * 100) if total_size > 0 else 0

        table.add_row(
            cat_name,
            str(stats["count"]),
            _format_size(stats["size"]),
            f"{pct:.1f}%",
        )

    console.print(table)
    console.print()

    # Total
    console.print(f"[bold]Total:[/] {len(files)} arquivos, {_format_size(total_size)}")

    # Extensões desconhecidas
    if unknown_extensions:
        console.print()
        console.print(
            f"[yellow]Extensões não mapeadas:[/] {', '.join(sorted(unknown_extensions)[:10])}"
        )
        if len(unknown_extensions) > 10:
            console.print(f"[dim]... e mais {len(unknown_extensions) - 10}[/]")

    console.print()


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "organize",
    "organize_run",
    "organize_preview",
    "organize_rules",
    "organize_stats",
]
