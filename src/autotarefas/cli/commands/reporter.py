"""
Comandos de Relatórios do AutoTarefas.

Gera relatórios em diversos formatos.

Uso:
    $ autotarefas report sales --format html
    $ autotarefas report sales --csv vendas.csv --period "Janeiro 2024"
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Final

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from autotarefas.cli.utils.click_utils import get_console, is_dry_run
from autotarefas.config import settings
from autotarefas.core.logger import logger
from autotarefas.tasks.sales_report import SalesData, SalesReportTask
from autotarefas.utils.helpers import ensure_dir, get_unique_filename

SUPPORTED_FORMATS: Final[list[str]] = ["txt", "html", "json", "csv", "md"]


# =============================================================================
# Helpers
# =============================================================================


def _now_stamp() -> str:
    """Gera timestamp curto para nomes de arquivo."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _print_header(console: Console, title: str) -> None:
    """Imprime um cabeçalho padrão para os comandos de relatório."""
    console.print()
    console.print(
        Panel.fit(f"[bold blue]AutoTarefas[/] - {title}", border_style="blue")
    )
    console.print()


def _resolve_output_path(
    output: Path | None, output_format: str, *, default_stem: str
) -> Path:
    """
    Resolve o caminho de saída do relatório e garante extensão.

    Regras:
    - Se o usuário informou `--output`:
        - se já tem extensão: respeita
        - se não tem: adiciona .<format>
    - Se não informou:
        - usa settings.REPORTS_PATH / "<stem>_<timestamp>.<format>"
    - Garante que o diretório pai exista.
    - Evita sobrescrever: se o arquivo já existir, cria nome único.
    """
    fmt = output_format.lower().strip()

    if output is not None:
        p = output.expanduser()
        if not p.suffix:
            p = p.with_suffix(f".{fmt}")
        ensure_dir(p.parent)
        return get_unique_filename(p)

    # padrão
    base_dir = ensure_dir(settings.REPORTS_PATH)
    name = f"{default_stem}_{_now_stamp()}.{fmt}"
    return get_unique_filename(base_dir / name)


def _open_file(path: Path, console: Console) -> None:
    """
    Abre arquivo no sistema operacional (best effort).

    - Windows: os.startfile
    - macOS: open
    - Linux: xdg-open
    """
    try:
        p = str(path)
        if sys.platform == "win32":
            os.startfile(p)  # type: ignore[attr-defined]
            return
        if sys.platform == "darwin":
            subprocess.run(["open", p], check=False)
            return
        subprocess.run(["xdg-open", p], check=False)
    except Exception as e:
        console.print(f"[yellow]⚠️  Não foi possível abrir automaticamente: {e}[/]")


def _build_sales_data(
    *,
    csv_file: Path | None,
    period: str | None,
    total: float | None,
    transactions: int | None,
) -> tuple[SalesData, str]:
    """
    Monta SalesData a partir da fonte escolhida e retorna (sales_data, source_label).

    Prioridade:
    1) CSV
    2) Manual (total/transactions)
    3) Exemplo
    """
    if csv_file is not None:
        source_label = f"Arquivo CSV ({csv_file})"
        sales_data = SalesData.from_csv(str(csv_file), period or "")
        return sales_data, source_label

    if total is not None or transactions is not None:
        source_label = "Dados manuais"
        sales_data = SalesData(
            period=period or "Período atual",
            total_sales=float(total or 0.0),
            transactions=int(transactions or 0),
        )
        return sales_data, source_label

    source_label = "Dados de exemplo"
    sales_data = SalesData(
        period=period or "Exemplo - Dezembro 2025",
        total_sales=157_890.50,
        transactions=1342,
        products_sold={
            "Produto Premium A": 245,
            "Produto Standard B": 512,
            "Serviço Mensal": 189,
            "Produto Basic C": 396,
        },
        categories={
            "Produtos": 98750.00,
            "Serviços": 45890.50,
            "Assinaturas": 13250.00,
        },
    )
    return sales_data, source_label


# =============================================================================
# CLI Group
# =============================================================================


@click.group()
@click.pass_context
def report(ctx: click.Context) -> None:
    """
    📊 Gera relatórios.

    Comandos para geração de relatórios em diversos formatos.
    """
    ctx.ensure_object(dict)


# =============================================================================
# report sales
# =============================================================================


@report.command("sales")
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(SUPPORTED_FORMATS, case_sensitive=False),
    default="html",
    show_default=True,
    help="Formato do relatório",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Arquivo de saída (se omitido, usa REPORTS_PATH)",
)
@click.option(
    "-c",
    "--csv",
    "csv_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Arquivo CSV com dados de vendas",
)
@click.option(
    "-p", "--period", default=None, help="Período do relatório (ex: 'Janeiro 2024')"
)
@click.option(
    "--total", type=float, default=None, help="Total de vendas (para relatório manual)"
)
@click.option(
    "--transactions",
    type=int,
    default=None,
    help="Número de transações (para relatório manual)",
)
@click.option(
    "--open/--no-open",
    "open_after",
    default=False,
    show_default=True,
    help="Abre o relatório após gerar",
)
@click.pass_context
def report_sales(
    ctx: click.Context,
    output_format: str,
    output: Path | None,
    csv_file: Path | None,
    period: str | None,
    total: float | None,
    transactions: int | None,
    open_after: bool,
) -> None:
    """
    💰 Gera relatório de vendas.

    Pode ser gerado a partir de:
      - Arquivo CSV com dados de vendas
      - Dados manuais (--total, --transactions)
      - Dados de exemplo (sem parâmetros)

    Formato do CSV esperado:
      product,quantity,unit_price,category,date

    Exemplos:
      autotarefas report sales --format html -o relatorio.html
      autotarefas report sales --csv vendas.csv --period "Janeiro 2024"
      autotarefas report sales --total 150000 --transactions 1250
    """
    console = get_console(ctx)
    dry_run = is_dry_run(ctx)

    _print_header(console, "Relatório de Vendas")

    output_format = output_format.lower().strip()
    sales_data, source_label = _build_sales_data(
        csv_file=csv_file,
        period=period,
        total=total,
        transactions=transactions,
    )
    output_path = _resolve_output_path(output, output_format, default_stem="vendas")

    # Plano da execução
    console.print(f"[bold]Fonte:[/] {source_label}")
    console.print(f"[bold]Formato:[/] {output_format.upper()}")
    console.print(f"[bold]Período:[/] {sales_data.period}")
    console.print(f"[bold]Saída:[/] {output_path}")
    console.print()

    if dry_run:
        console.print("[yellow]🔍 Modo dry-run: não vou gerar nem salvar arquivo.[/]")
        console.print("[dim]Dica: rode sem --dry-run para gerar o relatório.[/]")
        console.print()
        return

    # Geração
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Gerando relatório...", total=None)

        report_task = SalesReportTask()
        result = report_task.run(
            sales_data=sales_data,
            output_path=output_path,
            format=output_format,
        )

    if not result.is_success:
        logger.error(f"Falha ao gerar relatório de vendas: {result.message}")
        console.print(
            Panel(
                f"[red]❌ Falha ao gerar relatório[/]\n\n[bold]Erro:[/] {result.message}",
                title="[bold]Erro[/]",
                border_style="red",
            )
        )
        console.print()
        return

    data = result.data or {}
    output_file_raw = data.get("output_file")
    output_file = Path(output_file_raw).expanduser() if output_file_raw else output_path

    console.print(
        Panel(
            f"[green]✅ Relatório gerado com sucesso![/]\n\n"
            f"[bold]Arquivo:[/] {output_file}\n"
            f"[bold]Formato:[/] {output_format.upper()}\n"
            f"[bold]Duração:[/] {result.duration_formatted}",
            title="[bold]Relatório Gerado[/]",
            border_style="green",
        )
    )

    # Resumo (se existir)
    report_data = (data.get("data") or {}) if isinstance(data, dict) else {}
    resumo = (report_data.get("resumo") or {}) if isinstance(report_data, dict) else {}

    if resumo:
        console.print()
        table = Table(title="Resumo", show_header=True, header_style="bold cyan")
        table.add_column("Campo", style="cyan")
        table.add_column("Valor")
        for k, v in resumo.items():
            table.add_row(str(k), str(v))
        console.print(table)

    # Abrir (se solicitado)
    if open_after:
        console.print()
        console.print("[dim]Abrindo relatório...[/]")
        _open_file(output_file, console)

    console.print()


# =============================================================================
# report formats
# =============================================================================


@report.command("formats")
@click.pass_context
def report_formats(ctx: click.Context) -> None:
    """📋 Lista formatos de relatório disponíveis."""
    console = get_console(ctx)
    _print_header(console, "Formatos de Relatório")

    formats = [
        ("txt", "Texto simples", "Leitura rápida e compatível"),
        ("html", "HTML estilizado", "Visual bonito, abre no navegador"),
        ("json", "JSON estruturado", "Integração com sistemas/APIs"),
        ("csv", "CSV tabular", "Excel/planilhas"),
        ("md", "Markdown", "Documentação/GitHub"),
    ]

    table = Table(
        title="Formatos Disponíveis", show_header=True, header_style="bold cyan"
    )
    table.add_column("Formato", style="cyan")
    table.add_column("Descrição")
    table.add_column("Uso")

    for fmt, desc, uso in formats:
        table.add_row(fmt, desc, uso)

    console.print(table)
    console.print()
    console.print("[bold]Uso:[/]")
    console.print("  autotarefas report sales --format [formato] -o arquivo.ext")
    console.print()


# =============================================================================
# report templates
# =============================================================================


@report.command("templates")
@click.pass_context
def report_templates(ctx: click.Context) -> None:
    """📄 Lista templates de relatório disponíveis."""
    console = get_console(ctx)
    _print_header(console, "Templates de Relatório")

    templates = [
        ("sales", "Relatório de Vendas", "Vendas, transações, produtos, categorias"),
    ]

    table = Table(
        title="Templates Disponíveis", show_header=True, header_style="bold cyan"
    )
    table.add_column("Nome", style="cyan")
    table.add_column("Descrição")
    table.add_column("Conteúdo")

    for name, desc, content in templates:
        table.add_row(name, desc, content)

    console.print(table)
    console.print()
    console.print("[dim]Mais templates serão adicionados em versões futuras.[/]")
    console.print()


# =============================================================================
# report example-csv
# =============================================================================


@report.command("example-csv")
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("vendas_exemplo.csv"),
    show_default=True,
    help="Arquivo de saída",
)
@click.pass_context
def report_example_csv(ctx: click.Context, output: Path) -> None:
    """
    📝 Gera um arquivo CSV de exemplo para relatórios.

    Cria um CSV com dados de exemplo que pode ser usado como base.
    """
    console = get_console(ctx)
    dry_run = is_dry_run(ctx)

    _print_header(console, "CSV de Exemplo")

    csv_content = """product,quantity,unit_price,category,date
Produto Premium A,45,299.90,Produtos,2025-01-05
Produto Premium A,32,299.90,Produtos,2025-01-12
Produto Standard B,128,89.90,Produtos,2025-01-08
Produto Standard B,95,89.90,Produtos,2025-01-15
Serviço Mensal,67,149.90,Serviços,2025-01-10
Serviço Mensal,54,149.90,Serviços,2025-01-20
Produto Basic C,234,39.90,Produtos,2025-01-03
Produto Basic C,187,39.90,Produtos,2025-01-18
Assinatura Anual,23,599.90,Assinaturas,2025-01-07
Assinatura Anual,18,599.90,Assinaturas,2025-01-14
Consultoria,12,450.00,Serviços,2025-01-22
Suporte Premium,45,199.90,Serviços,2025-01-25
"""

    output_path = output.expanduser()
    ensure_dir(output_path.parent)

    if dry_run:
        console.print(
            f"[yellow]🔍 Modo dry-run: não vou escrever o arquivo {output_path}.[/]"
        )
        console.print()
        return

    output_path.write_text(csv_content, encoding="utf-8")

    console.print(f"[green]✅ Arquivo de exemplo criado: {output_path}[/]")
    console.print()
    console.print("[bold]Uso:[/]")
    console.print(
        f"  autotarefas report sales --csv {output_path} --period 'Janeiro 2024'"
    )
    console.print()


__all__ = ["report"]
