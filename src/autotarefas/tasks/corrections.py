"""
Correcoes por regras CONFIRMADAS (RF-PLA-010).

A limpeza do PLA-006 corrige o que e seguro corrigir sem perguntar
(espacos, caixa, formato). Este modulo vai um passo alem — e so um passo:
aplica correcoes que **o usuario declarou explicitamente** em um arquivo
de regras. Nada aqui e adivinhado.

Tres tipos de regra, escolhidos por serem os que aparecem em toda planilha
administrativa real:

- ``de_para``     — troca valores conhecidos por um valor canonico
  (``"sao paulo" -> "SP"``);
- ``padronizar``  — encaixa o valor em uma lista declarada, ignorando
  caixa e acentos (``"ativo " -> "Ativo"``);
- ``preencher``   — completa **apenas celulas vazias** com um valor fixo.

E uma regra que atravessa os tres: **caso fora da regra nunca vira
decisao**. Ou o valor casa com o que foi declarado, ou ele vai para a
lista de revisao com o motivo — configuravel por regra
(``fora_da_regra: revisao`` ou ``manter``).

O relatorio separa as quatro naturezas que a ficha exige:
``automatico_seguro`` (conversao de tipo feita pelo leitor),
``normalizacao`` (espacos/caixa), ``regra_confirmada`` (este modulo) e
``revisao``.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

import yaml

from autotarefas.core.exceptions import ConfigError
from autotarefas.tasks.cleaning import normalize_whitespace

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

#: Tipos de regra aceitos.
RuleKind = Literal["de_para", "padronizar", "preencher"]

#: O que fazer quando o valor nao casa com a regra.
OutOfRule = Literal["revisao", "manter"]

#: Natureza de cada alteracao, para o relatorio separado da ficha.
ChangeNature = Literal["automatico_seguro", "normalizacao", "regra_confirmada", "revisao"]

_RULE_KINDS: tuple[str, ...] = ("de_para", "padronizar", "preencher")
_OUT_OF_RULE: tuple[str, ...] = ("revisao", "manter")


def _fold(value: str) -> str:
    """Chave de comparacao: sem acento, sem caixa, sem espaco sobrando."""
    texto = normalize_whitespace(value).casefold()
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


@dataclass(frozen=True, slots=True)
class CorrectionRule:
    """Uma regra confirmada pelo usuario, para UMA coluna."""

    column: str
    kind: RuleKind
    mapping: dict[str, str] = field(default_factory=dict)
    """de_para: valor de origem (dobrado) -> valor canonico."""
    allowed: tuple[str, ...] = ()
    """padronizar: os valores canonicos aceitos."""
    value: str = ""
    """preencher: o valor fixo."""
    out_of_rule: OutOfRule = "revisao"

    def describe(self) -> str:
        if self.kind == "de_para":
            return f"{self.column}: de/para com {len(self.mapping)} valor(es)"
        if self.kind == "padronizar":
            return f"{self.column}: padronizar para {', '.join(self.allowed)}"
        return f"{self.column}: preencher vazios com '{self.value}'"


@dataclass(frozen=True, slots=True)
class CorrectionChange:
    """Uma celula alterada (ou apontada para revisao) por uma regra."""

    row: int
    """Linha FISICA na planilha."""
    column: str
    before: str
    after: str
    nature: ChangeNature
    rule: str
    """Descricao curta da regra que justificou (ou o motivo da revisao)."""


@dataclass(frozen=True, slots=True)
class CorrectionResult:
    """Resultado da aplicacao das regras confirmadas."""

    rules: tuple[CorrectionRule, ...] = ()
    changes: tuple[CorrectionChange, ...] = ()
    review: tuple[CorrectionChange, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def counts(self) -> dict[str, int]:
        por_natureza: dict[str, int] = {
            "automatico_seguro": 0,
            "normalizacao": 0,
            "regra_confirmada": 0,
            "revisao": len(self.review),
        }
        for change in self.changes:
            por_natureza[change.nature] = por_natureza.get(change.nature, 0) + 1
        return por_natureza


# ============================================================
# Leitura das regras
# ============================================================


def _rule_from_mapping(raw: Mapping[str, Any], indice: int) -> CorrectionRule:
    coluna = str(raw.get("coluna", "")).strip()
    tipo = str(raw.get("tipo", "")).strip()
    if not coluna:
        msg = f"regra #{indice}: falta 'coluna'."
        raise ConfigError(msg)
    if tipo not in _RULE_KINDS:
        msg = f"regra #{indice} ('{coluna}'): 'tipo' deve ser um de {', '.join(_RULE_KINDS)}."
        raise ConfigError(msg)

    fora = str(raw.get("fora_da_regra", "revisao")).strip()
    if fora not in _OUT_OF_RULE:
        msg = (
            f"regra #{indice} ('{coluna}'): 'fora_da_regra' deve ser "
            f"{' ou '.join(_OUT_OF_RULE)} (recebido: {fora})."
        )
        raise ConfigError(msg)

    if tipo == "de_para":
        mapa = raw.get("mapa")
        if not isinstance(mapa, dict) or not mapa:
            msg = f"regra #{indice} ('{coluna}'): 'de_para' exige 'mapa' com ao menos um item."
            raise ConfigError(msg)
        return CorrectionRule(
            column=coluna,
            kind="de_para",
            mapping={_fold(str(k)): str(v) for k, v in mapa.items()},
            out_of_rule=fora,  # type: ignore[arg-type]
        )

    if tipo == "padronizar":
        valores = raw.get("valores")
        if not isinstance(valores, list) or not valores:
            msg = f"regra #{indice} ('{coluna}'): 'padronizar' exige 'valores' com a lista aceita."
            raise ConfigError(msg)
        return CorrectionRule(
            column=coluna,
            kind="padronizar",
            allowed=tuple(str(v) for v in valores),
            out_of_rule=fora,  # type: ignore[arg-type]
        )

    valor = raw.get("valor")
    if valor is None or str(valor) == "":
        msg = f"regra #{indice} ('{coluna}'): 'preencher' exige 'valor'."
        raise ConfigError(msg)
    return CorrectionRule(
        column=coluna,
        kind="preencher",
        value=str(valor),
        out_of_rule=fora,  # type: ignore[arg-type]
    )


def load_rules(path: Path) -> tuple[CorrectionRule, ...]:
    """
    Le o arquivo YAML de regras confirmadas.

    Formato::

        correcoes:
          - coluna: uf
            tipo: de_para
            mapa: {"sao paulo": SP, "rio de janeiro": RJ}
            fora_da_regra: revisao
          - coluna: situacao
            tipo: padronizar
            valores: [Ativo, Inativo]
          - coluna: origem
            tipo: preencher
            valor: planilha

    Raises:
        ConfigError: arquivo ilegivel ou regra mal declarada (com o indice
            da regra e o que falta na mensagem).
    """
    try:
        conteudo = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        msg = f"nao foi possivel ler o arquivo de regras {path.name}: {exc}"
        raise ConfigError(msg) from exc

    if not isinstance(conteudo, dict) or "correcoes" not in conteudo:
        msg = f"{path.name}: o arquivo precisa ter a chave 'correcoes' com a lista de regras."
        raise ConfigError(msg)

    brutas = conteudo["correcoes"]
    if not isinstance(brutas, list) or not brutas:
        msg = f"{path.name}: 'correcoes' precisa ser uma lista com ao menos uma regra."
        raise ConfigError(msg)

    return tuple(
        _rule_from_mapping(bruta, indice)
        for indice, bruta in enumerate(brutas, start=1)
        if isinstance(bruta, dict) or _reject(indice)
    )


def _reject(indice: int) -> bool:  # pragma: no cover - so existe para a mensagem
    msg = f"regra #{indice}: cada item de 'correcoes' precisa ser um mapa."
    raise ConfigError(msg)


# ============================================================
# Aplicacao
# ============================================================


#: Retorno das regras: ``(novo_valor, natureza, justificativa)`` ou None
#: quando a regra nao tem nada a dizer sobre aquele valor.
Decision = tuple[str, "ChangeNature", str] | None


def _canonical_for(rule: CorrectionRule, value: str) -> str | None:
    """
    O valor canonico que a regra produz para este valor, se ela souber.

    Cobre tambem o caso do valor que JA e o destino da regra ("SP" num
    de/para que produz "SP"): esta correto, e mandar para revisao seria
    pedir conferencia do que ja esta certo.
    """
    dobrado = _fold(value)
    if rule.kind == "de_para":
        canonico = rule.mapping.get(dobrado)
        if canonico is not None:
            return canonico
        return next(
            (destino for destino in rule.mapping.values() if _fold(destino) == dobrado), None
        )
    return next((permitido for permitido in rule.allowed if _fold(permitido) == dobrado), None)


def _out_of_rule_decision(rule: CorrectionRule, value: str) -> Decision:
    if rule.out_of_rule == "manter":
        return None
    return value, "revisao", f"valor fora da regra declarada para '{rule.column}'"


def _apply_rule(rule: CorrectionRule, value: str) -> Decision:
    """Aplica UMA regra a UM valor (nunca altera nada fora da regra)."""
    if rule.kind == "preencher":
        if value.strip():
            return None
        return rule.value, "regra_confirmada", f"vazio preenchido com '{rule.value}'"

    if not value.strip():
        return None

    canonico = _canonical_for(rule, value)
    if canonico is None:
        return _out_of_rule_decision(rule, value)
    if canonico == value:
        return None

    justificativa = (
        f"de/para: '{value}' -> '{canonico}'"
        if rule.kind == "de_para"
        else f"padronizado para '{canonico}'"
    )
    return canonico, "regra_confirmada", justificativa


def apply_rules(
    rows: Sequence[Mapping[str, str]],
    rules: Sequence[CorrectionRule],
    *,
    first_data_row: int = 2,
) -> tuple[list[dict[str, str]], CorrectionResult]:
    """
    Aplica as regras confirmadas linha a linha.

    Args:
        rows: linhas da planilha (dicts coluna -> valor em texto).
        rules: regras ja validadas.
        first_data_row: linha fisica do primeiro registro.

    Returns:
        ``(linhas_corrigidas, resultado)``. As linhas de entrada nao sao
        alteradas: o retorno e uma copia.
    """
    colunas_presentes = set(rows[0].keys()) if rows else set()
    avisos = [
        f"coluna '{rule.column}' nao existe na planilha: a regra nao teve efeito"
        for rule in rules
        if colunas_presentes and rule.column not in colunas_presentes
    ]
    aplicaveis = [r for r in rules if not colunas_presentes or r.column in colunas_presentes]

    corrigidas: list[dict[str, str]] = []
    mudancas: list[CorrectionChange] = []
    revisao: list[CorrectionChange] = []

    for indice, linha in enumerate(rows):
        nova = dict(linha)
        fisica = first_data_row + indice
        for rule in aplicaveis:
            atual = nova.get(rule.column, "")
            decisao = _apply_rule(rule, atual)
            if decisao is None:
                continue
            novo_valor, natureza, justificativa = decisao
            registro = CorrectionChange(
                row=fisica,
                column=rule.column,
                before=atual,
                after=novo_valor,
                nature=natureza,
                rule=justificativa,
            )
            if natureza == "revisao":
                revisao.append(registro)
                continue
            nova[rule.column] = novo_valor
            mudancas.append(registro)
        corrigidas.append(nova)

    resultado = CorrectionResult(
        rules=tuple(rules),
        changes=tuple(mudancas),
        review=tuple(revisao),
        warnings=tuple(avisos),
    )
    return corrigidas, resultado


__all__ = [
    "ChangeNature",
    "CorrectionChange",
    "CorrectionResult",
    "CorrectionRule",
    "OutOfRule",
    "RuleKind",
    "apply_rules",
    "load_rules",
]
