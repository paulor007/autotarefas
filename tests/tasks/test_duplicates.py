"""Testes para autotarefas.tasks.duplicates."""

from __future__ import annotations

from autotarefas.tasks.duplicates import (
    find_duplicate_rows,
    find_duplicate_values,
    normalize_digits,
    normalize_text,
)


class TestNormalizers:
    def test_normalize_text(self) -> None:
        assert normalize_text("  Ana Lima ") == "ana lima"
        assert normalize_text("ANA@X.COM") == "ana@x.com"

    def test_normalize_digits(self) -> None:
        assert normalize_digits("111.444.777-35") == "11144477735"
        assert normalize_digits("(11) 99999-0000") == "11999990000"
        assert normalize_digits("sem digito") == ""


class TestFindDuplicateValues:
    def test_sem_duplicatas(self) -> None:
        assert find_duplicate_values(["a", "b", "c"]) == {}

    def test_duplicata_simples(self) -> None:
        assert find_duplicate_values(["a", "b", "a"]) == {"a": [0, 2]}

    def test_ignora_caixa_e_espaco(self) -> None:
        assert find_duplicate_values(["Ana", " ana ", "BOB"]) == {"ana": [0, 1]}

    def test_cpf_por_digitos(self) -> None:
        # mesmo CPF, um com mascara e outro sem
        values = ["111.444.777-35", "999.999.999-99", "11144477735"]
        assert find_duplicate_values(values, key=normalize_digits) == {"11144477735": [0, 2]}

    def test_vazios_ignorados_por_padrao(self) -> None:
        assert find_duplicate_values(["", "  ", "a", "a"]) == {"a": [2, 3]}

    def test_vazios_contam_se_skip_false(self) -> None:
        result = find_duplicate_values(["", "  "], key=lambda v: v.strip(), skip_empty=False)
        assert result == {"": [0, 1]}


class TestFindDuplicateRows:
    def test_sem_duplicatas(self) -> None:
        assert find_duplicate_rows([("a", "1"), ("b", "2")]) == []

    def test_linha_identica_ignora_caixa(self) -> None:
        rows = [("Ana", "1"), ("Bob", "2"), ("ana", "1")]
        assert find_duplicate_rows(rows) == [[0, 2]]

    def test_tres_iguais(self) -> None:
        rows = [("x", "y"), ("x", "y"), ("x", "y")]
        assert find_duplicate_rows(rows) == [[0, 1, 2]]

    def test_linhas_vazias_ignoradas(self) -> None:
        rows = [("", ""), ("", ""), ("a", "b")]
        assert find_duplicate_rows(rows) == []
