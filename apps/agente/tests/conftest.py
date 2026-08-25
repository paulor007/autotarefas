"""Configuracao dos testes do Agente.

O ambiente comum esta em `apps/conftest.py`. Em especial, e la que o cofre do
sistema operacional e desligado: sem isso, um teste da linha de comando cria
uma identidade no Credential Manager real de quem roda a suite.
"""

from __future__ import annotations
