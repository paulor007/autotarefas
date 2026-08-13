"""Comandos de manutencao e governanca do modo real privado."""

from __future__ import annotations

import sqlite3

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.core.audit import audit
from autotarefas.core.retention import (
    PurgePlan,
    build_purge_plan,
    execute_purge,
)
from autotarefas.core.settings import settings


@click.group(name="manutencao")
def manutencao() -> None:
    """Executa rotinas administrativas controladas."""


def _show_plan(console: Console, plan: PurgePlan) -> None:
    console.info("Plano de expurgo do modo real privado:")
    console.info(
        f"  Logs: {len(plan.log_files)} arquivo(s) (retencao: {plan.log_retention_days} dias)"
    )
    console.info(
        f"  Screenshots: {len(plan.screenshot_files)} arquivo(s) "
        f"(retencao: {plan.screenshot_retention_days} dias)"
    )
    if plan.audit_retention_days is None:
        console.info("  Audit: preservado; retencao nao configurada")
    else:
        console.info(
            f"  Audit: {plan.audit_rows} registro(s) (retencao: {plan.audit_retention_days} dias)"
        )
    console.info("  Uploads e artefatos escolhidos pelo operador: nao incluidos")
    console.info(f"  Total planejado: {plan.total_items}")


@manutencao.command(name="expurgar")
@click.option(
    "--logs-days",
    type=click.IntRange(min=1, max=3650),
    default=None,
    help="Sobrescreve temporariamente a retencao de logs.",
)
@click.option(
    "--screenshots-days",
    type=click.IntRange(min=1, max=3650),
    default=None,
    help="Sobrescreve temporariamente a retencao de screenshots.",
)
@click.option(
    "--audit-days",
    type=click.IntRange(min=1, max=3650),
    default=None,
    help="Ativa ou sobrescreve a retencao do audit nesta execucao.",
)
@click.pass_obj
def expurgar(
    ctx: CLIContext,
    logs_days: int | None,
    screenshots_days: int | None,
    audit_days: int | None,
) -> None:
    """Remove dados gerenciados expirados, com previa e confirmacao."""
    console = Console(ctx)

    if settings.environment == "demo":
        console.error(
            "Este comando e exclusivo do modo real privado. "
            "O Live usa workspaces efemeros com TTL proprio."
        )
        raise click.exceptions.Exit(2)

    effective_logs = logs_days if logs_days is not None else settings.log_retention_days
    effective_screenshots = (
        screenshots_days if screenshots_days is not None else settings.screenshot_retention_days
    )
    effective_audit = audit_days if audit_days is not None else settings.audit_retention_days

    try:
        plan = build_purge_plan(
            audit=audit,
            logs_dir=settings.logs_dir,
            screenshots_dir=settings.screenshots_dir,
            log_retention_days=effective_logs,
            screenshot_retention_days=effective_screenshots,
            audit_retention_days=effective_audit,
        )
    except (OSError, sqlite3.Error, ValueError) as exc:
        console.error(f"Nao foi possivel montar o plano de expurgo: {exc}")
        raise click.exceptions.Exit(1) from exc

    _show_plan(console, plan)

    if ctx.dry_run:
        console.warning("[DRY-RUN] Nenhum dado foi removido.")
        return

    if plan.total_items == 0:
        console.success("Nenhum dado gerenciado esta expirado.")
        return

    if not ctx.yes and not click.confirm(
        "Confirma a exclusao dos itens listados?",
        default=False,
    ):
        console.warning("Expurgo cancelado. Nenhum dado foi removido.")
        return

    result = execute_purge(plan, audit=audit)

    console.info(f"Logs removidos: {result.removed_logs}")
    console.info(f"Screenshots removidos: {result.removed_screenshots}")
    console.info(f"Registros de audit removidos: {result.removed_audit_rows}")

    if result.partial:
        console.error("O expurgo terminou parcialmente. Consulte o audit e os logs.")
        raise click.exceptions.Exit(1)

    console.success("Expurgo concluido e registrado no audit.")


__all__ = ["manutencao"]
