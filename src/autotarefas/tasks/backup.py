"""
Task de Backup do AutoTarefas.

Fornece funcionalidades para backup e restauração de arquivos:
    - BackupTask: Cria backups de arquivos/diretórios
    - RestoreTask: Restaura backups anteriores
    - BackupManager: Gerencia versões de backups
    - CompressionType: Tipos de compressão suportados

Uso:
    from autotarefas.tasks import BackupTask

    task = BackupTask()
    result = task.run(
        source="/home/user/documents",
        dest="/backups",
        compression="zip"
    )
"""

from __future__ import annotations

import fnmatch
import tarfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from autotarefas.config import settings
from autotarefas.core.base import BaseTask, TaskResult
from autotarefas.core.logger import logger
from autotarefas.utils.helpers import format_size, safe_path, sanitize_filename

_TarWriteMode = Literal["w", "w:gz", "w:bz2"]
_TarReadMode = Literal["r", "r:gz", "r:bz2"]


class CompressionType(Enum):
    """
    Tipos de compressão suportados para backup.

    Valores:
        ZIP: Formato ZIP (padrão, melhor compatibilidade)
        TAR: Formato TAR sem compressão
        TAR_GZ: Formato TAR com compressão GZIP
        TAR_BZ2: Formato TAR com compressão BZIP2
    """

    ZIP = "zip"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"

    @property
    def extension(self) -> str:
        """Retorna a extensão do arquivo para o tipo de compressão."""
        return f".{self.value}"

    @classmethod
    def from_string(cls, value: str) -> CompressionType:
        """
        Cria CompressionType a partir de string.

        Args:
            value: String do tipo de compressão (ex.: "zip", "tar.gz").

        Returns:
            CompressionType correspondente.

        Raises:
            ValueError: Se tipo não for suportado.
        """
        raw = (value or "").strip().lower()
        for ct in cls:
            if ct.value == raw:
                return ct
        raise ValueError(f"Tipo de compressão não suportado: {value}")


@dataclass
class BackupInfo:
    """
    Informações sobre um backup.

    Attributes:
        path: Caminho do arquivo de backup
        source: Diretório/arquivo original (derivado do nome)
        created_at: Data de criação (mtime do arquivo)
        size_bytes: Tamanho em bytes
        compression: Tipo de compressão detectado
        files_count: Número de arquivos no backup (quando disponível)
    """

    path: Path
    source: Path
    created_at: datetime
    size_bytes: int
    compression: CompressionType
    files_count: int = 0

    @property
    def size_formatted(self) -> str:
        """Retorna o tamanho formatado (ex.: '15.3 MB')."""
        return format_size(self.size_bytes)

    @property
    def age_days(self) -> int:
        """Retorna a idade do backup em dias."""
        return (datetime.now() - self.created_at).days

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário serializável."""
        return {
            "path": str(self.path),
            "source": str(self.source),
            "created_at": self.created_at.isoformat(),
            "size_bytes": self.size_bytes,
            "compression": self.compression.value,
            "files_count": self.files_count,
        }


# =======================================
# Helpers internos (segurança e padrões)
# =======================================


def _is_within_directory(base_dir: Path, target_path: Path) -> bool:
    """
    Garante que target_path está contido dentro de base_dir (anti path traversal).

    Returns:
        True se target_path estiver dentro de base_dir; caso contrário False.
    """
    base = base_dir.resolve()
    target = target_path.resolve()
    try:
        target.relative_to(base)
        return True
    except ValueError:
        return False


def _match_any_pattern(path_str: str, patterns: list[str]) -> bool:
    """
    Retorna True se path_str casar com qualquer pattern glob.

    Args:
        path_str: Caminho em string (idealmente POSIX) para comparar com patterns.
        patterns: Lista de patterns glob (ex.: ["*.tmp", "cache/*"]).

    Returns:
        True se algum pattern casar; caso contrário False.
    """
    pats = [p.strip() for p in patterns if p and p.strip()]
    return any(fnmatch.fnmatch(path_str, pat) for pat in pats)


def _zipinfo_is_symlink(info: zipfile.ZipInfo) -> bool:
    """
    Detecta symlink em ZIP (principalmente em sistemas UNIX) via external_attr.
    Em alguns ZIPs (principalmente Windows), isso pode não estar presente.

    Returns:
        True se a entrada parece ser um symlink.
    """
    mode = (info.external_attr >> 16) & 0o170000
    return mode == 0o120000


class BackupManager:
    """
    Gerenciador de backups.

    Gerencia versões de backup, rotação automática e limpeza.

    Attributes:
        backup_dir: Diretório onde backups são armazenados
        max_versions: Número máximo de versões a manter
    """

    def __init__(
        self,
        backup_dir: str | Path | None = None,
        max_versions: int | None = None,
    ) -> None:
        """
        Inicializa o gerenciador.

        Args:
            backup_dir: Diretório de backups (default: settings.backup.path)
            max_versions: Máximo de versões (default: settings.backup.max_versions)
        """
        self.backup_dir = safe_path(backup_dir or settings.backup.path)
        self.max_versions = int(max_versions or settings.backup.max_versions)

        # Cria diretório se não existir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def generate_backup_name(
        self,
        source: str | Path,
        compression: CompressionType = CompressionType.ZIP,
    ) -> str:
        """
        Gera nome único para backup.

        Args:
            source: Caminho original
            compression: Tipo de compressão

        Returns:
            Nome do arquivo de backup (ex.: documents_20240115_143022.zip)
        """
        source_name = sanitize_filename(Path(source).name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{source_name}_{timestamp}{compression.extension}"

    def _detect_compression(self, backup_path: Path) -> CompressionType:
        """
        Detecta o tipo de compressão com base na extensão do arquivo.

        Returns:
            Tipo de compressão detectado.
        """
        name = backup_path.name.lower()
        if name.endswith(".tar.gz"):
            return CompressionType.TAR_GZ
        if name.endswith(".tar.bz2"):
            return CompressionType.TAR_BZ2
        if name.endswith(".tar"):
            return CompressionType.TAR
        return CompressionType.ZIP

    def _source_from_filename(self, backup_path: Path) -> Path:
        """
        Extrai o "source" (origem) a partir do nome do arquivo de backup.

        Espera um padrão de nome como:
            <source>_YYYYMMDD_HHMMSS.<ext>
        Onde <ext> pode ser: .tar.gz, .tar.bz2, .tar, .zip

        Se o padrão não for reconhecido, usa um fallback baseado no stem do arquivo.
        """
        name = backup_path.name

        # remove extensões conhecidas
        for ext in (".tar.gz", ".tar.bz2", ".tar", ".zip"):
            if name.lower().endswith(ext):
                name = name[: -len(ext)]
                break

        parts = name.rsplit("_", 2)  # espera: [source, YYYYMMDD, HHMMSS]
        if len(parts) == 3 and len(parts[1]) == 8 and len(parts[2]) == 6:
            return Path(parts[0])

        return Path(backup_path.stem)

    def list_backups(self, source_name: str | None = None) -> list[BackupInfo]:
        """
        Lista backups existentes.

        Args:
            source_name: Filtrar por nome do source no arquivo (opcional).

        Returns:
            Lista de BackupInfo ordenada por data (mais recente primeiro).
        """
        backups: list[BackupInfo] = []
        patterns = ["*.zip", "*.tar", "*.tar.gz", "*.tar.bz2"]

        for pattern in patterns:
            for backup_path in self.backup_dir.glob(pattern):
                if source_name and source_name not in backup_path.name:
                    continue

                try:
                    stat = backup_path.stat()
                    compression = self._detect_compression(backup_path)
                    source = self._source_from_filename(backup_path)

                    backups.append(
                        BackupInfo(
                            path=backup_path,
                            source=source,
                            created_at=datetime.fromtimestamp(stat.st_mtime),
                            size_bytes=int(stat.st_size),
                            compression=compression,
                        )
                    )
                except OSError:
                    continue

        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups

    def cleanup_old_backups(self, source_name: str | None = None) -> int:
        """
        Remove backups antigos além do limite de versões.

        Args:
            source_name: Filtrar por nome do source (opcional).

        Returns:
            Número de backups removidos.
        """
        backups = self.list_backups(source_name)

        if len(backups) <= self.max_versions:
            return 0

        removed = 0
        for backup in backups[self.max_versions :]:
            try:
                backup.path.unlink()
                logger.info(f"Backup antigo removido: {backup.path.name}")
                removed += 1
            except OSError as e:
                logger.warning(f"Erro ao remover backup {backup.path}: {e}")

        return removed

    def get_latest_backup(self, source_name: str) -> BackupInfo | None:
        """
        Obtém o backup mais recente de um source.

        Args:
            source_name: Nome do source (parte do arquivo).

        Returns:
            BackupInfo do backup mais recente ou None.
        """
        backups = self.list_backups(source_name)
        return backups[0] if backups else None


class BackupTask(BaseTask):
    """
    Task para criar backups de arquivos e diretórios.

    Suporta múltiplos formatos de compressão e gerenciamento
    automático de versões.
    """

    @property
    def name(self) -> str:
        return "backup"

    @property
    def description(self) -> str:
        return "Cria backup de arquivos e diretórios com compressão"

    def validate(self, **kwargs: Any) -> tuple[bool, str]:
        """Valida parâmetros do backup."""
        source = kwargs.get("source")
        if not source:
            return False, "Parâmetro 'source' é obrigatório"

        source_path = safe_path(source)
        if not source_path.exists():
            return False, f"Source não existe: {source_path}"

        compression = kwargs.get("compression", "zip")
        try:
            CompressionType.from_string(compression)
        except ValueError as e:
            return False, str(e)

        return True, ""

    def execute(
        self,
        source: str | Path,
        dest: str | Path | None = None,
        compression: str = "zip",
        exclude_patterns: list[str] | None = None,
    ) -> TaskResult:
        """
        Executa o backup.

        Args:
            source: Arquivo ou diretório a fazer backup
            dest: Diretório de destino (default: settings.backup.path)
            compression: Tipo de compressão (zip, tar, tar.gz, tar.bz2)
            exclude_patterns: Padrões de arquivos a excluir (glob)

        Returns:
            TaskResult com informações do backup.
        """
        started_at = datetime.now()

        source_path = safe_path(source)
        dest_path = safe_path(dest or settings.backup.path)
        compression_type = CompressionType.from_string(compression)
        exclude_patterns = exclude_patterns or []

        dest_path.mkdir(parents=True, exist_ok=True)

        manager = BackupManager(dest_path)
        source_key = sanitize_filename(source_path.name)

        backup_name = manager.generate_backup_name(source_path, compression_type)
        backup_path = dest_path / backup_name

        logger.info(f"Iniciando backup: {source_path} -> {backup_path}")

        try:
            if compression_type == CompressionType.ZIP:
                files_count = self._create_zip_backup(
                    source_path, backup_path, exclude_patterns
                )
            else:
                files_count = self._create_tar_backup(
                    source_path, backup_path, compression_type, exclude_patterns
                )

            backup_size = backup_path.stat().st_size

            removed = manager.cleanup_old_backups(source_key)

            return TaskResult.success(
                message=f"Backup criado: {backup_name} ({format_size(backup_size)})",
                data={
                    "backup_path": str(backup_path),
                    "source": str(source_path),
                    "size_bytes": int(backup_size),
                    "size_formatted": format_size(int(backup_size)),
                    "files_count": int(files_count),
                    "compression": compression_type.value,
                    "old_backups_removed": int(removed),
                },
                started_at=started_at,
            )

        except Exception as e:
            logger.exception(f"Erro ao criar backup: {e}")

            # Remove backup incompleto
            try:
                if backup_path.exists():
                    backup_path.unlink()
            except OSError:
                pass

            return TaskResult.failure(
                message=f"Falha ao criar backup: {e}",
                error=e,
                started_at=started_at,
            )

    def _create_zip_backup(
        self,
        source: Path,
        dest: Path,
        exclude_patterns: list[str],
    ) -> int:
        """Cria backup em formato ZIP."""
        files_count = 0

        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            if source.is_file():
                if source.is_symlink():
                    logger.warning(f"[backup] Ignorando symlink: {source}")
                    return 0
                zf.write(source, arcname=source.name)
                return 1

            root = Path(source.name)
            for file_path in source.rglob("*"):
                if not file_path.is_file():
                    continue
                if file_path.is_symlink():
                    continue

                rel = root / file_path.relative_to(source)
                rel_str = rel.as_posix()

                if _match_any_pattern(rel_str, exclude_patterns):
                    continue

                try:
                    zf.write(file_path, arcname=rel_str)
                    files_count += 1
                except (OSError, PermissionError):
                    logger.warning(f"[backup] Sem permissão para ler: {file_path}")
                    continue

        return files_count

    def _create_tar_backup(
        self,
        source: Path,
        dest: Path,
        compression: CompressionType,
        exclude_patterns: list[str],
    ) -> int:
        """Cria backup em formato TAR."""
        mode_map: dict[CompressionType, _TarWriteMode] = {
            CompressionType.TAR: "w",
            CompressionType.TAR_GZ: "w:gz",
            CompressionType.TAR_BZ2: "w:bz2",
        }

        mode: _TarWriteMode = mode_map[compression]
        files_count = 0

        def filter_func(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
            nonlocal files_count

            name_in_tar = tarinfo.name  # ex: "Documents/file.txt"
            if _match_any_pattern(name_in_tar, exclude_patterns):
                return None

            if tarinfo.issym() or tarinfo.islnk():
                return None

            if tarinfo.isfile():
                files_count += 1

            return tarinfo

        with tarfile.open(name=str(dest), mode=mode) as tf:
            tf.add(source, arcname=source.name, filter=filter_func)

        return files_count


class RestoreTask(BaseTask):
    """Task para restaurar backups."""

    @property
    def name(self) -> str:
        return "restore"

    @property
    def description(self) -> str:
        return "Restaura arquivos de um backup"

    def validate(self, **kwargs: Any) -> tuple[bool, str]:
        """Valida parâmetros da restauração."""
        backup_path = kwargs.get("backup_path")
        if not backup_path:
            return False, "Parâmetro 'backup_path' é obrigatório"

        path = safe_path(backup_path)
        if not path.exists():
            return False, f"Backup não encontrado: {path}"
        if not path.is_file():
            return False, f"Caminho não é um arquivo: {path}"

        return True, ""

    def execute(
        self,
        backup_path: str | Path,
        dest: str | Path | None = None,
        overwrite: bool = False,
    ) -> TaskResult:
        """
        Restaura um backup.

        Args:
            backup_path: Caminho do arquivo de backup
            dest: Diretório de destino (default: diretório atual)
            overwrite: Se deve sobrescrever arquivos existentes

        Returns:
            TaskResult com informações da restauração.
        """
        started_at = datetime.now()

        backup_path_p = safe_path(backup_path)
        dest_path = safe_path(dest or Path.cwd())

        logger.info(f"Restaurando backup: {backup_path_p} -> {dest_path}")

        try:
            dest_path.mkdir(parents=True, exist_ok=True)

            name = backup_path_p.name.lower()

            if name.endswith(".zip"):
                files_count = self._restore_zip(backup_path_p, dest_path, overwrite)
            elif name.endswith((".tar", ".tar.gz", ".tar.bz2")):
                files_count = self._restore_tar(backup_path_p, dest_path, overwrite)
            else:
                return TaskResult.failure(
                    message=f"Formato de backup não suportado: {backup_path_p.suffix}",
                    started_at=started_at,
                )

            return TaskResult.success(
                message=f"Backup restaurado: {files_count} arquivos",
                data={
                    "backup_path": str(backup_path_p),
                    "dest": str(dest_path),
                    "files_count": int(files_count),
                },
                started_at=started_at,
            )

        except Exception as e:
            logger.exception(f"Erro ao restaurar backup: {e}")
            return TaskResult.failure(
                message=f"Falha ao restaurar backup: {e}",
                error=e,
                started_at=started_at,
            )

    def _restore_zip(self, backup: Path, dest: Path, overwrite: bool) -> int:
        """Restaura backup ZIP."""
        files_count = 0
        dest_resolved = dest.resolve()

        with zipfile.ZipFile(backup, "r") as zf:
            for info in zf.infolist():
                if _zipinfo_is_symlink(info):
                    logger.warning(f"Symlink no zip ignorado: {info.filename}")
                    continue

                member = Path(info.filename)

                if member.is_absolute() or ".." in member.parts:
                    logger.warning(
                        f"Entrada suspeita no zip, ignorando: {info.filename}"
                    )
                    continue

                target = dest / member

                if not _is_within_directory(dest_resolved, target):
                    logger.warning(
                        f"Entrada fora do destino, ignorando: {info.filename}"
                    )
                    continue

                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                if target.exists() and not overwrite:
                    logger.warning(f"Já existe, pulando: {target}")
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)
                zf.extract(info, dest)
                files_count += 1

        return files_count

    def _restore_tar(self, backup: Path, dest: Path, overwrite: bool) -> int:
        """Restaura backup TAR."""
        files_count = 0
        dest_resolved = dest.resolve()

        mode: _TarReadMode
        if backup.name.lower().endswith(".tar.gz"):
            mode = "r:gz"
        elif backup.name.lower().endswith(".tar.bz2"):
            mode = "r:bz2"
        else:
            mode = "r"

        with tarfile.open(backup, mode) as tf:
            for member in tf.getmembers():
                member_path = Path(member.name)

                # Prevenção de Tar Slip (path traversal).
                if member_path.is_absolute() or ".." in member_path.parts:
                    logger.warning(f"Entrada suspeita no tar, ignorando: {member.name}")
                    continue

                # Bloquear links no tar por segurança (symlink/hardlink).
                if member.issym() or member.islnk():
                    logger.warning(f"Link no tar ignorado: {member.name}")
                    continue

                target = dest / member_path
                if not _is_within_directory(dest_resolved, target):
                    logger.warning(f"Entrada fora do destino, ignorando: {member.name}")
                    continue

                if target.exists() and not overwrite:
                    logger.warning(f"Já existe, pulando: {target}")
                    continue

                tf.extract(member, dest)
                if member.isfile():
                    files_count += 1

        return files_count


__all__ = [
    "CompressionType",
    "BackupInfo",
    "BackupManager",
    "BackupTask",
    "RestoreTask",
]
