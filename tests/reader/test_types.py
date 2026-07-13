"""Testes da inferencia de tipos (agnostica de dominio)."""

from __future__ import annotations

from datetime import datetime

import pytest

from autotarefas.reader.types import (
    RawCell,
    classify_cell,
    classify_text,
    detect_decimal_separator,
    infer_column_type,
    looks_like_identifier,
)


def _texto(*valores: str) -> list[RawCell]:
    return [RawCell(value=v) for v in valores]


def _numeros(*valores: float) -> list[RawCell]:
    return [RawCell(value=v, excel_type="n") for v in valores]


class TestClassifyText:
    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [
            ("", "vazio"),
            ("#DIV/0!", "erro"),
            ("#REF!", "erro"),
            ("#N/D", "erro"),
            ("sim", "booleano"),
            ("false", "booleano"),
            ("01/12/2019", "data"),
            ("2019-12-01", "data"),
            ("01/12/2019 14:30", "data_hora"),
            ("12%", "percentual"),
            ("R$ 1.234,56", "moeda"),
            ("$1,234.56", "moeda"),
            ("42", "inteiro"),
            ("3,14", "decimal"),
            ("Camisa Listrada", "texto"),
        ],
    )
    def test_classificacao(self, valor: str, esperado: str) -> None:
        assert classify_text(valor) == esperado


class TestClassifyCell:
    def test_excel_afirma_moeda_pelo_formato(self) -> None:
        cell = RawCell(value=114, excel_type="n", number_format='"R$" #,##0.00')
        assert classify_cell(cell) == "moeda"

    def test_excel_afirma_percentual(self) -> None:
        assert classify_cell(RawCell(value=0.12, excel_type="n", number_format="0.00%")) == (
            "percentual"
        )

    def test_data_nativa(self) -> None:
        assert classify_cell(RawCell(value=datetime(2019, 12, 1), excel_type="d")) == "data"

    def test_data_hora_nativa(self) -> None:
        cell = RawCell(value=datetime(2019, 12, 1, 14, 30), excel_type="d")
        assert classify_cell(cell) == "data_hora"

    def test_erro_do_excel(self) -> None:
        assert classify_cell(RawCell(value="#DIV/0!", excel_type="e")) == "erro"


class TestIdentificador:
    def test_zero_a_esquerda(self) -> None:
        e_id, motivo = looks_like_identifier(["00123", "00456"])
        assert e_id is True
        assert "zero" in motivo

    def test_mascara_de_digitos(self) -> None:
        e_id, _ = looks_like_identifier(["529.982.247-25", "168.995.350-09"])
        assert e_id is True

    def test_comprimento_fixo_com_alta_cardinalidade(self) -> None:
        e_id, _ = looks_like_identifier(["65014", "65016", "65018", "65019"])
        assert e_id is True

    def test_numero_do_excel_NAO_e_identificador(self) -> None:
        """Se o Excel guardou como numero, e numero (evita o falso positivo de ANOS)."""
        e_id, _ = looks_like_identifier(["2019", "2020", "2021"], from_numbers=True)
        assert e_id is False

    def test_texto_comum_nao_e_identificador(self) -> None:
        e_id, _ = looks_like_identifier(["Camisa", "Calca"])
        assert e_id is False


class TestSeparadorDecimal:
    def test_virgula_decimal_br(self) -> None:
        assert detect_decimal_separator(["1.234,56", "89,90"]) == ","

    def test_ponto_decimal_us(self) -> None:
        assert detect_decimal_separator(["1,234.56", "89.90"]) == "."

    def test_apenas_milhar_sem_decimal(self) -> None:
        # "1.234" isolado e ambiguo -> sem sinal de decimal, o separador e milhar
        assert detect_decimal_separator(["1.234", "5.678"]) == ""

    def test_virgula_com_2_casas_e_decimal(self) -> None:
        assert detect_decimal_separator(["10,25", "3,50"]) == ","


class TestInferColumnType:
    def test_coluna_vazia(self) -> None:
        tipo, _, obs = infer_column_type([RawCell(value=None), RawCell(value="")])
        assert tipo == "vazio"
        assert "vazia" in obs[0]

    def test_moeda_texto(self) -> None:
        tipo, _, _ = infer_column_type(_texto("R$ 1.234,56", "R$ 89,90"))
        assert tipo == "moeda"

    def test_inteiro_e_decimal_juntos_viram_decimal(self) -> None:
        # numeros na mesma coluna nao sao "misto"
        tipo, _, _ = infer_column_type(_numeros(1, 2.5, 3))
        assert tipo == "decimal"

    def test_tipos_realmente_misturados(self) -> None:
        tipo, _, obs = infer_column_type(_texto("2", "uma duzia", "3"))
        assert tipo == "misto"
        assert "misturados" in obs[0]

    def test_identificador_preservado(self) -> None:
        tipo, _, _ = infer_column_type(_texto("00123", "00456"))
        assert tipo == "identificador"

    def test_numero_alta_cardinalidade_apenas_OBSERVA(self) -> None:
        """A decisao aprovada: o leitor observa, NAO conclui."""
        tipo, _, obs = infer_column_type(_numeros(65014, 65016, 65018, 65019))
        assert tipo == "inteiro"
        assert any("possivel identificador" in o for o in obs)
