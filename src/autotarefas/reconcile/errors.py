"""
Erros do modulo de reconciliacao.

Um erro daqui significa sempre a mesma coisa: **o pedido nao se aplica a
estes arquivos** (chave inexistente, tolerancia mal escrita, fonte
ilegivel). Nao e "as bases diferem" — divergencia e resultado do trabalho,
nao falha. Quem chama traduz isso em codigo de saida 2 (erro de uso).
"""

from __future__ import annotations

from autotarefas.core.exceptions import AutoTarefasError


class CompareError(AutoTarefasError):
    """A comparacao/reconciliacao pedida nao pode ser executada."""


__all__ = ["CompareError"]
