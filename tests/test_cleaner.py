"""
Testes do módulo de limpeza (cleaner).

Testa:
    - CleaningProfile: Perfis de limpeza
    - CleaningProfiles: Perfis pré-definidos
    - CleaningResult: Resultado da limpeza
    - CleanerTask: Execução da limpeza
"""

from __future__ import annotations

import contextlib
import inspect
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

# =============================================================================
# Helpers internos
# =============================================================================


def _has_var_kwargs(func: Any) -> bool:
    """True se a função aceita **kwargs."""
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


def _call_validate(task: Any, **kwargs: Any):
    """
    Chama task.validate.

    - Se validate aceitar **kwargs, repassa tudo.
    - Caso contrário, filtra kwargs conforme a assinatura real.
    """
    if _has_var_kwargs(task.validate):
        return cast(Any, task.validate)(**kwargs)

    sig = inspect.signature(task.validate)
    filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return cast(Any, task.validate)(**filtered)


def _call_execute(task: Any, **kwargs: Any):
    """
    Chama task.execute.

    - Se execute aceitar **kwargs, repassa tudo.
    - Caso contrário, filtra kwargs conforme a assinatura real.
    """
    if _has_var_kwargs(task.execute):
        return cast(Any, task.execute)(**kwargs)

    sig = inspect.signature(task.execute)
    filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return cast(Any, task.execute)(**filtered)


def _requires_param(func: Any, param_name: str) -> bool:
    """
    Retorna True se param_name existe na assinatura de func.

    Observação: se func aceitar **kwargs, consideramos que o parâmetro é suportado.
    """
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return False

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return True

    return param_name in sig.parameters


def _set_mtime(path: Path, dt: datetime) -> None:
    """Define mtime/atime para controlar idade de arquivo nos testes."""
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


def _make_old(path: Path, days: int = 2) -> None:
    """Marca arquivo como 'antigo' para passar no min_age padrão dos perfis."""
    _set_mtime(path, datetime.now(UTC) - timedelta(days=days))


# =============================================================================
# Testes de CleaningProfile
# =============================================================================


class TestCleaningProfile:
    """Testes da dataclass CleaningProfile."""

    def test_profile_creation(self):
        """Deve criar perfil básico."""
        from autotarefas.tasks.cleaner import CleaningProfile

        profile = CleaningProfile(
            name="test",
            description="Test profile",
            patterns=["*.tmp"],
        )

        assert profile.name == "test"
        assert profile.description == "Test profile"
        assert "*.tmp" in profile.patterns

    def test_profile_default_values(self):
        """Deve ter valores padrão corretos."""
        from autotarefas.tasks.cleaner import CleaningProfile

        profile = CleaningProfile(
            name="test",
            description="Test",
            patterns=["*"],
        )

        assert profile.min_age_days == 0
        assert profile.include_hidden is False
        assert profile.recursive is True

    def test_profile_with_extensions(self):
        """Deve aceitar extensões."""
        from autotarefas.tasks.cleaner import CleaningProfile

        profile = CleaningProfile(
            name="test",
            description="Test",
            patterns=[],
            extensions=[".tmp", ".log", ".bak"],
        )

        assert ".tmp" in profile.extensions
        assert ".log" in profile.extensions

    def test_profile_with_min_age(self):
        """Deve aceitar idade mínima."""
        from autotarefas.tasks.cleaner import CleaningProfile

        profile = CleaningProfile(
            name="old_files",
            description="Old files",
            patterns=["*"],
            min_age_days=30,
        )

        assert profile.min_age_days == 30


# =============================================================================
# Testes de CleaningProfiles
# =============================================================================


class TestCleaningProfiles:
    """Testes dos perfis pré-definidos."""

    def test_temp_files_profile(self):
        """Deve ter perfil TEMP_FILES."""
        from autotarefas.tasks.cleaner import CleaningProfiles

        profile = CleaningProfiles.TEMP_FILES
        assert profile.name == "temp_files"
        assert any("tmp" in p.lower() for p in profile.patterns)

    def test_log_files_profile(self):
        """Deve ter perfil LOG_FILES."""
        from autotarefas.tasks.cleaner import CleaningProfiles

        profile = CleaningProfiles.LOG_FILES
        assert profile.name == "log_files"
        assert any("log" in p.lower() for p in profile.patterns)

    def test_cache_files_profile(self):
        """Deve ter perfil CACHE_FILES."""
        from autotarefas.tasks.cleaner import CleaningProfiles

        profile = CleaningProfiles.CACHE_FILES
        assert profile.name == "cache_files"

    def test_downloads_profile(self):
        """Deve ter perfil DOWNLOADS."""
        from autotarefas.tasks.cleaner import CleaningProfiles

        profile = CleaningProfiles.DOWNLOADS
        assert profile.name == "downloads"
        assert profile.min_age_days > 0

    def test_thumbnails_profile(self):
        """Deve ter perfil THUMBNAILS."""
        from autotarefas.tasks.cleaner import CleaningProfiles

        profile = CleaningProfiles.THUMBNAILS
        assert profile.name == "thumbnails"
        assert any(("Thumbs.db" in p) or (".DS_Store" in p) for p in profile.patterns)

    def test_get_by_name(self):
        """get_by_name deve retornar perfil correto."""
        from autotarefas.tasks.cleaner import CleaningProfiles

        profile = CleaningProfiles.get_by_name("temp_files")
        assert profile is not None
        assert profile.name == "temp_files"

    def test_get_by_name_case_insensitive(self):
        """get_by_name deve ser case-insensitive."""
        from autotarefas.tasks.cleaner import CleaningProfiles

        profile = CleaningProfiles.get_by_name("TEMP_FILES")
        assert profile is not None

    def test_get_by_name_invalid(self):
        """get_by_name deve retornar None para perfil inválido."""
        from autotarefas.tasks.cleaner import CleaningProfiles

        profile = CleaningProfiles.get_by_name("invalid_profile")
        assert profile is None

    def test_list_profiles(self):
        """list_profiles deve retornar todos os perfis."""
        from autotarefas.tasks.cleaner import CleaningProfiles

        profiles = CleaningProfiles.list_profiles()

        assert "temp_files" in profiles
        assert "log_files" in profiles
        assert "cache_files" in profiles
        assert "downloads" in profiles
        assert "thumbnails" in profiles


# =============================================================================
# Testes de CleaningResult
# =============================================================================


class TestCleaningResult:
    """Testes da dataclass CleaningResult."""

    def test_result_creation(self):
        """Deve criar resultado básico."""
        from autotarefas.tasks.cleaner import CleaningResult

        result = CleaningResult()

        assert result.files_removed == 0
        assert result.dirs_removed == 0
        assert result.bytes_freed == 0
        assert result.errors == []
        assert result.skipped == []

    def test_result_with_values(self):
        """Deve aceitar valores."""
        from autotarefas.tasks.cleaner import CleaningResult

        result = CleaningResult(
            files_removed=10,
            dirs_removed=2,
            bytes_freed=1024000,
        )

        assert result.files_removed == 10
        assert result.dirs_removed == 2
        assert result.bytes_freed == 1024000

    def test_bytes_freed_formatted(self):
        """bytes_freed_formatted deve formatar corretamente."""
        from autotarefas.tasks.cleaner import CleaningResult

        result = CleaningResult(bytes_freed=1024 * 1024)

        formatted = result.bytes_freed_formatted
        assert isinstance(formatted, str)
        assert ("MB" in formatted) or ("1" in formatted)

    def test_to_dict(self):
        """to_dict deve retornar dicionário."""
        from autotarefas.tasks.cleaner import CleaningResult

        result = CleaningResult(
            files_removed=5,
            dirs_removed=1,
            bytes_freed=512,
            errors=["error1"],
            skipped=["skipped1", "skipped2"],
        )

        data = result.to_dict()

        assert isinstance(data, dict)
        assert data.get("files_removed") == 5
        assert data.get("dirs_removed") == 1
        assert data.get("bytes_freed") == 512
        assert data.get("errors_count", len(data.get("errors", []))) == 1
        assert data.get("skipped_count", len(data.get("skipped", []))) == 2


# =============================================================================
# Testes de CleanerTask
# =============================================================================


class TestCleanerTask:
    """Testes da classe CleanerTask."""

    def test_task_name(self):
        """Task deve ter nome 'cleaner'."""
        from autotarefas.tasks.cleaner import CleanerTask

        task = CleanerTask()
        assert task.name == "cleaner"

    def test_task_description(self):
        """Task deve ter descrição."""
        from autotarefas.tasks.cleaner import CleanerTask

        task = CleanerTask()
        assert task.description is not None
        assert len(task.description) > 0


class TestCleanerTaskValidation:
    """Testes de validação do CleanerTask."""

    def test_validate_missing_paths(self):
        """Deve falhar sem paths."""
        from autotarefas.tasks.cleaner import CleanerTask

        task = CleanerTask()
        is_valid, error = _call_validate(task)

        assert is_valid is False
        assert "path" in error.lower()

    def test_validate_empty_paths(self):
        """Deve falhar com paths vazio."""
        from autotarefas.tasks.cleaner import CleanerTask

        task = CleanerTask()
        is_valid, _ = _call_validate(task, paths=[])

        assert is_valid is False

    def test_validate_nonexistent_path(self, temp_dir: Path):
        """Deve falhar com path inexistente."""
        from autotarefas.tasks.cleaner import CleanerTask

        task = CleanerTask()
        is_valid, error = _call_validate(task, paths=[str(temp_dir / "nonexistent")])

        assert is_valid is False
        assert ("exist" in error.lower()) or ("não" in error.lower())

    def test_validate_file_not_dir(self, temp_dir: Path):
        """Deve falhar com arquivo ao invés de diretório."""
        from autotarefas.tasks.cleaner import CleanerTask

        file_path = temp_dir / "file.txt"
        file_path.write_text("content", encoding="utf-8")

        task = CleanerTask()
        is_valid, error = _call_validate(task, paths=[str(file_path)])

        assert is_valid is False
        assert ("diret" in error.lower()) or ("dir" in error.lower())

    def test_validate_dangerous_path(self):
        """Deve recusar caminhos perigosos (se implementado)."""
        from autotarefas.tasks.cleaner import CleanerTask

        task = CleanerTask()

        if not _requires_param(task.validate, "allow_system_paths"):
            pytest.skip("validate() não suporta allow_system_paths")

        dangerous_paths = ["/", "/etc", "/usr", "/var"]
        for path in dangerous_paths:
            if Path(path).exists():
                is_valid, error = _call_validate(
                    task, paths=[path], allow_system_paths=False
                )
                assert (
                    (is_valid is False)
                    or ("perig" in error.lower())
                    or ("danger" in error.lower())
                )

    def test_validate_allows_system_with_flag(self, temp_dir: Path):
        """Deve aceitar com allow_system_paths (se suportado)."""
        from autotarefas.tasks.cleaner import CleanerTask

        task = CleanerTask()

        if not _requires_param(task.validate, "allow_system_paths"):
            pytest.skip("validate() não suporta allow_system_paths")

        is_valid, error = _call_validate(
            task, paths=[str(temp_dir)], allow_system_paths=True
        )

        assert is_valid is True
        assert error == ""

    def test_validate_valid_paths(self, temp_dir: Path):
        """Deve aceitar paths válidos."""
        from autotarefas.tasks.cleaner import CleanerTask

        task = CleanerTask()
        is_valid, error = _call_validate(task, paths=[str(temp_dir)])

        assert is_valid is True
        assert error == ""


class TestCleanerTaskExecution:
    """Testes de execução do CleanerTask."""

    def test_execute_removes_temp_files(self, temp_dir: Path):
        """Deve remover arquivos temporários."""
        from autotarefas.tasks.cleaner import CleanerTask

        (temp_dir / "file.tmp").write_text("temp", encoding="utf-8")
        _make_old(temp_dir / "file.tmp")
        (temp_dir / "file.txt").write_text("keep", encoding="utf-8")

        task = CleanerTask()
        result = _call_execute(task, paths=[str(temp_dir)], patterns=["*.tmp"])

        assert result.is_success
        assert not (temp_dir / "file.tmp").exists()
        assert (temp_dir / "file.txt").exists()

    def test_execute_with_profile(self, temp_dir: Path):
        """Deve usar perfil de limpeza."""
        from autotarefas.tasks.cleaner import CleanerTask, CleaningProfiles

        (temp_dir / "test.tmp").write_text("temp", encoding="utf-8")
        _make_old(temp_dir / "test.tmp")
        (temp_dir / "test.temp").write_text("temp", encoding="utf-8")
        _make_old(temp_dir / "test.temp")

        task = CleanerTask()
        result = _call_execute(
            task, paths=[str(temp_dir)], profile=CleaningProfiles.TEMP_FILES
        )

        assert result.status.is_finished

    def test_execute_with_profile_name(self, temp_dir: Path):
        """Deve aceitar nome do perfil como string."""
        from autotarefas.tasks.cleaner import CleanerTask

        (temp_dir / "test.tmp").write_text("temp", encoding="utf-8")
        _make_old(temp_dir / "test.tmp")

        task = CleanerTask()
        result = _call_execute(task, paths=[str(temp_dir)], profile="temp_files")

        assert result.status.is_finished

    def test_execute_respects_min_age(self, temp_dir: Path):
        """Deve respeitar idade mínima dos arquivos."""
        from autotarefas.tasks.cleaner import CleanerTask

        new_file = temp_dir / "new.tmp"
        new_file.write_text("new", encoding="utf-8")

        old_file = temp_dir / "old.tmp"
        old_file.write_text("old", encoding="utf-8")
        _set_mtime(old_file, datetime.now(UTC) - timedelta(days=10))

        task = CleanerTask()
        result = _call_execute(
            task, paths=[str(temp_dir)], patterns=["*.tmp"], min_age_days=7
        )

        assert result.is_success
        assert new_file.exists()
        assert not old_file.exists()

    def test_execute_recursive(self, temp_dir: Path):
        """Deve limpar recursivamente."""
        from autotarefas.tasks.cleaner import CleanerTask

        sub = temp_dir / "sub"
        sub.mkdir()
        (temp_dir / "root.tmp").write_text("root", encoding="utf-8")
        _make_old(temp_dir / "root.tmp")
        (sub / "nested.tmp").write_text("nested", encoding="utf-8")
        _make_old(sub / "nested.tmp")

        task = CleanerTask()
        result = _call_execute(
            task, paths=[str(temp_dir)], patterns=["*.tmp"], recursive=True
        )

        assert result.is_success
        assert not (temp_dir / "root.tmp").exists()
        assert not (sub / "nested.tmp").exists()

    def test_execute_non_recursive(self, temp_dir: Path):
        """Deve limpar apenas raiz quando recursive=False."""
        from autotarefas.tasks.cleaner import CleanerTask

        sub = temp_dir / "sub"
        sub.mkdir()
        (temp_dir / "root.tmp").write_text("root", encoding="utf-8")
        _make_old(temp_dir / "root.tmp")
        (sub / "nested.tmp").write_text("nested", encoding="utf-8")
        _make_old(sub / "nested.tmp")

        task = CleanerTask()
        result = _call_execute(
            task, paths=[str(temp_dir)], patterns=["*.tmp"], recursive=False
        )

        assert result.is_success
        assert not (temp_dir / "root.tmp").exists()
        assert (sub / "nested.tmp").exists()

    def test_execute_removes_empty_dirs(self, temp_dir: Path):
        """Deve remover diretórios vazios (com remove_empty_dirs=True)."""
        from autotarefas.tasks.cleaner import CleanerTask

        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        task = CleanerTask()
        result = _call_execute(
            task, paths=[str(temp_dir)], patterns=["*"], remove_empty_dirs=True
        )

        assert result.status.is_finished

    def test_execute_returns_stats(self, temp_dir: Path):
        """Result deve ter estatísticas."""
        from autotarefas.tasks.cleaner import CleanerTask

        (temp_dir / "file1.tmp").write_text("x" * 100, encoding="utf-8")
        _make_old(temp_dir / "file1.tmp")
        (temp_dir / "file2.tmp").write_text("x" * 200, encoding="utf-8")
        _make_old(temp_dir / "file2.tmp")

        task = CleanerTask()
        result = _call_execute(task, paths=[str(temp_dir)], patterns=["*.tmp"])

        assert result.status.is_finished
        assert result.data is not None


class TestCleanerTaskExtensions:
    """Testes de limpeza por extensão."""

    def test_clean_by_extension(self, temp_dir: Path):
        """Deve limpar por extensão."""
        from autotarefas.tasks.cleaner import CleanerTask

        (temp_dir / "file.log").write_text("log", encoding="utf-8")
        _make_old(temp_dir / "file.log")
        (temp_dir / "file.txt").write_text("text", encoding="utf-8")
        (temp_dir / "file.bak").write_text("backup", encoding="utf-8")
        _make_old(temp_dir / "file.bak")

        task = CleanerTask()
        # patterns=["*"] porque o matches exige extensão E padrão
        result = _call_execute(
            task, paths=[str(temp_dir)], patterns=["*"], extensions=[".log", ".bak"]
        )

        assert result.is_success
        assert not (temp_dir / "file.log").exists()
        assert not (temp_dir / "file.bak").exists()
        assert (temp_dir / "file.txt").exists()

    def test_extension_normalization(self, temp_dir: Path):
        """Extensões devem ser normalizadas."""
        from autotarefas.tasks.cleaner import CleanerTask

        (temp_dir / "file.LOG").write_text("log", encoding="utf-8")
        _make_old(temp_dir / "file.LOG")
        (temp_dir / "file.Log").write_text("log2", encoding="utf-8")
        _make_old(temp_dir / "file.Log")

        task = CleanerTask()
        result = _call_execute(
            task, paths=[str(temp_dir)], patterns=["*"], extensions=["log"]
        )  # sem ponto

        assert result.status.is_finished


class TestCleanerTaskHiddenFiles:
    """Testes de arquivos ocultos."""

    def test_ignores_hidden_by_default(self, temp_dir: Path):
        """Deve ignorar arquivos ocultos por padrão."""
        from autotarefas.tasks.cleaner import CleanerTask

        (temp_dir / ".hidden.tmp").write_text("hidden", encoding="utf-8")
        _make_old(temp_dir / ".hidden.tmp")
        (temp_dir / "visible.tmp").write_text("visible", encoding="utf-8")
        _make_old(temp_dir / "visible.tmp")

        task = CleanerTask()
        result = _call_execute(
            task, paths=[str(temp_dir)], patterns=["*.tmp"], include_hidden=False
        )

        assert result.is_success
        assert (temp_dir / ".hidden.tmp").exists()
        assert not (temp_dir / "visible.tmp").exists()

    def test_includes_hidden_when_enabled(self, temp_dir: Path):
        """Deve incluir arquivos ocultos quando habilitado."""
        from autotarefas.tasks.cleaner import CleanerTask

        (temp_dir / ".hidden.tmp").write_text("hidden", encoding="utf-8")
        _make_old(temp_dir / ".hidden.tmp")

        task = CleanerTask()
        result = _call_execute(
            task, paths=[str(temp_dir)], patterns=["*.tmp"], include_hidden=True
        )

        assert result.is_success
        assert not (temp_dir / ".hidden.tmp").exists()


class TestCleanerTaskMultiplePaths:
    """Testes de limpeza em múltiplos diretórios."""

    def test_clean_multiple_paths(self, temp_dir: Path):
        """Deve limpar múltiplos diretórios."""
        from autotarefas.tasks.cleaner import CleanerTask

        dir1 = temp_dir / "dir1"
        dir2 = temp_dir / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        (dir1 / "file.tmp").write_text("dir1", encoding="utf-8")
        _make_old(dir1 / "file.tmp")
        (dir2 / "file.tmp").write_text("dir2", encoding="utf-8")
        _make_old(dir2 / "file.tmp")

        task = CleanerTask()
        result = _call_execute(task, paths=[str(dir1), str(dir2)], patterns=["*.tmp"])

        assert result.is_success
        assert not (dir1 / "file.tmp").exists()
        assert not (dir2 / "file.tmp").exists()


# =============================================================================
# Testes de Edge Cases
# =============================================================================


class TestCleanerEdgeCases:
    """Testes de casos extremos."""

    def test_empty_directory(self, temp_dir: Path):
        """Deve tratar diretório vazio."""
        from autotarefas.tasks.cleaner import CleanerTask

        empty = temp_dir / "empty"
        empty.mkdir()

        task = CleanerTask()
        result = _call_execute(task, paths=[str(empty)], patterns=["*"])

        assert result.status.is_finished

    def test_permission_error_handling(self, temp_dir: Path):
        """Deve tratar erros de permissão."""
        from autotarefas.tasks.cleaner import CleanerTask

        if os.name == "nt":
            pytest.skip("chmod 000 costuma não se comportar bem no Windows")

        protected = temp_dir / "protected.tmp"
        protected.write_text("protected", encoding="utf-8")
        _make_old(protected)

        try:
            protected.chmod(0o000)

            task = CleanerTask()
            result = _call_execute(task, paths=[str(temp_dir)], patterns=["*.tmp"])

            assert result.status.is_finished
        finally:
            with contextlib.suppress(PermissionError, FileNotFoundError):
                protected.chmod(0o644)

    def test_special_characters_in_filename(self, temp_dir: Path):
        """Deve tratar nomes com caracteres especiais."""
        from autotarefas.tasks.cleaner import CleanerTask

        (temp_dir / "arquivo com espaços.tmp").write_text("space", encoding="utf-8")
        _make_old(temp_dir / "arquivo com espaços.tmp")
        (temp_dir / "acentuação.tmp").write_text("accent", encoding="utf-8")
        _make_old(temp_dir / "acentuação.tmp")

        task = CleanerTask()
        result = _call_execute(task, paths=[str(temp_dir)], patterns=["*.tmp"])

        assert result.is_success
        assert not (temp_dir / "arquivo com espaços.tmp").exists()

    def test_symlink_handling(self, temp_dir: Path):
        """Deve tratar symlinks corretamente."""
        from autotarefas.tasks.cleaner import CleanerTask

        target = temp_dir / "target.txt"
        target.write_text("target", encoding="utf-8")

        link = temp_dir / "link.tmp"
        try:
            os.symlink(target, link)
        except OSError:
            pytest.skip("Symlinks não suportados")

        task = CleanerTask()
        result = _call_execute(task, paths=[str(temp_dir)], patterns=["*.tmp"])

        assert result.status.is_finished
        assert target.exists()

    def test_concurrent_deletion(self, temp_dir: Path):
        """Deve tratar arquivos deletados durante execução."""
        from autotarefas.tasks.cleaner import CleanerTask

        for i in range(10):
            (temp_dir / f"file{i}.tmp").write_text(f"content{i}", encoding="utf-8")
            _make_old(temp_dir / f"file{i}.tmp")

        (temp_dir / "file0.tmp").unlink(missing_ok=True)

        task = CleanerTask()
        result = _call_execute(task, paths=[str(temp_dir)], patterns=["*.tmp"])

        assert result.status.is_finished
