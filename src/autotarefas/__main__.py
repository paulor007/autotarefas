"""
Permite executar a CLI como módulo Python:

    python -m autotarefas --help
    python -m autotarefas info
    python -m autotarefas --dry-run --verbose info

Equivale ao comando ``autotarefas`` instalado via ``pip install -e .``.
"""

from autotarefas.cli.main import cli

if __name__ == "__main__":
    cli()
