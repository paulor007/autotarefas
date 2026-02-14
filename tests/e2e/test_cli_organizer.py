"""
Testes end-to-end da CLI do organizador de arquivos.

O QUE ESTES TESTES VERIFICAM:
=============================
- Comandos CLI funcionam corretamente
- Output é formatado corretamente
- Opções são processadas
- Erros são tratados adequadamente

COMO RODAR:
===========
    pytest tests/e2e/test_cli_organizer.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def runner() -> CliRunner:
    """Cria CliRunner para testes."""
    return CliRunner()


@pytest.fixture
def sample_dir(tmp_path: Path) -> Path:
    """Cria diretório com arquivos de exemplo."""
    (tmp_path / "foto.jpg").write_bytes(b"jpg content")
    (tmp_path / "documento.pdf").write_bytes(b"pdf content")
    (tmp_path / "video.mp4").write_bytes(b"mp4 content")
    return tmp_path


# ============================================================================
# Testes do Comando organize run
# ============================================================================


class TestOrganizeRunCommand:
    """Testes do comando organize run."""

    def test_run_basic(self, runner: CliRunner, sample_dir: Path) -> None:
        """Deve organizar arquivos."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "run", str(sample_dir)])

        assert result.exit_code == 0
        assert (
            "organizados" in result.output.lower()
            or "arquivos" in result.output.lower()
        )

    def test_run_dry_run(self, runner: CliRunner, sample_dir: Path) -> None:
        """Deve simular organização em dry-run."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["--dry-run", "organize", "run", str(sample_dir)])

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()

        # Arquivos não foram movidos
        assert (sample_dir / "foto.jpg").exists()

    def test_run_with_profile(self, runner: CliRunner, sample_dir: Path) -> None:
        """Deve aceitar opção --profile."""
        from autotarefas.cli.main import cli

        result = runner.invoke(
            cli,
            [
                "organize",
                "run",
                str(sample_dir),
                "--profile",
                "by_extension",
            ],
        )

        assert result.exit_code == 0

    def test_run_with_conflict(self, runner: CliRunner, sample_dir: Path) -> None:
        """Deve aceitar opção --conflict."""
        from autotarefas.cli.main import cli

        result = runner.invoke(
            cli,
            [
                "organize",
                "run",
                str(sample_dir),
                "--conflict",
                "skip",
            ],
        )

        assert result.exit_code == 0

    def test_run_recursive(self, runner: CliRunner, tmp_path: Path) -> None:
        """Deve aceitar opção --recursive."""
        from autotarefas.cli.main import cli

        # Criar estrutura aninhada
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "foto1.jpg").write_bytes(b"jpg1")
        (subdir / "foto2.jpg").write_bytes(b"jpg2")

        result = runner.invoke(
            cli,
            [
                "organize",
                "run",
                str(tmp_path),
                "--recursive",
            ],
        )

        assert result.exit_code == 0

    def test_run_nonexistent_path(self, runner: CliRunner) -> None:
        """Deve falhar com path inexistente."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "run", "/nonexistent/path/xyz"])

        assert result.exit_code != 0

    def test_run_help(self, runner: CliRunner) -> None:
        """Deve mostrar ajuda."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "run", "-h"])

        assert result.exit_code == 0
        assert "source" in result.output.lower()
        assert "profile" in result.output.lower()


# ============================================================================
# Testes do Comando organize preview
# ============================================================================


class TestOrganizePreviewCommand:
    """Testes do comando organize preview."""

    def test_preview_basic(self, runner: CliRunner, sample_dir: Path) -> None:
        """Deve mostrar preview."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "preview", str(sample_dir)])

        assert result.exit_code == 0
        assert "preview" in result.output.lower() or "arquivos" in result.output.lower()

        # Arquivos não foram movidos
        assert (sample_dir / "foto.jpg").exists()
        assert (sample_dir / "documento.pdf").exists()

    def test_preview_with_profile(self, runner: CliRunner, sample_dir: Path) -> None:
        """Deve aceitar opção --profile."""
        from autotarefas.cli.main import cli

        result = runner.invoke(
            cli,
            [
                "organize",
                "preview",
                str(sample_dir),
                "--profile",
                "by_date",
            ],
        )

        assert result.exit_code == 0

    def test_preview_empty_dir(self, runner: CliRunner, tmp_path: Path) -> None:
        """Deve tratar diretório vazio."""
        from autotarefas.cli.main import cli

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = runner.invoke(cli, ["organize", "preview", str(empty_dir)])

        assert result.exit_code == 0
        assert "nenhum" in result.output.lower()

    def test_preview_help(self, runner: CliRunner) -> None:
        """Deve mostrar ajuda."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "preview", "-h"])

        assert result.exit_code == 0


# ============================================================================
# Testes do Comando organize rules
# ============================================================================


class TestOrganizeRulesCommand:
    """Testes do comando organize rules."""

    def test_rules_basic(self, runner: CliRunner) -> None:
        """Deve listar regras."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "rules"])

        assert result.exit_code == 0
        assert "imagens" in result.output.lower()
        assert "documentos" in result.output.lower()
        assert ".jpg" in result.output.lower()
        assert ".pdf" in result.output.lower()

    def test_rules_filter_category(self, runner: CliRunner) -> None:
        """Deve filtrar por categoria."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "rules", "--category", "Imagens"])

        assert result.exit_code == 0
        assert ".jpg" in result.output.lower()
        # Não deve mostrar outras categorias
        assert "documentos" not in result.output.lower()

    def test_rules_invalid_category(self, runner: CliRunner) -> None:
        """Deve tratar categoria inválida."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "rules", "--category", "Inexistente"])

        assert result.exit_code == 0
        assert "não encontrada" in result.output.lower()

    def test_rules_help(self, runner: CliRunner) -> None:
        """Deve mostrar ajuda."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "rules", "-h"])

        assert result.exit_code == 0


# ============================================================================
# Testes do Comando organize stats
# ============================================================================


class TestOrganizeStatsCommand:
    """Testes do comando organize stats."""

    def test_stats_basic(self, runner: CliRunner, sample_dir: Path) -> None:
        """Deve mostrar estatísticas."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "stats", str(sample_dir)])

        assert result.exit_code == 0
        assert "arquivos" in result.output.lower()
        assert "total" in result.output.lower()

    def test_stats_empty_dir(self, runner: CliRunner, tmp_path: Path) -> None:
        """Deve tratar diretório vazio."""
        from autotarefas.cli.main import cli

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = runner.invoke(cli, ["organize", "stats", str(empty_dir)])

        assert result.exit_code == 0
        assert "nenhum" in result.output.lower()

    def test_stats_help(self, runner: CliRunner) -> None:
        """Deve mostrar ajuda."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "stats", "-h"])

        assert result.exit_code == 0


# ============================================================================
# Testes do Grupo organize
# ============================================================================


class TestOrganizeGroup:
    """Testes do grupo de comandos organize."""

    def test_organize_help(self, runner: CliRunner) -> None:
        """Deve mostrar ajuda do grupo."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "--help"])

        assert result.exit_code == 0
        assert "run" in result.output
        assert "preview" in result.output
        assert "rules" in result.output
        assert "stats" in result.output

    def test_organize_no_subcommand(self, runner: CliRunner) -> None:
        """Sem subcomando deve mostrar ajuda."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize"])

        # Pode mostrar ajuda ou erro
        assert "run" in result.output or "preview" in result.output


# ============================================================================
# Testes de Output Formatado
# ============================================================================


class TestOrganizeOutput:
    """Testes de formatação do output."""

    def test_output_has_table(self, runner: CliRunner, sample_dir: Path) -> None:
        """Output deve ter tabela formatada."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "run", str(sample_dir)])

        # Verifica elementos típicos de tabela Rich
        assert result.exit_code == 0
        # Pode ter caracteres de tabela ou separadores
        assert (
            "│" in result.output
            or "|" in result.output
            or "categoria" in result.output.lower()
        )

    def test_output_has_summary(self, runner: CliRunner, sample_dir: Path) -> None:
        """Output deve ter resumo."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "run", str(sample_dir)])

        assert result.exit_code == 0
        assert "✅" in result.output or "organizados" in result.output.lower()


# ============================================================================
# Testes de Integração CLI + Task
# ============================================================================


class TestCliTaskIntegration:
    """Testes de integração entre CLI e Task."""

    def test_cli_creates_correct_folders(
        self, runner: CliRunner, sample_dir: Path
    ) -> None:
        """CLI deve criar pastas corretas."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["organize", "run", str(sample_dir)])

        assert result.exit_code == 0

        # Verificar estrutura criada
        assert (sample_dir / "Imagens").is_dir()
        assert (sample_dir / "Documentos").is_dir()
        assert (sample_dir / "Videos").is_dir()

        # Verificar arquivos movidos
        assert (sample_dir / "Imagens" / "foto.jpg").exists()
        assert (sample_dir / "Documentos" / "documento.pdf").exists()
        assert (sample_dir / "Videos" / "video.mp4").exists()

    def test_cli_verbose_mode(self, runner: CliRunner, sample_dir: Path) -> None:
        """Modo verbose deve mostrar mais informações."""
        from autotarefas.cli.main import cli

        result = runner.invoke(cli, ["--verbose", "organize", "run", str(sample_dir)])

        assert result.exit_code == 0
        # Verbose pode ter mais output
        assert len(result.output) > 0
