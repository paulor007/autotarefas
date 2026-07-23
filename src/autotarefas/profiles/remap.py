"""
Remapeamento de um Schema: troca campos conceituais por colunas reais.

Um perfil fala em campos conceituais (`email`, `documento`). A planilha do
usuario fala em colunas reais (`Contato principal`, `CPF/CNPJ`). O
mapeamento e a ponte — e ele precisa trocar o nome em TODO lugar onde uma
coluna e referenciada, nao so em `columns[].name`:

    columns[].name
    group_keys[].columns[]
    group_checks[].consistent[]
    derived_checks[].target
    derived_checks[].expression   (as referencias [Nome] dentro do texto)

Uma unica funcao faz isso (`remap_schema`). Espalhar a troca por varios
lugares seria a receita para esquecer um deles e deixar uma referencia
apontando para um campo conceitual que nao existe mais no arquivo final.

As expressoes NAO sao reescritas por substituicao de texto ingenua — isso
poderia trocar um pedaco errado. Elas sao reanalisadas pelo parser seguro
da 1.5, que localiza cada referencia `[Nome]` ESTRUTURALMENTE; so os nomes
reconhecidos como coluna sao trocados, e numeros, operadores e parenteses
ficam intactos.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from autotarefas.tasks.expressions import (
    Col,
    Neg,
    Num,
    parse_expression,
)
from autotarefas.tasks.validate import (
    DerivedCheck,
    GroupCheck,
    GroupKey,
    Schema,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from autotarefas.tasks.expressions import Node


class RemapError(ValueError):
    """O mapeamento nao pode ser aplicado — erro de configuracao, explicito."""


def _rename(name: str, mapping: Mapping[str, str]) -> str:
    """Troca um nome conceitual pelo real, se houver mapeamento; senao mantem."""
    return mapping.get(name, name)


def _rewrite_expression(expression: str, mapping: Mapping[str, str]) -> str:
    """
    Reescreve as referencias [Nome] de uma expressao, preservando o resto.

    Feito sobre a arvore (nao sobre o texto): cada `Col` reconhecido pelo
    parser e trocado; operadores, numeros e agrupamento nao sao tocados.
    """
    arvore = parse_expression(expression)
    return _render(arvore, mapping)


def _render(node: Node, mapping: Mapping[str, str]) -> str:
    """Reconstroi o texto da expressao a partir da arvore, aplicando o mapa."""
    if isinstance(node, Num):
        texto = f"{node.value:f}"
        if "." in texto:
            texto = texto.rstrip("0").rstrip(".")
        return texto or "0"
    if isinstance(node, Col):
        return f"[{_rename(node.name, mapping)}]"
    if isinstance(node, Neg):
        return f"-{_render(node.operand, mapping)}"
    # BinOp: parenteses sempre, para nunca alterar a precedencia original
    return f"({_render(node.left, mapping)} {node.op} {_render(node.right, mapping)})"


def remap_schema(
    schema: Schema,
    mapping: Mapping[str, str],
    omit: set[str] | None = None,
) -> Schema:
    """
    Devolve um novo Schema com as referencias de coluna remapeadas.

    Args:
        schema: o schema do perfil, com nomes CONCEITUAIS.
        mapping: campo_conceitual -> coluna_real. Campos ausentes do mapa
            ficam com o nome conceitual (o chamador decide se e template ou erro).
        omit: campos conceituais a REMOVER do schema (ex.: um opcional que o
            usuario nao tem). Uma regra que dependa de um campo omitido tambem
            e removida — senao sobraria uma referencia orfa.

    Returns:
        Um Schema novo (o original nao e modificado).

    Raises:
        RemapError: se a reescrita de uma expressao falhar (rede de seguranca).
    """
    omit = omit or set()

    colunas = [
        col.model_copy(update={"name": _rename(col.name, mapping)})
        for col in schema.columns
        if col.name not in omit
    ]

    chaves = tuple(
        GroupKey(name=k.name, columns=tuple(_rename(c, mapping) for c in k.columns))
        for k in schema.group_keys
        if not (set(k.columns) & omit)  # chave que usa campo omitido some
    )
    nomes_de_chave = {k.name for k in chaves}

    checks = tuple(
        GroupCheck(
            name=g.name,
            group_key=g.group_key,
            consistent=tuple(_rename(c, mapping) for c in g.consistent),
            severity=g.severity,
        )
        for g in schema.group_checks
        if g.group_key in nomes_de_chave and not (set(g.consistent) & omit)
    )

    derivados = []
    for d in schema.derived_checks:
        if d.target in omit or (_expression_columns(d.expression) & omit):
            continue  # a regra depende de um campo omitido -> some junto
        try:
            nova_expr = _rewrite_expression(d.expression, mapping)
        except ValueError as exc:  # pragma: no cover - schema ja validado
            msg = f"nao foi possivel remapear a expressao de '{d.name}': {exc}"
            raise RemapError(msg) from exc
        derivados.append(
            DerivedCheck(
                name=d.name,
                target=_rename(d.target, mapping),
                expression=nova_expr,
                tolerance=d.tolerance,
                severity=d.severity,
            )
        )

    return Schema(
        columns=colunas,
        detect_duplicate_rows=schema.detect_duplicate_rows,
        group_keys=chaves,
        group_checks=checks,
        derived_checks=tuple(derivados),
    )


def referenced_fields(schema: Schema) -> set[str]:
    """
    Todos os nomes de coluna que o Schema referencia, em qualquer lugar.

    Usado para saber quais campos conceituais existem — e, depois do
    remapeamento, para detectar se sobrou alguma referencia nao trocada.
    """
    nomes: set[str] = {col.name for col in schema.columns}
    for chave in schema.group_keys:
        nomes.update(chave.columns)
    for check in schema.group_checks:
        nomes.update(check.consistent)
    for derivada in schema.derived_checks:
        nomes.add(derivada.target)
        nomes.update(_expression_columns(derivada.expression))
    return nomes


def _expression_columns(expression: str) -> set[str]:
    from autotarefas.tasks.expressions import columns_used

    return columns_used(parse_expression(expression))


__all__ = ["RemapError", "referenced_fields", "remap_schema"]
