"""
Funções utilitárias do AutoTarefas.

Este módulo concentra helpers usados em várias partes do sistema, incluindo:
- Formatação (tamanho, tempo, datas)
- Manipulação segura de caminhos e diretórios
- Operações comuns com arquivos (hash, tamanho, contagem, listagem)
- Validações simples (email, path)
- Sanitização de nomes de arquivos

Uso:
    from autotarefas.utils.helpers import (
        format_size, format_time, format_datetime,
        safe_path, ensure_dir, sanitize_filename
    )
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path

# =============================================================================
# Formatação
# =============================================================================


def format_size(size_bytes: int | float) -> str:
    """
    Formata tamanho em bytes para um formato legível.

    Args:
        size_bytes: Tamanho em bytes.

    Returns:
        String formatada (ex: "1.5 GB", "256 KB", "0 B").

    Exemplos:
        >>> format_size(1024)
        '1.0 KB'
        >>> format_size(1536000)
        '1.5 MB'
        >>> format_size(0)
        '0 B'
    """
    try:
        size = float(size_bytes)
    except (TypeError, ValueError):
        return "0 B"

    if size <= 0:
        return "0 B"

    units = ("B", "KB", "MB", "GB", "TB", "PB")
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def format_time(seconds: float) -> str:
    """
    Formata tempo em segundos para formato legível.

    Args:
        seconds: Tempo em segundos.

    Returns:
        String formatada (ex: "2h 30m", "45s", "1d 2h").

    Exemplos:
        >>> format_time(45)
        '45s'
        >>> format_time(150)
        '2m 30s'
        >>> format_time(3700)
        '1h 1m'
    """
    try:
        sec = float(seconds)
    except (TypeError, ValueError):
        return "0s"

    if sec <= 0:
        return "0s"

    if sec < 60:
        return f"{int(sec)}s"

    if sec < 3600:
        minutes = int(sec // 60)
        rem = int(sec % 60)
        return f"{minutes}m {rem}s" if rem else f"{minutes}m"

    if sec < 86400:
        hours = int(sec // 3600)
        minutes = int((sec % 3600) // 60)
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"

    days = int(sec // 86400)
    hours = int((sec % 86400) // 3600)
    return f"{days}d {hours}h" if hours else f"{days}d"


def format_datetime(dt: datetime | None, fmt: str = "%d/%m/%Y %H:%M:%S") -> str:
    """
    Formata um datetime para string.

    Args:
        dt: Datetime a formatar (None retorna "-").
        fmt: Formato strftime (default: "%d/%m/%Y %H:%M:%S").

    Returns:
        String formatada ou "-" se dt for None.
    """
    if dt is None:
        return "-"
    return dt.strftime(fmt)


def format_relative_time(dt: datetime) -> str:
    """
    Formata datetime como tempo relativo (ex: "há 5 minutos").

    Args:
        dt: Datetime a formatar.

    Returns:
        String com tempo relativo.

    Observação:
        Se dt estiver no futuro (clock skew), retorna "agora mesmo".
    """
    now = datetime.now(tz=dt.tzinfo) if dt.tzinfo else datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()

    if seconds <= 0:
        return "agora mesmo"

    if seconds < 60:
        return "agora mesmo"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"há {minutes} minuto{'s' if minutes != 1 else ''}"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"há {hours} hora{'s' if hours != 1 else ''}"
    if seconds < 604800:
        days = int(seconds // 86400)
        return f"há {days} dia{'s' if days != 1 else ''}"

    return format_datetime(dt, "%d/%m/%Y")


# =============================================================================
# Caminhos
# =============================================================================


def safe_path(path: str | Path) -> Path:
    """
    Converte e normaliza um caminho de forma segura.

    - Expande "~" e variáveis de ambiente.
    - Resolve caminhos relativos.
    - NÃO exige que o caminho exista (strict=False).

    Args:
        path: Caminho como str ou Path.

    Returns:
        Path expandido e resolvido.
    """
    expanded = os.path.expandvars(os.path.expanduser(str(path)))
    return Path(expanded).resolve(strict=False)


def ensure_dir(path: str | Path) -> Path:
    """
    Garante que um diretório exista, criando se necessário.

    Args:
        path: Caminho do diretório.

    Returns:
        Path do diretório (resolvido).

    Raises:
        PermissionError: Se não houver permissão para criar.
        OSError: Se falhar ao criar por algum motivo.
    """
    dir_path = safe_path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_file_extension(path: str | Path) -> str:
    """
    Obtém extensão do arquivo em minúsculas, sem o ponto.

    Observação:
        Para "arquivo.tar.gz" retorna "gz" (comportamento padrão do Path.suffix).

    Args:
        path: Caminho do arquivo.

    Returns:
        Extensão em minúsculas (ex: "txt", "py", "pdf") ou "" se não houver.

    Exemplos:
        >>> get_file_extension("documento.PDF")
        'pdf'
        >>> get_file_extension("arquivo.tar.gz")
        'gz'
    """
    return Path(path).suffix.lower().lstrip(".")


def get_file_category(path: str | Path) -> str:
    """
    Categoriza arquivo pela extensão.

    Args:
        path: Caminho do arquivo.

    Returns:
        Categoria ("imagem", "documento", "video", "audio", "codigo", "arquivo", "outro").
    """
    ext = get_file_extension(path)

    categories: dict[str, set[str]] = {
        "imagem": {"jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "ico", "tiff"},
        "documento": {
            "pdf",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "ppt",
            "pptx",
            "odt",
            "txt",
            "rtf",
            "md",
        },
        "video": {"mp4", "avi", "mkv", "mov", "wmv", "flv", "webm", "m4v"},
        "audio": {"mp3", "wav", "flac", "aac", "ogg", "wma", "m4a"},
        "codigo": {
            "py",
            "js",
            "ts",
            "html",
            "css",
            "java",
            "cpp",
            "c",
            "go",
            "rs",
            "rb",
            "php",
        },
        "arquivo": {"zip", "rar", "7z", "tar", "gz", "bz2", "xz"},
    }

    for category, extensions in categories.items():
        if ext in extensions:
            return category

    return "outro"


def get_unique_filename(path: str | Path) -> Path:
    """
    Gera um nome de arquivo único, adicionando sufixo numérico se necessário.

    Ex:
        arquivo.txt -> arquivo_1.txt -> arquivo_2.txt ...

    Args:
        path: Caminho desejado.

    Returns:
        Um Path único (original ou com sufixo).
    """
    p = safe_path(path)
    if not p.exists():
        return p

    stem = p.stem
    suffix = p.suffix
    parent = p.parent

    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


# =============================================================================
# Arquivos
# =============================================================================


def get_dir_size(path: str | Path) -> int:
    """
    Calcula tamanho total de um diretório em bytes.

    Args:
        path: Caminho do diretório (ou arquivo).

    Returns:
        Tamanho total em bytes. Se não existir ou não for acessível, retorna 0.
    """
    p = safe_path(path)

    if not p.exists():
        return 0

    if p.is_file():
        try:
            return p.stat().st_size
        except (OSError, PermissionError):
            return 0

    total = 0
    for item in p.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except (OSError, PermissionError):
                continue

    return total


def count_files(path: str | Path, pattern: str = "*") -> int:
    """
    Conta arquivos em um diretório.

    Args:
        path: Caminho do diretório.
        pattern: Padrão glob (default: "*").

    Returns:
        Número de arquivos encontrados.
    """
    p = safe_path(path)
    if not p.is_dir():
        return 0
    return sum(1 for f in p.rglob(pattern) if f.is_file())


def iter_files(
    path: str | Path, pattern: str = "*", recursive: bool = True
) -> Generator[Path, None, None]:
    """
    Itera sobre arquivos em um diretório.

    Args:
        path: Caminho do diretório.
        pattern: Padrão glob.
        recursive: Se deve incluir subdiretórios.

    Yields:
        Path de cada arquivo encontrado.
    """
    p = safe_path(path)
    if not p.is_dir():
        return

    glob_func = p.rglob if recursive else p.glob
    for item in glob_func(pattern):
        if item.is_file():
            yield item


def get_old_files(path: str | Path, days: int = 30, pattern: str = "*") -> list[Path]:
    """
    Lista arquivos mais antigos que X dias.

    Args:
        path: Caminho do diretório.
        days: Idade mínima em dias.
        pattern: Padrão glob.

    Returns:
        Lista de Paths dos arquivos antigos.
    """
    if days <= 0:
        return []

    cutoff_ts = (datetime.now() - timedelta(days=days)).timestamp()
    old_files: list[Path] = []

    for file_path in iter_files(path, pattern):
        try:
            if file_path.stat().st_mtime < cutoff_ts:
                old_files.append(file_path)
        except (OSError, PermissionError):
            continue

    return old_files


def get_file_hash(path: str | Path, algorithm: str = "md5") -> str:
    """
    Calcula hash de um arquivo.

    Args:
        path: Caminho do arquivo.
        algorithm: Algoritmo (md5, sha1, sha256, ...).

    Returns:
        Hash em hexadecimal.

    Raises:
        FileNotFoundError: Se arquivo não existe.
        ValueError: Se algoritmo inválido.
    """
    p = safe_path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {p}")

    try:
        hasher = hashlib.new(algorithm)
    except ValueError as e:
        raise ValueError(f"Algoritmo inválido: {algorithm}") from e

    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def get_disk_usage(path: str | Path = "/") -> dict[str, int | float]:
    """
    Obtém uso de disco da partição onde `path` está.

    Args:
        path: Caminho na partição (default: "/").

    Returns:
        Dict com total, used, free (bytes) e percent (%).
    """
    p = safe_path(path)
    usage = shutil.disk_usage(p)

    total = usage.total
    used = usage.used
    free = usage.free
    percent = (used / total) * 100 if total > 0 else 0.0

    return {"total": total, "used": used, "free": free, "percent": percent}


# =============================================================================
# Validação
# =============================================================================


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email: str | None) -> bool:
    """
    Valida formato simples de email.

    Args:
        email: String do email (pode ser None).

    Returns:
        True se o formato for válido, senão False.
    """
    if not isinstance(email, str):
        return False

    email = email.strip()
    if not email:
        return False

    return bool(_EMAIL_RE.fullmatch(email))


def is_valid_path(path: str | Path | None) -> bool:
    """
    Verifica se um caminho existe e é acessível.

    Regras:
    - None, "" ou "   " => False
    - Strings com byte nulo => False
    - Caso contrário: safe_path(...).exists()

    Args:
        path: Caminho a verificar.

    Returns:
        True se existir, caso contrário False.
    """
    if path is None:
        return False

    if isinstance(path, str):
        if not path.strip():
            return False
        if "\x00" in path:
            return False

    try:
        return safe_path(path).exists()
    except (OSError, PermissionError, ValueError, TypeError):
        return False


def sanitize_filename(filename: str) -> str:
    """
    Remove caracteres inválidos de nome de arquivo (seguro para Windows e Unix).

    Regras:
    - Troca caracteres proibidos por "_"
    - Remove espaços extras
    - Remove " ." no final (regra do Windows)
    - Evita nomes reservados do Windows (CON, PRN, AUX, NUL, COM1.., LPT1..)
    - Limita tamanho (255 caracteres é um limite típico)

    Args:
        filename: Nome original.

    Returns:
        Nome sanitizado.

    Exemplo:
        >>> sanitize_filename("arquivo:teste?.txt")
        'arquivo_teste_.txt'
    """
    # Caracteres inválidos (Windows e Unix)
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, "_", filename)

    # Normaliza espaços
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    # Windows: não pode terminar com espaço/ponto
    sanitized = sanitized.rstrip(" .")

    # Nomes reservados (Windows)
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }

    name, ext = os.path.splitext(sanitized)
    if name.upper() in reserved:
        sanitized = f"_{name}{ext}"

    # Limite típico de FS
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[: 255 - len(ext)] + ext

    return sanitized or "unnamed"


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Formatação
    "format_size",
    "format_time",
    "format_datetime",
    "format_relative_time",
    # Caminhos
    "safe_path",
    "ensure_dir",
    "get_file_extension",
    "get_file_category",
    "get_unique_filename",
    # Arquivos
    "get_dir_size",
    "count_files",
    "iter_files",
    "get_old_files",
    "get_file_hash",
    "get_disk_usage",
    # Validação
    "is_valid_email",
    "is_valid_path",
    "sanitize_filename",
]
