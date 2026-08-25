"""Banco em uso pelo servico.

Um ponto so para pegar o banco, e um ponto so para trocar. A suite troca por
um banco proprio; producao usa o de `DATABASE_URL`. Sem esse ponto unico, cada
rota abriria a propria conexao e um teste acabaria escrevendo no banco de
desenvolvimento — ou pior, lendo o dado de outro teste.
"""

from __future__ import annotations

from ..config import settings
from .sessao import Banco

_banco: Banco | None = None


def banco() -> Banco:
    """
    Devolve o banco em uso, criando o esquema na primeira chamada.

    Criacao preguicosa de proposito: importar o modulo nao pode tocar em
    disco nem em rede, senao qualquer `import` dispara conexao.
    """
    global _banco
    if _banco is None:
        _banco = Banco(settings.database_url or None)
        _banco.criar_esquema()
    return _banco


def definir_banco(novo: Banco | None) -> None:
    """Troca o banco em uso. Usado pela suite e pelo encerramento do servico."""
    global _banco
    if _banco is not None and _banco is not novo:
        _banco.descartar()
    _banco = novo


__all__ = ["banco", "definir_banco"]
