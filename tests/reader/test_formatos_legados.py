"""
Leitura de `.xls` e `.ods` — os formatos que ainda circulam em orgao publico.

Sao formatos SO DE LEITURA para o produto: o openpyxl nao os abre, entao nao
ha como avaliar apresentacao nem gerar a versao organizada. A analise geral —
duplicidade, tipos, vazios, cabecalho — funciona igual, e e o que a maioria
dessas planilhas precisa. Prometer organizacao aqui seria mentira.

As fixtures nascem no proprio teste: um `.ods` binario versionado seria um
arquivo opaco no repositorio, e gerar na hora prova tambem que a dependencia
esta instalada.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from autotarefas.reader import read_workbook


@pytest.fixture
def beneficios_ods(tmp_path: Path) -> Path:
    """Planilha de assistencia social, com uma linha repetida de proposito."""
    destino = tmp_path / "beneficios.ods"
    pd.DataFrame(
        {
            "Protocolo": ["000123", "000124", "000125", "000125"],
            "Familia": ["Silva", "Souza", "Lima", "Lima"],
            "Valor": [600, 600, 450, 450],
        }
    ).to_excel(destino, index=False, engine="odf")
    return destino


class TestOds:
    def test_e_lido_como_tabela(self, beneficios_ods: Path) -> None:
        leitura = read_workbook(beneficios_ods)

        assert leitura.ok, leitura.rejected_reason
        assert leitura.file_type == "legado"
        assert leitura.header_row == 1
        assert list(leitura.original_dataframe.columns) == ["Protocolo", "Familia", "Valor"]
        assert len(leitura.original_dataframe) == 4

    def test_analise_geral_funciona_igual(self, beneficios_ods: Path) -> None:
        """A verificacao de linhas repetidas nao depende do formato do arquivo."""
        leitura = read_workbook(beneficios_ods)

        assert "linhas_duplicadas" in {aviso.code for aviso in leitura.warnings}

    def test_o_arquivo_nao_e_alterado(self, beneficios_ods: Path) -> None:
        import hashlib

        antes = hashlib.sha256(beneficios_ods.read_bytes()).hexdigest()
        read_workbook(beneficios_ods)

        assert hashlib.sha256(beneficios_ods.read_bytes()).hexdigest() == antes


#: `.xls` de verdade, gravado pelo Excel (BIFF8). Nao da para gerar aqui:
#: `xlrd` so le, e `xlwt` esta sem manutencao desde 2017 — por isso a fixture
#: e versionada. Ver `tests/fixtures/dominios/build_fixtures.py`.
PATRIMONIO_XLS = (
    Path(__file__).resolve().parents[1] / "fixtures" / "dominios" / "patrimonio_legado.xls"
)


class TestXls:
    """
    `.xls` legitimo, do Excel — nao um arquivo renomeado.

    Este e o formato que ainda chega de sistemas antigos de orgao publico.
    Aceitar a extensao sem nunca ter lido um arquivo valido seria promessa
    sem prova.
    """

    def test_e_mesmo_um_xls_e_nao_um_xlsx_renomeado(self) -> None:
        """A assinatura OLE (D0CF11E0) prova que o binario e BIFF, nao zip."""
        assert PATRIMONIO_XLS.read_bytes()[:4] == bytes.fromhex("d0cf11e0")

    def test_e_lido_como_tabela(self) -> None:
        leitura = read_workbook(PATRIMONIO_XLS)

        assert leitura.ok, leitura.rejected_reason
        assert leitura.file_type == "legado"
        assert leitura.selected_sheet == "Bens"
        assert leitura.header_row == 1
        assert list(leitura.original_dataframe.columns) == [
            "Tombamento",
            "Bem",
            "Setor",
            "Valor",
        ]
        assert len(leitura.original_dataframe) == 6

    def test_analise_geral_funciona_igual(self) -> None:
        leitura = read_workbook(PATRIMONIO_XLS)

        assert "linhas_duplicadas" in {aviso.code for aviso in leitura.warnings}

    def test_zero_a_esquerda_sobrevive(self) -> None:
        """`000431` e tombamento, nao quantidade. Virar 431 seria estrago."""
        leitura = read_workbook(PATRIMONIO_XLS)

        assert leitura.original_dataframe.iloc[0, 0] == "000431"


class TestRecusas:
    def test_xls_estragado_e_recusa_e_nao_erro(self, tmp_path: Path) -> None:
        """
        `xlrd` levanta excecao propria, que nao herda de ValueError.

        Deixar escapar viraria erro 500 para quem so mandou um arquivo
        estragado — e um `.xlsx` renomeado para `.xls` e comum demais.
        """
        falso = tmp_path / "renomeado.xls"
        falso.write_bytes(b"PK\x03\x04 isto e um xlsx disfarcado")

        leitura = read_workbook(falso)

        assert leitura.ok is False
        assert leitura.rejected_reason
        assert "nao foi possivel ler o arquivo .xls" in leitura.rejected_reason

    def test_extensao_desconhecida_diz_quais_valem(self, tmp_path: Path) -> None:
        estranho = tmp_path / "planilha.numbers"
        estranho.write_bytes(b"qualquer coisa")

        leitura = read_workbook(estranho)

        assert leitura.ok is False
        assert leitura.rejected_reason
        assert ".ods" in leitura.rejected_reason
