# type: ignore
"""
AutoTarefas - Cloud Storage Module
==================================

Integrações com serviços de armazenamento em nuvem.

Provedores suportados:
    - Google Drive (pip install google-api-python-client google-auth-oauthlib)
    - Dropbox (pip install dropbox)
    - AWS S3 (pip install boto3)
"""

from .base import CloudFile, CloudProvider, CloudStorageBase, DownloadResult, UploadResult
from .dropbox_storage import DropboxStorage
from .google_drive import GoogleDriveStorage
from .s3_storage import S3Storage

__all__ = [
    "CloudProvider",
    "CloudFile",
    "UploadResult",
    "DownloadResult",
    "CloudStorageBase",
    "GoogleDriveStorage",
    "DropboxStorage",
    "S3Storage",
    "get_storage",
]


def get_storage(provider: str | CloudProvider, **kwargs) -> CloudStorageBase:
    """
    Factory para criar instância de storage.

    Args:
        provider: Nome ou enum do provedor (google_drive, dropbox, aws_s3)
        **kwargs: Argumentos específicos do provedor

    Returns:
        Instância do storage configurado
    """
    if isinstance(provider, str):
        provider = CloudProvider(provider.lower())

    providers = {
        CloudProvider.GOOGLE_DRIVE: GoogleDriveStorage,
        CloudProvider.DROPBOX: DropboxStorage,
        CloudProvider.AWS_S3: S3Storage,
    }

    if provider not in providers:
        raise ValueError(f"Provedor não suportado: {provider}")

    return providers[provider](**kwargs)
