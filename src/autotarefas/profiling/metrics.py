"""
Metricas puras da perfilagem.

Funcoes sem estado, sem dominio e sem efeito colateral. Cada uma percorre
a coluna UMA vez (a planilha do cliente pode ter centenas de milhares de
linhas — nada aqui pode ser O(n^2)).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

import pandas as pd

from autotarefas.reader.types import EXCEL_ERRORS

if TYPE_CHECKING:
    from autotarefas.reader.result import CellType

#: Quantas amostras acompanham cada achado (mensagens curtas, nunca listas gigantes).
SAMPLE_SIZE = 5

#: Tipos em que minimo/maximo fazem sentido. Um identificador NAO entra aqui:
#: "o menor CPF da base" nao e uma metrica, e um acidente.
RANGE_TYPES: frozenset[str] = frozenset(
    {"inteiro", "decimal", "moeda", "percentual", "data", "data_hora"}
)

_INTERNAL_SPACES = re.compile(r"\S\s{2,}\S")


def fill_stats(valores: list[str]) -> tuple[int, int, float]:
    """(preenchidos, vazios, taxa de preenchimento)."""
    total = len(valores)
    preenchidos = sum(1 for v in valores if v.strip() != "")
    vazios = total - preenchidos
    taxa = round(preenchidos / total, 4) if total else 0.0
    return preenchidos, vazios, taxa


def distinct_stats(valores: list[str]) -> tuple[int, float, int]:
    """
    (distintos, taxa de unicidade, celulas com valor repetido).

    `duplicados` conta as celulas EXCEDENTES: se "Vestuario" aparece 3x,
    2 sao excedentes. Isso e ESTATISTICA — nunca um veredito de erro.
    """
    preenchidos = [v for v in valores if v.strip() != ""]
    if not preenchidos:
        return 0, 0.0, 0
    distintos = len(set(preenchidos))
    taxa = round(distintos / len(preenchidos), 4)
    return distintos, taxa, len(preenchidos) - distintos


def whitespace_issues(valores: list[str]) -> tuple[int, list[str]]:
    """
    Celulas com espaco sobrando: nas pontas ou 2+ espacos internos.

    Detecta — nao corrige. (A remocao das pontas ja e feita pelo leitor,
    com Conversion registrada; os espacos INTERNOS ficam intactos, porque
    "Meia   Longa" pode ser intencional.)
    """
    afetadas = [v for v in valores if v != v.strip() or bool(_INTERNAL_SPACES.search(v))]
    return len(afetadas), [repr(v) for v in afetadas[:SAMPLE_SIZE]]


def excel_error_stats(valores: list[str]) -> tuple[int, list[str]]:
    """Quantas celulas sao erro do Excel (#DIV/0!, #REF!, #N/D...)."""
    erros = [v for v in valores if v.strip().upper() in EXCEL_ERRORS]
    return len(erros), sorted(set(erros))[:SAMPLE_SIZE]


def _format(valor: object) -> str:
    if isinstance(valor, pd.Timestamp):
        return valor.date().isoformat() if valor.time().isoformat() == "00:00:00" else str(valor)
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def value_range(serie: pd.Series, tipo: CellType) -> tuple[str | None, str | None]:
    """
    (minimo, maximo) — apenas quando o tipo permite ordenacao com sentido.

    Para identificador, texto, booleano, misto e erro: (None, None).
    """
    if tipo not in RANGE_TYPES:
        return None, None
    limpa = serie.dropna()
    if limpa.empty:
        return None, None
    try:
        return _format(limpa.min()), _format(limpa.max())
    except TypeError:
        # tipos nao comparaveis entre si: nao inventa um intervalo
        return None, None


def duplicate_row_count(original: pd.DataFrame) -> tuple[int, list[int], int]:
    """
    Linhas EXCEDENTES identicas a outra + suas linhas fisicas + linhas vazias.

    Nada e removido: a contagem e um fato, nao uma acao.
    """
    if original.empty:
        return 0, [], 0
    duplicadas = original.duplicated(keep="first")
    posicoes = [int(i) for i in duplicadas[duplicadas].index[:SAMPLE_SIZE]]
    vazias = int((original.apply(lambda r: all(str(v).strip() == "" for v in r), axis=1)).sum())
    return int(duplicadas.sum()), posicoes, vazias


def top_repeated(valores: list[str], limite: int = SAMPLE_SIZE) -> list[str]:
    """Os valores mais repetidos (so para ILUSTRAR a estatistica)."""
    contagem = Counter(v for v in valores if v.strip() != "")
    return [f"{valor} ({n}x)" for valor, n in contagem.most_common(limite) if n > 1]


__all__ = [
    "RANGE_TYPES",
    "SAMPLE_SIZE",
    "distinct_stats",
    "duplicate_row_count",
    "excel_error_stats",
    "fill_stats",
    "top_repeated",
    "value_range",
    "whitespace_issues",
]
