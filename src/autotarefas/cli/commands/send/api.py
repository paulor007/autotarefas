"""
Subcomando `send api`: envio em massa de uma planilha via API REST.

"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import click

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.send_api import SendApiTask

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


def _imprimir_resumo(result_data: dict[str, Any]) -> None:
    """Imprime o resumo final do envio (totais, categorias, dica)."""
    total = result_data.get("total", 0)
    enviados = result_data.get("enviados", 0)
    falhas = result_data.get("falhas", 0)
    reenviaveis = result_data.get("reenviaveis", 0)
    por_categoria: dict[str, int] = result_data.get("falhas_por_categoria", {})

    click.echo(f"Total:    {total}")
    click.secho(f"Enviados: {enviados}", fg="green")
    if falhas:
        click.secho(f"Falhas:   {falhas}", fg="red")
        detalhe = ", ".join(f"{cat}: {n}" for cat, n in por_categoria.items())
        if detalhe:
            click.echo(f"          ({detalhe})")
        cor_reenvio = "yellow" if reenviaveis else None
        click.secho(f"Reenviaveis: {reenviaveis}", fg=cor_reenvio)
    else:
        click.echo(f"Falhas:   {falhas}")
    if result_data.get("report_path"):
        click.echo(f"Relatorio: {result_data['report_path']}")
    click.echo(_SEP)

    # Dica de produto: falha dominada por erro de validacao -> a Auditoria
    # de planilha resolve (formata CPF/telefone/e-mail e separa os validos).
    falhas_validacao = por_categoria.get("validacao", 0)
    if falhas and falhas_validacao * 2 >= falhas:
        click.secho(
            "Dica: rode a Auditoria de planilha antes "
            "(autotarefas validate -s schema.yaml --mode limpeza --out-dir out/) "
            "para preparar os dados e enviar apenas os registros validos.",
            fg="cyan",
        )


@click.command(name="api")
@click.option(
    "--planilha",
    "-p",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Planilha CSV/XLSX com os registros a enviar.",
)
@click.option(
    "--url",
    "-u",
    required=True,
    help="Endpoint da API que recebe cada registro (http:// ou https://).",
)
@click.option(
    "--api-key",
    default=None,
    help="Chave de API (header X-API-Key).",
)
@click.option(
    "--bearer",
    default=None,
    help="Token Bearer (header Authorization: Bearer ...).",
)
@click.option(
    "--delay",
    default=0.0,
    type=float,
    show_default=True,
    help="Pausa entre envios em segundos (rate limit).",
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
    help="Tentativas por linha em erro temporario.",
)
@click.option(
    "--report",
    "-r",
    "report",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Arquivo de relatorio por linha (.csv/.xlsx/.json).",
)
@click.pass_obj
def api_command(
    ctx: CLIContext,
    planilha: Path,
    url: str,
    api_key: str | None,
    bearer: str | None,
    delay: float,
    timeout: float,
    max_retries: int,
    report: Path | None,
) -> None:
    """
    Envia os registros de uma planilha para uma API (POST por linha).

    Cada linha vira um JSON enviado para a API. Tolerante a falhas:
    uma linha ruim nao interrompe as demais. Use --report para salvar
    o resultado de cada linha.

    \b
    Exemplos:
      autotarefas send api -p clientes.csv -u http://localhost:5555/api/clientes
      autotarefas send api -p clientes.xlsx -u https://api.empresa.com/clientes -r saida.csv --delay 0.2
    """  # noqa: E501
    # Validacao de URL (erro de uso -> exit 2)
    if not url.startswith(("http://", "https://")):
        click.secho(
            "Erro: a URL deve comecar com http:// ou https://",
            fg="red",
            err=True,
        )
        raise SystemExit(_EXIT_USAGE)

    # Aviso de seguranca: credencial sobre http externo (sem TLS)
    tem_credencial = bool(api_key or bearer)
    if tem_credencial and url.startswith("http://") and not _is_localhost(url):
        click.secho(
            "Aviso: enviar credencial (--api-key/--bearer) sobre http:// "
            "(sem TLS) a expoe em transito. Prefira https://.",
            fg="yellow",
            err=True,
        )

    dry_run = bool(ctx.dry_run)

    # Header
    click.echo(_SEP)
    click.secho(" Envio via API", bold=True)
    click.echo(_SEP)
    click.echo(f"Planilha: {planilha}")
    click.echo(f"URL:      {url}")
    modo = "dry-run (nao envia)" if dry_run else "normal"
    click.echo(f"Modo:     {modo}")
    click.echo("")

    def _on_progress(info: dict[str, object]) -> None:
        marca = click.style("OK", fg="green") if info["sucesso"] else click.style("FALHA", fg="red")
        click.echo(
            f"  [{info['linha']}/{info['total']}] [{marca}] {info['mensagem']}",
        )
        tentativas = info.get("tentativas")
        if isinstance(tentativas, int) and tentativas > 1:
            click.secho(f"      ({tentativas} tentativas)", fg="yellow")

    # Cria a task (ValidationError -> exit 2)
    try:
        task = SendApiTask(
            planilha_path=planilha,
            url=url,
            api_key=api_key,
            bearer_token=bearer,
            delay_s=delay,
            timeout_s=timeout,
            max_retries=max_retries,
            report_path=report,
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
            f"[dry-run] Enviaria {result.data.get('would_send')} registros",
            fg="cyan",
        )
        click.echo(_SEP)
        return

    _imprimir_resumo(result.data)

    if result.status == TaskStatus.PARTIAL:
        click.secho(
            "Alguns registros falharam. Veja o relatorio para os detalhes.",
            fg="yellow",
        )
    elif result.status == TaskStatus.FAILURE:
        click.secho("Nenhum registro foi enviado.", fg="red", err=True)
        raise SystemExit(_EXIT_FAILURE)


__all__ = ["api_command"]
