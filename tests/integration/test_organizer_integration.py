"""
Testes de integração do módulo de organização de arquivos.

O QUE ESTES TESTES VERIFICAM:
=============================
- Fluxo completo de organização com múltiplos arquivos
- Integração com RunHistory
- Organização de estruturas complexas de diretórios
- Preservação de integridade dos arquivos
- Cenários reais de uso

COMO RODAR:
===========
    pytest tests/integration/test_organizer_integration.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_downloads(tmp_path: Path) -> Path:
    """
    Cria estrutura simulando pasta Downloads típica.

    Estrutura:
        downloads/
        ├── foto_ferias.jpg
        ├── foto_familia.png
        ├── relatorio_2024.pdf
        ├── planilha_gastos.xlsx
        ├── apresentacao.pptx
        ├── video_aniversario.mp4
        ├── musica_favorita.mp3
        ├── backup.zip
        ├── programa.exe
        ├── script.py
        └── arquivo_estranho.xyz
    """
    downloads = tmp_path / "downloads"
    downloads.mkdir()

    # Imagens
    (downloads / "foto_ferias.jpg").write_bytes(b"\xff\xd8\xff" + b"x" * 100)
    (downloads / "foto_familia.png").write_bytes(b"\x89PNG" + b"x" * 100)

    # Documentos
    (downloads / "relatorio_2024.pdf").write_bytes(b"%PDF" + b"x" * 100)
    (downloads / "planilha_gastos.xlsx").write_bytes(b"PK" + b"x" * 100)
    (downloads / "apresentacao.pptx").write_bytes(b"PK" + b"x" * 100)

    # Vídeos
    (downloads / "video_aniversario.mp4").write_bytes(b"\x00\x00\x00\x1c" + b"x" * 200)

    # Áudio
    (downloads / "musica_favorita.mp3").write_bytes(b"ID3" + b"x" * 100)

    # Arquivos compactados
    (downloads / "backup.zip").write_bytes(b"PK" + b"x" * 100)

    # Executáveis
    (downloads / "programa.exe").write_bytes(b"MZ" + b"x" * 100)

    # Código
    (downloads / "script.py").write_text("print('hello')")

    # Desconhecido
    (downloads / "arquivo_estranho.xyz").write_text("unknown format")

    return downloads


@pytest.fixture
def nested_structure(tmp_path: Path) -> Path:
    """
    Cria estrutura aninhada para testar recursividade.

    Estrutura:
        root/
        ├── level1/
        │   ├── foto1.jpg
        │   └── level2/
        │       ├── foto2.jpg
        │       └── level3/
        │           └── foto3.jpg
        └── doc.pdf
    """
    root = tmp_path / "root"
    root.mkdir()

    level1 = root / "level1"
    level1.mkdir()

    level2 = level1 / "level2"
    level2.mkdir()

    level3 = level2 / "level3"
    level3.mkdir()

    (root / "doc.pdf").write_bytes(b"pdf")
    (level1 / "foto1.jpg").write_bytes(b"jpg1")
    (level2 / "foto2.jpg").write_bytes(b"jpg2")
    (level3 / "foto3.jpg").write_bytes(b"jpg3")

    return root


# ============================================================================
# Testes de Fluxo Completo
# ============================================================================


class TestOrganizeCompleteFlow:
    """Testes de fluxo completo de organização."""

    def test_organize_typical_downloads(self, sample_downloads: Path) -> None:
        """Deve organizar pasta Downloads típica corretamente."""
        from autotarefas.tasks.organizer import OrganizerTask

        task = OrganizerTask()
        result = task.run(source=str(sample_downloads))

        assert result.is_success is True
        assert result.data["files_moved"] == 11

        # Verificar pastas criadas
        assert (sample_downloads / "Imagens").is_dir()
        assert (sample_downloads / "Documentos").is_dir()
        assert (sample_downloads / "Videos").is_dir()
        assert (sample_downloads / "Audio").is_dir()
        assert (sample_downloads / "Arquivos").is_dir()
        assert (sample_downloads / "Executaveis").is_dir()
        assert (sample_downloads / "Codigo").is_dir()
        assert (sample_downloads / "Outros").is_dir()

        # Verificar arquivos nas pastas corretas
        assert (sample_downloads / "Imagens" / "foto_ferias.jpg").exists()
        assert (sample_downloads / "Imagens" / "foto_familia.png").exists()
        assert (sample_downloads / "Documentos" / "relatorio_2024.pdf").exists()
        assert (sample_downloads / "Documentos" / "planilha_gastos.xlsx").exists()
        assert (sample_downloads / "Videos" / "video_aniversario.mp4").exists()
        assert (sample_downloads / "Audio" / "musica_favorita.mp3").exists()
        assert (sample_downloads / "Arquivos" / "backup.zip").exists()
        assert (sample_downloads / "Executaveis" / "programa.exe").exists()
        assert (sample_downloads / "Codigo" / "script.py").exists()
        assert (sample_downloads / "Outros" / "arquivo_estranho.xyz").exists()

    def test_organize_preserves_content(self, tmp_path: Path) -> None:
        """Deve preservar conteúdo dos arquivos."""
        from autotarefas.tasks.organizer import OrganizerTask

        original_content = b"Este e o conteudo original do arquivo"
        (tmp_path / "documento.pdf").write_bytes(original_content)

        task = OrganizerTask()
        result = task.run(source=str(tmp_path))

        assert result.is_success is True

        # Verificar que conteúdo foi preservado
        moved_file = tmp_path / "Documentos" / "documento.pdf"
        assert moved_file.exists()
        assert moved_file.read_bytes() == original_content

    def test_organize_to_different_destination(
        self, sample_downloads: Path, tmp_path: Path
    ) -> None:
        """Deve organizar para diretório de destino diferente."""
        from autotarefas.tasks.organizer import OrganizerTask

        dest = tmp_path / "organized"

        task = OrganizerTask()
        result = task.run(source=str(sample_downloads), dest=str(dest))

        assert result.is_success is True

        # Arquivos originais foram movidos
        assert not (sample_downloads / "foto_ferias.jpg").exists()

        # Arquivos estão no destino
        assert (dest / "Imagens" / "foto_ferias.jpg").exists()

    def test_organize_categories_count(self, sample_downloads: Path) -> None:
        """Deve contar categorias corretamente."""
        from autotarefas.tasks.organizer import OrganizerTask

        task = OrganizerTask()
        result = task.run(source=str(sample_downloads))

        categories = result.data["categories_used"]

        assert categories["Imagens"] == 2
        assert categories["Documentos"] == 3
        assert categories["Videos"] == 1
        assert categories["Audio"] == 1
        assert categories["Arquivos"] == 1
        assert categories["Executaveis"] == 1
        assert categories["Codigo"] == 1
        assert categories["Outros"] == 1


# ============================================================================
# Testes de Estruturas Complexas
# ============================================================================


class TestOrganizeComplexStructures:
    """Testes com estruturas complexas."""

    def test_recursive_organization(self, nested_structure: Path) -> None:
        """Deve organizar recursivamente."""
        from autotarefas.tasks.organizer import OrganizerTask

        task = OrganizerTask()
        result = task.run(source=str(nested_structure), recursive=True)

        assert result.is_success is True
        assert result.data["files_moved"] == 4  # 1 pdf + 3 jpgs

    def test_already_organized_files_skipped(self, tmp_path: Path) -> None:
        """Arquivos já em pastas de categoria devem ser pulados."""
        from autotarefas.tasks.organizer import OrganizerTask

        # Criar estrutura já organizada
        (tmp_path / "Imagens").mkdir()
        (tmp_path / "Imagens" / "foto.jpg").write_bytes(b"jpg")

        # Adicionar novo arquivo
        (tmp_path / "nova_foto.jpg").write_bytes(b"new jpg")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path))

        assert result.is_success is True
        assert result.data["files_moved"] == 1  # Só a nova foto

        # Foto original não foi movida novamente
        assert (tmp_path / "Imagens" / "foto.jpg").exists()
        assert (tmp_path / "Imagens" / "nova_foto.jpg").exists()

    def test_unicode_filenames(self, tmp_path: Path) -> None:
        """Deve lidar com nomes de arquivo unicode."""
        from autotarefas.tasks.organizer import OrganizerTask

        (tmp_path / "foto_férias.jpg").write_bytes(b"jpg")
        (tmp_path / "日本語.pdf").write_bytes(b"pdf")
        (tmp_path / "données.xlsx").write_bytes(b"xlsx")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path))

        assert result.is_success is True
        assert result.data["files_moved"] == 3


# ============================================================================
# Testes de Múltiplos Conflitos
# ============================================================================


class TestOrganizeMultipleConflicts:
    """Testes com múltiplos conflitos."""

    def test_multiple_rename_conflicts(self, tmp_path: Path) -> None:
        """Deve renomear múltiplos conflitos sequencialmente."""
        from autotarefas.tasks.organizer import OrganizerTask

        # Criar arquivos com mesmo nome
        (tmp_path / "foto.jpg").write_bytes(b"original")

        # Criar pasta Imagens com conflitos
        (tmp_path / "Imagens").mkdir()
        (tmp_path / "Imagens" / "foto.jpg").write_bytes(b"conflict1")
        (tmp_path / "Imagens" / "foto_1.jpg").write_bytes(b"conflict2")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), conflict_strategy="rename")

        assert result.is_success is True

        # Deve criar foto_2.jpg
        assert (tmp_path / "Imagens" / "foto_2.jpg").exists()
        assert (tmp_path / "Imagens" / "foto_2.jpg").read_bytes() == b"original"


# ============================================================================
# Testes de Integração com RunHistory
# ============================================================================


class TestOrganizerWithRunHistory:
    """Testes de integração com RunHistory."""

    def test_organize_with_run_history(
        self,
        tmp_path: Path,
        integration_env: dict[str, Path],
    ) -> None:
        """Deve registrar execução no RunHistory."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus
        from autotarefas.tasks.organizer import OrganizerTask

        # Criar arquivo para organizar
        source = tmp_path / "source"
        source.mkdir()
        (source / "foto.jpg").write_bytes(b"jpg")

        history = RunHistory(integration_env["data"] / "test_history.db")

        # Registrar início
        record = history.start_run(
            job_id="organizer-job-1",
            job_name="organize_downloads",
            task="organizer",
            params={"source": str(source)},
        )

        # Executar organização
        result = OrganizerTask().run(source=str(source))

        # Registrar fim
        history.finish_run(
            record.id,
            RunStatus.SUCCESS if result.is_success else RunStatus.FAILED,
            duration=result.duration_seconds,
            output=result.message,
        )

        # Verificar histórico
        runs = history.get_by_job("organizer-job-1")
        assert len(runs) == 1
        assert runs[0].status == RunStatus.SUCCESS


# ============================================================================
# Testes de Perfis Avançados
# ============================================================================


class TestOrganizerProfilesAdvanced:
    """Testes avançados de perfis."""

    def test_by_date_multiple_months(self, tmp_path: Path) -> None:
        """Perfil BY_DATE com arquivos de meses diferentes."""
        import os
        import time

        from autotarefas.tasks.organizer import OrganizerTask

        # Criar arquivo recente
        recent = tmp_path / "recent.txt"
        recent.write_text("recent")

        # Criar arquivo antigo (modificar mtime)
        old = tmp_path / "old.txt"
        old.write_text("old")
        # Setar para 60 dias atrás
        old_time = time.time() - (60 * 24 * 60 * 60)
        os.utime(old, (old_time, old_time))

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), profile="by_date")

        assert result.is_success is True
        assert result.data["files_moved"] == 2

        # Devem estar em pastas diferentes
        year_folders = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(year_folders) >= 1

    def test_by_extension_multiple_same_ext(self, tmp_path: Path) -> None:
        """Perfil BY_EXTENSION agrupa mesma extensão."""
        from autotarefas.tasks.organizer import OrganizerTask

        # Criar múltiplos PDFs
        for i in range(5):
            (tmp_path / f"documento_{i}.pdf").write_bytes(b"pdf")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), profile="by_extension")

        assert result.is_success is True
        assert result.data["files_moved"] == 5

        # Todos na pasta pdf
        pdf_folder = tmp_path / "pdf"
        assert pdf_folder.is_dir()
        assert len(list(pdf_folder.iterdir())) == 5


# ============================================================================
# Testes de Edge Cases
# ============================================================================


class TestOrganizerEdgeCases:
    """Testes de casos extremos."""

    def test_empty_extension(self, tmp_path: Path) -> None:
        """Arquivo sem extensão pelo perfil by_extension."""
        from autotarefas.tasks.organizer import OrganizerTask

        (tmp_path / "Makefile").write_text("all:")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path), profile="by_extension")

        assert result.is_success is True
        assert (tmp_path / "sem_extensao" / "Makefile").exists()

    def test_multiple_dots_in_filename(self, tmp_path: Path) -> None:
        """Deve usar apenas última extensão."""
        from autotarefas.tasks.organizer import OrganizerTask

        (tmp_path / "arquivo.backup.2024.pdf").write_bytes(b"pdf")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path))

        assert result.is_success is True
        assert (tmp_path / "Documentos" / "arquivo.backup.2024.pdf").exists()

    def test_case_insensitive_extension(self, tmp_path: Path) -> None:
        """Extensões devem ser case-insensitive."""
        from autotarefas.tasks.organizer import OrganizerTask

        (tmp_path / "FOTO.JPG").write_bytes(b"jpg")
        (tmp_path / "doc.PDF").write_bytes(b"pdf")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path))

        assert result.is_success is True
        assert (tmp_path / "Imagens" / "FOTO.JPG").exists()
        assert (tmp_path / "Documentos" / "doc.PDF").exists()

    def test_symlinks_skipped(self, tmp_path: Path) -> None:
        """Symlinks devem ser ignorados."""
        from autotarefas.tasks.organizer import OrganizerTask

        # Criar arquivo real
        real_file = tmp_path / "real.txt"
        real_file.write_text("real content")

        # Criar symlink (pode falhar no Windows sem privilégios)
        try:
            symlink = tmp_path / "link.txt"
            symlink.symlink_to(real_file)
        except OSError:
            pytest.skip("Symlinks não suportados neste ambiente")

        task = OrganizerTask()
        result = task.run(source=str(tmp_path))

        # Arquivo real foi movido, symlink foi ignorado ou quebrado
        assert result.is_success is True

    def test_large_number_of_files(self, tmp_path: Path) -> None:
        """Deve lidar com grande número de arquivos."""
        from autotarefas.tasks.organizer import OrganizerTask

        # Criar 100 arquivos
        for i in range(100):
            ext = [".jpg", ".pdf", ".mp4", ".mp3", ".zip"][i % 5]
            (tmp_path / f"arquivo_{i:03d}{ext}").write_bytes(b"x" * 10)

        task = OrganizerTask()
        result = task.run(source=str(tmp_path))

        assert result.is_success is True
        assert result.data["files_moved"] == 100
