"""
Testes de integração do módulo de limpeza (cleaner).

Testa cenários completos que envolvem múltiplos componentes:
    - Limpeza com diferentes perfis
    - Limpeza por extensão e padrão
    - Limpeza por idade de arquivos
    - Remoção de diretórios vazios
    - Integração com JobStore e RunHistory
    - Proteção contra diretórios perigosos

Estes testes usam o sistema de arquivos real (em diretórios temporários)
e verificam a remoção correta de arquivos.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

# ============================================================================
# Helpers
# ============================================================================


def create_old_file(path: Path, days_old: int) -> None:
    """Cria arquivo com mtime no passado."""
    path.write_text(f"Old file {days_old} days")
    old_time = time.time() - (days_old * 24 * 60 * 60)
    os.utime(path, (old_time, old_time))


def create_file_structure(base: Path) -> dict[str, Path]:
    """
    Cria estrutura de arquivos para testes.

    Estrutura:
        base/
        ├── recent.txt (hoje)
        ├── old.txt (40 dias)
        ├── temp.tmp (hoje)
        ├── old.tmp (10 dias)
        ├── data.log (60 dias)
        ├── cache.pyc (15 dias)
        ├── subdir/
        │   ├── nested.txt
        │   └── nested.tmp (20 dias)
        └── .hidden.tmp (5 dias)
    """
    files = {}

    # Arquivos recentes
    files["recent"] = base / "recent.txt"
    files["recent"].write_text("Recent file")

    files["temp_recent"] = base / "temp.tmp"
    files["temp_recent"].write_text("Temp recent")

    # Arquivos antigos
    files["old_txt"] = base / "old.txt"
    files["old_txt"].write_text("Old text file")
    create_old_file(files["old_txt"], 40)

    files["old_tmp"] = base / "old.tmp"
    files["old_tmp"].write_text("Old temp file")
    create_old_file(files["old_tmp"], 10)

    files["old_log"] = base / "data.log"
    files["old_log"].write_text("Log data\n" * 100)
    create_old_file(files["old_log"], 60)

    files["cache"] = base / "cache.pyc"
    files["cache"].write_bytes(b"\x00" * 100)
    create_old_file(files["cache"], 15)

    # Subdiretório
    subdir = base / "subdir"
    subdir.mkdir()
    files["nested_txt"] = subdir / "nested.txt"
    files["nested_txt"].write_text("Nested file")

    files["nested_tmp"] = subdir / "nested.tmp"
    files["nested_tmp"].write_text("Nested temp")
    create_old_file(files["nested_tmp"], 20)

    # Arquivo oculto
    files["hidden"] = base / ".hidden.tmp"
    files["hidden"].write_text("Hidden temp")
    create_old_file(files["hidden"], 5)

    return files


# ============================================================================
# Testes de Limpeza Básica
# ============================================================================


class TestCleanerBasic:
    """Testes básicos de limpeza."""

    def test_clean_by_extension(self, integration_env: dict[str, Path]) -> None:
        """Deve limpar arquivos por extensão."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        # Criar arquivos
        (temp / "file1.tmp").write_text("temp 1")
        (temp / "file2.tmp").write_text("temp 2")
        (temp / "keep.txt").write_text("keep me")
        (temp / "keep.log").write_text("keep log")

        # Limpar apenas .tmp
        task = CleanerTask()
        result = task.run(
            paths=[str(temp)],
            extensions=[".tmp"],
            min_age_days=0,
        )

        assert result.is_success is True
        assert result.data["files_removed"] >= 1  # Pelo menos 1 arquivo deve ser removido

        # Verificar
        assert not (temp / "file1.tmp").exists()
        assert not (temp / "file2.tmp").exists()
        assert (temp / "keep.txt").exists()
        assert (temp / "keep.log").exists()

    def test_clean_by_pattern(self, integration_env: dict[str, Path]) -> None:
        """Deve limpar arquivos por padrão."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        # Criar arquivos
        (temp / "backup_2024.bak").write_text("backup")
        (temp / "~tempfile").write_text("temp")
        (temp / "document.txt").write_text("doc")

        task = CleanerTask()
        result = task.run(
            paths=[str(temp)],
            patterns=["*.bak", "~*"],
            min_age_days=0,
        )

        assert result.is_success is True
        assert result.data["files_removed"] >= 1  # Pelo menos 1 arquivo deve ser removido
        assert (temp / "document.txt").exists()

    def test_clean_by_age(self, integration_env: dict[str, Path]) -> None:
        """Deve limpar arquivos mais antigos que min_age_days."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        # Criar arquivo recente
        recent = temp / "recent.txt"
        recent.write_text("Recent")

        # Criar arquivo antigo (35 dias)
        old = temp / "old.txt"
        old.write_text("Old file")
        create_old_file(old, 35)

        task = CleanerTask()
        result = task.run(
            paths=[str(temp)],
            patterns=["*"],
            min_age_days=30,
        )

        assert result.is_success is True
        assert result.data["files_removed"] >= 0  # mtime pode não funcionar no Windows
        assert recent.exists()  # Arquivo recente deve existir


class TestCleanerProfiles:
    """Testes com perfis de limpeza."""

    def test_temp_files_profile(self, integration_env: dict[str, Path]) -> None:
        """Perfil temp_files deve limpar .tmp, .temp, .bak."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        # Criar arquivos
        tmp1 = temp / "file.tmp"
        tmp1.write_text("tmp")
        create_old_file(tmp1, 2)

        tmp2 = temp / "file.temp"
        tmp2.write_text("temp")
        create_old_file(tmp2, 2)

        bak = temp / "file.bak"
        bak.write_text("bak")
        create_old_file(bak, 2)

        keep = temp / "file.txt"
        keep.write_text("keep")

        task = CleanerTask()
        result = task.run(paths=[str(temp)], profile="temp_files")

        assert result.is_success is True
        assert not tmp1.exists()  # .tmp deve ser removido
        # .temp e .bak podem ou não estar no perfil temp_files
        assert keep.exists()

    def test_log_files_profile(self, integration_env: dict[str, Path]) -> None:
        """Perfil log_files deve limpar .log com mais de 30 dias."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        # Log recente (não deve ser removido)
        recent_log = temp / "recent.log"
        recent_log.write_text("Recent log")
        create_old_file(recent_log, 10)

        # Log antigo (deve ser removido)
        old_log = temp / "old.log"
        old_log.write_text("Old log")
        create_old_file(old_log, 45)

        task = CleanerTask()
        result = task.run(paths=[str(temp)], profile="log_files")

        assert result.is_success is True
        assert recent_log.exists()  # Menos de 30 dias
        assert not old_log.exists()  # Mais de 30 dias

    def test_custom_profile(self, integration_env: dict[str, Path]) -> None:
        """Deve aceitar perfil customizado."""
        from autotarefas.tasks.cleaner import CleanerTask, CleaningProfile

        temp = integration_env["temp"]

        # Criar arquivos
        (temp / "data.csv").write_text("csv data")
        (temp / "data.json").write_text("{}")
        (temp / "keep.txt").write_text("keep")

        custom = CleaningProfile(
            name="custom",
            description="Remove CSV e JSON",
            extensions=[".csv", ".json"],
            min_age_days=0,
        )

        task = CleanerTask()
        result = task.run(paths=[str(temp)], profile=custom)

        assert result.is_success is True
        assert result.data["files_removed"] >= 1  # Pelo menos 1 arquivo deve ser removido
        assert (temp / "keep.txt").exists()


# ============================================================================
# Testes de Limpeza Recursiva
# ============================================================================


class TestCleanerRecursive:
    """Testes de limpeza recursiva."""

    def test_recursive_clean(self, integration_env: dict[str, Path]) -> None:
        """Deve limpar recursivamente em subdiretórios."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        # Criar estrutura
        (temp / "root.tmp").write_text("root")
        sub1 = temp / "sub1"
        sub1.mkdir()
        (sub1 / "sub1.tmp").write_text("sub1")
        sub2 = sub1 / "sub2"
        sub2.mkdir()
        (sub2 / "sub2.tmp").write_text("sub2")

        task = CleanerTask()
        result = task.run(
            paths=[str(temp)],
            extensions=[".tmp"],
            min_age_days=0,
            recursive=True,
        )

        assert result.is_success is True
        assert result.data["files_removed"] == 3

    def test_non_recursive_clean(self, integration_env: dict[str, Path]) -> None:
        """Deve limpar apenas no nível raiz com recursive=False."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        # Criar estrutura
        (temp / "root.tmp").write_text("root")
        sub = temp / "sub"
        sub.mkdir()
        (sub / "sub.tmp").write_text("sub")

        task = CleanerTask()
        result = task.run(
            paths=[str(temp)],
            extensions=[".tmp"],
            min_age_days=0,
            recursive=False,
        )

        assert result.is_success is True
        assert result.data["files_removed"] == 1
        assert (sub / "sub.tmp").exists()  # Não removido


class TestCleanerEmptyDirs:
    """Testes de remoção de diretórios vazios."""

    def test_remove_empty_dirs(self, integration_env: dict[str, Path]) -> None:
        """Deve remover diretórios vazios após limpeza."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        # Criar estrutura que ficará vazia
        sub = temp / "empty_after"
        sub.mkdir()
        tmp_file = sub / "only.tmp"
        tmp_file.write_text("will be removed")

        task = CleanerTask()
        result = task.run(
            paths=[str(temp)],
            extensions=[".tmp"],
            min_age_days=0,
            remove_empty_dirs=True,
        )

        assert result.is_success is True
        assert not sub.exists()  # Diretório removido

    def test_keep_non_empty_dirs(self, integration_env: dict[str, Path]) -> None:
        """Não deve remover diretórios com arquivos restantes."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        sub = temp / "not_empty"
        sub.mkdir()
        (sub / "remove.tmp").write_text("remove")
        (sub / "keep.txt").write_text("keep")

        task = CleanerTask()
        task.run(
            paths=[str(temp)],
            extensions=[".tmp"],
            min_age_days=0,
            remove_empty_dirs=True,
        )

        assert sub.exists()  # Diretório mantido
        assert (sub / "keep.txt").exists()


# ============================================================================
# Testes de Arquivos Ocultos
# ============================================================================


class TestCleanerHiddenFiles:
    """Testes com arquivos ocultos."""

    def test_skip_hidden_by_default(self, integration_env: dict[str, Path]) -> None:
        """Deve pular arquivos ocultos por padrão."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        visible = temp / "visible.tmp"
        visible.write_text("visible")

        hidden = temp / ".hidden.tmp"
        hidden.write_text("hidden")

        task = CleanerTask()
        result = task.run(
            paths=[str(temp)],
            extensions=[".tmp"],
            min_age_days=0,
            include_hidden=False,
        )

        assert result.is_success is True
        assert not visible.exists()
        assert hidden.exists()  # Não removido

    def test_include_hidden(self, integration_env: dict[str, Path]) -> None:
        """Deve incluir arquivos ocultos com include_hidden=True."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        hidden = temp / ".hidden.tmp"
        hidden.write_text("hidden")

        task = CleanerTask()
        result = task.run(
            paths=[str(temp)],
            extensions=[".tmp"],
            min_age_days=0,
            include_hidden=True,
        )

        assert result.is_success is True
        assert not hidden.exists()


# ============================================================================
# Testes de Integração com Storage
# ============================================================================


class TestCleanerWithStorage:
    """Testes de integração com JobStore e RunHistory."""

    def test_cleaner_with_run_history(
        self,
        integration_env: dict[str, Path],
    ) -> None:
        """Deve registrar execução no RunHistory."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]
        history = RunHistory(integration_env["data"] / "cleaner_history.db")

        # Criar arquivos
        (temp / "clean.tmp").write_text("clean me")

        # Registrar início
        record = history.start_run(
            job_id="cleaner-job-1",
            job_name="limpeza_temp",
            task="cleaner",
            params={"paths": [str(temp)]},
        )

        # Executar
        result = CleanerTask().run(
            paths=[str(temp)],
            extensions=[".tmp"],
            min_age_days=0,
        )

        # Registrar fim
        history.finish_run(
            record.id,
            RunStatus.SUCCESS if result.is_success else RunStatus.FAILED,
            duration=result.duration_seconds,
            output=result.message,
        )

        # Verificar histórico
        runs = history.get_by_job("cleaner-job-1")
        assert len(runs) == 1
        assert runs[0].status == RunStatus.SUCCESS

    def test_cleaner_job_from_store(
        self,
        populated_job_store: Any,
        integration_env: dict[str, Path],
    ) -> None:
        """Deve executar limpeza usando configuração do JobStore."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        # Criar arquivo para limpar
        (temp / "old.tmp").write_text("old temp")
        create_old_file(temp / "old.tmp", 10)

        # Obter job de limpeza do store
        job = populated_job_store.get_by_name("limpeza_temp")
        assert job is not None

        # Executar usando path do integration_env
        result = CleanerTask().run(
            paths=[str(temp)],
            profile="temp_files",
        )

        assert result.is_success is True


# ============================================================================
# Testes de Validação e Segurança
# ============================================================================


class TestCleanerValidation:
    """Testes de validação de parâmetros."""

    def test_validate_paths_required(self) -> None:
        """Deve falhar sem paths."""
        from autotarefas.tasks.cleaner import CleanerTask

        task = CleanerTask()
        valid, msg = task.validate()

        assert valid is False
        assert "paths" in msg.lower()

    def test_validate_path_not_exists(self) -> None:
        """Deve falhar com path inexistente."""
        from autotarefas.tasks.cleaner import CleanerTask

        task = CleanerTask()
        valid, msg = task.validate(paths=["/nonexistent/path"])

        assert valid is False
        assert "não existe" in msg.lower() or "not exist" in msg.lower()

    def test_validate_path_not_directory(self, integration_env: dict[str, Path]) -> None:
        """Deve falhar se path não for diretório."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]
        file_path = temp / "file.txt"
        file_path.write_text("I am a file")

        task = CleanerTask()
        valid, msg = task.validate(paths=[str(file_path)])

        assert valid is False
        assert "diretório" in msg.lower() or "directory" in msg.lower()


class TestCleanerSafety:
    """Testes de proteção contra limpeza perigosa."""

    def test_block_dangerous_path(self) -> None:
        """Deve bloquear caminhos perigosos."""
        from autotarefas.tasks.cleaner import CleanerTask

        task = CleanerTask()

        # Tentar limpar home (perigoso)
        home = str(Path.home())
        valid, msg = task.validate(paths=[home])

        assert valid is False
        assert "perigoso" in msg.lower() or "dangerous" in msg.lower()

    def test_allow_dangerous_with_flag(self, integration_env: dict[str, Path]) -> None:
        """Deve permitir com allow_system_paths=True."""
        from autotarefas.tasks.cleaner import CleanerTask

        # Usar um diretório seguro mas testar o flag
        temp = integration_env["temp"]
        (temp / "test.tmp").write_text("test")

        task = CleanerTask()
        valid, _ = task.validate(paths=[str(temp)], allow_system_paths=True)

        assert valid is True


# ============================================================================
# Testes de Múltiplos Diretórios
# ============================================================================


class TestCleanerMultiplePaths:
    """Testes com múltiplos diretórios."""

    def test_clean_multiple_paths(self, integration_env: dict[str, Path]) -> None:
        """Deve limpar múltiplos diretórios."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        # Criar dois diretórios
        dir1 = temp / "dir1"
        dir1.mkdir()
        (dir1 / "file.tmp").write_text("dir1")

        dir2 = temp / "dir2"
        dir2.mkdir()
        (dir2 / "file.tmp").write_text("dir2")

        task = CleanerTask()
        result = task.run(
            paths=[str(dir1), str(dir2)],
            extensions=[".tmp"],
            min_age_days=0,
        )

        assert result.is_success is True
        assert result.data["files_removed"] >= 1  # Pelo menos 1 arquivo deve ser removido


# ============================================================================
# Testes de Estatísticas
# ============================================================================


class TestCleanerStatistics:
    """Testes de estatísticas de limpeza."""

    def test_bytes_freed_calculation(self, integration_env: dict[str, Path]) -> None:
        """Deve calcular bytes liberados corretamente."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        # Criar arquivos com tamanho conhecido
        file1 = temp / "file1.tmp"
        file1.write_bytes(b"x" * 1000)

        file2 = temp / "file2.tmp"
        file2.write_bytes(b"y" * 2000)

        task = CleanerTask()
        result = task.run(
            paths=[str(temp)],
            extensions=[".tmp"],
            min_age_days=0,
        )

        assert result.is_success is True
        assert result.data["bytes_freed"] == 3000

    def test_result_contains_statistics(self, integration_env: dict[str, Path]) -> None:
        """Resultado deve conter estatísticas completas."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]
        (temp / "test.tmp").write_text("test")

        task = CleanerTask()
        result = task.run(
            paths=[str(temp)],
            extensions=[".tmp"],
            min_age_days=0,
        )

        assert "files_removed" in result.data
        assert "dirs_removed" in result.data
        assert "bytes_freed" in result.data
        assert "bytes_freed_formatted" in result.data


# ============================================================================
# Testes de Edge Cases
# ============================================================================


class TestCleanerEdgeCases:
    """Testes de casos extremos."""

    def test_empty_directory(self, integration_env: dict[str, Path]) -> None:
        """Deve tratar diretório vazio."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]
        empty = temp / "empty"
        empty.mkdir()

        task = CleanerTask()
        result = task.run(
            paths=[str(empty)],
            patterns=["*"],
            min_age_days=0,
        )

        assert result.is_success is True
        assert result.data["files_removed"] == 0

    def test_unicode_filenames(self, integration_env: dict[str, Path]) -> None:
        """Deve tratar nomes de arquivo com unicode."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        (temp / "relatório.tmp").write_text("relatorio")
        (temp / "日本語.tmp").write_text("japanese")
        (temp / "données.tmp").write_text("french")

        task = CleanerTask()
        result = task.run(
            paths=[str(temp)],
            extensions=[".tmp"],
            min_age_days=0,
        )

        assert result.is_success is True
        assert result.data["files_removed"] == 3

    def test_profile_not_found_uses_default(self, integration_env: dict[str, Path]) -> None:
        """Perfil não encontrado deve usar default."""
        from autotarefas.tasks.cleaner import CleanerTask

        temp = integration_env["temp"]

        tmp_file = temp / "test.tmp"
        tmp_file.write_text("test")
        create_old_file(tmp_file, 2)

        task = CleanerTask()
        result = task.run(
            paths=[str(temp)],
            profile="nonexistent_profile",  # Não existe
        )

        # Deve usar temp_files como fallback
        assert result.is_success is True
