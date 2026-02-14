"""
Utilitários de JSON do AutoTarefas.

Inclui escrita atômica para evitar arquivos corrompidos em caso de:
- queda de energia
- interrupção no meio da gravação
- exceções inesperadas
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path, data: dict[str, Any], *, indent: int = 2) -> None:
    """
    Escrita atômica:
    - escreve em arquivo temporário no mesmo diretório
    - replace() para o destino final
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)

    tmp.replace(path)


def json_dumps(obj: dict[str, Any] | None) -> str | None:
    """Dumps seguro para dict (retorna None se obj for None)."""
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False)


def json_loads(value: str | None) -> dict[str, Any]:
    """Loads seguro: garante dict e evita quebrar se JSON vier inválido."""
    if not value:
        return {}

    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}
