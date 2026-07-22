"""Testes para autotarefas.tasks.validators."""

from __future__ import annotations

import re

import pytest

from autotarefas.tasks.issues import IssueCollector, IssueSeverity
from autotarefas.tasks.validators import (
    CNPJValidator,
    CPFValidator,
    EmailValidator,
    EnumValidator,
    MinLengthValidator,
    PhoneValidator,
    RangeValidator,
    RegexValidator,
    TypeValidator,
)

# ============================================================
# Fixtures e helpers
# ============================================================


@pytest.fixture
def collector() -> IssueCollector:
    """IssueCollector novo pra cada teste — sem state compartilhado."""
    return IssueCollector()


def _assert_one_issue(
    collector: IssueCollector,
    *,
    line: int,
    column: str,
    message_part: str,
    severity: IssueSeverity = IssueSeverity.ERROR,
) -> None:
    """
    Helper: verifica que collector tem exatamente 1 issue com os campos esperados.

    Reduz duplicacao de asserts entre testes.
    """
    assert len(collector) == 1, f"Esperava 1 issue, achou {len(collector)}"
    issue = collector.issues[0]
    assert issue.line == line
    assert issue.column == column
    assert message_part in issue.message, f"Mensagem '{issue.message}' nao contem '{message_part}'"
    assert issue.severity == severity


# ============================================================
# Tests: TypeValidator (int, float, date, bool)
# ============================================================


class TestTypeValidatorInt:
    """Testes do TypeValidator para tipo int."""

    @pytest.mark.parametrize("value", ["30", "0", "-5", "12345", "  30  "])
    def test_int_valido_passa(self, collector: IssueCollector, value: str) -> None:
        TypeValidator(expected_type="int").validate(
            value, line=1, column="idade", collector=collector
        )
        assert not collector

    @pytest.mark.parametrize("value", ["abc", "1.5", "30a", "12,5"])
    def test_int_invalido_adiciona_issue(self, collector: IssueCollector, value: str) -> None:
        TypeValidator(expected_type="int").validate(
            value, line=2, column="idade", collector=collector
        )
        _assert_one_issue(
            collector,
            line=2,
            column="idade",
            message_part="nao e um int valido",
        )


class TestTypeValidatorFloat:
    """Testes do TypeValidator para tipo float."""

    @pytest.mark.parametrize(
        "value",
        [
            "1.5",  # US
            "1,5",  # BR
            "0",
            "-3.14",
            "1000",
            "  1.5  ",  # com espaços
        ],
    )
    def test_float_valido_passa(self, collector: IssueCollector, value: str) -> None:
        TypeValidator(expected_type="float").validate(
            value, line=1, column="preco", collector=collector
        )
        assert not collector

    @pytest.mark.parametrize("value", ["abc", "1.5.6", "1,5,6"])
    def test_float_invalido_adiciona_issue(self, collector: IssueCollector, value: str) -> None:
        TypeValidator(expected_type="float").validate(
            value, line=3, column="preco", collector=collector
        )
        _assert_one_issue(
            collector,
            line=3,
            column="preco",
            message_part="nao e um float valido",
        )


class TestTypeValidatorDate:
    """
    Testes do TypeValidator para tipo date.

    Ate a 1.5.1 este validador so aceitava ISO — e uma data brasileira que
    o LEITOR entendia sem problema era recusada aqui, na mesma celula.
    Agora os dois usam `core.dates`.
    """

    @pytest.mark.parametrize(
        "value",
        [
            "2026-05-15",
            "2024-01-01",
            "1999-12-31",
            # formatos brasileiros — recusados antes da 1.5.1
            "15/05/2026",
            "15-05-2026",
            "15.05.2026",
            "2026/05/15",
            "15/05/2026 14:30",
            "29/02/2024",  # bissexto
        ],
    )
    def test_date_iso_valida(self, collector: IssueCollector, value: str) -> None:
        TypeValidator(expected_type="date").validate(
            value, line=1, column="data", collector=collector
        )
        assert not collector

    @pytest.mark.parametrize(
        "value",
        [
            "abc",
            "2026-13-01",  # mes invalido
            "31/02/2026",  # dia impossivel
            "29/02/2023",  # nao e bissexto
            "05/15/2026",  # padrao americano: RECUSADO, nao reinterpretado
            "100",  # numero NAO e serial de data fora do leitor
            "45000",
        ],
    )
    def test_date_invalida(self, collector: IssueCollector, value: str) -> None:
        TypeValidator(expected_type="date").validate(
            value, line=4, column="data", collector=collector
        )
        _assert_one_issue(
            collector,
            line=4,
            column="data",
            message_part="nao e um date valido",
        )


class TestTypeValidatorBool:
    """Testes do TypeValidator para tipo bool."""

    @pytest.mark.parametrize(
        "value",
        [
            "true",
            "false",
            "sim",
            "nao",
            "yes",
            "no",
            "1",
            "0",
            "TRUE",
            "False",  # case-insensitive
            "  sim  ",  # whitespace ignorado
        ],
    )
    def test_bool_valores_aceitos(self, collector: IssueCollector, value: str) -> None:
        TypeValidator(expected_type="bool").validate(
            value, line=1, column="ativo", collector=collector
        )
        assert not collector

    @pytest.mark.parametrize("value", ["talvez", "ok", "2", "verdadeiro"])
    def test_bool_invalido(self, collector: IssueCollector, value: str) -> None:
        TypeValidator(expected_type="bool").validate(
            value, line=5, column="ativo", collector=collector
        )
        _assert_one_issue(
            collector,
            line=5,
            column="ativo",
            message_part="nao e um bool valido",
        )


class TestTypeValidatorComum:
    """Comportamentos comuns do TypeValidator."""

    def test_vazio_e_ignorado(self, collector: IssueCollector) -> None:
        """Strings vazias nao geram issue (nullable cuida disso)."""
        TypeValidator(expected_type="int").validate("", line=1, column="x", collector=collector)
        assert not collector

    def test_whitespace_e_ignorado(self, collector: IssueCollector) -> None:
        TypeValidator(expected_type="int").validate("   ", line=1, column="x", collector=collector)
        assert not collector

    def test_severity_warning_customizada(self, collector: IssueCollector) -> None:
        TypeValidator(
            expected_type="int",
            severity=IssueSeverity.WARNING,
        ).validate("abc", line=1, column="x", collector=collector)
        _assert_one_issue(
            collector,
            line=1,
            column="x",
            message_part="abc",
            severity=IssueSeverity.WARNING,
        )

    def test_issue_inclui_value_original(self, collector: IssueCollector) -> None:
        """O valor original e preservado no issue (debug)."""
        TypeValidator(expected_type="int").validate("abc", line=1, column="x", collector=collector)
        assert collector.issues[0].value == "abc"


# ============================================================
# Tests: RegexValidator
# ============================================================


class TestRegexValidator:
    """Testes do RegexValidator."""

    def test_pattern_match_passa(self, collector: IssueCollector) -> None:
        cep_pattern = re.compile(r"\d{5}-?\d{3}")
        RegexValidator(pattern=cep_pattern).validate(
            "01310-100", line=1, column="cep", collector=collector
        )
        assert not collector

    def test_pattern_no_match_adiciona_issue(self, collector: IssueCollector) -> None:
        cep_pattern = re.compile(r"\d{5}-?\d{3}")
        RegexValidator(pattern=cep_pattern, message="CEP invalido").validate(
            "abc", line=2, column="cep", collector=collector
        )
        _assert_one_issue(collector, line=2, column="cep", message_part="CEP invalido")

    def test_fullmatch_exige_match_completo(self, collector: IssueCollector) -> None:
        """re.fullmatch exige que TODO o valor case, nao so um trecho."""
        digits_pattern = re.compile(r"\d+")
        RegexValidator(pattern=digits_pattern).validate(
            "123abc", line=3, column="x", collector=collector
        )
        # "123abc" contem digitos, mas "abc" no fim faz fullmatch falhar
        assert len(collector) == 1

    def test_message_default_generica(self, collector: IssueCollector) -> None:
        """Message default deve ser 'Formato invalido' (definido na classe)."""
        pattern = re.compile(r"\d+")
        RegexValidator(pattern=pattern).validate("abc", line=1, column="x", collector=collector)
        assert collector.issues[0].message == "Formato invalido"

    def test_vazio_e_ignorado(self, collector: IssueCollector) -> None:
        pattern = re.compile(r"\d+")
        RegexValidator(pattern=pattern).validate("", line=1, column="x", collector=collector)
        assert not collector


# ============================================================
# Tests: RangeValidator
# ============================================================


class TestRangeValidator:
    """Testes do RangeValidator."""

    @pytest.mark.parametrize("value", ["50", "0", "150"])
    def test_dentro_do_intervalo_passa(self, collector: IssueCollector, value: str) -> None:
        RangeValidator(min_value=0, max_value=150).validate(
            value, line=1, column="idade", collector=collector
        )
        assert not collector

    def test_abaixo_do_minimo_gera_issue(self, collector: IssueCollector) -> None:
        RangeValidator(min_value=0).validate("-5", line=2, column="idade", collector=collector)
        _assert_one_issue(collector, line=2, column="idade", message_part="menor que o minimo")

    def test_acima_do_maximo_gera_issue(self, collector: IssueCollector) -> None:
        RangeValidator(max_value=150).validate("200", line=3, column="idade", collector=collector)
        _assert_one_issue(collector, line=3, column="idade", message_part="maior que o maximo")

    def test_so_min_definido(self, collector: IssueCollector) -> None:
        """Sem max — aceita qualquer valor >= min."""
        RangeValidator(min_value=0).validate("9999", line=1, column="x", collector=collector)
        assert not collector

    def test_so_max_definido(self, collector: IssueCollector) -> None:
        """Sem min — aceita qualquer valor <= max."""
        RangeValidator(max_value=100).validate("-9999", line=1, column="x", collector=collector)
        assert not collector

    def test_sem_limites_nao_faz_nada(self, collector: IssueCollector) -> None:
        """Caso degenerado: sem min e sem max — sempre passa."""
        RangeValidator().validate("100", line=1, column="x", collector=collector)
        assert not collector

    def test_aceita_decimal_br(self, collector: IssueCollector) -> None:
        """Aceita virgula como separador decimal."""
        RangeValidator(min_value=0, max_value=10).validate(
            "5,5", line=1, column="x", collector=collector
        )
        assert not collector

    def test_nao_numero_e_ignorado(self, collector: IssueCollector) -> None:
        """RangeValidator ignora valores nao-numericos (TypeValidator pega)."""
        RangeValidator(min_value=0, max_value=10).validate(
            "abc", line=1, column="x", collector=collector
        )
        assert not collector  # nao reclamou

    def test_vazio_e_ignorado(self, collector: IssueCollector) -> None:
        RangeValidator(min_value=0).validate("", line=1, column="x", collector=collector)
        assert not collector


# ============================================================
# Tests: EnumValidator
# ============================================================


class TestEnumValidator:
    """Testes do EnumValidator."""

    @pytest.mark.parametrize("value", ["SP", "RJ", "MG"])
    def test_valor_aceito_passa(self, collector: IssueCollector, value: str) -> None:
        EnumValidator(allowed_values=("SP", "RJ", "MG")).validate(
            value, line=1, column="uf", collector=collector
        )
        assert not collector

    def test_valor_nao_aceito_gera_issue(self, collector: IssueCollector) -> None:
        EnumValidator(allowed_values=("SP", "RJ", "MG")).validate(
            "XX", line=1, column="uf", collector=collector
        )
        _assert_one_issue(collector, line=1, column="uf", message_part="nao esta entre os aceitos")

    def test_case_sensitive_default(self, collector: IssueCollector) -> None:
        """Por default, 'sp' nao bate com 'SP'."""
        EnumValidator(allowed_values=("SP",)).validate(
            "sp", line=1, column="uf", collector=collector
        )
        assert len(collector) == 1

    def test_case_insensitive_opcional(self, collector: IssueCollector) -> None:
        EnumValidator(allowed_values=("SP", "RJ"), case_sensitive=False).validate(
            "sp", line=1, column="uf", collector=collector
        )
        assert not collector

    def test_vazio_e_ignorado(self, collector: IssueCollector) -> None:
        EnumValidator(allowed_values=("A", "B")).validate(
            "", line=1, column="x", collector=collector
        )
        assert not collector


# ============================================================
# Tests: CPFValidator e CNPJValidator
# ============================================================


class TestCPFValidator:
    """Testes do CPFValidator."""

    def test_cpf_valido_passa(self, collector: IssueCollector) -> None:
        CPFValidator().validate("529.982.247-25", line=1, column="cpf", collector=collector)
        assert not collector

    def test_cpf_invalido_gera_issue(self, collector: IssueCollector) -> None:
        CPFValidator().validate("529.982.247-26", line=2, column="cpf", collector=collector)
        _assert_one_issue(collector, line=2, column="cpf", message_part="CPF invalido")

    def test_cpf_blacklist_gera_issue(self, collector: IssueCollector) -> None:
        CPFValidator().validate("111.111.111-11", line=3, column="cpf", collector=collector)
        assert len(collector) == 1

    def test_vazio_e_ignorado(self, collector: IssueCollector) -> None:
        CPFValidator().validate("", line=1, column="cpf", collector=collector)
        assert not collector


class TestCNPJValidator:
    """Testes do CNPJValidator."""

    def test_cnpj_valido_passa(self, collector: IssueCollector) -> None:
        CNPJValidator().validate("11.222.333/0001-81", line=1, column="cnpj", collector=collector)
        assert not collector

    def test_cnpj_invalido_gera_issue(self, collector: IssueCollector) -> None:
        CNPJValidator().validate("11.222.333/0001-82", line=2, column="cnpj", collector=collector)
        _assert_one_issue(collector, line=2, column="cnpj", message_part="CNPJ invalido")

    def test_vazio_e_ignorado(self, collector: IssueCollector) -> None:
        CNPJValidator().validate("", line=1, column="cnpj", collector=collector)
        assert not collector


# ============================================================
# Tests: Acumulacao (varios validators no mesmo collector)
# ============================================================


class TestAcumulacao:
    """Testes que varios validators acumulam no mesmo collector."""

    def test_dois_validators_acumulam_issues(self, collector: IssueCollector) -> None:
        """Validators aplicados em sequencia acumulam — nao sobrescrevem."""
        TypeValidator(expected_type="int").validate(
            "abc", line=1, column="idade", collector=collector
        )
        CPFValidator().validate("111.111.111-11", line=2, column="cpf", collector=collector)

        assert len(collector) == 2
        assert "int valido" in collector.issues[0].message
        assert "CPF invalido" in collector.issues[1].message

    def test_collector_independente_entre_testes(self, collector: IssueCollector) -> None:
        """Fixture cria collector novo — nao tem residuo de outros testes."""
        assert len(collector) == 0


# ============================================================
# EmailValidator
# ============================================================


class TestEmailValidator:
    """Validacao de formato de e-mail."""

    @pytest.mark.parametrize(
        "email",
        [
            "ana@example.com",
            "ana.lima@example.com",
            "joao_silva@empresa.io",
            "a+tag@sub.dominio.com.br",
            "nome123@host-x.co",
        ],
    )
    def test_validos(self, email: str, collector: IssueCollector) -> None:
        EmailValidator().validate(email, line=2, column="email", collector=collector)
        assert collector.is_valid

    @pytest.mark.parametrize(
        "email",
        [
            "ana",
            "ana@",
            "@example.com",
            "ana@dominio",
            "ana@@example.com",
            "ana lima@example.com",
            "ana@exa mple.com",
        ],
    )
    def test_invalidos(self, email: str, collector: IssueCollector) -> None:
        EmailValidator().validate(email, line=2, column="email", collector=collector)
        assert not collector.is_valid
        assert len(collector.errors) == 1

    def test_vazio_ignorado(self, collector: IssueCollector) -> None:
        EmailValidator().validate("", line=2, column="email", collector=collector)
        EmailValidator().validate("   ", line=3, column="email", collector=collector)
        assert collector.total == 0


# ============================================================
# PhoneValidator
# ============================================================


class TestPhoneValidator:
    """Validacao de telefone brasileiro (wrapper de is_valid_phone_br)."""

    @pytest.mark.parametrize(
        "phone",
        [
            "(11) 98765-4321",
            "11987654321",
            "+55 11 98765-4321",
            "(21) 3334-4444",
            "2133445566",
        ],
    )
    def test_validos(self, phone: str, collector: IssueCollector) -> None:
        PhoneValidator().validate(phone, line=2, column="telefone", collector=collector)
        assert collector.is_valid

    @pytest.mark.parametrize(
        "phone",
        [
            "9999",
            "(20) 98765-4321",
            "1187654321",
            "telefone",
        ],
    )
    def test_invalidos(self, phone: str, collector: IssueCollector) -> None:
        PhoneValidator().validate(phone, line=2, column="telefone", collector=collector)
        assert not collector.is_valid
        assert len(collector.errors) == 1

    def test_vazio_ignorado(self, collector: IssueCollector) -> None:
        PhoneValidator().validate("", line=2, column="telefone", collector=collector)
        assert collector.total == 0


# ============================================================
# MinLengthValidator
# ============================================================


class TestMinLengthValidator:
    """Comprimento minimo de texto (apos strip)."""

    @pytest.mark.parametrize("value", ["Ana", "Maria Silva", "Jose"])
    def test_validos(self, value: str, collector: IssueCollector) -> None:
        MinLengthValidator(min_length=3).validate(value, line=2, column="nome", collector=collector)
        assert collector.is_valid

    @pytest.mark.parametrize("value", ["A", "Jo", " X "])
    def test_invalidos(self, value: str, collector: IssueCollector) -> None:
        MinLengthValidator(min_length=3).validate(value, line=2, column="nome", collector=collector)
        assert not collector.is_valid
        assert len(collector.errors) == 1

    def test_vazio_ignorado(self, collector: IssueCollector) -> None:
        MinLengthValidator(min_length=3).validate("", line=2, column="nome", collector=collector)
        assert collector.total == 0

    def test_strip_antes_de_medir(self, collector: IssueCollector) -> None:
        # "  Ana  " tem 3 caracteres uteis -> valido
        MinLengthValidator(min_length=3).validate(
            "  Ana  ", line=2, column="nome", collector=collector
        )
        assert collector.is_valid
