"""
Módulo de utilitários do AutoTarefas.

Funções auxiliares usadas em todo o sistema:
    - Formatação: format_size, format_time, format_datetime
    - Caminhos: safe_path, ensure_dir, get_file_extension
    - Arquivos: get_dir_size, count_files, iter_files, get_old_files
    - Validação: is_valid_email, is_valid_path, sanitize_filename

Uso:
    from autotarefas.utils import format_size, safe_path
"""

from __future__ import annotations

from autotarefas.utils.helpers import (  # Formatação; Arquivos; Validação; Caminhos
    count_files,
    ensure_dir,
    format_datetime,
    format_relative_time,
    format_size,
    format_time,
    get_dir_size,
    get_disk_usage,
    get_file_category,
    get_file_extension,
    get_file_hash,
    get_old_files,
    get_unique_filename,
    is_valid_email,
    is_valid_path,
    iter_files,
    safe_path,
    sanitize_filename,
)

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
