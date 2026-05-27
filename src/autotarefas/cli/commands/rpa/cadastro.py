"""
Comando ``autotarefas rpa cadastro`` — cadastra registros web em massa.

Le uma planilha CSV/Excel e cadastra cada linha em um sistema web.
Por seguranca, so aceita URLs locais (localhost/127.0.0.1) por default.
Para URLs remotas, exige a flag ``--allow-remote``.

Uso:
    autotarefas rpa cadastro --planilha clientes.csv --site http://localhost:5555
    autotarefas rpa cadastro --planilha c.csv --site http://localhost:5555 --show-browser
    autotarefas rpa cadastro --planilha c.csv --site http://demo.empresa.com --allow-remote
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.rpa_cadastro import RPACadastroTask

# ============================================================
# Constantes
# ============================================================

#: Hosts considerados "seguros" (locais) por default.
_SAFE_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})


# ============================================================
# Helpers
# ============================================================


def _is_local_url(url: str) -> bool:
    """Retorna True se a URL aponta para hosts locais (localhost/127.0.0.1)."""
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return False
    if parsed.hostname is None:
        return False
    return parsed.hostname.lower() in _SAFE_HOSTS


def _format_progress_line(op: dict[str, Any], idx: int, total: int) -> str:
    """Formata uma linha de progresso pra ser printada durante execucao."""
    nome = op.get("nome", "") or ""
    nome_short = nome[:30]
    status = op.get("status", "?")
    prefix = f"[{idx + 1}/{total}] {nome_short:30s} ..."

    if status == "success":
        rid = op.get("record_id", "?")
        return f"{prefix} [OK] ID: {rid}"
    if status in ("would_create",):
        return f"{prefix} [WOULD CREATE]"
    if status in ("skipped", "would_skip"):
        err = op.get("error", "") or ""
        # Limpa quebras de linha do erro pra ficar em uma linha so
        err_clean = " ".join(err.split())[:80]
        return f"{prefix} [SKIP] {err_clean}"
    # error ou would_error
    err = op.get("error", "") or ""
    err_clean = " ".join(err.split())[:80]
    return f"{prefix} [ERR]  {err_clean}"


def _print_header(
    console: Console,
    planilha: Path,
    site: str,
    headless: bool,
    dry_run: bool,
) -> None:
    """Imprime cabecalho do comando."""
    bar = "=" * 60
    mode = (
        "DRY-RUN (simulacao)"
        if dry_run
        else ("headless" if headless else "headful (mostra navegador)")
    )

    click.echo(bar)
    click.echo(" RPA Cadastro")
    click.echo(bar)
    click.echo(f"Planilha: {planilha}")
    click.echo(f"Site:     {site}")
    click.echo(f"Modo:     {mode}")
    click.echo()
    click.echo("Processando...")
    click.echo()


def _print_summary(
    data: dict[str, Any],
    duration_ms: int,
) -> None:
    """Imprime sumario apos execucao."""
    bar = "=" * 60
    click.echo()
    click.echo(bar)
    click.echo(f"Total:    {data['total']} linhas processadas")
    click.echo(f"Sucesso:  {data['success_count']} cadastros realizados")
    click.echo(f"Skipped:  {data['skipped_count']} linhas puladas")
    click.echo(f"Erros:    {data['error_count']}")
    click.echo(f"Tempo:    {duration_ms / 1000:.1f}s")
    click.echo(bar)


# ============================================================
# Comando
# ============================================================


@click.command(name="cadastro")
@click.option(
    "--planilha",
    "-p",
    type=click.Path(
        exists=True,
        dir_okay=False,
        file_okay=True,
        readable=True,
        path_type=Path,
    ),
    required=True,
    help="Path da planilha CSV/XLSX com os cadastros.",
)
@click.option(
    "--site",
    "-s",
    type=str,
    required=True,
    help="URL base do sistema alvo (ex: http://localhost:5555).",
)
@click.option(
    "--show-browser",
    is_flag=True,
    default=False,
    help="Mostra janela do navegador (default: headless).",
)
@click.option(
    "--no-screenshot",
    is_flag=True,
    default=False,
    help="Desabilita screenshots automaticas em erro.",
)
@click.option(
    "--allow-remote",
    is_flag=True,
    default=False,
    help=(
        "Permite URLs nao-locais (producao, homolog). "
        "Por seguranca, apenas localhost/127.0.0.1 sao aceitos por default."
    ),
)
@click.pass_obj
def cadastro(
    ctx: CLIContext,
    planilha: Path,
    site: str,
    show_browser: bool,
    no_screenshot: bool,
    allow_remote: bool,
) -> None:
    """
    Cadastra registros web a partir de planilha CSV/Excel.

    Le linha a linha e usa um navegador Chromium pra preencher o
    formulario de cadastro do sistema alvo. Valida CPF localmente
    antes de cadastrar (pula linhas com CPF invalido).

    Por default, executa em modo headless (sem janela). Use
    --show-browser pra visualizar a execucao (util pra debug).

    Exit codes:
      0 - Sucesso, parcial, ou skipped (servidor offline)
      1 - Falha geral
      2 - Erro de uso (URL invalida, etc.)
    """
    console = Console(ctx)

    # 1. Valida URL
    if not site.startswith(("http://", "https://")):
        console.error(f"URL invalida: '{site}'. Deve comecar com http:// ou https://")
        raise click.exceptions.Exit(2)

    if not _is_local_url(site) and not allow_remote:
        console.error(
            f"URL nao-local detectada: '{site}'. "
            f"Por seguranca, RPA so roda contra localhost/127.0.0.1 por default. "
            f"Use --allow-remote se tiver certeza que pode automatizar este sistema."
        )
        raise click.exceptions.Exit(2)

    # 2. Cria task
    try:
        task = RPACadastroTask(
            planilha_path=planilha,
            base_url=site,
            headless=not show_browser,
            screenshot_on_error=not no_screenshot,
            on_progress=lambda op: None,  # placeholder; sera substituido
            dry_run=ctx.dry_run,
        )
    except ValidationError as exc:
        console.error(f"Erro ao criar task: {exc}")
        raise click.exceptions.Exit(2) from exc

    # 3. Imprime cabecalho
    _print_header(
        console,
        planilha=planilha,
        site=site,
        headless=not show_browser,
        dry_run=ctx.dry_run,
    )

    # 4. Configura callback de progresso
    # Como nao sabemos o total ate ler a planilha, vamos contar dinamicamente
    progress_state: dict[str, int] = {"current": 0, "total": 0}

    def on_progress(op: dict[str, Any]) -> None:
        idx = progress_state["current"]
        total = progress_state["total"] or (idx + 1)
        line = _format_progress_line(op, idx, total)
        click.echo(line)
        progress_state["current"] = idx + 1

    task.on_progress = on_progress

    # 5. Roda a task
    # Tentei o total da planilha pra mostrar progresso melhor
    try:
        import pandas as pd

        suffix = planilha.suffix.lower()
        if suffix == ".csv":
            progress_state["total"] = len(pd.read_csv(planilha, dtype=str))
        elif suffix in (".xlsx", ".xls"):
            progress_state["total"] = len(pd.read_excel(planilha, dtype=str))
    except Exception as exc:
        console.warning(f"Nao foi possivel calcular o total previamente: {exc}")

    result = task.run()

    # 6. Trata resultado
    if result.status == TaskStatus.SKIPPED:
        click.echo()
        console.warning(f"Task skipped: {result.error_message or 'sem detalhes'}")
        return  # exit 0 (skipped nao eh erro)

    if result.status == TaskStatus.FAILURE:
        click.echo()
        console.error(f"Task falhou: {result.error_message or 'sem detalhes'}")
        raise click.exceptions.Exit(1)

    # 7. Imprime sumario (success ou partial)
    _print_summary(result.data, result.duration_ms)

    # 8. Avisa se foi parcial
    if result.status == TaskStatus.PARTIAL:
        click.echo()
        console.warning(f"Execucao PARCIAL: {result.data['error_count']} linha(s) com erro.")


__all__ = ["cadastro"]
