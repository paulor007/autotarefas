"""
Motor das regras que envolvem varias colunas ou varias linhas.

Duas familias, ambas puras (recebem dados, devolvem achados — nao criam
issues, nao conhecem o schema, nao conhecem dominio nenhum):

    GRUPOS      linhas que compartilham uma chave devem concordar em
                certas colunas. A chave pode se repetir a vontade — isso
                e o normal, e o que forma o grupo. Nada a ver com "linha
                duplicada", que continua sendo outra verificacao.

    DERIVADAS   uma coluna deve bater com uma conta feita a partir de
                outras colunas.

Segue o padrao de `duplicates.py`: indices 0-based aqui dentro; quem
chama converte para numero de linha fisica.

DESEMPENHO: tudo por dicionario indexado (hash). Uma passada para
agrupar, uma para conferir. Nenhuma comparacao par a par — nada de
O(n^2). Ver a analise de complexidade em cada funcao.

O QUE ESTE MODULO NAO FAZ, DE PROPOSITO: escolher qual valor de um grupo
divergente e o "certo". O AutoTarefas nao conhece a verdade do negocio.
Ele mostra os valores encontrados e as linhas de cada um; quem decide e
o cliente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from autotarefas.tasks.expressions import Node

from autotarefas.tasks.expressions import EvaluationError, evaluate, format_decimal

#: Quantos valores distintos mostrar numa divergencia (mensagem util, nao gigante).
MAX_VARIANTS_SHOWN = 4
#: Quantas linhas listar por valor.
MAX_LINES_PER_VARIANT = 5

#: Textos que o Excel/planilha usa para erro — nunca sao numero.
_ERROR_MARKERS = frozenset(
    {
        "#DIV/0!",
        "#REF!",
        "#N/D",
        "#N/A",
        "#VALUE!",
        "#VALOR!",
        "#NAME?",
        "#NOME?",
        "#NULL!",
        "#NUM!",
    }
)


# --------------------------------------------------------------------------
# Conversao numerica
# --------------------------------------------------------------------------


def to_decimal(value: object) -> Decimal | None:
    """
    Converte uma celula em Decimal exato, ou None se nao for numero utilizavel.

    `None` (em vez de excecao) porque "esta celula nao tem numero" e um fato
    sobre o dado, nao um erro do programa — quem chama decide o que fazer.

    Passa por `str()` de proposito: `Decimal(str(3.3))` da exatamente 3.3,
    enquanto `Decimal(3.3)` traria o lixo binario do float.

    Separador decimal: se aparecem ponto E virgula, o ULTIMO e o decimal
    (cobre "1.234,56" e "1,234.56"). Se so ha virgula, ela e o decimal
    (convencao brasileira, igual ao resto do projeto).
    """
    if value is None:
        return None

    if isinstance(value, bool):  # bool e subclasse de int — nao e numero aqui
        return None

    if isinstance(value, (int, Decimal)):
        return Decimal(value)

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return Decimal(str(value))

    return _from_text(str(value))


def _from_text(texto: str) -> Decimal | None:
    """Parte textual da conversao (mantida separada para nao virar um funil)."""
    texto = texto.strip()
    if not texto or texto.upper() in _ERROR_MARKERS:
        return None

    limpo = texto.replace("R$", "").replace("%", "").replace(" ", "").replace("\u00a0", "")
    if not limpo:
        return None

    tem_ponto, tem_virgula = "." in limpo, "," in limpo
    if tem_ponto and tem_virgula:
        decimal_sep = "." if limpo.rfind(".") > limpo.rfind(",") else ","
        milhar = "," if decimal_sep == "." else "."
        limpo = limpo.replace(milhar, "").replace(decimal_sep, ".")
    elif tem_virgula:
        limpo = limpo.replace(",", ".")

    try:
        return Decimal(limpo)
    except InvalidOperation:
        return None


# --------------------------------------------------------------------------
# Grupos
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UngroupedRow:
    """Uma linha que nao pode entrar em nenhum grupo (chave vazia)."""

    index: int
    empty_positions: tuple[int, ...]
    """Posicoes (0-based) das colunas da chave que estavam vazias.
    Quem chama traduz para os nomes — o motor nao conhece nomes."""
    partial: bool
    """True = chave composta com parte preenchida; False = chave toda vazia."""


@dataclass(frozen=True, slots=True)
class GroupInconsistency:
    """Uma coluna que tem valores diferentes dentro de um mesmo grupo."""

    key: tuple[str, ...]
    column: str
    variants: tuple[tuple[str, tuple[int, ...]], ...]
    """((valor, (indices...)), ...) — TODOS os valores encontrados, em ordem
    de aparicao. Nenhum e marcado como o correto: essa decisao e do cliente."""
    group_size: int
    distinct_count: int
    anchor_index: int
    """Primeira linha do grupo — so para ancorar o issue, nao para culpar."""


def index_groups(
    keys: Sequence[Sequence[str]],
) -> tuple[dict[tuple[str, ...], list[int]], list[UngroupedRow]]:
    """
    Indexa as linhas por chave. Chave repetida e o esperado — e o que agrupa.

    Linhas com chave vazia (toda ou em parte) NAO entram num "grupo vazio"
    silencioso: saem separadas, para quem chama reportar.

    Complexidade: O(n * k), k = colunas da chave. Uma passada, hash.
    """
    grupos: dict[tuple[str, ...], list[int]] = {}
    fora: list[UngroupedRow] = []

    for indice, partes in enumerate(keys):
        valores = tuple(p.strip() for p in partes)
        vazias = tuple(i for i, v in enumerate(valores) if not v)

        if vazias:
            fora.append(
                UngroupedRow(
                    index=indice,
                    empty_positions=vazias,
                    partial=len(vazias) < len(valores),
                )
            )
            continue

        grupos.setdefault(valores, []).append(indice)

    return grupos, fora


def find_inconsistencies(
    grupos: Mapping[tuple[str, ...], Sequence[int]],
    values_by_column: Mapping[str, Sequence[str]],
    columns: Sequence[str],
) -> list[GroupInconsistency]:
    """
    Acha colunas que divergem dentro de um grupo.

    Um achado por (grupo, coluna) — nao um por linha. A mensagem carrega
    todos os valores e as linhas de cada um.

    Complexidade: O(n * c), c = colunas conferidas. Cada linha e visitada
    uma vez por coluna; nunca ha comparacao par a par.
    """
    achados: list[GroupInconsistency] = []

    for chave, indices in grupos.items():
        if len(indices) < 2:  # noqa: PLR2004 - grupo de 1 nao tem com quem divergir
            continue

        for coluna in columns:
            serie = values_by_column.get(coluna)
            if serie is None:
                continue

            variantes: dict[str, list[int]] = {}
            for i in indices:
                variantes.setdefault(serie[i].strip(), []).append(i)

            if len(variantes) < 2:  # noqa: PLR2004 - todos concordam
                continue

            mostradas = tuple(
                (valor, tuple(linhas[:MAX_LINES_PER_VARIANT]))
                for valor, linhas in list(variantes.items())[:MAX_VARIANTS_SHOWN]
            )
            achados.append(
                GroupInconsistency(
                    key=chave,
                    column=coluna,
                    variants=mostradas,
                    group_size=len(indices),
                    distinct_count=len(variantes),
                    anchor_index=indices[0],
                )
            )

    return achados


# --------------------------------------------------------------------------
# Regras derivadas
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DerivedFinding:
    """Uma linha em que a conta nao fechou — ou nao pode ser feita."""

    index: int
    computed: str | None
    observed: str | None
    difference: str | None
    reason: str | None
    """Preenchido = a regra NAO PODE ser calculada (dado faltando, /0).
    Vazio = a regra foi calculada e o resultado DIVERGE. Sao coisas
    diferentes e recebem tratamento diferente."""


def apply_derived(
    tree: Node,
    target_values: Sequence[object],
    column_values: Mapping[str, Sequence[object]],
    tolerance: Decimal,
) -> Iterator[DerivedFinding]:
    """
    Aplica uma regra derivada linha a linha, devolvendo SO os problemas.

    A arvore ja vem pronta (construida uma vez por regra). Cada linha e
    percorrida no maximo uma vez. Gerador: linhas corretas nao ocupam
    memoria nenhuma.

    Complexidade: O(n * t), t = nos da arvore (pequeno e constante).
    """
    colunas = list(column_values)

    for indice, bruto in enumerate(target_values):
        contexto: dict[str, Decimal | None] = {
            nome: to_decimal(column_values[nome][indice]) for nome in colunas
        }

        try:
            calculado = evaluate(tree, contexto)
        except EvaluationError as exc:
            yield DerivedFinding(
                index=indice,
                computed=None,
                observed=_texto(bruto),
                difference=None,
                reason=str(exc),
            )
            continue

        observado = to_decimal(bruto)
        if observado is None:
            yield DerivedFinding(
                index=indice,
                computed=format_decimal(calculado),
                observed=_texto(bruto),
                difference=None,
                reason="a coluna verificada nao tem um numero utilizavel nesta linha",
            )
            continue

        diferenca = abs(observado - calculado)
        if diferenca > tolerance:
            yield DerivedFinding(
                index=indice,
                computed=format_decimal(calculado),
                observed=format_decimal(observado),
                difference=format_decimal(diferenca),
                reason=None,
            )


def _texto(valor: object) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


__all__ = [
    "MAX_LINES_PER_VARIANT",
    "MAX_VARIANTS_SHOWN",
    "DerivedFinding",
    "GroupInconsistency",
    "UngroupedRow",
    "apply_derived",
    "find_inconsistencies",
    "index_groups",
    "to_decimal",
]
