"""
Subcomando `send email`: envio de emails em massa a partir de uma planilha.

Destino deste arquivo:
    src/autotarefas/cli/commands/send/email.py

SEGURANCA: a senha SMTP NUNCA e um argumento de linha de comando. Ela
vem da variavel de ambiente AUTOTAREFAS_SMTP_PASSWORD ou de um prompt
oculto (getpass). Assim nao vaza no historico do shell nem em logs.

(O nome do modulo eh '...send.email'; os imports sao absolutos, entao
nao ha conflito com o modulo 'email' da stdlib.)
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path
from typing import TYPE_CHECKING

import click

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.send_email import SendEmailTask, SmtpConfig

if TYPE_CHECKING:
    from autotarefas.cli.context import CLIContext

# Exit codes
_EXIT_USAGE = 2
_EXIT_FAILURE = 1

# Nome da variavel de ambiente que guarda a senha (NAO e a senha)
_ENV_SENHA = "AUTOTAREFAS_SMTP_PASSWORD"

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_SEP = "=" * 60


def _resolver_senha(usuario: str | None) -> str | None:
    """
    Resolve a senha SMTP de forma segura.

    - Sem usuario -> sem login (None).
    - Com usuario -> tenta a env var; se ausente, pede no prompt oculto.
    """
    if usuario is None:
        return None
    senha = os.environ.get(_ENV_SENHA)
    if senha:
        return senha
    return getpass.getpass(f"Senha SMTP para {usuario}: ")


@click.command(name="email")
@click.option(
    "--planilha",
    "-p",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Planilha CSV/XLSX com os destinatarios.",
)
@click.option("--smtp-host", required=True, help="Servidor SMTP.")
@click.option(
    "--smtp-port",
    default=587,
    type=int,
    show_default=True,
    help="Porta do servidor SMTP.",
)
@click.option(
    "--from",
    "remetente",
    required=True,
    help="Endereco do remetente (campo From).",
)
@click.option(
    "--subject",
    required=True,
    help="Assunto do email (aceita {coluna}).",
)
@click.option(
    "--body",
    default=None,
    help="Corpo do email (aceita {coluna}).",
)
@click.option(
    "--body-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Arquivo com o corpo (precede --body).",
)
@click.option(
    "--email-column",
    default="email",
    show_default=True,
    help="Nome da coluna com o email do destinatario.",
)
@click.option(
    "--user",
    default=None,
    help=(
        "Usuario SMTP (login). A senha vem da env var " "AUTOTAREFAS_SMTP_PASSWORD ou de um prompt."
    ),
)
@click.option("--html", is_flag=True, default=False, help="Envia o corpo como HTML.")
@click.option(
    "--no-tls",
    is_flag=True,
    default=False,
    help="Desativa STARTTLS (ex: servidor de debug local).",
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
    help="Timeout da conexao SMTP em segundos.",
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
def email_command(  # noqa: PLR0912, PLR0915
    ctx: CLIContext,
    planilha: Path,
    smtp_host: str,
    smtp_port: int,
    remetente: str,
    subject: str,
    body: str | None,
    body_file: Path | None,
    email_column: str,
    user: str | None,
    html: bool,
    no_tls: bool,
    delay: float,
    timeout: float,
    report: Path | None,
) -> None:
    """
    Envia um email para cada linha de uma planilha (via SMTP).

    O assunto e o corpo aceitam {coluna}: trechos como {nome} sao
    trocados pelos valores da linha. Tolerante a falhas: um email ruim
    nao interrompe os demais.

    \b
    A senha SMTP nunca e passada na linha de comando. Defina:
      $env:AUTOTAREFAS_SMTP_PASSWORD = "..."   (PowerShell)
    ou informe --user e ela sera solicitada num prompt oculto.

    \b
    Exemplos:
      autotarefas send email -p lista.csv --smtp-host localhost --smtp-port 8025 --no-tls \\
        --from robo@local --subject "Ola {nome}" --body "Oi {nome}!"
      autotarefas send email -p lista.csv --smtp-host smtp.gmail.com \\
        --from voce@empresa.com --subject "Aviso" --body-file corpo.txt --user voce@empresa.com
    """
    # Resolver corpo (body-file precede body)
    if body_file is not None:
        corpo = body_file.read_text(encoding="utf-8")
    elif body is not None:
        corpo = body
    else:
        click.secho(
            "Erro: informe o corpo com --body ou --body-file",
            fg="red",
            err=True,
        )
        raise SystemExit(_EXIT_USAGE)

    usar_tls = not no_tls

    # Aviso: login sem TLS em host externo expoe a senha
    if user is not None and not usar_tls and smtp_host not in _LOCAL_HOSTS:
        click.secho(
            "Aviso: login sem TLS (--no-tls) em host externo expoe a senha "
            "em transito. Prefira TLS.",
            fg="yellow",
            err=True,
        )

    senha = _resolver_senha(user)
    dry_run = bool(ctx.dry_run)

    smtp = SmtpConfig(
        host=smtp_host,
        port=smtp_port,
        usuario=user,
        senha=senha,
        usar_tls=usar_tls,
    )

    # Header
    click.echo(_SEP)
    click.secho(" Envio de emails", bold=True)
    click.echo(_SEP)
    click.echo(f"Planilha: {planilha}")
    tls_txt = "on" if usar_tls else "off"
    click.echo(f"SMTP:     {smtp_host}:{smtp_port} (TLS {tls_txt})")
    click.echo(f"De:       {remetente}")
    click.echo(f"Assunto:  {subject}")
    modo = "dry-run (nao envia)" if dry_run else "normal"
    click.echo(f"Modo:     {modo}")
    click.echo("")

    def _on_progress(info: dict[str, object]) -> None:
        marca = click.style("OK", fg="green") if info["sucesso"] else click.style("FALHA", fg="red")
        dest = info["para"] or "(sem email)"
        click.echo(
            f"  [{info['linha']}/{info['total']}] [{marca}] " f"{dest} - {info['mensagem']}",
        )

    # Cria a task (ValidationError -> exit 2)
    try:
        task = SendEmailTask(
            planilha_path=planilha,
            smtp=smtp,
            remetente=remetente,
            assunto=subject,
            corpo=corpo,
            coluna_email=email_column,
            is_html=html,
            delay_s=delay,
            timeout_s=timeout,
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
            f"[dry-run] Enviaria {result.data.get('would_send')} emails",
            fg="cyan",
        )
        preview = result.data.get("preview", [])
        if isinstance(preview, list):
            for p in preview:
                click.echo(f"  -> {p['para']}: {p['assunto']}")
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
            "Alguns emails falharam. Veja o relatorio para os detalhes.",
            fg="yellow",
        )
    elif result.status == TaskStatus.FAILURE:
        click.secho("Nenhum email foi enviado.", fg="red", err=True)
        raise SystemExit(_EXIT_FAILURE)


__all__ = ["email_command"]
