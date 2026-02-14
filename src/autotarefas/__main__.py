#!/usr/bin/env python3
"""
Entry point principal do AutoTarefas.

Permite executar o pacote como módulo:
    python -m autotarefas
"""

import logging
import sys

__all__ = ["main"]
__version__ = "0.1.0"

# Configuração inicial de logging
logger = logging.getLogger("autotarefas")
logger.addHandler(logging.NullHandler())


def main(args: list[str] | None = None) -> int:
    """
    Função principal do AutoTarefas.

    Args:
        args: Lista de argumentos da linha de comando.
              Se None, usa sys.argv.

    Returns:
        int: Código de saída (0 para sucesso, >0 para erro).
    """
    try:
        # Importará a CLI quando estiver pronta
        from autotarefas.cli import cli

        # Se args foi fornecido, usá-lo; senão usar sys.argv
        if args is not None:
            # Simular sys.argv para a CLI
            sys.argv = ["autotarefas"] + args

        # Executar CLI e retornar código de saída
        return cli()

    except ImportError:
        logger.warning("CLI ainda não disponível. Rodando modo informativo.")
        print("AutoTarefas v0.1.0 - Em desenvolvimento")
        print("Use: python -m autotarefas --help (disponível em breve)")
        return 0

    except KeyboardInterrupt:
        # Ctrl+C foi pressionado
        print("\n\nOperação cancelada pelo usuário.")
        return 130  # Código padrão para SIGINT

    except Exception as e:
        # Erro não tratado
        print(f"\nErro inesperado: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    # Quando executado diretamente
    sys.exit(main())
