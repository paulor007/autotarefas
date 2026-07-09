"""
Subcomando `extract api`: extracao de dados via API REST paginada.

Destino deste arquivo:
    src/autotarefas/cli/commands/extract/api.py

"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import click

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.extract_api import ExtractApiTask

if TYPE_CHECKING:
    from autotarefas.cli.context import CLIContext
    from autotarefas.core.base import TaskResult

# Exit codes
_EXIT_USAGE = 2
_EXIT_FAILURE = 1

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_SEP = "=" * 60


def _is_localhost(url: str) -> bool:
    """True se a URL aponta para um host local."""
    return urlparse(url).hostname in _LOCAL_HOSTS


def _gerar_artefatos(task: ExtractApiTask, result: TaskResult, out_dir: Path) -> None:
    """Gera os 3 artefatos da Exportacao e imprime os caminhos."""
    from autotarefas.tasks.extract_artifacts import write_extract_artifacts

    try:
        csv_path, xlsx_path, report = write_extract_artifacts(
            task.extracted_records, result, out_dir
        )
    except OSError as exc:
        click.secho(f"Erro ao gerar artefatos: {exc}", fg="red", err=True)
        return
    click.secho(f"Dados (CSV):    {csv_path}", fg="green")
    click.secho(f"Dados (Excel):  {xlsx_path}", fg="green")
    click.secho(f"Relatorio JSON: {report}", fg="green")


def _imprimir_sucesso(
    result: TaskResult,
    task: ExtractApiTask,
    out_dir: Path | None,
    output: Path | None,
    *,
    dry_run: bool,
) -> None:
    """Imprime o desfecho de uma extracao bem-sucedida (e gera artefatos)."""
    if dry_run:
        click.secho(
            f"[dry-run] Extrairia {result.data.get('would_extract')} "
            f"registros em {result.data.get('total_pages')} paginas",
            fg="cyan",
        )
        if out_dir is not None:
            click.secho(f"[dry-run] Geraria os artefatos em: {out_dir}", fg="cyan")
        return
    if result.data.get("saved"):
        click.secho(f"Extraidos {result.rows_affected} registros", fg="green")
        if out_dir is not None:
            _gerar_artefatos(task, result, out_dir)
        else:
            click.secho(f"Arquivo: {result.data.get('output_path')}", fg="green")
        return
    click.secho("Nenhum registro retornado pela API (nada salvo).", fg="yellow")


@click.command(name="api")
@click.option(
    "--url",
    "-u",
    required=True,
    help="Endpoint da API paginada (http:// ou https://).",
)
@click.option(
    "--output",
    "-o",
    "output",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Arquivo de saida unico (.csv, .xlsx ou .json).",
)
@click.option(
    "--out-dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help=(
        "Diretorio de saida do pacote de artefatos: dados_extraidos.csv, "
        "dados_extraidos.xlsx e extracao_report.json."
    ),
)
@click.option(
    "--per-page",
    default=50,
    show_default=True,
    help="Itens por pagina a solicitar.",
)
@click.option(
    "--max-pages",
    default=None,
    type=int,
    help="Limite de paginas (default: todas).",
)
@click.option(
    "--delay",
    default=0.0,
    type=float,
    show_default=True,
    help="Pausa entre paginas em segundos (rate limit).",
)
@click.option(
    "--api-key",
    default=None,
    help="Chave de API (enviada no header X-API-Key).",
)
@click.option(
    "--timeout",
    default=30.0,
    type=float,
    show_default=True,
    help="Timeout por request em segundos.",
)
@click.option(
    "--max-retries",
    default=3,
    type=int,
    show_default=True,
    help="Tentativas por pagina em erro temporario.",
)
@click.pass_obj
def api_command(
    ctx: CLIContext,
    url: str,
    output: Path | None,
    out_dir: Path | None,
    per_page: int,
    max_pages: int | None,
    delay: float,
    api_key: str | None,
    timeout: float,
    max_retries: int,
) -> None:
    """
    Extrai dados de uma API REST paginada e salva em arquivo.

    A API deve retornar JSON com 'data' (lista) e 'has_next' (bool).
    Informe --out-dir (pacote de artefatos: CSV + XLSX + report JSON) e/ou
    --output (arquivo unico, formato pela extensao). Pelo menos um dos dois.

    \b
    Exemplos:
      autotarefas extract api -u http://localhost:5555/api/clientes --out-dir saida/
      autotarefas extract api -u https://api.exemplo.com/itens -o dados.xlsx --delay 0.5
    """
    # Precisa de ao menos um destino (erro de uso -> exit 2)
    if output is None and out_dir is None:
        click.secho(
            "Erro: informe --out-dir e/ou --output (pelo menos um destino).",
            fg="red",
            err=True,
        )
        raise SystemExit(_EXIT_USAGE)

    # Validacao de URL (erro de uso -> exit 2)
    if not url.startswith(("http://", "https://")):
        click.secho(
            "Erro: a URL deve comecar com http:// ou https://",
            fg="red",
            err=True,
        )
        raise SystemExit(_EXIT_USAGE)

    # Aviso de seguranca: api-key sobre http externo (sem TLS)
    if api_key and url.startswith("http://") and not _is_localhost(url):
        click.secho(
            "Aviso: enviar --api-key sobre http:// (sem TLS) expoe a chave "
            "em transito. Prefira https://.",
            fg="yellow",
            err=True,
        )

    dry_run = bool(ctx.dry_run)

    # A task exige um output_path. Se so --out-dir foi dado, a extracao usa
    # o CSV canonico do pacote como destino "primario"; o XLSX/JSON saem na
    # geracao de artefatos. Se --output foi dado, ele manda.
    from autotarefas.tasks.extract_artifacts import DATA_CSV_NAME

    primary_output = output if output is not None else (out_dir / DATA_CSV_NAME)  # type: ignore[operator]

    # Header
    click.echo(_SEP)
    click.secho(" Exportacao automatica de dados", bold=True)
    click.echo(_SEP)
    click.echo(f"URL:    {url}")
    if out_dir is not None:
        click.echo(f"Saida:  {out_dir} (pacote de artefatos)")
    else:
        click.echo(f"Saida:  {output}")
    modo = "dry-run (preview, nao salva)" if dry_run else "normal"
    click.echo(f"Modo:   {modo}")
    click.echo("")

    def _on_progress(info: dict[str, object]) -> None:
        total = info.get("total_pages") or "?"
        click.echo(
            f"  Pagina {info['page']}/{total} ... "
            f"{info['records']} registros (total: {info['accumulated']})",
        )

    # Cria a task (ValidationError -> exit 2)
    try:
        task = ExtractApiTask(
            url=url,
            output_path=primary_output,
            per_page=per_page,
            max_pages=max_pages,
            delay_s=delay,
            api_key=api_key,
            timeout_s=timeout,
            max_retries=max_retries,
            on_progress=None if dry_run else _on_progress,
            dry_run=dry_run,
        )
    except ValidationError as exc:
        click.secho(f"Erro de configuracao: {exc}", fg="red", err=True)
        raise SystemExit(_EXIT_USAGE) from exc

    result = task.run()

    # Resultado
    click.echo("")
    click.echo(_SEP)

    if result.status == TaskStatus.SUCCESS:
        _imprimir_sucesso(result, task, out_dir, output, dry_run=dry_run)
        click.echo(_SEP)
        return

    # Failure -> exit 1
    click.secho(f"Falha: {result.error_message}", fg="red", err=True)
    click.echo(_SEP)
    raise SystemExit(_EXIT_FAILURE)


__all__ = ["api_command"]
