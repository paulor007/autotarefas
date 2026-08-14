"""
Testes da transferencia entre planilhas (RF-REC-003).

O criterio de aceite da ficha e curto e duro: **campo nao autorizado
jamais alterado** e **nao-encontrados listados com a chave buscada**. Os
testes abaixo existem principalmente para isso.
"""

from __future__ import annotations

import pandas as pd
import pytest

from autotarefas.reconcile.compare import compare_tables
from autotarefas.reconcile.errors import CompareError
from autotarefas.reconcile.result import TableSource
from autotarefas.reconcile.transfer import (
    ORIGIN_PREFIX,
    TransferPolicy,
    source_field_warnings,
    transfer_values,
)

COLUNAS = ["codigo", "nome", "email"]


def _tabela(nome: str, linhas: list[list[str]], colunas: list[str] | None = None) -> TableSource:
    return TableSource(name=nome, frame=pd.DataFrame(linhas, columns=colunas or COLUNAS, dtype=str))


def _transferir(
    destino: TableSource,
    fonte: TableSource,
    policy: TransferPolicy,
    normalizations: list[str] | None = None,
):
    comparacao = compare_tables(
        destino, fonte, key_columns=["codigo"], normalizations=normalizations or []
    )
    return transfer_values(destino, fonte, comparacao, policy)


@pytest.fixture
def par() -> tuple[TableSource, TableSource]:
    destino = _tabela(
        "destino.xlsx",
        [
            ["1", "Ana Lima", ""],
            ["2", "Bruno Sa", "bruno@antigo.com"],
            ["3", "Carla Nunes", "carla@x.com"],
            ["9", "Zeca", ""],
        ],
    )
    fonte = _tabela(
        "fonte.xlsx",
        [
            ["1", "Ana L.", "ana@empresa.com"],
            ["2", "Bruno S.", "bruno@empresa.com"],
            ["3", "Carla N.", "carla@x.com"],
            ["8", "Novo", "novo@empresa.com"],
        ],
    )
    return destino, fonte


class TestCamposAutorizados:
    def test_campo_vazio_e_preenchido(self, par: tuple[TableSource, TableSource]) -> None:
        destino, fonte = par
        resultado = _transferir(destino, fonte, TransferPolicy(fields=("email",)))

        linha = next(r for r in resultado.rows if r["codigo"] == "1")
        assert linha["email"] == "ana@empresa.com"
        acao = next(
            t for t in resultado.transfers if t.key == ("1",) and t.column == "email"
        ).action
        assert acao == "preenchido"

    def test_valor_diferente_e_atualizado(self, par: tuple[TableSource, TableSource]) -> None:
        destino, fonte = par
        resultado = _transferir(destino, fonte, TransferPolicy(fields=("email",)))

        linha = next(r for r in resultado.rows if r["codigo"] == "2")
        assert linha["email"] == "bruno@empresa.com"
        transferencia = next(
            t for t in resultado.transfers if t.key == ("2",) and t.column == "email"
        )
        assert (transferencia.action, transferencia.before) == ("atualizado", "bruno@antigo.com")

    def test_valor_igual_e_mantido(self, par: tuple[TableSource, TableSource]) -> None:
        destino, fonte = par
        resultado = _transferir(destino, fonte, TransferPolicy(fields=("email",)))
        acao = next(
            t for t in resultado.transfers if t.key == ("3",) and t.column == "email"
        ).action
        assert acao == "mantido"

    def test_campo_nao_autorizado_jamais_e_alterado(
        self, par: tuple[TableSource, TableSource]
    ) -> None:
        """Criterio de aceite da ficha: 'nome' difere nos dois lados e nao muda."""
        destino, fonte = par
        resultado = _transferir(destino, fonte, TransferPolicy(fields=("email",)))

        nomes = {r["codigo"]: r["nome"] for r in resultado.rows}
        assert nomes == {"1": "Ana Lima", "2": "Bruno Sa", "3": "Carla Nunes", "9": "Zeca"}
        assert all(t.column == "email" for t in resultado.transfers)

    def test_somente_vazios_nunca_sobrescreve(self, par: tuple[TableSource, TableSource]) -> None:
        destino, fonte = par
        resultado = _transferir(destino, fonte, TransferPolicy(fields=("email",), only_empty=True))

        linha = next(r for r in resultado.rows if r["codigo"] == "2")
        assert linha["email"] == "bruno@antigo.com"
        assert resultado.counts["preenchidos"] == 1
        assert resultado.counts["atualizados"] == 0

    def test_fonte_sem_valor_nao_apaga_o_destino(self) -> None:
        destino = _tabela("destino.xlsx", [["1", "Ana", "ana@x.com"]])
        fonte = _tabela("fonte.xlsx", [["1", "Ana", ""]])

        resultado = _transferir(destino, fonte, TransferPolicy(fields=("email",)))

        assert resultado.rows[0]["email"] == "ana@x.com"
        assert resultado.transfers[0].action == "sem_valor_na_fonte"


class TestNaoEncontrados:
    def test_registro_sem_correspondente_e_listado_com_a_chave(
        self, par: tuple[TableSource, TableSource]
    ) -> None:
        destino, fonte = par
        resultado = _transferir(destino, fonte, TransferPolicy(fields=("email",)))

        (nao_encontrado,) = resultado.not_found
        assert nao_encontrado.key == ("9",)
        assert nao_encontrado.row == 5

    def test_registro_sem_correspondente_continua_na_saida(
        self, par: tuple[TableSource, TableSource]
    ) -> None:
        """Nada some do destino: o registro sai como entrou."""
        destino, fonte = par
        resultado = _transferir(destino, fonte, TransferPolicy(fields=("email",)))

        linha = next(r for r in resultado.rows if r["codigo"] == "9")
        assert linha["email"] == ""
        assert len(resultado.rows) == 4

    def test_registro_so_na_fonte_e_reportado(self, par: tuple[TableSource, TableSource]) -> None:
        destino, fonte = par
        resultado = _transferir(destino, fonte, TransferPolicy(fields=("email",)))

        assert resultado.unmatched_source == (("8",),)
        assert all(r["codigo"] != "8" for r in resultado.rows)

    def test_chave_duplicada_nao_e_pareada(self) -> None:
        destino = _tabela("destino.xlsx", [["1", "Ana", ""], ["1", "Ana II", ""]])
        fonte = _tabela("fonte.xlsx", [["1", "Ana", "ana@x.com"]])

        resultado = _transferir(destino, fonte, TransferPolicy(fields=("email",)))
        assert resultado.rows == ()
        assert resultado.comparison.conflicts


class TestOrigemEAvisos:
    def test_marcar_origem_cria_a_coluna(self, par: tuple[TableSource, TableSource]) -> None:
        destino, fonte = par
        resultado = _transferir(destino, fonte, TransferPolicy(fields=("email",), mark_origin=True))

        assert f"{ORIGIN_PREFIX}email" in resultado.columns
        linha = next(r for r in resultado.rows if r["codigo"] == "1")
        assert linha[f"{ORIGIN_PREFIX}email"] == "fonte.xlsx"

    def test_origem_fica_vazia_quando_nada_mudou(
        self, par: tuple[TableSource, TableSource]
    ) -> None:
        destino, fonte = par
        resultado = _transferir(destino, fonte, TransferPolicy(fields=("email",), mark_origin=True))
        linha = next(r for r in resultado.rows if r["codigo"] == "3")
        assert linha[f"{ORIGIN_PREFIX}email"] == ""

    def test_campo_ausente_na_fonte_vira_aviso(self) -> None:
        destino = _tabela("destino.xlsx", [["1", "Ana", ""]])
        fonte = _tabela("fonte.xlsx", [["1", "Ana"]], ["codigo", "nome"])

        policy = TransferPolicy(fields=("email",))
        resultado = _transferir(destino, fonte, policy)

        assert resultado.transfers == ()
        assert "nao existe na fonte" in source_field_warnings(fonte, policy)[0]

    def test_normalizacao_da_chave_permite_parear(self) -> None:
        destino = _tabela("destino.xlsx", [["529.982.247-25", "Ana", ""]])
        fonte = _tabela("fonte.xlsx", [["52998224725", "Ana", "ana@x.com"]])

        resultado = _transferir(
            destino, fonte, TransferPolicy(fields=("email",)), normalizations=["digitos"]
        )
        assert resultado.rows[0]["email"] == "ana@x.com"


class TestErrosDeUso:
    def test_sem_campo_autorizado(self, par: tuple[TableSource, TableSource]) -> None:
        destino, fonte = par
        with pytest.raises(CompareError, match="ao menos um campo"):
            _transferir(destino, fonte, TransferPolicy())

    def test_campo_inexistente_no_destino(self, par: tuple[TableSource, TableSource]) -> None:
        destino, fonte = par
        with pytest.raises(CompareError, match="inexistente"):
            _transferir(destino, fonte, TransferPolicy(fields=("fantasma",)))


def test_destino_original_nao_e_alterado(par: tuple[TableSource, TableSource]) -> None:
    destino, fonte = par
    antes = destino.frame.copy()

    _transferir(destino, fonte, TransferPolicy(fields=("email",), mark_origin=True))

    pd.testing.assert_frame_equal(destino.frame, antes)
