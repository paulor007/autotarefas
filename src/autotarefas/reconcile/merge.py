"""
Reconciliacao: das diferencas para a decisao (RF-REC-002).

A comparacao (REC-001) responde "o que mudou". Este modulo responde a
pergunta seguinte, que e a que da trabalho: **qual valor vale?** — e sob
qual regra, declarada por quem conhece o negocio.

O desenho tem tres pecas:

1. **Fonte principal x complementar.** Uma das bases manda. A outra so
   pode alterar o que foi AUTORIZADO, coluna por coluna
   (``campos_atualizaveis``).

2. **Nada fora da regra e resolvido sozinho.** Divergencia em coluna nao
   autorizada nao vira escolha automatica: o valor da fonte principal e
   PRESERVADO (a base nao muda sem autorizacao) e o caso vai inteiro para
   o arquivo de revisao, com os dois valores lado a lado.

3. **Toda decisao automatica fica registrada** com a regra que a
   justificou (``FieldDecision.rule``) — inclusive as diferencas absorvidas
   por tolerancia. Tolerar nao e esquecer.

Chave duplicada ou vazia nunca entra na base conciliada: sem pareamento
confiavel, nao existe decisao confiavel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from autotarefas.reconcile.result import (
    CellDifference,
    ComparisonResult,
    RecordComparison,
    TableSource,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

#: Qual fonte manda quando as duas tem o registro.
PrimarySource = Literal["a", "b"]

#: Por que um valor foi escolhido.
DecisionRule = Literal[
    "fonte_principal",
    "campo_autorizado",
    "tolerancia",
    "registro_exclusivo",
]

#: Por que um caso foi para revisao humana.
ReviewReason = Literal[
    "divergencia_nao_autorizada",
    "chave_duplicada",
    "chave_vazia",
    "registro_novo_nao_incluido",
]

#: Limites declarados desta fatia da reconciliacao.
LIMITATIONS: tuple[str, ...] = (
    "a base conciliada tem as colunas da fonte principal; coluna que so existe "
    "na complementar nao e criada",
    "sem autorizacao explicita (--atualizar), o valor da fonte principal e "
    "preservado e a divergencia vai para revisao",
    "chave duplicada ou vazia nao entra na base conciliada — vai para revisao",
    "nenhuma fonte e alterada: a base conciliada e sempre um arquivo novo",
)


@dataclass(frozen=True, slots=True)
class ReconcilePolicy:
    """As regras declaradas pelo usuario para decidir."""

    primary: PrimarySource = "a"
    updatable_columns: tuple[str, ...] = ()
    """Colunas que a fonte complementar pode atualizar na principal."""
    include_new: bool = True
    """Registros que so existem na complementar entram na base conciliada."""

    @property
    def secondary(self) -> PrimarySource:
        return "b" if self.primary == "a" else "a"

    def describe(self) -> str:
        campos = ", ".join(self.updatable_columns) or "(nenhum)"
        novos = "incluidos" if self.include_new else "enviados para revisao"
        return (
            f"fonte principal: {self.primary.upper()}; campos atualizaveis: {campos}; "
            f"registros novos da complementar: {novos}"
        )


@dataclass(frozen=True, slots=True)
class FieldDecision:
    """Um valor escolhido — e a regra que justificou a escolha."""

    column: str
    value: str
    source: PrimarySource
    rule: DecisionRule
    other_value: str = ""
    """O valor do outro lado (vazio quando so um lado tinha o registro)."""


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """Um caso que o AutoTarefas se recusa a decidir sozinho."""

    key: tuple[str, ...]
    reason: ReviewReason
    column: str | None = None
    value_a: str = ""
    value_b: str = ""
    rows_a: tuple[int, ...] = ()
    rows_b: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ReconciledRecord:
    """Uma linha da base conciliada, com as decisoes que a formaram."""

    key: tuple[str, ...]
    origin: Literal["a", "b", "ambos"]
    values: dict[str, str]
    decisions: tuple[FieldDecision, ...] = ()


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Resultado completo da reconciliacao."""

    comparison: ComparisonResult
    policy: ReconcilePolicy
    columns: tuple[str, ...]
    records: tuple[ReconciledRecord, ...] = ()
    review: tuple[ReviewItem, ...] = ()
    limitations: tuple[str, ...] = field(default_factory=lambda: LIMITATIONS)

    @property
    def counts(self) -> dict[str, int]:
        """Contadores da reconciliacao (o resumo que o operador le primeiro)."""
        campos_atualizados = [
            d for r in self.records for d in r.decisions if d.rule == "campo_autorizado"
        ]
        registros_atualizados = sum(
            1 for r in self.records if any(d.rule == "campo_autorizado" for d in r.decisions)
        )
        return {
            "conciliados": len(self.records),
            "registros_atualizados": registros_atualizados,
            "campos_atualizados": len(campos_atualizados),
            "para_revisao": len(self.review),
            "toleradas": self.comparison.tolerated_count,
        }


def _position(row: int | None, table: TableSource) -> int | None:
    return None if row is None else row - table.first_data_row


def _row_values(table: TableSource, position: int, columns: Sequence[str]) -> dict[str, str]:
    """Valores de uma linha, restritos as colunas pedidas (ausente = vazio)."""
    frame = table.frame
    existentes = {str(c) for c in frame.columns}
    linha = frame.iloc[position]
    return {coluna: ("" if coluna not in existentes else str(linha[coluna])) for coluna in columns}


@dataclass(frozen=True, slots=True)
class _Sides:
    """As duas fontes ja resolvidas em 'principal' e 'complementar'."""

    primary: TableSource
    secondary: TableSource
    primary_label: PrimarySource
    secondary_label: PrimarySource


def _sides(table_a: TableSource, table_b: TableSource, policy: ReconcilePolicy) -> _Sides:
    if policy.primary == "a":
        return _Sides(table_a, table_b, "a", "b")
    return _Sides(table_b, table_a, "b", "a")


def _side_value(difference: CellDifference, side: PrimarySource) -> str:
    return difference.value_a if side == "a" else difference.value_b


def _decisions_for_pair(
    record_values: dict[str, str],
    comparison_record: RecordComparison,
    sides: _Sides,
    policy: ReconcilePolicy,
) -> tuple[dict[str, str], list[FieldDecision], list[ReviewItem]]:
    """
    Aplica as regras a um registro presente nas DUAS fontes.

    Comeca do valor da fonte principal e so troca o que foi autorizado.
    """
    valores = dict(record_values)
    decisoes: list[FieldDecision] = []
    revisao: list[ReviewItem] = []

    for diferenca in comparison_record.differences:
        valor_principal = _side_value(diferenca, sides.primary_label)
        valor_complementar = _side_value(diferenca, sides.secondary_label)

        if diferenca.column in policy.updatable_columns:
            valores[diferenca.column] = valor_complementar
            decisoes.append(
                FieldDecision(
                    column=diferenca.column,
                    value=valor_complementar,
                    source=sides.secondary_label,
                    rule="campo_autorizado",
                    other_value=valor_principal,
                )
            )
            continue

        decisoes.append(
            FieldDecision(
                column=diferenca.column,
                value=valor_principal,
                source=sides.primary_label,
                rule="fonte_principal",
                other_value=valor_complementar,
            )
        )
        revisao.append(
            ReviewItem(
                key=comparison_record.key,
                reason="divergencia_nao_autorizada",
                column=diferenca.column,
                value_a=diferenca.value_a,
                value_b=diferenca.value_b,
                rows_a=(comparison_record.row_a,) if comparison_record.row_a else (),
                rows_b=(comparison_record.row_b,) if comparison_record.row_b else (),
            )
        )

    for tolerada in comparison_record.tolerated:
        decisoes.append(
            FieldDecision(
                column=tolerada.column,
                value=_side_value(tolerada, sides.primary_label),
                source=sides.primary_label,
                rule="tolerancia",
                other_value=_side_value(tolerada, sides.secondary_label),
            )
        )

    return valores, decisoes, revisao


def _conflict_reviews(comparison: ComparisonResult) -> list[ReviewItem]:
    """Conflitos de chave viram itens de revisao — nunca entram na base."""
    return [
        ReviewItem(
            key=conflito.key,
            reason=conflito.reason,
            rows_a=conflito.rows_a,
            rows_b=conflito.rows_b,
        )
        for conflito in comparison.conflicts
    ]


def reconcile_tables(
    table_a: TableSource,
    table_b: TableSource,
    comparison: ComparisonResult,
    policy: ReconcilePolicy,
) -> ReconciliationResult:
    """
    Monta a base conciliada e a lista de revisao a partir de uma comparacao.

    Args:
        table_a: fonte A (a mesma usada na comparacao).
        table_b: fonte B.
        comparison: resultado de :func:`compare_tables`.
        policy: regras declaradas (fonte principal, campos atualizaveis).

    Returns:
        ReconciliationResult com uma linha por registro decidido e um item
        de revisao para cada caso que ficou fora das regras.
    """
    sides = _sides(table_a, table_b, policy)
    colunas = tuple(str(c) for c in sides.primary.frame.columns)

    registros: list[ReconciledRecord] = []
    revisao: list[ReviewItem] = []

    for record in comparison.records:
        pos_a = _position(record.row_a, table_a)
        pos_b = _position(record.row_b, table_b)
        pos_principal = pos_a if policy.primary == "a" else pos_b
        pos_complementar = pos_b if policy.primary == "a" else pos_a

        if pos_principal is not None and pos_complementar is not None:
            base = _row_values(sides.primary, pos_principal, colunas)
            valores, decisoes, para_revisao = _decisions_for_pair(base, record, sides, policy)
            revisao.extend(para_revisao)
            registros.append(
                ReconciledRecord(
                    key=record.key,
                    origin="ambos",
                    values=valores,
                    decisions=tuple(decisoes),
                )
            )
            continue

        if pos_principal is not None:
            registros.append(
                ReconciledRecord(
                    key=record.key,
                    origin=sides.primary_label,
                    values=_row_values(sides.primary, pos_principal, colunas),
                    decisions=(),
                )
            )
            continue

        # So existe na fonte COMPLEMENTAR: registro novo.
        if not policy.include_new:
            revisao.append(
                ReviewItem(
                    key=record.key,
                    reason="registro_novo_nao_incluido",
                    rows_a=(record.row_a,) if record.row_a else (),
                    rows_b=(record.row_b,) if record.row_b else (),
                )
            )
            continue
        if pos_complementar is None:  # pragma: no cover - registro sem nenhum lado
            continue
        registros.append(
            ReconciledRecord(
                key=record.key,
                origin=sides.secondary_label,
                values=_row_values(sides.secondary, pos_complementar, colunas),
                decisions=(
                    FieldDecision(
                        column="(registro)",
                        value="incluido",
                        source=sides.secondary_label,
                        rule="registro_exclusivo",
                    ),
                ),
            )
        )

    revisao.extend(_conflict_reviews(comparison))

    return ReconciliationResult(
        comparison=comparison,
        policy=policy,
        columns=colunas,
        records=tuple(registros),
        review=tuple(revisao),
    )


__all__ = [
    "LIMITATIONS",
    "DecisionRule",
    "FieldDecision",
    "PrimarySource",
    "ReconcilePolicy",
    "ReconciledRecord",
    "ReconciliationResult",
    "ReviewItem",
    "ReviewReason",
    "reconcile_tables",
]
