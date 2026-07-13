"""Testes da normalizacao segura e da trilha de conversoes."""

from __future__ import annotations

from datetime import datetime

import pytest

from autotarefas.reader.normalize import (
    normalize_column,
    parse_bool,
    parse_date,
    parse_number,
)
from autotarefas.reader.types import RawCell


class TestParseNumber:
    @pytest.mark.parametrize(
        ("texto", "sep", "esperado"),
        [
            ("R$ 1.234,56", ",", 1234.56),
            ("89,90", ",", 89.90),
            ("$1,234.56", ".", 1234.56),
            ("1.234", "", 1234.0),  # sem decimal na coluna -> ponto e milhar
            ("-45,5", ",", -45.5),
            ("12%", ",", 12.0),
            ("nao é numero", ",", None),
            ("", ",", None),
        ],
    )
    def test_conversao(self, texto: str, sep: str, esperado: float | None) -> None:
        assert parse_number(texto, sep) == esperado


class TestParseDate:
    def test_datetime_nativo(self) -> None:
        d = datetime(2019, 12, 1)
        assert parse_date(d) == d

    def test_serial_do_excel(self) -> None:
        assert parse_date(43800) == datetime(2019, 12, 1)

    def test_texto_ddmmaaaa(self) -> None:
        assert parse_date("01/12/2019") == datetime(2019, 12, 1)

    def test_texto_iso(self) -> None:
        assert parse_date("2019-12-01") == datetime(2019, 12, 1)

    def test_texto_com_hora(self) -> None:
        assert parse_date("01/12/2019 14:30") == datetime(2019, 12, 1, 14, 30)

    def test_texto_invalido(self) -> None:
        assert parse_date("amanha") is None


class TestParseBool:
    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [("sim", True), ("SIM", True), ("verdadeiro", True), ("nao", False), ("false", False)],
    )
    def test_conversao(self, texto: str, esperado: bool) -> None:
        assert parse_bool(texto) is esperado

    def test_invalido(self) -> None:
        assert parse_bool("talvez") is None


class TestNormalizeColumn:
    def test_moeda_br_gera_trilha(self) -> None:
        cells = [RawCell(value="R$ 1.234,56"), RawCell(value="R$ 89,90")]
        valores, conversoes = normalize_column(cells, "moeda", "preco", first_data_row=2)

        assert valores == [1234.56, 89.90]
        assert len(conversoes) == 2
        assert conversoes[0].row == 2  # linha FISICA da planilha
        assert conversoes[0].column == "preco"
        assert conversoes[0].original == "R$ 1.234,56"
        assert conversoes[0].normalized == "1234.56"
        assert conversoes[0].rule == "moeda_br"

    def test_numero_que_ja_era_numero_NAO_gera_conversao(self) -> None:
        cells = [RawCell(value=114, excel_type="n"), RawCell(value=269, excel_type="n")]
        valores, conversoes = normalize_column(cells, "moeda", "valor", first_data_row=2)
        assert valores == [114, 269]
        assert conversoes == []  # nada mudou -> nada a registrar

    def test_identificador_e_preservado_intacto(self) -> None:
        cells = [RawCell(value="00123"), RawCell(value="00456")]
        valores, conversoes = normalize_column(cells, "identificador", "codigo", first_data_row=2)
        assert valores == ["00123", "00456"]
        assert conversoes == []

    def test_coluna_mista_nao_e_convertida(self) -> None:
        cells = [RawCell(value="2"), RawCell(value="uma duzia")]
        valores, conversoes = normalize_column(cells, "misto", "qtd", first_data_row=2)
        assert valores == ["2", "uma duzia"]
        assert conversoes == []

    def test_celula_vazia_vira_None_sem_inventar(self) -> None:
        cells = [RawCell(value="10"), RawCell(value=None), RawCell(value="30")]
        valores, _ = normalize_column(cells, "inteiro", "qtd", first_data_row=2)
        assert valores == [10.0, None, 30.0]  # o vazio NAO foi preenchido

    def test_linha_fisica_e_correta_com_cabecalho_na_linha_4(self) -> None:
        cells = [RawCell(value="R$ 10,00")]
        _, conversoes = normalize_column(cells, "moeda", "v", first_data_row=5)
        assert conversoes[0].row == 5
