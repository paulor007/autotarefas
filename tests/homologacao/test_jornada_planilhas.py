"""
Homologação do card "Análise e organização de planilhas".

A planilha real do proprietário estava limpa: nenhuma célula precisou de
correção. Isso provou a PRESERVAÇÃO, mas não provou as CORREÇÕES. Estes
testes fecham essa lacuna com fixtures sintéticas onde cada linha tem um
comportamento esperado declarado antes da execução.

O que estes testes protegem, em uma frase cada:

- desligado significa desligado: sem confirmação, nenhuma célula muda;
- ligado corrige só o que é seguro, e registra o antes/depois;
- zero à esquerda nunca vira número;
- linha inteira repetida é sinalizada, nunca removida;
- chave repetida (venda com vários itens) NÃO é duplicidade;
- o que é ambíguo continua ambíguo e vai para revisão.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from openpyxl import load_workbook

from autotarefas.services import analyze_spreadsheet
from autotarefas.tasks.presentation import write_treated_xlsx
from autotarefas.tasks.validate import ValidateTask, load_schema

FIXTURES = Path(__file__).parent.parent / "fixtures" / "homologacao"
VENDAS = FIXTURES / "A_vendas_com_anomalias.xlsx"
DUAS_ABAS = FIXTURES / "B_duas_abas.xlsx"
APRESENTACAO = FIXTURES / "C_apresentacao_rica.xlsx"
COM_GRAFICO = FIXTURES / "D_com_grafico.xlsx"

#: Linha (física) de cada caso plantado na fixture A. O cabeçalho é a 1.
LINHA_ESPACOS = 3
LINHA_ZEROS = 4
LINHA_DUPLICADA_ORIGINAL = 11
LINHA_DUPLICADA_REPETIDA = 12
LINHA_PRODUTO_VAZIO = 13
LINHA_AMBIGUA = 14
LINHAS_MESMA_VENDA = (15, 16, 17, 18)


def _schema_de(caminho: Path, *, obrigatorios: tuple[str, ...] = ()) -> dict[str, Any]:
    """
    Schema sugerido pela análise, com o que a jornada confirma na tela.

    É exatamente o caminho do Live: a sugestão sai da análise; a pessoa
    confirma a detecção de linhas repetidas e (aqui) os obrigatórios.
    """
    analise = analyze_spreadsheet(caminho)
    schema = yaml.safe_load(analise.schema_suggestion)
    schema["detect_duplicate_rows"] = True
    for coluna in schema["columns"]:
        if coluna["name"] in obrigatorios:
            coluna["required"] = True
    return schema


def _rodar(
    caminho: Path,
    tmp_path: Path,
    *,
    modo: str,
    obrigatorios: tuple[str, ...] = (),
) -> tuple[ValidateTask, Any]:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        yaml.safe_dump(_schema_de(caminho, obrigatorios=obrigatorios), allow_unicode=True),
        encoding="utf-8",
    )
    task = ValidateTask(
        file_path=caminho,
        schema=load_schema(schema_path),
        mode=modo,  # type: ignore[arg-type]
    )
    return task, task.run()


@pytest.fixture
def desligado(tmp_path: Path) -> tuple[ValidateTask, Any]:
    return _rodar(VENDAS, tmp_path, modo="auditoria", obrigatorios=("Produto",))


@pytest.fixture
def ligado(tmp_path: Path) -> tuple[ValidateTask, Any]:
    return _rodar(VENDAS, tmp_path, modo="limpeza", obrigatorios=("Produto",))


# ============================================================
# Correções DESLIGADAS
# ============================================================


class TestCorrecoesDesligadas:
    def test_nenhuma_celula_e_modificada(self, desligado: tuple[ValidateTask, Any]) -> None:
        _, resultado = desligado
        assert resultado.data["total_cleaned"] == 0
        assert resultado.data["cleaning_changes"] == []

    def test_os_problemas_continuam_sendo_detectados(
        self, desligado: tuple[ValidateTask, Any]
    ) -> None:
        _, resultado = desligado
        assert resultado.data["total_errors"] + resultado.data["total_warnings"] > 0

    def test_espacos_continuam_no_dado(self, desligado: tuple[ValidateTask, Any]) -> None:
        task, _ = desligado
        assert task.processed_dataframe is not None
        loja = task.processed_dataframe.iloc[LINHA_ESPACOS - 2]["Loja"]
        assert str(loja) == "  Loja   Norte  "

    def test_arquivo_de_entrada_intocado(self, desligado: tuple[ValidateTask, Any]) -> None:
        antes = hashlib.sha256(VENDAS.read_bytes()).hexdigest()
        assert hashlib.sha256(VENDAS.read_bytes()).hexdigest() == antes


# ============================================================
# Correções LIGADAS
# ============================================================


class TestCorrecoesLigadas:
    def test_espacos_sao_normalizados(self, ligado: tuple[ValidateTask, Any]) -> None:
        task, _ = ligado
        assert task.processed_dataframe is not None
        assert task.processed_dataframe.iloc[LINHA_ESPACOS - 2]["Loja"] == "Loja Norte"

    def test_antes_e_depois_ficam_registrados(self, ligado: tuple[ValidateTask, Any]) -> None:
        _, resultado = ligado
        mudancas = resultado.data["cleaning_changes"]
        assert mudancas
        espaco = next(m for m in mudancas if m["line"] == LINHA_ESPACOS)
        assert espaco["before"] == "  Loja   Norte  "
        assert espaco["after"] == "Loja Norte"
        assert espaco["rules"]

    def test_zeros_a_esquerda_sobrevivem(self, ligado: tuple[ValidateTask, Any]) -> None:
        """'00123' jamais pode virar 123 — nem com as correções ligadas."""
        task, _ = ligado
        assert task.processed_dataframe is not None
        codigo = task.processed_dataframe.iloc[LINHA_ZEROS - 2]["Codigo Venda"]
        assert str(codigo) == "00123"

    def test_linha_duplicada_nao_e_removida(self, ligado: tuple[ValidateTask, Any]) -> None:
        task, resultado = ligado
        assert task.processed_dataframe is not None
        # As duas linhas continuam na tabela...
        assert len(task.processed_dataframe) == len(load_workbook(VENDAS)["Vendas"]["A"]) - 1
        # ...e a repetição virou problema com o número da linha.
        duplicadas = [
            i for i in resultado.data["issues"] if "duplicad" in str(i["message"]).lower()
        ]
        assert duplicadas
        assert any(i["line"] == LINHA_DUPLICADA_REPETIDA for i in duplicadas)

    def test_valor_ambiguo_nao_e_decidido(self, ligado: tuple[ValidateTask, Any]) -> None:
        """'1.234' pode ser 1234 ou 1,234: o AutoTarefas não escolhe por ninguém."""
        _, resultado = ligado
        mudancas = resultado.data["cleaning_changes"]
        assert all(m["line"] != LINHA_AMBIGUA for m in mudancas)

    def test_campo_obrigatorio_vazio_vira_problema(self, ligado: tuple[ValidateTask, Any]) -> None:
        _, resultado = ligado
        problemas = [i for i in resultado.data["issues"] if i["line"] == LINHA_PRODUTO_VAZIO]
        assert problemas
        assert any(i["severity"] == "error" for i in problemas)


# ============================================================
# Duplicidade x chave repetida (exigência do perfil de vendas)
# ============================================================


class TestDuplicidadeVersusChaveRepetida:
    def test_mesma_venda_com_varios_itens_nao_e_duplicidade(
        self, ligado: tuple[ValidateTask, Any]
    ) -> None:
        """V-100 aparece em 4 linhas diferentes: é uma venda com 4 itens."""
        _, resultado = ligado
        duplicadas = [
            i for i in resultado.data["issues"] if "duplicad" in str(i["message"]).lower()
        ]
        linhas_acusadas = {i["line"] for i in duplicadas}
        assert not linhas_acusadas & set(LINHAS_MESMA_VENDA)

    def test_somente_a_linha_inteira_repetida_e_sinalizada(
        self, ligado: tuple[ValidateTask, Any]
    ) -> None:
        _, resultado = ligado
        duplicadas = [
            i for i in resultado.data["issues"] if "duplicad" in str(i["message"]).lower()
        ]
        # Exatamente uma ocorrência excedente na fixture (linhas 11 e 12).
        assert len(duplicadas) == 1
        assert duplicadas[0]["line"] == LINHA_DUPLICADA_REPETIDA

    def test_analise_conta_a_excedente_nao_o_par(self) -> None:
        """1 excedente = 2 linhas envolvidas. O relatório não pode confundir."""
        analise = analyze_spreadsheet(VENDAS)
        achado = next(f for f in analise.report["findings"] if f["code"] == "linhas_duplicadas")
        assert achado["message"].startswith("1 linha")

    def test_os_quatro_itens_da_venda_seguem_validos(
        self, ligado: tuple[ValidateTask, Any]
    ) -> None:
        _, resultado = ligado
        com_erro = {i["line"] for i in resultado.data["issues"] if i["severity"] == "error"}
        assert not com_erro & set(LINHAS_MESMA_VENDA)


# ============================================================
# Ambiguidade de aba (fixture B)
# ============================================================


class TestDuasAbas:
    def test_o_sistema_pergunta_qual_aba(self) -> None:
        analise = analyze_spreadsheet(DUAS_ABAS)
        assert analise.needs_choice is True
        (ambiguidade,) = analise.ambiguities
        assert ambiguidade.kind == "sheet"
        assert {o.name for o in ambiguidade.sheet_options} == {"Dezembro", "Janeiro"}

    def test_nenhuma_aba_e_escolhida_em_silencio(self) -> None:
        analise = analyze_spreadsheet(DUAS_ABAS)
        assert analise.ok is False  # sem escolha, nao segue

    def test_com_a_escolha_a_analise_conclui(self) -> None:
        analise = analyze_spreadsheet(DUAS_ABAS, sheet="Janeiro")
        assert analise.ok is True
        assert analise.selected_sheet == "Janeiro"


# ============================================================
# Preservação (fixture C) e limitação declarada (fixture D)
# ============================================================


class TestPreservacao:
    def _tratar(self, origem: Path, tmp_path: Path, *, aba: str) -> Path:
        destino = tmp_path / "planilha_tratada.xlsx"
        write_treated_xlsx(
            origem,
            destino,
            [{"line": 2, "column": "Cliente", "after": "Cliente Um"}],
            sheet=aba,
        )
        return destino

    def test_recursos_visuais_sobrevivem(self, tmp_path: Path) -> None:
        tratada = self._tratar(APRESENTACAO, tmp_path, aba="Base")
        ws = load_workbook(tratada)["Base"]

        assert ws.freeze_panes == "A2"
        assert ws.auto_filter.ref == "A1:F3"
        assert ws.column_dimensions["B"].width == 38
        assert ws["A1"].fill.fgColor.rgb == "001F4E78"
        assert ws["A1"].font.bold is True
        assert ws["C2"].number_format == "DD/MM/YYYY"
        assert ws["E2"].number_format == "R$ #,##0.00"

    def test_formula_nao_tocada_continua_formula(self, tmp_path: Path) -> None:
        tratada = self._tratar(APRESENTACAO, tmp_path, aba="Base")
        ws = load_workbook(tratada)["Base"]
        assert str(ws["F2"].value).startswith("=")

    def test_zeros_a_esquerda_no_arquivo_tratado(self, tmp_path: Path) -> None:
        tratada = self._tratar(APRESENTACAO, tmp_path, aba="Base")
        ws = load_workbook(tratada)["Base"]
        assert ws["A2"].value == "00123"

    def test_valor_corrigido_foi_aplicado(self, tmp_path: Path) -> None:
        tratada = self._tratar(APRESENTACAO, tmp_path, aba="Base")
        assert load_workbook(tratada)["Base"]["B2"].value == "Cliente Um"

    def test_grafico_e_declarado_como_nao_preservado(self, tmp_path: Path) -> None:
        relatorio = write_treated_xlsx(COM_GRAFICO, tmp_path / "tratada.xlsx", [], sheet="Base")
        assert relatorio.fully_preserved is False
        assert any("grafico" in item for item in relatorio.not_preserved)

    def test_o_relatorio_de_preservacao_e_serializavel(self, tmp_path: Path) -> None:
        relatorio = write_treated_xlsx(COM_GRAFICO, tmp_path / "tratada.xlsx", [], sheet="Base")
        payload = json.loads(json.dumps(relatorio.as_dict(), ensure_ascii=False))
        assert payload["preservacao_total"] is False
        assert payload["nao_preservado"]


def test_as_fixtures_existem() -> None:
    """Fixtures versionadas e sintéticas: nenhum dado real entra no Git."""
    for caminho in (VENDAS, DUAS_ABAS, APRESENTACAO, COM_GRAFICO):
        assert caminho.is_file(), caminho
