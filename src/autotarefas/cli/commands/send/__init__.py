"""
Grupo de comandos `send` — envio de dados para sistemas externos.

Por ora expoe apenas o subcomando `api` (envio em massa via API REST).
Simetrico ao grupo `extract`: enquanto `extract` LE dados de fora,
`send` ESCREVE dados em sistemas externos.

Destino deste arquivo:
    src/autotarefas/cli/commands/send/__init__.py
"""

from __future__ import annotations

import click

from autotarefas.cli.commands.send.api import api_command


@click.group(name="send")
def send() -> None:
    """Envia dados para sistemas externos (API, ...)."""


send.add_command(api_command)


__all__ = ["send"]
