"""Arquivos de exemplo (fixtures) para rodar com 1 clique, sem upload.

Permite a experiencia "clicar e executar" mesmo para quem nao quer enviar nada:
o servidor copia estes arquivos ficticios para o workspace e roda a automacao.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

_SAMPLES = Path(__file__).resolve().parent / "assets" / "samples"

# id da automacao -> arquivos de origem (ficticios, versionados em ./assets/samples)
_MAP: dict[str, list[Path]] = {
    "validate": [_SAMPLES / "clientes.csv"],
    "backup": sorted((_SAMPLES / "bagunca").glob("*")),
    "organize": sorted((_SAMPLES / "bagunca").glob("*")),
}


def has_sample(automation_id: str) -> bool:
    """True se ha arquivos de exemplo para a automacao."""
    return automation_id in _MAP


def list_sample(automation_id: str) -> list[dict[str, Any]]:
    """Metadados dos arquivos de exemplo (para o front exibir)."""
    items = _MAP.get(automation_id, [])
    return [{"name": p.name, "bytes": p.stat().st_size} for p in items if p.is_file()]


def copy_sample_to(automation_id: str, in_dir: Path) -> list[Path]:
    """Copia os arquivos de exemplo para `in_dir`. Retorna os caminhos copiados."""
    copied: list[Path] = []
    for src in _MAP.get(automation_id, []):
        if src.is_file():
            dest = in_dir / src.name
            shutil.copy2(src, dest)
            copied.append(dest)
    return copied
