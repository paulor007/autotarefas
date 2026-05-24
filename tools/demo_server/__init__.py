"""
Servidor demo do AutoTarefas.

Mini sistema web Flask usado como alvo controlado das automações
RPA durante desenvolvimento. NÃO é parte do pacote autotarefas.
"""

from __future__ import annotations

from tools.demo_server.app import app, main
from tools.demo_server.storage import Storage

__all__ = ["Storage", "app", "main"]
