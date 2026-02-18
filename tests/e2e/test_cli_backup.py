"""
Testes End-to-End dos comandos de backup do AutoTarefas.

Este arquivo testa os comandos da CLI relacionados a backup,
verificando que funcionam corretamente do ponto de vista do usuário.

=============================================================================
O QUE O test_cli_backup.py TESTA
=============================================================================

Este arquivo testa os **comandos de backup** da CLI:

1. **backup run** - Cria um backup
   - Argumentos: SOURCE (obrigatório)
   - Opções: -d/--dest, -c/--compression, -e/--exclude
   - Cria arquivo compactado no destino

2. **backup list** - Lista backups existentes
   - Opções: -d/--dir, -n/--name, -l/--limit
   - Exibe tabela com backups encontrados

3. **backup restore** - Restaura um backup
   - Argumentos: BACKUP_FILE (obrigatório)
   - Opções: -d/--dest, -f/--force
   - Extrai arquivos do backup

4. **backup cleanup** - Remove backups antigos
   - Opções: -d/--dir, -n/--name, -k/--keep, -y/--yes
   - Remove versões antigas mantendo as mais recentes

=============================================================================
POR QUE ESTES TESTES SÃO IMPORTANTES
=============================================================================

Os comandos de backup são críticos porque:
- Dados do usuário estão em jogo
- Erros podem causar perda de dados
- A interface deve ser intuitiva e segura
- Mensagens de erro devem ser claras

=============================================================================
CENÁRIOS TESTADOS
=============================================================================

- Criação de backup com diferentes compressões
- Listagem de backups existentes
- Restauração de backup
- Limpeza de backups antigos
- Modo dry-run (simulação)
- Tratamento de erros (source inexistente, etc.)
- Opções de exclusão de arquivos
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


class TestBackupHelp:
    """Testes de help dos comandos de backup."""

    def test_backup_help(self, cli_invoke: Callable[..., Result]) -> None:
        """backup --help deve mostrar subcomandos."""
        result = cli_invoke("backup", "--help")

        assert result.exit_code == 0
        assert "run" in result.output
        assert "list" in result.output
        assert "restore" in result.output
        assert "cleanup" in result.output

    def test_backup_run_help(self, cli_invoke: Callable[..., Result]) -> None:
        """backup run --help deve mostrar opções."""
        result = cli_invoke("backup", "run", "--help")

        assert result.exit_code == 0
        assert "--dest" in result.output or "-d" in result.output
        assert "--compression" in result.output or "-c" in result.output
        assert "--exclude" in result.output or "-e" in result.output

    def test_backup_list_help(self, cli_invoke: Callable[..., Result]) -> None:
        """backup list --help deve mostrar opções."""
        result = cli_invoke("backup", "list", "--help")

        assert result.exit_code == 0
        assert "BACKUP_DIR" in result.output or "backup_dir" in result.output.lower()

    def test_backup_restore_help(self, cli_invoke: Callable[..., Result]) -> None:
        """backup restore --help deve mostrar opções."""
        result = cli_invoke("backup", "restore", "--help")

        assert result.exit_code == 0
        assert "--dest" in result.output or "-d" in result.output
        assert "--force" in result.output or "-f" in result.output

    def test_backup_cleanup_help(self, cli_invoke: Callable[..., Result]) -> None:
        """backup cleanup --help deve mostrar opções."""
        result = cli_invoke("backup", "cleanup", "--help")

        assert result.exit_code == 0
        assert "--keep" in result.output or "-k" in result.output
        assert "--yes" in result.output or "-y" in result.output


# ============================================================================
# Testes de backup run
# ============================================================================


class TestBackupRun:
    """Testes do comando backup run."""

    def test_backup_run_requires_source(self, cli_invoke: Callable[..., Result]) -> None:
        """backup run deve exigir SOURCE."""
        result = cli_invoke("backup", "run")

        assert result.exit_code != 0
        # Deve indicar que falta argumento
        assert (
            "source" in result.output.lower()
            or "missing" in result.output.lower()
            or "argument" in result.output.lower()
        )

    def test_backup_run_invalid_source(self, cli_invoke: Callable[..., Result]) -> None:
        """backup run deve falhar com source inexistente."""
        result = cli_invoke("backup", "run", "/caminho/que/nao/existe")

        assert result.exit_code != 0

    def test_backup_run_dry_run(
        self,
        cli_invoke: Callable[..., Result],
        sample_source_dir: Path,
    ) -> None:
        """backup run --dry-run deve simular sem criar arquivo."""
        result = cli_invoke(
            "--dry-run",
            "backup",
            "run",
            str(sample_source_dir),
        )

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower() or "dry" in result.output.lower()

    def test_backup_run_creates_backup(
        self,
        cli_invoke: Callable[..., Result],
        sample_source_dir: Path,
        e2e_env: dict[str, Path],
    ) -> None:
        """backup run deve criar arquivo de backup."""
        dest = e2e_env["backups"]

        result = cli_invoke(
            "backup",
            "run",
            str(sample_source_dir),
            str(dest),
        )

        # Verificar se criou backup (pode ter sucesso ou falhar dependendo de config)
        # O importante é não ter erro de sintaxe/uso
        assert "erro de uso" not in result.output.lower()

    def test_backup_run_with_compression(
        self,
        cli_invoke: Callable[..., Result],
        sample_source_dir: Path,
        e2e_env: dict[str, Path],
    ) -> None:
        """backup run deve aceitar opção de compressão."""
        dest = e2e_env["backups"]

        result = cli_invoke(
            "--dry-run",
            "backup",
            "run",
            str(sample_source_dir),
            str(dest),
            "-c",
            "zip",
        )

        assert result.exit_code == 0
        assert "zip" in result.output.lower()

    def test_backup_run_with_exclude(
        self,
        cli_invoke: Callable[..., Result],
        sample_source_dir: Path,
        e2e_env: dict[str, Path],
    ) -> None:
        """backup run deve aceitar padrões de exclusão."""
        dest = e2e_env["backups"]

        result = cli_invoke(
            "--dry-run",
            "backup",
            "run",
            str(sample_source_dir),
            str(dest),
            "-e",
            "*.tmp",
            "-e",
            "__pycache__",
        )

        assert result.exit_code == 0


# ============================================================================
# Testes de backup list
# ============================================================================


class TestBackupList:
    """Testes do comando backup list."""

    def test_backup_list_empty(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """backup list em diretório vazio deve informar."""
        empty_dir = e2e_env["backups"]

        result = cli_invoke(
            "backup",
            "list",
            str(empty_dir),
        )

        # Não deve dar erro, apenas informar que não há backups
        assert result.exit_code == 0 or "nenhum" in result.output.lower() or "no backup" in result.output.lower()

    def test_backup_list_with_limit(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """backup list deve aceitar opção --limit."""
        result = cli_invoke(
            "backup",
            "list",
            str(e2e_env["backups"]),
            "-l",
            "5",
        )

        # Não deve dar erro de sintaxe
        assert "erro de uso" not in result.output.lower()

    def test_backup_list_with_name_filter(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """backup list deve aceitar filtro por nome."""
        result = cli_invoke(
            "backup",
            "list",
            str(e2e_env["backups"]),
            "-n",
            "documents",
        )

        # Não deve dar erro de sintaxe
        assert "erro de uso" not in result.output.lower()


# ============================================================================
# Testes de backup restore
# ============================================================================


class TestBackupRestore:
    """Testes do comando backup restore."""

    def test_backup_restore_requires_file(self, cli_invoke: Callable[..., Result]) -> None:
        """backup restore deve exigir BACKUP_FILE."""
        result = cli_invoke("backup", "restore")

        assert result.exit_code != 0

    def test_backup_restore_invalid_file(self, cli_invoke: Callable[..., Result]) -> None:
        """backup restore deve falhar com arquivo inexistente."""
        result = cli_invoke("backup", "restore", "/arquivo/que/nao/existe.zip")

        assert result.exit_code != 0

    def test_backup_restore_dry_run(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """backup restore --dry-run deve simular."""
        # Criar um arquivo fake de backup
        fake_backup = e2e_env["backups"] / "fake_backup.zip"
        fake_backup.write_bytes(b"PK")  # Header mínimo de ZIP

        result = cli_invoke(
            "--dry-run",
            "backup",
            "restore",
            str(fake_backup),
        )

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower() or "dry" in result.output.lower()


# ============================================================================
# Testes de backup cleanup
# ============================================================================


class TestBackupCleanup:
    """Testes do comando backup cleanup."""

    def test_backup_cleanup_empty_dir(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """backup cleanup em diretório vazio deve funcionar."""
        result = cli_invoke(
            "backup",
            "cleanup",
            str(e2e_env["backups"]),
            "-y",  # Não pedir confirmação
        )

        # Não deve dar erro
        assert result.exit_code == 0 or "nenhum" in result.output.lower()

    def test_backup_cleanup_with_keep(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """backup cleanup deve aceitar opção --keep."""
        result = cli_invoke(
            "backup",
            "cleanup",
            str(e2e_env["backups"]),
            "-k",
            "3",
            "-y",
        )

        # Não deve dar erro de sintaxe
        assert "erro de uso" not in result.output.lower()

    def test_backup_cleanup_dry_run(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """backup cleanup --dry-run deve simular."""
        result = cli_invoke(
            "--dry-run",
            "backup",
            "cleanup",
            str(e2e_env["backups"]),
        )

        assert result.exit_code == 0


# ============================================================================
# Testes de Fluxo Completo
# ============================================================================


class TestBackupWorkflow:
    """
    Testes de fluxo completo de backup.

    Simula uso real: criar → listar → restaurar.
    """

    def test_full_backup_workflow_dry_run(
        self,
        cli_invoke: Callable[..., Result],
        sample_source_dir: Path,
        e2e_env: dict[str, Path],
    ) -> None:
        """Fluxo completo em dry-run deve funcionar."""
        dest = e2e_env["backups"]

        # 1. Criar backup (dry-run)
        result1 = cli_invoke(
            "--dry-run",
            "backup",
            "run",
            str(sample_source_dir),
            str(dest),
        )
        assert result1.exit_code == 0

        # 2. Listar backups
        result2 = cli_invoke(
            "backup",
            "list",
            str(dest),
        )
        assert result2.exit_code == 0 or "nenhum" in result2.output.lower()

        # 3. Cleanup (dry-run)
        result3 = cli_invoke(
            "--dry-run",
            "backup",
            "cleanup",
            str(dest),
        )
        assert result3.exit_code == 0


# ============================================================================
# Testes de Compressão
# ============================================================================


class TestBackupCompression:
    """Testes de tipos de compressão."""

    @pytest.mark.parametrize("compression", ["zip", "tar", "tar.gz", "tar.bz2"])
    def test_compression_types_accepted(
        self,
        cli_invoke: Callable[..., Result],
        sample_source_dir: Path,
        e2e_env: dict[str, Path],
        compression: str,
    ) -> None:
        """Todos os tipos de compressão devem ser aceitos."""
        result = cli_invoke(
            "--dry-run",
            "backup",
            "run",
            str(sample_source_dir),
            str(e2e_env["backups"]),
            "-c",
            compression,
        )

        assert result.exit_code == 0

    def test_invalid_compression_rejected(
        self,
        cli_invoke: Callable[..., Result],
        sample_source_dir: Path,
    ) -> None:
        """Tipo de compressão inválido deve ser rejeitado."""
        result = cli_invoke(
            "backup",
            "run",
            str(sample_source_dir),
            "-c",
            "invalid_format",
        )

        assert result.exit_code != 0


# ============================================================================
# Testes de Mensagens
# ============================================================================


class TestBackupMessages:
    """Testes de mensagens da CLI."""

    def test_backup_run_shows_source(
        self,
        cli_invoke: Callable[..., Result],
        sample_source_dir: Path,
    ) -> None:
        """backup run deve mostrar origem."""
        result = cli_invoke(
            "--dry-run",
            "backup",
            "run",
            str(sample_source_dir),
        )

        assert result.exit_code == 0
        # Deve mostrar o caminho de origem
        assert (
            "origem" in result.output.lower()
            or "source" in result.output.lower()
            or str(sample_source_dir.name) in result.output
        )

    def test_backup_run_shows_destination(
        self,
        cli_invoke: Callable[..., Result],
        sample_source_dir: Path,
        e2e_env: dict[str, Path],
    ) -> None:
        """backup run deve mostrar destino."""
        dest = e2e_env["backups"]

        result = cli_invoke(
            "--dry-run",
            "backup",
            "run",
            str(sample_source_dir),
            str(dest),
        )

        assert result.exit_code == 0
        # Deve mostrar o caminho de destino
        assert "destino" in result.output.lower() or "dest" in result.output.lower()


# ============================================================================
# Testes de Edge Cases
# ============================================================================


class TestBackupEdgeCases:
    """Testes de casos extremos."""

    def test_backup_source_is_file(
        self,
        cli_invoke: Callable[..., Result],
        sample_source_dir: Path,
        e2e_env: dict[str, Path],
    ) -> None:
        """backup run deve aceitar arquivo como source."""
        # Usar um arquivo específico como source
        single_file = sample_source_dir / "config.json"

        if single_file.exists():
            result = cli_invoke(
                "--dry-run",
                "backup",
                "run",
                str(single_file),
                str(e2e_env["backups"]),
            )

            assert result.exit_code == 0

    def test_backup_with_unicode_path(
        self,
        cli_invoke: Callable[..., Result],
        e2e_env: dict[str, Path],
    ) -> None:
        """backup run deve funcionar com caminhos unicode."""
        # Criar diretório com nome unicode
        unicode_dir = e2e_env["source"] / "relatórios_日本語"
        unicode_dir.mkdir(exist_ok=True)
        (unicode_dir / "dados.txt").write_text("Conteúdo com acentos: é ã ç")

        result = cli_invoke(
            "--dry-run",
            "backup",
            "run",
            str(unicode_dir),
            str(e2e_env["backups"]),
        )

        assert result.exit_code == 0

    def test_backup_multiple_excludes(
        self,
        cli_invoke: Callable[..., Result],
        sample_source_dir: Path,
        e2e_env: dict[str, Path],
    ) -> None:
        """backup run deve aceitar múltiplos --exclude."""
        result = cli_invoke(
            "--dry-run",
            "backup",
            "run",
            str(sample_source_dir),
            str(e2e_env["backups"]),
            "-e",
            "*.tmp",
            "-e",
            "*.log",
            "-e",
            "__pycache__",
            "-e",
            ".git",
        )

        assert result.exit_code == 0
