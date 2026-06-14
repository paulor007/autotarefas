"""
Subcomando `send telegram`: envio de mensagens via Telegram (Bot API).

Destino deste arquivo:
    src/autotarefas/cli/commands/send/telegram.py

SEGURANCA: o token do bot NUNCA e um argumento de linha de comando. Ele
vem da variavel de ambiente AUTOTAREFAS_TELEGRAM_TOKEN ou de um prompt
oculto (getpass). Assim nao vaza no historico do shell nem em logs.
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import click

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.send_telegram import SendTelegramTask

if TYPE_CHECKING:
    from autotarefas.cli.context import CLIContext

# Exit codes
_EXIT_USAGE = 2
_EXIT_FAILURE = 1

# Nome da variavel de ambiente que guarda o token (NAO e o token)
_TELEGRAM_ENV_VAR = "_".join(("AUTOTAREFAS", "TELEGRAM", "TOKEN"))

_DEFAULT_BASE_URL = "https://api.telegram.org"
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_SEP = "=" * 60


def _resolver_token() -> tuple[str, str]:
    """
    Resolve o token do bot de forma segura.

    Tenta a env var; se ausente, pede num prompt oculto.
    Retorna (token, origem) — a origem e so para exibicao.
    """
    token = os.environ.get(_TELEGRAM_ENV_VAR)
    if token:
        return token, f"env {_TELEGRAM_ENV_VAR}"
    return getpass.getpass("Token do bot Telegram: "), "prompt"


@click.command(name="telegram")
@click.option(
    "--planilha",
    "-p",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Planilha CSV/XLSX com os dados.",
)
@click.option(
    "--text",
    default=None,
    help="Template da mensagem (aceita {coluna}).",
)
@click.option(
    "--text-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Arquivo com o template (precede --text).",
)
@click.option(
    "--chat-id",
    default=None,
    help="Chat de destino fixo (todas as mensagens vao para ele).",
)
@click.option(
    "--chat-id-column",
    default=None,
    help="OU a coluna da planilha com o chat_id de cada linha.",
)
@click.option(
    "--base-url",
    default=_DEFAULT_BASE_URL,
    show_default=True,
    help="Base da Bot API (use o demo local para testar sem bot real).",
)
@click.option(
    "--parse-mode",
    default=None,
    type=click.Choice(["MarkdownV2", "Markdown", "HTML"]),
    help="Formatacao da mensagem (opcional).",
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
    help="Tentativas por mensagem em erro temporario.",
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
def telegram_command(  # noqa: PLR0912, PLR0915
    ctx: CLIContext,
    planilha: Path,
    text: str | None,
    text_file: Path | None,
    chat_id: str | None,
    chat_id_column: str | None,
    base_url: str,
    parse_mode: str | None,
    delay: float,
    timeout: float,
    max_retries: int,
    report: Path | None,
) -> None:
    """
    Envia mensagens via Telegram (Bot API) a partir de uma planilha.

    O texto aceita {coluna}: trechos como {nome} sao trocados pelos
    valores da linha. Tolerante a falhas: uma mensagem ruim nao
    interrompe as demais.

    \b
    O token do bot nunca e passado na linha de comando. Defina:
      $env:AUTOTAREFAS_TELEGRAM_TOKEN = "123456:ABC..."   (PowerShell)
    ou ele sera solicitado num prompt oculto.

    \b
    Exemplos:
      # contra o demo local (mock; token fake serve)
      autotarefas send telegram -p contatos.csv --text "Ola {nome}!" \\
        --chat-id-column chat_id --base-url http://localhost:5555
      # contra o Telegram real (bot criado no @BotFather)
      autotarefas send telegram -p contatos.csv --text "Ola {nome}!" \\
        --chat-id 123456789
    """
    # Resolver texto (text-file precede text)
    if text_file is not None:
        template = text_file.read_text(encoding="utf-8")
    elif text is not None:
        template = text
    else:
        click.secho(
            "Erro: informe o texto com --text ou --text-file",
            fg="red",
            err=True,
        )
        raise SystemExit(_EXIT_USAGE)

    # Destino: exatamente um (fixo OU coluna)
    if (chat_id is None) == (chat_id_column is None):
        click.secho(
            "Erro: informe exatamente um destino: --chat-id OU --chat-id-column",
            fg="red",
            err=True,
        )
        raise SystemExit(_EXIT_USAGE)

    # Aviso: http (sem TLS) em host externo expoe o token em transito
    host = urlparse(base_url).hostname or ""
    if base_url.startswith("http://") and host not in _LOCAL_HOSTS:
        click.secho(
            "Aviso: --base-url sem https em host externo expoe o token em transito. Prefira https.",
            fg="yellow",
            err=True,
        )

    token, token_origem = _resolver_token()
    dry_run = bool(ctx.dry_run)

    # Header (nunca mostra o token, so a origem)
    click.echo(_SEP)
    click.secho(" Envio via Telegram", bold=True)
    click.echo(_SEP)
    click.echo(f"Planilha: {planilha}")
    click.echo(f"API:      {base_url}")
    destino = f"chat fixo {chat_id}" if chat_id else f"coluna '{chat_id_column}'"
    click.echo(f"Destino:  {destino}")
    click.echo(f"Token:    via {token_origem}")
    modo = "dry-run (nao envia)" if dry_run else "normal"
    click.echo(f"Modo:     {modo}")
    click.echo("")

    def _on_progress(info: dict[str, object]) -> None:
        marca = click.style("OK", fg="green") if info["sucesso"] else click.style("FALHA", fg="red")
        click.echo(
            f"  [{info['linha']}/{info['total']}] [{marca}] {info['mensagem']}",
        )

    # Cria a task (ValidationError -> exit 2)
    try:
        task = SendTelegramTask(
            planilha_path=planilha,
            token=token,
            text_template=template,
            chat_id=chat_id,
            chat_id_column=chat_id_column,
            base_url=base_url,
            parse_mode=parse_mode,
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
            f"[dry-run] Enviaria {result.data.get('would_send')} mensagens",
            fg="cyan",
        )
        exemplo = result.data.get("exemplo_texto")
        if exemplo:
            click.echo("Exemplo da 1a mensagem (apenas visual; nao enviada nem salva):")
            click.echo(f"  {exemplo}")
        click.echo(_SEP)
        return

    total = result.data.get("total", 0)
    enviados = result.data.get("enviados", 0)
    falhas = result.data.get("falhas", 0)

    click.echo(f"Total:    {total}")
    click.secho(f"Enviados: {enviados}", fg="green")
    if falhas:
        click.secho(f"Falhas:   {falhas}", fg="red")
    else:
        click.echo(f"Falhas:   {falhas}")
    if result.data.get("report_path"):
        click.echo(f"Relatorio: {result.data['report_path']}")
    click.echo(_SEP)

    if result.status == TaskStatus.PARTIAL:
        click.secho(
            "Algumas mensagens falharam. Veja o relatorio para os detalhes.",
            fg="yellow",
        )
    elif result.status == TaskStatus.FAILURE:
        click.secho("Nenhuma mensagem foi enviada.", fg="red", err=True)
        raise SystemExit(_EXIT_FAILURE)


__all__ = ["telegram_command"]
