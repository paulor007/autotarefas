"""
Helpers de segurança do AutoTarefas.

Funções utilitárias usadas em todo o projeto:

- ``safe_path()`` — valida path contra allowlist (anti path-traversal)
- ``validate_url()`` — valida URL (HTTPS obrigatório em prod)
- ``hash_string()`` — HMAC-SHA256 ou SHA256

Uso:
    from autotarefas.core.security import safe_path, validate_url

    # Validar arquivo de input
    arquivo = safe_path("dados/planilha.csv", [Path.home() / "Projetos"])

    # Validar URL antes de fazer request
    url = validate_url("https://api.exemplo.com", environment="prod")
"""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from urllib.parse import urlparse

from autotarefas.core.exceptions import SecurityError


def safe_path(path: Path | str, allowed_roots: list[Path]) -> Path:
    """
    Valida que ``path`` está dentro de uma das ``allowed_roots``.

    Protege contra **path traversal attacks** (ex: caminhos com ``..``).
    Resolve symlinks e ``~`` antes de validar.

    Args:
        path: Caminho a validar (string ou Path).
        allowed_roots: Lista de pastas raiz permitidas.

    Returns:
        Path absoluto e resolvido (dentro de uma das ``allowed_roots``).

    Raises:
        ValueError: Se ``allowed_roots`` está vazio.
        SecurityError: Se ``path`` não está em nenhuma ``allowed_root``.
    """
    if not allowed_roots:
        raise ValueError("allowed_roots não pode ser vazio")

    resolved = Path(path).expanduser().resolve(strict=False)

    for root in allowed_roots:
        root_resolved = root.expanduser().resolve(strict=False)
        try:
            resolved.relative_to(root_resolved)
            return resolved
        except ValueError:
            continue

    raise SecurityError(f"Path '{path}' nao esta em nenhum diretorio permitido")


def validate_url(url: str, *, environment: str = "dev") -> str:
    """
    Valida uma URL. Em produção, exige HTTPS.

    Args:
        url: URL pra validar.
        environment: 'dev', 'demo', 'homolog', 'prod'.

    Returns:
        URL validada (mesma string, com strip de whitespace).

    Raises:
        SecurityError: Se URL for inválida ou inseguro pra produção.
    """
    if not url or not url.strip():
        raise SecurityError("URL vazia")

    url = url.strip()
    parsed = urlparse(url)

    if not parsed.scheme:
        raise SecurityError(f"URL sem schema: {url}")

    if parsed.scheme not in ("http", "https"):
        raise SecurityError(f"Schema nao suportado: {parsed.scheme} (URL: {url})")

    if not parsed.netloc:
        raise SecurityError(f"URL sem host: {url}")

    if environment == "prod" and parsed.scheme != "https":
        raise SecurityError(f"URL HTTP nao permitida em producao: {url}")

    return url


def hash_string(data: str, secret: str | None = None) -> str:
    """
    Calcula hash de uma string.

    Se ``secret`` for fornecido, usa HMAC-SHA256.
    Caso contrário, SHA-256 puro.

    Args:
        data: String a hashear.
        secret: Chave HMAC (opcional). Se None/vazia, usa SHA-256.

    Returns:
        Hash hexadecimal (64 caracteres).
    """
    if secret:
        return hmac.new(
            secret.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


__all__ = ["hash_string", "safe_path", "validate_url"]
