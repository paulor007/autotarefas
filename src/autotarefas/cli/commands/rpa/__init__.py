"""
Grupo de comandos ``rpa`` — automacao web.

Subcomandos:
- ``cadastro``: cadastra registros web a partir de planilha

Futuros:
- ``consulta``: extrai dados de sistema web
- ``exportar``: exporta dados de sistema web
"""

from __future__ import annotations

import click

from autotarefas.cli.commands.rpa.cadastro import cadastro


@click.group(name="rpa")
def rpa() -> None:
    """Comandos de RPA (automacao web)."""


rpa.add_command(cadastro)


__all__ = ["rpa"]
