"""Testes para autotarefas.cli.commands.init."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from autotarefas.cli.main import cli


class TestInitBasico:
    """Testes do funcionamento básico do init."""

    def test_init_cria_diretorios(self, tmp_path: Path) -> None:
        """init cria logs/, screenshots/, reports/."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--data-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert (tmp_path / "logs").exists()
        assert (tmp_path / "screenshots").exists()
        assert (tmp_path / "reports").exists()

    def test_init_cria_env(self, tmp_path: Path) -> None:
        """init cria .env com template."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--data-dir", str(tmp_path)])

        assert result.exit_code == 0
        env_path = tmp_path / ".env"
        assert env_path.exists()

        content = env_path.read_text(encoding="utf-8")
        assert "ENVIRONMENT=dev" in content
        assert "LOG_LEVEL=INFO" in content

    def test_init_mostra_resumo(self, tmp_path: Path) -> None:
        """init mostra resumo do que foi feito."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--data-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "concluida" in result.output.lower()
        assert "criados" in result.output.lower()


class TestInitIdempotente:
    """Testes de idempotência (rodar várias vezes)."""

    def test_segunda_execucao_nao_quebra(self, tmp_path: Path) -> None:
        """Rodar init 2x não deve quebrar."""
        runner = CliRunner()

        # Primeira execução
        result1 = runner.invoke(cli, ["init", "--data-dir", str(tmp_path)])
        assert result1.exit_code == 0

        # Segunda execução
        result2 = runner.invoke(cli, ["init", "--data-dir", str(tmp_path)])
        assert result2.exit_code == 0

    def test_segunda_execucao_mostra_skip(self, tmp_path: Path) -> None:
        """Segunda execução marca arquivos como SKIP."""
        runner = CliRunner()

        runner.invoke(cli, ["init", "--data-dir", str(tmp_path)])
        result = runner.invoke(cli, ["init", "--data-dir", str(tmp_path)])

        assert "SKIP" in result.output

    def test_segunda_execucao_preserva_env(self, tmp_path: Path) -> None:
        """Segunda execução NÃO sobrescreve .env."""
        runner = CliRunner()

        # Primeira execução cria
        runner.invoke(cli, ["init", "--data-dir", str(tmp_path)])

        # Modifica o .env
        env_path = tmp_path / ".env"
        env_path.write_text("CUSTOM=value", encoding="utf-8")

        # Segunda execução: NÃO deve sobrescrever
        result = runner.invoke(cli, ["init", "--data-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert env_path.read_text(encoding="utf-8") == "CUSTOM=value"


class TestInitForce:
    """Testes do flag --force."""

    def test_force_sobrescreve_env(self, tmp_path: Path) -> None:
        """--force sobrescreve .env existente."""
        runner = CliRunner()

        # Cria com conteúdo custom
        runner.invoke(cli, ["init", "--data-dir", str(tmp_path)])
        env_path = tmp_path / ".env"
        env_path.write_text("CUSTOM=value", encoding="utf-8")

        # Com --force, sobrescreve
        result = runner.invoke(cli, ["init", "--data-dir", str(tmp_path), "--force"])

        assert result.exit_code == 0
        content = env_path.read_text(encoding="utf-8")
        assert "CUSTOM=value" not in content
        assert "ENVIRONMENT=dev" in content


class TestInitDryRun:
    """Testes do --dry-run."""

    def test_dry_run_nao_cria_pastas(self, tmp_path: Path) -> None:
        """--dry-run não cria nada de verdade."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--dry-run", "init", "--data-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert not (tmp_path / "logs").exists()
        assert not (tmp_path / "screenshots").exists()
        assert not (tmp_path / "reports").exists()
        assert not (tmp_path / ".env").exists()

    def test_dry_run_mostra_oque_faria(self, tmp_path: Path) -> None:
        """--dry-run mostra mensagens DRY-RUN."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--dry-run", "init", "--data-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "DRY-RUN" in result.output


class TestInitDataDir:
    """Testes do --data-dir."""

    def test_data_dir_customizado(self, tmp_path: Path) -> None:
        """--data-dir aceita path custom."""
        custom_dir = tmp_path / "meu-dir"
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--data-dir", str(custom_dir)])

        assert result.exit_code == 0
        assert (custom_dir / "logs").exists()

    def test_data_dir_cria_pasta_pai(self, tmp_path: Path) -> None:
        """--data-dir cria a pasta base se não existir."""
        nested = tmp_path / "a" / "b" / "c"
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--data-dir", str(nested)])

        assert result.exit_code == 0
        assert (nested / "logs").exists()


class TestInitVerbose:
    """Testes com flags de verbosidade."""

    def test_quiet_suprime_info(self, tmp_path: Path) -> None:
        """-q suprime mensagens INFO mas mantém execução."""
        runner = CliRunner()
        result = runner.invoke(cli, ["-q", "init", "--data-dir", str(tmp_path)])

        assert result.exit_code == 0
        # Diretórios foram criados mesmo em modo quiet
        assert (tmp_path / "logs").exists()


class TestInitHelp:
    """Testes do --help."""

    def test_init_help_mostra_opcoes(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--help"])

        assert result.exit_code == 0
        assert "--data-dir" in result.output
        assert "--force" in result.output

    def test_init_aparece_no_help_principal(self) -> None:
        """Comando init aparece no help raiz."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "init" in result.output
