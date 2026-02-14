"""Tests for autotarefas.tasks.backup.

Cobre:
- CompressionType: Enum e conversões
- BackupInfo: Dataclass de informações
- BackupManager: nomes, listagem, latest, cleanup
- BackupTask: validate + execução (zip/tar.gz) + exclusões + edge cases
- RestoreTask: restauração (zip)

Observação:
- Alguns testes usam fixtures do projeto (ex.: temp_dir, large_file).
"""

from __future__ import annotations

import inspect
import os
import re
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

# =============================================================================
# Helpers internos dos testes
# =============================================================================

_ARCHIVE_PATTERNS = ("*.zip", "*.tar", "*.tar.gz", "*.tar.bz2")


def _set_mtime(path: Path, dt: datetime) -> None:
    """Define mtime/atime para ficar determinístico."""
    # dt pode ser aware (UTC) ou naive; timestamp() funciona para ambos.
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


def _find_archives(dest: Path) -> list[Path]:
    """Retorna arquivos de backup conhecidos dentro de dest."""
    found: list[Path] = []
    for pat in _ARCHIVE_PATTERNS:
        found.extend(dest.glob(pat))
    return sorted(found)


def _list_archive_members(archive_path: Path) -> list[str]:
    """Lista membros do arquivo compactado (zip/tar/tar.gz/tar.bz2)."""
    name = archive_path.name.lower()

    if name.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            return zf.namelist()

    if name.endswith(".tar.gz"):
        mode = "r:gz"
    elif name.endswith(".tar.bz2"):
        mode = "r:bz2"
    elif name.endswith(".tar"):
        mode = "r"
    else:
        raise AssertionError(
            f"Formato de backup não suportado no teste: {archive_path}"
        )

    with tarfile.open(archive_path, mode) as tf:
        return [m.name for m in tf.getmembers()]


def _list_archive_files_only(archive_path: Path) -> list[str]:
    """Lista apenas arquivos (ignora diretórios) para asserts mais precisos."""
    name = archive_path.name.lower()

    if name.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            return [n for n in zf.namelist() if not n.endswith("/")]

    if name.endswith(".tar.gz"):
        mode = "r:gz"
    elif name.endswith(".tar.bz2"):
        mode = "r:bz2"
    elif name.endswith(".tar"):
        mode = "r"
    else:
        raise AssertionError(
            f"Formato de backup não suportado no teste: {archive_path}"
        )

    with tarfile.open(archive_path, mode) as tf:
        return [m.name for m in tf.getmembers() if m.isfile()]


def _make_tree(root: Path, files: dict[str, str]) -> Path:
    """Cria estrutura de arquivos a partir de um dict {relpath: content}."""
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return root


# =============================================================================
# Testes de CompressionType
# =============================================================================


class TestCompressionType:
    """Testes do enum CompressionType."""

    def test_compression_values_exist(self):
        """Deve ter todos os tipos de compressão suportados."""
        from autotarefas.tasks.backup import CompressionType

        assert hasattr(CompressionType, "ZIP")
        assert hasattr(CompressionType, "TAR")
        assert hasattr(CompressionType, "TAR_GZ")
        assert hasattr(CompressionType, "TAR_BZ2")

    @pytest.mark.parametrize(
        ("attr", "value", "ext"),
        [
            ("ZIP", "zip", ".zip"),
            ("TAR", "tar", ".tar"),
            ("TAR_GZ", "tar.gz", ".tar.gz"),
            ("TAR_BZ2", "tar.bz2", ".tar.bz2"),
        ],
    )
    def test_compression_values_and_extension(self, attr: str, value: str, ext: str):
        """value/extension devem bater com o Enum real."""
        from autotarefas.tasks.backup import CompressionType

        ct = getattr(CompressionType, attr)
        assert ct.value == value
        assert ct.extension == ext

    @pytest.mark.parametrize(
        ("raw", "expected_attr"),
        [
            ("zip", "ZIP"),
            ("tar", "TAR"),
            ("tar.gz", "TAR_GZ"),
            ("tar.bz2", "TAR_BZ2"),
            (" ZIP ", "ZIP"),
            ("Tar.Gz", "TAR_GZ"),
        ],
    )
    def test_from_string_valid(self, raw: str, expected_attr: str):
        """from_string deve converter strings válidas (case/whitespace)."""
        from autotarefas.tasks.backup import CompressionType

        assert CompressionType.from_string(raw) == getattr(
            CompressionType, expected_attr
        )

    @pytest.mark.parametrize("raw", ["invalid", "rar", "", "   "])
    def test_from_string_invalid(self, raw: str):
        """from_string deve falhar para tipos inválidos."""
        from autotarefas.tasks.backup import CompressionType

        with pytest.raises(ValueError):
            CompressionType.from_string(raw)


# =============================================================================
# Testes de BackupInfo
# =============================================================================


class TestBackupInfo:
    """Testes da dataclass BackupInfo."""

    def test_backup_info_creation(self, temp_dir: Path):
        """Deve criar BackupInfo corretamente."""
        from autotarefas.tasks.backup import BackupInfo, CompressionType

        backup_path = temp_dir / "test_20240115_120000.zip"
        backup_path.write_bytes(b"fake zip content")

        info = BackupInfo(
            path=backup_path,
            source=Path("test"),
            created_at=datetime.now(UTC),
            size_bytes=100,
            compression=CompressionType.ZIP,
        )

        assert info.path == backup_path
        assert info.source == Path("test")
        assert info.size_bytes == 100
        assert info.compression == CompressionType.ZIP
        assert info.files_count == 0

    def test_backup_info_with_files_count(self, temp_dir: Path):
        """Deve aceitar files_count."""
        from autotarefas.tasks.backup import BackupInfo, CompressionType

        info = BackupInfo(
            path=temp_dir / "backup.zip",
            source=Path("source"),
            created_at=datetime.now(UTC),
            size_bytes=1024,
            compression=CompressionType.ZIP,
            files_count=42,
        )
        assert info.files_count == 42


# =============================================================================
# Testes de BackupManager
# =============================================================================


class TestBackupManager:
    """Testes da classe BackupManager."""

    def test_manager_creation(self, temp_dir: Path):
        """Deve criar BackupManager e diretório."""
        from autotarefas.tasks.backup import BackupManager

        backup_dir = temp_dir / "backups"
        manager = BackupManager(backup_dir=backup_dir, max_versions=5)

        assert manager.backup_dir == backup_dir
        assert manager.max_versions == 5
        assert backup_dir.exists()

    def test_manager_creates_directory(self, temp_dir: Path):
        """Deve criar diretório de backup se não existir."""
        from autotarefas.tasks.backup import BackupManager

        backup_dir = temp_dir / "new" / "nested" / "backups"
        _ = BackupManager(backup_dir=backup_dir)

        assert backup_dir.exists()

    def test_generate_backup_name(self, temp_dir: Path):
        """Deve gerar nome de backup válido."""
        from autotarefas.tasks.backup import BackupManager, CompressionType

        manager = BackupManager(backup_dir=temp_dir)
        name = manager.generate_backup_name("documents", CompressionType.ZIP)

        assert name.startswith("documents_")
        assert name.endswith(".zip")
        assert re.search(r"documents_\d{8}_\d{6}\.zip$", name)

    def test_list_backups_empty(self, temp_dir: Path):
        """Deve retornar lista vazia se não houver backups."""
        from autotarefas.tasks.backup import BackupManager

        manager = BackupManager(backup_dir=temp_dir)
        backups = manager.list_backups()

        assert backups == []

    def test_list_backups_sorted_by_date(self, temp_dir: Path):
        """Backups devem ser ordenados por data (mais recente primeiro)."""
        from autotarefas.tasks.backup import BackupManager

        old = temp_dir / "docs_20240101_100000.zip"
        new = temp_dir / "docs_20240115_100000.zip"
        old.write_bytes(b"old")
        new.write_bytes(b"new")

        _set_mtime(old, datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC))
        _set_mtime(new, datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))

        manager = BackupManager(backup_dir=temp_dir)
        backups = manager.list_backups()

        assert [b.path.name for b in backups] == [new.name, old.name]

    def test_list_backups_filter_by_source(self, temp_dir: Path):
        """Deve filtrar por source_name."""
        from autotarefas.tasks.backup import BackupManager

        (temp_dir / "docs_20240115_100000.zip").write_bytes(b"fake")
        (temp_dir / "photos_20240115_100000.zip").write_bytes(b"fake")

        manager = BackupManager(backup_dir=temp_dir)
        docs_backups = manager.list_backups(source_name="docs")

        assert len(docs_backups) == 1
        assert "docs" in docs_backups[0].path.name

    def test_get_latest_backup(self, temp_dir: Path):
        """Deve retornar backup mais recente."""
        from autotarefas.tasks.backup import BackupManager

        old = temp_dir / "docs_20240101_100000.zip"
        new = temp_dir / "docs_20240115_100000.zip"
        old.write_bytes(b"old")
        new.write_bytes(b"new")

        _set_mtime(old, datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC))
        _set_mtime(new, datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))

        manager = BackupManager(backup_dir=temp_dir)
        latest = manager.get_latest_backup("docs")

        assert latest is not None
        assert latest.path.name == new.name

    def test_get_latest_backup_none(self, temp_dir: Path):
        """Deve retornar None se não houver backups."""
        from autotarefas.tasks.backup import BackupManager

        manager = BackupManager(backup_dir=temp_dir)
        latest = manager.get_latest_backup("nonexistent")

        assert latest is None

    def test_cleanup_old_backups(self, temp_dir: Path):
        """Deve remover backups além do limite."""
        from autotarefas.tasks.backup import BackupManager

        for i in range(5):
            p = temp_dir / f"docs_2024011{i}_100000.zip"
            p.write_bytes(b"fake")
            _set_mtime(p, datetime(2024, 1, 10 + i, 10, 0, 0, tzinfo=UTC))

        manager = BackupManager(backup_dir=temp_dir, max_versions=3)
        removed = manager.cleanup_old_backups()

        assert removed == 2
        assert len(manager.list_backups()) == 3


# =============================================================================
# Testes de BackupTask
# =============================================================================


class TestBackupTask:
    """Testes da classe BackupTask."""

    def test_task_metadata(self):
        """Task deve ter nome e descrição."""
        from autotarefas.tasks.backup import BackupTask

        task = BackupTask()
        assert task.name == "backup"
        assert task.description

    def test_validate_missing_source(self):
        """Deve falhar sem source."""
        from autotarefas.tasks.backup import BackupTask

        task = BackupTask()
        is_valid, error = task.validate(dest="/backups")

        assert is_valid is False
        assert "source" in error.lower()

    def test_validate_nonexistent_source(self, temp_dir: Path):
        """Deve falhar com source inexistente."""
        from autotarefas.tasks.backup import BackupTask

        task = BackupTask()
        is_valid, error = task.validate(source=str(temp_dir / "nonexistent"))

        assert is_valid is False
        assert "não existe" in error.lower() or "exist" in error.lower()

    def test_validate_invalid_compression(self, temp_dir: Path):
        """Deve falhar com compressão inválida."""
        from autotarefas.tasks.backup import BackupTask

        source = temp_dir / "source"
        source.mkdir()

        task = BackupTask()
        is_valid, error = task.validate(source=str(source), compression="rar")

        assert is_valid is False
        assert "não suportado" in error.lower()

    def test_validate_valid_params(self, temp_dir: Path):
        """Deve aceitar parâmetros válidos."""
        from autotarefas.tasks.backup import BackupTask

        source = _make_tree(temp_dir / "source", {"file.txt": "content"})
        dest = temp_dir / "backups"

        task = BackupTask()
        is_valid, error = task.validate(source=str(source), dest=str(dest))

        assert is_valid is True
        assert error == ""


class TestBackupTaskExecution:
    """Testes de execução do BackupTask."""

    @pytest.mark.parametrize(
        ("compression", "suffix"),
        [
            ("zip", ".zip"),
            ("tar.gz", ".tar.gz"),
        ],
    )
    def test_execute_creates_archive(
        self, temp_dir: Path, compression: str, suffix: str
    ):
        """Deve criar backup no formato solicitado."""
        from autotarefas.tasks.backup import BackupTask

        source = _make_tree(temp_dir / "source", {"file1.txt": "1", "file2.txt": "2"})
        dest = temp_dir / "backups"

        task = BackupTask()
        result = task.execute(
            source=str(source), dest=str(dest), compression=compression
        )

        assert result.is_success
        archives = _find_archives(dest)
        assert any(p.name.endswith(suffix) for p in archives)

    def test_execute_backup_contains_files(self, temp_dir: Path):
        """Backup deve conter os arquivos."""
        from autotarefas.tasks.backup import BackupTask

        source = _make_tree(temp_dir / "source", {"test.txt": "test content"})
        dest = temp_dir / "backups"

        task = BackupTask()
        result = task.execute(source=str(source), dest=str(dest))

        assert result.is_success
        archives = _find_archives(dest)
        assert len(archives) == 1

        files = _list_archive_files_only(archives[0])
        assert any(name.endswith("test.txt") for name in files)

    def test_execute_returns_data(self, temp_dir: Path):
        """Result deve ter dados do backup."""
        from autotarefas.tasks.backup import BackupTask

        source = _make_tree(temp_dir / "source", {"file.txt": "x" * 100})
        dest = temp_dir / "backups"

        task = BackupTask()
        result = task.execute(source=str(source), dest=str(dest))

        assert result.is_success
        assert isinstance(result.data, dict)
        assert "backup_path" in result.data
        assert "files_count" in result.data
        assert "compression" in result.data

    def test_execute_exclude_patterns(self, temp_dir: Path):
        """Deve excluir arquivos por padrão."""
        from autotarefas.tasks.backup import BackupTask

        source = _make_tree(
            temp_dir / "source",
            {
                "include.txt": "include",
                "exclude.tmp": "exclude",
                "exclude.log": "exclude",
            },
        )
        dest = temp_dir / "backups"

        task = BackupTask()
        result = task.execute(
            source=str(source),
            dest=str(dest),
            exclude_patterns=["*.tmp", "*.log"],
        )

        assert result.is_success
        archives = _find_archives(dest)
        assert len(archives) == 1

        files = _list_archive_files_only(archives[0])
        assert any(name.endswith("include.txt") for name in files)
        assert not any(name.endswith(".tmp") for name in files)
        assert not any(name.endswith(".log") for name in files)

    def test_execute_dry_run_future(self, temp_dir: Path):
        """Se um dia existir dry_run, não deve criar arquivo."""
        from autotarefas.tasks.backup import BackupTask

        task = BackupTask()
        sig = inspect.signature(task.execute)
        if "dry_run" not in sig.parameters:
            pytest.skip("execute() não suporta dry_run ainda")

        source = _make_tree(temp_dir / "source", {"file.txt": "content"})
        dest = temp_dir / "backups"

        kwargs: dict[str, Any] = {
            "source": str(source),
            "dest": str(dest),
            "dry_run": True,
        }
        result = task.execute(**kwargs)  # type: ignore[arg-type]

        assert result.status.is_finished
        if dest.exists():
            assert len(_find_archives(dest)) == 0


class TestBackupTaskWithSubdirs:
    """Testes de backup com subdiretórios."""

    def test_backup_nested_structure(self, temp_dir: Path):
        """Deve incluir estrutura aninhada."""
        from autotarefas.tasks.backup import BackupTask

        source = _make_tree(
            temp_dir / "source",
            {
                "sub1/file1.txt": "sub1 content",
                "sub2/deep/file2.txt": "deep content",
            },
        )
        dest = temp_dir / "backups"

        task = BackupTask()
        result = task.execute(source=str(source), dest=str(dest))

        assert result.is_success

        archives = _find_archives(dest)
        assert len(archives) == 1

        members = _list_archive_members(archives[0])
        assert len(members) >= 2


# =============================================================================
# Testes de RestoreTask
# =============================================================================


class TestRestoreTask:
    """Testes da classe RestoreTask."""

    def test_restore_task_metadata(self):
        """Task deve ter nome e descrição."""
        from autotarefas.tasks.backup import RestoreTask

        task = RestoreTask()
        assert task.name == "restore"
        assert task.description

    def test_restore_zip_backup(self, temp_dir: Path):
        """Deve restaurar backup ZIP."""
        from autotarefas.tasks.backup import BackupTask, RestoreTask

        source = _make_tree(temp_dir / "source", {"original.txt": "original content"})
        backup_dir = temp_dir / "backups"

        backup_task = BackupTask()
        backup_result = backup_task.execute(
            source=str(source), dest=str(backup_dir), compression="zip"
        )
        assert backup_result.is_success

        zip_files = list(backup_dir.glob("*.zip"))
        assert len(zip_files) == 1

        restore_dir = temp_dir / "restored"
        restore_task = RestoreTask()
        restore_result = restore_task.execute(
            backup_path=str(zip_files[0]), dest=str(restore_dir)
        )

        assert restore_result.is_success

        restored = list(restore_dir.rglob("original.txt"))
        assert restored, "original.txt não foi restaurado"
        assert restored[0].read_text(encoding="utf-8") == "original content"


# =============================================================================
# Edge Cases
# =============================================================================


class TestBackupEdgeCases:
    """Testes de casos extremos."""

    def test_backup_empty_directory(self, temp_dir: Path):
        """Deve tratar diretório vazio."""
        from autotarefas.tasks.backup import BackupTask

        source = temp_dir / "empty"
        source.mkdir()
        dest = temp_dir / "backups"

        task = BackupTask()
        result = task.execute(source=str(source), dest=str(dest))

        assert result.status.is_finished

    def test_backup_single_file(self, temp_dir: Path):
        """Deve fazer backup de arquivo único."""
        from autotarefas.tasks.backup import BackupTask

        source = temp_dir / "single.txt"
        source.write_text("single file content", encoding="utf-8")
        dest = temp_dir / "backups"

        task = BackupTask()
        result = task.execute(source=str(source), dest=str(dest))

        assert result.status.is_finished

    def test_backup_special_characters(self, temp_dir: Path):
        """Deve tratar nomes com caracteres especiais."""
        from autotarefas.tasks.backup import BackupTask

        source = temp_dir / "source"
        source.mkdir()
        (source / "arquivo com espaços.txt").write_text("content", encoding="utf-8")
        (source / "acentuação.txt").write_text("conteúdo", encoding="utf-8")

        dest = temp_dir / "backups"

        task = BackupTask()
        result = task.execute(source=str(source), dest=str(dest))

        assert result.is_success

    def test_backup_large_file(self, temp_dir: Path, large_file: Path):
        """Deve fazer backup de arquivo grande."""
        from autotarefas.tasks.backup import BackupTask

        dest = temp_dir / "backups"

        task = BackupTask()
        result = task.execute(source=str(large_file), dest=str(dest))

        assert result.is_success

    def test_backup_symlinks(self, temp_dir: Path):
        """Deve tratar symlinks corretamente (podem ser ignorados no backup)."""
        from autotarefas.tasks.backup import BackupTask

        source = temp_dir / "source"
        source.mkdir()

        target = source / "target.txt"
        target.write_text("target content", encoding="utf-8")

        link = source / "link.txt"
        try:
            os.symlink(target, link)
        except OSError:
            pytest.skip("Symlinks não suportados neste ambiente")

        dest = temp_dir / "backups"

        task = BackupTask()
        result = task.execute(source=str(source), dest=str(dest))

        assert result.status.is_finished
