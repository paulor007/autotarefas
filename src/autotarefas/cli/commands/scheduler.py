"""
Comandos de Agendamento do AutoTarefas.

Gerencia jobs agendados e o scheduler via CLI.

Uso:
    $ autotarefas schedule list
    $ autotarefas schedule add backup_diario backup "0 2 * * *"
    $ autotarefas schedule remove <job_id>
    $ autotarefas schedule run <job_id>
    $ autotarefas schedule start
    $ autotarefas schedule stop
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

import click
from rich.panel import Panel
from rich.table import Table

from autotarefas.cli.utils.click_utils import (
    get_console,
    is_dry_run,
    params_tuple_to_dict,
)
from autotarefas.core.scheduler import ScheduleType, get_scheduler

SCHEDULE_TYPE_CHOICES: Final[list[str]] = ["cron", "interval", "daily", "once"]


# =============================================================================
# Helpers locais (específicos do scheduler)
# =============================================================================


def _format_datetime(dt: datetime | None) -> str:
    """Formata datetime para exibição."""
    if dt is None:
        return "-"
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def _format_duration(seconds: float) -> str:
    """Formata duração em segundos para exibição."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}min"
    return f"{seconds / 3600:.1f}h"


def _status_badge(enabled: bool) -> tuple[str, str]:
    if enabled:
        return "🟢", "green"
    return "⏸️", "yellow"


def _schedule_type_emoji(schedule_type: ScheduleType) -> str:
    return {
        ScheduleType.CRON: "⏰",
        ScheduleType.INTERVAL: "🔄",
        ScheduleType.DAILY: "📅",
        ScheduleType.ONCE: "1️⃣",
    }.get(schedule_type, "❓")


def _resolve_job_id(scheduler: Any, job_id_or_name: str) -> str:
    """
    Resolve 'job_id' ou 'job_name' para um job_id válido.
    """
    job = scheduler.get_job(job_id_or_name)
    if job is not None:
        return job.job_id

    job_by_name = scheduler.get_job_by_name(job_id_or_name)
    if job_by_name is not None:
        return job_by_name.job_id

    raise click.ClickException(f"Job não encontrado: {job_id_or_name}")


# =============================================================================
# Grupo Principal
# =============================================================================


@click.group()
@click.pass_context
def schedule(ctx: click.Context) -> None:
    """
    ⏰ Gerencia agendamento de tarefas.

    \b
    Exemplos:
      autotarefas schedule list
      autotarefas schedule add meu_backup backup "0 2 * * *"
      autotarefas schedule start
    """
    _ = ctx


# =============================================================================
# schedule list
# =============================================================================


@schedule.command("list")
@click.option(
    "-a",
    "--all",
    "show_all",
    is_flag=True,
    default=False,
    help="Inclui jobs desabilitados",
)
@click.option(
    "-v", "--verbose", is_flag=True, default=False, help="Mostra informações detalhadas"
)
@click.pass_context
def schedule_list(ctx: click.Context, show_all: bool, verbose: bool) -> None:
    scheduler = get_scheduler()
    jobs = scheduler.list_jobs(enabled_only=not show_all)

    console = get_console(ctx)

    if not jobs:
        console.print(
            Panel(
                "[yellow]Nenhum job agendado encontrado.[/yellow]\n\n"
                "Use [cyan]autotarefas schedule add[/cyan] para criar um novo job.",
                title="📋 Jobs Agendados",
                border_style="yellow",
            )
        )
        return

    table = Table(title="📋 Jobs Agendados", show_header=True, header_style="bold cyan")
    table.add_column("Status", justify="center", width=3)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Nome", style="bold")
    table.add_column("Task", style="cyan")
    table.add_column("Tipo", justify="center", width=4)
    table.add_column("Schedule", style="magenta")
    table.add_column("Próxima Execução", style="green")

    if verbose:
        table.add_column("Execuções", justify="right")
        table.add_column("Taxa", justify="right")

    for job in jobs:
        status_emoji, _ = _status_badge(job.enabled)
        type_emoji = _schedule_type_emoji(job.schedule_type)

        row = [
            status_emoji,
            job.job_id,
            job.job_name,
            job.task_name,
            type_emoji,
            job.schedule,
            _format_datetime(job.next_run),
        ]

        if verbose:
            row.append(str(job.run_count))
            row.append(f"{job.success_rate * 100:.0f}%" if job.run_count > 0 else "-")

        table.add_row(*row)

    console.print(table)
    console.print(f"\n[dim]Total: {len(jobs)} job(s)[/dim]")


# =============================================================================
# schedule add
# =============================================================================


@schedule.command("add")
@click.argument("name")
@click.argument("task")
@click.argument("schedule_expr")
@click.option(
    "-t",
    "--type",
    "schedule_type",
    type=click.Choice(SCHEDULE_TYPE_CHOICES, case_sensitive=False),
    default="cron",
    show_default=True,
    help="Tipo de agendamento",
)
@click.option(
    "-p",
    "--param",
    "params",
    multiple=True,
    type=(str, str),
    help="Parâmetro para a task: -p chave valor (pode repetir)",
)
@click.option("-d", "--description", default="", help="Descrição do job")
@click.option(
    "--tag", "tags", multiple=True, help="Tag para organização (pode repetir)"
)
@click.option("--disabled", is_flag=True, default=False, help="Criar job desabilitado")
@click.pass_context
def schedule_add(
    ctx: click.Context,
    name: str,
    task: str,
    schedule_expr: str,
    schedule_type: str,
    params: tuple[tuple[str, str], ...],
    description: str,
    tags: tuple[str, ...],
    disabled: bool,
) -> None:
    console = get_console(ctx)

    if is_dry_run(ctx):
        console.print(
            Panel(
                "[yellow]DRY-RUN:[/yellow] Job não será criado.\n\n"
                f"[bold]Nome:[/bold] {name}\n"
                f"[bold]Task:[/bold] {task}\n"
                f"[bold]Schedule:[/bold] {schedule_expr} ({schedule_type})",
                title="➕ Novo Job (simulação)",
                border_style="yellow",
            )
        )
        return

    scheduler = get_scheduler()
    params_dict = params_tuple_to_dict(params)

    try:
        job = scheduler.add_job(
            name=name,
            task=task,
            schedule=schedule_expr,
            schedule_type=schedule_type,
            params=params_dict,
            tags=[t for t in tags if t.strip()],
            description=description.strip(),
            enabled=not disabled,
        )
    except (ValueError, RuntimeError) as e:
        raise click.ClickException(str(e)) from e

    console.print(
        Panel(
            f"[green]✅ Job criado com sucesso![/green]\n\n"
            f"[bold]ID:[/bold] {job.job_id}\n"
            f"[bold]Nome:[/bold] {job.job_name}\n"
            f"[bold]Task:[/bold] {job.task_name}\n"
            f"[bold]Schedule:[/bold] {job.schedule} ({job.schedule_type.value})\n"
            f"[bold]Próxima execução:[/bold] {_format_datetime(job.next_run)}\n"
            f"[bold]Status:[/bold] {'Habilitado' if job.enabled else 'Desabilitado'}",
            title="➕ Novo Job",
            border_style="green",
        )
    )


# =============================================================================
# schedule remove
# =============================================================================


@schedule.command("remove")
@click.argument("job_id_or_name")
@click.option(
    "-f", "--force", is_flag=True, default=False, help="Remove sem confirmação"
)
@click.pass_context
def schedule_remove(ctx: click.Context, job_id_or_name: str, force: bool) -> None:
    scheduler = get_scheduler()
    console = get_console(ctx)

    job_id = _resolve_job_id(scheduler, job_id_or_name)
    job = scheduler.get_job(job_id)
    if job is None:
        raise click.ClickException(f"Job não encontrado: {job_id_or_name}")

    if is_dry_run(ctx):
        console.print(
            f"[yellow]DRY-RUN:[/yellow] Remoção simulada do job '{job.job_name}' ({job_id})."
        )
        return

    if not force and not click.confirm(f"Remover job '{job.job_name}' ({job_id})?"):
        console.print("[yellow]Operação cancelada.[/yellow]")
        return

    if not scheduler.remove_job(job_id):
        raise click.ClickException("Erro ao remover job.")

    console.print(f"[green]✅ Job '{job.job_name}' removido com sucesso![/green]")


# =============================================================================
# schedule run
# =============================================================================


@schedule.command("run")
@click.argument("job_id_or_name")
@click.pass_context
def schedule_run(ctx: click.Context, job_id_or_name: str) -> None:
    scheduler = get_scheduler()
    console = get_console(ctx)

    job_id = _resolve_job_id(scheduler, job_id_or_name)
    job = scheduler.get_job(job_id)
    if job is None:
        raise click.ClickException(f"Job não encontrado: {job_id_or_name}")

    if is_dry_run(ctx):
        console.print(
            f"[yellow]DRY-RUN:[/yellow] Execução simulada do job '{job.job_name}' ({job_id})."
        )
        return

    console.print(f"[cyan]▶️ Executando job '{job.job_name}'...[/cyan]")

    with console.status(f"Executando {job.task_name}...", spinner="dots"):
        success = scheduler.run_job(job_id)

    job = scheduler.get_job(job_id)
    if job is None:
        raise click.ClickException(
            "Job desapareceu após execução (estado inconsistente)."
        )

    if success:
        console.print(
            Panel(
                f"[green]✅ Job executado com sucesso![/green]\n\n"
                f"[bold]Duração:[/bold] {_format_duration(job.last_duration)}\n"
                f"[bold]Execuções:[/bold] {job.run_count}\n"
                f"[bold]Taxa de sucesso:[/bold] {job.success_rate * 100:.0f}%",
                title=f"▶️ {job.job_name}",
                border_style="green",
            )
        )
        return

    console.print(
        Panel(
            f"[red]❌ Job falhou![/red]\n\n"
            f"[bold]Erro:[/bold] {job.last_error or 'Desconhecido'}\n"
            f"[bold]Duração:[/bold] {_format_duration(job.last_duration)}",
            title=f"▶️ {job.job_name}",
            border_style="red",
        )
    )
    raise click.ClickException("Execução do job falhou.")


# =============================================================================
# schedule pause / resume
# =============================================================================


@schedule.command("pause")
@click.argument("job_id_or_name")
@click.pass_context
def schedule_pause(ctx: click.Context, job_id_or_name: str) -> None:
    scheduler = get_scheduler()
    console = get_console(ctx)

    job_id = _resolve_job_id(scheduler, job_id_or_name)
    job = scheduler.get_job(job_id)
    if job is None:
        raise click.ClickException(f"Job não encontrado: {job_id_or_name}")

    if not job.enabled:
        console.print(f"[yellow]⚠️ Job '{job.job_name}' já está pausado.[/yellow]")
        return

    if is_dry_run(ctx):
        console.print(
            f"[yellow]DRY-RUN:[/yellow] Pausa simulada do job '{job.job_name}' ({job_id})."
        )
        return

    if not scheduler.disable_job(job_id):
        raise click.ClickException("Erro ao pausar job.")

    console.print(f"[green]⏸️ Job '{job.job_name}' pausado com sucesso![/green]")


@schedule.command("resume")
@click.argument("job_id_or_name")
@click.pass_context
def schedule_resume(ctx: click.Context, job_id_or_name: str) -> None:
    scheduler = get_scheduler()
    console = get_console(ctx)

    job_id = _resolve_job_id(scheduler, job_id_or_name)
    job = scheduler.get_job(job_id)
    if job is None:
        raise click.ClickException(f"Job não encontrado: {job_id_or_name}")

    if job.enabled:
        console.print(f"[yellow]⚠️ Job '{job.job_name}' já está ativo.[/yellow]")
        return

    if is_dry_run(ctx):
        console.print(
            f"[yellow]DRY-RUN:[/yellow] Resume simulado do job '{job.job_name}' ({job_id})."
        )
        return

    if not scheduler.enable_job(job_id):
        raise click.ClickException("Erro ao resumir job.")

    job = scheduler.get_job(job_id)
    if job is None:
        raise click.ClickException(
            "Job não encontrado após resumir (estado inconsistente)."
        )

    console.print(
        f"[green]▶️ Job '{job.job_name}' resumido![/green]\n"
        f"[dim]Próxima execução: {_format_datetime(job.next_run)}[/dim]"
    )


# =============================================================================
# schedule start / stop / status
# =============================================================================


@schedule.command("start")
@click.option(
    "-f", "--foreground", is_flag=True, default=False, help="Executa em primeiro plano"
)
@click.pass_context
def schedule_start(ctx: click.Context, foreground: bool) -> None:
    scheduler = get_scheduler()
    console = get_console(ctx)

    if scheduler.running:
        console.print("[yellow]⚠️ Scheduler já está rodando.[/yellow]")
        return

    enabled_jobs = scheduler.list_jobs(enabled_only=True)
    if not enabled_jobs:
        console.print(
            Panel(
                "[yellow]Nenhum job habilitado encontrado.[/yellow]\n\n"
                "O scheduler será iniciado, mas não há jobs para executar.\n"
                "Use [cyan]autotarefas schedule add[/cyan] para criar jobs.",
                title="⚠️ Aviso",
                border_style="yellow",
            )
        )

    if is_dry_run(ctx):
        console.print("[yellow]DRY-RUN:[/yellow] Start do scheduler simulado.")
        return

    console.print("[cyan]🚀 Iniciando scheduler...[/cyan]")

    if foreground:
        console.print("[dim]Pressione Ctrl+C para parar.[/dim]\n")
        try:
            scheduler.start(blocking=True)
        except KeyboardInterrupt:
            console.print("\n[yellow]Parando scheduler...[/yellow]")
            scheduler.stop()
            console.print("[green]✅ Scheduler parado.[/green]")
        return

    scheduler.start(blocking=False)
    status = scheduler.get_status()
    console.print(
        Panel(
            f"[green]✅ Scheduler iniciado em background![/green]\n\n"
            f"[bold]Jobs ativos:[/bold] {status['enabled_jobs']}\n"
            f"[bold]Próximo:[/bold] {status['next_job'] or '-'}\n"
            f"[bold]Execução:[/bold] {status['next_execution'] or '-'}\n\n"
            "[dim]Use 'autotarefas schedule stop' para parar.[/dim]",
            title="🚀 Scheduler",
            border_style="green",
        )
    )


@schedule.command("stop")
@click.option("-f", "--force", is_flag=True, default=False, help="Para sem aguardar")
@click.pass_context
def schedule_stop(ctx: click.Context, force: bool) -> None:
    scheduler = get_scheduler()
    console = get_console(ctx)

    if not scheduler.running:
        console.print("[yellow]⚠️ Scheduler não está rodando.[/yellow]")
        return

    if is_dry_run(ctx):
        console.print("[yellow]DRY-RUN:[/yellow] Stop do scheduler simulado.")
        return

    console.print("[cyan]🛑 Parando scheduler...[/cyan]")
    scheduler.stop(wait=not force)
    console.print("[green]✅ Scheduler parado com sucesso![/green]")


@schedule.command("status")
@click.pass_context
def schedule_status(ctx: click.Context) -> None:
    scheduler = get_scheduler()
    console = get_console(ctx)

    status = scheduler.get_status()
    stats = scheduler.get_stats()

    if status["running"]:
        scheduler_status = (
            "[yellow]⏸️ Pausado[/yellow]"
            if status["paused"]
            else "[green]🟢 Rodando[/green]"
        )
    else:
        scheduler_status = "[red]🔴 Parado[/red]"

    content = [
        f"[bold]Status:[/bold] {scheduler_status}",
        "",
        f"[bold]Total de jobs:[/bold] {status['total_jobs']}",
        f"[bold]Jobs habilitados:[/bold] {status['enabled_jobs']}",
        "",
        f"[bold]Próximo job:[/bold] {status['next_job'] or '-'}",
        f"[bold]Próxima execução:[/bold] {status['next_execution'] or '-'}",
    ]

    if stats["total_runs"] > 0:
        content.extend(
            [
                "",
                "[bold]Estatísticas:[/bold]",
                f"  Total de execuções: {stats['total_runs']}",
                f"  Sucessos: {stats['total_success']}",
                f"  Erros: {stats['total_errors']}",
                f"  Taxa de sucesso: {stats['success_rate'] * 100:.1f}%",
            ]
        )

    console.print(
        Panel("\n".join(content), title="📊 Status do Scheduler", border_style="cyan")
    )


# =============================================================================
# schedule tasks / show
# =============================================================================


@schedule.command("tasks")
@click.pass_context
def schedule_tasks(ctx: click.Context) -> None:
    scheduler = get_scheduler()
    console = get_console(ctx)

    tasks = scheduler.registry.list_tasks()
    if not tasks:
        console.print("[yellow]Nenhuma task registrada.[/yellow]")
        return

    table = Table(
        title="📦 Tasks Disponíveis", show_header=True, header_style="bold cyan"
    )
    table.add_column("Task", style="bold green")
    table.add_column("Tipo", style="dim")
    table.add_column("Descrição")

    descriptions = {
        "backup": "Backup de arquivos e diretórios",
        "cleaner": "Limpeza de arquivos temporários",
        "clean": "Alias para cleaner",
        "monitor": "Monitoramento do sistema (CPU, RAM, disco)",
        "sales_report": "Geração de relatórios de vendas",
        "sales": "Alias para sales_report",
    }

    for task in tasks:
        desc = descriptions.get(task, "Task customizada")
        kind = "alias" if task in {"clean", "sales"} else "task"
        table.add_row(task, kind, desc)

    console.print(table)
    console.print(
        "\n[dim]Use 'autotarefas schedule add <nome> <task> <schedule>' para agendar uma task.[/dim]"
    )


@schedule.command("show")
@click.argument("job_id_or_name")
@click.pass_context
def schedule_show(ctx: click.Context, job_id_or_name: str) -> None:
    scheduler = get_scheduler()
    console = get_console(ctx)

    job_id = _resolve_job_id(scheduler, job_id_or_name)
    job = scheduler.get_job(job_id)
    if job is None:
        raise click.ClickException(f"Job não encontrado: {job_id_or_name}")

    status_emoji, _ = _status_badge(job.enabled)
    type_emoji = _schedule_type_emoji(job.schedule_type)

    content: list[str] = [
        f"[bold]ID:[/bold] {job.job_id}",
        f"[bold]Nome:[/bold] {job.job_name}",
        f"[bold]Status:[/bold] {status_emoji} {'Habilitado' if job.enabled else 'Desabilitado'}",
        "",
        f"[bold]Task:[/bold] {job.task_name}",
        f"[bold]Tipo:[/bold] {type_emoji} {job.schedule_type.value}",
        f"[bold]Schedule:[/bold] {job.schedule}",
        "",
        f"[bold]Criado em:[/bold] {_format_datetime(job.created_at)}",
        f"[bold]Última execução:[/bold] {_format_datetime(job.last_run)}",
        f"[bold]Próxima execução:[/bold] {_format_datetime(job.next_run)}",
    ]

    if job.description:
        content.insert(3, f"[bold]Descrição:[/bold] {job.description}")

    if job.tags:
        content.append(f"[bold]Tags:[/bold] {', '.join(job.tags)}")

    if job.params:
        content.append("")
        content.append("[bold]Parâmetros:[/bold]")
        for k, v in job.params.items():
            content.append(f"  {k}: {v}")

    if job.run_count > 0:
        content.extend(
            [
                "",
                "[bold]Estatísticas:[/bold]",
                f"  Execuções: {job.run_count}",
                f"  Sucessos: {job.success_count}",
                f"  Erros: {job.error_count}",
                f"  Taxa: {job.success_rate * 100:.1f}%",
                f"  Última duração: {_format_duration(job.last_duration)}",
            ]
        )
        if job.last_error:
            content.append(f"  [red]Último erro: {job.last_error}[/red]")

    console.print(
        Panel("\n".join(content), title=f"🔍 Job: {job.job_name}", border_style="cyan")
    )


__all__ = ["schedule"]
