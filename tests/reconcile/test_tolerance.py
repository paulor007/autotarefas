"""
Testes das tolerancias declaradas (RF-REC-002).

Criterio de aceite da ficha: "tolerancia de R$ 0,01 nao gera divergencia".
E o complemento indispensavel: o que a tolerancia NAO cobre continua sendo
divergencia, e toda diferenca tolerada fica registrada.
"""

from __future__ import annotations

import pandas as pd
import pytest

from autotarefas.reconcile.compare import compare_tables
from autotarefas.reconcile.errors import CompareError
from autotarefas.reconcile.result import TableSource
from autotarefas.reconcile.tolerance import (
    Tolerance,
    parse_tolerance,
    parse_tolerances,
    within_tolerance,
)

COLUNAS = ["codigo", "valor", "vencimento"]


def _tabela(nome: str, linhas: list[list[str]]) -> TableSource:
    return TableSource(name=nome, frame=pd.DataFrame(linhas, columns=COLUNAS, dtype=str))


class TestLeituraDaTolerancia:
    def test_absoluta(self) -> None:
        tolerancia = parse_tolerance("valor=0,01")
        assert tolerancia.column == "valor"
        assert tolerancia.kind == "absoluta"
        assert tolerancia.amount == 0.01

    def test_percentual(self) -> None:
        assert parse_tolerance("valor=1%").kind == "percentual"

    def test_dias(self) -> None:
        tolerancia = parse_tolerance("vencimento=2d")
        assert (tolerancia.kind, tolerancia.amount) == ("dias", 2.0)

    def test_espacos_e_maiusculas_no_sufixo(self) -> None:
        assert parse_tolerance(" vencimento = 3D ").kind == "dias"

    @pytest.mark.parametrize("spec", ["valor", "valor=", "=0,01", "valor=abc", "valor=-1"])
    def test_sintaxe_invalida(self, spec: str) -> None:
        with pytest.raises(CompareError, match="tolerancia invalida"):
            parse_tolerance(spec)

    def test_ultima_declaracao_para_a_coluna_vence(self) -> None:
        lidas = parse_tolerances(["valor=0,01", "valor=5%"])
        assert len(lidas) == 1
        assert lidas[0].kind == "percentual"

    def test_descricao_legivel(self) -> None:
        assert "valor: ate 0.01" in parse_tolerance("valor=0,01").describe()


class TestAplicacaoDaTolerancia:
    def test_centavo_de_arredondamento_cabe(self) -> None:
        tolerancia = Tolerance("valor", "absoluta", 0.01)
        assert within_tolerance(tolerancia, "1.000,00", "1.000,01") is True

    def test_diferenca_maior_nao_cabe(self) -> None:
        tolerancia = Tolerance("valor", "absoluta", 0.01)
        assert within_tolerance(tolerancia, "1.000,00", "1.000,05") is False

    def test_percentual_usa_o_maior_valor_como_base(self) -> None:
        tolerancia = Tolerance("valor", "percentual", 1.0)
        assert within_tolerance(tolerancia, "100,00", "100,90") is True
        assert within_tolerance(tolerancia, "100,90", "100,00") is True
        assert within_tolerance(tolerancia, "100,00", "102,00") is False

    def test_dias(self) -> None:
        tolerancia = Tolerance("vencimento", "dias", 2)
        assert within_tolerance(tolerancia, "01/03/2026", "03/03/2026") is True
        assert within_tolerance(tolerancia, "01/03/2026", "05/03/2026") is False

    def test_texto_nao_numerico_nunca_e_tolerado(self) -> None:
        tolerancia = Tolerance("valor", "absoluta", 1000)
        assert within_tolerance(tolerancia, "Ana", "Bruno") is False

    def test_ausencia_nao_e_arredondamento(self) -> None:
        tolerancia = Tolerance("valor", "absoluta", 1000)
        assert within_tolerance(tolerancia, "", "10,00") is False

    def test_moeda_com_simbolo(self) -> None:
        tolerancia = Tolerance("valor", "absoluta", 0.01)
        assert within_tolerance(tolerancia, "R$ 10,00", "R$ 10,01") is True


class TestToleranciaNaComparacao:
    def test_um_centavo_nao_gera_divergencia(self) -> None:
        a = _tabela("a.xlsx", [["1", "1.000,00", "01/03/2026"]])
        b = _tabela("b.xlsx", [["1", "1.000,01", "01/03/2026"]])

        resultado = compare_tables(
            a, b, key_columns=["codigo"], tolerances=[Tolerance("valor", "absoluta", 0.01)]
        )

        assert resultado.counts["divergente"] == 0
        assert resultado.counts["identico"] == 1

    def test_diferenca_tolerada_fica_registrada(self) -> None:
        a = _tabela("a.xlsx", [["1", "1.000,00", "01/03/2026"]])
        b = _tabela("b.xlsx", [["1", "1.000,01", "01/03/2026"]])

        resultado = compare_tables(
            a, b, key_columns=["codigo"], tolerances=[Tolerance("valor", "absoluta", 0.01)]
        )

        (registro,) = resultado.records
        assert [(d.column, d.value_a, d.value_b) for d in registro.tolerated] == [
            ("valor", "1.000,00", "1.000,01")
        ]
        assert resultado.tolerated_count == 1

    def test_diferenca_alem_da_tolerancia_continua_divergindo(self) -> None:
        a = _tabela("a.xlsx", [["1", "1.000,00", "01/03/2026"]])
        b = _tabela("b.xlsx", [["1", "1.050,00", "01/03/2026"]])

        resultado = compare_tables(
            a, b, key_columns=["codigo"], tolerances=[Tolerance("valor", "absoluta", 0.01)]
        )
        assert resultado.counts["divergente"] == 1

    def test_tolerancia_de_data(self) -> None:
        a = _tabela("a.xlsx", [["1", "10,00", "01/03/2026"]])
        b = _tabela("b.xlsx", [["1", "10,00", "02/03/2026"]])

        resultado = compare_tables(
            a, b, key_columns=["codigo"], tolerances=[Tolerance("vencimento", "dias", 2)]
        )
        assert resultado.counts["identico"] == 1

    def test_tolerancia_so_vale_para_a_coluna_declarada(self) -> None:
        a = _tabela("a.xlsx", [["1", "10,00", "01/03/2026"]])
        b = _tabela("b.xlsx", [["1", "10,01", "05/03/2026"]])

        resultado = compare_tables(
            a, b, key_columns=["codigo"], tolerances=[Tolerance("valor", "absoluta", 0.01)]
        )
        (registro,) = resultado.records
        assert [d.column for d in registro.differences] == ["vencimento"]

    def test_tolerancia_em_coluna_inexistente_vira_aviso(self) -> None:
        a = _tabela("a.xlsx", [["1", "10,00", "01/03/2026"]])
        b = _tabela("b.xlsx", [["1", "10,00", "01/03/2026"]])

        resultado = compare_tables(
            a, b, key_columns=["codigo"], tolerances=[Tolerance("fantasma", "absoluta", 1)]
        )
        assert any(w.code == "tolerancia_sem_coluna" for w in resultado.warnings)

    def test_tolerancias_aparecem_no_resultado(self) -> None:
        a = _tabela("a.xlsx", [["1", "10,00", "01/03/2026"]])
        b = _tabela("b.xlsx", [["1", "10,00", "01/03/2026"]])

        resultado = compare_tables(
            a, b, key_columns=["codigo"], tolerances=[Tolerance("valor", "absoluta", 0.01)]
        )
        assert resultado.tolerances == ("valor: ate 0.01 (absoluta)",)
