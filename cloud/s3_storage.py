# type: ignore
"""
AutoTarefas - AWS S3 Integration
================================

Requisitos: pip install boto3
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, BinaryIO

from .base import CloudFile, CloudProvider, CloudStorageBase, DownloadResult, UploadResult

logger = logging.getLogger(__name__)

S3_AVAILABLE = False
boto3 = None
ClientError = Exception
NoCredentialsError = Exception

try:
    import boto3 as boto3_module
    from botocore.exceptions import ClientError as CE
    from botocore.exceptions import NoCredentialsError as NCE

    boto3 = boto3_module
    ClientError = CE
    NoCredentialsError = NCE
    S3_AVAILABLE = True
except ImportError:
    pass


class S3Storage(CloudStorageBase):
    """Integração com Amazon S3."""

    def __init__(
        self,
        bucket_name: str,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region_name: str = "us-east-1",
        endpoint_url: str | None = None,
        credentials: dict[str, Any] | None = None,
    ):
        super().__init__(credentials)
        creds = credentials or {}
        self.bucket_name = bucket_name
        self.aws_access_key_id = aws_access_key_id or creds.get("aws_access_key_id")
        self.aws_secret_access_key = aws_secret_access_key or creds.get("aws_secret_access_key")
        self.region_name = region_name or creds.get("region_name", "us-east-1")
        self.endpoint_url = endpoint_url or creds.get("endpoint_url")
        self._client: Any = None
        self._resource: Any = None

    @property
    def provider(self) -> CloudProvider:
        return CloudProvider.AWS_S3

    def _check_available(self) -> None:
        if not S3_AVAILABLE or boto3 is None:
            raise ImportError("boto3 não instalado. Execute: pip install boto3")

    def connect(self) -> bool:
        self._check_available()
        try:
            session_kwargs: dict[str, Any] = {}
            if self.aws_access_key_id and self.aws_secret_access_key:
                session_kwargs["aws_access_key_id"] = self.aws_access_key_id
                session_kwargs["aws_secret_access_key"] = self.aws_secret_access_key

            session = boto3.Session(**session_kwargs)

            client_kwargs: dict[str, Any] = {"region_name": self.region_name}
            if self.endpoint_url:
                client_kwargs["endpoint_url"] = self.endpoint_url

            self._client = session.client("s3", **client_kwargs)
            self._resource = session.resource("s3", **client_kwargs)

            self._client.head_bucket(Bucket=self.bucket_name)
            self._connected = True
            logger.info(f"Conectado ao S3 bucket: {self.bucket_name}")
            return True
        except NoCredentialsError:
            logger.error("Credenciais AWS não encontradas")
            self._connected = False
            return False
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                logger.error(f"Bucket não encontrado: {self.bucket_name}")
            else:
                logger.error(f"Erro ao conectar ao S3: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        self._client = None
        self._resource = None
        self._connected = False

    def _normalize_key(self, key: str) -> str:
        return key.lstrip("/")

    def upload(
        self,
        local_path: Path,
        remote_path: str,
        overwrite: bool = True,
    ) -> UploadResult:
        if not self._connected or self._client is None:
            return UploadResult.fail("Não conectado")
        if not local_path.exists():
            return UploadResult.fail(f"Arquivo não encontrado: {local_path}")

        start_time = time.time()
        key = self._normalize_key(remote_path)

        try:
            if not overwrite and self.exists(remote_path):
                return UploadResult.fail("Arquivo já existe e overwrite=False")

            file_size = local_path.stat().st_size

            self._client.upload_file(
                str(local_path),
                self.bucket_name,
                key,
                ExtraArgs={"ContentType": self._get_content_type(local_path)},
            )

            response = self._client.head_object(Bucket=self.bucket_name, Key=key)
            etag = response.get("ETag", "").strip('"')

            return UploadResult.ok(
                file_id=key,
                file_url=f"s3://{self.bucket_name}/{key}",
                size=file_size,
                checksum=etag,
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
        if not self._connected or self._client is None:
            return UploadResult.fail("Não conectado")

        start_time = time.time()
        key = self._normalize_key(f"{remote_path}/{filename}".replace("//", "/"))

        try:
            if not overwrite and self.exists(key):
                return UploadResult.fail("Arquivo já existe e overwrite=False")

            self._client.upload_fileobj(stream, self.bucket_name, key)

            response = self._client.head_object(Bucket=self.bucket_name, Key=key)
            etag = response.get("ETag", "").strip('"')
            size = response.get("ContentLength", 0)

            return UploadResult.ok(
                file_id=key,
                file_url=f"s3://{self.bucket_name}/{key}",
                size=size,
                checksum=etag,
                elapsed=time.time() - start_time,
            )
        except Exception as e:
            return UploadResult.fail(str(e))

    def download(self, remote_path: str, local_path: Path) -> DownloadResult:
        if not self._connected or self._client is None:
            return DownloadResult.fail("Não conectado")

        start_time = time.time()
        key = self._normalize_key(remote_path)

        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)

            response = self._client.head_object(Bucket=self.bucket_name, Key=key)
            size = response.get("ContentLength", 0)
            etag = response.get("ETag", "").strip('"')

            self._client.download_file(self.bucket_name, key, str(local_path))

            return DownloadResult.ok(
                local_path=local_path,
                size=size,
                checksum=etag,
                elapsed=time.time() - start_time,
            )
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "Not Found" in error_msg:
                return DownloadResult.fail(f"Arquivo não encontrado: {remote_path}")
            return DownloadResult.fail(str(e))

    def list_files(
        self,
        remote_path: str = "/",
        recursive: bool = False,
    ) -> list[CloudFile]:
        if not self._connected or self._client is None:
            return []

        prefix = self._normalize_key(remote_path)
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        try:
            files = []
            paginator = self._client.get_paginator("list_objects_v2")

            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]

                    if not recursive:
                        relative = key[len(prefix) :]
                        if "/" in relative:
                            continue

                    files.append(
                        CloudFile(
                            id=key,
                            name=Path(key).name,
                            path=str(Path(key).parent),
                            size=obj.get("Size", 0),
                            modified_at=obj.get("LastModified"),
                            checksum=obj.get("ETag", "").strip('"'),
                        )
                    )

            return files
        except Exception as e:
            logger.error(f"Erro ao listar: {e}")
            return []

    def delete(self, remote_path: str) -> bool:
        if not self._connected or self._client is None:
            return False

        key = self._normalize_key(remote_path)

        try:
            self._client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False

    def exists(self, remote_path: str) -> bool:
        if not self._connected or self._client is None:
            return False

        key = self._normalize_key(remote_path)

        try:
            self._client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False

    def get_file_info(self, remote_path: str) -> CloudFile | None:
        if not self._connected or self._client is None:
            return None

        key = self._normalize_key(remote_path)

        try:
            response = self._client.head_object(Bucket=self.bucket_name, Key=key)
            return CloudFile(
                id=key,
                name=Path(key).name,
                path=str(Path(key).parent),
                size=response.get("ContentLength", 0),
                modified_at=response.get("LastModified"),
                mime_type=response.get("ContentType"),
                checksum=response.get("ETag", "").strip('"'),
            )
        except Exception:
            return None

    def create_folder(self, remote_path: str) -> bool:
        """S3 não tem pastas reais."""
        _ = remote_path  # S3 não precisa criar pastas
        return True

    def _get_content_type(self, path: Path) -> str:
        content_types = {
            ".zip": "application/zip",
            ".tar": "application/x-tar",
            ".gz": "application/gzip",
            ".json": "application/json",
            ".txt": "text/plain",
            ".html": "text/html",
            ".pdf": "application/pdf",
        }
        return content_types.get(path.suffix.lower(), "application/octet-stream")

    def get_presigned_url(self, remote_path: str, expiration: int = 3600) -> str | None:
        """Gera URL pré-assinada para download."""
        if not self._connected or self._client is None:
            return None

        key = self._normalize_key(remote_path)

        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expiration,
            )
            return url
        except Exception:
            return None
