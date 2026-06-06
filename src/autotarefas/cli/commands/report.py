"""
Comando ``autotarefas report`` — gera relatórios do audit trail.

Lê o audit DB (criado por ``autotarefas.core.audit``) e mostra
estatísticas, listas ou apenas falhas. Suporta filtros temporais,
por task, por status, e múltiplos formatos de saída.

Uso típico:
    # Summary das ultimas 24h (default)
    $ autotarefas report

    # Filtros
    $ autotarefas report --task validate --days 7
    $ autotarefas report --status failure --since 2026-05-01

    # Tipos de relatorio
    $ autotarefas report --type list
    $ autotarefas report --type errors

    # Output em arquivo
    $ autotarefas report --format json --output rel.json
    $ autotarefas report --format csv --output rel.csv
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.report_audit import ReportAuditTask, ReportFilters

# ============================================================
# Helpers de cálculo de período
# ============================================================


def _calculate_period(
    since: datetime | None,
    until: datetime | None,
    days: int,
) -> tuple[datetime | None, datetime | None]:
    """
    Calcula período efetivo a partir das opções da CLI.

    Regras:
    - Se ``--since`` foi passado, usa ele (ignora ``--days``).
    - Se ``--since`` NÃO foi passado, calcula a partir de ``--days``.
    - ``--until`` é opcional em ambos os casos.
    - Garante tzinfo=UTC em datetimes (Click pode retornar naive).

    Args:
        since: --since da CLI (datetime ou None).
        until: --until da CLI (datetime ou None).
        days: --days da CLI (int).

    Returns:
        Tupla (since_efetivo, until_efetivo).
    """
    # Se since nao foi passado, calcula a partir de days
    if since is None:
        actual_since = datetime.now(UTC) - timedelta(days=days)
    else:
        # Garante tzinfo UTC se naive
        actual_since = since if since.tzinfo else since.replace(tzinfo=UTC)

    actual_until: datetime | None = None
    if until is not None:
        actual_until = until if until.tzinfo else until.replace(tzinfo=UTC)

    return actual_since, actual_until


# ============================================================
# Helpers de formatação
# ============================================================


def _format_size(seconds_or_ms: float, unit: str = "ms") -> str:
    """Formata duração em ms/s humanizado."""
    if unit == "ms":
        if seconds_or_ms < 1000:  # noqa: PLR2004
            return f"{seconds_or_ms:.0f}ms"
        return f"{seconds_or_ms / 1000:.2f}s"
    return f"{seconds_or_ms:.2f}{unit}"


def _format_timestamp(ts: str) -> str:
    """Formata timestamp ISO pra mostrar curto (YYYY-MM-DD HH:MM)."""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return ts


def _format_summary_table(data: dict[str, Any]) -> str:  # noqa: PLR0912, PLR0915
    """
    Formata summary como texto pra terminal.

    Não usa Rich Table direto pra ficar portável e fácil de salvar
    em arquivo.
    """
    lines: list[str] = []
    width = 60

    # Cabecalho
    lines.append("=" * width)
    lines.append(" AutoTarefas - Relatorio Audit Trail")
    lines.append("=" * width)
    lines.append("")

    # Periodo + total
    filters = data.get("filters", {})
    since_str = _format_timestamp(filters["since"]) if filters.get("since") else "inicio"
    until_str = _format_timestamp(filters["until"]) if filters.get("until") else "agora"
    lines.append(f"Periodo:  {since_str}  ->  {until_str}")
    lines.append(f"Total:    {data['total_executions']} execucoes")
    lines.append("")

    if data["total_executions"] == 0:
        lines.append("Nenhuma execucao encontrada no periodo.")
        lines.append("")
        return "\n".join(lines)

    # Por task (com sucessos/falhas inline)
    by_task = data.get("by_task", {})
    cross = data.get("by_task_and_status", {})
    total = data["total_executions"]

    if by_task:
        lines.append("Por task:")
        for task_name, count in by_task.items():
            pct = (count / total * 100) if total > 0 else 0
            status_breakdown = cross.get(task_name, {})

            # Monta breakdown de status: "22 ok, 1 falha"
            parts = []
            if status_breakdown.get("success", 0):
                parts.append(f"{status_breakdown['success']} ok")
            if status_breakdown.get("failure", 0):
                parts.append(f"{status_breakdown['failure']} falha")
            if status_breakdown.get("partial", 0):
                parts.append(f"{status_breakdown['partial']} parcial")
            if status_breakdown.get("dry_run", 0):
                parts.append(f"{status_breakdown['dry_run']} dry-run")
            if status_breakdown.get("skipped", 0):
                parts.append(f"{status_breakdown['skipped']} skipped")
            breakdown = ", ".join(parts) if parts else ""

            lines.append(f"  - {task_name:12s} {count:4d} ({pct:5.1f}%)  {breakdown}")
        lines.append("")

    # Por status
    by_status = data.get("by_status", {})
    if by_status:
        lines.append("Por status:")
        for status, count in by_status.items():
            pct = (count / total * 100) if total > 0 else 0
            lines.append(f"  - {status:12s} {count:4d} ({pct:5.1f}%)")
        lines.append("")

    # Duracao media
    avg_duration = data.get("avg_duration_ms_by_task", {})
    if avg_duration:
        lines.append("Duracao media por task:")
        for task_name, avg_ms in avg_duration.items():
            lines.append(f"  - {task_name:12s} {_format_size(avg_ms)}")
        lines.append("")

    # Rows
    total_rows = data.get("total_rows_affected", 0)
    failed_rows = data.get("total_rows_failed", 0)
    if total_rows or failed_rows:
        lines.append(f"Linhas processadas: {total_rows} (com {failed_rows} falhas)")
        lines.append("")

    # Falhas recentes
    failures = data.get("recent_failures", [])
    if failures:
        lines.append("Falhas recentes (ultimas 5):")
        for fail in failures:
            ts = _format_timestamp(fail.get("timestamp", ""))
            task = fail.get("task_name", "?")
            err = fail.get("error_message", "") or ""
            # Truncar mensagem
            if len(err) > 50:  # noqa: PLR2004
                err = err[:47] + "..."
            lines.append(f"  X {ts}  {task:12s}  {err}")
        lines.append("")

    return "\n".join(lines)


def _format_list_table(data: dict[str, Any]) -> str:
    """Formata lista de execuções como tabela texto."""
    lines: list[str] = []
    executions = data.get("executions", [])

    if not executions:
        return "Nenhuma execucao encontrada.\n"

    # Header
    lines.append(f"{'Timestamp':<19}  {'Task':<12}  {'Status':<10}  {'Duracao':>10}  {'Rows':>5}")
    lines.append("-" * 70)

    for e in executions:
        ts = _format_timestamp(e.get("timestamp", ""))
        task = e.get("task_name", "?")[:12]
        status = e.get("status", "?")[:10]
        duration = e.get("duration_ms", 0)
        duration_str = _format_size(float(duration)) if duration else "—"
        rows = e.get("rows_affected", 0)

        lines.append(f"{ts:<19}  {task:<12}  {status:<10}  {duration_str:>10}  {rows:>5}")

    lines.append("")
    lines.append(f"Total: {len(executions)} execucoes")

    return "\n".join(lines)


def _format_json(data: dict[str, Any]) -> str:
    """Serializa data como JSON (indentado)."""
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _format_csv(data: dict[str, Any]) -> str:
    """
    Serializa execuções como CSV.

    Funciona apenas pra report_type='list' ou 'errors'. Pra 'summary',
    retorna mensagem de aviso.
    """
    if "executions" not in data:
        return (
            "# CSV nao disponivel pra report_type='summary'\n# Use --type list ou --type errors\n"
        )

    executions = data["executions"]
    if not executions:
        return "# Nenhuma execucao encontrada\n"

    # Determina colunas a partir do primeiro registro
    fieldnames = list(executions[0].keys())

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in executions:
        writer.writerow(row)

    return buffer.getvalue()


# ============================================================
# Comando CLI
# ============================================================


@click.command(name="report")
@click.option(
    "--task",
    "-t",
    "task_name",
    type=str,
    default=None,
    help="Filtra por nome de task (ex: validate, backup).",
)
@click.option(
    "--status",
    "-s",
    type=str,
    default=None,
    help="Filtra por status (success/failure/partial/dry_run/skipped).",
)
@click.option(
    "--days",
    type=int,
    default=1,
    show_default=True,
    help="Ultimos N dias (ignorado se --since for passado).",
)
@click.option(
    "--since",
    type=click.DateTime(formats=["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]),
    default=None,
    help="Data inicial (formato: YYYY-MM-DD ou 'YYYY-MM-DD HH:MM:SS').",
)
@click.option(
    "--until",
    type=click.DateTime(formats=["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]),
    default=None,
    help="Data final (formato: YYYY-MM-DD ou 'YYYY-MM-DD HH:MM:SS').",
)
@click.option(
    "--type",
    "report_type",
    type=click.Choice(["summary", "list", "errors"], case_sensitive=False),
    default="summary",
    show_default=True,
    help="Tipo de relatorio.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Formato de saida.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Salva relatorio em arquivo (default: stdout).",
)
@click.option(
    "--limit",
    type=int,
    default=100,
    show_default=True,
    help="Maximo de execucoes em list/errors.",
)
@click.option(
    "--audit-db-path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    hidden=True,
    help="Caminho interno do audit DB para testes.",
)
@click.pass_obj
def report(  # noqa: PLR0912
    ctx: CLIContext,
    task_name: str | None,
    status: str | None,
    days: int,
    since: datetime | None,
    until: datetime | None,
    report_type: str,
    output_format: str,
    output: Path | None,
    limit: int,
    audit_db_path: Path | None,
) -> None:
    """
    Gera relatorios do audit trail.

    Lê o histórico de execuções (audit DB) e mostra estatísticas
    agregadas (summary), lista detalhada (list) ou apenas falhas
    (errors).

    Períodos: por default mostra as últimas 24h. Use --days N para
    mais dias ou --since/--until para período customizado.

    Exemplos:

      $ autotarefas report                          # summary 24h
      $ autotarefas report --days 7                 # ultima semana
      $ autotarefas report --task validate          # so validate
      $ autotarefas report --type list --limit 50  # lista detalhada
      $ autotarefas report --format json -o rel.json
    """
    console = Console(ctx)

    # 1. Calcula periodo efetivo
    actual_since, actual_until = _calculate_period(since, until, days)

    # 2. Constroi filters (pode levantar ValidationError)
    try:
        filters = ReportFilters(
            task_name=task_name,
            status=status,
            since=actual_since,
            until=actual_until,
            limit=limit,
        )
    except ValidationError as e:
        console.error(f"Filtros invalidos: {e}")
        raise click.exceptions.Exit(2) from e

    # 3. Roda task
    task_obj = ReportAuditTask(
        filters=filters,
        report_type=report_type,  # type: ignore[arg-type]
        audit_db_path=audit_db_path,
        dry_run=ctx.dry_run,
    )
    result = task_obj.run()

    # 4. Trata SKIPPED (audit DB nao existe ainda)
    if result.status == TaskStatus.SKIPPED:
        console.warning(result.error_message or "Nenhum dado disponivel.")
        return

    # 5. Trata falha
    if result.is_failure:
        console.error(f"Falha ao gerar relatorio: {result.error_message}")
        raise click.exceptions.Exit(1)

    # 6. Trunca se passou do limite (em list/errors)
    if report_type in ("list", "errors"):
        executions = result.data.get("executions", [])
        if len(executions) >= limit:
            console.warning(f"Resultado truncado em {limit} linhas. Use --limit N para ajustar.")

    # 7. Formata
    if output_format == "table":
        if report_type == "summary":
            formatted = _format_summary_table(result.data)
        else:
            formatted = _format_list_table(result.data)
    elif output_format == "json":
        formatted = _format_json(result.data)
    else:  # csv
        formatted = _format_csv(result.data)

    # 8. Escreve (stdout ou arquivo)
    if output is not None:
        if ctx.dry_run:
            console.warning(f"[DRY-RUN] Salvaria em: {output}")
            click.echo(formatted)
            return

        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(formatted, encoding="utf-8")
        except OSError as e:
            console.error(f"Falha ao salvar arquivo: {e}")
            raise click.exceptions.Exit(1) from e

        console.success(f"Relatorio salvo em: {output}")
    else:
        click.echo(formatted)


__all__ = ["report"]
