"""Configuracao dos testes do Agente.

Uma linha carrega todo o peso: a suite **nao pode** escrever no Credential
Manager da maquina de quem roda os testes. Sem isto, um teste da linha de
comando cria uma identidade no cofre real do desenvolvedor — e o teste
seguinte a encontra e passa por acidente, escondendo um defeito.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

os.environ["AUTOTAREFAS_AGENTE_SEM_COFRE"] = "1"

# O Agente conversa com o backend nos testes de ponta a ponta; o backend sobe
# um banco na partida e nao pode criar arquivo na raiz do repositorio.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SESSION_SECRET", "suite-de-testes-nao-e-producao")  # nosec B105
os.environ.setdefault("DEMO_SERVERS_AUTOSTART", "0")
