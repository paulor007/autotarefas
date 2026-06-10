"""
Grupo de comandos `extract` — extracao de dados de fontes externas.

Subcomandos:
    extract api  -> extracao via API REST paginada (JSON)
    extract web  -> extracao via web scraping (HTML, por seletores CSS)

Destino deste arquivo (substitui o atual):
    src/autotarefas/cli/commands/extract/__init__.py
"""

from __future__ import annotations

import click

from autotarefas.cli.commands.extract.api import api_command
from autotarefas.cli.commands.extract.web import web_command


@click.group(name="extract")
def extract() -> None:
    """Extrai dados de fontes externas (API, web)."""


extract.add_command(api_command)
extract.add_command(web_command)


__all__ = ["extract"]
