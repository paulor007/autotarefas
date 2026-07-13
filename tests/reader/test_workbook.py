"""
Matriz de leitura: as 27 fixtures.

Cada fixture isola UM problema. Este arquivo e a defesa contra o leitor
ficar bom numa planilha so.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from autotarefas.reader import ColumnInfo, ReaderError, WorkbookReadResult, read_workbook

FIXTURES = Path(__file__).parent.parent / "fixtures" / "planilhas"


def ler(
    nome: str,
    sheet: str | None = None,
    header_row: int | None = None,
) -> WorkbookReadResult:
    return read_workbook(FIXTURES / nome, sheet=sheet, header_row=header_row)


def coluna(resultado: WorkbookReadResult, nome: str) -> ColumnInfo:
    """Busca a coluna e falha o teste se ela nao existir (mantem o mypy feliz)."""
    col = resultado.column(nome)
    assert col is not None, f"coluna '{nome}' nao foi detectada"
    return col


def normalizado(resultado: WorkbookReadResult) -> pd.DataFrame:
    assert resultado.normalized_dataframe is not None
    return resultado.normalized_dataframe


def original(resultado: WorkbookReadResult) -> pd.DataFrame:
    assert resultado.original_dataframe is not None
    return resultado.original_dataframe


def motivo(resultado: WorkbookReadResult) -> str:
    assert resultado.rejected_reason is not None, "esperava recusa, mas o arquivo foi aceito"
    return resultado.rejected_reason


# --- LIMPAS ------------------------------------------------------------------


class TestLimpas:
    def test_csv_limpo(self) -> None:
        r = ler("01_csv_limpo.csv")
        assert r.ok
        assert r.header_row == 1
        assert r.row_count == 3
        assert [c.name for c in r.detected_columns] == ["nome", "idade", "cidade"]
        assert coluna(r, "idade").inferred_type == "inteiro"

    def test_xlsx_limpo(self) -> None:
        r = ler("02_xlsx_limpo.xlsx")
        assert r.ok
        assert r.selected_sheet == "Plan1"
        assert r.row_count == 3

    def test_clientes(self) -> None:
        r = ler("03_clientes.xlsx")
        assert coluna(r, "cpf").inferred_type == "identificador"  # mascara de digitos

    def test_vendas(self) -> None:
        r = ler("04_vendas.xlsx")
        assert coluna(r, "Data").inferred_type == "data"
        assert coluna(r, "Valor Unitario").inferred_type == "decimal"

    def test_produtos(self) -> None:
        r = ler("05_produtos.xlsx")
        assert coluna(r, "sku").inferred_type == "texto"  # "PRD-0001" nao e so digito
        assert coluna(r, "preco").inferred_type == "decimal"


# --- ESTRUTURA ---------------------------------------------------------------


class TestEstrutura:
    def test_cabecalho_na_linha_4(self) -> None:
        r = ler("06_cabecalho_linha_4.xlsx")
        assert r.ok
        assert r.header_row == 4
        assert r.row_count == 3
        assert [c.name for c in r.detected_columns] == ["produto", "quantidade", "valor"]

    def test_tres_abas_ambiguidade(self) -> None:
        """3 abas plausiveis -> NAO escolhe sozinho: pede --sheet."""
        r = ler("07_tres_abas.xlsx")
        assert not r.ok
        assert "--sheet" in motivo(r)
        assert len(r.available_sheets) == 3

    def test_tres_abas_com_sheet_explicito(self) -> None:
        r = ler("07_tres_abas.xlsx", sheet="Estoque")
        assert r.ok
        assert r.selected_sheet == "Estoque"
        assert [c.name for c in r.detected_columns] == ["sku", "saldo"]

    def test_capa_e_dados_escolhe_a_aba_de_dados(self) -> None:
        """A aba 1 e uma CAPA. O leitor tem que escolher 'Dados'."""
        r = ler("08_capa_e_dados.xlsx")
        assert r.ok
        assert r.selected_sheet == "Dados"
        assert r.row_count == 4

    def test_mescladas_antes_do_cabecalho(self) -> None:
        r = ler("24_mescladas_antes_do_cabecalho.xlsx")
        assert r.ok
        assert r.header_row == 3
        assert r.row_count == 3

    def test_nao_tabular_e_RECUSADO(self) -> None:
        """O criterio-chave: recusar em vez de entregar lixo."""
        r = ler("25_nao_tabular.xlsx")
        assert not r.ok
        assert r.rejected_reason
        assert r.original_dataframe is None


# --- COLUNAS -----------------------------------------------------------------


class TestColunas:
    def test_ordem_diferente(self) -> None:
        r = ler("09_ordem_diferente.xlsx")
        assert [c.name for c in r.detected_columns] == ["cpf", "nome", "telefone", "email"]

    def test_colunas_desconhecidas(self) -> None:
        r = ler("10_colunas_desconhecidas.xlsx")
        assert r.ok  # o leitor nao exige coluna nenhuma
        assert r.row_count == 2

    def test_coluna_vazia(self) -> None:
        r = ler("11_coluna_vazia.xlsx")
        assert coluna(r, "reservado").inferred_type == "vazio"
        assert any(w.code == "coluna_vazia" for w in r.warnings)


# --- LINHAS ------------------------------------------------------------------


class TestLinhas:
    def test_linhas_vazias_no_meio_sao_ignoradas(self) -> None:
        r = ler("12_linhas_vazias_no_meio.xlsx")
        assert r.row_count == 3  # 3 produtos; as vazias nao viram registro

    def test_linhas_duplicadas_sao_AVISADAS_nao_removidas(self) -> None:
        r = ler("21_linhas_duplicadas.xlsx")
        assert r.row_count == 4  # NADA foi removido
        aviso = next(w for w in r.warnings if w.code == "linhas_duplicadas")
        assert "1 linha" in aviso.message

    def test_rodape_de_totais_e_MARCADO_nao_removido(self) -> None:
        r = ler("23_rodape_de_totais.xlsx")
        assert r.row_count == 4  # o TOTAL continua la
        assert any(w.code == "rodape_suspeito" for w in r.warnings)


# --- TIPOS -------------------------------------------------------------------


class TestTipos:
    def test_numero_como_texto(self) -> None:
        r = ler("13_numero_como_texto.csv")
        assert coluna(r, "quantidade").inferred_type == "inteiro"
        assert list(normalizado(r)["quantidade"]) == [2, 1, 3]

    def test_moeda_br(self) -> None:
        r = ler("14_moeda_br.csv")
        assert coluna(r, "preco").inferred_type == "moeda"
        assert list(normalizado(r)["preco"]) == [1234.56, 89.90, 12.00]
        conv = next(c for c in r.conversions if c.column == "preco")
        assert conv.rule == "moeda_br"
        assert conv.original == "R$ 1.234,56"
        assert conv.normalized == "1234.56"

    def test_moeda_us(self) -> None:
        r = ler("15_moeda_us.csv")
        assert list(normalizado(r)["preco"]) == [1234.56, 89.90, 12.00]

    def test_serial_sem_formato_de_data_e_OBSERVADO_nao_convertido(self) -> None:
        """43800 sem formato de data e indistinguivel de uma quantidade.

        Converter seria ADIVINHAR. O leitor observa e deixa o valor intacto.
        """
        r = ler("16_datas_seriais.xlsx")
        col = coluna(r, "data")
        assert col.inferred_type == "inteiro"
        assert any("data serial" in o for o in col.observations)
        assert r.conversions == []

    def test_datas_ddmmaaaa(self) -> None:
        r = ler("17_datas_ddmmaaaa.csv")
        assert coluna(r, "data").inferred_type == "data"
        assert next(iter(normalizado(r)["data"])) == datetime(2019, 12, 1)

    def test_tipos_misturados_NAO_sao_convertidos_a_forca(self) -> None:
        r = ler("18_tipos_misturados.csv")
        assert coluna(r, "quantidade").inferred_type == "misto"
        assert any(w.code == "coluna_mista" for w in r.warnings)
        # nada foi convertido: os valores originais continuam la
        assert list(normalizado(r)["quantidade"]) == ["2", "uma duzia", "3"]

    def test_zeros_a_esquerda_preservados(self) -> None:
        r = ler("26_zeros_a_esquerda.csv")
        assert coluna(r, "codigo").inferred_type == "identificador"
        assert list(normalizado(r)["codigo"]) == ["00123", "00456", "00789"]


# --- FORMULAS E ERROS --------------------------------------------------------


class TestFormulasEErros:
    def test_formulas_sao_avisadas(self) -> None:
        r = ler("19_formulas.xlsx")
        assert r.ok
        assert any(w.code == "formulas" for w in r.warnings)

    def test_erros_do_excel_detectados(self) -> None:
        r = ler("20_erros_excel.xlsx")
        assert coluna(r, "margem").inferred_type == "erro"
        assert any(w.code == "erro_excel" for w in r.warnings)


# --- DOMINIO (o leitor NAO julga; so le) -------------------------------------


class TestDominio:
    def test_codigo_repetido_e_lido_sem_julgamento(self) -> None:
        """O leitor NAO decide se codigo repetido e duplicidade. Isso e do perfil."""
        r = ler("22_codigo_repetido_valido.xlsx")
        assert r.row_count == 4
        assert not any(w.code == "linhas_duplicadas" for w in r.warnings)

    def test_valor_derivado_divergente_e_apenas_LIDO(self) -> None:
        """O leitor nao checa formulas de negocio (isso e a subetapa 1.5)."""
        r = ler("27_valor_derivado_divergente.xlsx")
        assert r.ok
        assert r.row_count == 3


# --- PRESERVACAO E RECUSA ----------------------------------------------------


class TestPreservacao:
    def test_original_e_fiel_e_normalizado_tem_trilha(self) -> None:
        r = ler("14_moeda_br.csv")
        # o original mantem o texto EXATO do arquivo
        assert list(original(r)["preco"]) == ["R$ 1.234,56", "R$ 89,90", "R$ 12,00"]
        # toda diferenca tem uma Conversion
        assert len(r.conversions) == 3
        assert len(original(r)) == len(normalizado(r))

    def test_arquivo_inexistente(self) -> None:
        with pytest.raises(ReaderError, match="nao encontrado"):
            read_workbook(FIXTURES / "nao_existe.xlsx")

    def test_extensao_nao_suportada(self, tmp_path: Path) -> None:
        alvo = tmp_path / "dados.txt"
        alvo.write_text("a,b\n1,2\n", encoding="utf-8")
        r = read_workbook(alvo)
        assert not r.ok
        assert "extensao nao suportada" in motivo(r)

    def test_xls_antigo_recusado_com_orientacao(self, tmp_path: Path) -> None:
        alvo = tmp_path / "antigo.xls"
        alvo.write_bytes(b"\xd0\xcf\x11\xe0")
        r = read_workbook(alvo)
        assert not r.ok
        assert "converta para .xlsx" in motivo(r)

    def test_header_row_explicito_sobrescreve(self) -> None:
        r = ler("06_cabecalho_linha_4.xlsx", header_row=4)
        assert r.ok
        assert r.header_row == 4
        assert r.header_confidence == 1.0


class TestVolume:
    """A fixture sintetica: mesma estrutura de uma exportacao empresarial real."""

    def test_le_planilha_com_volume_e_moeda(self) -> None:
        r = ler("28_vendas_sintetica.xlsx")
        assert r.ok
        assert r.selected_sheet == "Plan1"
        assert r.header_row == 1
        assert r.row_count == 245
        assert len(r.detected_columns) == 7

    def test_moeda_reconhecida_pelo_number_format(self) -> None:
        r = ler("28_vendas_sintetica.xlsx")
        assert coluna(r, "Valor Unitario").inferred_type == "moeda"
        assert coluna(r, "Valor Final").inferred_type == "moeda"
        formato = coluna(r, "Valor Final").excel_number_format
        assert formato is not None
        assert "R$" in formato

    def test_nenhuma_conversao_em_planilha_ja_tipada(self) -> None:
        """Os valores ja sao numero/data no Excel: nada a converter."""
        r = ler("28_vendas_sintetica.xlsx")
        assert r.conversions == []

    def test_duplicatas_avisadas_sem_remocao(self) -> None:
        r = ler("28_vendas_sintetica.xlsx")
        assert any(w.code == "linhas_duplicadas" for w in r.warnings)
        assert r.row_count == 245  # nada removido
