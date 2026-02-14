#!/usr/bin/env python3
"""
Script para verificar cobertura de testes do AutoTarefas.

O QUE ESTE SCRIPT FAZ:
======================
1. Roda todos os testes com medição de cobertura
2. Mostra um relatório colorido no terminal
3. Indica arquivos abaixo da meta (80%)
4. Retorna código de erro se cobertura for insuficiente

QUANDO USAR:
============
- Antes de fazer commit (verificar se testes cobrem o código)
- No CI/CD (falhar build se cobertura cair)
- Para identificar arquivos que precisam de mais testes

COMO USAR:
==========
    python scripts/check_coverage.py          # Roda tudo
    python scripts/check_coverage.py --html   # Gera relatório HTML
    python scripts/check_coverage.py --quick  # Só testes unitários
    python scripts/check_coverage.py --fail-under 90  # Meta customizada

SAÍDA:
======
    ✅ arquivo.py: 95.2%
    ⚠️  outro.py: 78.5% (abaixo de 80%)
    ❌ ruim.py: 45.0% (crítico)

    TOTAL: 82.3% ✅
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


# Cores ANSI para terminal
class Colors:
    """Códigos de cores ANSI para output colorido."""

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_header(text: str) -> None:
    """Imprime cabeçalho formatado."""
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print()


def print_success(text: str) -> None:
    """Imprime mensagem de sucesso."""
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")


def print_warning(text: str) -> None:
    """Imprime mensagem de aviso."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")


def print_error(text: str) -> None:
    """Imprime mensagem de erro."""
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")


def print_info(text: str) -> None:
    """Imprime mensagem informativa."""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")


def run_coverage(
    html: bool = False,
    xml: bool = False,
    quick: bool = False,
    fail_under: int = 80,
    verbose: bool = False,
) -> tuple[bool, float]:
    """
    Executa testes com cobertura.

    Args:
        html: Se True, gera relatório HTML em htmlcov/
        xml: Se True, gera relatório XML (para CI)
        quick: Se True, roda apenas testes unitários (mais rápido)
        fail_under: Porcentagem mínima exigida
        verbose: Se True, mostra output detalhado

    Returns:
        Tupla (sucesso, porcentagem_total)
    """
    # Montar comando pytest
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "--cov=src/autotarefas",
        f"--cov-fail-under={fail_under}",
        "--cov-report=term-missing",
    ]

    # Adicionar relatórios extras
    if html:
        cmd.append("--cov-report=html:htmlcov")

    if xml:
        cmd.append("--cov-report=xml:coverage.xml")

    # Selecionar testes
    if quick:
        # Apenas testes unitários (exclui integration e e2e)
        cmd.extend(
            [
                "tests/",
                "--ignore=tests/integration/",
                "--ignore=tests/e2e/",
                "-q",  # Quiet mode
            ]
        )
    else:
        cmd.append("tests/")

    # Verbose mode
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Executar
    print_info(f"Executando: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, capture_output=False)

    # Verificar resultado
    success = result.returncode == 0

    # Tentar extrair porcentagem do output (simplificado)
    # Na prática, pytest-cov já mostra isso
    coverage_percent = 0.0

    return success, coverage_percent


def check_coverage_files() -> None:
    """Verifica se arquivos de cobertura existem."""
    coverage_file = Path(".coverage")

    if coverage_file.exists():
        print_info(f"Arquivo de cobertura encontrado: {coverage_file}")
    else:
        print_warning("Arquivo .coverage não encontrado (será criado ao rodar testes)")


def main() -> int:
    """
    Função principal.

    Returns:
        0 se cobertura OK, 1 se abaixo da meta
    """
    parser = argparse.ArgumentParser(
        description="Verifica cobertura de testes do AutoTarefas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python scripts/check_coverage.py              # Verificação padrão
  python scripts/check_coverage.py --html       # Gera relatório HTML
  python scripts/check_coverage.py --quick      # Apenas testes unitários
  python scripts/check_coverage.py --fail-under 90  # Meta de 90%
        """,
    )

    parser.add_argument(
        "--html",
        action="store_true",
        help="Gera relatório HTML em htmlcov/",
    )

    parser.add_argument(
        "--xml",
        action="store_true",
        help="Gera relatório XML para CI/CD",
    )

    parser.add_argument(
        "--quick",
        "-q",
        action="store_true",
        help="Roda apenas testes unitários (mais rápido)",
    )

    parser.add_argument(
        "--fail-under",
        type=int,
        default=80,
        metavar="N",
        help="Porcentagem mínima de cobertura (default: 80)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Output detalhado",
    )

    args = parser.parse_args()

    # Header
    print_header("VERIFICAÇÃO DE COBERTURA - AutoTarefas")

    # Info
    print_info(f"Meta de cobertura: {args.fail_under}%")
    print_info(
        f"Modo: {'Rápido (unitários)' if args.quick else 'Completo (todos os testes)'}"
    )

    if args.html:
        print_info("Relatório HTML será gerado em: htmlcov/index.html")

    if args.xml:
        print_info("Relatório XML será gerado em: coverage.xml")

    print()

    # Verificar arquivos existentes
    check_coverage_files()
    print()

    # Rodar cobertura
    print_header("EXECUTANDO TESTES")

    success, _ = run_coverage(
        html=args.html,
        xml=args.xml,
        quick=args.quick,
        fail_under=args.fail_under,
        verbose=args.verbose,
    )

    # Resultado final
    print()
    print_header("RESULTADO")

    if success:
        print_success(f"Cobertura atende a meta de {args.fail_under}%!")

        if args.html:
            print()
            print_info("Para ver o relatório HTML:")
            print("    abrir htmlcov/index.html")

        return 0
    else:
        print_error(f"Cobertura abaixo da meta de {args.fail_under}%!")
        print()
        print_warning("Dicas para melhorar a cobertura:")
        print("  1. Veja quais arquivos estão abaixo da meta no relatório acima")
        print("  2. Adicione testes para as linhas não cobertas")
        print("  3. Use 'pytest --cov-report=html' para ver detalhes visuais")

        return 1


if __name__ == "__main__":
    sys.exit(main())
