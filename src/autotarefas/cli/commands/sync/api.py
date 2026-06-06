"""
Subcomando `sync api`: sincronizacao de dados entre duas APIs.

Extrai de uma API origem e envia para uma API destino (compoe as tasks
de extracao e envio).

Destino deste arquivo:
    src/autotarefas/cli/commands/sync/api.py
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import click

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.sync_api import SyncApiTask

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
    "--source-url",
    "-s",
    required=True,
    help="API origem: endpoint paginado para extrair (http:// ou https://).",
)
@click.option(
    "--dest-url",
    "-d",
    required=True,
    help="API destino: recebe POST de cada registro (http:// ou https://).",
)
@click.option(
    "--source-api-key",
    default=None,
    help="Chave da API origem (header X-API-Key).",
)
@click.option(
    "--dest-api-key",
    default=None,
    help="Chave da API destino (header X-API-Key).",
)
@click.option(
    "--dest-bearer",
    default=None,
    help="Token Bearer da API destino (Authorization).",
)
@click.option(
    "--per-page",
    default=50,
    show_default=True,
    help="Itens por pagina na extracao.",
)
@click.option(
    "--max-pages",
    default=None,
    type=int,
    help="Limite de paginas a extrair (padrao: todas).",
)
@click.option(
    "--delay",
    default=0.0,
    type=float,
    show_default=True,
    help="Pausa em segundos entre paginas e entre envios (rate limit).",
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
    help="Tentativas por pagina/linha em erro temporario.",
)
@click.option(
    "--report",
    "-r",
    "report",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Relatorio por linha do envio (.csv/.xlsx/.json).",
)
@click.option(
    "--format",
    "intermediate_format",
    default="csv",
    type=click.Choice(["csv", "xlsx"]),
    show_default=True,
    help="Formato do arquivo intermediario.",
)
@click.pass_obj
def api_command(  # noqa: PLR0915
    ctx: CLIContext,
    source_url: str,
    dest_url: str,
    source_api_key: str | None,
    dest_api_key: str | None,
    dest_bearer: str | None,
    per_page: int,
    max_pages: int | None,
    delay: float,
    timeout: float,
    max_retries: int,
    report: Path | None,
    intermediate_format: str,
) -> None:
    """
    Sincroniza registros de uma API origem para uma API destino.

    Extrai todos os registros da origem (paginada) e faz POST de cada um
    no destino. Tolerante a falhas por registro; uma falha nao interrompe
    os demais.

    \b
    Exemplos:
      autotarefas sync api -s http://origem.local/api/clientes -d https://destino.com/api/clientes
      autotarefas sync api -s URL_ORIGEM -d URL_DESTINO --dest-api-key SEGREDO -r resultado.csv
    """
    # Validacao das URLs (erro de uso -> exit 2)
    for label, u in (("--source-url", source_url), ("--dest-url", dest_url)):
        if not u.startswith(("http://", "https://")):
            click.secho(
                f"Erro: {label} deve comecar com http:// ou https://",
                fg="red",
                err=True,
            )
            raise SystemExit(_EXIT_USAGE)

    # Avisos de seguranca: credencial sobre http externo (sem TLS)
    if source_api_key and source_url.startswith("http://") and not _is_localhost(source_url):
        click.secho(
            "Aviso: --source-api-key sobre http:// externo (sem TLS) "
            "expoe a chave em transito. Prefira https://.",
            fg="yellow",
            err=True,
        )
    if (
        (dest_api_key or dest_bearer)
        and dest_url.startswith("http://")
        and not _is_localhost(dest_url)
    ):
        click.secho(
            "Aviso: credencial do destino sobre http:// externo (sem TLS) "
            "fica exposta em transito. Prefira https://.",
            fg="yellow",
            err=True,
        )

    dry_run = bool(ctx.dry_run)

    # Header
    click.echo(_SEP)
    click.secho(" Sincronizacao API -> API", bold=True)
    click.echo(_SEP)
    click.echo(f"Origem:  {source_url}")
    click.echo(f"Destino: {dest_url}")
    modo = "dry-run (testa origem, nao envia)" if dry_run else "normal"
    click.echo(f"Modo:    {modo}")
    click.echo("")

    def _on_progress(info: dict[str, object]) -> None:
        marca = click.style("OK", fg="green") if info["sucesso"] else click.style("FALHA", fg="red")
        click.echo(
            f"  [{info['linha']}/{info['total']}] [{marca}] {info['mensagem']}",
        )

    # Cria a task (ValidationError -> exit 2)
    try:
        task = SyncApiTask(
            source_url=source_url,
            dest_url=dest_url,
            source_api_key=source_api_key,
            dest_api_key=dest_api_key,
            dest_bearer_token=dest_bearer,
            per_page=per_page,
            max_pages=max_pages,
            delay_s=delay,
            timeout_s=timeout,
            max_retries=max_retries,
            report_path=report,
            intermediate_format=intermediate_format,
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

    if dry_run:
        click.secho(
            "[dry-run] Origem testada; sincronizacao nao executada.",
            fg="cyan",
        )
        click.echo(_SEP)
        return

    # Extracao falhou antes de enviar
    if result.status == TaskStatus.FAILURE and result.data.get("stage") == "extract":
        click.secho(
            result.error_message or "Extracao da origem falhou.",
            fg="red",
            err=True,
        )
        click.echo(_SEP)
        raise SystemExit(_EXIT_FAILURE)

    extraidos = result.data.get("extraidos", 0)
    enviados = result.data.get("enviados", 0)
    falhas = result.data.get("falhas", 0)

    click.echo(f"Extraidos: {extraidos}")
    click.secho(f"Enviados:  {enviados}", fg="green")
    if falhas:
        click.secho(f"Falhas:    {falhas}", fg="red")
    else:
        click.echo(f"Falhas:    {falhas}")
    if result.data.get("report_path"):
        click.echo(f"Relatorio: {result.data['report_path']}")
    click.echo(_SEP)

    if result.status == TaskStatus.PARTIAL:
        click.secho(
            "Alguns registros falharam. Veja o relatorio para os detalhes.",
            fg="yellow",
        )
    elif result.status == TaskStatus.FAILURE:
        click.secho(
            "Sincronizacao falhou (nenhum registro enviado).",
            fg="red",
            err=True,
        )
        raise SystemExit(_EXIT_FAILURE)


__all__ = ["api_command"]
