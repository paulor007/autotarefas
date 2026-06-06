"""
Sistema de logging do AutoTarefas (loguru com mascaramento automático).

Mascara dados sensíveis (CPF, CNPJ, email, senha, token, Bearer)
ANTES de gravar nos sinks.

Uso:
    from autotarefas.core.logger import logger

    logger.info("Processando arquivo: {path}", path="/tmp/x.csv")
    logger.error("Erro de login: {user}", user="paulo@gmail.com")
    # Logado como: "Erro de login: p***@gmail.com"
"""

from __future__ import annotations

import re
import sys
from typing import Any

from loguru import logger

from autotarefas.core.settings import settings

# ============================================================
# Padrões de mascaramento (regex → substituição)
# ============================================================

# Cada item é (regex_compilada, substituição).
# Substituição pode ser str ou callable (re.sub aceita ambos).
SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], Any]] = [
    # CPF: 123.456.789-00
    (
        re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
        "***.***.***-XX",
    ),
    # CNPJ: 12.345.678/0001-90
    (
        re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),
        "**.***.***/****-**",
    ),
    # Senhas em qualquer formato (password=, pwd=, senha=)
    (
        re.compile(r"\b(password|pwd|senha)\s*[=:]\s*\S+", re.IGNORECASE),
        r"\1=***",
    ),
    # Tokens (token=, api_key=, api-key=)
    (
        re.compile(r"\b(token|api[_-]?key)\s*[=:]\s*\S+", re.IGNORECASE),
        r"\1=***",
    ),
    # Bearer tokens em headers HTTP
    (
        re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE),
        "Bearer ***",
    ),
    # Email: mantém primeira letra + domínio (ex: paulo@x.com → p***@x.com)
    (
        re.compile(r"\b([a-zA-Z0-9._%+-])[a-zA-Z0-9._%+-]*" r"@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b"),
        r"\1***@\2",
    ),
]


def mask_sensitive(message: str) -> str:
    """
    Mascara dados sensíveis em mensagem de log.

    Aplica TODOS os padrões em ``SENSITIVE_PATTERNS``.

    Args:
        message: Texto original.

    Returns:
        Texto com dados sensíveis mascarados.

    Examples:
        >>> mask_sensitive("CPF: 123.456.789-00")
        'CPF: ***.***.***-XX'

        >>> mask_sensitive("user paulo@gmail.com")
        'user p***@gmail.com'

        >>> mask_sensitive("password=segredo123")
        'password=***'
    """
    for pattern, replacement in SENSITIVE_PATTERNS:
        message = pattern.sub(replacement, message)
    return message


def _mask_patcher(record: Any) -> None:
    """
    Patcher do loguru: mascara ``record["message"]`` antes dos sinks.

    Esse patcher é aplicado em TODAS as mensagens, em TODOS os sinks.

    Note: usamos ``Any`` em vez de ``loguru.Record`` porque o stub do
    loguru não exporta esse tipo de forma estável entre versões.
    """
    record["message"] = mask_sensitive(record["message"])


def configure_logger() -> None:
    """
    Configura o logger global com:

    - Mascaramento automático de dados sensíveis
    - Sink no console (stderr) com cores
    - Sink em arquivo (rotação diária + retenção 30 dias + compressão zip)
    """
    # Remove qualquer config padrão (loguru vem com um sink default)
    logger.remove()

    # Aplica patcher de mascaramento — vale para TODOS os sinks abaixo
    logger.configure(patcher=_mask_patcher)

    # ---------- Sink: console (stderr) ----------
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level:8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # ---------- Sink: arquivo ----------
    # Cria pasta de logs (se não existir)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = settings.logs_dir / "autotarefas_{time:YYYY-MM-DD}.log"

    logger.add(
        str(log_file),
        level=settings.log_level,
        format=("{time:YYYY-MM-DD HH:mm:ss} | {level:8} | {name}:{function}:{line} - {message}"),
        rotation="00:00",  # Rotaciona à meia-noite
        retention="30 days",  # Mantém 30 dias de logs
        compression="zip",  # Compacta logs antigos
        enqueue=True,  # Async-safe (multi-thread/process)
        encoding="utf-8",
    )


# Configura ao importar o módulo
configure_logger()


__all__ = ["configure_logger", "logger", "mask_sensitive"]
