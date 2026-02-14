"""
Interface de Linha de Comando (CLI) do AutoTarefas.

Fornece comandos para executar todas as funcionalidades:
    - autotarefas init: Inicializa configuração
    - autotarefas backup: Gerencia backups
    - autotarefas clean: Limpeza de arquivos
    - autotarefas monitor: Monitoramento do sistema
    - autotarefas report: Geração de relatórios

Uso:
    $ autotarefas --help
    $ autotarefas backup run /home/user/docs
    $ autotarefas monitor status
"""

from autotarefas.cli.main import cli, main

__all__ = [
    "cli",
    "main",
]
