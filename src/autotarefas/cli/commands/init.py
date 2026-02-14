"""
Comandos de inicialização do AutoTarefas.

Cria a estrutura básica de configuração do AutoTarefas (pastas e .env)
e exibe informações do ambiente.

Uso:
    $ autotarefas init
    $ autotarefas init --force
    $ autotarefas init --config ~/.autotarefas

    $ autotarefas info
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from autotarefas import __version__
from autotarefas.cli.utils.click_utils import get_console, is_dry_run
from autotarefas.config import settings
from autotarefas.utils.helpers import ensure_dir, safe_path

ENV_TEMPLATE: Final[
    str
] = """# ═══════════════════════════════════════════════════════════════
# AutoTarefas - Configuração
# Gerado automaticamente pela CLI
# ═══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────
# Ambiente
# ─────────────────────────────────────────────────────────────────
ENVIRONMENT=development
DEBUG=true

# ─────────────────────────────────────────────────────────────────
# Caminhos
# ─────────────────────────────────────────────────────────────────
LOG_PATH={log_path}
TEMP_PATH={temp_path}
REPORTS_PATH={reports_path}

# ─────────────────────────────────────────────────────────────────
# Backup
# ─────────────────────────────────────────────────────────────────
BACKUP_PATH={backup_path}
BACKUP_MAX_VERSIONS=5
BACKUP_COMPRESSION=zip

# ─────────────────────────────────────────────────────────────────
# Limpeza
# ─────────────────────────────────────────────────────────────────
CLEANER_DAYS_TO_KEEP=30
CLEANER_PROTECTED_EXTENSIONS=.doc,.docx,.pdf,.xlsx,.xls,.pptx

# ─────────────────────────────────────────────────────────────────
# Monitoramento
# ─────────────────────────────────────────────────────────────────
MONITOR_CPU_THRESHOLD=80
MONITOR_MEMORY_THRESHOLD=85
MONITOR_DISK_THRESHOLD=90

# ─────────────────────────────────────────────────────────────────
# Email (configurar quando necessário)
# ─────────────────────────────────────────────────────────────────
# EMAIL_SMTP_HOST=smtp.gmail.com
# EMAIL_SMTP_PORT=587
# EMAIL_SMTP_USER=seu_email@gmail.com
# EMAIL_SMTP_PASSWORD=sua_senha_de_app
# EMAIL_FROM=AutoTarefas <seu_email@gmail.com>
# EMAIL_TO=destinatario@email.com

# ─────────────────────────────────────────────────────────────────
# Agendamento
# ─────────────────────────────────────────────────────────────────
SCHEDULER_TIMEZONE=America/Sao_Paulo
SCHEDULER_MAX_CONCURRENT=3
"""


# =============================================================================
# Model
# =============================================================================


@dataclass(frozen=True)
class InitPaths:
    """Caminhos gerados na inicialização."""

    config_dir: Path
    env_file: Path
    log_dir: Path
    temp_dir: Path
    reports_dir: Path
    backup_dir: Path

    @property
    def all_dirs(self) -> list[Path]:
        return [
            self.config_dir,
            self.log_dir,
            self.temp_dir,
            self.reports_dir,
            self.backup_dir,
        ]


# =============================================================================
# Helpers
# =============================================================================


def _resolve_config_dir(config: str | None) -> Path:
    """
    Resolve o diretório de configuração.

    Se não informado, usa ~/.autotarefas.
    """
    default_dir = Path.home() / ".autotarefas"
    return safe_path(config or default_dir)


def _build_init_paths(
    config_dir: Path,
    *,
    log_path: str,
    temp_path: str,
    reports_path: str,
    backup_path: str,
) -> InitPaths:
    """Constrói os Paths finais (expandidos e resolvidos)."""
    cfg = safe_path(config_dir)
    return InitPaths(
        config_dir=cfg,
        env_file=cfg / ".env",
        log_dir=safe_path(log_path),
        temp_dir=safe_path(temp_path),
        reports_dir=safe_path(reports_path),
        backup_dir=safe_path(backup_path),
    )


def _render_env(paths: InitPaths) -> str:
    """Renderiza o conteúdo do .env."""
    return (
        ENV_TEMPLATE.format(
            log_path=str(paths.log_dir),
            temp_path=str(paths.temp_dir),
            reports_path=str(paths.reports_dir),
            backup_path=str(paths.backup_dir),
        ).rstrip()
        + "\n"
    )


def _atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """
    Escrita atômica (best effort).

    Escreve em um arquivo temporário no mesmo diretório e depois faz replace.
    """
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding=encoding)
    tmp.replace(path)


def _print_banner(console: Console, title: str) -> None:
    """Imprime o banner padrão do comando."""
    console.print()
    console.print(Panel.fit(title, border_style="blue"))
    console.print()


# =============================================================================
# Commands
# =============================================================================


@click.command("init")
@click.option(
    "-c",
    "--config",
    type=click.Path(dir_okay=True, file_okay=False, path_type=str),
    default=None,
    help="Diretório de configuração (default: ~/.autotarefas)",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Sobrescreve configurações existentes",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    default=False,
    help="Responde sim para todas as perguntas",
)
@click.pass_context
def init(ctx: click.Context, config: str | None, force: bool, yes: bool) -> None:
    """
    🚀 Inicializa o AutoTarefas.

    Cria diretórios e arquivo .env necessários para o funcionamento do sistema.
    """
    console = get_console(ctx)
    dry = is_dry_run(ctx)

    _print_banner(console, f"[bold blue]AutoTarefas[/] v{__version__} - Inicialização")

    config_dir = _resolve_config_dir(config)

    console.print(f"[bold]Diretório de configuração:[/] {config_dir}")
    if dry:
        console.print(
            "[yellow]⚠️  DRY-RUN habilitado: nenhuma alteração será aplicada.[/]"
        )
    console.print()

    env_file = config_dir / ".env"
    if env_file.exists() and not force:
        console.print("[yellow]⚠️  Configuração já existe![/]")
        if not yes and not Confirm.ask(
            "Deseja sobrescrever o arquivo .env?", default=False
        ):
            console.print("[dim]Operação cancelada.[/]")
            return

    # Defaults (modo --yes)
    if yes:
        log_path = str(config_dir / "logs")
        temp_path = str(config_dir / "temp")
        reports_path = str(config_dir / "reports")
        backup_path = str(config_dir / "backups")
    else:
        console.print("[bold]Configure os caminhos:[/]")
        console.print("[dim](Pressione Enter para usar o padrão)[/]")
        console.print()

        log_path = Prompt.ask("  Diretório de logs", default=str(config_dir / "logs"))
        temp_path = Prompt.ask(
            "  Diretório temporário", default=str(config_dir / "temp")
        )
        reports_path = Prompt.ask(
            "  Diretório de relatórios", default=str(config_dir / "reports")
        )
        backup_path = Prompt.ask(
            "  Diretório de backups", default=str(config_dir / "backups")
        )

    paths = _build_init_paths(
        config_dir,
        log_path=log_path,
        temp_path=temp_path,
        reports_path=reports_path,
        backup_path=backup_path,
    )

    # Resumo
    summary = Table(title="Resumo da Inicialização", show_header=True)
    summary.add_column("Item", style="cyan", no_wrap=True)
    summary.add_column("Valor")
    summary.add_row("Config dir", str(paths.config_dir))
    summary.add_row(".env", str(paths.env_file))
    summary.add_row("Logs", str(paths.log_dir))
    summary.add_row("Temp", str(paths.temp_dir))
    summary.add_row("Reports", str(paths.reports_dir))
    summary.add_row("Backups", str(paths.backup_dir))
    console.print(summary)
    console.print()

    # Criação de dirs
    console.print("[bold]Criando diretórios...[/]")
    for d in paths.all_dirs:
        if dry:
            console.print(f"  [yellow]•[/] (dry-run) {d}")
            continue
        ensure_dir(d)
        console.print(f"  [green]✓[/] {d}")
    console.print()

    # Escrita do .env
    console.print("[bold]Criando arquivo de configuração...[/]")
    env_content = _render_env(paths)
    if dry:
        console.print(f"  [yellow]•[/] (dry-run) {paths.env_file}")
    else:
        _atomic_write_text(paths.env_file, env_content)
        console.print(f"  [green]✓[/] {paths.env_file}")

    console.print()
    console.print(
        Panel(
            "[green]✅ AutoTarefas inicializado com sucesso![/]\n\n"
            f"Configuração: [cyan]{paths.env_file}[/]\n\n"
            "[dim]Próximos passos:[/]\n"
            "  1. Edite o arquivo .env conforme necessário\n"
            "  2. Rode: [cyan]autotarefas --help[/] para ver comandos\n"
            "  3. Teste: [cyan]autotarefas monitor --help[/]\n",
            title="[bold]Inicialização Completa[/]",
            border_style="green",
        )
    )
    console.print()


@click.command("info")
@click.pass_context
def info(ctx: click.Context) -> None:
    """
    📋 Mostra informações do sistema.

    Exibe configurações atuais e thresholds do monitoramento.
    """
    console = get_console(ctx)

    _print_banner(console, f"[bold blue]AutoTarefas[/] v{__version__} - Informações")

    table = Table(title="Configurações Atuais", show_header=True)
    table.add_column("Configuração", style="cyan")
    table.add_column("Valor")

    table.add_row("Ambiente", str(getattr(settings, "ENVIRONMENT", "N/A")))
    table.add_row("Debug", str(getattr(settings, "DEBUG", "N/A")))
    table.add_row("Logs", str(getattr(settings, "LOG_PATH", "N/A")))
    table.add_row("Temp", str(getattr(settings, "TEMP_PATH", "N/A")))
    table.add_row("Reports", str(getattr(settings, "REPORTS_PATH", "N/A")))
    table.add_row(
        "Backups", str(getattr(getattr(settings, "backup", object()), "path", "N/A"))
    )

    console.print(table)
    console.print()

    table2 = Table(title="Thresholds de Monitoramento", show_header=True)
    table2.add_column("Recurso", style="cyan")
    table2.add_column("Threshold")

    monitor_cfg = getattr(settings, "monitor", None)
    cpu_th = getattr(monitor_cfg, "cpu_threshold", "N/A")
    mem_th = getattr(monitor_cfg, "memory_threshold", "N/A")
    disk_th = getattr(monitor_cfg, "disk_threshold", "N/A")

    table2.add_row("CPU", f"{cpu_th}%" if cpu_th != "N/A" else "N/A")
    table2.add_row("Memória", f"{mem_th}%" if mem_th != "N/A" else "N/A")
    table2.add_row("Disco", f"{disk_th}%" if disk_th != "N/A" else "N/A")

    console.print(table2)
    console.print()


__all__ = ["init", "info"]
