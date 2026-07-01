"""
Validadores de conteudo de celulas.

Cada validador implementa a interface `Validator` (Protocol) com um
metodo `validate()`. Quando encontram problema, adicionam ao
`IssueCollector` em vez de levantar excecao — permite acumular varios
erros e retornar todos juntos no relatorio.

Validadores ignoram valores vazios ("" ou whitespace) — nulidade e
responsabilidade do `nullable` no schema, nao do validador.

Validadores implementados:
- TypeValidator   — int, float, date, bool
- RegexValidator  — formato customizado (CEP, telefone, email, etc)
- RangeValidator  — intervalo numerico (min/max)
- EnumValidator   — valor em lista de aceitos
- CPFValidator    — wrapper de is_valid_cpf
- CNPJValidator   — wrapper de is_valid_cnpj

Uso:
    validators = [
        TypeValidator(expected_type="int"),
        RangeValidator(min_value=0, max_value=150),
    ]

    collector = IssueCollector()
    for v in validators:
        v.validate("30", line=7, column="idade", collector=collector)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from autotarefas.tasks.issues import IssueCollector, IssueSeverity
from autotarefas.tasks.validators_br import is_valid_cnpj, is_valid_cpf, is_valid_phone_br

# ============================================================
# Tipos
# ============================================================

#: Tipos suportados pelo TypeValidator.
ValidatableType = Literal["int", "float", "date", "bool"]


# ============================================================
# Helper interno
# ============================================================


def _is_empty(value: str) -> bool:
    """
    True se a string e vazia ou contem so whitespace.

    Validadores ignoram empty — nulidade e tratada pelo schema (nullable).
    """
    return not value or not value.strip()


# ============================================================
# Interface comum (Protocol)
# ============================================================


class Validator(Protocol):
    """
    Interface comum de validadores (PEP 544 - Structural typing).

    Qualquer classe que implemente o metodo `validate()` com a assinatura
    abaixo e considerada um Validator pelo mypy — NAO precisa herdar.

    O metodo nao retorna valor — apenas adiciona issues ao collector
    quando encontra problema. Isso permite acumular varios erros.
    """

    def validate(
        self,
        value: str,
        *,
        line: int,
        column: str,
        collector: IssueCollector,
    ) -> None:
        """
        Valida um valor. Adiciona issue ao collector se inválido.

        Args:
            value: Valor da célula (já convertido pra string).
            line: Número da linha (1-based).
            column: Nome da coluna.
            collector: Onde acumular issues encontrados.
        """
        ...  # pragma: no cover (Protocol — implementacao nas classes)


# ============================================================
# TypeValidator — int, float, date, bool
# ============================================================


@dataclass(frozen=True, slots=True)
class TypeValidator:
    """
    Valida que o valor pode ser convertido pro tipo esperado.

    Tipos suportados:
    - ``int``    — `int(value)`
    - ``float``  — `float(value)`, aceita virgula ou ponto como decimal
    - ``date``   — formato ISO (YYYY-MM-DD), via `datetime.fromisoformat`
    - ``bool``   — aceita "true"/"false", "sim"/"nao", "1"/"0" (case-insensitive)

    Para tipo "str" nao ha validacao (qualquer string passa) — nao instancia.

    Attributes:
        expected_type: Tipo esperado.
        severity: Severidade do issue (default ERROR).
    """

    expected_type: ValidatableType
    severity: IssueSeverity = IssueSeverity.ERROR

    def validate(
        self,
        value: str,
        *,
        line: int,
        column: str,
        collector: IssueCollector,
    ) -> None:
        if _is_empty(value):
            return

        if not self._can_convert(value):
            collector.add(
                line=line,
                column=column,
                message=f"Valor '{value}' nao e um {self.expected_type} valido",
                severity=self.severity,
                value=value,
            )

    def _can_convert(self, value: str) -> bool:
        """
        Tenta converter pro tipo esperado. Retorna True se conseguir.

        Funcao pura sem efeitos colaterais — facil de testar isoladamente.
        """
        try:
            if self.expected_type == "int":
                int(value.strip())
            elif self.expected_type == "float":
                # Aceita decimal BR (virgula) e US (ponto)
                float(value.strip().replace(",", "."))
            elif self.expected_type == "date":
                datetime.fromisoformat(value.strip())
            elif self.expected_type == "bool" and value.strip().lower() not in {
                "true",
                "false",
                "sim",
                "nao",
                "yes",
                "no",
                "1",
                "0",
            }:
                return False
        except (ValueError, TypeError):
            return False
        return True


# ============================================================
# RegexValidator — formato customizado
# ============================================================


@dataclass(frozen=True, slots=True)
class RegexValidator:
    """
    Valida que o valor casa com uma regex (usando `fullmatch`).

    Usar `re.fullmatch` (nao `re.search`) — exige que TODA a string case,
    nao so um trecho. Evita falsos positivos.

    Aceita pattern ja compilado (`re.Pattern[str]`). Pra compilar antes,
    use `re.compile(r"...")`.

    Attributes:
        pattern: Regex compilada.
        message: Mensagem customizada do erro (default generica).
        severity: Severidade (default ERROR).
    """

    pattern: re.Pattern[str]
    message: str = "Formato invalido"
    severity: IssueSeverity = IssueSeverity.ERROR

    def validate(
        self,
        value: str,
        *,
        line: int,
        column: str,
        collector: IssueCollector,
    ) -> None:
        if _is_empty(value):
            return

        if not self.pattern.fullmatch(value):
            collector.add(
                line=line,
                column=column,
                message=self.message,
                severity=self.severity,
                value=value,
            )


# ============================================================
# RangeValidator — intervalo numerico
# ============================================================


@dataclass(frozen=True, slots=True)
class RangeValidator:
    """
    Valida que valor numerico esta dentro de um intervalo [min, max].

    Ambos os limites sao OPCIONAIS — pode ter so min, so max, ou ambos.
    Quando ambos sao None, o validador nao faz nada (caso degenerado).

    Tenta converter o valor pra float. Se nao conseguir, o validador
    NAO reclama (deixa pro TypeValidator fazer isso). Mantem
    responsabilidades separadas.

    Attributes:
        min_value: Valor minimo (inclusive). None = sem minimo.
        max_value: Valor maximo (inclusive). None = sem maximo.
        severity: Severidade (default ERROR).
    """

    min_value: float | None = None
    max_value: float | None = None
    severity: IssueSeverity = IssueSeverity.ERROR

    def validate(
        self,
        value: str,
        *,
        line: int,
        column: str,
        collector: IssueCollector,
    ) -> None:
        if _is_empty(value):
            return

        try:
            num = float(value.strip().replace(",", "."))
        except (ValueError, TypeError):
            # Nao e numero — deixa o TypeValidator reclamar
            return

        if self.min_value is not None and num < self.min_value:
            collector.add(
                line=line,
                column=column,
                message=f"Valor {num} menor que o minimo {self.min_value}",
                severity=self.severity,
                value=value,
            )
            return

        if self.max_value is not None and num > self.max_value:
            collector.add(
                line=line,
                column=column,
                message=f"Valor {num} maior que o maximo {self.max_value}",
                severity=self.severity,
                value=value,
            )


# ============================================================
# EnumValidator — valor em lista de aceitos
# ============================================================


@dataclass(frozen=True, slots=True)
class EnumValidator:
    """
    Valida que o valor esta em uma lista predefinida.

    Util pra colunas como "status" (ativo/inativo), "uf" (SP, RJ, ...),
    "categoria" (A, B, C).

    `allowed_values` e uma TUPLA (nao list) porque dataclasses frozen
    nao podem ter campos mutaveis como default.

    Attributes:
        allowed_values: Tupla de valores aceitos.
        case_sensitive: Se True (default), compara exatamente.
            Se False, ignora maiusculas/minusculas.
        severity: Severidade (default ERROR).
    """

    allowed_values: tuple[str, ...]
    case_sensitive: bool = True
    severity: IssueSeverity = IssueSeverity.ERROR

    def validate(
        self,
        value: str,
        *,
        line: int,
        column: str,
        collector: IssueCollector,
    ) -> None:
        if _is_empty(value):
            return

        # Normaliza pra comparacao
        candidate = value.strip()
        if self.case_sensitive:
            allowed = self.allowed_values
        else:
            candidate = candidate.lower()
            allowed = tuple(v.lower() for v in self.allowed_values)

        if candidate not in allowed:
            collector.add(
                line=line,
                column=column,
                message=(f"Valor '{value}' nao esta entre os aceitos: {list(self.allowed_values)}"),
                severity=self.severity,
                value=value,
            )


# ============================================================
# CPFValidator e CNPJValidator — wrappers
# ============================================================


@dataclass(frozen=True, slots=True)
class CPFValidator:
    """
    Valida CPF brasileiro (algoritmo modulo 11).

    Wrapper de `is_valid_cpf` de validators_br.py. Aceita CPF com ou
    sem mascara.

    Attributes:
        severity: Severidade (default ERROR).
    """

    severity: IssueSeverity = IssueSeverity.ERROR

    def validate(
        self,
        value: str,
        *,
        line: int,
        column: str,
        collector: IssueCollector,
    ) -> None:
        if _is_empty(value):
            return

        if not is_valid_cpf(value):
            collector.add(
                line=line,
                column=column,
                message=f"CPF invalido: '{value}'",
                severity=self.severity,
                value=value,
            )


@dataclass(frozen=True, slots=True)
class CNPJValidator:
    """
    Valida CNPJ brasileiro (algoritmo modulo 11).

    Wrapper de `is_valid_cnpj` de validators_br.py. Aceita CNPJ com ou
    sem mascara.

    Attributes:
        severity: Severidade (default ERROR).
    """

    severity: IssueSeverity = IssueSeverity.ERROR

    def validate(
        self,
        value: str,
        *,
        line: int,
        column: str,
        collector: IssueCollector,
    ) -> None:
        if _is_empty(value):
            return

        if not is_valid_cnpj(value):
            collector.add(
                line=line,
                column=column,
                message=f"CNPJ invalido: '{value}'",
                severity=self.severity,
                value=value,
            )


# ============================================================
# EmailValidator — formato de e-mail
# ============================================================

#: Regex pratica de e-mail (cobre a vasta maioria dos casos reais).
#: Nao implementa a RFC 5322 completa de proposito — seria complexa
#: demais e, na pratica, rejeitaria poucos casos a mais.
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


@dataclass(frozen=True, slots=True)
class EmailValidator:
    """
    Valida que o valor tem formato de e-mail.

    Usa `re.fullmatch` com um padrao pratico (local@dominio.tld). Aceita
    subdominios (a@x.y.com) e os caracteres comuns na parte local
    (``. _ % + -``). Ignora valores vazios (nulidade e do schema).

    Attributes:
        severity: Severidade (default ERROR).
    """

    severity: IssueSeverity = IssueSeverity.ERROR

    def validate(
        self,
        value: str,
        *,
        line: int,
        column: str,
        collector: IssueCollector,
    ) -> None:
        if _is_empty(value):
            return

        if not _EMAIL_PATTERN.fullmatch(value.strip()):
            collector.add(
                line=line,
                column=column,
                message=f"E-mail invalido: '{value}'",
                severity=self.severity,
                value=value,
            )


# ============================================================
# PhoneValidator — telefone brasileiro
# ============================================================


@dataclass(frozen=True, slots=True)
class PhoneValidator:
    """
    Valida telefone brasileiro (fixo ou celular).

    Wrapper de `is_valid_phone_br`. Aceita com ou sem mascara e com ou
    sem +55. Ignora valores vazios.

    Attributes:
        severity: Severidade (default ERROR).
    """

    severity: IssueSeverity = IssueSeverity.ERROR

    def validate(
        self,
        value: str,
        *,
        line: int,
        column: str,
        collector: IssueCollector,
    ) -> None:
        if _is_empty(value):
            return

        if not is_valid_phone_br(value):
            collector.add(
                line=line,
                column=column,
                message=f"Telefone invalido: '{value}'",
                severity=self.severity,
                value=value,
            )


# ============================================================
# MinLengthValidator — comprimento minimo
# ============================================================


@dataclass(frozen=True, slots=True)
class MinLengthValidator:
    """
    Valida que o valor tem um comprimento minimo (apos strip).

    Util pra campos como "nome", que nao podem ter 1 caractere. Ignora
    valores vazios — obrigatoriedade e do schema (nullable).

    Attributes:
        min_length: Comprimento minimo (inclusive).
        severity: Severidade (default ERROR).
    """

    min_length: int
    severity: IssueSeverity = IssueSeverity.ERROR

    def validate(
        self,
        value: str,
        *,
        line: int,
        column: str,
        collector: IssueCollector,
    ) -> None:
        if _is_empty(value):
            return

        length = len(value.strip())
        if length < self.min_length:
            collector.add(
                line=line,
                column=column,
                message=(
                    f"Valor muito curto: '{value}' tem {length} caractere(s), "
                    f"minimo {self.min_length}"
                ),
                severity=self.severity,
                value=value,
            )


__all__ = [
    "CNPJValidator",
    "CPFValidator",
    "EmailValidator",
    "EnumValidator",
    "MinLengthValidator",
    "PhoneValidator",
    "RangeValidator",
    "RegexValidator",
    "TypeValidator",
    "ValidatableType",
    "Validator",
]
