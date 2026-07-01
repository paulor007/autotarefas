"""
Deteccao de duplicatas em planilhas (analise *cross-row*).

Diferente dos validadores de `validators.py`, que olham uma celula por
vez, este modulo compara linhas/valores ENTRE SI — algo que so faz
sentido com a planilha inteira em maos.

Funcoes puras (sem estado, sem I/O) que trabalham com indices 0-based.
A conversao indice → numero de linha (ex. +2, por causa do cabecalho)
e responsabilidade de quem chama (a ValidateTask).

Duas deteccoes:
- `find_duplicate_values` — valores repetidos em UMA coluna (ex. CPF,
  e-mail). Aceita uma funcao `key` para normalizar antes de comparar
  ("111.444.777-35" e "11144477735" sao o mesmo CPF).
- `find_duplicate_rows` — linhas 100% identicas (todas as colunas iguais).

Uso:
    from autotarefas.tasks.duplicates import (
        find_duplicate_values, normalize_digits,
    )

    cpfs = ["111.444.777-35", "999...", "11144477735"]
    find_duplicate_values(cpfs, key=normalize_digits)
    # → {"11144477735": [0, 2]}
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

# ============================================================
# Normalizadores (chaves de comparacao)
# ============================================================


def normalize_text(value: str) -> str:
    """
    Normaliza texto para comparacao: remove espacos das pontas e ignora
    caixa (``casefold`` e mais agressivo que ``lower`` para Unicode).

    Exemplos:
        " Ana Lima "  → "ana lima"
        "ANA@X.COM"   → "ana@x.com"
    """
    return value.strip().casefold()


def normalize_digits(value: str) -> str:
    """
    Mantem apenas digitos. Usado para comparar CPF/CNPJ/telefone
    independente da mascara.

    Exemplos:
        "111.444.777-35" → "11144477735"
        "(11) 99999-0000" → "11999990000"
    """
    return "".join(ch for ch in value if ch.isdigit())


# ============================================================
# Deteccao
# ============================================================


def find_duplicate_values(
    values: Sequence[str],
    *,
    key: Callable[[str], str] = normalize_text,
    skip_empty: bool = True,
) -> dict[str, list[int]]:
    """
    Encontra valores que aparecem mais de uma vez em uma coluna.

    Args:
        values: Valores da coluna, em ordem (indice 0-based).
        key: Funcao que normaliza cada valor antes de comparar.
            Default `normalize_text`. Use `normalize_digits` para CPF/CNPJ.
        skip_empty: Se True (default), ignora valores que ficam vazios
            apos a normalizacao (vazio nao conta como duplicata).

    Returns:
        Dict ``{chave_normalizada: [indices]}`` contendo SOMENTE as chaves
        com 2 ou mais ocorrencias. Os indices preservam a ordem de
        aparicao. Vazio se nao ha duplicatas.
    """
    seen: dict[str, list[int]] = {}
    for index, raw in enumerate(values):
        normalized = key(raw)
        if skip_empty and not normalized:
            continue
        seen.setdefault(normalized, []).append(index)
    return {value: indices for value, indices in seen.items() if len(indices) > 1}


def find_duplicate_rows(
    rows: Sequence[Sequence[str]],
    *,
    skip_empty: bool = True,
) -> list[list[int]]:
    """
    Encontra linhas 100% identicas (todas as colunas iguais).

    A comparacao normaliza cada celula com `normalize_text` (ignora caixa
    e espacos nas pontas), de modo que linhas que diferem apenas por
    capitalizacao/espacos sao consideradas iguais.

    Args:
        rows: Sequencia de linhas; cada linha e uma sequencia de valores.
        skip_empty: Se True (default), ignora linhas totalmente vazias.

    Returns:
        Lista de grupos; cada grupo e uma lista de indices (0-based) de
        linhas identicas entre si (2 ou mais). A ordem dentro do grupo
        preserva a aparicao — o primeiro indice e o "original".
    """
    seen: dict[tuple[str, ...], list[int]] = {}
    for index, row in enumerate(rows):
        normalized = tuple(normalize_text(str(cell)) for cell in row)
        if skip_empty and not any(normalized):
            continue
        seen.setdefault(normalized, []).append(index)
    return [indices for indices in seen.values() if len(indices) > 1]


__all__ = [
    "find_duplicate_rows",
    "find_duplicate_values",
    "normalize_digits",
    "normalize_text",
]
