"""
Grupo de comandos `extract` — extracao de dados de fontes externas.

Por ora expoe apenas o subcomando `api` (extracao via API REST
paginada). A estrutura ja fica pronta para um futuro `extract web`
(web scraping), que reaproveitara o BrowserSession da Fase 8.

"""

from __future__ import annotations

import click

from autotarefas.cli.commands.extract.api import api_command


@click.group(name="extract")
def extract() -> None:
    """Extrai dados de fontes externas (API, ...)."""


extract.add_command(api_command)


__all__ = ["extract"]
