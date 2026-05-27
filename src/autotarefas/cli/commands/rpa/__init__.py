"""
Grupo de comandos ``rpa`` — automacao web.

Subcomandos:
- ``cadastro``: cadastra registros web a partir de planilha

Futuros (a serem adicionados):
- ``consulta``: extrai dados de sistema web
- ``exportar``: exporta dados de sistema web

Uso:
    autotarefas rpa cadastro --planilha X --site Y
"""

from __future__ import annotations

import click

from autotarefas.cli.commands.rpa.cadastro import cadastro


@click.group(name="rpa")
def rpa() -> None:
    """Comandos de RPA (automacao web)."""


# Registro dos subcomandos
rpa.add_command(cadastro)


__all__ = ["rpa"]
