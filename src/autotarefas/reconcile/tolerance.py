"""
Tolerancias declaradas da reconciliacao (RF-REC-002).

Existe por um motivo concreto: um centavo de arredondamento entre dois
sistemas nao e uma divergencia que alguem precise conferir — mas o
comparador da REC-001, que compara texto, acusa. A tolerancia e a forma de
o usuario DECLARAR o que ele considera igual, coluna por coluna.

Tres formas, uma sintaxe:

    coluna=0,01   diferenca absoluta de ate 1 centavo
    coluna=1%     diferenca de ate 1% (sobre o maior valor absoluto do par)
    coluna=2d     diferenca de ate 2 dias

Regras que nao se negociam:

- tolerancia so vale para valores COMPARAVEIS: se um dos lados nao e
  numero (ou nao e data), nao ha tolerancia — e divergencia de verdade;
- vazio de um lado e valor do outro nunca e tolerado: e ausencia, nao
  arredondamento;
- toda tolerancia aplicada e REGISTRADA no relatorio. Diferenca tolerada
  nao vira "identico" em silencio.

A leitura de numeros e datas reusa o proprio leitor do projeto
(`reader.normalize`), para que "R$ 1.234,56" signifique aqui exatamente o
que significa la.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from autotarefas.reader.normalize import parse_date, parse_number
from autotarefas.reader.types import detect_decimal_separator
from autotarefas.reconcile.errors import CompareError

#: Formas de tolerancia aceitas.
ToleranceKind = Literal["absoluta", "percentual", "dias"]

_SPEC_RE = re.compile(r"^\s*(?P<coluna>.+?)\s*=\s*(?P<valor>[\d.,]+)\s*(?P<sufixo>[%dD]?)\s*$")

_PERCENT_BASE = 100.0
_SECONDS_PER_DAY = 86400.0


@dataclass(frozen=True, slots=True)
class Tolerance:
    """Quanto de diferenca uma coluna pode ter sem virar divergencia."""

    column: str
    kind: ToleranceKind
    amount: float

    def describe(self) -> str:
        """Texto para o relatorio (ex.: ``valor: ate 0.01 (absoluta)``)."""
        unidade = {"absoluta": "", "percentual": "%", "dias": " dia(s)"}[self.kind]
        return f"{self.column}: ate {self.amount:g}{unidade} ({self.kind})"


def parse_tolerance(spec: str) -> Tolerance:
    """
    Le uma tolerancia declarada (``coluna=0,01`` | ``coluna=1%`` | ``coluna=2d``).

    Raises:
        CompareError: sintaxe invalida ou valor negativo — erro de uso, com
            a forma correta na mensagem.
    """
    match = _SPEC_RE.match(spec)
    if match is None:
        msg = (
            f"tolerancia invalida: {spec!r}. Use 'coluna=0,01' (absoluta), "
            "'coluna=1%' (percentual) ou 'coluna=2d' (dias)."
        )
        raise CompareError(msg)

    coluna = match.group("coluna")
    bruto = match.group("valor")
    sufixo = match.group("sufixo").lower()

    quantidade = parse_number(bruto, detect_decimal_separator([bruto]) or ",")
    if quantidade is None or quantidade < 0:
        msg = f"tolerancia invalida: {spec!r} — a quantidade precisa ser um numero >= 0."
        raise CompareError(msg)

    kind: ToleranceKind = "absoluta"
    if sufixo == "%":
        kind = "percentual"
    elif sufixo == "d":
        kind = "dias"

    return Tolerance(column=coluna, kind=kind, amount=quantidade)


def parse_tolerances(specs: Sequence[str]) -> tuple[Tolerance, ...]:
    """Le varias tolerancias; a ultima declarada para uma coluna vence."""
    lidas: dict[str, Tolerance] = {}
    for spec in specs:
        tolerancia = parse_tolerance(spec)
        lidas[tolerancia.column] = tolerancia
    return tuple(lidas.values())


def _numbers(value_a: str, value_b: str) -> tuple[float, float] | None:
    """Os dois lados como numero, ou None se algum nao for numero."""
    separador = detect_decimal_separator([value_a, value_b]) or ","
    numero_a = parse_number(value_a, separador)
    numero_b = parse_number(value_b, separador)
    if numero_a is None or numero_b is None:
        return None
    return numero_a, numero_b


def _dates_delta_days(value_a: str, value_b: str) -> float | None:
    data_a = parse_date(value_a)
    data_b = parse_date(value_b)
    if data_a is None or data_b is None:
        return None
    return abs((data_a - data_b).total_seconds()) / _SECONDS_PER_DAY


def within_tolerance(tolerance: Tolerance, value_a: str, value_b: str) -> bool:
    """
    A diferenca entre os dois valores cabe na tolerancia declarada?

    Percentual usa como base o MAIOR valor absoluto do par: assim a conta
    nao muda de resultado dependendo de qual planilha veio primeiro.
    """
    if not value_a.strip() or not value_b.strip():
        return False  # ausencia nao e arredondamento

    if tolerance.kind == "dias":
        delta = _dates_delta_days(value_a, value_b)
        return delta is not None and delta <= tolerance.amount

    par = _numbers(value_a, value_b)
    if par is None:
        return False
    numero_a, numero_b = par
    diferenca = abs(numero_a - numero_b)

    if tolerance.kind == "absoluta":
        return diferenca <= tolerance.amount

    base = max(abs(numero_a), abs(numero_b))
    return diferenca <= base * (tolerance.amount / _PERCENT_BASE)


def index_tolerances(tolerances: tuple[Tolerance, ...]) -> dict[str, Tolerance]:
    """Tolerancias por nome de coluna (para consulta durante a comparacao)."""
    return {t.column: t for t in tolerances}


__all__ = [
    "Tolerance",
    "ToleranceKind",
    "index_tolerances",
    "parse_tolerance",
    "parse_tolerances",
    "within_tolerance",
]
