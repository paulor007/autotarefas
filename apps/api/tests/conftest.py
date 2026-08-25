"""Configuracao dos testes do backend do Live System.

O ambiente comum (limites, banco em memoria, segredo de sessao, workspaces)
esta em `apps/conftest.py`, que o pytest carrega antes deste — e antes de
qualquer import do backend, que e o que importa: `settings` e congelado no
import e nao muda depois.
"""

from __future__ import annotations
