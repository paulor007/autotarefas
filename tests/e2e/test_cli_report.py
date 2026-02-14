"""
Testes End-to-End dos comandos de relatório do AutoTarefas.

Este arquivo testa os comandos da CLI relacionados a geração de relatórios,
verificando que funcionam corretamente do ponto de vista do usuário.

=============================================================================
O QUE O test_cli_report.py TESTA
=============================================================================

Este arquivo testa os **comandos de relatório** da CLI:

1. **report sales** - Gera relatório de vendas
   - Opções: -f/--format, -o/--output, -c/--csv, -p/--period
   - Opções manuais: --total, --transactions
   - Formatos: txt, html, json, csv, md

2. **report formats** - Lista formatos disponíveis
   - Exibe tabela com formatos suportados
   - Mostra descrição e uso de cada formato

3. **report templates** - Lista templates disponíveis
   - Exibe templates de relatório existentes
   - Mostra o que cada template inclui

4. **report example-csv** - Gera CSV de exemplo
   - Opções: -o/--output
   - Cria arquivo CSV com dados de exemplo

=============================================================================
FORMATOS DE RELATÓRIO
=============================================================================

| Formato | Descrição                | Uso                      |
|---------|--------------------------|--------------------------|
| txt     | Texto simples            | Leitura rápida           |
| html    | HTML estilizado          | Abre no navegador        |
| json    | JSON estruturado         | Integração com APIs      |
| csv     | CSV tabular              | Excel/planilhas          |
| md      | Markdown                 | Documentação/GitHub      |

=============================================================================
FONTES DE DADOS
=============================================================================

O relatório de vendas pode usar:
1. Arquivo CSV (--csv vendas.csv)
2. Dados manuais (--total 150000 --transactions 1250)
3. Dados de exemplo (sem parâmetros)

=============================================================================
POR QUE ESTES TESTES SÃO IMPORTANTES
=============================================================================

Comandos de relatório são importantes porque:
- Geram documentos que podem ser compartilhados
- Múltiplos formatos precisam funcionar corretamente
- Arquivos de saída devem ser criados nos lugares certos
- Interface deve ser clara para configurar relatórios
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from click.testing import Result


# ============================================================================
# Testes de Help
# ============================================================================


class TestReportHelp:
    """Testes de help dos comandos de relatório."""

    def test_report_help(self, cli_invoke: Callable[..., Result]) -> None:
        """report --help deve mostrar subcomandos."""
        result = cli_invoke("report", "--help")

        assert result.exit_code == 0
        assert "sales" in result.output
        assert "formats" in result.output
        assert "templates" in result.output

    def test_report_sales_help(self, cli_invoke: Callable[..., Result]) -> None:
        """report sales --help deve mostrar opções."""
        result = cli_invoke("report", "sales", "--help")

        assert result.exit_code == 0
        assert "--format" in result.output or "-f" in result.output
        assert "--output" in result.output or "-o" in result.output
        assert "--csv" in result.output or "-c" in result.output

    def test_report_formats_help(self, cli_invoke: Callable[..., Result]) -> None:
        """report formats --help deve funcionar."""
        result = cli_invoke("report", "formats", "--help")

        assert result.exit_code == 0

    def test_report_templates_help(self, cli_invoke: Callable[..., Result]) -> None:
        """report templates --help deve funcionar."""
        result = cli_invoke("report", "templates", "--help")

        assert result.exit_code == 0

    def test_report_example_csv_help(self, cli_invoke: Callable[..., Result]) -> None:
        """report example-csv --help deve mostrar opções."""
        result = cli_invoke("report", "example-csv", "--help")

        assert result.exit_code == 0
        assert "--output" in result.output or "-o" in result.output


# ============================================================================
# Testes de report sales
# ============================================================================


class TestReportSales:
    """Testes do comando report sales."""

    def test_report_sales_dry_run(self, cli_invoke: Callable[..., Result]) -> None:
        """report sales em dry-run deve simular."""
        result = cli_invoke("--dry-run", "report", "sales")

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()

    def test_report_sales_with_format(self, cli_invoke: Callable[..., Result]) -> None:
        """report sales deve aceitar --format."""
        result = cli_invoke(
            "--dry-run",
            "report",
            "sales",
            "--format",
            "html",
        )

        assert result.exit_code == 0
        assert "html" in result.output.lower()

    def test_report_sales_with_period(self, cli_invoke: Callable[..., Result]) -> None:
        """report sales deve aceitar --period."""
        result = cli_invoke(
            "--dry-run",
            "report",
            "sales",
            "--period",
            "Janeiro 2024",
        )

        assert result.exit_code == 0
        assert "janeiro" in result.output.lower() or "2024" in result.output

    def test_report_sales_with_total(self, cli_invoke: Callable[..., Result]) -> None:
        """report sales deve aceitar --total."""
        result = cli_invoke(
            "--dry-run",
            "report",
            "sales",
            "--total",
            "150000",
        )

        assert result.exit_code == 0

    def test_report_sales_with_transactions(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """report sales deve aceitar --transactions."""
        result = cli_invoke(
            "--dry-run",
            "report",
            "sales",
            "--transactions",
            "1250",
        )

        assert result.exit_code == 0

    def test_report_sales_with_output(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """report sales deve aceitar --output."""
        output = e2e_env["reports"] / "relatorio.html"

        result = cli_invoke(
            "--dry-run",
            "report",
            "sales",
            "--output",
            str(output),
        )

        assert result.exit_code == 0


# ============================================================================
# Testes de Formatos de Relatório
# ============================================================================


class TestReportFormats:
    """Testes dos formatos de relatório."""

    def test_report_formats_lists_all(self, cli_invoke: Callable[..., Result]) -> None:
        """report formats deve listar todos os formatos."""
        result = cli_invoke("report", "formats")

        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "txt" in output_lower
        assert "html" in output_lower
        assert "json" in output_lower
        assert "csv" in output_lower
        assert "md" in output_lower

    @pytest.mark.parametrize("fmt", ["txt", "html", "json", "csv", "md"])
    def test_all_formats_accepted(
        self,
        cli_invoke: Callable[..., Result],
        fmt: str,
    ) -> None:
        """Todos os formatos devem ser aceitos."""
        result = cli_invoke(
            "--dry-run",
            "report",
            "sales",
            "--format",
            fmt,
        )

        assert result.exit_code == 0

    def test_invalid_format_rejected(self, cli_invoke: Callable[..., Result]) -> None:
        """Formato inválido deve ser rejeitado."""
        result = cli_invoke(
            "report",
            "sales",
            "--format",
            "invalid_format",
        )

        assert result.exit_code != 0


# ============================================================================
# Testes de report templates
# ============================================================================


class TestReportTemplates:
    """Testes do comando report templates."""

    def test_report_templates_lists(self, cli_invoke: Callable[..., Result]) -> None:
        """report templates deve listar templates."""
        result = cli_invoke("report", "templates")

        assert result.exit_code == 0
        # Deve listar pelo menos o template de vendas
        output_lower = result.output.lower()
        assert "sales" in output_lower or "venda" in output_lower

    def test_report_templates_shows_table(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """report templates deve mostrar tabela formatada."""
        result = cli_invoke("report", "templates")

        assert result.exit_code == 0
        # Deve ter alguma estrutura
        assert len(result.output) > 50


# ============================================================================
# Testes de report example-csv
# ============================================================================


class TestReportExampleCsv:
    """Testes do comando report example-csv."""

    def test_report_example_csv_dry_run(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """report example-csv em dry-run deve simular."""
        result = cli_invoke("--dry-run", "report", "example-csv")

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()

    def test_report_example_csv_with_output(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """report example-csv deve aceitar --output."""
        output = e2e_env["temp"] / "exemplo.csv"

        result = cli_invoke(
            "--dry-run",
            "report",
            "example-csv",
            "--output",
            str(output),
        )

        assert result.exit_code == 0


# ============================================================================
# Testes de Fluxo Completo
# ============================================================================


class TestReportWorkflow:
    """Testes de fluxo completo de relatório."""

    def test_full_workflow_dry_run(
        self,
        cli_invoke: Callable[..., Result],
    ) -> None:
        """Fluxo completo em dry-run deve funcionar."""
        # 1. Listar formatos
        result1 = cli_invoke("report", "formats")
        assert result1.exit_code == 0

        # 2. Listar templates
        result2 = cli_invoke("report", "templates")
        assert result2.exit_code == 0

        # 3. Gerar relatório (dry-run)
        result3 = cli_invoke(
            "--dry-run",
            "report",
            "sales",
            "--format",
            "html",
            "--period",
            "2024",
        )
        assert result3.exit_code == 0


# ============================================================================
# Testes de Mensagens
# ============================================================================


class TestReportMessages:
    """Testes de mensagens da CLI."""

    def test_report_sales_shows_source(self, cli_invoke: Callable[..., Result]) -> None:
        """report sales deve mostrar fonte dos dados."""
        result = cli_invoke("--dry-run", "report", "sales")

        assert result.exit_code == 0
        # Deve indicar a fonte (exemplo, CSV, manual)
        output_lower = result.output.lower()
        assert (
            "fonte" in output_lower
            or "source" in output_lower
            or "exemplo" in output_lower
        )

    def test_report_sales_shows_format(self, cli_invoke: Callable[..., Result]) -> None:
        """report sales deve mostrar formato."""
        result = cli_invoke(
            "--dry-run",
            "report",
            "sales",
            "--format",
            "json",
        )

        assert result.exit_code == 0
        assert "json" in result.output.lower()

    def test_report_sales_shows_output_path(
        self,
        cli_invoke: Callable[..., Result],
    ) -> None:
        """report sales deve mostrar caminho de saída."""
        result = cli_invoke("--dry-run", "report", "sales")

        assert result.exit_code == 0
        # Deve mostrar caminho de saída
        output_lower = result.output.lower()
        assert "saída" in output_lower or "output" in output_lower


# ============================================================================
# Testes de Edge Cases
# ============================================================================


class TestReportEdgeCases:
    """Testes de casos extremos."""

    def test_report_with_verbose(self, cli_invoke: Callable[..., Result]) -> None:
        """Comandos devem funcionar com --verbose global."""
        result = cli_invoke("--verbose", "report", "formats")

        assert result.exit_code == 0

    def test_report_with_quiet(self, cli_invoke: Callable[..., Result]) -> None:
        """Comandos devem funcionar com --quiet global."""
        result = cli_invoke("--quiet", "report", "formats")

        assert result.exit_code == 0

    def test_invalid_subcommand(self, cli_invoke: Callable[..., Result]) -> None:
        """Subcomando inválido deve dar erro."""
        result = cli_invoke("report", "invalid_command")

        assert result.exit_code != 0

    def test_report_sales_manual_data(self, cli_invoke: Callable[..., Result]) -> None:
        """report sales com dados manuais deve funcionar."""
        result = cli_invoke(
            "--dry-run",
            "report",
            "sales",
            "--total",
            "250000.50",
            "--transactions",
            "2500",
            "--period",
            "Q1 2024",
        )

        assert result.exit_code == 0

    def test_report_sales_format_case_insensitive(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """Formato deve ser case-insensitive."""
        result = cli_invoke(
            "--dry-run",
            "report",
            "sales",
            "--format",
            "HTML",
        )

        assert result.exit_code == 0
