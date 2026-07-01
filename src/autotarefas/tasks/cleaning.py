"""
Normalizacao segura de dados de planilha (modo limpeza da Auditoria).

REGRA DE OURO: nunca inventar dado. Apenas transformacoes
deterministicas e conservadoras:
- remover espacos das pontas e colapsar espacos internos (qualquer campo)
- e-mail para minusculo
- CPF/CNPJ: aplicar a mascara canonica SOMENTE quando os digitos ja
  formam um documento valido (senao mantem o original — nunca "conserta")
- telefone: aplicar a mascara canonica SOMENTE quando o numero e valido

Cada alteracao vira um `CleaningChange` (antes/depois/regras) para o
audit trail — transparencia total do que o sistema mudou.

As funcoes de normalizacao sao puras. Este modulo NAO conhece o Schema
(evita import circular com validate.py): quem chama passa flags simples
para `clean_cell` indicando quais normalizacoes se aplicam a cada coluna.
"""

from __future__ import annotations

from dataclasses import dataclass

from autotarefas.tasks.validators_br import (
    is_valid_cnpj,
    is_valid_cpf,
    is_valid_phone_br,
)

# ============================================================
# Nomes das regras (rotulos legiveis no audit trail)
# ============================================================

RULE_WHITESPACE = "espacos"
RULE_LOWERCASE = "minusculo"
RULE_CPF = "formato_cpf"
RULE_CNPJ = "formato_cnpj"
RULE_PHONE = "formato_telefone"


@dataclass(frozen=True, slots=True)
class CleaningChange:
    """
    Registro de uma celula normalizada (uma entrada do audit trail).

    Attributes:
        line: Numero da linha (1-based, como Excel; 1a linha de dados = 2).
        column: Nome da coluna.
        before: Valor original (antes da normalizacao).
        after: Valor final (depois da normalizacao).
        rules: Regras aplicadas que de fato alteraram o valor.
    """

    line: int
    column: str
    before: str
    after: str
    rules: tuple[str, ...]


# ============================================================
# Normalizadores de valor (funcoes puras)
# ============================================================


def _only_digits(value: str) -> str:
    """Mantem apenas digitos."""
    return "".join(ch for ch in value if ch.isdigit())


def normalize_whitespace(value: str) -> str:
    """
    Remove espacos das pontas e colapsa espacos internos repetidos.

    Exemplos:
        "  Ana   Lima "  → "Ana Lima"
        "  ana@x.com "   → "ana@x.com"
    """
    return " ".join(value.split())


def normalize_email(value: str) -> str:
    """
    E-mail para minusculo. Nao valida — apenas normaliza a caixa.
    (E-mails nao devem ter espacos; use apos `normalize_whitespace`.)
    """
    return value.lower()


def format_cpf(value: str) -> str:
    """
    Aplica a mascara XXX.XXX.XXX-XX se os digitos formam um CPF valido.
    Caso contrario retorna o valor inalterado (nunca inventa/conserta).
    """
    if not is_valid_cpf(value):
        return value
    d = _only_digits(value)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def format_cnpj(value: str) -> str:
    """
    Aplica a mascara XX.XXX.XXX/XXXX-XX se os digitos formam um CNPJ valido.
    Caso contrario retorna o valor inalterado.
    """
    if not is_valid_cnpj(value):
        return value
    d = _only_digits(value)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def format_phone_br(value: str) -> str:
    """
    Aplica a mascara nacional se o telefone e valido:
    - celular (11 digitos): ``(XX) XXXXX-XXXX``
    - fixo (10 digitos):    ``(XX) XXXX-XXXX``

    Remove o codigo do pais (+55) quando presente. Caso invalido, retorna
    o valor inalterado.
    """
    if not is_valid_phone_br(value):
        return value
    d = _only_digits(value)
    if len(d) in (12, 13) and d.startswith("55"):
        d = d[2:]
    ddd, num = d[:2], d[2:]
    if len(num) == 9:  # noqa: PLR2004 — celular
        return f"({ddd}) {num[:5]}-{num[5:]}"
    return f"({ddd}) {num[:4]}-{num[4:]}"  # fixo


# ============================================================
# Orquestrador por celula
# ============================================================


def clean_cell(
    value: str,
    *,
    lowercase: bool = False,
    cpf: bool = False,
    cnpj: bool = False,
    phone: bool = False,
) -> tuple[str, tuple[str, ...]]:
    """
    Normaliza uma celula aplicando somente transformacoes seguras.

    O whitespace e sempre aplicado; as demais dependem das flags (que o
    chamador deriva do schema da coluna). Uma regra so entra na tupla de
    saida se de fato alterou o valor — o que permite ao chamador registrar
    no audit trail apenas o que mudou.

    Args:
        value: Valor original da celula (ja como string).
        lowercase: Aplica `normalize_email` (coluna com format=email).
        cpf: Aplica `format_cpf` (coluna com validator_br=cpf).
        cnpj: Aplica `format_cnpj` (coluna com validator_br=cnpj).
        phone: Aplica `format_phone_br` (coluna com format=phone).

    Returns:
        Tupla ``(valor_final, regras_aplicadas)``.
    """
    rules: list[str] = []
    current = value

    stripped = normalize_whitespace(current)
    if stripped != current:
        rules.append(RULE_WHITESPACE)
    current = stripped

    if lowercase:
        lowered = normalize_email(current)
        if lowered != current:
            rules.append(RULE_LOWERCASE)
        current = lowered

    if cpf:
        formatted = format_cpf(current)
        if formatted != current:
            rules.append(RULE_CPF)
        current = formatted

    if cnpj:
        formatted = format_cnpj(current)
        if formatted != current:
            rules.append(RULE_CNPJ)
        current = formatted

    if phone:
        formatted = format_phone_br(current)
        if formatted != current:
            rules.append(RULE_PHONE)
        current = formatted

    return current, tuple(rules)


__all__ = [
    "RULE_CNPJ",
    "RULE_CPF",
    "RULE_LOWERCASE",
    "RULE_PHONE",
    "RULE_WHITESPACE",
    "CleaningChange",
    "clean_cell",
    "format_cnpj",
    "format_cpf",
    "format_phone_br",
    "normalize_email",
    "normalize_whitespace",
]
