"""Testes para autotarefas.cli.main e autotarefas.cli.commands.info."""

from __future__ import annotations

from click.testing import CliRunner

from autotarefas import __version__
from autotarefas.cli.main import cli


class TestCliVersion:
    """Testes da opção --version."""

    def test_version_exit_code_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0

    def test_version_mostra_numero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert __version__ in result.output


class TestCliHelp:
    """Testes da opção --help."""

    def test_help_exit_code_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_help_mostra_descricao(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "automacao" in result.output.lower()

    def test_help_lista_opcoes_globais(self) -> None:
        """--help mostra --verbose, --dry-run, --yes."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "--verbose" in result.output
        assert "--dry-run" in result.output
        assert "--yes" in result.output

    def test_help_atalho_h(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-h"])
        assert result.exit_code == 0


class TestCliInfoComando:
    """Testes do subcomando 'info'."""

    def test_info_basico(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["info"])
        assert result.exit_code == 0
        assert "AutoTarefas" in result.output
        assert __version__ in result.output

    def test_info_mostra_environment(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["info"])
        assert "Environment" in result.output

    def test_info_dry_run_default_false(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["info"])
        assert "False" in result.output  # Dry-run: False

    def test_info_com_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--dry-run", "info"])
        assert result.exit_code == 0
        assert "True" in result.output  # Dry-run: True

    def test_info_com_yes(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--yes", "info"])
        assert result.exit_code == 0
        assert "True" in result.output

    def test_info_com_verbose_2(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-vv", "info"])
        assert result.exit_code == 0
        assert "DEBUG" in result.output

    def test_info_com_quiet(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-q", "info"])
        assert result.exit_code == 0
        assert "WARNING" in result.output


class TestCliSemSubcomando:
    """Testes do comportamento sem subcomando."""

    def test_sem_args_mostra_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [])
        # Click mostra help (exit 0 ou 2 dependendo da versão)
        assert result.exit_code in (0, 2)
        assert "Usage" in result.output or "automacao" in result.output.lower()
