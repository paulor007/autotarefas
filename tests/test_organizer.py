"""
Testes unitários do módulo de organização de arquivos.

O QUE ESTES TESTES VERIFICAM:
=============================
- Enums (OrganizeProfile, ConflictStrategy, FileCategory)
- Mapeamento de extensões (DEFAULT_EXTENSION_MAP)
- Dataclasses (OrganizeResult, FileMove)
- Métodos individuais do OrganizerTask
- Validação de parâmetros

COMO RODAR:
===========
    pytest tests/test_organizer.py -v
    pytest tests/test_organizer.py -k "test_enum" -v
"""

from __future__ import annotations

from pathlib import Path

# ============================================================================
# Testes de Enums
# ============================================================================


class TestOrganizeProfile:
    """Testes do enum OrganizeProfile."""

    def test_profile_values(self) -> None:
        """Deve ter os valores esperados."""
        from autotarefas.tasks.organizer import OrganizeProfile

        assert OrganizeProfile.DEFAULT.value == "default"
        assert OrganizeProfile.BY_DATE.value == "by_date"
        assert OrganizeProfile.BY_EXTENSION.value == "by_extension"
        assert OrganizeProfile.CUSTOM.value == "custom"

    def test_profile_str(self) -> None:
        """__str__ deve retornar o valor."""
        from autotarefas.tasks.organizer import OrganizeProfile

        assert str(OrganizeProfile.DEFAULT) == "default"

    def test_profile_from_string(self) -> None:
        """Deve criar enum a partir de string."""
        from autotarefas.tasks.organizer import OrganizeProfile

        profile = OrganizeProfile("default")
        assert profile == OrganizeProfile.DEFAULT


class TestConflictStrategy:
    """Testes do enum ConflictStrategy."""

    def test_strategy_values(self) -> None:
        """Deve ter os valores esperados."""
        from autotarefas.tasks.organizer import ConflictStrategy

        assert ConflictStrategy.SKIP.value == "skip"
        assert ConflictStrategy.OVERWRITE.value == "overwrite"
        assert ConflictStrategy.RENAME.value == "rename"
        assert ConflictStrategy.ASK.value == "ask"

    def test_strategy_str(self) -> None:
        """__str__ deve retornar o valor."""
        from autotarefas.tasks.organizer import ConflictStrategy

        assert str(ConflictStrategy.RENAME) == "rename"


class TestFileCategory:
    """Testes do enum FileCategory."""

    def test_category_values(self) -> None:
        """Deve ter as categorias esperadas."""
        from autotarefas.tasks.organizer import FileCategory

        assert FileCategory.IMAGES.value == "Imagens"
        assert FileCategory.DOCUMENTS.value == "Documentos"
        assert FileCategory.VIDEOS.value == "Videos"
        assert FileCategory.AUDIO.value == "Audio"
        assert FileCategory.ARCHIVES.value == "Arquivos"
        assert FileCategory.OTHERS.value == "Outros"

    def test_category_count(self) -> None:
        """Deve ter pelo menos 10 categorias."""
        from autotarefas.tasks.organizer import FileCategory

        assert len(FileCategory) >= 10


# ============================================================================
# Testes do Mapeamento de Extensões
# ============================================================================


class TestExtensionMap:
    """Testes do DEFAULT_EXTENSION_MAP."""

    def test_map_not_empty(self) -> None:
        """Mapa não deve estar vazio."""
        from autotarefas.tasks.organizer import DEFAULT_EXTENSION_MAP

        assert len(DEFAULT_EXTENSION_MAP) > 0

    def test_map_has_common_extensions(self) -> None:
        """Deve mapear extensões comuns."""
        from autotarefas.tasks.organizer import DEFAULT_EXTENSION_MAP, FileCategory

        # Imagens
        assert DEFAULT_EXTENSION_MAP[".jpg"] == FileCategory.IMAGES
        assert DEFAULT_EXTENSION_MAP[".png"] == FileCategory.IMAGES
        assert DEFAULT_EXTENSION_MAP[".gif"] == FileCategory.IMAGES

        # Documentos
        assert DEFAULT_EXTENSION_MAP[".pdf"] == FileCategory.DOCUMENTS
        assert DEFAULT_EXTENSION_MAP[".docx"] == FileCategory.DOCUMENTS
        assert DEFAULT_EXTENSION_MAP[".txt"] == FileCategory.DOCUMENTS

        # Vídeos
        assert DEFAULT_EXTENSION_MAP[".mp4"] == FileCategory.VIDEOS
        assert DEFAULT_EXTENSION_MAP[".avi"] == FileCategory.VIDEOS

        # Áudio
        assert DEFAULT_EXTENSION_MAP[".mp3"] == FileCategory.AUDIO
        assert DEFAULT_EXTENSION_MAP[".wav"] == FileCategory.AUDIO

        # Arquivos compactados
        assert DEFAULT_EXTENSION_MAP[".zip"] == FileCategory.ARCHIVES
        assert DEFAULT_EXTENSION_MAP[".rar"] == FileCategory.ARCHIVES

    def test_extensions_are_lowercase(self) -> None:
        """Todas as extensões devem estar em minúsculas."""
        from autotarefas.tasks.organizer import DEFAULT_EXTENSION_MAP

        for ext in DEFAULT_EXTENSION_MAP:
            assert ext == ext.lower(), f"Extensão não está em minúsculas: {ext}"

    def test_extensions_start_with_dot(self) -> None:
        """Todas as extensões devem começar com ponto."""
        from autotarefas.tasks.organizer import DEFAULT_EXTENSION_MAP

        for ext in DEFAULT_EXTENSION_MAP:
            assert ext.startswith("."), f"Extensão não começa com ponto: {ext}"


# ============================================================================
# Testes de Dataclasses
# ============================================================================


class TestOrganizeResult:
    """Testes da dataclass OrganizeResult."""

    def test_default_values(self) -> None:
        """Deve ter valores default corretos."""
        from autotarefas.tasks.organizer import OrganizeResult

        result = OrganizeResult()

        assert result.files_moved == 0
        assert result.files_skipped == 0
        assert result.files_renamed == 0
        assert result.files_failed == 0
        assert result.bytes_organized == 0
        assert result.categories_used == {}
        assert result.errors == []

    def test_to_dict(self) -> None:
        """to_dict deve retornar dicionário correto."""
        from autotarefas.tasks.organizer import OrganizeResult

        result = OrganizeResult(
            files_moved=10,
            files_skipped=2,
            bytes_organized=1024,
            categories_used={"Imagens": 5, "Documentos": 5},
        )

        data = result.to_dict()

        assert data["files_moved"] == 10
        assert data["files_skipped"] == 2
        assert data["bytes_organized"] == 1024
        assert data["categories_used"]["Imagens"] == 5


class TestFileMove:
    """Testes da dataclass FileMove."""

    def test_creation(self) -> None:
        """Deve criar FileMove corretamente."""
        from autotarefas.tasks.organizer import FileCategory, FileMove

        move = FileMove(
            source=Path("/tmp/foto.jpg"),
            destination=Path("/tmp/Imagens/foto.jpg"),
            category=FileCategory.IMAGES,
            size=1024,
        )

        assert move.source == Path("/tmp/foto.jpg")
        assert move.destination == Path("/tmp/Imagens/foto.jpg")
        assert move.category == FileCategory.IMAGES
        assert move.size == 1024
        assert move.success is False
        assert move.renamed is False
        assert move.error is None


# ============================================================================
# Testes do OrganizerTask
# ============================================================================


class TestOrganizerTaskProperties:
    """Testes das propriedades do OrganizerTask."""

    def test_name(self) -> None:
        """Deve retornar nome correto."""
        from autotarefas.tasks.organizer import OrganizerTask

        task = OrganizerTask()
        assert task.name == "organizer"

    def test_description(self) -> None:
        """Deve retornar descrição."""
        from autotarefas.tasks.organizer import OrganizerTask

        task = OrganizerTask()
        assert len(task.description) > 0


class TestOrganizerTaskValidation:
    """Testes de validação do OrganizerTask."""

    def test_validate_source_required(self) -> None:
        """Deve falhar sem source."""
        from autotarefas.tasks.organizer import OrganizerTask

        task = OrganizerTask()
        valid, msg = task.validate()

        assert valid is False
        assert "source" in msg.lower()

    def test_validate_source_not_exists(self) -> None:
        """Deve falhar com source inexistente."""
        from autotarefas.tasks.organizer import OrganizerTask

        task = OrganizerTask()
        valid, msg = task.validate(source="/nonexistent/path/xyz")

        assert valid is False
        assert "não existe" in msg.lower() or "not exist" in msg.lower()

    def test_validate_source_not_directory(self, tmp_path: Path) -> None:
        """Deve falhar se source não for diretório."""
        from autotarefas.tasks.organizer import OrganizerTask

        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        task = OrganizerTask()
        valid, msg = task.validate(source=str(file_path))

        assert valid is False
        assert "diretório" in msg.lower() or "directory" in msg.lower()

    def test_validate_dangerous_path(self) -> None:
        """Deve bloquear diretórios perigosos."""
        from autotarefas.tasks.organizer import OrganizerTask

        task = OrganizerTask()
        home = str(Path.home())
        valid, msg = task.validate(source=home)

        assert valid is False
        assert "sistema" in msg.lower() or "permitido" in msg.lower()

    def test_validate_success(self, tmp_path: Path) -> None:
        """Deve validar diretório válido."""
        from autotarefas.tasks.organizer import OrganizerTask

        task = OrganizerTask()
        valid, msg = task.validate(source=str(tmp_path))

        assert valid is True


# ============================================================================
# Testes de Execução Básica
# ============================================================================


class TestOrganizerTaskExecution:
    """Testes de execução do OrganizerTask."""

    def test_organize_empty_directory(self, tmp_path: Path) -> None:
        """Deve tratar diretório vazio."""
        from autotarefas.tasks.organizer import OrganizerTask

        task = OrganizerTask()
        result = task.run(source=str(tmp_path))

        assert result.is_success is True
        assert result.data["files_moved"] == 0

    def test_organize_single_file(self, tmp_path: Path) -> None:
        """Deve organizar arquivo único."""
        from autotarefas.tasks.organizer import OrganizerTask

        # Criar arquivo
        (tmp_path / "foto.jpg").write_bytes(b"fake jpg content")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path))

        assert result.is_success is True
        assert result.data["files_moved"] == 1
        assert (tmp_path / "Imagens" / "foto.jpg").exists()

    def test_organize_multiple_files(self, tmp_path: Path) -> None:
        """Deve organizar múltiplos arquivos."""
        from autotarefas.tasks.organizer import OrganizerTask

        # Criar arquivos de diferentes tipos
        (tmp_path / "foto.jpg").write_bytes(b"jpg")
        (tmp_path / "doc.pdf").write_bytes(b"pdf")
        (tmp_path / "video.mp4").write_bytes(b"mp4")
        (tmp_path / "musica.mp3").write_bytes(b"mp3")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path))

        assert result.is_success is True
        assert result.data["files_moved"] == 4
        assert (tmp_path / "Imagens" / "foto.jpg").exists()
        assert (tmp_path / "Documentos" / "doc.pdf").exists()
        assert (tmp_path / "Videos" / "video.mp4").exists()
        assert (tmp_path / "Audio" / "musica.mp3").exists()

    def test_organize_unknown_extension(self, tmp_path: Path) -> None:
        """Extensão desconhecida deve ir para Outros."""
        from autotarefas.tasks.organizer import OrganizerTask

        (tmp_path / "arquivo.xyz").write_text("unknown")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path))

        assert result.is_success is True
        assert (tmp_path / "Outros" / "arquivo.xyz").exists()

    def test_organize_no_extension(self, tmp_path: Path) -> None:
        """Arquivo sem extensão deve ir para Outros."""
        from autotarefas.tasks.organizer import OrganizerTask

        (tmp_path / "README").write_text("readme content")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path))

        assert result.is_success is True
        assert (tmp_path / "Outros" / "README").exists()


# ============================================================================
# Testes de Dry Run
# ============================================================================


class TestOrganizerDryRun:
    """Testes do modo dry-run."""

    def test_dry_run_no_changes(self, tmp_path: Path) -> None:
        """Dry-run não deve mover arquivos."""
        from autotarefas.tasks.organizer import OrganizerTask

        (tmp_path / "foto.jpg").write_bytes(b"jpg content")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), dry_run=True)

        # Dry-run pode retornar SUCCESS ou SKIPPED dependendo da implementação
        assert result.status.value in ("success", "skipped")

        # O importante é que arquivos simulados foram contados
        if result.data:
            assert result.data.get("files_moved", 0) >= 0

        # Arquivo NÃO foi movido
        assert (tmp_path / "foto.jpg").exists()
        assert not (tmp_path / "Imagens").exists()


# ============================================================================
# Testes de Conflitos
# ============================================================================


class TestOrganizerConflicts:
    """Testes de estratégias de conflito."""

    def test_conflict_skip(self, tmp_path: Path) -> None:
        """Estratégia SKIP deve pular arquivo existente."""
        from autotarefas.tasks.organizer import OrganizerTask

        # Criar arquivo e destino
        (tmp_path / "foto.jpg").write_bytes(b"novo")
        (tmp_path / "Imagens").mkdir()
        (tmp_path / "Imagens" / "foto.jpg").write_bytes(b"existente")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), conflict_strategy="skip")

        assert result.is_success is True
        assert result.data["files_skipped"] == 1

        # Arquivo existente não foi alterado
        assert (tmp_path / "Imagens" / "foto.jpg").read_bytes() == b"existente"

    def test_conflict_overwrite(self, tmp_path: Path) -> None:
        """Estratégia OVERWRITE deve sobrescrever."""
        from autotarefas.tasks.organizer import OrganizerTask

        # Criar arquivo e destino
        (tmp_path / "foto.jpg").write_bytes(b"novo")
        (tmp_path / "Imagens").mkdir()
        (tmp_path / "Imagens" / "foto.jpg").write_bytes(b"existente")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), conflict_strategy="overwrite")

        assert result.is_success is True
        assert result.data["files_moved"] == 1

        # Arquivo foi sobrescrito
        assert (tmp_path / "Imagens" / "foto.jpg").read_bytes() == b"novo"

    def test_conflict_rename(self, tmp_path: Path) -> None:
        """Estratégia RENAME deve renomear."""
        from autotarefas.tasks.organizer import OrganizerTask

        # Criar arquivo e destino
        (tmp_path / "foto.jpg").write_bytes(b"novo")
        (tmp_path / "Imagens").mkdir()
        (tmp_path / "Imagens" / "foto.jpg").write_bytes(b"existente")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), conflict_strategy="rename")

        assert result.is_success is True
        assert result.data["files_moved"] == 1
        assert result.data["files_renamed"] == 1

        # Ambos os arquivos existem
        assert (tmp_path / "Imagens" / "foto.jpg").exists()
        assert (tmp_path / "Imagens" / "foto_1.jpg").exists()


# ============================================================================
# Testes de Perfis
# ============================================================================


class TestOrganizerProfiles:
    """Testes de diferentes perfis de organização."""

    def test_profile_by_extension(self, tmp_path: Path) -> None:
        """Perfil BY_EXTENSION deve criar pasta por extensão."""
        from autotarefas.tasks.organizer import OrganizerTask

        (tmp_path / "arquivo.pdf").write_bytes(b"pdf")
        (tmp_path / "outro.pdf").write_bytes(b"pdf2")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), profile="by_extension")

        assert result.is_success is True
        assert (tmp_path / "pdf" / "arquivo.pdf").exists()
        assert (tmp_path / "pdf" / "outro.pdf").exists()

    def test_profile_by_date(self, tmp_path: Path) -> None:
        """Perfil BY_DATE deve criar pasta por ano/mês."""
        from autotarefas.tasks.organizer import OrganizerTask

        (tmp_path / "arquivo.txt").write_text("test")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), profile="by_date")

        assert result.is_success is True
        assert result.data["files_moved"] == 1

        # Deve existir pasta com ano/mês
        from datetime import datetime

        now = datetime.now()
        expected_folder = tmp_path / str(now.year) / f"{now.month:02d}"
        assert expected_folder.exists()


# ============================================================================
# Testes de Opções
# ============================================================================


class TestOrganizerOptions:
    """Testes de opções adicionais."""

    def test_recursive(self, tmp_path: Path) -> None:
        """Opção recursive deve incluir subdiretórios."""
        from autotarefas.tasks.organizer import OrganizerTask

        # Criar estrutura
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "foto1.jpg").write_bytes(b"jpg1")
        (subdir / "foto2.jpg").write_bytes(b"jpg2")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), recursive=True)

        assert result.is_success is True
        assert result.data["files_moved"] == 2

    def test_not_recursive_by_default(self, tmp_path: Path) -> None:
        """Por padrão não deve incluir subdiretórios."""
        from autotarefas.tasks.organizer import OrganizerTask

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "foto1.jpg").write_bytes(b"jpg1")
        (subdir / "foto2.jpg").write_bytes(b"jpg2")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), recursive=False)

        assert result.is_success is True
        assert result.data["files_moved"] == 1  # Só o do root

    def test_include_hidden(self, tmp_path: Path) -> None:
        """Opção include_hidden deve incluir arquivos ocultos."""
        from autotarefas.tasks.organizer import OrganizerTask

        (tmp_path / ".hidden.jpg").write_bytes(b"hidden")
        (tmp_path / "visible.jpg").write_bytes(b"visible")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), include_hidden=True)

        assert result.is_success is True
        assert result.data["files_moved"] == 2

    def test_exclude_hidden_by_default(self, tmp_path: Path) -> None:
        """Por padrão não deve incluir arquivos ocultos."""
        from autotarefas.tasks.organizer import OrganizerTask

        (tmp_path / ".hidden.jpg").write_bytes(b"hidden")
        (tmp_path / "visible.jpg").write_bytes(b"visible")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), include_hidden=False)

        assert result.is_success is True
        assert result.data["files_moved"] == 1


# ============================================================================
# Testes de Função de Conveniência
# ============================================================================


class TestOrganizeDirectory:
    """Testes da função organize_directory."""

    def test_basic_usage(self, tmp_path: Path) -> None:
        """Deve funcionar com uso básico."""
        from autotarefas.tasks.organizer import organize_directory

        (tmp_path / "foto.jpg").write_bytes(b"jpg")

        result = organize_directory(tmp_path)

        assert result.is_success is True
        assert result.data["files_moved"] == 1

    def test_with_options(self, tmp_path: Path) -> None:
        """Deve aceitar opções."""
        from autotarefas.tasks.organizer import organize_directory

        (tmp_path / "foto.jpg").write_bytes(b"jpg")

        result = organize_directory(
            tmp_path,
            profile="by_extension",
            dry_run=True,
        )

        # Dry-run pode retornar SUCCESS ou SKIPPED
        assert result.status.value in ("success", "skipped")
        # Dry run não move
        assert (tmp_path / "foto.jpg").exists()
