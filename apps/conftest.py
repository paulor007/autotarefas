"""Ambiente comum aos testes de `apps/` — backend e Agente.

Este arquivo existe por um motivo concreto e um pouco traicoeiro: `settings` e
um dataclass **congelado**, criado no `import` do modulo de configuracao. Quem
importa o backend primeiro fixa os valores para a sessao inteira de testes.

Enquanto so o backend tinha suite, o `conftest.py` dele bastava. Quando o
Agente ganhou testes que importam o backend, a ordem alfabetica passou a
carregar `apps/agente` primeiro — e o backend nascia com o limite de requisicao
de PRODUCAO, derrubando meia duzia de testes com 429. O ajuste precisa
acontecer antes de qualquer import, e por isso mora aqui.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Mocks de demonstracao nao sobem: as automacoes locais nao precisam de rede.
os.environ.setdefault("DEMO_SERVERS_AUTOSTART", "0")

# Limite de requisicao alto: a suite dispara muitas execucoes em sequencia, e
# o limite existe para conter visitante, nao teste.
os.environ.setdefault("RATE_LIMIT_PER_MIN", "1000")

os.environ.setdefault(
    "WORKSPACES_ROOT", str(Path(tempfile.gettempdir()) / "autotarefas-live-tests")
)

# Banco em memoria: a suite nao pode criar `autotarefas.db` na raiz do
# repositorio, e um banco compartilhado faria um teste enxergar o dado do
# outro — que e exatamente o que os testes de isolamento medem.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Segredo fixo so na suite: sem ele cada processo sorteia um, e o cookie
# emitido num teste nao seria lido no seguinte.
os.environ.setdefault("SESSION_SECRET", "suite-de-testes-nao-e-producao")  # nosec B105

# A suite NAO pode escrever no Credential Manager da maquina de quem roda os
# testes: sujaria o cofre real e o teste seguinte encontraria a chave deixada
# la, passando por acidente.
os.environ["AUTOTAREFAS_AGENTE_SEM_COFRE"] = "1"

# Higiene: workspaces de execucoes anteriores acumulam e, ao atingir
# MAX_WORKSPACES, todo run passa a responder 503 ("servidor ocupado").
shutil.rmtree(os.environ["WORKSPACES_ROOT"], ignore_errors=True)
