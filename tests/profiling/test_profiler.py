"""
Perfilagem: a matriz das fixtures.

A regra que estes testes protegem: a perfilagem OBSERVA e DESCREVE.
Nunca conclui obrigatoriedade, nunca conclui unicidade, nunca remove nada.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from autotarefas.profiling import ColumnProfile, ProfileResult, profile_workbook
from autotarefas.reader import read_workbook

FIXTURES = Path(__file__).parent.parent / "fixtures" / "planilhas"


def perfilar(nome: str) -> ProfileResult:
    return profile_workbook(read_workbook(FIXTURES / nome))


def col(perfil: ProfileResult, nome: str) -> ColumnProfile:
    achada = perfil.column(nome)
    assert achada is not None, f"coluna '{nome}' nao foi perfilada"
    return achada


# --- Metricas gerais ---------------------------------------------------------


class TestMetricasGerais:
    def test_planilha_limpa(self) -> None:
        p = perfilar("02_xlsx_limpo.xlsx")
        assert p.ok
        assert p.row_count == 3
        assert p.column_count == 3
        assert p.total_cells == 9
        assert p.filled_cells == 9
        assert p.empty_cells == 0
        assert p.fill_rate == 1.0
        assert p.duplicate_row_count == 0
        assert p.mixed_type_column_count == 0
        assert p.excel_error_count == 0

    def test_metadados_do_leitor_sao_repassados(self) -> None:
        p = perfilar("06_cabecalho_linha_4.xlsx")
        assert p.selected_sheet == "Plan1"
        assert p.header_row == 4
        assert p.reader_confidence > 0

    def test_arquivo_recusado_nao_inventa_metricas(self) -> None:
        p = perfilar("25_nao_tabular.xlsx")
        assert not p.ok
        assert p.rejected_reason
        assert p.row_count == 0
        assert p.columns == []


# --- Preenchimento e colunas vazias ------------------------------------------


class TestPreenchimento:
    def test_coluna_totalmente_vazia(self) -> None:
        p = perfilar("11_coluna_vazia.xlsx")
        c = col(p, "reservado")
        assert c.inferred_type == "vazio"
        assert c.filled_count == 0
        assert c.fill_rate == 0.0
        assert p.completely_empty_column_count == 1
        # informacao, NAO problema: obrigatoriedade e do schema
        achado = next(f for f in p.findings if f.code == "coluna_vazia")
        assert achado.severity == "informacao"

    def test_vazio_nao_e_declarado_invalido(self) -> None:
        p = perfilar("11_coluna_vazia.xlsx")
        assert not any(f.severity == "problema" for f in p.findings)

    def test_linhas_vazias_sao_contadas_mas_nao_viram_registro(self) -> None:
        p = perfilar("12_linhas_vazias_no_meio.xlsx")
        assert p.row_count == 3
        assert p.completely_empty_row_count == 2


# --- Duplicidade: linha inteira != valor repetido -----------------------------


class TestDuplicidade:
    def test_linha_completamente_duplicada(self) -> None:
        p = perfilar("21_linhas_duplicadas.xlsx")
        assert p.duplicate_row_count == 1  # 1 EXCEDENTE
        assert p.row_count == 4  # nada removido

    def test_valor_repetido_legitimo_NAO_e_duplicidade_de_linha(self) -> None:
        """Codigo repetido em linhas diferentes e valido — e o caso multi-item."""
        p = perfilar("22_codigo_repetido_valido.xlsx")
        assert p.duplicate_row_count == 0  # nenhuma LINHA identica
        c = col(p, "codigo_venda")
        assert c.distinct_count == 2
        assert c.duplicate_value_count == 2  # so estatistica
        # e nenhum achado diz que a coluna "deveria ser unica"
        assert not any("unic" in f.message.lower() for f in p.findings)

    def test_nunca_conclui_unicidade(self) -> None:
        p = perfilar("28_vendas_sintetica.xlsx")
        for c in p.columns:
            assert all("deve ser unic" not in o for o in c.observations)


# --- Tipos -------------------------------------------------------------------


class TestTipos:
    def test_tipos_misturados_sao_reportados_com_contagem(self) -> None:
        p = perfilar("18_tipos_misturados.csv")
        c = col(p, "quantidade")
        assert c.inferred_type == "misto"
        assert c.mixed_types == {"inteiro": 2, "texto": 1}
        achado = next(f for f in p.findings if f.code == "tipos_misturados")
        assert achado.severity == "aviso"  # aviso, NAO erro
        assert p.mixed_type_column_count == 1

    def test_numero_como_texto(self) -> None:
        p = perfilar("13_numero_como_texto.csv")
        c = col(p, "quantidade")
        assert c.inferred_type == "inteiro"
        assert c.minimum == "1"
        assert c.maximum == "3"

    def test_moeda_tem_min_e_max(self) -> None:
        p = perfilar("14_moeda_br.csv")
        c = col(p, "preco")
        assert c.inferred_type == "moeda"
        assert c.minimum == "12"
        assert c.maximum == "1234.56"

    def test_data_tem_min_e_max(self) -> None:
        p = perfilar("17_datas_ddmmaaaa.csv")
        c = col(p, "data")
        assert c.minimum == "2019-12-01"
        assert c.maximum == "2019-12-31"

    def test_identificador_NAO_tem_min_max(self) -> None:
        """'O menor CPF da base' nao e uma metrica — e um acidente."""
        p = perfilar("26_zeros_a_esquerda.csv")
        c = col(p, "codigo")
        assert c.inferred_type == "identificador"
        assert c.minimum is None
        assert c.maximum is None

    def test_texto_NAO_tem_min_max(self) -> None:
        c = col(perfilar("02_xlsx_limpo.xlsx"), "nome")
        assert c.minimum is None


# --- Espacos, erros do Excel --------------------------------------------------


class TestQualidade:
    def test_espacos_extras_detectados_sem_modificar(self) -> None:
        p = perfilar("29_espacos_extras.csv")
        c = col(p, "produto")
        assert c.whitespace_issue_count == 3  # 2 nas pontas + 1 interno
        achado = next(f for f in p.findings if f.code == "espacos_extras")
        assert achado.severity == "aviso"
        assert achado.samples

    def test_erros_do_excel_sao_problema(self) -> None:
        p = perfilar("20_erros_excel.xlsx")
        c = col(p, "margem")
        assert c.excel_error_count == 3
        assert p.excel_error_count == 3
        achado = next(f for f in p.findings if f.code == "erro_excel")
        assert achado.severity == "problema"


# --- Cardinalidade: informacao, nunca conclusao -------------------------------


class TestCardinalidade:
    def test_alta_cardinalidade_e_apenas_observada(self) -> None:
        p = perfilar("28_vendas_sintetica.xlsx")
        c = col(p, "Valor Final")
        assert c.uniqueness_rate > 0
        assert not any("chave" in o.lower() for o in c.observations)

    def test_baixa_cardinalidade_sugere_categorico_sem_concluir(self) -> None:
        p = perfilar("28_vendas_sintetica.xlsx")
        c = col(p, "ID Loja")
        assert c.distinct_count == 5
        assert any("categorico" in o for o in c.observations)
        assert not any("enum" in o.lower() for o in c.observations)


# --- Preservacao --------------------------------------------------------------


class TestPreservacao:
    def test_nao_altera_os_dataframes(self) -> None:
        leitura = read_workbook(FIXTURES / "29_espacos_extras.csv")
        assert leitura.original_dataframe is not None
        assert leitura.normalized_dataframe is not None
        antes_original = leitura.original_dataframe.copy(deep=True)
        antes_normalizado = leitura.normalized_dataframe.copy(deep=True)

        profile_workbook(leitura)

        pd.testing.assert_frame_equal(leitura.original_dataframe, antes_original)
        pd.testing.assert_frame_equal(leitura.normalized_dataframe, antes_normalizado)

    def test_original_preserva_os_espacos(self) -> None:
        leitura = read_workbook(FIXTURES / "29_espacos_extras.csv")
        assert leitura.original_dataframe is not None
        assert list(leitura.original_dataframe["produto"])[:2] == ["  Camisa", "Calca  "]

    def test_deterministico(self) -> None:
        a = perfilar("28_vendas_sintetica.xlsx")
        b = perfilar("28_vendas_sintetica.xlsx")
        assert a.row_count == b.row_count
        assert a.duplicate_row_count == b.duplicate_row_count
        assert [c.distinct_count for c in a.columns] == [c.distinct_count for c in b.columns]
        assert [f.code for f in a.findings] == [f.code for f in b.findings]


# --- Volume -------------------------------------------------------------------


class TestVolume:
    def test_vendas_sintetica(self) -> None:
        p = perfilar("28_vendas_sintetica.xlsx")
        assert p.row_count == 245
        assert p.column_count == 7
        assert p.empty_cells == 0
        assert p.duplicate_row_count == 3
        assert p.mixed_type_column_count == 0
        assert p.excel_error_count == 0
        assert col(p, "Quantidade").minimum == "1"
        assert col(p, "Valor Unitario").inferred_type == "moeda"

    def test_avisos_do_leitor_sao_consolidados_sem_duplicar(self) -> None:
        p = perfilar("28_vendas_sintetica.xlsx")
        codigos = [f.code for f in p.findings]
        assert "linhas_duplicadas" in codigos
        assert len(codigos) == len(set(codigos)) or codigos.count("linhas_duplicadas") == 1
