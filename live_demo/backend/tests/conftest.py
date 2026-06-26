"""Configuracao dos testes do backend do Live System.

Isola os testes da suite principal: insere a raiz do repo no path, desliga a
subida dos mocks (as automacoes locais nao precisam de rede) e aponta os
workspaces para um diretorio temporario de teste.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

os.environ.setdefault("DEMO_SERVERS_AUTOSTART", "0")
os.environ.setdefault(
    "WORKSPACES_ROOT", str(Path(tempfile.gettempdir()) / "autotarefas-live-tests")
)
