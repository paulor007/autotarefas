"""
Comparacao (diff) entre duas planilhas por chave — RF-REC-001.

Nucleo PURO: recebe duas tabelas ja lidas e devolve a classificacao. Nao
abre arquivo, nao escreve nada, nao conhece dominio. Quem le e o leitor;
quem grava artefato e :mod:`autotarefas.reconcile.artifacts`.

O que este modulo decide, e por que:

- **Chave canonica.** As colunas da chave sao ordenadas e deduplicadas
  antes de indexar. ``--chave loja --chave codigo`` e ``--chave codigo
  --chave loja`` produzem exatamente o mesmo pareamento, como exige a
  ficha do requisito.

- **Comparacao sobre o texto fiel.** Nao ha conversao de tipo aqui. Se A
  guarda ``10`` e B guarda ``10,00``, isso e uma divergencia — e o
  operador decide se importa. Tolerancia numerica/de data e assunto da
  RF-REC-002, nao desta fatia.

- **Normalizacao e opcional e explicita.** Sem ``--normalizar``, a
  comparacao e literal. As opcoes reusam a limpeza que ja existe no
  projeto (``normalize_whitespace``, ``normalize_digits``) e valem para a
  COMPARACAO; os valores relatados continuam sendo os originais.

- **Nada e pareado em silencio.** Chave repetida ou vazia vira conflito
  com as linhas envolvidas, nunca um pareamento adivinhado.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from autotarefas.reconcile.errors import CompareError
from autotarefas.reconcile.result import (
    CellDifference,
    CompareWarning,
    ComparisonResult,
    KeyConflict,
    RecordComparison,
    TableSource,
)
from autotarefas.reconcile.tolerance import Tolerance, index_tolerances, within_tolerance
from autotarefas.tasks.cleaning import normalize_whitespace
from autotarefas.tasks.duplicates import normalize_digits

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    import pandas as pd

#: Normalizacoes aceitas, na ordem em que sao aplicadas.
NORMALIZATION_OPTIONS: tuple[str, ...] = ("espacos", "caixa", "digitos")

#: Limites DESTA fatia, declarados no relatorio para que ninguem confunda
#: "nao encontrou diferenca" com "nao sabe procurar esse tipo de diferenca".
LIMITATIONS: tuple[str, ...] = (
    "comparacao textual: sem tolerancia declarada, '10' e '10,00' sao diferentes "
    "(use --tolerancia para numeros/datas e --normalizar para espacos/caixa/digitos)",
    "uma tabela por arquivo: a comparacao roda sobre a aba selecionada na leitura",
    "chave duplicada ou vazia nao e pareada — vai para a lista de conflitos",
    "colunas presentes em apenas uma das fontes ficam fora da comparacao (com aviso)",
)


# ============================================================
# Normalizacao dos valores comparados
# ============================================================


def _text(value: object) -> str:
    """Texto de uma celula, tolerando None/NaN (que viram string vazia)."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def normalize_for_comparison(
    value: str,
    normalizations: Iterable[str],
    *,
    is_key: bool = False,
) -> str:
    """
    Aplica as normalizacoes escolhidas ao valor, so para efeito de comparacao.

    ``digitos`` vale SOMENTE para a chave: aplicada a uma coluna de texto,
    ela transformaria "Ana Lima" e "Bruno Sa" ambos em string vazia e
    esconderia diferencas reais. Na chave ela e o que permite parear
    "529.982.247-25" com "52998224725".
    """
    opcoes = set(normalizations)
    texto = value
    if "espacos" in opcoes:
        texto = normalize_whitespace(texto)
    if "caixa" in opcoes:
        texto = texto.casefold()
    if is_key and "digitos" in opcoes:
        texto = normalize_digits(texto)
    return texto


def _canonical_key_columns(columns: Iterable[str]) -> tuple[str, ...]:
    """Chave em ordem canonica (dedup + ordenada): a ordem declarada nao importa."""
    return tuple(sorted(dict.fromkeys(columns)))


def _validate_normalizations(normalizations: Iterable[str]) -> tuple[str, ...]:
    escolhidas = set(normalizations)
    desconhecidas = sorted(escolhidas - set(NORMALIZATION_OPTIONS))
    if desconhecidas:
        msg = (
            f"normalizacao desconhecida: {', '.join(desconhecidas)} "
            f"(disponiveis: {', '.join(NORMALIZATION_OPTIONS)})"
        )
        raise CompareError(msg)
    return tuple(o for o in NORMALIZATION_OPTIONS if o in escolhidas)


# ============================================================
# Selecao das colunas comparadas
# ============================================================


def _resolve_columns(
    frame_a: pd.DataFrame,
    frame_b: pd.DataFrame,
    key_columns: tuple[str, ...],
    requested: Sequence[str] | None,
) -> tuple[tuple[str, ...], list[CompareWarning]]:
    """
    Decide quais colunas entram na comparacao.

    Sem escolha do usuario: todas as comuns as duas fontes, menos a chave.
    Coluna que existe em apenas um lado nunca e comparada — seria comparar
    com o vazio e acusar divergencia em todas as linhas. Ela vira AVISO.
    """
    colunas_a = [str(c) for c in frame_a.columns]
    colunas_b = [str(c) for c in frame_b.columns]
    em_b = set(colunas_b)
    em_a = set(colunas_a)
    avisos: list[CompareWarning] = []

    if requested is None:
        candidatas = [c for c in colunas_a if c in em_b]
        for coluna in colunas_a:
            if coluna not in em_b and coluna not in key_columns:
                avisos.append(_coluna_ausente(coluna, "B"))
        for coluna in colunas_b:
            if coluna not in em_a and coluna not in key_columns:
                avisos.append(_coluna_ausente(coluna, "A"))
    else:
        candidatas = []
        for coluna in dict.fromkeys(requested):
            if coluna not in em_a:
                avisos.append(_coluna_ausente(coluna, "A"))
            elif coluna not in em_b:
                avisos.append(_coluna_ausente(coluna, "B"))
            elif coluna in key_columns:
                # So avisa quando o usuario PEDIU a coluna: no caminho padrao,
                # a chave sair da lista de comparadas e o esperado, e um aviso
                # por coluna de chave viraria ruido em toda execucao.
                avisos.append(
                    CompareWarning(
                        code="coluna_chave_ignorada",
                        message=(
                            f"coluna '{coluna}' faz parte da chave: ela pareia os "
                            "registros, entao nao entra na comparacao"
                        ),
                        column=coluna,
                    )
                )
            else:
                candidatas.append(coluna)

    comparadas = tuple(c for c in candidatas if c not in key_columns)

    if not comparadas:
        avisos.append(
            CompareWarning(
                code="sem_colunas_comparadas",
                message=(
                    "nenhuma coluna em comum fora da chave: os registros pareados sao "
                    "reportados como identicos porque nao ha o que comparar"
                ),
            )
        )
    return comparadas, avisos


def _coluna_ausente(column: str, missing_in: str) -> CompareWarning:
    return CompareWarning(
        code="coluna_ausente",
        message=(f"coluna '{column}' nao existe na fonte {missing_in}: ficou fora da comparacao"),
        column=column,
    )


# ============================================================
# Indexacao por chave
# ============================================================


@dataclass(frozen=True, slots=True)
class _Indexed:
    """Uma fonte indexada pela chave (posicoes 0-based no DataFrame)."""

    table: TableSource
    cells: dict[str, list[str]]
    by_key: dict[tuple[str, ...], list[int]]
    order: list[tuple[str, ...]]
    empty_positions: list[int]

    def rows(self, positions: Iterable[int]) -> tuple[int, ...]:
        """Linhas FISICAS das posicoes informadas."""
        return tuple(self.table.physical_row(p) for p in positions)

    def value(self, column: str, position: int) -> str:
        return self.cells[column][position]


def _index_table(
    table: TableSource,
    key_columns: tuple[str, ...],
    columns: tuple[str, ...],
    normalizations: tuple[str, ...],
) -> _Indexed:
    """Le as colunas necessarias uma unica vez e indexa a fonte pela chave."""
    frame = table.frame
    necessarias = dict.fromkeys((*key_columns, *columns))
    cells = {coluna: [_text(v) for v in frame[coluna].tolist()] for coluna in necessarias}

    by_key: dict[tuple[str, ...], list[int]] = {}
    order: list[tuple[str, ...]] = []
    vazias: list[int] = []

    for position in range(len(frame)):
        partes = tuple(
            normalize_for_comparison(cells[coluna][position], normalizations, is_key=True)
            for coluna in key_columns
        )
        if not any(partes):
            vazias.append(position)
            continue
        if partes not in by_key:
            by_key[partes] = []
            order.append(partes)
        by_key[partes].append(position)

    return _Indexed(table=table, cells=cells, by_key=by_key, order=order, empty_positions=vazias)


# ============================================================
# Classificacao
# ============================================================


def _conflicts(a: _Indexed, b: _Indexed) -> tuple[tuple[KeyConflict, ...], set[tuple[str, ...]]]:
    """
    Chaves que NAO podem ser pareadas, com todas as linhas envolvidas.

    Uma chave repetida em qualquer um dos lados contamina o par inteiro:
    mesmo que B tenha um unico registro, nao da para saber a qual das
    linhas de A ele corresponde. Melhor um conflito explicito do que um
    pareamento inventado.
    """
    duplicadas = [k for k in a.order if len(a.by_key[k]) > 1]
    ja_listadas = set(duplicadas)
    duplicadas += [k for k in b.order if len(b.by_key[k]) > 1 and k not in ja_listadas]
    conflitos = [
        KeyConflict(
            key=chave,
            reason="chave_duplicada",
            rows_a=a.rows(a.by_key.get(chave, ())),
            rows_b=b.rows(b.by_key.get(chave, ())),
        )
        for chave in duplicadas
    ]

    if a.empty_positions or b.empty_positions:
        conflitos.append(
            KeyConflict(
                key=(),
                reason="chave_vazia",
                rows_a=a.rows(a.empty_positions),
                rows_b=b.rows(b.empty_positions),
            )
        )

    return tuple(conflitos), set(duplicadas)


@dataclass(frozen=True, slots=True)
class _Rules:
    """O que a comparacao considera igual: colunas, normalizacoes, tolerancias."""

    columns: tuple[str, ...]
    normalizations: tuple[str, ...]
    tolerances: dict[str, Tolerance]


def _differences(
    a: _Indexed,
    b: _Indexed,
    positions: tuple[int, int],
    rules: _Rules,
) -> tuple[tuple[CellDifference, ...], tuple[CellDifference, ...]]:
    """
    Separa o que difere de verdade do que a tolerancia declarada absorve.

    Returns:
        ``(divergencias, toleradas)`` — ambas com os valores ORIGINAIS.
    """
    pos_a, pos_b = positions
    divergentes: list[CellDifference] = []
    toleradas: list[CellDifference] = []
    for coluna in rules.columns:
        valor_a = a.value(coluna, pos_a)
        valor_b = b.value(coluna, pos_b)
        if normalize_for_comparison(valor_a, rules.normalizations) == normalize_for_comparison(
            valor_b, rules.normalizations
        ):
            continue
        diferenca = CellDifference(column=coluna, value_a=valor_a, value_b=valor_b)
        tolerancia = rules.tolerances.get(coluna)
        if tolerancia is not None and within_tolerance(tolerancia, valor_a, valor_b):
            toleradas.append(diferenca)
        else:
            divergentes.append(diferenca)
    return tuple(divergentes), tuple(toleradas)


def _classify(
    a: _Indexed,
    b: _Indexed,
    rules: _Rules,
    conflicting: set[tuple[str, ...]],
) -> tuple[RecordComparison, ...]:
    """Percorre as chaves de A (na ordem do arquivo) e depois as exclusivas de B."""
    registros: list[RecordComparison] = []

    for chave in a.order:
        if chave in conflicting:
            continue
        pos_a = a.by_key[chave][0]
        posicoes_b = b.by_key.get(chave)
        if posicoes_b is None:
            registros.append(
                RecordComparison(
                    key=chave,
                    category="somente_a",
                    row_a=a.table.physical_row(pos_a),
                )
            )
            continue
        pos_b = posicoes_b[0]
        diferencas, toleradas = _differences(a, b, (pos_a, pos_b), rules)
        registros.append(
            RecordComparison(
                key=chave,
                category="divergente" if diferencas else "identico",
                row_a=a.table.physical_row(pos_a),
                row_b=b.table.physical_row(pos_b),
                differences=diferencas,
                tolerated=toleradas,
            )
        )

    for chave in b.order:
        if chave in conflicting or chave in a.by_key:
            continue
        registros.append(
            RecordComparison(
                key=chave,
                category="somente_b",
                row_b=b.table.physical_row(b.by_key[chave][0]),
            )
        )

    return tuple(registros)


def _missing_key_columns(frame: pd.DataFrame, key_columns: tuple[str, ...]) -> list[str]:
    existentes = {str(c) for c in frame.columns}
    return [c for c in key_columns if c not in existentes]


def _skipped_rows_warnings(table_a: TableSource, table_b: TableSource) -> list[CompareWarning]:
    """
    Aviso quando o leitor descartou linhas vazias no meio da tabela.

    Sem ele, os numeros de linha do relatorio poderiam apontar para a linha
    errada da planilha original — e o operador perderia tempo procurando.
    """
    avisos: list[CompareWarning] = []
    for rotulo, tabela in (("A", table_a), ("B", table_b)):
        if tabela.skipped_empty_rows:
            avisos.append(
                CompareWarning(
                    code="linhas_vazias_ignoradas",
                    message=(
                        f"fonte {rotulo}: {tabela.skipped_empty_rows} linha(s) totalmente "
                        "vazia(s) foram descartadas na leitura; os numeros de linha do "
                        "relatorio podem estar deslocados em relacao ao arquivo"
                    ),
                )
            )
    return avisos


def _tolerance_warnings(
    tolerances: Sequence[Tolerance],
    compared_columns: tuple[str, ...],
) -> list[CompareWarning]:
    """
    Tolerancia declarada para coluna que nao esta sendo comparada e AVISO.

    Sem isso, um erro de digitacao no nome da coluna passaria despercebido e
    o usuario acreditaria estar tolerando algo que continua divergindo.
    """
    return [
        CompareWarning(
            code="tolerancia_sem_coluna",
            message=(
                f"tolerancia declarada para '{t.column}', que nao esta entre as colunas "
                "comparadas: ela nao teve efeito"
            ),
            column=t.column,
        )
        for t in tolerances
        if t.column not in compared_columns
    ]


# ============================================================
# Entry point
# ============================================================


def compare_tables(  # noqa: PLR0913 - quatro opcionais keyword-only
    table_a: TableSource,
    table_b: TableSource,
    *,
    key_columns: Sequence[str],
    columns: Sequence[str] | None = None,
    normalizations: Sequence[str] = (),
    tolerances: Sequence[Tolerance] = (),
) -> ComparisonResult:
    """
    Compara duas tabelas por chave e classifica cada registro.

    Args:
        table_a: fonte A (texto fiel do arquivo).
        table_b: fonte B.
        key_columns: colunas que identificam o registro. A ordem declarada
            nao afeta o pareamento (a chave e canonicalizada).
        columns: colunas a comparar. None = todas as comuns, menos a chave.
        normalizations: subconjunto de :data:`NORMALIZATION_OPTIONS`,
            aplicado apenas para efeito de comparacao.
        tolerances: tolerancias declaradas por coluna (REC-002). Uma
            diferenca dentro da tolerancia NAO conta como divergencia, mas
            fica registrada em ``RecordComparison.tolerated``.

    Returns:
        ComparisonResult com registros, conflitos, avisos e limitacoes.

    Raises:
        CompareError: chave vazia ou coluna de chave ausente em alguma fonte.
    """
    chave = _canonical_key_columns(key_columns)
    if not chave:
        msg = "informe ao menos uma coluna de chave para parear os registros"
        raise CompareError(msg)

    faltando_a = _missing_key_columns(table_a.frame, chave)
    faltando_b = _missing_key_columns(table_b.frame, chave)
    if faltando_a or faltando_b:
        detalhe = []
        if faltando_a:
            detalhe.append(f"A ({table_a.name}): {', '.join(faltando_a)}")
        if faltando_b:
            detalhe.append(f"B ({table_b.name}): {', '.join(faltando_b)}")
        msg = "coluna(s) de chave ausente(s) em " + "; ".join(detalhe)
        raise CompareError(msg)

    normalizacoes = _validate_normalizations(normalizations)
    comparadas, avisos = _resolve_columns(table_a.frame, table_b.frame, chave, columns)
    avisos.extend(_skipped_rows_warnings(table_a, table_b))
    avisos.extend(_tolerance_warnings(tolerances, comparadas))

    indexada_a = _index_table(table_a, chave, comparadas, normalizacoes)
    indexada_b = _index_table(table_b, chave, comparadas, normalizacoes)

    regras = _Rules(
        columns=comparadas,
        normalizations=normalizacoes,
        tolerances=index_tolerances(tuple(tolerances)),
    )
    conflitos, chaves_conflitantes = _conflicts(indexada_a, indexada_b)
    registros = _classify(indexada_a, indexada_b, regras, chaves_conflitantes)

    return ComparisonResult(
        source_a=table_a.info(),
        source_b=table_b.info(),
        key_columns=chave,
        compared_columns=comparadas,
        records=registros,
        conflicts=conflitos,
        warnings=tuple(avisos),
        normalizations=normalizacoes,
        tolerances=tuple(t.describe() for t in tolerances),
        limitations=LIMITATIONS,
    )


__all__ = [
    "LIMITATIONS",
    "NORMALIZATION_OPTIONS",
    "CompareError",
    "compare_tables",
    "normalize_for_comparison",
]
