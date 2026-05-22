"""
Helpers de segurança do AutoTarefas.

Funções utilitárias usadas em todo o projeto:

- ``safe_path()`` — valida path contra allowlist (anti path-traversal)
- ``validate_url()`` — valida URL (HTTPS obrigatório em prod)
- ``hash_string()`` — HMAC-SHA256 ou SHA256
- ``validate_filename()`` — bloqueia chars perigosos em nomes
- ``safe_extension()`` — whitelist de extensões permitidas
- ``is_within_directory()`` — path traversal check (retorna bool)
- ``mask_sensitive_in_dict()`` — mascara dados sensíveis em dicts

Uso:
    from autotarefas.core.security import safe_path, validate_url

    # Validar arquivo de input
    arquivo = safe_path("dados/planilha.csv", [Path.home() / "Projetos"])

    # Validar URL antes de fazer request
    url = validate_url("https://api.exemplo.com", environment="prod")

    # Validar nome de arquivo (anti-path-traversal)
    nome_ok = validate_filename("relatorio.pdf")

    # Mascarar dict pra audit log
    safe_data = mask_sensitive_in_dict({"user": "ana", "senha": "123"})
    # -> {"user": "ana", "senha": "***"}
"""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlparse

from autotarefas.core.exceptions import SecurityError

# ============================================================
# Constantes privadas
# ============================================================

#: Keys consideradas sensíveis em dicts (mascaramento automatico).
#: Comparação case-insensitive via substring match.
_SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "password",
        "passwd",
        "senha",
        "secret",
        "token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "cpf",
        "cnpj",
        "rg",
        "credit_card",
        "card_number",
        "card",
        "private_key",
        "session_id",
        "access_key",
    }
)

#: Valor placeholder usado pra mascarar dados sensíveis.
_MASKED_VALUE: Final[str] = "***"

#: Nomes de arquivo reservados no Windows (case-insensitive).
_WINDOWS_RESERVED_NAMES: Final[frozenset[str]] = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
)

#: Caracteres proibidos em nomes de arquivo (Windows + boas práticas).
_FORBIDDEN_FILENAME_CHARS: Final[str] = '<>:"|?*'

#: Tamanho máximo de nome de arquivo (cross-platform seguro).
_MAX_FILENAME_LENGTH: Final[int] = 255


# ============================================================
# Funções (existentes)
# ============================================================


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


# ============================================================
# Funções novas (Fase 6 — Segurança Transversal)
# ============================================================


def validate_filename(name: str) -> str:
    """
    Valida um nome de arquivo (sem path) é seguro pra uso.

    Aplica camadas defensivas:

    1. **Não-vazio**: rejeita strings vazias ou só whitespace.
    2. **Tamanho**: rejeita nomes >255 chars (cross-platform).
    3. **Path separators**: rejeita ``/`` e ``\\\\`` (anti path-traversal).
    4. **Path traversal**: rejeita ``.`` e ``..``.
    5. **Chars de controle**: rejeita 0x00-0x1F (NUL, tab, newline, etc).
    6. **Chars proibidos**: rejeita ``< > : " | ? *`` (Windows + boas práticas).
    7. **Nomes reservados Windows**: rejeita CON, PRN, AUX, NUL,
       COM1-9, LPT1-9 (case-insensitive, com ou sem extensão).

    Args:
        name: Nome do arquivo a validar (apenas nome, sem path).

    Returns:
        O próprio ``name`` se validar com sucesso (sem alterações).

    Raises:
        SecurityError: Se o nome falhar em qualquer camada de validação.

    Examples:
        >>> validate_filename("relatorio.pdf")
        'relatorio.pdf'
        >>> validate_filename("../etc/passwd")
        Traceback (most recent call last):
        ...
        SecurityError: Nome contem path separator: '../etc/passwd'
    """
    # 1. Vazio
    if not name or not name.strip():
        raise SecurityError("Nome de arquivo vazio")

    # 2. Tamanho
    if len(name) > _MAX_FILENAME_LENGTH:
        preview = name[:50]
        raise SecurityError(f"Nome muito longo (>{_MAX_FILENAME_LENGTH} chars): '{preview}...'")

    # 3. Path separators
    if "/" in name or "\\" in name:
        raise SecurityError(f"Nome contem path separator: '{name}'")

    # 4. Path traversal (nomes especiais de navegacao)
    if name in (".", ".."):
        raise SecurityError(f"Nome reservado para navegacao: '{name}'")

    # 5. Chars de controle (0x00 a 0x1F)
    for char in name:
        if ord(char) < 0x20:
            raise SecurityError(f"Nome contem char de controle (0x{ord(char):02x}): {name!r}")

    # 6. Chars proibidos
    for char in _FORBIDDEN_FILENAME_CHARS:
        if char in name:
            raise SecurityError(f"Nome contem char proibido '{char}': '{name}'")

    # 7. Nomes reservados do Windows (verificar tanto com quanto sem extensao)
    # "CON.txt" e "CON" sao ambos reservados — pega o stem
    base = name.split(".", 1)[0].upper()
    if base in _WINDOWS_RESERVED_NAMES:
        raise SecurityError(f"Nome reservado no Windows: '{name}'")

    return name


def safe_extension(filename: str, allowed_extensions: list[str]) -> str:
    """
    Valida que a extensão do arquivo está numa whitelist.

    A comparação é **case-insensitive**. Considera apenas a **última**
    extensão, pra evitar tricks tipo ``arquivo.pdf.exe``.

    Args:
        filename: Nome do arquivo (com extensão).
        allowed_extensions: Lista de extensões permitidas, com ponto
            (ex: ``[".pdf", ".txt"]``).

    Returns:
        A extensão validada, lowercase e com ponto (ex: ``".pdf"``).

    Raises:
        ValueError: Se ``allowed_extensions`` está vazio.
        SecurityError: Se extensão não permitida ou ausente.

    Examples:
        >>> safe_extension("doc.pdf", [".pdf"])
        '.pdf'
        >>> safe_extension("doc.PDF", [".pdf"])
        '.pdf'
        >>> safe_extension("doc.pdf.exe", [".pdf"])
        Traceback (most recent call last):
        ...
        SecurityError: Extensao '.exe' nao permitida...
    """
    if not allowed_extensions:
        raise ValueError("allowed_extensions nao pode ser vazio")

    # .suffix pega APENAS a última extensão (".pdf.exe" -> ".exe")
    actual = Path(filename).suffix.lower()

    if not actual:
        raise SecurityError(f"Arquivo sem extensao: '{filename}'")

    # Normaliza whitelist pra lowercase
    allowed_lower = [ext.lower() for ext in allowed_extensions]

    if actual not in allowed_lower:
        raise SecurityError(
            f"Extensao '{actual}' nao permitida. " f"Permitidas: {allowed_extensions}"
        )

    return actual


def is_within_directory(child: Path | str, parent: Path | str) -> bool:
    """
    Verifica se ``child`` está dentro de ``parent`` (recursivamente).

    Resolve symlinks e ``..`` antes de comparar. Útil pra checar
    path traversal **sem levantar exceção** (forma "soft" do ``safe_path``).

    Args:
        child: Caminho potencialmente dentro de ``parent``.
        parent: Caminho pai.

    Returns:
        ``True`` se ``child`` está dentro de ``parent`` (a qualquer nível).
        ``False`` caso contrário (incluindo casos de erro de resolução).

    Examples:
        >>> is_within_directory("/home/user/file.txt", "/home/user")
        True
        >>> is_within_directory("/etc/passwd", "/home/user")
        False
    """
    try:
        child_resolved = Path(child).expanduser().resolve(strict=False)
        parent_resolved = Path(parent).expanduser().resolve(strict=False)
        child_resolved.relative_to(parent_resolved)
    except (ValueError, OSError):
        return False
    return True


def mask_sensitive_in_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Cria cópia do dict com valores sensíveis mascarados.

    Detecta keys sensíveis por **substring match** (case-insensitive):
    se a key contém qualquer palavra de ``_SENSITIVE_KEYS``, o valor
    é substituído por ``"***"``.

    Sub-dicts são processados recursivamente. **O dict original NÃO
    é modificado** (retorna nova cópia).

    Sensitive keys reconhecidas: password, passwd, senha, secret, token,
    api_key, apikey, auth, authorization, cpf, cnpj, rg, credit_card,
    card_number, card, private_key, session_id, access_key.

    Args:
        data: Dict potencialmente com dados sensíveis.

    Returns:
        Nova cópia do dict com valores sensíveis mascarados como ``"***"``.

    Examples:
        >>> mask_sensitive_in_dict({"user": "ana", "senha": "x123"})
        {'user': 'ana', 'senha': '***'}
        >>> mask_sensitive_in_dict({"api_key": "abc", "data": {"token": "xyz"}})
        {'api_key': '***', 'data': {'token': '***'}}
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()

        # Key sensível: mascara
        if any(sensitive in key_lower for sensitive in _SENSITIVE_KEYS):
            result[key] = _MASKED_VALUE
        # Sub-dict: recursa
        elif isinstance(value, dict):
            result[key] = mask_sensitive_in_dict(value)
        else:
            result[key] = value

    return result


__all__ = [
    "hash_string",
    "is_within_directory",
    "mask_sensitive_in_dict",
    "safe_extension",
    "safe_path",
    "validate_filename",
    "validate_url",
]
