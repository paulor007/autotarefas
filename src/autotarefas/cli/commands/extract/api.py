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

# Exit codes
_EXIT_USAGE = 2
_EXIT_FAILURE = 1

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_SEP = "=" * 60


def _is_localhost(url: str) -> bool:
    """True se a URL aponta para um host local."""
    return urlparse(url).hostname in _LOCAL_HOSTS


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
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Arquivo de saida (.csv, .xlsx ou .json).",
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
    output: Path,
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
    O formato de saida e definido pela extensao do --output.

    \b
    Exemplos:
      autotarefas extract api -u http://localhost:5555/api/clientes -o saida.csv
      autotarefas extract api -u https://api.exemplo.com/itens -o dados.xlsx --delay 0.5
    """
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

    # Header
    click.echo(_SEP)
    click.secho(" Extracao via API", bold=True)
    click.echo(_SEP)
    click.echo(f"URL:    {url}")
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
            output_path=output,
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
        if dry_run:
            click.secho(
                f"[dry-run] Extrairia {result.data.get('would_extract')} "
                f"registros em {result.data.get('total_pages')} paginas",
                fg="cyan",
            )
        elif result.data.get("saved"):
            click.secho(
                f"Extraidos {result.rows_affected} registros -> {result.data.get('output_path')}",
                fg="green",
            )
        else:
            click.secho(
                "Nenhum registro retornado pela API (nada salvo).",
                fg="yellow",
            )
        click.echo(_SEP)
        return

    # Failure -> exit 1
    click.secho(f"Falha: {result.error_message}", fg="red", err=True)
    click.echo(_SEP)
    raise SystemExit(_EXIT_FAILURE)


__all__ = ["api_command"]
