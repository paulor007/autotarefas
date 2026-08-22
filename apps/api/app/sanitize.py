"""Sanitizacao da saida (stdout/stderr) antes de devolver ao visitante.

Remove cores ANSI, mascara CPF, redige possiveis segredos e reescreve caminhos
absolutos para relativos - para nunca vazar o caminho interno do workspace.
"""

from __future__ import annotations

import re
from pathlib import Path

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_SECRET = re.compile(r"(?i)\b(token|secret|api[_-]?key|password|senha)\b\s*[=:]\s*\S+")


def strip_ansi(text: str) -> str:
    """Remove sequencias de escape ANSI (cores)."""
    return _ANSI.sub("", text)


def mask_cpf(text: str) -> str:
    """Mascara CPFs no formato 000.000.000-00."""
    return _CPF.sub("***.***.***-**", text)


def redact_secrets(text: str) -> str:
    """Redige valores que parecem segredos (token=..., senha: ...)."""
    return _SECRET.sub(r"\1=[REDACTED]", text)


def relativize(text: str, *roots: Path) -> str:
    """Reescreve caminhos absolutos conhecidos para relativos."""
    out = text
    for root in roots:
        if not root:
            continue
        base = str(root)
        out = out.replace(base + "/", "").replace(base + "\\", "").replace(base, "")
    return out


def sanitize(text: str, workspace: Path, repo_root: Path) -> str:
    """Pipeline completo de sanitizacao da saida."""
    out = strip_ansi(text or "")
    out = relativize(out, workspace, repo_root)
    out = mask_cpf(out)
    out = redact_secrets(out)
    return out.strip("\n")
