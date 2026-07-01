"""Testes para autotarefas.tasks.cleaning."""

from __future__ import annotations

from autotarefas.tasks.cleaning import (
    RULE_CPF,
    RULE_LOWERCASE,
    RULE_PHONE,
    RULE_WHITESPACE,
    clean_cell,
    format_cnpj,
    format_cpf,
    format_phone_br,
    normalize_email,
    normalize_whitespace,
)

# CPF valido sintetico (algoritmo oficial) e um invalido (blacklist).
_CPF_VALIDO = "52998224725"
_CPF_INVALIDO = "111.111.111-11"


class TestNormalizeWhitespace:
    def test_pontas_e_interno(self) -> None:
        assert normalize_whitespace("  Ana   Lima ") == "Ana Lima"

    def test_sem_mudanca(self) -> None:
        assert normalize_whitespace("Ana Lima") == "Ana Lima"

    def test_so_espacos_vira_vazio(self) -> None:
        assert normalize_whitespace("   ") == ""


class TestNormalizeEmail:
    def test_minusculo(self) -> None:
        assert normalize_email("Ana@Example.COM") == "ana@example.com"


class TestFormatCpf:
    def test_valido_sem_mascara_recebe_mascara(self) -> None:
        assert format_cpf(_CPF_VALIDO) == "529.982.247-25"

    def test_valido_com_mascara_mantem(self) -> None:
        assert format_cpf("529.982.247-25") == "529.982.247-25"

    def test_invalido_nao_muda(self) -> None:
        # blacklist -> nunca "conserta", devolve o original
        assert format_cpf(_CPF_INVALIDO) == _CPF_INVALIDO

    def test_incompleto_nao_muda(self) -> None:
        assert format_cpf("529") == "529"


class TestFormatCnpj:
    def test_valido_recebe_mascara(self) -> None:
        assert format_cnpj("11222333000181") == "11.222.333/0001-81"

    def test_invalido_nao_muda(self) -> None:
        assert format_cnpj("00.000.000/0000-00") == "00.000.000/0000-00"


class TestFormatPhoneBr:
    def test_celular(self) -> None:
        assert format_phone_br("11987654321") == "(11) 98765-4321"

    def test_fixo(self) -> None:
        assert format_phone_br("2133445566") == "(21) 3344-5566"

    def test_com_55_remove_codigo_pais(self) -> None:
        assert format_phone_br("5511987654321") == "(11) 98765-4321"

    def test_invalido_nao_muda(self) -> None:
        assert format_phone_br("9999") == "9999"


class TestCleanCell:
    def test_whitespace_sempre(self) -> None:
        after, rules = clean_cell("Ana   Lima")
        assert after == "Ana Lima"
        assert RULE_WHITESPACE in rules

    def test_email_lower(self) -> None:
        after, rules = clean_cell("Ana@Example.COM", lowercase=True)
        assert after == "ana@example.com"
        assert RULE_LOWERCASE in rules

    def test_cpf_valido_formata(self) -> None:
        after, rules = clean_cell(_CPF_VALIDO, cpf=True)
        assert after == "529.982.247-25"
        assert RULE_CPF in rules

    def test_cpf_invalido_nao_formata(self) -> None:
        after, rules = clean_cell(_CPF_INVALIDO, cpf=True)
        assert after == _CPF_INVALIDO
        assert RULE_CPF not in rules

    def test_phone_valido_formata(self) -> None:
        after, rules = clean_cell("11987654321", phone=True)
        assert after == "(11) 98765-4321"
        assert RULE_PHONE in rules

    def test_sem_mudanca_sem_regras(self) -> None:
        after, rules = clean_cell("Ana Lima")
        assert after == "Ana Lima"
        assert rules == ()

    def test_idempotente(self) -> None:
        # aplicar duas vezes nao muda o resultado nem gera novas regras
        first, _ = clean_cell("Ana@Example.COM", lowercase=True)
        second, rules2 = clean_cell(first, lowercase=True)
        assert second == first
        assert rules2 == ()
