"""Testes para autotarefas.tasks.validators_br."""

from __future__ import annotations

import pytest

from autotarefas.tasks.validators_br import is_valid_cnpj, is_valid_cpf

# ============================================================
# CPFs/CNPJs validos usados como fixtures (sinteticos, nao pessoais)
# ============================================================

# CPFs validos (gerados pelos algoritmos oficiais).
# Nenhum corresponde a pessoa real conhecida.
_CPF_VALIDO_1 = "529.982.247-25"
_CPF_VALIDO_2 = "111.444.777-35"
_CPF_VALIDO_3 = "052.482.396-05"

# CNPJs validos (sinteticos)
_CNPJ_VALIDO_1 = "11.222.333/0001-81"
_CNPJ_VALIDO_2 = "11.444.777/0001-61"


# ============================================================
# Tests: is_valid_cpf
# ============================================================


class TestIsValidCpfValidos:
    """CPFs validos em varios formatos de entrada."""

    @pytest.mark.parametrize(
        "cpf",
        [
            _CPF_VALIDO_1,
            _CPF_VALIDO_2,
            _CPF_VALIDO_3,
        ],
    )
    def test_com_mascara(self, cpf: str) -> None:
        """CPFs validos com mascara completa (XXX.XXX.XXX-XX)."""
        assert is_valid_cpf(cpf) is True

    @pytest.mark.parametrize(
        "cpf",
        [
            "52998224725",
            "11144477735",
            "05248239605",
        ],
    )
    def test_sem_mascara(self, cpf: str) -> None:
        """CPFs validos so com digitos."""
        assert is_valid_cpf(cpf) is True

    def test_com_espacos_extras(self) -> None:
        """Espacos sao ignorados pelo _only_digits."""
        assert is_valid_cpf(" 529.982.247-25 ") is True

    def test_com_separadores_alternativos(self) -> None:
        """Outros separadores tambem funcionam (espacos, virgulas, qualquer non-digit)."""
        assert is_valid_cpf("529 982 247 25") is True
        assert is_valid_cpf("529,982,247,25") is True
        assert is_valid_cpf("529/982/247/25") is True


class TestIsValidCpfInvalidos:
    """CPFs invalidos por motivos variados."""

    def test_dv1_errado(self) -> None:
        """Modifica o 10o digito (DV1) — deve falhar."""
        # CPF valido: 529.982.247-25 (DV1=2, DV2=5)
        assert is_valid_cpf("529.982.247-35") is False  # DV1 era 2, virou 3

    def test_dv2_errado(self) -> None:
        """Modifica o 11o digito (DV2) — deve falhar."""
        # CPF valido: 529.982.247-25 (DV1=2, DV2=5)
        assert is_valid_cpf("529.982.247-26") is False  # DV2 era 5, virou 6

    @pytest.mark.parametrize(
        "cpf",
        [
            "",  # vazio
            "1",  # 1 digito
            "1234567890",  # 10 digitos (falta um)
            "123456789012",  # 12 digitos (sobra um)
            "0000000000000000",  # muitos digitos
        ],
    )
    def test_tamanho_errado(self, cpf: str) -> None:
        """CPFs com numero errado de digitos."""
        assert is_valid_cpf(cpf) is False

    @pytest.mark.parametrize(
        "cpf",
        [
            "abc",
            "abcdefghijk",  # 11 chars mas nao digitos
            "...",
            "---",
        ],
    )
    def test_sem_digitos(self, cpf: str) -> None:
        """Strings sem digitos ficam vazias apos _only_digits."""
        assert is_valid_cpf(cpf) is False


class TestIsValidCpfBlacklist:
    """CPFs com todos digitos iguais — passam no calculo mas sao oficialmente invalidos."""

    @pytest.mark.parametrize(
        "cpf",
        [
            "000.000.000-00",
            "111.111.111-11",
            "222.222.222-22",
            "333.333.333-33",
            "444.444.444-44",
            "555.555.555-55",
            "666.666.666-66",
            "777.777.777-77",
            "888.888.888-88",
            "999.999.999-99",
        ],
    )
    def test_todos_digitos_iguais_sao_invalidos(self, cpf: str) -> None:
        assert is_valid_cpf(cpf) is False


# ============================================================
# Tests: is_valid_cnpj
# ============================================================


class TestIsValidCnpjValidos:
    """CNPJs validos em varios formatos."""

    @pytest.mark.parametrize(
        "cnpj",
        [
            _CNPJ_VALIDO_1,
            _CNPJ_VALIDO_2,
        ],
    )
    def test_com_mascara(self, cnpj: str) -> None:
        """CNPJs validos com mascara (XX.XXX.XXX/XXXX-XX)."""
        assert is_valid_cnpj(cnpj) is True

    @pytest.mark.parametrize(
        "cnpj",
        [
            "11222333000181",
            "11444777000161",
        ],
    )
    def test_sem_mascara(self, cnpj: str) -> None:
        """CNPJs validos so com digitos."""
        assert is_valid_cnpj(cnpj) is True

    def test_com_espacos_extras(self) -> None:
        assert is_valid_cnpj(" 11.222.333/0001-81 ") is True


class TestIsValidCnpjInvalidos:
    """CNPJs invalidos."""

    def test_dv1_errado(self) -> None:
        """Modifica o 13o digito (DV1) — falha."""
        # CNPJ valido: 11.222.333/0001-81 (DV1=8, DV2=1)
        assert is_valid_cnpj("11.222.333/0001-91") is False

    def test_dv2_errado(self) -> None:
        """Modifica o 14o digito (DV2) — falha."""
        assert is_valid_cnpj("11.222.333/0001-82") is False

    @pytest.mark.parametrize(
        "cnpj",
        [
            "",
            "1",
            "1234567890123",  # 13 digitos
            "123456789012345",  # 15 digitos
        ],
    )
    def test_tamanho_errado(self, cnpj: str) -> None:
        assert is_valid_cnpj(cnpj) is False

    @pytest.mark.parametrize(
        "cnpj",
        [
            "abc",
            "abcdefghijklmn",  # 14 chars mas sem digitos
            "..............",
        ],
    )
    def test_sem_digitos(self, cnpj: str) -> None:
        assert is_valid_cnpj(cnpj) is False


class TestIsValidCnpjBlacklist:
    """CNPJs com todos digitos iguais."""

    @pytest.mark.parametrize(
        "cnpj",
        [
            "00.000.000/0000-00",
            "11.111.111/1111-11",
            "22.222.222/2222-22",
            "99.999.999/9999-99",
        ],
    )
    def test_todos_digitos_iguais_sao_invalidos(self, cnpj: str) -> None:
        assert is_valid_cnpj(cnpj) is False


# ============================================================
# Tests: Independencia (CPF nao valida como CNPJ e vice-versa)
# ============================================================


class TestIndependencia:
    """Garante que as duas funcoes nao se confundem."""

    def test_cpf_valido_nao_e_cnpj_valido(self) -> None:
        """CPF tem 11 digitos, CNPJ tem 14 — nunca devem cruzar."""
        assert is_valid_cnpj(_CPF_VALIDO_1) is False  # 11 digits != 14

    def test_cnpj_valido_nao_e_cpf_valido(self) -> None:
        """CNPJ tem 14 digitos, CPF tem 11 — nunca devem cruzar."""
        assert is_valid_cpf(_CNPJ_VALIDO_1) is False  # 14 digits != 11
