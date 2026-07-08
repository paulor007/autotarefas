"""Configuracao dos testes do backend do Live System.

Isola os testes da suite principal: insere a raiz do repo no path, desliga a
subida dos mocks (as automacoes locais nao precisam de rede) e aponta os
workspaces para um diretorio temporario de teste.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

os.environ.setdefault("DEMO_SERVERS_AUTOSTART", "0")
os.environ.setdefault("RATE_LIMIT_PER_MIN", "1000")
os.environ.setdefault(
    "WORKSPACES_ROOT", str(Path(tempfile.gettempdir()) / "autotarefas-live-tests")
)

# Higiene: workspaces de execucoes anteriores acumulam neste diretorio e,
# ao atingir MAX_WORKSPACES, todo run passa a responder 503 ("servidor
# ocupado"). Cada sessao de testes comeca do zero.
shutil.rmtree(os.environ["WORKSPACES_ROOT"], ignore_errors=True)
