"""
Configuracao compartilhada dos testes (pytest).

ISOLAMENTO DO AUDIT DB
======================
O AutoTarefas grava um audit trail em SQLite cujo caminho deriva de
`settings.autotarefas_home` (default: ~/.autotarefas/audit.db). Como
`settings` e `audit` sao singletons criados na importacao, rodar a
suite poderia gravar no audit REAL do usuario.

Para evitar isso, este modulo:

1. Redireciona AUTOTAREFAS_HOME para um diretorio temporario ANTES de
   qualquer import do projeto -> os singletons nascem apontando para o
   tmp, e nada toca ~/.autotarefas.
2. Fornece uma fixture `autouse` que aponta o audit do singleton para o
   `tmp_path` de cada teste -> cada teste tem um audit limpo e isolado.

Destino deste arquivo:
    tests/conftest.py
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# ------------------------------------------------------------
# (1) Redireciona o home ANTES de importar settings/audit.
#     setdefault respeita um AUTOTAREFAS_HOME ja definido no ambiente.
# ------------------------------------------------------------
os.environ.setdefault(
    "AUTOTAREFAS_HOME",
    str(Path(tempfile.mkdtemp(prefix="autotarefas-tests-"))),
)

from autotarefas.core.audit import AuditTrail, audit


@pytest.fixture(autouse=True)
def _isolate_audit_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Isola o audit DB por teste.

    Aponta o singleton `audit` para um arquivo dentro do `tmp_path` do
    teste (limpo automaticamente pelo pytest). Garante que cada teste
    comece com um audit vazio e que nada seja gravado fora do tmp.
    """
    test_db = tmp_path / "audit.db"
    # O __init__ de AuditTrail cria a tabela no caminho informado.
    _ = AuditTrail(db_path=test_db)
    monkeypatch.setattr(audit, "db_path", test_db)
