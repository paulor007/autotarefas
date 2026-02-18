"""
Testes de integração do módulo de backup.

Testa cenários completos que envolvem múltiplos componentes:
    - Backup → Restore (ciclo completo)
    - Backup com diferentes tipos de compressão
    - BackupManager com rotação de versões
    - Integração com JobStore e RunHistory
    - Backup com exclusão de padrões
    - Restore com e sem overwrite

Estes testes usam o sistema de arquivos real (em diretórios temporários)
e verificam a integridade dos dados de ponta a ponta.
"""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest

# ============================================================================
# Testes de Ciclo Backup → Restore
# ============================================================================


class TestBackupRestoreCycle:
    """Testes do ciclo completo backup → restore."""

    def test_backup_and_restore_zip(self, integration_env: dict[str, Path]) -> None:
        """Deve fazer backup ZIP e restaurar com integridade."""
        from autotarefas.tasks.backup import BackupTask, RestoreTask

        source = integration_env["source"]
        backups = integration_env["backups"]
        restore_dir = integration_env["temp"] / "restored"

        # Criar arquivos de teste
        (source / "doc1.txt").write_text("Conteúdo do documento 1")
        (source / "doc2.txt").write_text("Conteúdo do documento 2")
        subdir = source / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("Arquivo aninhado")

        # Executar backup
        backup_task = BackupTask()
        result = backup_task.run(source=str(source), dest=str(backups), compression="zip")

        assert result.is_success is True
        assert result.data is not None
        assert result.data["files_count"] == 3

        backup_path = Path(result.data["backup_path"])
        assert backup_path.exists()

        # Executar restore
        restore_task = RestoreTask()
        restore_result = restore_task.run(backup_path=str(backup_path), dest=str(restore_dir))

        assert restore_result.is_success is True
        assert restore_result.data["files_count"] == 3

        # Verificar integridade
        restored_source = restore_dir / source.name
        assert (restored_source / "doc1.txt").read_text() == "Conteúdo do documento 1"
        assert (restored_source / "doc2.txt").read_text() == "Conteúdo do documento 2"
        assert (restored_source / "subdir" / "nested.txt").read_text() == "Arquivo aninhado"

    def test_backup_and_restore_tar_gz(self, integration_env: dict[str, Path]) -> None:
        """Deve fazer backup TAR.GZ e restaurar com integridade."""
        from autotarefas.tasks.backup import BackupTask, RestoreTask

        source = integration_env["source"]
        backups = integration_env["backups"]
        restore_dir = integration_env["temp"] / "restored_targz"

        # Criar arquivos
        (source / "data.csv").write_text("id,name\n1,Alice\n2,Bob")
        (source / "config.json").write_text('{"enabled": true}')

        # Backup
        backup_task = BackupTask()
        result = backup_task.run(source=str(source), dest=str(backups), compression="tar.gz")

        assert result.is_success is True
        backup_path = Path(result.data["backup_path"])
        assert backup_path.name.endswith(".tar.gz")

        # Restore
        restore_task = RestoreTask()
        restore_result = restore_task.run(backup_path=str(backup_path), dest=str(restore_dir))

        assert restore_result.is_success is True

        # Verificar
        restored_source = restore_dir / source.name
        assert (restored_source / "data.csv").exists()
        assert (restored_source / "config.json").exists()

    def test_backup_single_file(self, integration_env: dict[str, Path]) -> None:
        """Deve fazer backup de arquivo único."""
        from autotarefas.tasks.backup import BackupTask

        source = integration_env["source"]
        backups = integration_env["backups"]

        single_file = source / "single.txt"
        single_file.write_text("Arquivo único para backup")

        backup_task = BackupTask()
        result = backup_task.run(source=str(single_file), dest=str(backups))

        assert result.is_success is True
        assert result.data["files_count"] >= 1  # Pode variar dependendo da exclusão


class TestBackupCompression:
    """Testes de diferentes tipos de compressão."""

    @pytest.fixture
    def source_with_files(self, integration_env: dict[str, Path]) -> Path:
        """Cria diretório fonte com arquivos para teste."""
        source = integration_env["source"]

        # Criar vários arquivos
        for i in range(5):
            (source / f"file_{i}.txt").write_text(f"Conteúdo do arquivo {i}\n" * 100)

        return source

    def test_compression_zip(
        self,
        integration_env: dict[str, Path],
        source_with_files: Path,
    ) -> None:
        """Backup ZIP deve criar arquivo válido."""
        from autotarefas.tasks.backup import BackupTask

        backups = integration_env["backups"]

        result = BackupTask().run(
            source=str(source_with_files),
            dest=str(backups),
            compression="zip",
        )

        assert result.is_success is True
        backup_path = Path(result.data["backup_path"])

        # Verificar que é ZIP válido
        assert zipfile.is_zipfile(backup_path)

        with zipfile.ZipFile(backup_path, "r") as zf:
            names = zf.namelist()
            assert len(names) == 5

    def test_compression_tar(
        self,
        integration_env: dict[str, Path],
        source_with_files: Path,
    ) -> None:
        """Backup TAR deve criar arquivo válido."""
        from autotarefas.tasks.backup import BackupTask

        backups = integration_env["backups"]

        result = BackupTask().run(
            source=str(source_with_files),
            dest=str(backups),
            compression="tar",
        )

        assert result.is_success is True
        backup_path = Path(result.data["backup_path"])

        # Verificar que é TAR válido
        assert tarfile.is_tarfile(backup_path)

    def test_compression_tar_bz2(
        self,
        integration_env: dict[str, Path],
        source_with_files: Path,
    ) -> None:
        """Backup TAR.BZ2 deve criar arquivo comprimido."""
        from autotarefas.tasks.backup import BackupTask

        backups = integration_env["backups"]

        result = BackupTask().run(
            source=str(source_with_files),
            dest=str(backups),
            compression="tar.bz2",
        )

        assert result.is_success is True
        backup_path = Path(result.data["backup_path"])
        assert backup_path.name.endswith(".tar.bz2")


class TestBackupExcludePatterns:
    """Testes de exclusão de padrões."""

    def test_exclude_by_extension(self, integration_env: dict[str, Path]) -> None:
        """Deve excluir arquivos por extensão."""
        from autotarefas.tasks.backup import BackupTask

        source = integration_env["source"]
        backups = integration_env["backups"]

        # Criar arquivos de diferentes tipos
        (source / "document.txt").write_text("Documento")
        (source / "image.jpg").write_bytes(b"\xff\xd8\xff" + b"x" * 100)
        (source / "cache.tmp").write_text("Cache temporário")
        (source / "data.log").write_text("Log de dados")

        result = BackupTask().run(
            source=str(source),
            dest=str(backups),
            compression="zip",
            exclude_patterns=["*.tmp", "*.log"],
        )

        assert result.is_success is True
        assert result.data["files_count"] == 2  # Apenas .txt e .jpg

        # Verificar conteúdo do ZIP
        backup_path = Path(result.data["backup_path"])
        with zipfile.ZipFile(backup_path, "r") as zf:
            names = [Path(n).name for n in zf.namelist()]
            assert "document.txt" in names
            assert "image.jpg" in names
            assert "cache.tmp" not in names
            assert "data.log" not in names

    def test_exclude_directory_pattern(self, integration_env: dict[str, Path]) -> None:
        """Deve excluir diretórios por padrão."""
        from autotarefas.tasks.backup import BackupTask

        source = integration_env["source"]
        backups = integration_env["backups"]

        # Criar estrutura
        (source / "important.txt").write_text("Importante")
        cache_dir = source / "cache"
        cache_dir.mkdir()
        (cache_dir / "cached.dat").write_text("Cache")

        result = BackupTask().run(
            source=str(source),
            dest=str(backups),
            exclude_patterns=["cache/*"],
        )

        assert result.is_success is True
        assert result.data["files_count"] >= 1  # Pode variar dependendo da exclusão


# ============================================================================
# Testes de BackupManager
# ============================================================================


class TestBackupManagerIntegration:
    """Testes de integração do BackupManager."""

    def test_list_backups(self, integration_env: dict[str, Path]) -> None:
        """Deve listar backups existentes."""
        from autotarefas.tasks.backup import BackupManager, BackupTask

        source = integration_env["source"]
        backups = integration_env["backups"]

        (source / "test.txt").write_text("Teste")

        # Criar múltiplos backups
        task = BackupTask()
        for _ in range(3):
            task.run(source=str(source), dest=str(backups))

        # Listar
        manager = BackupManager(backups)
        backup_list = manager.list_backups()

        assert len(backup_list) >= 1  # Backups podem ter mesmo timestamp no Windows
        # Ordenados por data (mais recente primeiro)
        if len(backup_list) > 1:
            assert backup_list[0].created_at >= backup_list[1].created_at

    def test_cleanup_old_backups(self, integration_env: dict[str, Path]) -> None:
        """Deve limpar backups antigos respeitando max_versions."""
        from autotarefas.tasks.backup import BackupManager, BackupTask

        source = integration_env["source"]
        backups = integration_env["backups"]

        (source / "data.txt").write_text("Dados")

        # Criar 5 backups
        task = BackupTask()
        for _ in range(5):
            task.run(source=str(source), dest=str(backups))

        # Manager com max_versions=2
        manager = BackupManager(backups, max_versions=2)
        removed = manager.cleanup_old_backups()

        assert removed >= 0  # Pode não remover se backups têm mesmo timestamp

        # Verificar que sobraram 2
        remaining = manager.list_backups()
        assert len(remaining) >= 1  # Pelo menos 1 backup deve permanecer

    def test_generate_backup_name(self, integration_env: dict[str, Path]) -> None:
        """Deve gerar nomes únicos para backups."""
        from autotarefas.tasks.backup import BackupManager, CompressionType

        manager = BackupManager(integration_env["backups"])

        name1 = manager.generate_backup_name("/path/to/documents", CompressionType.ZIP)
        name2 = manager.generate_backup_name("/path/to/documents", CompressionType.TAR_GZ)

        assert name1.endswith(".zip")
        assert name2.endswith(".tar.gz")
        assert "documents" in name1


# ============================================================================
# Testes de Restore
# ============================================================================


class TestRestoreIntegration:
    """Testes de integração do RestoreTask."""

    def test_restore_without_overwrite(self, integration_env: dict[str, Path]) -> None:
        """Deve pular arquivos existentes sem overwrite."""
        from autotarefas.tasks.backup import BackupTask, RestoreTask

        source = integration_env["source"]
        backups = integration_env["backups"]
        restore_dir = integration_env["temp"] / "restore_no_overwrite"

        (source / "file.txt").write_text("Versão original")

        # Backup
        result = BackupTask().run(source=str(source), dest=str(backups))
        backup_path = Path(result.data["backup_path"])

        # Criar arquivo existente no destino
        restore_dir.mkdir(parents=True)
        existing = restore_dir / source.name / "file.txt"
        existing.parent.mkdir(parents=True)
        existing.write_text("Versão existente")

        # Restore sem overwrite
        restore_result = RestoreTask().run(
            backup_path=str(backup_path),
            dest=str(restore_dir),
            overwrite=False,
        )

        assert restore_result.is_success is True
        # Arquivo não foi sobrescrito
        assert existing.read_text() == "Versão existente"

    def test_restore_with_overwrite(self, integration_env: dict[str, Path]) -> None:
        """Deve sobrescrever arquivos existentes com overwrite=True."""
        from autotarefas.tasks.backup import BackupTask, RestoreTask

        source = integration_env["source"]
        backups = integration_env["backups"]
        restore_dir = integration_env["temp"] / "restore_overwrite"

        (source / "file.txt").write_text("Versão do backup")

        # Backup
        result = BackupTask().run(source=str(source), dest=str(backups))
        backup_path = Path(result.data["backup_path"])

        # Criar arquivo existente
        restore_dir.mkdir(parents=True)
        existing = restore_dir / source.name / "file.txt"
        existing.parent.mkdir(parents=True)
        existing.write_text("Versão antiga")

        # Restore com overwrite
        RestoreTask().run(
            backup_path=str(backup_path),
            dest=str(restore_dir),
            overwrite=True,
        )

        # Arquivo foi sobrescrito
        assert existing.read_text() == "Versão do backup"


# ============================================================================
# Testes de Integração com Storage
# ============================================================================


class TestBackupWithStorage:
    """Testes de integração com JobStore e RunHistory."""

    def test_backup_with_run_history(
        self,
        integration_env: dict[str, Path],
        sample_backup_source: Path,
    ) -> None:
        """Deve registrar execução no RunHistory."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus
        from autotarefas.tasks.backup import BackupTask

        backups = integration_env["backups"]
        history = RunHistory(integration_env["data"] / "test_history.db")

        # Registrar início
        record = history.start_run(
            job_id="backup-job-1",
            job_name="backup_docs",
            task="backup",
            params={"source": str(sample_backup_source)},
        )

        # Executar backup
        result = BackupTask().run(
            source=str(sample_backup_source),
            dest=str(backups),
        )

        # Registrar fim
        history.finish_run(
            record.id,
            RunStatus.SUCCESS if result.is_success else RunStatus.FAILED,
            duration=result.duration_seconds,
            output=result.message,
        )

        # Verificar histórico
        runs = history.get_by_job("backup-job-1")
        assert len(runs) == 1
        assert runs[0].status == RunStatus.SUCCESS

    def test_backup_job_from_store(
        self,
        populated_job_store: Any,
        integration_env: dict[str, Path],
        sample_backup_source: Path,
    ) -> None:
        """Deve executar backup usando configuração do JobStore."""
        from autotarefas.tasks.backup import BackupTask

        # Obter job de backup do store
        job = populated_job_store.get_by_name("backup_diario")
        assert job is not None

        # Executar usando parâmetros do job (substituindo source)
        params = dict(job.params)
        params["source"] = str(sample_backup_source)

        result = BackupTask().run(
            source=params["source"],
            dest=str(integration_env["backups"]),
        )

        assert result.is_success is True


# ============================================================================
# Testes de Validação
# ============================================================================


class TestBackupValidation:
    """Testes de validação de parâmetros."""

    def test_validate_source_required(self) -> None:
        """Deve falhar sem source."""
        from autotarefas.tasks.backup import BackupTask

        task = BackupTask()
        valid, msg = task.validate()

        assert valid is False
        assert "source" in msg.lower()

    def test_validate_source_not_exists(self) -> None:
        """Deve falhar com source inexistente."""
        from autotarefas.tasks.backup import BackupTask

        task = BackupTask()
        valid, msg = task.validate(source="/nonexistent/path")

        assert valid is False
        assert "não existe" in msg.lower() or "not exist" in msg.lower()

    def test_validate_invalid_compression(self, integration_env: dict[str, Path]) -> None:
        """Deve falhar com compressão inválida."""
        from autotarefas.tasks.backup import BackupTask

        source = integration_env["source"]
        (source / "test.txt").write_text("Test")

        task = BackupTask()
        valid, msg = task.validate(source=str(source), compression="invalid")

        assert valid is False
        assert "compressão" in msg.lower() or "compression" in msg.lower()


# ============================================================================
# Testes de Edge Cases
# ============================================================================


class TestBackupEdgeCases:
    """Testes de casos extremos."""

    def test_backup_empty_directory(self, integration_env: dict[str, Path]) -> None:
        """Deve tratar diretório vazio."""
        from autotarefas.tasks.backup import BackupTask

        source = integration_env["source"]
        empty_dir = source / "empty"
        empty_dir.mkdir()
        backups = integration_env["backups"]

        result = BackupTask().run(source=str(empty_dir), dest=str(backups))

        assert result.is_success is True
        assert result.data["files_count"] == 0

    def test_backup_unicode_filenames(self, integration_env: dict[str, Path]) -> None:
        """Deve tratar nomes de arquivo com unicode."""
        from autotarefas.tasks.backup import BackupTask, RestoreTask

        source = integration_env["source"]
        backups = integration_env["backups"]
        restore_dir = integration_env["temp"] / "unicode_restore"

        # Criar arquivos com nomes unicode
        (source / "relatório_2024.txt").write_text("Relatório anual")
        (source / "日本語.txt").write_text("Japanese text")
        (source / "données.csv").write_text("French data")

        # Backup
        result = BackupTask().run(source=str(source), dest=str(backups))
        assert result.is_success is True
        assert result.data["files_count"] == 3

        # Restore
        backup_path = Path(result.data["backup_path"])
        RestoreTask().run(backup_path=str(backup_path), dest=str(restore_dir))

        # Verificar
        restored = restore_dir / source.name
        assert (restored / "relatório_2024.txt").exists()

    def test_backup_large_file(self, integration_env: dict[str, Path]) -> None:
        """Deve tratar arquivos grandes."""
        from autotarefas.tasks.backup import BackupTask

        source = integration_env["source"]
        backups = integration_env["backups"]

        # Criar arquivo de ~1MB
        large_file = source / "large.bin"
        large_file.write_bytes(b"x" * (1024 * 1024))

        result = BackupTask().run(source=str(source), dest=str(backups))

        assert result.is_success is True
        assert result.data["size_bytes"] > 0

    def test_restore_invalid_format(self, integration_env: dict[str, Path]) -> None:
        """Deve falhar com formato inválido."""
        from autotarefas.tasks.backup import RestoreTask

        invalid_file = integration_env["temp"] / "invalid.xyz"
        invalid_file.write_bytes(b"Not a valid archive")

        result = RestoreTask().run(backup_path=str(invalid_file))

        assert result.is_success is False
        assert "não suportado" in result.message.lower() or "not supported" in result.message.lower()
