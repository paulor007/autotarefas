"""
Comando ``autotarefas dashboard`` — gera o dashboard HTML do audit trail.

Le o historico de execucoes (audit DB), monta uma pagina HTML estatica e
autocontida (resumo + tabela + indicacao do input_hash) e a grava em
disco. Opcionalmente abre o arquivo no navegador padrao.

Orquestra as camadas do pacote ``autotarefas.dashboard``:
``read_entries`` (dados) + ``summarize`` (resumo) + ``render_dashboard``
(HTML). Nao sobe servidor e nao adiciona dependencia (o ``--open`` usa
apenas a stdlib ``webbrowser``).

Uso tipico:
    $ autotarefas dashboard
    $ autotarefas dashboard --output relatorios/audit.html --open
    $ autotarefas dashboard --task validate --status failure --limit 50
"""

from __future__ import annotations

import webbrowser
from datetime import UTC, datetime
from pathlib import Path

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.dashboard import read_entries, render_dashboard, summarize

_DEFAULT_OUTPUT = Path("dashboard.html")


@click.command(name="dashboard")
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=_DEFAULT_OUTPUT,
    show_default=True,
    help="Arquivo HTML de saida.",
)
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
    "--limit",
    type=int,
    default=100,
    show_default=True,
    help="Maximo de execucoes incluidas.",
)
@click.option(
    "--open",
    "open_browser",
    is_flag=True,
    default=False,
    help="Abre o dashboard gerado no navegador padrao.",
)
@click.pass_obj
def dashboard(
    ctx: CLIContext,
    output: Path,
    task_name: str | None,
    status: str | None,
    limit: int,
    open_browser: bool,
) -> None:
    """
    Gera o dashboard HTML do audit trail.

    Le as execucoes registradas, monta uma pagina HTML estatica e
    autocontida e a grava em --output (default: dashboard.html). Com
    --open, abre o arquivo gerado no navegador padrao.

    Exemplos:

      $ autotarefas dashboard
      $ autotarefas dashboard -o relatorios/audit.html --open
      $ autotarefas dashboard --task validate --limit 50
    """
    console = Console(ctx)

    # 1. Le os dados (camada reader) e resume.
    entries = read_entries(task_name=task_name, status=status, limit=limit)
    summary = summarize(entries)

    if not entries:
        console.warning("Nenhuma execucao no audit; gerando dashboard vazio.")

    # 2. Renderiza o HTML (camada renderer). Hora local (aware) para exibir.
    html = render_dashboard(
        entries,
        summary,
        generated_at=datetime.now(UTC).astimezone(),
    )

    # 3. Dry-run: nao escreve nem abre.
    if ctx.dry_run:
        console.warning(f"[DRY-RUN] Geraria o dashboard em: {output}")
        return

    # 4. Grava o arquivo (cria diretorios pais se necessario).
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html, encoding="utf-8")
    except OSError as e:
        console.error(f"Falha ao salvar o dashboard: {e}")
        raise click.exceptions.Exit(1) from e

    console.success(f"Dashboard gerado em: {output}")

    # 5. Abre no navegador, se pedido (best-effort).
    if open_browser:
        opened = webbrowser.open(output.resolve().as_uri())
        if not opened:
            console.warning("Nao foi possivel abrir o navegador automaticamente.")


__all__ = ["dashboard"]
