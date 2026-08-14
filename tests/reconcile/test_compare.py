"""
Testes do nucleo puro da comparacao (RF-REC-001).

Cada teste planta UM caso e cobra a classificacao exata. O criterio de
aceite da ficha e "100% correto nas fixtures plantadas" — entao aqui nao
existe assert de "mais ou menos": ou a categoria e a esperada, ou falhou.
"""

from __future__ import annotations

import pandas as pd
import pytest

from autotarefas.reconcile.compare import (
    NORMALIZATION_OPTIONS,
    CompareError,
    compare_tables,
    normalize_for_comparison,
)
from autotarefas.reconcile.result import TableSource

COLUNAS = ["codigo", "nome", "valor"]


def _tabela(
    nome: str,
    linhas: list[list[str]],
    colunas: list[str] | None = None,
    first_data_row: int = 2,
) -> TableSource:
    frame = pd.DataFrame(linhas, columns=colunas or COLUNAS, dtype=str)
    return TableSource(name=nome, frame=frame, first_data_row=first_data_row)


@pytest.fixture
def par_basico() -> tuple[TableSource, TableSource]:
    """A e B com um caso de cada categoria."""
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
            ["2", "Bruno", "25,00"],
            ["4", "Diego", "40,00"],
        ],
    )
    return a, b


class TestClassificacao:
    def test_quatro_categorias(self, par_basico: tuple[TableSource, TableSource]) -> None:
        a, b = par_basico
        resultado = compare_tables(a, b, key_columns=["codigo"])

        assert resultado.counts == {
            "identico": 1,
            "divergente": 1,
            "somente_a": 1,
            "somente_b": 1,
            "conflitos": 0,
        }

    def test_divergencia_aponta_coluna_e_valores_originais(
        self, par_basico: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par_basico
        resultado = compare_tables(a, b, key_columns=["codigo"])

        (divergente,) = resultado.by_category("divergente")
        assert divergente.key == ("2",)
        assert [(d.column, d.value_a, d.value_b) for d in divergente.differences] == [
            ("valor", "20,00", "25,00")
        ]

    def test_linhas_fisicas_seguem_o_cabecalho(self) -> None:
        """Com o cabecalho na linha 4, o primeiro registro e a linha 5."""
        a = _tabela("a.xlsx", [["1", "Ana", "10,00"]], first_data_row=5)
        b = _tabela("b.xlsx", [["1", "Ana", "11,00"]], first_data_row=2)

        (registro,) = compare_tables(a, b, key_columns=["codigo"]).records
        assert (registro.row_a, registro.row_b) == (5, 2)

    def test_identicos_nao_geram_diferencas(
        self, par_basico: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par_basico
        (identico,) = compare_tables(a, b, key_columns=["codigo"]).by_category("identico")
        assert identico.differences == ()

    def test_bases_iguais_nao_tem_diferencas(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana", "10,00"]])
        b = _tabela("b.csv", [["1", "Ana", "10,00"]])
        assert compare_tables(a, b, key_columns=["codigo"]).has_differences is False


class TestChaveComposta:
    def test_ordem_declarada_nao_muda_o_pareamento(self) -> None:
        colunas = ["codigo", "filial", "valor"]
        a = _tabela("a.xlsx", [["1", "SP", "10,00"]], colunas)
        b = _tabela("b.xlsx", [["1", "SP", "12,00"]], colunas)

        direta = compare_tables(a, b, key_columns=["codigo", "filial"])
        invertida = compare_tables(a, b, key_columns=["filial", "codigo"])

        assert direta.records == invertida.records
        assert direta.key_columns == invertida.key_columns == ("codigo", "filial")

    def test_chave_composta_separa_registros_do_mesmo_codigo(self) -> None:
        colunas = ["codigo", "filial", "valor"]
        a = _tabela("a.xlsx", [["1", "SP", "10,00"], ["1", "RJ", "20,00"]], colunas)
        b = _tabela("b.xlsx", [["1", "SP", "10,00"], ["1", "RJ", "99,00"]], colunas)

        resultado = compare_tables(a, b, key_columns=["codigo", "filial"])
        assert resultado.counts["identico"] == 1
        assert resultado.counts["divergente"] == 1
        assert resultado.counts["conflitos"] == 0

    def test_chave_repetida_na_declaracao_e_deduplicada(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana", "10,00"]])
        b = _tabela("b.xlsx", [["1", "Ana", "10,00"]])
        resultado = compare_tables(a, b, key_columns=["codigo", "codigo"])
        assert resultado.key_columns == ("codigo",)


class TestConflitos:
    def test_chave_duplicada_em_a_nao_e_pareada(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana", "10,00"], ["1", "Ana II", "11,00"]])
        b = _tabela("b.xlsx", [["1", "Ana", "10,00"]])

        resultado = compare_tables(a, b, key_columns=["codigo"])

        assert resultado.records == ()
        (conflito,) = resultado.conflicts
        assert conflito.reason == "chave_duplicada"
        assert conflito.rows_a == (2, 3)
        assert conflito.rows_b == (2,)

    def test_chave_duplicada_so_em_b_tambem_vira_conflito(self) -> None:
        """Regressao: a duplicidade pode estar do lado B, com A intacto."""
        a = _tabela("a.xlsx", [["1", "Ana", "10,00"]])
        b = _tabela("b.xlsx", [["1", "Ana", "10,00"], ["1", "Ana", "10,00"]])

        resultado = compare_tables(a, b, key_columns=["codigo"])

        assert resultado.records == ()
        (conflito,) = resultado.conflicts
        assert conflito.reason == "chave_duplicada"
        assert conflito.rows_b == (2, 3)

    def test_chave_vazia_vai_para_conflito(self) -> None:
        a = _tabela("a.xlsx", [["", "Ana", "10,00"], ["1", "Bruno", "20,00"]])
        b = _tabela("b.xlsx", [["1", "Bruno", "20,00"]])

        resultado = compare_tables(a, b, key_columns=["codigo"])

        assert resultado.counts["identico"] == 1
        (conflito,) = resultado.conflicts
        assert conflito.reason == "chave_vazia"
        assert conflito.rows_a == (2,)
        assert conflito.rows_b == ()

    def test_nenhum_registro_some_do_relatorio(self) -> None:
        """Somatorio: registros classificados + linhas em conflito = linhas lidas."""
        a = _tabela(
            "a.xlsx",
            [["1", "Ana", "1"], ["2", "Bruno", "2"], ["2", "Bruno II", "3"], ["", "X", "4"]],
        )
        b = _tabela("b.xlsx", [["1", "Ana", "1"], ["2", "Bruno", "2"]])

        resultado = compare_tables(a, b, key_columns=["codigo"])
        linhas_a = {r.row_a for r in resultado.records if r.row_a is not None}
        for conflito in resultado.conflicts:
            linhas_a.update(conflito.rows_a)
        assert linhas_a == {2, 3, 4, 5}


class TestColunasComparadas:
    def test_default_usa_as_colunas_comuns_menos_a_chave(
        self, par_basico: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par_basico
        resultado = compare_tables(a, b, key_columns=["codigo"])
        assert resultado.compared_columns == ("nome", "valor")

    def test_coluna_so_em_uma_fonte_fica_de_fora_com_aviso(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana", "10,00"]], ["codigo", "nome", "extra_a"])
        b = _tabela("b.xlsx", [["1", "Ana", "x"]], ["codigo", "nome", "extra_b"])

        resultado = compare_tables(a, b, key_columns=["codigo"])

        assert resultado.compared_columns == ("nome",)
        ausentes = [w for w in resultado.warnings if w.code == "coluna_ausente"]
        assert {w.column for w in ausentes} == {"extra_a", "extra_b"}

    def test_selecao_explicita_restringe_a_comparacao(
        self, par_basico: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par_basico
        resultado = compare_tables(a, b, key_columns=["codigo"], columns=["nome"])

        assert resultado.compared_columns == ("nome",)
        # a divergencia estava em 'valor', que ficou fora: agora sao identicos
        assert resultado.counts["divergente"] == 0
        assert resultado.counts["identico"] == 2

    def test_coluna_pedida_que_nao_existe_vira_aviso(
        self, par_basico: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par_basico
        resultado = compare_tables(a, b, key_columns=["codigo"], columns=["fantasma"])
        codigos = {w.code for w in resultado.warnings}
        assert "coluna_ausente" in codigos

    def test_pedir_a_coluna_da_chave_avisa_que_ela_nao_e_comparada(
        self, par_basico: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par_basico
        resultado = compare_tables(a, b, key_columns=["codigo"], columns=["codigo", "nome"])
        assert resultado.compared_columns == ("nome",)
        assert any(w.code == "coluna_chave_ignorada" for w in resultado.warnings)

    def test_sem_coluna_comum_avisa_e_pareia_como_identico(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana"]], ["codigo", "so_a"])
        b = _tabela("b.xlsx", [["1", "Ana"]], ["codigo", "so_b"])

        resultado = compare_tables(a, b, key_columns=["codigo"])

        assert resultado.compared_columns == ()
        assert resultado.counts["identico"] == 1
        assert any(w.code == "sem_colunas_comparadas" for w in resultado.warnings)


class TestNormalizacao:
    def test_sem_normalizacao_a_comparacao_e_literal(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana Lima", "10,00"]])
        b = _tabela("b.xlsx", [["1", "  ana   lima ", "10,00"]])

        resultado = compare_tables(a, b, key_columns=["codigo"])
        assert resultado.counts["divergente"] == 1

    def test_espacos_e_caixa_apagam_a_diferenca_de_forma(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana Lima", "10,00"]])
        b = _tabela("b.xlsx", [["1", "  ana   lima ", "10,00"]])

        resultado = compare_tables(
            a, b, key_columns=["codigo"], normalizations=["espacos", "caixa"]
        )
        assert resultado.counts["identico"] == 1
        assert resultado.normalizations == ("espacos", "caixa")

    def test_digitos_pareia_documento_com_e_sem_mascara(self) -> None:
        a = _tabela("a.xlsx", [["529.982.247-25", "Ana", "10,00"]])
        b = _tabela("b.xlsx", [["52998224725", "Ana", "10,00"]])

        resultado = compare_tables(a, b, key_columns=["codigo"], normalizations=["digitos"])
        assert resultado.counts["identico"] == 1

    def test_digitos_nao_destroi_o_valor_das_colunas_comparadas(self) -> None:
        """'digitos' vale so para a chave: senao 'Ana' e 'Bruno' virariam iguais."""
        a = _tabela("a.xlsx", [["1", "Ana", "10,00"]])
        b = _tabela("b.xlsx", [["1", "Bruno", "10,00"]])

        resultado = compare_tables(a, b, key_columns=["codigo"], normalizations=["digitos"])
        assert resultado.counts["divergente"] == 1

    def test_valores_relatados_sao_os_originais(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana Lima", "10,00"]])
        b = _tabela("b.xlsx", [["1", "  ANA  SOUZA ", "10,00"]])

        resultado = compare_tables(
            a, b, key_columns=["codigo"], normalizations=["espacos", "caixa"]
        )
        (divergente,) = resultado.by_category("divergente")
        assert divergente.differences[0].value_b == "  ANA  SOUZA "

    @pytest.mark.parametrize("opcao", NORMALIZATION_OPTIONS)
    def test_todas_as_opcoes_declaradas_funcionam(self, opcao: str) -> None:
        a = _tabela("a.xlsx", [["1", "Ana", "10,00"]])
        b = _tabela("b.xlsx", [["1", "Ana", "10,00"]])
        resultado = compare_tables(a, b, key_columns=["codigo"], normalizations=[opcao])
        assert resultado.normalizations == (opcao,)

    def test_normalize_for_comparison_e_pura(self) -> None:
        assert normalize_for_comparison("  Ana   Lima ", ["espacos"]) == "Ana Lima"
        assert normalize_for_comparison("ANA", ["caixa"]) == "ana"
        assert normalize_for_comparison("1a2b3", ["digitos"], is_key=True) == "123"
        assert normalize_for_comparison("1a2b3", ["digitos"]) == "1a2b3"


class TestErrosDeUso:
    def test_sem_chave(self, par_basico: tuple[TableSource, TableSource]) -> None:
        a, b = par_basico
        with pytest.raises(CompareError, match="ao menos uma coluna de chave"):
            compare_tables(a, b, key_columns=[])

    def test_chave_inexistente_diz_em_qual_fonte(
        self, par_basico: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par_basico
        with pytest.raises(CompareError, match="fantasma"):
            compare_tables(a, b, key_columns=["fantasma"])

    def test_chave_ausente_apenas_em_b(self) -> None:
        a = _tabela("a.xlsx", [["1", "Ana", "10,00"]])
        b = _tabela("b.xlsx", [["Ana", "10,00"]], ["nome", "valor"])
        with pytest.raises(CompareError, match=r"B \(b.xlsx\)"):
            compare_tables(a, b, key_columns=["codigo"])

    def test_normalizacao_desconhecida(self, par_basico: tuple[TableSource, TableSource]) -> None:
        a, b = par_basico
        with pytest.raises(CompareError, match="normalizacao desconhecida"):
            compare_tables(a, b, key_columns=["codigo"], normalizations=["arredondar"])


class TestAvisosEstruturais:
    def test_linhas_vazias_descartadas_pelo_leitor_viram_aviso(self) -> None:
        a = TableSource(
            name="a.xlsx",
            frame=pd.DataFrame([["1", "Ana", "10,00"]], columns=COLUNAS, dtype=str),
            skipped_empty_rows=2,
        )
        b = _tabela("b.xlsx", [["1", "Ana", "10,00"]])

        resultado = compare_tables(a, b, key_columns=["codigo"])
        avisos = [w for w in resultado.warnings if w.code == "linhas_vazias_ignoradas"]
        assert len(avisos) == 1
        assert "fonte A" in avisos[0].message

    def test_limitacoes_viajam_no_resultado(
        self, par_basico: tuple[TableSource, TableSource]
    ) -> None:
        a, b = par_basico
        resultado = compare_tables(a, b, key_columns=["codigo"])
        assert resultado.limitations
        assert any("tolerancia" in limite for limite in resultado.limitations)

    def test_fontes_nao_sao_alteradas(self, par_basico: tuple[TableSource, TableSource]) -> None:
        a, b = par_basico
        antes_a = a.frame.copy()
        antes_b = b.frame.copy()

        compare_tables(a, b, key_columns=["codigo"], normalizations=["espacos", "caixa"])

        pd.testing.assert_frame_equal(a.frame, antes_a)
        pd.testing.assert_frame_equal(b.frame, antes_b)
