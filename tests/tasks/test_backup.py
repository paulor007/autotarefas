"""Testes para autotarefas.tasks.backup."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from autotarefas.core.base import TaskStatus
from autotarefas.tasks.backup import BackupTask

# ============================================================
# Helpers
# ============================================================


def _criar_estrutura(base: Path, files: dict[str, str]) -> None:
    """
    Cria arquivos/pastas a partir de um dict {path: conteudo}.

    Exemplo:
        _criar_estrutura(tmp_path, {
            "src/main.py": "print('oi')",
            "README.md": "# Doc",
            "__pycache__/cache.pyc": "binario",
        })
    """
    for relative_path, content in files.items():
        full_path = base / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")


def _zip_namelist(zip_path: Path) -> list[str]:
    """Retorna lista de arcnames dentro do ZIP."""
    with zipfile.ZipFile(zip_path) as zf:
        return zf.namelist()


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def projeto_simples(tmp_path: Path) -> Path:
    """Pasta com estrutura simples (sem nada pra excluir por default)."""
    src = tmp_path / "projeto"
    _criar_estrutura(
        src,
        {
            "main.py": "print('hello')",
            "README.md": "# Projeto",
            "src/app.py": "# app",
        },
    )
    return src


@pytest.fixture
def projeto_com_excludes(tmp_path: Path) -> Path:
    """Pasta com arquivos que devem ser excluidos pelos defaults."""
    src = tmp_path / "projeto"
    _criar_estrutura(
        src,
        {
            "main.py": "code",
            "README.md": "doc",
            "__pycache__/main.cpython-312.pyc": "binary",
            "src/__pycache__/app.cpython-312.pyc": "binary",
            ".git/config": "git config",
            "node_modules/lib/index.js": "code",
            ".mypy_cache/data.json": "{}",
        },
    )
    return src


# ============================================================
# Tests: Backup basico (caminho feliz)
# ============================================================


class TestBackupTaskBasico:
    """Cenarios basicos de sucesso."""

    def test_backup_pasta_simples_sucesso(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Backup de pasta simples retorna SUCCESS."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(sources=[projeto_simples], destination=dest)
        result = task.run()

        assert result.is_success
        assert dest.exists()

    def test_backup_inclui_arquivos_esperados(self, tmp_path: Path, projeto_simples: Path) -> None:
        """ZIP contem os 3 arquivos do projeto."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(sources=[projeto_simples], destination=dest)
        result = task.run()

        assert result.data["file_count"] == 3

    def test_backup_arquivo_individual(self, tmp_path: Path) -> None:
        """Backup de um arquivo (nao pasta) funciona."""
        # Cria um arquivo solto
        single_file = tmp_path / "documento.txt"
        single_file.write_text("conteudo", encoding="utf-8")

        dest = tmp_path / "backup.zip"
        task = BackupTask(sources=[single_file], destination=dest)
        result = task.run()

        assert result.is_success
        assert result.data["file_count"] == 1

    def test_backup_multiplas_sources(self, tmp_path: Path) -> None:
        """Backup combinando multiplas pastas."""
        # Cria duas pastas
        pasta1 = tmp_path / "p1"
        pasta2 = tmp_path / "p2"
        _criar_estrutura(pasta1, {"a.txt": "1"})
        _criar_estrutura(pasta2, {"b.txt": "2"})

        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[pasta1, pasta2],
            destination=dest,
        )
        result = task.run()

        assert result.is_success
        assert result.data["file_count"] == 2

    def test_result_inclui_metadados(self, tmp_path: Path, projeto_simples: Path) -> None:
        """result.data tem todos os campos esperados."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_simples], destination=dest).run()

        assert "destination" in result.data
        assert "file_count" in result.data
        assert "skipped_count" in result.data
        assert "size_bytes" in result.data
        assert "sha256" in result.data

    def test_rows_affected_igual_file_count(self, tmp_path: Path, projeto_simples: Path) -> None:
        """rows_affected do TaskResult bate com file_count."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_simples], destination=dest).run()

        assert result.rows_affected == result.data["file_count"]

    def test_destination_pasta_pai_criada(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Cria diretorio pai do destination se nao existir."""
        dest = tmp_path / "subpasta" / "outra" / "backup.zip"
        task = BackupTask(sources=[projeto_simples], destination=dest)
        result = task.run()

        assert result.is_success
        assert dest.exists()


# ============================================================
# Tests: Excludes
# ============================================================


class TestBackupTaskExcludes:
    """Testes de exclusao de arquivos."""

    def test_default_excludes_remove_pycache(
        self, tmp_path: Path, projeto_com_excludes: Path
    ) -> None:
        """__pycache__ e excluido por padrao."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(sources=[projeto_com_excludes], destination=dest)
        task.run()

        namelist = _zip_namelist(dest)
        assert not any("__pycache__" in name for name in namelist)
        assert not any(name.endswith(".pyc") for name in namelist)

    def test_default_excludes_remove_git(self, tmp_path: Path, projeto_com_excludes: Path) -> None:
        """.git e excluido por padrao."""
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_com_excludes], destination=dest).run()

        namelist = _zip_namelist(dest)
        assert not any(".git" in name for name in namelist)

    def test_default_excludes_remove_node_modules(
        self, tmp_path: Path, projeto_com_excludes: Path
    ) -> None:
        """node_modules e excluido por padrao."""
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_com_excludes], destination=dest).run()

        namelist = _zip_namelist(dest)
        assert not any("node_modules" in name for name in namelist)

    def test_apenas_arquivos_uteis_no_zip(self, tmp_path: Path, projeto_com_excludes: Path) -> None:
        """Apos defaults, sobram apenas main.py e README.md."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_com_excludes], destination=dest).run()

        # main.py + README.md = 2 arquivos
        assert result.data["file_count"] == 2

    def test_skipped_count_correto(self, tmp_path: Path, projeto_com_excludes: Path) -> None:
        """Conta corretamente os arquivos excluidos."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_com_excludes], destination=dest).run()

        # 5 excluidos: 2 .pyc + .git/config + node_modules/lib/index.js + .mypy_cache/data.json
        assert result.data["skipped_count"] == 5

    def test_exclude_pattern_customizado(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Pode passar excludes adicionais via construtor."""
        # Cria um .log na pasta
        (projeto_simples / "debug.log").write_text("logs", encoding="utf-8")

        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_simples],
            destination=dest,
            exclude_patterns=["*.log"],
        )
        result = task.run()

        namelist = _zip_namelist(dest)
        assert not any(name.endswith(".log") for name in namelist)
        # Os outros 3 arquivos foram incluidos
        assert result.data["file_count"] == 3

    def test_no_default_excludes(self, tmp_path: Path, projeto_com_excludes: Path) -> None:
        """include_default_excludes=False mantem __pycache__."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_com_excludes],
            destination=dest,
            include_default_excludes=False,
        )
        result = task.run()

        # Tudo deve ter sido incluido (7 arquivos)
        assert result.data["file_count"] == 7
        assert result.data["skipped_count"] == 0

    def test_excludes_combinados(self, tmp_path: Path, projeto_com_excludes: Path) -> None:
        """Default + customizados aplicados juntos."""
        # Adiciona um arquivo .tmp
        (projeto_com_excludes / "scratch.tmp").write_text("tmp", encoding="utf-8")

        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_com_excludes],
            destination=dest,
            exclude_patterns=["*.tmp"],
        )
        result = task.run()

        namelist = _zip_namelist(dest)
        # Nao deve ter .pyc (default) nem .tmp (custom)
        assert not any(name.endswith(".pyc") for name in namelist)
        assert not any(name.endswith(".tmp") for name in namelist)
        # Sobram main.py + README.md
        assert result.data["file_count"] == 2


# ============================================================
# Tests: Validacao de input
# ============================================================


class TestBackupTaskValidacao:
    """Validacao de argumentos."""

    def test_source_inexistente_levanta(self, tmp_path: Path) -> None:
        """Source inexistente -> TaskResult de FAILURE."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[tmp_path / "nao_existe"],
            destination=dest,
        )
        result = task.run()

        # BaseTask captura AutoTarefasError e retorna FAILURE
        assert result.is_failure
        assert "nao encontrado" in (result.error_message or "")

    def test_multiplas_sources_uma_inexistente(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Se UMA source nao existe, a task falha (atomico)."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_simples, tmp_path / "fake"],
            destination=dest,
        )
        result = task.run()

        assert result.is_failure
        # ZIP nao deve ter sido criado
        assert not dest.exists()


# ============================================================
# Tests: Dry-run
# ============================================================


class TestBackupTaskDryRun:
    """Testes do modo dry-run."""

    def test_dry_run_nao_cria_zip(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Dry-run nao cria arquivo."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_simples],
            destination=dest,
            dry_run=True,
        )
        task.run()

        assert not dest.exists()

    def test_dry_run_status_dry_run(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Status retornado e DRY_RUN."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_simples],
            destination=dest,
            dry_run=True,
        )
        result = task.run()

        assert result.status == TaskStatus.DRY_RUN

    def test_dry_run_inclui_files_preview(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Dry-run inclui preview dos arquivos no data."""
        dest = tmp_path / "backup.zip"
        task = BackupTask(
            sources=[projeto_simples],
            destination=dest,
            dry_run=True,
        )
        result = task.run()

        assert "files_preview" in result.data
        assert len(result.data["files_preview"]) > 0

    def test_dry_run_conta_arquivos_corretamente(
        self, tmp_path: Path, projeto_simples: Path
    ) -> None:
        """Dry-run reporta file_count correto."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(
            sources=[projeto_simples],
            destination=dest,
            dry_run=True,
        ).run()

        # projeto_simples tem 3 arquivos
        assert result.data["file_count"] == 3


# ============================================================
# Tests: SHA-256
# ============================================================


class TestBackupTaskHash:
    """Testes do hash SHA-256."""

    def test_sha256_presente_no_data(self, tmp_path: Path, projeto_simples: Path) -> None:
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_simples], destination=dest).run()

        assert "sha256" in result.data
        assert result.data["sha256"]  # nao vazio

    def test_sha256_tem_64_caracteres_hex(self, tmp_path: Path, projeto_simples: Path) -> None:
        """SHA-256 em hex tem exatamente 64 chars (0-9a-f)."""
        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[projeto_simples], destination=dest).run()

        sha = result.data["sha256"]
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)


# ============================================================
# Tests: Conteudo do ZIP
# ============================================================


class TestBackupTaskZipContent:
    """Verificacoes da estrutura interna do ZIP."""

    def test_zip_e_arquivo_zip_valido(self, tmp_path: Path, projeto_simples: Path) -> None:
        """Arquivo gerado e um ZIP valido (parseavel)."""
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_simples], destination=dest).run()

        # zipfile consegue abrir sem erro
        with zipfile.ZipFile(dest) as zf:
            assert zf.testzip() is None  # integridade OK

    def test_arcname_inclui_nome_da_pasta_source(
        self, tmp_path: Path, projeto_simples: Path
    ) -> None:
        """Arcname comeca com nome da pasta source (preserva estrutura)."""
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_simples], destination=dest).run()

        namelist = _zip_namelist(dest)
        # Todos os arcnames devem comecar com "projeto/"
        assert all(name.startswith("projeto/") for name in namelist)

    def test_arcname_preserva_subpastas(self, tmp_path: Path, projeto_simples: Path) -> None:
        """src/app.py preserva o sub-path src/."""
        dest = tmp_path / "backup.zip"
        BackupTask(sources=[projeto_simples], destination=dest).run()

        namelist = _zip_namelist(dest)
        assert any("projeto/src/app.py" in name for name in namelist)

    def test_arquivo_individual_arcname_e_nome(self, tmp_path: Path) -> None:
        """Quando source eh arquivo, arcname e so o nome dele."""
        single_file = tmp_path / "doc.txt"
        single_file.write_text("oi", encoding="utf-8")

        dest = tmp_path / "backup.zip"
        BackupTask(sources=[single_file], destination=dest).run()

        namelist = _zip_namelist(dest)
        assert namelist == ["doc.txt"]


# ============================================================
# Tests: ZIP vazio (SKIPPED)
# ============================================================


class TestBackupTaskVazio:
    """Cenarios em que nao ha arquivos pra fazer backup."""

    def test_pasta_vazia_retorna_skipped(self, tmp_path: Path) -> None:
        """Pasta sem arquivos -> status SKIPPED."""
        pasta_vazia = tmp_path / "vazia"
        pasta_vazia.mkdir()

        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[pasta_vazia], destination=dest).run()

        assert result.status == TaskStatus.SKIPPED
        # ZIP nao deve ter sido criado
        assert not dest.exists()

    def test_tudo_excluido_retorna_skipped(self, tmp_path: Path) -> None:
        """Se TUDO for excluido, retorna SKIPPED."""
        src = tmp_path / "projeto"
        _criar_estrutura(
            src,
            {
                "__pycache__/cache.pyc": "binary",
                ".git/config": "git",
            },
        )

        dest = tmp_path / "backup.zip"
        result = BackupTask(sources=[src], destination=dest).run()

        assert result.status == TaskStatus.SKIPPED


# ============================================================
# Tests: Atributos da classe
# ============================================================


class TestBackupTaskAtributos:
    """Testes dos atributos de classe."""

    def test_name(self) -> None:
        assert BackupTask.name == "backup"

    def test_description(self) -> None:
        assert BackupTask.description

    def test_default_excludes_inclui_pycache(self) -> None:
        assert "__pycache__" in BackupTask.DEFAULT_EXCLUDES

    def test_default_excludes_inclui_git(self) -> None:
        assert ".git" in BackupTask.DEFAULT_EXCLUDES

    def test_default_excludes_inclui_node_modules(self) -> None:
        assert "node_modules" in BackupTask.DEFAULT_EXCLUDES

    def test_default_excludes_e_tupla(self) -> None:
        """DEFAULT_EXCLUDES deve ser imutavel (tupla)."""
        assert isinstance(BackupTask.DEFAULT_EXCLUDES, tuple)


# ============================================================
# Testes de seguranca
# ============================================================


class TestBackupTaskSeguranca:
    """Validacoes de seguranca aplicadas em construtor."""

    def test_destination_com_char_proibido_falha(
        self, tmp_path: Path, projeto_simples: Path
    ) -> None:
        """destination com '|' (proibido no Windows) e rejeitado."""
        from autotarefas.core.exceptions import ValidationError

        dest_ruim = tmp_path / "backup|ruim.zip"

        with pytest.raises(ValidationError, match="invalido"):
            BackupTask(
                sources=[projeto_simples],
                destination=dest_ruim,
            )

    def test_destination_com_nul_byte_falha(self, tmp_path: Path, projeto_simples: Path) -> None:
        """destination com NUL byte e rejeitado."""
        from autotarefas.core.exceptions import ValidationError

        # Path com NUL embutido no nome
        dest_ruim = tmp_path / "backup\x00.zip"

        with pytest.raises(ValidationError, match="invalido"):
            BackupTask(
                sources=[projeto_simples],
                destination=dest_ruim,
            )
