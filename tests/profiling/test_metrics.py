"""Testes das metricas puras (funcoes sem estado, sem dominio)."""

from __future__ import annotations

import pandas as pd
import pytest

from autotarefas.profiling.metrics import (
    RANGE_TYPES,
    distinct_stats,
    duplicate_row_count,
    excel_error_stats,
    fill_stats,
    top_repeated,
    value_range,
    whitespace_issues,
)


class TestFillStats:
    def test_tudo_preenchido(self) -> None:
        assert fill_stats(["a", "b", "c"]) == (3, 0, 1.0)

    def test_com_vazios(self) -> None:
        preenchidos, vazios, taxa = fill_stats(["a", "", "c", "   "])
        assert (preenchidos, vazios) == (2, 2)
        assert taxa == 0.5

    def test_coluna_vazia(self) -> None:
        assert fill_stats(["", "", ""]) == (0, 3, 0.0)

    def test_lista_vazia(self) -> None:
        assert fill_stats([]) == (0, 0, 0.0)


class TestDistinctStats:
    def test_todos_distintos(self) -> None:
        distintos, unicidade, duplicados = distinct_stats(["a", "b", "c"])
        assert distintos == 3
        assert unicidade == 1.0
        assert duplicados == 0

    def test_valores_repetidos_sao_estatistica_nao_erro(self) -> None:
        distintos, unicidade, duplicados = distinct_stats(["x", "x", "x", "y"])
        assert distintos == 2
        assert unicidade == 0.5
        assert duplicados == 2  # 2 celulas EXCEDENTES

    def test_ignora_vazios(self) -> None:
        distintos, _, _ = distinct_stats(["a", "", "a"])
        assert distintos == 1


class TestWhitespaceIssues:
    def test_espacos_nas_pontas(self) -> None:
        n, amostras = whitespace_issues(["  Camisa", "Calca  ", "Meia"])
        assert n == 2
        assert amostras

    def test_espacos_internos_excessivos(self) -> None:
        n, _ = whitespace_issues(["Meia   Longa", "Camisa Listrada"])
        assert n == 1  # so a com 3 espacos internos

    def test_texto_limpo(self) -> None:
        n, amostras = whitespace_issues(["Camisa", "Calca"])
        assert n == 0
        assert amostras == []


class TestExcelErrors:
    def test_detecta_erros(self) -> None:
        n, amostras = excel_error_stats(["#DIV/0!", "10", "#REF!"])
        assert n == 2
        assert "#DIV/0!" in amostras

    def test_sem_erros(self) -> None:
        assert excel_error_stats(["10", "20"]) == (0, [])


class TestValueRange:
    @pytest.mark.parametrize("tipo", ["inteiro", "decimal", "moeda", "percentual"])
    def test_numeros_tem_intervalo(self, tipo: str) -> None:
        minimo, maximo = value_range(pd.Series([10.0, 5.0, 30.0]), tipo)  # type: ignore[arg-type]
        assert (minimo, maximo) == ("5", "30")

    def test_datas_tem_intervalo(self) -> None:
        serie = pd.to_datetime(pd.Series(["2019-12-01", "2019-12-31"]))
        minimo, maximo = value_range(serie, "data")
        assert (minimo, maximo) == ("2019-12-01", "2019-12-31")

    @pytest.mark.parametrize("tipo", ["identificador", "texto", "booleano", "misto", "erro"])
    def test_tipos_sem_ordenacao_NAO_tem_intervalo(self, tipo: str) -> None:
        """'O menor CPF da base' nao e uma metrica."""
        assert value_range(pd.Series(["00123", "00456"]), tipo) == (None, None)  # type: ignore[arg-type]

    def test_serie_vazia(self) -> None:
        assert value_range(pd.Series([], dtype=float), "inteiro") == (None, None)

    def test_identificador_nao_esta_nos_tipos_com_intervalo(self) -> None:
        assert "identificador" not in RANGE_TYPES
        assert "texto" not in RANGE_TYPES


class TestDuplicateRows:
    def test_linha_identica(self) -> None:
        df = pd.DataFrame({"a": ["1", "2", "1"], "b": ["x", "y", "x"]})
        duplicadas, _, _ = duplicate_row_count(df)
        assert duplicadas == 1  # 1 EXCEDENTE

    def test_valor_repetido_em_coluna_NAO_e_linha_duplicada(self) -> None:
        df = pd.DataFrame({"codigo": ["1", "1"], "item": ["A", "B"]})
        duplicadas, _, _ = duplicate_row_count(df)
        assert duplicadas == 0

    def test_dataframe_vazio(self) -> None:
        assert duplicate_row_count(pd.DataFrame()) == (0, [], 0)


class TestTopRepeated:
    def test_lista_os_mais_comuns(self) -> None:
        top = top_repeated(["a", "a", "a", "b", "b", "c"])
        assert top[0].startswith("a (3x)")
        assert "c" not in " ".join(top)  # aparece 1x: nao e repetido

    def test_sem_repeticao(self) -> None:
        assert top_repeated(["a", "b"]) == []
