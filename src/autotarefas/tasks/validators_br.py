"""
Validadores de identificadores brasileiros: CPF e CNPJ.

Funcoes puras (sem efeitos colaterais, sem excecoes) que retornam bool.
Aceitam strings com ou sem mascara (123.456.789-09 ou 12345678909).

Algoritmos oficiais da Receita Federal (modulo 11 com pesos).

Uso:
    from autotarefas.tasks.validators_br import is_valid_cpf, is_valid_cnpj

    is_valid_cpf("123.456.789-09")       → False (DV nao bate)
    is_valid_cpf("111.111.111-11")       → False (blacklist)
    is_valid_cpf("12345678909")          → False
    is_valid_cpf("529.982.247-25")       → True

    is_valid_cnpj("12.345.678/0001-95")  → True
    is_valid_cnpj("00.000.000/0000-00")  → False (blacklist)
"""

from __future__ import annotations

# ============================================================
# Helpers internos
# ============================================================


def _only_digits(value: str) -> str:
    """
    Remove tudo que nao for digito da string.

    Exemplos:
        "123.456.789-09"  → "12345678909"
        "12 345 678"      → "12345678"
        ""                → ""
        "abc"             → ""

    Usar str.isdigit() em compreensao e a forma mais idiomatica e rapida
    em Python pra esse caso (mais rapido que regex pra strings curtas).
    """
    return "".join(ch for ch in value if ch.isdigit())


def _calculate_dv(digits: str, weights: list[int]) -> int:
    """
    Calcula um digito verificador (DV) pelo algoritmo modulo 11.

    Algoritmo:
        1. Multiplica cada digito pelo peso correspondente
        2. Soma os produtos
        3. Calcula resto da divisao por 11
        4. Se resto < 2, DV = 0
        5. Senao, DV = 11 - resto

    Args:
        digits: String com apenas digitos (ex: "123456789").
        weights: Pesos a aplicar (mesmo tamanho que digits).

    Returns:
        Digito verificador (0-9).

    Pre-condicoes:
        - len(digits) == len(weights)
        - digits contem so caracteres '0'-'9'

    Exemplo (CPF DV1):
        _calculate_dv("123456789", [10, 9, 8, 7, 6, 5, 4, 3, 2])
        → soma = 210, resto = 210 % 11 = 1, dv = 0 (porque 1 < 2)
    """
    total = sum(int(d) * w for d, w in zip(digits, weights, strict=True))
    remainder = total % 11
    if remainder < 2:  # noqa: PLR2004
        return 0
    return 11 - remainder


# ============================================================
# Validacao de CPF
# ============================================================

#: Pesos para o 1o digito verificador do CPF (aplicados aos 9 primeiros digitos).
_CPF_WEIGHTS_DV1: list[int] = [10, 9, 8, 7, 6, 5, 4, 3, 2]

#: Pesos para o 2o digito verificador do CPF (aplicados aos 10 primeiros).
_CPF_WEIGHTS_DV2: list[int] = [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]


def is_valid_cpf(value: str) -> bool:
    """
    Valida um CPF brasileiro.

    Aceita com ou sem mascara. Verifica:
    1. String nao vazia
    2. Tem 11 digitos apos remover mascara
    3. Nao esta na blacklist de CPFs com todos digitos iguais
       ("000.000.000-00", "111.111.111-11", etc).
       Estes passariam no calculo de DV mas sao oficialmente invalidos.
    4. Os 2 digitos verificadores conferem.

    Args:
        value: CPF a validar (com ou sem mascara).

    Returns:
        True se valido, False caso contrario.

    Exemplos:
        >>> is_valid_cpf("529.982.247-25")
        True
        >>> is_valid_cpf("52998224725")
        True
        >>> is_valid_cpf("529.982.247-26")  # DV errado
        False
        >>> is_valid_cpf("111.111.111-11")  # blacklist
        False
        >>> is_valid_cpf("")
        False
        >>> is_valid_cpf("abc")
        False
    """
    digits = _only_digits(value)

    # 1. Tem que ter exatamente 11 digitos
    if len(digits) != 11:  # noqa: PLR2004
        return False

    # 2. Blacklist: CPFs com todos digitos iguais.
    # Estes passariam no calculo mas sao oficialmente invalidos.
    # O Python permite essa checagem elegante:
    if len(set(digits)) == 1:
        return False

    # 3. Calcula DV1 a partir dos 9 primeiros digitos
    dv1_calculado = _calculate_dv(digits[:9], _CPF_WEIGHTS_DV1)
    if dv1_calculado != int(digits[9]):
        return False

    # 4. Calcula DV2 a partir dos 10 primeiros (incluindo DV1)
    dv2_calculado = _calculate_dv(digits[:10], _CPF_WEIGHTS_DV2)
    return dv2_calculado == int(digits[10])


# ============================================================
# Validacao de CNPJ
# ============================================================

#: Pesos para o 1o DV do CNPJ (12 digitos).
_CNPJ_WEIGHTS_DV1: list[int] = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

#: Pesos para o 2o DV do CNPJ (13 digitos).
_CNPJ_WEIGHTS_DV2: list[int] = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def is_valid_cnpj(value: str) -> bool:
    """
    Valida um CNPJ brasileiro.

    Aceita com ou sem mascara. Verifica:
    1. String nao vazia
    2. Tem 14 digitos apos remover mascara
    3. Nao esta na blacklist de CNPJs com todos digitos iguais
    4. Os 2 digitos verificadores conferem.

    Args:
        value: CNPJ a validar (com ou sem mascara).

    Returns:
        True se valido, False caso contrario.

    Exemplos:
        >>> is_valid_cnpj("11.222.333/0001-81")
        True
        >>> is_valid_cnpj("11222333000181")
        True
        >>> is_valid_cnpj("11.222.333/0001-80")  # DV errado
        False
        >>> is_valid_cnpj("00.000.000/0000-00")  # blacklist
        False
    """
    digits = _only_digits(value)

    if len(digits) != 14:  # noqa: PLR2004
        return False

    if len(set(digits)) == 1:
        return False

    dv1_calculado = _calculate_dv(digits[:12], _CNPJ_WEIGHTS_DV1)
    if dv1_calculado != int(digits[12]):
        return False

    dv2_calculado = _calculate_dv(digits[:13], _CNPJ_WEIGHTS_DV2)
    return dv2_calculado == int(digits[13])


__all__ = [
    "is_valid_cnpj",
    "is_valid_cpf",
]
