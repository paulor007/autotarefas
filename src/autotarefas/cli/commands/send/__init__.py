"""
Grupo de comandos `send` — envio de dados para sistemas externos.

Subcomandos:
    send api       -> envio em massa via API REST
    send email     -> envio de emails em massa (SMTP)
    send telegram  -> envio de mensagens via Telegram (Bot API)

Destino deste arquivo (substitui o atual):
    src/autotarefas/cli/commands/send/__init__.py
"""

from __future__ import annotations

import click

from autotarefas.cli.commands.send.api import api_command
from autotarefas.cli.commands.send.email import email_command
from autotarefas.cli.commands.send.telegram import telegram_command


@click.group(name="send")
def send() -> None:
    """Envia dados para sistemas externos (API, email, Telegram, ...)."""


send.add_command(api_command)
send.add_command(email_command)
send.add_command(telegram_command)


__all__ = ["send"]
