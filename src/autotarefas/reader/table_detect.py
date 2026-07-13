"""
Deteccao de tabela: qual aba, qual linha e o cabecalho.

Nada aqui olha o NOME de coluna nenhuma. A decisao e estrutural: uma
tabela tem uma linha de rotulos (texto, distintos entre si) seguida de
linhas de dados com tipos consistentes entre si.

Quando a confianca e baixa, o leitor NAO escolhe em silencio: ele lista
as alternativas e pede `--sheet` / `--header-row`. Entregar a planilha
errada em silencio e pior que recusar.
"""

from __future__ import annotations

from itertools import islice
from typing import TYPE_CHECKING

from autotarefas.reader.types import classify_cell

if TYPE_CHECKING:
    from autotarefas.reader.types import RawCell

Grid = list[list["RawCell"]]

#: Quantas linhas do topo sao consideradas candidatas a cabecalho.
HEADER_SCAN_ROWS = 20
#: Abaixo disto, a aba nao parece uma tabela.
MIN_SHEET_SCORE = 0.35
#: Abaixo disto, nao ha cabecalho confiavel.
MIN_HEADER_CONFIDENCE = 0.45
#: Diferenca minima para considerar a escolha de aba "sem ambiguidade".
SHEET_MARGIN = 0.15

_TYPE_CHECK_ROWS = 5
_MIN_DATA_ROWS = 1
_MIN_TABLE_COLS = 2
#: Uma coluna "consistente" e preenchida em pelo menos metade das linhas.
_COLUMN_FILL_THRESHOLD = 0.5
#: Abaixo disto, as colunas estao espalhadas: nao e tabela.
_MIN_COLUMN_CONSISTENCY = 0.3
_NOT_A_TABLE_CEILING = 0.2
#: Um cabecalho de verdade e seguido de pelo menos ~3 linhas de dados.
_MIN_ROWS_BELOW_HEADER = 3
#: Quantas linhas abaixo do candidato bastam para avaliar (nunca a planilha toda).
_ROWS_BELOW_SAMPLE = 5


def _filled(row: list[RawCell]) -> int:
    return sum(1 for c in row if not c.is_empty)


def score_sheet(grid: Grid) -> tuple[float, str]:
    """
    O quanto esta aba 'parece uma tabela'. Score 0.0 a 1.0.

    O discriminador mais forte NAO e a densidade — e a CONSISTENCIA DAS
    COLUNAS: numa tabela, se a coluna 3 tem valor na primeira linha, ela
    tem valor em quase todas. Num painel (rotulo aqui, numero ali, nota
    acolá) as celulas preenchidas mudam de lugar a cada linha.

    Tambem entra a plausibilidade do cabecalho: uma "aba de capa" pode ser
    densa e regular, mas nao tem uma linha de rotulos seguida de dados.
    """
    if not grid:
        return 0.0, "aba vazia"

    linhas = [r for r in grid if _filled(r) > 0]
    if not linhas:
        return 0.0, "aba vazia"

    # largura FISICA (a do intervalo usado), nao o maximo de preenchidas
    n_cols = max(len(r) for r in linhas)
    if n_cols < _MIN_TABLE_COLS:
        return 0.05, "menos de 2 colunas: nao e uma tabela"
    if len(linhas) < _MIN_DATA_ROWS + 1:
        return 0.1, "poucas linhas preenchidas"

    larguras = [_filled(r) for r in linhas]

    # densidade sobre o retangulo fisico
    densidade = sum(larguras) / (len(linhas) * n_cols)

    # consistencia: quantas colunas estao preenchidas na maioria das linhas
    consistentes = 0
    for col in range(n_cols):
        cheias = sum(1 for r in linhas if col < len(r) and not r[col].is_empty)
        if cheias / len(linhas) >= _COLUMN_FILL_THRESHOLD:
            consistentes += 1
    consistencia = consistentes / n_cols

    # regularidade: quantas linhas tem a largura mais comum
    mais_comum = max(set(larguras), key=larguras.count)
    regularidade = larguras.count(mais_comum) / len(linhas)

    volume = min(len(linhas) / 10.0, 1.0)

    # ha uma linha de rotulos seguida de dados?
    _, conf_header, _ = find_header_row(grid)

    score = (
        0.30 * densidade
        + 0.25 * consistencia
        + 0.15 * regularidade
        + 0.10 * volume
        + 0.20 * conf_header
    )
    motivo = (
        f"{len(linhas)} linhas x {n_cols} colunas, densidade {densidade:.0%}, "
        f"colunas consistentes {consistencia:.0%}"
    )

    # TETO: uma tabela TEM colunas. Se nenhuma coluna e preenchida de forma
    # consistente, isto e um painel/relatorio livre — e os outros sinais
    # (regularidade, cabecalho plausivel) nao podem "carregar" o score.
    if consistencia < _MIN_COLUMN_CONSISTENCY:
        score = min(score, _NOT_A_TABLE_CEILING)
        motivo = f"colunas espalhadas ({consistencia:.0%} consistentes): nao parece uma tabela"

    return round(score, 3), motivo


def _header_score(grid: Grid, index: int, n_cols: int) -> float:
    """Quanto a linha `index` (0-based) parece um CABECALHO."""
    linha = grid[index]
    preenchidas = _filled(linha)
    if preenchidas < _MIN_TABLE_COLS or n_cols == 0:
        return 0.0

    cobertura = preenchidas / n_cols
    valores = [c.text for c in linha if not c.is_empty]
    tipos = [classify_cell(c) for c in linha if not c.is_empty]
    frac_texto = sum(1 for t in tipos if t == "texto") / len(tipos)
    frac_distintos = len(set(valores)) / len(valores)

    # So precisamos das PRIMEIRAS linhas abaixo — nunca da planilha inteira.
    # (O perfilador flagrou exatamente isto: varrer 7 mil linhas para cada
    #  uma das 20 candidatas a cabecalho custava segundos.)
    abaixo = list(islice((r for r in grid[index + 1 :] if _filled(r) > 0), _ROWS_BELOW_SAMPLE))
    if not abaixo:
        return 0.0

    # Um cabecalho de verdade e seguido de MUITAS linhas de dados. Sem isto,
    # uma linha de dados com 2 celulas de texto ("Calca", "uma duzia") seguida
    # de uma unica linha marcaria 1.0 e roubaria o lugar do cabecalho real.
    volume_abaixo = min(len(abaixo) / _MIN_ROWS_BELOW_HEADER, 1.0)

    # as linhas seguintes tem tipos consistentes entre si?
    amostra = abaixo[:_TYPE_CHECK_ROWS]
    consistencia = 0.0
    for col in range(len(linha)):
        tipos_col = [classify_cell(r[col]) for r in amostra if col < len(r) and not r[col].is_empty]
        if not tipos_col:
            continue
        dominante = max(set(tipos_col), key=tipos_col.count)
        consistencia += tipos_col.count(dominante) / len(tipos_col)
    consistencia /= max(len(linha), 1)

    return round(
        0.25 * cobertura
        + 0.25 * frac_texto
        + 0.15 * frac_distintos
        + 0.15 * consistencia
        + 0.20 * volume_abaixo,
        3,
    )


def find_header_row(grid: Grid) -> tuple[int | None, float, list[int]]:
    """
    Acha a linha de cabecalho.

    Returns:
        (indice 0-based, confianca, alternativas 0-based). Indice None =
        nenhuma linha plausivel encontrada.
    """
    if not grid:
        return None, 0.0, []

    n_cols = max((len(r) for r in grid if _filled(r) > 0), default=0)
    limite = min(HEADER_SCAN_ROWS, len(grid))
    scores = [(i, _header_score(grid, i, n_cols)) for i in range(limite)]
    scores = [(i, s) for i, s in scores if s > 0]
    if not scores:
        return None, 0.0, []

    scores.sort(key=lambda t: (-t[1], t[0]))
    melhor_idx, melhor_score = scores[0]
    alternativas = [i for i, s in scores[1:] if s >= melhor_score * 0.85]
    return melhor_idx, melhor_score, alternativas[:3]


def looks_like_footer(grid: Grid, index: int, n_cols: int) -> bool:
    """
    A linha `index` parece um RODAPE de totais?

    Estrutural: bem menos celulas preenchidas que o corpo, mas com numero.
    O leitor apenas MARCA — nunca remove (remocao exige flag explicita).
    """
    linha = grid[index]
    preenchidas = _filled(linha)
    if preenchidas == 0 or n_cols == 0:
        return False

    cobertura = preenchidas / n_cols
    tem_numero = any(
        classify_cell(c) in ("inteiro", "decimal", "moeda") for c in linha if not c.is_empty
    )
    tem_rotulo_total = any(
        "total" in c.text.lower() or "soma" in c.text.lower() for c in linha if not c.is_empty
    )
    esparsa = cobertura <= 0.6  # noqa: PLR2004 - metade das colunas vazias

    return (esparsa and tem_numero) or tem_rotulo_total


__all__ = [
    "HEADER_SCAN_ROWS",
    "MIN_HEADER_CONFIDENCE",
    "MIN_SHEET_SCORE",
    "SHEET_MARGIN",
    "Grid",
    "find_header_row",
    "looks_like_footer",
    "score_sheet",
]
