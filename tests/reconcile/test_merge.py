"""
Testes das regras de decisao da reconciliacao (RF-REC-002).

A regra que estes testes protegem e a mais importante do modulo: **nada
fora da regra declarada e resolvido automaticamente**. Campo nao
autorizado mantem o valor da fonte principal e vai para revisao; chave sem
pareamento confiavel nunca entra na base conciliada.
"""

from __future__ import annotations

import pandas as pd
import pytest

from autotarefas.reconcile.compare import compare_tables
from autotarefas.reconcile.merge import ReconcilePolicy, reconcile_tables
from autotarefas.reconcile.result import TableSource
from autotarefas.reconcile.tolerance import Tolerance

COLUNAS = ["codigo", "nome", "valor"]


def _tabela(nome: str, linhas: list[list[str]], colunas: list[str] | None = None) -> TableSource:
    return TableSource(name=nome, frame=pd.DataFrame(linhas, columns=colunas or COLUNAS, dtype=str))


def _conciliar(
    a: TableSource,
    b: TableSource,
    policy: ReconcilePolicy | None = None,
    tolerances: list[Tolerance] | None = None,
):
    comparacao = compare_tables(a, b, key_columns=["codigo"], tolerances=tolerances or [])
    return reconcile_tables(a, b, comparacao, policy or ReconcilePolicy())


@pytest.fixture
def par() -> tuple[TableSource, TableSource]:
    a = _tabela(
        "a.xlsx",
        [
            ["1", "Ana", "10,00"],
            ["2", "Bruno", "20,00"],
            ["3", "Carla", "30,00"],
        ],
    )
    b = _tabela(
        "b.xlsx",
        [
            ["1", "Ana", "10,00"],
            ["2", "Bruno Silva", "25,00"],
            ["4", "Diego", "40,00"],
        ],
    )
    return a, b


class TestCampoAutorizado:
    def test_campo_autorizado_e_atualizado_pela_complementar(
        self, par: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par
        resultado = _conciliar(a, b, ReconcilePolicy(updatable_columns=("valor",)))

        registro = next(r for r in resultado.records if r.key == ("2",))
        assert registro.values["valor"] == "25,00"
        decisao = next(d for d in registro.decisions if d.column == "valor")
        assert (decisao.rule, decisao.source, decisao.other_value) == (
            "campo_autorizado",
            "b",
            "20,00",
        )

    def test_campo_nao_autorizado_preserva_a_principal(
        self, par: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par
        resultado = _conciliar(a, b, ReconcilePolicy(updatable_columns=("valor",)))

        registro = next(r for r in resultado.records if r.key == ("2",))
        assert registro.values["nome"] == "Bruno"
        decisao = next(d for d in registro.decisions if d.column == "nome")
        assert decisao.rule == "fonte_principal"

    def test_campo_nao_autorizado_vai_para_revisao(
        self, par: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par
        resultado = _conciliar(a, b, ReconcilePolicy(updatable_columns=("valor",)))

        (item,) = [i for i in resultado.review if i.reason == "divergencia_nao_autorizada"]
        assert (item.key, item.column) == (("2",), "nome")
        assert (item.value_a, item.value_b) == ("Bruno", "Bruno Silva")

    def test_sem_autorizacao_nenhum_campo_muda(self, par: tuple[TableSource, TableSource]) -> None:
        a, b = par
        resultado = _conciliar(a, b)

        registro = next(r for r in resultado.records if r.key == ("2",))
        assert registro.values == {"codigo": "2", "nome": "Bruno", "valor": "20,00"}
        assert len(resultado.review) == 2  # nome e valor


class TestFontePrincipal:
    def test_fonte_b_como_principal_inverte_a_base(
        self, par: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par
        resultado = _conciliar(a, b, ReconcilePolicy(primary="b", updatable_columns=("valor",)))

        registro = next(r for r in resultado.records if r.key == ("2",))
        assert registro.values["nome"] == "Bruno Silva"  # B manda
        assert registro.values["valor"] == "20,00"  # A pode atualizar o campo autorizado

    def test_registro_exclusivo_da_principal_entra(
        self, par: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par
        resultado = _conciliar(a, b)
        registro = next(r for r in resultado.records if r.key == ("3",))
        assert registro.origin == "a"

    def test_registro_novo_da_complementar_entra_por_padrao(
        self, par: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par
        resultado = _conciliar(a, b)
        registro = next(r for r in resultado.records if r.key == ("4",))
        assert registro.origin == "b"
        assert registro.decisions[0].rule == "registro_exclusivo"

    def test_registro_novo_pode_ir_para_revisao(self, par: tuple[TableSource, TableSource]) -> None:
        a, b = par
        resultado = _conciliar(a, b, ReconcilePolicy(include_new=False))

        assert all(r.key != ("4",) for r in resultado.records)
        assert any(i.reason == "registro_novo_nao_incluido" for i in resultado.review)


class TestConflitosETolerancia:
    def test_chave_duplicada_nunca_entra_na_base(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana", "10,00"], ["1", "Ana II", "11,00"]])
        b = _tabela("b.xlsx", [["1", "Ana", "10,00"]])

        resultado = _conciliar(a, b)

        assert resultado.records == ()
        assert [i.reason for i in resultado.review] == ["chave_duplicada"]

    def test_diferenca_tolerada_nao_vai_para_revisao_mas_e_registrada(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana", "1.000,00"]])
        b = _tabela("b.xlsx", [["1", "Ana", "1.000,01"]])

        resultado = _conciliar(a, b, tolerances=[Tolerance("valor", "absoluta", 0.01)])

        assert resultado.review == ()
        (registro,) = resultado.records
        assert registro.values["valor"] == "1.000,00"  # a principal manda
        decisao = next(d for d in registro.decisions if d.rule == "tolerancia")
        assert (decisao.value, decisao.other_value) == ("1.000,00", "1.000,01")

    def test_contadores(self, par: tuple[TableSource, TableSource]) -> None:
        a, b = par
        resultado = _conciliar(a, b, ReconcilePolicy(updatable_columns=("valor",)))

        assert resultado.counts == {
            "conciliados": 4,
            "registros_atualizados": 1,
            "campos_atualizados": 1,
            "para_revisao": 1,
            "toleradas": 0,
        }


class TestColunasEFontes:
    def test_base_usa_as_colunas_da_fonte_principal(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana", "10,00"]])
        b = _tabela("b.xlsx", [["1", "Ana", "10,00", "extra"]], [*COLUNAS, "so_em_b"])

        resultado = _conciliar(a, b)
        assert resultado.columns == tuple(COLUNAS)
        assert "so_em_b" not in resultado.records[0].values

    def test_coluna_ausente_na_complementar_vira_vazio(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana", "10,00"]])
        b = _tabela("b.xlsx", [["9", "Nova"]], ["codigo", "nome"])

        resultado = _conciliar(a, b)
        novo = next(r for r in resultado.records if r.key == ("9",))
        assert novo.values["valor"] == ""

    def test_fontes_nao_sao_alteradas(self, par: tuple[TableSource, TableSource]) -> None:
        a, b = par
        antes_a, antes_b = a.frame.copy(), b.frame.copy()

        _conciliar(a, b, ReconcilePolicy(updatable_columns=("valor", "nome")))

        pd.testing.assert_frame_equal(a.frame, antes_a)
        pd.testing.assert_frame_equal(b.frame, antes_b)

    def test_politica_descreve_a_si_mesma(self) -> None:
        descricao = ReconcilePolicy(primary="b", updatable_columns=("valor",)).describe()
        assert "fonte principal: B" in descricao
        assert "valor" in descricao
