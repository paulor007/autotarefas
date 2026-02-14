"""
Comandos de Monitoramento do AutoTarefas.

Monitora recursos do sistema (CPU, memória, disco e rede).

Uso:
    $ autotarefas monitor status
    $ autotarefas monitor status --all
    $ autotarefas monitor status --json
    $ autotarefas monitor live -i 2
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Final

import click
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ✅ Utils (padrão CLI)
from autotarefas.cli.utils.click_utils import get_console, is_dry_run
from autotarefas.config import settings
from autotarefas.tasks.monitor import MonitorTask
from autotarefas.utils.helpers import format_datetime

BAR_WIDTH: Final[int] = 20


# =============================================================================
# Helpers (UI)
# =============================================================================


def _clamp_percent(value: object) -> float:
    """Normaliza percentual para o intervalo [0, 100]."""
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(100.0, v))


def _bar(percent: float, width: int = BAR_WIDTH) -> str:
    """Cria barra de progresso textual."""
    p = _clamp_percent(percent)
    filled = int((p / 100.0) * width)
    empty = max(0, width - filled)
    return f"[{'█' * filled}{'░' * empty}]"


def _color_for(value: float, threshold: float) -> str:
    """Escolhe cor baseada no valor vs threshold."""
    v = _clamp_percent(value)
    thr = float(threshold or 0)
    if v >= thr:
        return "red"
    if v >= thr * 0.8:
        return "yellow"
    return "green"


def _timestamp_now() -> str:
    """Timestamp padrão para footer."""
    return format_datetime(datetime.now())


def _build_status_panel(
    metrics: dict, *, show_all: bool, include_network: bool
) -> Panel:
    """
    Constrói o painel de status usando métricas do MonitorTask.

    Esse builder é usado tanto no `status` quanto no `live`,
    garantindo renderização consistente.
    """
    cpu = metrics.get("cpu") or {}
    memory = metrics.get("memory") or {}
    disks = metrics.get("disks") or []
    alerts = metrics.get("alerts") or []

    # Tabela principal (sem borda, estilo "dashboard")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", width=16)
    table.add_column()

    # CPU
    cpu_percent = _clamp_percent(cpu.get("percent", 0))
    cpu_color = _color_for(cpu_percent, settings.monitor.cpu_threshold)
    table.add_row("CPU", f"[{cpu_color}]{_bar(cpu_percent)} {cpu_percent:.1f}%[/]")

    # Memória
    mem_percent = _clamp_percent(memory.get("percent", 0))
    mem_color = _color_for(mem_percent, settings.monitor.memory_threshold)
    mem_used = memory.get("used_formatted", "?")
    mem_total = memory.get("total_formatted", "?")
    table.add_row(
        "Memória",
        f"[{mem_color}]{_bar(mem_percent)} {mem_percent:.1f}%[/] ({mem_used} / {mem_total})",
    )

    # Swap (se existir)
    try:
        swap_total = int(memory.get("swap_total", 0) or 0)
    except (TypeError, ValueError):
        swap_total = 0

    if swap_total > 0:
        swap_percent = _clamp_percent(memory.get("swap_percent", 0))
        table.add_row("Swap", f"{swap_percent:.1f}% usado")

    # Discos (limita para não poluir)
    for disk in disks[:3]:
        disk_percent = _clamp_percent(disk.get("percent", 0))
        disk_color = _color_for(disk_percent, settings.monitor.disk_threshold)
        disk_free = disk.get("free_formatted", "?")
        disk_path = str(disk.get("path", "/") or "/")
        table.add_row(
            f"Disco {disk_path}",
            f"[{disk_color}]{_bar(disk_percent)} {disk_percent:.1f}%[/] ({disk_free} livre)",
        )

    # Blocos extras (texto simples)
    extra_lines: list[str] = []

    if show_all:
        system = metrics.get("system") or {}
        if system:
            extra_lines.append("[bold]Sistema:[/]")
            extra_lines.append(
                f"  • Plataforma: {system.get('platform', '?')} {system.get('platform_release', '')}"
            )
            extra_lines.append(f"  • Uptime: {system.get('uptime_formatted', '?')}")
            extra_lines.append(f"  • Python: {system.get('python_version', '?')}")

    if include_network:
        network = metrics.get("network") or {}
        if network:
            if extra_lines:
                extra_lines.append("")
            extra_lines.append("[bold]Rede:[/]")
            extra_lines.append(
                f"  • Host: {network.get('hostname', '?')} ({network.get('ip_address', '?')})"
            )
            extra_lines.append(
                f"  • Enviado: {network.get('bytes_sent_formatted', '?')}"
            )
            extra_lines.append(
                f"  • Recebido: {network.get('bytes_recv_formatted', '?')}"
            )

    # Alertas
    alert_text = ""
    if alerts:
        alert_text = "[bold red]⚠️  Alertas:[/]\n" + "\n".join(
            f"  • {a}" for a in alerts
        )

    # Montar renderables usando Text para strings
    renderables: list[Table | Text] = [table]
    if alert_text:
        renderables.append(Text(""))
        renderables.append(Text.from_markup(alert_text))
    if extra_lines:
        renderables.append(Text(""))
        renderables.append(Text.from_markup("\n".join(extra_lines)))

    renderables.append(Text(""))
    renderables.append(Text.from_markup(f"[dim]Atualizado em: {_timestamp_now()}[/]"))

    return Panel(
        Group(*renderables), title="[bold]Status do Sistema[/]", border_style="blue"
    )


def _fetch_metrics(*, show_all: bool, include_network: bool) -> tuple[bool, str, dict]:
    """
    Coleta métricas chamando MonitorTask e retorna:
        (ok, message, metrics_dict)
    """
    task = MonitorTask()
    result = task.run(
        check_cpu=True,
        check_memory=True,
        check_disk=True,
        check_network=bool(include_network),
        include_system_info=bool(show_all),
    )

    if not result.is_success:
        return False, (result.message or "Erro desconhecido"), {}

    metrics = (result.data or {}).get("metrics", {}) or {}
    return True, "ok", metrics


# =============================================================================
# CLI group
# =============================================================================


@click.group()
@click.pass_context
def monitor(ctx: click.Context) -> None:
    """
    📊 Monitora recursos do sistema.

    Comandos para verificar CPU, memória, disco e rede.
    """
    ctx.ensure_object(dict)


# =============================================================================
# monitor status
# =============================================================================


@monitor.command("status")
@click.option(
    "-a",
    "--all",
    "show_all",
    is_flag=True,
    default=False,
    help="Mostra informações completas",
)
@click.option("--network/--no-network", default=False, help="Inclui métricas de rede")
@click.option(
    "--json", "output_json", is_flag=True, default=False, help="Saída em formato JSON"
)
@click.pass_context
def monitor_status(
    ctx: click.Context, show_all: bool, network: bool, output_json: bool
) -> None:
    """
    📋 Mostra status atual do sistema.

    Exemplos:
        autotarefas monitor status
        autotarefas monitor status --all
        autotarefas monitor status --network
        autotarefas monitor status --json
    """
    console = get_console(ctx)
    dry = is_dry_run(ctx)

    console.print()
    console.print(Panel.fit("[bold blue]AutoTarefas[/] - Monitor", border_style="blue"))
    console.print()

    if dry:
        console.print(
            "[yellow]🔍 Modo dry-run: o monitor apenas lê métricas (nenhuma alteração).[/]"
        )
        console.print()

    include_network = bool(network or show_all)

    ok, msg, metrics = _fetch_metrics(
        show_all=show_all, include_network=include_network
    )
    if not ok:
        console.print(f"[red]❌ Erro ao coletar métricas: {msg}[/]")
        console.print()
        return

    if output_json:
        console.print(json.dumps(metrics, indent=2, ensure_ascii=False, default=str))
        console.print()
        return

    console.print(
        _build_status_panel(metrics, show_all=show_all, include_network=include_network)
    )
    console.print()


# =============================================================================
# monitor live
# =============================================================================


@monitor.command("live")
@click.option(
    "-i",
    "--interval",
    default=2.0,
    show_default=True,
    type=float,
    help="Intervalo de atualização em segundos",
)
@click.option("--network/--no-network", default=False, help="Inclui métricas de rede")
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    default=False,
    help="Inclui informações completas (sistema + rede)",
)
@click.pass_context
def monitor_live(
    ctx: click.Context, interval: float, network: bool, show_all: bool
) -> None:
    """
    📺 Monitoramento em tempo real.

    Atualiza a tela automaticamente. Pressione Ctrl+C para sair.
    """
    console = get_console(ctx)

    if interval <= 0:
        interval = 1.0

    include_network = bool(network or show_all)

    console.print()
    console.print("[bold]Monitoramento em tempo real[/]")
    console.print("[dim]Pressione Ctrl+C para sair[/]")
    console.print()

    # Refresh do Live (limitado) para não gastar CPU
    refresh = (
        4  # atualiza UI algumas vezes por segundo; métricas seguem o sleep(interval)
    )

    try:
        with Live(console=console, refresh_per_second=refresh, transient=True) as live:
            while True:
                ok, msg, metrics = _fetch_metrics(
                    show_all=show_all, include_network=include_network
                )

                if ok:
                    panel = _build_status_panel(
                        metrics, show_all=show_all, include_network=include_network
                    )
                    live.update(
                        Panel(
                            panel.renderable,
                            title="[bold]AutoTarefas - Monitor (Live)[/]",
                            border_style="blue",
                        )
                    )
                else:
                    live.update(
                        Panel(
                            f"[red]❌ Erro ao coletar métricas:[/] {msg}\n[dim]Atualizado em: {_timestamp_now()}[/]",
                            title="[bold]AutoTarefas - Monitor (Live)[/]",
                            border_style="red",
                        )
                    )

                time.sleep(interval)

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Monitoramento encerrado.[/]")
        console.print()


# =============================================================================
# monitor quick
# =============================================================================


@monitor.command("quick")
@click.pass_context
def monitor_quick(ctx: click.Context) -> None:
    """
    ⚡ Verificação rápida (uma linha).

    Mostra status resumido em uma linha.
    """
    console = get_console(ctx)

    task = MonitorTask()
    metrics = task.quick_check()  # dict simples

    cpu = _clamp_percent(metrics.get("cpu_percent", 0))
    mem = _clamp_percent(metrics.get("memory_percent", 0))
    disk = _clamp_percent(metrics.get("disk_percent", 0))

    cpu_color = _color_for(cpu, settings.monitor.cpu_threshold)
    mem_color = _color_for(mem, settings.monitor.memory_threshold)
    disk_color = _color_for(disk, settings.monitor.disk_threshold)

    console.print(
        f"CPU: [{cpu_color}]{cpu:.0f}%[/] | Mem: [{mem_color}]{mem:.0f}%[/] | Disco: [{disk_color}]{disk:.0f}%[/]"
    )


__all__ = ["monitor"]
