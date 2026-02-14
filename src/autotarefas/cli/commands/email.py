"""
Comandos CLI para Email e Notificações.

Fornece comandos para gerenciar emails e notificações:
    - email status: Exibe status da configuração
    - email test: Testa conexão SMTP (opcionalmente envia teste)
    - email send: Envia email (texto/HTML/anexos)
    - email notify: Envia notificação via Notifier (multi-canal)
    - email history: Exibe ou limpa histórico de notificações
    - email channels: Lista e gerencia canais de notificação

Uso:
    $ autotarefas email status
    $ autotarefas email test
    $ autotarefas email test --send --to usuario@exemplo.com
    $ autotarefas email send usuario@exemplo.com -s "Assunto" -m "Mensagem"
    $ autotarefas email notify "Backup concluído!" --level success
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from autotarefas.config import settings
from autotarefas.core.logger import logger

console = Console()

LEVEL_CHOICES = ("debug", "info", "success", "warning", "error", "critical")
CHANNEL_CHOICES = ("console", "email", "file", "webhook")
PRIORITY_CHOICES = ("low", "normal", "high", "urgent")


def _get_console(ctx: click.Context) -> Console:
    """
    Retorna o Console preferencial.

    Se o comando foi chamado pelo entrypoint principal, ele injeta
    um Console em ctx.obj["console"]. Caso contrário, usa o Console local.
    """
    obj = getattr(ctx, "obj", None)
    if isinstance(obj, dict) and isinstance(obj.get("console"), Console):
        return obj["console"]
    return console


def _is_dry_run(ctx: click.Context) -> bool:
    """
    Indica se a execução está em modo dry-run (simulação).

    Returns:
        True quando `--dry-run` foi usado no comando raiz.
    """
    obj = getattr(ctx, "obj", None)
    if isinstance(obj, dict):
        return bool(obj.get("dry_run", False))
    return False


def _status_icon(enabled: bool) -> str:
    """Ícone simples de status."""
    return "✅" if enabled else "❌"


def _level_style(level: str) -> str:
    """Estilo Rich para cada nível de notificação."""
    styles = {
        "debug": "dim",
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "critical": "bold red",
    }
    return styles.get(level.lower(), "white")


def _print_header(c: Console, title: str, *, style: str = "cyan") -> None:
    """Imprime um cabeçalho padrão com Panel."""
    c.print()
    c.print(Panel.fit(f"[bold {style}]{title}[/bold {style}]", border_style=style))
    c.print()


def _parse_json_object(value: str) -> dict[str, Any]:
    """
    Faz parse de JSON e garante que é um objeto (dict).

    Args:
        value: string JSON.

    Returns:
        dict com os dados parseados.

    Raises:
        click.BadParameter: quando não for JSON válido ou não for objeto.
    """
    try:
        data = json.loads(value)
    except json.JSONDecodeError as e:
        raise click.BadParameter(f"JSON inválido: {e}") from e

    if not isinstance(data, dict):
        raise click.BadParameter(
            "O JSON precisa ser um objeto (ex: {'chave': 'valor'})."
        )

    return data


@click.group(help="📧 Gerenciamento de emails e notificações.")
@click.pass_context
def email(ctx: click.Context) -> None:
    """Grupo de comandos `email`."""
    ctx.ensure_object(dict)


@email.command("status")
@click.pass_context
def email_status(ctx: click.Context) -> None:
    """📊 Exibe status da configuração de email e notificações."""
    c = _get_console(ctx)

    try:
        from autotarefas.core.email import get_email_sender
        from autotarefas.core.notifier import get_notifier
    except Exception as e:  # noqa: BLE001
        logger.exception("Falha ao importar módulos de email/notifier")
        raise click.ClickException(f"Falha ao carregar módulos: {e}") from e

    _print_header(c, "📧 Status do Sistema de Email", style="cyan")

    sender = get_email_sender()
    smtp_status = sender.get_status()

    table = Table(
        title="⚙️ Configuração SMTP",
        show_header=True,
        header_style="bold blue",
        border_style="blue",
    )
    table.add_column("Configuração", style="cyan")
    table.add_column("Valor", style="white")
    table.add_column("Status", justify="center")

    table.add_row(
        "Host",
        smtp_status.get("host") or "[dim]Não configurado[/dim]",
        _status_icon(bool(smtp_status.get("host"))),
    )
    table.add_row(
        "Porta",
        str(smtp_status.get("port")),
        _status_icon(smtp_status.get("port") in [25, 465, 587, 2525]),
    )
    table.add_row(
        "Remetente",
        smtp_status.get("from_addr") or "[dim]Não configurado[/dim]",
        _status_icon(bool(smtp_status.get("from_addr"))),
    )
    table.add_row(
        "Nome",
        smtp_status.get("from_name") or "[dim]Não configurado[/dim]",
        "✅" if smtp_status.get("from_name") else "➖",
    )
    table.add_row(
        "TLS",
        "Habilitado" if smtp_status.get("use_tls") else "Desabilitado",
        _status_icon(bool(smtp_status.get("use_tls"))),
    )
    table.add_row(
        "SSL",
        "Habilitado" if smtp_status.get("use_ssl") else "Desabilitado",
        "✅" if smtp_status.get("use_ssl") else "➖",
    )
    table.add_row(
        "Autenticação",
        "Configurada" if smtp_status.get("has_auth") else "Não configurada",
        _status_icon(bool(smtp_status.get("has_auth"))),
    )

    table.add_row("", "", "")
    configured = bool(smtp_status.get("configured"))
    table.add_row(
        "[bold]Status Geral[/bold]",
        "[green]Configurado[/green]" if configured else "[red]Não configurado[/red]",
        _status_icon(configured),
    )

    c.print(table)
    c.print()

    notifier = get_notifier()
    notifier_status = notifier.get_status()

    table2 = Table(
        title="🔔 Sistema de Notificações",
        show_header=True,
        header_style="bold magenta",
        border_style="magenta",
    )
    table2.add_column("Item", style="cyan")
    table2.add_column("Valor", style="white")

    channels = notifier_status.get("channels", [])
    active = [ch.get("channel", "") for ch in channels if ch.get("enabled")]
    table2.add_row(
        "Canais Ativos", ", ".join(active) if active else "[dim]Nenhum[/dim]"
    )
    table2.add_row(
        "Histórico", f"{notifier_status.get('history_size', 0)} notificações"
    )
    table2.add_row(
        "Arquivo Log", notifier_status.get("file_path") or "[dim]Não configurado[/dim]"
    )
    table2.add_row(
        "Webhook",
        (
            "Configurado"
            if notifier_status.get("webhook_configured")
            else "[dim]Não configurado[/dim]"
        ),
    )

    recipients = notifier_status.get("email_recipients") or []
    table2.add_row(
        "Destinatários", ", ".join(recipients) if recipients else "[dim]Nenhum[/dim]"
    )

    c.print(table2)
    c.print()

    if not configured:
        c.print(
            Panel(
                "[yellow]💡 Configure as variáveis EMAIL_* no arquivo .env[/yellow]",
                title="Configuração",
                border_style="yellow",
            )
        )

    logger.info("Status de email exibido")


@email.command("test")
@click.option(
    "--send", "-s", is_flag=True, help="Envia email de teste após validar conexão"
)
@click.option(
    "--to",
    "-t",
    default=None,
    help="Destinatário do teste (se não informado, usa settings.email.to_addr ou from_addr)",
)
@click.pass_context
def email_test(ctx: click.Context, send: bool, to: str | None) -> None:
    """🧪 Testa conexão com servidor SMTP (opcionalmente envia um email de teste)."""
    c = _get_console(ctx)
    dry_run = _is_dry_run(ctx)

    try:
        from autotarefas.core.email import get_email_sender
    except Exception as e:  # noqa: BLE001
        logger.exception("Falha ao importar EmailSender")
        raise click.ClickException(f"Falha ao carregar EmailSender: {e}") from e

    _print_header(c, "🧪 Teste de Conexão SMTP", style="cyan")

    sender = get_email_sender()

    if dry_run:
        c.print("[yellow]DRY-RUN:[/] conexão SMTP seria testada.")
        if not sender.is_configured:
            c.print(
                "[yellow]DRY-RUN:[/] EmailSender não configurado (seria necessário configurar EMAIL_*)."
            )
        if send:
            recipient = to or "teste@exemplo.com"
            c.print(f"[yellow]DRY-RUN:[/] enviaria email de teste para {recipient}.")
        c.print()
        return

    if not sender.is_configured:
        raise click.ClickException(
            "EmailSender não configurado. Configure EMAIL_* no .env."
        )

    c.print("[cyan]🔄 Testando conexão...[/cyan]")
    with c.status("[cyan]Conectando...[/cyan]"):
        success, message = sender.test_connection()

    if not success:
        raise click.ClickException(message)

    c.print(f"[green]✅ {message}[/green]")

    if send:
        recipient = to or settings.email.to_addr or settings.email.from_addr
        if not recipient:
            raise click.ClickException("Nenhum destinatário definido. Use --to.")

        c.print(f"[cyan]📧 Enviando teste para {recipient}...[/cyan]")
        result = sender.send_simple(
            to=recipient,
            subject="🧪 Teste do AutoTarefas",
            body=f"Teste do AutoTarefas - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        )

        if not result.success:
            raise click.ClickException(
                f"Falha ao enviar email de teste: {result.error}"
            )

        c.print("[green]✅ Email de teste enviado![/green]")

    c.print()


@email.command("send")
@click.argument("to", nargs=-1, required=True)
@click.option("--subject", "-s", required=True, help="Assunto")
@click.option("--message", "-m", default=None, help="Corpo do email (texto)")
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True, dir_okay=False),
    help="Arquivo de texto com o corpo do email",
)
@click.option(
    "--html",
    type=click.Path(exists=True, dir_okay=False),
    help="Arquivo HTML (corpo em HTML)",
)
@click.option(
    "--attach",
    "-a",
    multiple=True,
    type=click.Path(exists=True),
    help="Anexos (pode repetir)",
)
@click.option("--cc", multiple=True, help="Cópias (CC)")
@click.option("--bcc", multiple=True, help="Cópias ocultas (BCC)")
@click.option(
    "--priority",
    "-p",
    default="normal",
    type=click.Choice(PRIORITY_CHOICES, case_sensitive=False),
)
@click.pass_context
def email_send(
    ctx: click.Context,
    to: tuple[str, ...],
    subject: str,
    message: str | None,
    file: str | None,
    html: str | None,
    attach: tuple[str, ...],
    cc: tuple[str, ...],
    bcc: tuple[str, ...],
    priority: str,
) -> None:
    """📤 Envia um email."""
    c = _get_console(ctx)
    dry_run = _is_dry_run(ctx)

    try:
        from autotarefas.core.email import (
            EmailAttachment,
            EmailMessage,
            EmailPriority,
            get_email_sender,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Falha ao importar módulos de email")
        raise click.ClickException(f"Falha ao carregar módulos de email: {e}") from e

    body = message
    html_content: str | None = None

    if file:
        body = Path(file).read_text(encoding="utf-8")
    if html:
        html_content = Path(html).read_text(encoding="utf-8")

    if not body and not html_content:
        raise click.UsageError("Informe --message/-m ou --file/-f ou --html.")

    # Se só houver HTML, ainda mantemos um body de fallback.
    if not body:
        body = "Este email contém conteúdo em HTML."

    priority_map = {
        "low": EmailPriority.LOW,
        "normal": EmailPriority.NORMAL,
        "high": EmailPriority.HIGH,
        "urgent": EmailPriority.URGENT,
    }

    attachments = [EmailAttachment.from_file(a) for a in attach] if attach else []

    email_msg = EmailMessage(
        to=list(to),
        subject=subject,
        body=body,
        html=html_content,
        cc=list(cc),
        bcc=list(bcc),
        attachments=attachments,
        priority=priority_map[priority.lower()],
    )

    _print_header(c, "📤 Enviando Email", style="cyan")
    c.print(f"  Para: {', '.join(to)}")
    c.print(f"  Assunto: {subject}")
    if cc:
        c.print(f"  CC: {', '.join(cc)}")
    if bcc:
        c.print("  BCC: (oculto)")
    if attach:
        c.print(f"  Anexos: {len(attach)} arquivo(s)")
    c.print()

    if dry_run:
        c.print("[yellow]DRY-RUN:[/] email não será enviado.")
        c.print()
        return

    sender = get_email_sender()
    with c.status("[cyan]Enviando...[/cyan]"):
        result = sender.send(email_msg)

    if not result.success:
        raise click.ClickException(f"Falha ao enviar email: {result.error}")

    c.print("[green]✅ Email enviado![/green]")
    c.print(f"[dim]ID: {result.message_id} | Tempo: {result.duration:.2f}s[/dim]")
    c.print()


@email.command("notify")
@click.argument("message")
@click.option("--title", "-t", default=None, help="Título")
@click.option(
    "--level",
    "-l",
    default="info",
    type=click.Choice(LEVEL_CHOICES, case_sensitive=False),
)
@click.option("--source", "-s", default="cli", help="Origem")
@click.option(
    "--channel",
    "-c",
    multiple=True,
    type=click.Choice(CHANNEL_CHOICES, case_sensitive=False),
    help="Canais alvo (pode repetir)",
)
@click.option("--tag", multiple=True, help="Tags (pode repetir)")
@click.option("--data", "-d", default=None, help="Dados em JSON (objeto)")
@click.pass_context
def email_notify(
    ctx: click.Context,
    message: str,
    title: str | None,
    level: str,
    source: str,
    channel: tuple[str, ...],
    tag: tuple[str, ...],
    data: str | None,
) -> None:
    """🔔 Envia uma notificação (multi-canal) via Notifier."""
    c = _get_console(ctx)
    dry_run = _is_dry_run(ctx)

    try:
        from autotarefas.core.notifier import (
            NotificationChannel,
            NotificationLevel,
            get_notifier,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Falha ao importar Notifier")
        raise click.ClickException(f"Falha ao carregar Notifier: {e}") from e

    level_map: dict[str, NotificationLevel] = {
        "debug": NotificationLevel.DEBUG,
        "info": NotificationLevel.INFO,
        "success": NotificationLevel.SUCCESS,
        "warning": NotificationLevel.WARNING,
        "error": NotificationLevel.ERROR,
        "critical": NotificationLevel.CRITICAL,
    }
    channel_map: dict[str, NotificationChannel] = {
        "console": NotificationChannel.CONSOLE,
        "email": NotificationChannel.EMAIL,
        "file": NotificationChannel.FILE,
        "webhook": NotificationChannel.WEBHOOK,
    }

    notif_data: dict[str, Any] = {}
    if data:
        notif_data = _parse_json_object(data)

    target_channels = [channel_map[ch.lower()] for ch in channel] if channel else None

    _print_header(c, "🔔 Enviar Notificação", style="magenta")

    if dry_run:
        c.print("[yellow]DRY-RUN:[/] notificação não será enviada.")
        c.print(f"  Nível: {level.lower()}")
        c.print(f"  Origem: {source}")
        c.print(
            f"  Canais: {', '.join([ch.lower() for ch in channel]) if channel else '(default)'}"
        )
        if title:
            c.print(f"  Título: {title}")
        if tag:
            c.print(f"  Tags: {', '.join(tag)}")
        if notif_data:
            c.print("  Data: (JSON)")
        c.print()
        return

    notifier = get_notifier()
    results = notifier.notify(
        message=message,
        title=title,
        level=level_map[level.lower()],
        source=source,
        data=notif_data,
        tags=list(tag),
        channels=target_channels,
    )

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    c.print()
    if success_count > 0:
        c.print(f"[green]✅ Notificação enviada para {success_count} canal(is)[/green]")
    if fail_count > 0:
        c.print(f"[yellow]⚠️ Falha em {fail_count} canal(is)[/yellow]")
    if not results:
        c.print("[yellow]⚠️ Nenhum canal configurado[/yellow]")
    c.print()


@email.command("history")
@click.option(
    "--limit", "-n", default=20, show_default=True, help="Máximo de registros"
)
@click.option(
    "--level",
    "-l",
    default=None,
    type=click.Choice(LEVEL_CHOICES, case_sensitive=False),
    help="Filtrar por nível",
)
@click.option("--clear", is_flag=True, help="Limpa histórico")
@click.pass_context
def email_history(
    ctx: click.Context, limit: int, level: str | None, clear: bool
) -> None:
    """📜 Exibe histórico de notificações (ou limpa)."""
    c = _get_console(ctx)
    dry_run = _is_dry_run(ctx)

    try:
        from autotarefas.core.notifier import get_notifier
    except Exception as e:  # noqa: BLE001
        logger.exception("Falha ao importar Notifier")
        raise click.ClickException(f"Falha ao carregar Notifier: {e}") from e

    notifier = get_notifier()
    c.print()

    if clear:
        if dry_run:
            c.print("[yellow]DRY-RUN:[/] histórico seria limpo.")
            c.print()
            return
        count = notifier.clear_history()
        c.print(f"[green]✅ Histórico limpo ({count} registros)[/green]")
        c.print()
        return

    history = notifier.get_history(limit=limit)
    if not history:
        c.print("[yellow]📭 Nenhuma notificação no histórico[/yellow]")
        c.print()
        return

    if level:
        history = [
            h
            for h in history
            if str(h["notification"]["level"]).lower() == level.lower()
        ]
        if not history:
            c.print(f"[yellow]📭 Nenhuma com nível '{level.lower()}'[/yellow]")
            c.print()
            return

    c.print(
        Panel.fit(
            f"[bold cyan]📜 Histórico ({len(history)} registros)[/bold cyan]",
            border_style="cyan",
        )
    )
    c.print()

    table = Table(show_header=True, header_style="bold blue", border_style="blue")
    table.add_column("Data/Hora", style="dim", width=16)
    table.add_column("Nível", width=10, justify="center")
    table.add_column("Origem", width=10)
    table.add_column("Mensagem")
    table.add_column("Canais", width=14)

    for item in reversed(history):
        notif = item["notification"]
        results = item["results"]

        ts = datetime.fromisoformat(notif["timestamp"]).strftime("%d/%m %H:%M:%S")
        lvl = str(notif["level"])
        level_text = Text(lvl.upper(), style=_level_style(lvl))

        ok = [r["channel"] for r in results if r["success"]]
        fail = [r["channel"] for r in results if not r["success"]]
        ch_str = f"[green]{','.join(ok)}[/green]" if ok else ""
        if fail:
            ch_str = (ch_str + " " if ch_str else "") + f"[red]{','.join(fail)}[/red]"

        msg = str(notif["message"])
        msg = (msg[:35] + "...") if len(msg) > 35 else msg

        table.add_row(ts, level_text, str(notif["source"]), msg, ch_str or "-")

    c.print(table)
    c.print()


@email.command("channels")
@click.option(
    "--add",
    "-a",
    default=None,
    type=click.Choice(CHANNEL_CHOICES, case_sensitive=False),
    help="Adiciona canal",
)
@click.option(
    "--remove",
    "-r",
    default=None,
    type=click.Choice(CHANNEL_CHOICES, case_sensitive=False),
    help="Remove canal",
)
@click.option(
    "--enable",
    default=None,
    type=click.Choice(CHANNEL_CHOICES, case_sensitive=False),
    help="Habilita canal",
)
@click.option(
    "--disable",
    default=None,
    type=click.Choice(CHANNEL_CHOICES, case_sensitive=False),
    help="Desabilita canal",
)
@click.option(
    "--set-level", default=None, help="Define nível mínimo (formato: canal:nivel)"
)
@click.option(
    "--set-file", type=click.Path(), default=None, help="Arquivo para canal FILE"
)
@click.option("--set-webhook", default=None, help="URL do webhook")
@click.option("--set-recipients", multiple=True, help="Destinatários (email)")
@click.pass_context
def email_channels(
    ctx: click.Context,
    add: str | None,
    remove: str | None,
    enable: str | None,
    disable: str | None,
    set_level: str | None,
    set_file: str | None,
    set_webhook: str | None,
    set_recipients: tuple[str, ...],
) -> None:
    """📡 Lista e gerencia canais de notificação."""
    c = _get_console(ctx)
    dry_run = _is_dry_run(ctx)

    try:
        from autotarefas.core.notifier import (
            NotificationChannel,
            NotificationLevel,
            get_notifier,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Falha ao importar Notifier")
        raise click.ClickException(f"Falha ao carregar Notifier: {e}") from e

    notifier = get_notifier()
    c.print()

    channel_map: dict[str, NotificationChannel] = {
        "console": NotificationChannel.CONSOLE,
        "email": NotificationChannel.EMAIL,
        "file": NotificationChannel.FILE,
        "webhook": NotificationChannel.WEBHOOK,
    }
    level_map: dict[str, NotificationLevel] = {
        "debug": NotificationLevel.DEBUG,
        "info": NotificationLevel.INFO,
        "success": NotificationLevel.SUCCESS,
        "warning": NotificationLevel.WARNING,
        "error": NotificationLevel.ERROR,
        "critical": NotificationLevel.CRITICAL,
    }

    action_taken = False

    def _apply_or_print(action_desc: str, fn) -> None:
        nonlocal action_taken
        if dry_run:
            c.print(f"[yellow]DRY-RUN:[/] {action_desc}")
        else:
            fn()
        action_taken = True

    if add:
        add_key = add.lower()
        _apply_or_print(
            f"adicionaria canal '{add_key}'",
            lambda: notifier.add_channel(channel_map[add_key]),
        )
        if not dry_run:
            c.print(f"[green]✅ Canal '{add_key}' adicionado[/green]")

    if remove:
        remove_key = remove.lower()
        _apply_or_print(
            f"removeria canal '{remove_key}'",
            lambda: notifier.remove_channel(channel_map[remove_key]),
        )
        if not dry_run:
            c.print(f"[green]✅ Canal '{remove_key}' removido[/green]")

    if enable:
        enable_key = enable.lower()
        _apply_or_print(
            f"habilitaria canal '{enable_key}'",
            lambda: notifier.enable_channel(channel_map[enable_key]),
        )
        if not dry_run:
            c.print(f"[green]✅ Canal '{enable_key}' habilitado[/green]")

    if disable:
        disable_key = disable.lower()
        _apply_or_print(
            f"desabilitaria canal '{disable_key}'",
            lambda: notifier.disable_channel(channel_map[disable_key]),
        )
        if not dry_run:
            c.print(f"[green]✅ Canal '{disable_key}' desabilitado[/green]")

    if set_level:
        try:
            channel_name, level_name = (x.strip() for x in set_level.split(":", 1))
        except ValueError as e:
            raise click.UsageError("Formato inválido. Use: canal:nivel") from e

        channel_name = channel_name.lower()
        level_name = level_name.lower()

        if channel_name not in channel_map or level_name not in level_map:
            raise click.UsageError(
                "Valores inválidos. Use: canal:nivel (ex: email:warning)"
            )

        _apply_or_print(
            f"definiria nível mínimo de '{channel_name}' para '{level_name}'",
            lambda: notifier.set_min_level(
                channel_map[channel_name], level_map[level_name]
            ),
        )
        if not dry_run:
            c.print(
                f"[green]✅ Nível mínimo de '{channel_name}' = '{level_name}'[/green]"
            )

    if set_file:
        path = Path(set_file)
        _apply_or_print(
            f"definiria arquivo do canal FILE = {path}",
            lambda: notifier.set_file_path(path),
        )
        if not dry_run:
            c.print(f"[green]✅ Arquivo: {path}[/green]")

    if set_webhook:
        _apply_or_print(
            "definiria URL do webhook", lambda: notifier.set_webhook_url(set_webhook)
        )
        if not dry_run:
            c.print("[green]✅ Webhook definido[/green]")

    if set_recipients:
        recipients = list(set_recipients)
        _apply_or_print(
            f"definiria destinatários: {', '.join(recipients)}",
            lambda: notifier.set_email_recipients(recipients),
        )
        if not dry_run:
            c.print(f"[green]✅ Destinatários: {', '.join(recipients)}[/green]")

    if action_taken:
        c.print()

    # Lista canais (estado atual)
    c.print(
        Panel.fit(
            "[bold cyan]📡 Canais de Notificação[/bold cyan]", border_style="cyan"
        )
    )
    c.print()

    channels = notifier.list_channels()
    if not channels:
        c.print("[yellow]📭 Nenhum canal configurado[/yellow]")
        c.print("[dim]Use --add para adicionar[/dim]")
        c.print()
        return

    table = Table(show_header=True, header_style="bold blue", border_style="blue")
    table.add_column("Canal", style="cyan", width=12)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Nível Mínimo", width=12)

    for channel_cfg in channels:
        status = (
            "[green]Ativo[/green]" if channel_cfg["enabled"] else "[red]Inativo[/red]"
        )
        min_level = str(channel_cfg["min_level"])
        lvl_text = Text(min_level.upper(), style=_level_style(min_level))
        table.add_row(str(channel_cfg["channel"]).upper(), status, lvl_text)

    c.print(table)
    c.print()


__all__ = ["email"]
