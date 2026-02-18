# type: ignore
"""
AutoTarefas - Cloud Backup Task
===============================

Task para fazer backup e enviar para cloud storage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cloud import CloudProvider, CloudStorageBase, get_storage

logger = logging.getLogger(__name__)

# Imports opcionais do autotarefas
AUTOTAREFAS_AVAILABLE = False
BaseTask = object
TaskResult = None
TaskStatus = None
BackupTask = None

try:
    from autotarefas.core.base import BaseTask as BT
    from autotarefas.core.base import TaskResult as TR
    from autotarefas.core.base import TaskStatus as TS
    from autotarefas.tasks.backup import BackupTask as BKT

    BaseTask = BT
    TaskResult = TR
    TaskStatus = TS
    BackupTask = BKT
    AUTOTAREFAS_AVAILABLE = True
except ImportError:
    pass


@dataclass
class CloudBackupTask(BaseTask):
    """
    Task para fazer backup local e enviar para cloud storage.

    Exemplo:
        task = CloudBackupTask(
            name="backup_cloud",
            source=Path("/dados"),
            cloud_provider="google_drive",
            cloud_path="/backups",
            cloud_credentials={"credentials_file": "creds.json"},
        )
        result = task.run()
    """

    source: Path = field(default_factory=Path)
    destination: Path = field(default_factory=lambda: Path("./backups"))
    cloud_provider: str | CloudProvider = CloudProvider.GOOGLE_DRIVE
    cloud_path: str = "/backups"
    cloud_credentials: dict[str, Any] = field(default_factory=dict)
    compression: str = "zip"
    exclude_patterns: list[str] = field(default_factory=list)
    keep_local: bool = True
    max_cloud_backups: int = 10

    def validate(self) -> tuple[bool, str]:
        """Valida os parâmetros da task."""
        if not AUTOTAREFAS_AVAILABLE:
            return False, "autotarefas não está instalado"

        if not self.source:
            return False, "Parâmetro 'source' é obrigatório"

        if not self.source.exists():
            return False, f"Diretório fonte não existe: {self.source}"

        return True, ""

    def execute(self) -> Any:
        """Executa o backup local e upload para cloud."""
        if not AUTOTAREFAS_AVAILABLE:
            raise ImportError("autotarefas não está instalado")

        results: dict[str, Any] = {
            "local_backup": None,
            "cloud_upload": None,
            "local_path": None,
            "cloud_path": None,
        }

        # 1. Backup local
        logger.info(f"Iniciando backup local de: {self.source}")

        backup_task = BackupTask(
            name=f"{self.name}_local",
            source=self.source,
            destination=self.destination,
            compression=self.compression,
            exclude_patterns=self.exclude_patterns,
        )

        local_result = backup_task.run()

        if local_result.status != TaskStatus.SUCCESS:
            return TaskResult.failure(
                task_name=self.name,
                message=f"Falha no backup local: {local_result.message}",
                data=results,
            )

        local_backup_path = Path(local_result.data.get("backup_path", ""))
        results["local_backup"] = local_result.data
        results["local_path"] = str(local_backup_path)

        # 2. Conectar ao cloud
        storage: CloudStorageBase | None = None
        try:
            storage = get_storage(self.cloud_provider, **self.cloud_credentials)
            if not storage.connect():
                return TaskResult.failure(
                    task_name=self.name,
                    message=f"Falha ao conectar ao {self.cloud_provider}",
                    data=results,
                )
        except Exception as e:
            return TaskResult.failure(
                task_name=self.name,
                message=f"Erro ao configurar cloud storage: {e}",
                data=results,
            )

        # 3. Upload
        try:
            remote_path = f"{self.cloud_path.rstrip('/')}/{local_backup_path.name}"
            logger.info(f"Enviando para cloud: {remote_path}")

            upload_result = storage.upload(local_backup_path, remote_path)

            if not upload_result.success:
                storage.disconnect()
                return TaskResult.failure(
                    task_name=self.name,
                    message=f"Falha no upload: {upload_result.error}",
                    data=results,
                )

            results["cloud_upload"] = {
                "file_id": upload_result.file_id,
                "file_url": upload_result.file_url,
                "size": upload_result.size,
                "checksum": upload_result.checksum,
            }
            results["cloud_path"] = remote_path

            # 4. Limpar backups antigos
            if self.max_cloud_backups > 0:
                self._cleanup_old_backups(storage)

            # 5. Remover local se configurado
            if not self.keep_local and local_backup_path.exists():
                local_backup_path.unlink()
                results["local_path"] = None

            storage.disconnect()

            return TaskResult.success(
                task_name=self.name,
                message=f"Backup enviado: {remote_path}",
                data=results,
            )

        except Exception as e:
            if storage:
                storage.disconnect()
            return TaskResult.failure(
                task_name=self.name,
                message=f"Erro durante upload: {e}",
                data=results,
            )

    def _cleanup_old_backups(self, storage: CloudStorageBase) -> None:
        """Remove backups antigos do cloud."""
        try:
            files = storage.list_files(self.cloud_path)
            backup_files = [
                f for f in files if f.extension in [".zip", ".tar", ".gz", ".bz2"]
            ]
            backup_files.sort(
                key=lambda f: f.modified_at or f.created_at, reverse=True
            )

            for old_file in backup_files[self.max_cloud_backups :]:
                full_path = f"{old_file.path}/{old_file.name}".replace("//", "/")
                if storage.delete(full_path):
                    logger.info(f"Backup antigo removido: {old_file.name}")
        except Exception as e:
            logger.warning(f"Erro ao limpar backups antigos: {e}")
