# type: ignore
"""
AutoTarefas - Cloud Storage Base
================================

Módulo base para integrações com serviços de armazenamento em nuvem.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO


class CloudProvider(Enum):
    """Provedores de cloud suportados."""

    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"
    AWS_S3 = "aws_s3"


@dataclass
class CloudFile:
    """Representa um arquivo no cloud storage."""

    id: str
    name: str
    path: str
    size: int
    modified_at: datetime | None = None
    created_at: datetime | None = None
    mime_type: str | None = None
    checksum: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def extension(self) -> str:
        """Retorna a extensão do arquivo."""
        return Path(self.name).suffix.lower()

    def __str__(self) -> str:
        return f"{self.path}/{self.name} ({self.size} bytes)"


@dataclass
class UploadResult:
    """Resultado de um upload."""

    success: bool
    file_id: str | None = None
    file_url: str | None = None
    size: int = 0
    checksum: str | None = None
    error: str | None = None
    elapsed_seconds: float = 0.0

    @classmethod
    def ok(
        cls,
        file_id: str,
        file_url: str | None = None,
        size: int = 0,
        checksum: str | None = None,
        elapsed: float = 0.0,
    ) -> UploadResult:
        return cls(
            success=True,
            file_id=file_id,
            file_url=file_url,
            size=size,
            checksum=checksum,
            elapsed_seconds=elapsed,
        )

    @classmethod
    def fail(cls, error: str) -> UploadResult:
        return cls(success=False, error=error)


@dataclass
class DownloadResult:
    """Resultado de um download."""

    success: bool
    local_path: Path | None = None
    size: int = 0
    checksum: str | None = None
    error: str | None = None
    elapsed_seconds: float = 0.0

    @classmethod
    def ok(
        cls,
        local_path: Path,
        size: int = 0,
        checksum: str | None = None,
        elapsed: float = 0.0,
    ) -> DownloadResult:
        return cls(
            success=True,
            local_path=local_path,
            size=size,
            checksum=checksum,
            elapsed_seconds=elapsed,
        )

    @classmethod
    def fail(cls, error: str) -> DownloadResult:
        return cls(success=False, error=error)


class CloudStorageBase(ABC):
    """Classe base abstrata para provedores de cloud storage."""

    def __init__(self, credentials: dict[str, Any] | None = None):
        self.credentials = credentials or {}
        self._connected = False

    @property
    @abstractmethod
    def provider(self) -> CloudProvider:
        pass

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def upload(
        self,
        local_path: Path,
        remote_path: str,
        overwrite: bool = True,
    ) -> UploadResult:
        pass

    @abstractmethod
    def upload_stream(
        self,
        stream: BinaryIO,
        remote_path: str,
        filename: str,
        overwrite: bool = True,
    ) -> UploadResult:
        pass

    @abstractmethod
    def download(self, remote_path: str, local_path: Path) -> DownloadResult:
        pass

    @abstractmethod
    def list_files(
        self,
        remote_path: str = "/",
        recursive: bool = False,
    ) -> list[CloudFile]:
        pass

    @abstractmethod
    def delete(self, remote_path: str) -> bool:
        pass

    @abstractmethod
    def exists(self, remote_path: str) -> bool:
        pass

    @abstractmethod
    def get_file_info(self, remote_path: str) -> CloudFile | None:
        pass

    def create_folder(self, remote_path: str) -> bool:
        """Cria uma pasta no cloud (implementação padrão)."""
        _ = remote_path  # Argumento usado em subclasses
        return False

    def __enter__(self) -> CloudStorageBase:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.disconnect()

    def __repr__(self) -> str:
        status = "conectado" if self._connected else "desconectado"
        return f"<{self.__class__.__name__} ({status})>"
