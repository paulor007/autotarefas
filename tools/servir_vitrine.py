"""Sobe o Live apontado para o banco da vitrine.

Existe porque o ambiente publico e outro banco, outro endereco e outra
configuracao — e acertar as tres na mao, toda vez, e como o link impresso
apontando para a porta errada nasceu.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from tools import vitrine  # noqa: E402


def main() -> None:
    vitrine._preparar_ambiente()
    import os

    os.environ["PUBLIC_BASE_URL"] = "http://localhost:7860"

    import uvicorn

    uvicorn.run("apps.api.app.main:app", host="127.0.0.1", port=7860)


if __name__ == "__main__":
    main()
