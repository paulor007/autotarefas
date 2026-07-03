"""Recepcao e validacao segura dos uploads do visitante.

Salva cada arquivo no diretorio `in/` do workspace com nome sanitizado, valida a
extensao contra a allowlist e corta no streaming ao exceder o limite de tamanho.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from .config import settings

_CHUNK = 64 * 1024


class UploadError(Exception):
    """Erro de validacao de upload (vira 4xx no main)."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def safe_name(filename: str | None) -> str:
    """Reduz a um basename seguro; rejeita vazio e travessia de caminho."""
    name = Path(filename or "").name.strip()
    if not name or name in {".", ".."}:
        raise UploadError(400, "nome de arquivo invalido")
    return name


def _check_ext(name: str, allowed: tuple[str, ...]) -> None:
    ext = Path(name).suffix.lower()
    if ext not in allowed:
        raise UploadError(415, f"extensao nao permitida: {ext or '(sem extensao)'}")


async def save_uploads(
    files: list[UploadFile],
    in_dir: Path,
    *,
    allowed_exts: tuple[str, ...] | None = None,
) -> list[Path]:
    """
    Valida e salva os uploads em `in_dir`. Retorna os caminhos salvos.

    Args:
        files: Arquivos enviados pelo visitante.
        in_dir: Diretorio `in/` do workspace.
        allowed_exts: Extensoes aceitas para esta automacao (ex.
            ``(".csv", ".xlsx")``). Se None, vale a allowlist geral
            de `settings.allowed_upload_extensions`.
    """
    if not files:
        raise UploadError(400, "nenhum arquivo enviado")
    if len(files) > settings.max_upload_files:
        raise UploadError(413, f"maximo de {settings.max_upload_files} arquivos por envio")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    allowed = allowed_exts if allowed_exts is not None else settings.allowed_upload_extensions
    saved: list[Path] = []
    total = 0

    for upload in files:
        name = safe_name(upload.filename)
        _check_ext(name, allowed)
        dest = in_dir / name
        with dest.open("wb") as handle:
            while True:
                chunk = await upload.read(_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    handle.close()
                    dest.unlink(missing_ok=True)
                    raise UploadError(413, f"upload excede {settings.max_upload_mb} MB")
                handle.write(chunk)
        await upload.close()
        saved.append(dest)

    return saved
