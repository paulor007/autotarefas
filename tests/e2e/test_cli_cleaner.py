"""
Testes End-to-End dos comandos de limpeza do AutoTarefas.

Este arquivo testa os comandos da CLI relacionados a limpeza de arquivos,
verificando que funcionam corretamente do ponto de vista do usuário.

=============================================================================
O QUE O test_cli_cleaner.py TESTA
=============================================================================

Este arquivo testa os **comandos de limpeza** da CLI:

1. **clean run** - Executa limpeza de arquivos
   - Argumentos: PATHS (um ou mais diretórios, obrigatório)
   - Opções: -p/--profile, -d/--days, -e/--extension, --no-recursive
   - Remove arquivos que correspondem ao perfil selecionado

2. **clean preview** - Visualiza o que seria limpo
   - Argumentos: PATHS (obrigatório)
   - Opções: -p/--profile
   - Mostra arquivos sem remover (dry-run implícito)

3. **clean profiles** - Lista perfis disponíveis
   - Sem argumentos
   - Exibe tabela com perfis e descrições

=============================================================================
PERFIS DE LIMPEZA DISPONÍVEIS
=============================================================================

| Perfil       | Descrição                           |
|--------------|-------------------------------------|
| temp_files   | Arquivos temporários (.tmp, .bak)   |
| log_files    | Arquivos de log antigos (.log)      |
| cache_files  | Arquivos de cache (.cache, .pyc)    |
| downloads    | Downloads antigos (>90 dias)        |
| thumbnails   | Miniaturas e lixo do sistema        |

=============================================================================
POR QUE ESTES TESTES SÃO IMPORTANTES
=============================================================================

Os comandos de limpeza são sensíveis porque:
- Removem arquivos permanentemente
- Erros podem causar perda de dados importantes
- O preview é essencial para segurança
- Perfis devem ser bem documentados

=============================================================================
CENÁRIOS TESTADOS
=============================================================================

- Limpeza com diferentes perfis
- Preview antes da limpeza
- Modo dry-run (simulação)
- Filtros por extensão e idade
- Tratamento de diretórios inexistentes
- Opções recursiva/não-recursiva
- Listagem de perfis disponíveis
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


class TestCleanHelp:
    """Testes de help dos comandos de limpeza."""

    def test_clean_help(self, cli_invoke: Callable[..., Result]) -> None:
        """clean --help deve mostrar subcomandos."""
        result = cli_invoke("clean", "--help")

        assert result.exit_code == 0
        assert "run" in result.output
        assert "preview" in result.output
        assert "profiles" in result.output

    def test_clean_run_help(self, cli_invoke: Callable[..., Result]) -> None:
        """clean run --help deve mostrar opções."""
        result = cli_invoke("clean", "run", "--help")

        assert result.exit_code == 0
        assert "--profile" in result.output or "-p" in result.output
        assert "--days" in result.output or "-d" in result.output
        assert "--extension" in result.output or "-e" in result.output

    def test_clean_preview_help(self, cli_invoke: Callable[..., Result]) -> None:
        """clean preview --help deve mostrar opções."""
        result = cli_invoke("clean", "preview", "--help")

        assert result.exit_code == 0
        assert "--profile" in result.output or "-p" in result.output

    def test_clean_profiles_help(self, cli_invoke: Callable[..., Result]) -> None:
        """clean profiles --help deve funcionar."""
        result = cli_invoke("clean", "profiles", "--help")

        assert result.exit_code == 0


# ============================================================================
# Testes de clean run
# ============================================================================


class TestCleanRun:
    """Testes do comando clean run."""

    def test_clean_run_requires_paths(self, cli_invoke: Callable[..., Result]) -> None:
        """clean run deve exigir PATHS."""
        result = cli_invoke("clean", "run")

        assert result.exit_code != 0
        # Deve indicar que falta argumento
        assert (
            "paths" in result.output.lower()
            or "missing" in result.output.lower()
            or "argument" in result.output.lower()
        )

    def test_clean_run_invalid_path(self, cli_invoke: Callable[..., Result]) -> None:
        """clean run deve falhar com path inexistente."""
        result = cli_invoke("clean", "run", "/caminho/que/nao/existe")

        assert result.exit_code != 0

    def test_clean_run_dry_run(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """clean run --dry-run deve simular sem remover."""
        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(sample_temp_files),
        )

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower() or "preview" in result.output.lower()

    def test_clean_run_with_profile(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """clean run deve aceitar opção --profile."""
        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(sample_temp_files),
            "-p",
            "temp_files",
        )

        assert result.exit_code == 0
        assert "temp_files" in result.output.lower()

    def test_clean_run_with_days(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """clean run deve aceitar opção --days."""
        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(sample_temp_files),
            "-d",
            "30",
        )

        assert result.exit_code == 0

    def test_clean_run_with_extension(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """clean run deve aceitar opção --extension."""
        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(sample_temp_files),
            "-e",
            ".tmp",
        )

        assert result.exit_code == 0

    def test_clean_run_multiple_paths(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """clean run deve aceitar múltiplos diretórios."""
        path1 = e2e_env["temp"]
        path2 = e2e_env["source"]

        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(path1),
            str(path2),
        )

        assert result.exit_code == 0

    def test_clean_run_no_recursive(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """clean run deve aceitar opção --no-recursive."""
        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(sample_temp_files),
            "--no-recursive",
        )

        assert result.exit_code == 0
        assert (
            "recursivo" in result.output.lower() or "recursive" in result.output.lower()
        )


# ============================================================================
# Testes de clean preview
# ============================================================================


class TestCleanPreview:
    """Testes do comando clean preview."""

    def test_clean_preview_requires_paths(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """clean preview deve exigir PATHS."""
        result = cli_invoke("clean", "preview")

        assert result.exit_code != 0

    def test_clean_preview_shows_files(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """clean preview deve mostrar arquivos encontrados."""
        result = cli_invoke(
            "clean",
            "preview",
            str(sample_temp_files),
        )

        assert result.exit_code == 0
        # Deve mostrar informações sobre arquivos ou indicar que não há nada
        assert (
            "arquivo" in result.output.lower()
            or "nenhum" in result.output.lower()
            or "file" in result.output.lower()
        )

    def test_clean_preview_with_profile(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """clean preview deve aceitar --profile."""
        result = cli_invoke(
            "clean",
            "preview",
            str(sample_temp_files),
            "-p",
            "temp_files",
        )

        assert result.exit_code == 0


# ============================================================================
# Testes de clean profiles
# ============================================================================


class TestCleanProfiles:
    """Testes do comando clean profiles."""

    def test_clean_profiles_lists_available(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """clean profiles deve listar perfis disponíveis."""
        result = cli_invoke("clean", "profiles")

        assert result.exit_code == 0
        # Deve listar pelo menos alguns perfis
        assert "temp_files" in result.output.lower()

    def test_clean_profiles_shows_table(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """clean profiles deve mostrar tabela formatada."""
        result = cli_invoke("clean", "profiles")

        assert result.exit_code == 0
        # Deve ter alguma estrutura de tabela (nome/descrição)
        assert (
            "nome" in result.output.lower()
            or "perfil" in result.output.lower()
            or "profile" in result.output.lower()
        )


# ============================================================================
# Testes de Perfis Específicos
# ============================================================================


class TestCleanProfileTypes:
    """Testes dos diferentes perfis de limpeza."""

    @pytest.mark.parametrize(
        "profile",
        [
            "temp_files",
            "log_files",
            "cache_files",
            "downloads",
            "thumbnails",
        ],
    )
    def test_all_profiles_accepted(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
        profile: str,
    ) -> None:
        """Todos os perfis padrão devem ser aceitos."""
        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(sample_temp_files),
            "-p",
            profile,
        )

        assert result.exit_code == 0

    def test_invalid_profile_rejected(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """Perfil inválido deve ser rejeitado."""
        result = cli_invoke(
            "clean",
            "run",
            str(sample_temp_files),
            "-p",
            "perfil_inexistente",
        )

        assert result.exit_code != 0


# ============================================================================
# Testes de Mensagens
# ============================================================================


class TestCleanMessages:
    """Testes de mensagens da CLI."""

    def test_clean_run_shows_directories(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """clean run deve mostrar diretórios a limpar."""
        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(sample_temp_files),
        )

        assert result.exit_code == 0
        # Deve mostrar o caminho do diretório
        assert (
            "diretório" in result.output.lower()
            or str(sample_temp_files.name) in result.output
        )

    def test_clean_run_shows_profile(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """clean run deve mostrar perfil utilizado."""
        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(sample_temp_files),
            "-p",
            "cache_files",
        )

        assert result.exit_code == 0
        assert "cache_files" in result.output.lower()


# ============================================================================
# Testes de Opções Avançadas
# ============================================================================


class TestCleanAdvancedOptions:
    """Testes de opções avançadas."""

    def test_clean_run_keep_empty_dirs(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """clean run deve aceitar --keep-empty-dirs."""
        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(sample_temp_files),
            "--keep-empty-dirs",
        )

        assert result.exit_code == 0

    def test_clean_run_max_files(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """clean run deve aceitar --max-files."""
        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(sample_temp_files),
            "--max-files",
            "1000",
        )

        assert result.exit_code == 0

    def test_clean_run_multiple_extensions(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """clean run deve aceitar múltiplas extensões."""
        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(sample_temp_files),
            "-e",
            ".tmp",
            "-e",
            ".log",
            "-e",
            ".bak",
        )

        assert result.exit_code == 0


# ============================================================================
# Testes de Fluxo Completo
# ============================================================================


class TestCleanWorkflow:
    """Testes de fluxo completo de limpeza."""

    def test_preview_then_run_workflow(
        self,
        cli_invoke: Callable[..., Result],
        sample_temp_files: Path,
    ) -> None:
        """Fluxo preview → run deve funcionar."""
        # 1. Preview primeiro
        result1 = cli_invoke(
            "clean",
            "preview",
            str(sample_temp_files),
        )
        assert result1.exit_code == 0

        # 2. Run em dry-run
        result2 = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(sample_temp_files),
        )
        assert result2.exit_code == 0


# ============================================================================
# Testes de Edge Cases
# ============================================================================


class TestCleanEdgeCases:
    """Testes de casos extremos."""

    def test_clean_empty_directory(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """clean em diretório vazio deve funcionar."""
        empty_dir = e2e_env["temp"]
        # Garantir que está vazio
        for f in empty_dir.iterdir():
            if f.is_file():
                f.unlink()

        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(empty_dir),
        )

        assert result.exit_code == 0

    def test_clean_with_unicode_filenames(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """clean deve funcionar com nomes de arquivo unicode."""
        temp = e2e_env["temp"]
        (temp / "arquivo_日本語.tmp").write_text("teste")
        (temp / "données_été.tmp").write_text("teste")

        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(temp),
        )

        assert result.exit_code == 0

    def test_clean_with_symlinks(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """clean deve tratar symlinks corretamente."""
        temp = e2e_env["temp"]
        real_file = temp / "real_file.txt"
        real_file.write_text("real content")

        # Criar symlink (pode falhar em alguns sistemas)
        try:
            link = temp / "link_file.txt"
            link.symlink_to(real_file)
        except OSError:
            pytest.skip("Sistema não suporta symlinks")

        result = cli_invoke(
            "--dry-run",
            "clean",
            "run",
            str(temp),
        )

        assert result.exit_code == 0
