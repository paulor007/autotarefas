# type: ignore
"""
AutoTarefas - Dropbox Integration
=================================

Requisitos: pip install dropbox
"""

from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path
from typing import Any, BinaryIO

from .base import CloudFile, CloudProvider, CloudStorageBase, DownloadResult, UploadResult

logger = logging.getLogger(__name__)

DROPBOX_AVAILABLE = False
dropbox = None

try:
    import dropbox as dropbox_module

    dropbox = dropbox_module
    DROPBOX_AVAILABLE = True
except ImportError:
    pass


class DropboxStorage(CloudStorageBase):
    """Integração com Dropbox."""

    CHUNK_SIZE = 4 * 1024 * 1024  # 4MB

    def __init__(
        self,
        access_token: str | None = None,
        app_key: str | None = None,
        app_secret: str | None = None,
        refresh_token: str | None = None,
        credentials: dict[str, Any] | None = None,
    ):
        super().__init__(credentials)
        creds = credentials or {}
        self.access_token = access_token or creds.get("access_token")
        self.app_key = app_key or creds.get("app_key")
        self.app_secret = app_secret or creds.get("app_secret")
        self.refresh_token = refresh_token or creds.get("refresh_token")
        self._client: Any = None

    @property
    def provider(self) -> CloudProvider:
        return CloudProvider.DROPBOX

    def _check_available(self) -> None:
        if not DROPBOX_AVAILABLE or dropbox is None:
            raise ImportError("Dropbox não instalado. Execute: pip install dropbox")

    def connect(self) -> bool:
        self._check_available()
        try:
            if self.refresh_token and self.app_key and self.app_secret:
                self._client = dropbox.Dropbox(
                    oauth2_refresh_token=self.refresh_token,
                    app_key=self.app_key,
                    app_secret=self.app_secret,
                )
            elif self.access_token:
                self._client = dropbox.Dropbox(self.access_token)
            else:
                raise ValueError("Token de acesso ou refresh token necessário")

            self._client.users_get_current_account()
            self._connected = True
            logger.info("Conectado ao Dropbox!")
            return True
        except Exception as e:
            logger.error(f"Erro ao conectar ao Dropbox: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._client is not None:
            with contextlib.suppress(Exception):
                self._client.close()
        self._client = None
        self._connected = False

    def _normalize_path(self, path: str) -> str:
        path = path.strip()
        if not path or path == "/":
            return ""
        if not path.startswith("/"):
            path = "/" + path
        return path

    def upload(
        self,
        local_path: Path,
        remote_path: str,
        overwrite: bool = True,
    ) -> UploadResult:
        if not self._connected or self._client is None or dropbox is None:
            return UploadResult.fail("Não conectado")
        if not local_path.exists():
            return UploadResult.fail(f"Arquivo não encontrado: {local_path}")

        start_time = time.time()
        remote_path = self._normalize_path(remote_path)
        mode = dropbox.files.WriteMode.overwrite if overwrite else dropbox.files.WriteMode.add

        try:
            file_size = local_path.stat().st_size
            result = None

            with open(local_path, "rb") as f:
                if file_size <= self.CHUNK_SIZE:
                    result = self._client.files_upload(f.read(), remote_path, mode=mode)
                else:
                    upload_session = self._client.files_upload_session_start(f.read(self.CHUNK_SIZE))
                    cursor = dropbox.files.UploadSessionCursor(session_id=upload_session.session_id, offset=f.tell())
                    commit = dropbox.files.CommitInfo(path=remote_path, mode=mode)

                    while f.tell() < file_size:
                        remaining = file_size - f.tell()
                        if remaining <= self.CHUNK_SIZE:
                            result = self._client.files_upload_session_finish(f.read(self.CHUNK_SIZE), cursor, commit)
                        else:
                            self._client.files_upload_session_append_v2(f.read(self.CHUNK_SIZE), cursor)
                            cursor.offset = f.tell()

            if result is None:
                return UploadResult.fail("Upload falhou")

            return UploadResult.ok(
                file_id=result.id,
                size=result.size,
                checksum=result.content_hash,
                elapsed=time.time() - start_time,
            )
        except Exception as e:
            return UploadResult.fail(str(e))

    def upload_stream(
        self,
        stream: BinaryIO,
        remote_path: str,
        filename: str,
        overwrite: bool = True,
    ) -> UploadResult:
        if not self._connected or self._client is None or dropbox is None:
            return UploadResult.fail("Não conectado")

        start_time = time.time()
        full_path = self._normalize_path(f"{remote_path}/{filename}")
        mode = dropbox.files.WriteMode.overwrite if overwrite else dropbox.files.WriteMode.add

        try:
            data = stream.read()
            result = self._client.files_upload(data, full_path, mode=mode)

            return UploadResult.ok(
                file_id=result.id,
                size=result.size,
                checksum=result.content_hash,
                elapsed=time.time() - start_time,
            )
        except Exception as e:
            return UploadResult.fail(str(e))

    def download(self, remote_path: str, local_path: Path) -> DownloadResult:
        if not self._connected or self._client is None:
            return DownloadResult.fail("Não conectado")

        start_time = time.time()
        remote_path = self._normalize_path(remote_path)

        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            metadata, response = self._client.files_download(remote_path)

            with open(local_path, "wb") as f:
                f.write(response.content)

            return DownloadResult.ok(
                local_path=local_path,
                size=metadata.size,
                checksum=metadata.content_hash,
                elapsed=time.time() - start_time,
            )
        except Exception as e:
            return DownloadResult.fail(str(e))

    def list_files(
        self,
        remote_path: str = "/",
        recursive: bool = False,
    ) -> list[CloudFile]:
        if not self._connected or self._client is None:
            return []

        remote_path = self._normalize_path(remote_path)

        try:
            result = self._client.files_list_folder(remote_path, recursive=recursive)
            files = []

            while True:
                for entry in result.entries:
                    if hasattr(entry, "size"):
                        files.append(
                            CloudFile(
                                id=entry.id,
                                name=entry.name,
                                path=str(Path(entry.path_display).parent),
                                size=entry.size,
                                modified_at=getattr(entry, "client_modified", None),
                                checksum=getattr(entry, "content_hash", None),
                            )
                        )

                if not result.has_more:
                    break
                result = self._client.files_list_folder_continue(result.cursor)

            return files
        except Exception as e:
            logger.error(f"Erro ao listar: {e}")
            return []

    def delete(self, remote_path: str) -> bool:
        if not self._connected or self._client is None:
            return False

        remote_path = self._normalize_path(remote_path)

        try:
            self._client.files_delete_v2(remote_path)
            return True
        except Exception:
            return False

    def exists(self, remote_path: str) -> bool:
        return self.get_file_info(remote_path) is not None

    def get_file_info(self, remote_path: str) -> CloudFile | None:
        if not self._connected or self._client is None:
            return None

        remote_path = self._normalize_path(remote_path)

        try:
            metadata = self._client.files_get_metadata(remote_path)
            if hasattr(metadata, "size"):
                return CloudFile(
                    id=metadata.id,
                    name=metadata.name,
                    path=str(Path(metadata.path_display).parent),
                    size=metadata.size,
                    modified_at=getattr(metadata, "client_modified", None),
                    checksum=getattr(metadata, "content_hash", None),
                )
            return None
        except Exception:
            return None

    def create_folder(self, remote_path: str) -> bool:
        if not self._connected or self._client is None:
            return False

        remote_path = self._normalize_path(remote_path)

        try:
            self._client.files_create_folder_v2(remote_path)
            return True
        except Exception as e:
            return "path/conflict/folder" in str(e)

    def get_shared_link(self, remote_path: str) -> str | None:
        """Obtém link compartilhável para um arquivo."""
        if not self._connected or self._client is None:
            return None

        remote_path = self._normalize_path(remote_path)

        try:
            links = self._client.sharing_list_shared_links(path=remote_path).links
            if links:
                return links[0].url
            link = self._client.sharing_create_shared_link_with_settings(remote_path)
            return link.url
        except Exception:
            return None
