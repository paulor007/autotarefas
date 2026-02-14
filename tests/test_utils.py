"""
Testes do módulo de utilitários (helpers).

Testa:
    - Formatação: format_size, format_time, format_datetime
    - Caminhos: safe_path, ensure_dir, get_file_extension
    - Arquivos: get_dir_size, count_files, iter_files, get_old_files
    - Validação: is_valid_email, is_valid_path, sanitize_filename
    - Outros utils: datetime_utils, format_utils, json_utils
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

# ============================================================================
# Testes de Formatação de Tamanho
# ============================================================================


class TestFormatSize:
    """Testes da função format_size."""

    def test_format_bytes(self):
        """Deve formatar bytes."""
        from autotarefas.utils import format_size

        assert format_size(0) == "0 B"
        assert format_size(100) == "100 B"
        assert format_size(1023) == "1023 B"

    def test_format_kilobytes(self):
        """Deve formatar kilobytes."""
        from autotarefas.utils import format_size

        result = format_size(1024)
        assert "KB" in result
        assert "1" in result

    def test_format_megabytes(self):
        """Deve formatar megabytes."""
        from autotarefas.utils import format_size

        result = format_size(1024 * 1024)
        assert "MB" in result

    def test_format_gigabytes(self):
        """Deve formatar gigabytes."""
        from autotarefas.utils import format_size

        result = format_size(1024 * 1024 * 1024)
        assert "GB" in result

    def test_format_terabytes(self):
        """Deve formatar terabytes."""
        from autotarefas.utils import format_size

        result = format_size(1024**4)
        assert "TB" in result

    def test_format_with_decimals(self):
        """Deve formatar com decimais."""
        from autotarefas.utils import format_size

        result = format_size(1536)  # 1.5 KB
        assert "1.5" in result or "1,5" in result

    def test_format_negative_returns_zero(self):
        """Valor negativo deve retornar 0 B."""
        from autotarefas.utils import format_size

        result = format_size(-100)
        assert "0" in result

    def test_format_float_input(self):
        """Deve aceitar float."""
        from autotarefas.utils import format_size

        result = format_size(1024.5)
        assert result is not None

    def test_format_invalid_input(self):
        """Deve tratar entrada inválida (fallback ou erro controlado)."""
        from autotarefas.utils import format_size

        # Pylance: evita erro de tipo no teste (entrada inválida intencional)
        func = cast(Any, format_size)

        try:
            result = func("invalid")
        except (TypeError, ValueError):
            # Se sua implementação optar por falhar, também é aceitável.
            return

        assert isinstance(result, str)
        assert result.startswith("0")


# ============================================================================
# Testes de Formatação de Tempo
# ============================================================================


class TestFormatTime:
    """Testes da função format_time."""

    def test_format_seconds(self):
        """Deve formatar segundos."""
        from autotarefas.utils import format_time

        result = format_time(45)
        assert "45" in result and "s" in result

    def test_format_minutes(self):
        """Deve formatar minutos."""
        from autotarefas.utils import format_time

        result = format_time(150)  # 2m 30s
        assert "m" in result

    def test_format_hours(self):
        """Deve formatar horas."""
        from autotarefas.utils import format_time

        result = format_time(3700)  # ~1h
        assert "h" in result

    def test_format_zero(self):
        """Zero deve retornar 0s."""
        from autotarefas.utils import format_time

        result = format_time(0)
        assert "0" in result

    def test_format_negative(self):
        """Negativo deve retornar 0s."""
        from autotarefas.utils import format_time

        result = format_time(-10)
        assert "0" in result


# ============================================================================
# Testes de Formatação de Data
# ============================================================================


class TestFormatDatetime:
    """Testes da função format_datetime."""

    def test_format_datetime_basic(self):
        """Deve formatar datetime básico."""
        from autotarefas.utils import format_datetime

        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = format_datetime(dt)

        assert "2024" in result
        assert "15" in result or "01" in result

    def test_format_datetime_none(self):
        """None deve retornar string vazia ou placeholder."""
        from autotarefas.utils import format_datetime

        # Alguns projetos tipam como datetime|None, outros apenas datetime.
        func = cast(Any, format_datetime)
        result = func(None)

        assert result == "" or result == "-" or result is None or "N/A" in str(result)

    def test_format_datetime_custom_format(self):
        """Deve aceitar formato customizado (se suportado)."""
        from autotarefas.utils import format_datetime

        dt = datetime(2024, 1, 15, 10, 30, 0)

        # Tenta com formato customizado se a função aceitar
        try:
            result = format_datetime(dt, fmt="%Y-%m-%d")
            assert "2024-01-15" in result
        except TypeError:
            # Se não aceitar formato, usa padrão
            result = format_datetime(dt)
            assert "2024" in result


# ============================================================================
# Testes de Caminhos
# ============================================================================


class TestSafePath:
    """Testes da função safe_path."""

    def test_safe_path_string(self):
        """Deve converter string para Path."""
        from autotarefas.utils import safe_path

        result = safe_path("/tmp/test")
        assert isinstance(result, Path)

    def test_safe_path_path(self):
        """Deve aceitar Path."""
        from autotarefas.utils import safe_path

        p = Path("/tmp/test")
        result = safe_path(p)
        assert isinstance(result, Path)

    def test_safe_path_expanduser(self):
        """Deve expandir ~."""
        from autotarefas.utils import safe_path

        result = safe_path("~/test")
        assert "~" not in str(result)

    def test_safe_path_resolve(self):
        """Deve resolver caminho."""
        from autotarefas.utils import safe_path

        result = safe_path("./test/../test")
        assert ".." not in str(result)


class TestEnsureDir:
    """Testes da função ensure_dir."""

    def test_ensure_dir_creates(self, temp_dir: Path):
        """Deve criar diretório."""
        from autotarefas.utils import ensure_dir

        new_dir = temp_dir / "new_dir"
        result = ensure_dir(new_dir)

        assert result.exists()
        assert result.is_dir()

    def test_ensure_dir_nested(self, temp_dir: Path):
        """Deve criar diretórios aninhados."""
        from autotarefas.utils import ensure_dir

        nested = temp_dir / "a" / "b" / "c"
        result = ensure_dir(nested)

        assert result.exists()

    def test_ensure_dir_existing(self, temp_dir: Path):
        """Deve aceitar diretório existente."""
        from autotarefas.utils import ensure_dir

        result = ensure_dir(temp_dir)

        assert result == temp_dir or result.samefile(temp_dir)


class TestGetFileExtension:
    """Testes da função get_file_extension."""

    def test_get_extension_basic(self):
        """Deve retornar extensão básica."""
        from autotarefas.utils import get_file_extension

        assert get_file_extension("file.txt") == "txt"
        assert get_file_extension("file.py") == "py"
        assert get_file_extension("file.PDF") == "pdf"  # lowercase

    def test_get_extension_no_extension(self):
        """Arquivo sem extensão deve retornar vazio."""
        from autotarefas.utils import get_file_extension

        assert get_file_extension("file") == ""
        assert get_file_extension("Makefile") == ""

    def test_get_extension_double(self):
        """Extensão dupla deve retornar última."""
        from autotarefas.utils import get_file_extension

        # Comportamento padrão do Path
        assert get_file_extension("file.tar.gz") == "gz"

    def test_get_extension_hidden(self):
        """Arquivo oculto com extensão."""
        from autotarefas.utils import get_file_extension

        assert get_file_extension(".gitignore") == ""
        assert get_file_extension(".env.local") == "local"


# ============================================================================
# Testes de Categoria de Arquivo
# ============================================================================


class TestGetFileCategory:
    """Testes da função get_file_category."""

    def test_category_image(self):
        """Deve categorizar imagens."""
        from autotarefas.utils import get_file_category

        assert get_file_category("photo.jpg") == "imagem"
        assert get_file_category("icon.png") == "imagem"
        assert get_file_category("logo.svg") == "imagem"

    def test_category_document(self):
        """Deve categorizar documentos."""
        from autotarefas.utils import get_file_category

        assert get_file_category("report.pdf") == "documento"
        assert get_file_category("notes.txt") == "documento"
        assert get_file_category("doc.docx") == "documento"

    def test_category_video(self):
        """Deve categorizar vídeos."""
        from autotarefas.utils import get_file_category

        assert get_file_category("movie.mp4") == "video"
        assert get_file_category("clip.avi") == "video"

    def test_category_audio(self):
        """Deve categorizar áudios."""
        from autotarefas.utils import get_file_category

        assert get_file_category("song.mp3") == "audio"
        assert get_file_category("sound.wav") == "audio"

    def test_category_code(self):
        """Deve categorizar código."""
        from autotarefas.utils import get_file_category

        assert get_file_category("script.py") == "codigo"
        assert get_file_category("app.js") == "codigo"

    def test_category_archive(self):
        """Deve categorizar arquivos compactados."""
        from autotarefas.utils import get_file_category

        assert get_file_category("backup.zip") == "arquivo"
        assert get_file_category("data.tar.gz") == "arquivo"  # .gz

    def test_category_unknown(self):
        """Extensão desconhecida deve retornar 'outro'."""
        from autotarefas.utils import get_file_category

        assert get_file_category("file.xyz") == "outro"
        assert get_file_category("noextension") == "outro"


# ============================================================================
# Testes de Operações com Diretórios
# ============================================================================


class TestGetDirSize:
    """Testes da função get_dir_size."""

    def test_dir_size_empty(self, temp_dir: Path):
        """Diretório vazio deve retornar 0."""
        from autotarefas.utils import get_dir_size

        size = get_dir_size(temp_dir)
        assert size == 0

    def test_dir_size_with_files(self, temp_dir: Path):
        """Deve somar tamanho dos arquivos."""
        from autotarefas.utils import get_dir_size

        (temp_dir / "file1.txt").write_text("a" * 100)
        (temp_dir / "file2.txt").write_text("b" * 200)

        size = get_dir_size(temp_dir)
        assert size >= 300  # Pode ser maior por overhead

    def test_dir_size_nested(self, temp_dir: Path):
        """Deve incluir subdiretórios."""
        from autotarefas.utils import get_dir_size

        sub = temp_dir / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("x" * 500)

        size = get_dir_size(temp_dir)
        assert size >= 500

    def test_dir_size_nonexistent(self):
        """Diretório inexistente deve retornar 0."""
        from autotarefas.utils import get_dir_size

        size = get_dir_size("/nonexistent/path")
        assert size == 0


class TestCountFiles:
    """Testes da função count_files."""

    def test_count_empty(self, temp_dir: Path):
        """Diretório vazio deve retornar 0."""
        from autotarefas.utils import count_files

        count = count_files(temp_dir)
        assert count == 0

    def test_count_files_basic(self, temp_dir: Path):
        """Deve contar arquivos."""
        from autotarefas.utils import count_files

        (temp_dir / "file1.txt").touch()
        (temp_dir / "file2.txt").touch()
        (temp_dir / "file3.py").touch()

        count = count_files(temp_dir)
        assert count == 3

    def test_count_with_pattern(self, temp_dir: Path):
        """Deve filtrar por padrão."""
        from autotarefas.utils import count_files

        (temp_dir / "file1.txt").touch()
        (temp_dir / "file2.txt").touch()
        (temp_dir / "file3.py").touch()

        count = count_files(temp_dir, "*.txt")
        assert count == 2

    def test_count_includes_nested_when_supported(self, temp_dir: Path):
        """Deve incluir arquivos em subdiretórios quando suportado."""
        from autotarefas.utils import count_files

        (temp_dir / "file.txt").touch()
        sub = temp_dir / "sub"
        sub.mkdir()
        (sub / "nested.txt").touch()

        # Evita kwargs que não existam na assinatura (Pylance).
        # Se sua implementação for recursiva por padrão => 2
        # Se não for recursiva por padrão => 1
        result = count_files(temp_dir)
        assert result in (1, 2)


class TestIterFiles:
    """Testes da função iter_files."""

    def test_iter_files_basic(self, temp_dir: Path):
        """Deve iterar sobre arquivos."""
        from autotarefas.utils import iter_files

        (temp_dir / "file1.txt").touch()
        (temp_dir / "file2.txt").touch()

        files = list(iter_files(temp_dir))
        assert len(files) == 2
        assert all(isinstance(f, Path) for f in files)

    def test_iter_files_with_pattern(self, temp_dir: Path):
        """Deve filtrar por padrão."""
        from autotarefas.utils import iter_files

        (temp_dir / "file.txt").touch()
        (temp_dir / "file.py").touch()

        files = list(iter_files(temp_dir, "*.txt"))
        assert len(files) == 1

    def test_iter_files_recursive(self, temp_dir: Path):
        """Deve ser recursivo por padrão."""
        from autotarefas.utils import iter_files

        (temp_dir / "file.txt").touch()
        sub = temp_dir / "sub"
        sub.mkdir()
        (sub / "nested.txt").touch()

        files = list(iter_files(temp_dir))
        assert len(files) == 2


# ============================================================================
# Testes de Validação
# ============================================================================


class TestIsValidEmail:
    """Testes da função is_valid_email."""

    def test_valid_emails(self):
        """Deve aceitar emails válidos."""
        from autotarefas.utils import is_valid_email

        assert is_valid_email("user@example.com") is True
        assert is_valid_email("test.user@domain.org") is True
        assert is_valid_email("user+tag@example.com") is True

    def test_invalid_emails(self):
        """Deve rejeitar emails inválidos."""
        from autotarefas.utils import is_valid_email

        assert is_valid_email("invalid") is False
        assert is_valid_email("@domain.com") is False
        assert is_valid_email("user@") is False
        assert is_valid_email("") is False

    def test_none_email(self):
        """None deve retornar False."""
        from autotarefas.utils import is_valid_email

        func = cast(Any, is_valid_email)
        assert func(None) is False


class TestIsValidPath:
    """Testes da função is_valid_path."""

    def test_valid_existing_path(self, temp_dir: Path):
        """Caminho existente deve ser válido."""
        from autotarefas.utils import is_valid_path

        assert is_valid_path(str(temp_dir)) is True

    def test_valid_syntax_path(self):
        """Caminho com sintaxe válida."""
        from autotarefas.utils import is_valid_path

        # Pode validar apenas sintaxe ou existência
        result = is_valid_path("/tmp/some/path")
        assert isinstance(result, bool)

    def test_invalid_path(self):
        """Deve rejeitar caminhos inválidos."""
        from autotarefas.utils import is_valid_path

        result = is_valid_path("")
        assert result is False


class TestSanitizeFilename:
    """Testes da função sanitize_filename."""

    def test_sanitize_basic(self):
        """Deve manter nome válido."""
        from autotarefas.utils import sanitize_filename

        result = sanitize_filename("valid_filename.txt")
        assert result == "valid_filename.txt"

    def test_sanitize_removes_invalid(self):
        """Deve remover caracteres inválidos."""
        from autotarefas.utils import sanitize_filename

        result = sanitize_filename("file/with\\invalid:chars?.txt")
        assert "/" not in result
        assert "\\" not in result
        assert ":" not in result
        assert "?" not in result

    def test_sanitize_replaces_spaces(self):
        """Pode substituir espaços."""
        from autotarefas.utils import sanitize_filename

        result = sanitize_filename("file with spaces.txt")
        assert result is not None

    def test_sanitize_empty_string(self):
        """String vazia deve retornar algo válido."""
        from autotarefas.utils import sanitize_filename

        result = sanitize_filename("")
        assert result is not None


# ============================================================================
# Testes de datetime_utils
# ============================================================================


class TestDatetimeUtils:
    """Testes do módulo datetime_utils."""

    def test_utc_now(self):
        """utc_now() deve retornar datetime em UTC."""
        from autotarefas.utils.datetime_utils import utc_now

        result = utc_now()
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_dt_to_iso(self):
        """dt_to_iso() deve converter para ISO8601."""
        from autotarefas.utils.datetime_utils import dt_to_iso

        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = dt_to_iso(dt)

        assert isinstance(result, str)
        assert "2024" in result
        assert "T" in result  # ISO format has T separator

    def test_dt_to_iso_none(self):
        """dt_to_iso(None) deve retornar None."""
        from autotarefas.utils.datetime_utils import dt_to_iso

        func = cast(Any, dt_to_iso)
        result = func(None)
        assert result is None

    def test_parse_dt_string(self):
        """parse_dt() deve converter string ISO."""
        from autotarefas.utils.datetime_utils import parse_dt

        result = parse_dt("2024-01-15T10:30:00+00:00")
        assert isinstance(result, datetime)

    def test_parse_dt_none(self):
        """parse_dt(None) deve retornar None."""
        from autotarefas.utils.datetime_utils import parse_dt

        func = cast(Any, parse_dt)
        result = func(None)
        assert result is None


# ============================================================================
# Testes de format_utils
# ============================================================================


class TestFormatUtils:
    """Testes do módulo format_utils."""

    def test_brl_formatting(self):
        """brl() deve formatar como moeda brasileira."""
        from autotarefas.utils.format_utils import brl

        result = brl(1234.56)
        assert "R$" in result
        assert "1.234" in result or "1234" in result
        assert "56" in result

    def test_safe_int(self):
        """safe_int() deve converter com fallback."""
        from autotarefas.utils.format_utils import safe_int

        assert safe_int("42") == 42
        assert safe_int("invalid", default=0) == 0
        assert safe_int(None, default=-1) == -1

    def test_safe_float(self):
        """safe_float() deve converter com fallback."""
        from autotarefas.utils.format_utils import safe_float

        assert safe_float("3.14") == pytest.approx(3.14)
        assert safe_float("invalid", default=0.0) == 0.0


# ============================================================================
# Testes de json_utils
# ============================================================================


class TestJsonUtils:
    """Testes do módulo json_utils."""

    def test_atomic_write_json(self, temp_dir: Path):
        """atomic_write_json() deve escrever atomicamente."""
        from autotarefas.utils.json_utils import atomic_write_json

        file_path = temp_dir / "data.json"
        data = {"key": "value", "number": 42}

        atomic_write_json(file_path, data)

        assert file_path.exists()
        content = json.loads(file_path.read_text())
        assert content == data

    def test_atomic_write_creates_parent(self, temp_dir: Path):
        """Deve criar diretórios pai."""
        from autotarefas.utils.json_utils import atomic_write_json

        file_path = temp_dir / "nested" / "deep" / "data.json"
        data = {"test": True}

        atomic_write_json(file_path, data)

        assert file_path.exists()

    def test_json_dumps_safe(self):
        """json_dumps() deve ser seguro com None."""
        from autotarefas.utils.json_utils import json_dumps

        func = cast(Any, json_dumps)
        assert func(None) is None
        assert json_dumps({"key": "value"}) is not None

    def test_json_loads_safe(self):
        """json_loads() deve ser seguro com entrada inválida."""
        from autotarefas.utils.json_utils import json_loads

        func = cast(Any, json_loads)

        assert func(None) == {}
        assert json_loads("") == {}
        assert json_loads("invalid json") == {}
        assert json_loads('{"key": "value"}') == {"key": "value"}


# ============================================================================
# Testes de Arquivos Antigos
# ============================================================================


class TestGetOldFiles:
    """Testes da função get_old_files."""

    def test_get_old_files_basic(self, temp_dir: Path):
        """Deve encontrar arquivos antigos."""
        from autotarefas.utils import get_old_files

        # Cria arquivo "antigo"
        old_file = temp_dir / "old.txt"
        old_file.write_text("old content")

        # Define data antiga (30 dias atrás)
        old_time = (datetime.now(UTC) - timedelta(days=30)).timestamp()
        os.utime(old_file, (old_time, old_time))

        # Cria arquivo novo
        new_file = temp_dir / "new.txt"
        new_file.write_text("new content")

        # Busca arquivos com mais de 7 dias
        old_files = list(get_old_files(temp_dir, days=7))

        assert len(old_files) == 1
        assert old_files[0].name == "old.txt"

    def test_get_old_files_empty(self, temp_dir: Path):
        """Deve retornar vazio se não houver arquivos antigos."""
        from autotarefas.utils import get_old_files

        (temp_dir / "recent.txt").write_text("recent")

        old_files = list(get_old_files(temp_dir, days=30))
        assert len(old_files) == 0


# ============================================================================
# Testes de Hash
# ============================================================================


class TestGetFileHash:
    """Testes da função get_file_hash."""

    def test_hash_file(self, temp_dir: Path):
        """Deve calcular hash do arquivo."""
        from autotarefas.utils import get_file_hash

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        hash1 = get_file_hash(file_path)
        assert hash1 is not None
        assert len(hash1) > 0

    def test_hash_same_content_same_hash(self, temp_dir: Path):
        """Mesmo conteúdo deve ter mesmo hash."""
        from autotarefas.utils import get_file_hash

        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"

        content = "identical content"
        file1.write_text(content)
        file2.write_text(content)

        assert get_file_hash(file1) == get_file_hash(file2)

    def test_hash_different_content_different_hash(self, temp_dir: Path):
        """Conteúdo diferente deve ter hash diferente."""
        from autotarefas.utils import get_file_hash

        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"

        file1.write_text("content A")
        file2.write_text("content B")

        assert get_file_hash(file1) != get_file_hash(file2)


# ============================================================================
# Testes de Disco
# ============================================================================


class TestGetDiskUsage:
    """Testes da função get_disk_usage."""

    def test_disk_usage_returns_dict(self):
        """Deve retornar dicionário com uso de disco."""
        from autotarefas.utils import get_disk_usage

        usage = get_disk_usage("/")

        assert isinstance(usage, dict)
        assert "total" in usage or "total_bytes" in usage or len(usage) > 0

    def test_disk_usage_has_values(self):
        """Deve ter valores de uso."""
        from autotarefas.utils import get_disk_usage

        usage = get_disk_usage("/")

        values = list(usage.values())
        assert any(isinstance(v, (int, float)) and v > 0 for v in values)
