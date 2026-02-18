# type: ignore
"""
AutoTarefas - Google Drive Integration
======================================

Requisitos: pip install google-api-python-client google-auth-oauthlib
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

from .base import CloudFile, CloudProvider, CloudStorageBase, DownloadResult, UploadResult

logger = logging.getLogger(__name__)

GOOGLE_AVAILABLE = False
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload

    GOOGLE_AVAILABLE = True
except ImportError:
    Request = None
    Credentials = None
    InstalledAppFlow = None
    build = None
    MediaFileUpload = None
    MediaIoBaseDownload = None
    MediaIoBaseUpload = None

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveStorage(CloudStorageBase):
    """Integração com Google Drive."""

    def __init__(
        self,
        credentials_file: str | Path = "credentials.json",
        token_file: str | Path = "token.json",
        credentials: dict[str, Any] | None = None,
    ):
        super().__init__(credentials)
        self.credentials_file = Path(credentials_file)
        self.token_file = Path(token_file)
        self._service: Any = None
        self._creds: Any = None
        self._folder_cache: dict[str, str] = {}

    @property
    def provider(self) -> CloudProvider:
        return CloudProvider.GOOGLE_DRIVE

    def _check_available(self) -> None:
        if not GOOGLE_AVAILABLE:
            raise ImportError(
                "Google API não instalada. Execute:\npip install google-api-python-client google-auth-oauthlib"
            )

    def connect(self) -> bool:
        self._check_available()
        try:
            creds = None
            if self.token_file.exists():
                creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not self.credentials_file.exists():
                        raise FileNotFoundError(f"Credenciais não encontradas: {self.credentials_file}")
                    flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_file), SCOPES)
                    creds = flow.run_local_server(port=0)

                self.token_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_file, "w") as token:
                    token.write(creds.to_json())

            self._creds = creds
            self._service = build("drive", "v3", credentials=creds)
            self._connected = True
            logger.info("Conectado ao Google Drive!")
            return True
        except Exception as e:
            logger.error(f"Erro ao conectar: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        self._service = None
        self._creds = None
        self._connected = False
        self._folder_cache.clear()

    def _get_or_create_folder(self, folder_path: str) -> str:
        if not self._connected or self._service is None:
            return "root"

        if folder_path in self._folder_cache:
            return self._folder_cache[folder_path]

        parts = [p for p in folder_path.strip("/").split("/") if p]
        if not parts:
            return "root"

        parent_id = "root"
        for part in parts:
            cache_key = f"{parent_id}/{part}"
            if cache_key in self._folder_cache:
                parent_id = self._folder_cache[cache_key]
                continue

            query = (
                f"name='{part}' and '{parent_id}' in parents and "
                f"mimeType='application/vnd.google-apps.folder' and trashed=false"
            )
            results = self._service.files().list(q=query, spaces="drive", fields="files(id)").execute()
            folders = results.get("files", [])

            if folders:
                parent_id = folders[0]["id"]
            else:
                file_metadata = {
                    "name": part,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                }
                folder = self._service.files().create(body=file_metadata, fields="id").execute()
                parent_id = folder["id"]

            self._folder_cache[cache_key] = parent_id

        self._folder_cache[folder_path] = parent_id
        return parent_id

    def upload(
        self,
        local_path: Path,
        remote_path: str,
        overwrite: bool = True,
    ) -> UploadResult:
        if not self._connected or self._service is None:
            return UploadResult.fail("Não conectado")
        if not local_path.exists():
            return UploadResult.fail(f"Arquivo não encontrado: {local_path}")

        start_time = time.time()
        try:
            remote_parts = remote_path.strip("/").rsplit("/", 1)
            folder_path = "/" + remote_parts[0] if len(remote_parts) == 2 else "/"
            filename = remote_parts[-1]

            folder_id = self._get_or_create_folder(folder_path)

            existing_id = None
            if overwrite:
                query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
                results = self._service.files().list(q=query, fields="files(id)").execute()
                files_list = results.get("files", [])
                if files_list:
                    existing_id = files_list[0]["id"]

            file_metadata: dict[str, Any] = {"name": filename}
            if not existing_id:
                file_metadata["parents"] = [folder_id]

            media = MediaFileUpload(str(local_path), resumable=True)

            if existing_id:
                file = (
                    self._service.files()
                    .update(
                        fileId=existing_id,
                        body=file_metadata,
                        media_body=media,
                        fields="id, webViewLink, size, md5Checksum",
                    )
                    .execute()
                )
            else:
                file = (
                    self._service.files()
                    .create(
                        body=file_metadata,
                        media_body=media,
                        fields="id, webViewLink, size, md5Checksum",
                    )
                    .execute()
                )

            return UploadResult.ok(
                file["id"],
                file.get("webViewLink"),
                int(file.get("size", 0)),
                file.get("md5Checksum"),
                time.time() - start_time,
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
        if not self._connected or self._service is None:
            return UploadResult.fail("Não conectado")

        start_time = time.time()
        try:
            folder_id = self._get_or_create_folder(remote_path)

            existing_id = None
            if overwrite:
                query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
                results = self._service.files().list(q=query, fields="files(id)").execute()
                files_list = results.get("files", [])
                if files_list:
                    existing_id = files_list[0]["id"]

            file_metadata: dict[str, Any] = {"name": filename}
            if not existing_id:
                file_metadata["parents"] = [folder_id]

            media = MediaIoBaseUpload(stream, mimetype="application/octet-stream", resumable=True)

            if existing_id:
                file = (
                    self._service.files()
                    .update(
                        fileId=existing_id,
                        body=file_metadata,
                        media_body=media,
                        fields="id, webViewLink, size, md5Checksum",
                    )
                    .execute()
                )
            else:
                file = (
                    self._service.files()
                    .create(
                        body=file_metadata,
                        media_body=media,
                        fields="id, webViewLink, size, md5Checksum",
                    )
                    .execute()
                )

            return UploadResult.ok(
                file["id"],
                file.get("webViewLink"),
                int(file.get("size", 0)),
                file.get("md5Checksum"),
                time.time() - start_time,
            )
        except Exception as e:
            return UploadResult.fail(str(e))

    def download(self, remote_path: str, local_path: Path) -> DownloadResult:
        if not self._connected or self._service is None:
            return DownloadResult.fail("Não conectado")

        start_time = time.time()
        try:
            file_info = self.get_file_info(remote_path)
            if not file_info:
                return DownloadResult.fail(f"Arquivo não encontrado: {remote_path}")

            local_path.parent.mkdir(parents=True, exist_ok=True)
            request = self._service.files().get_media(fileId=file_info.id)

            with open(local_path, "wb") as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()

            return DownloadResult.ok(
                local_path,
                file_info.size,
                file_info.checksum,
                time.time() - start_time,
            )
        except Exception as e:
            return DownloadResult.fail(str(e))

    def list_files(
        self,
        remote_path: str = "/",
        recursive: bool = False,
    ) -> list[CloudFile]:
        if not self._connected or self._service is None:
            return []

        _ = recursive  # Reservado para uso futuro

        try:
            folder_id = self._get_or_create_folder(remote_path)
            query = f"'{folder_id}' in parents and trashed=false"
            query += " and mimeType!='application/vnd.google-apps.folder'"

            results = (
                self._service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name, size, mimeType, createdTime, modifiedTime, md5Checksum)",
                    orderBy="name",
                )
                .execute()
            )

            files = []
            for item in results.get("files", []):
                created = None
                modified = None
                if "createdTime" in item:
                    created = datetime.fromisoformat(item["createdTime"].replace("Z", "+00:00"))
                if "modifiedTime" in item:
                    modified = datetime.fromisoformat(item["modifiedTime"].replace("Z", "+00:00"))

                files.append(
                    CloudFile(
                        id=item["id"],
                        name=item["name"],
                        path=remote_path,
                        size=int(item.get("size", 0)),
                        mime_type=item.get("mimeType"),
                        created_at=created,
                        modified_at=modified,
                        checksum=item.get("md5Checksum"),
                    )
                )
            return files
        except Exception as e:
            logger.error(f"Erro ao listar: {e}")
            return []

    def delete(self, remote_path: str) -> bool:
        if not self._connected or self._service is None:
            return False
        try:
            file_info = self.get_file_info(remote_path)
            if not file_info:
                return False
            self._service.files().update(fileId=file_info.id, body={"trashed": True}).execute()
            return True
        except Exception:
            return False

    def exists(self, remote_path: str) -> bool:
        return self.get_file_info(remote_path) is not None

    def get_file_info(self, remote_path: str) -> CloudFile | None:
        if not self._connected or self._service is None:
            return None

        try:
            remote_parts = remote_path.strip("/").rsplit("/", 1)
            folder_path = "/" + remote_parts[0] if len(remote_parts) == 2 else "/"
            filename = remote_parts[-1]

            folder_id = self._get_or_create_folder(folder_path)
            query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
            results = (
                self._service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name, size, mimeType, createdTime, modifiedTime, md5Checksum)",
                )
                .execute()
            )

            files_list = results.get("files", [])
            if not files_list:
                return None

            item = files_list[0]
            created = None
            modified = None
            if "createdTime" in item:
                created = datetime.fromisoformat(item["createdTime"].replace("Z", "+00:00"))
            if "modifiedTime" in item:
                modified = datetime.fromisoformat(item["modifiedTime"].replace("Z", "+00:00"))

            return CloudFile(
                id=item["id"],
                name=item["name"],
                path=folder_path,
                size=int(item.get("size", 0)),
                mime_type=item.get("mimeType"),
                created_at=created,
                modified_at=modified,
                checksum=item.get("md5Checksum"),
            )
        except Exception:
            return None

    def create_folder(self, remote_path: str) -> bool:
        if not self._connected or self._service is None:
            return False
        try:
            self._get_or_create_folder(remote_path)
            return True
        except Exception:
            return False
