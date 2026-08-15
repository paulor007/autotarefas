"""
Card 01 — Análise e organização de planilhas: o contrato, em testes.

Cada classe abaixo corresponde a um item dos critérios de aceite. As
fixtures são de domínios diferentes de propósito (vendas, financeiro,
serviço público, estoque, clientes, pesquisa, atendimentos, contratos):
o card não pode ter sido calibrado para uma planilha só.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from autotarefas.organize import (
    ANALYSIS_REPORT_NAME,
    IndicatorRequest,
    ReportInput,
    SortRequest,
    audit_presentation,
    build_indicators,
    candidates,
    needs_sheet_choice,
    organize_workbook,
    suggest_roles,
    summary_is_offerable,
    survey_sheets,
    write_analysis_report,
)
from autotarefas.reader import read_workbook

FIXTURES = Path(__file__).parent.parent / "fixtures" / "dominios"

VENDAS = FIXTURES / "vendas_simples.xlsx"
FINANCEIRO = FIXTURES / "financeiro_profissional.xlsx"
PUBLICO = FIXTURES / "servico_publico.xlsx"
ESTOQUE = FIXTURES / "estoque_com_formulas.xlsx"
CLIENTES = FIXTURES / "clientes.csv"
PESQUISA = FIXTURES / "pesquisa_ambigua.xlsx"
ATENDIMENTOS = FIXTURES / "atendimentos_duas_abas.xlsx"
CONTRATOS = FIXTURES / "contratos_sem_anomalia.xlsx"


# ============================================================
# Avaliação objetiva da apresentação
# ============================================================


class TestAvaliacaoDaApresentacao:
    def test_planilha_profissional_e_declarada_organizada(self) -> None:
        """Quem já cuidou da planilha não recebe proposta de reformatação."""
        audit = audit_presentation(FINANCEIRO)
        assert audit.verdict == "organizada"
        assert audit.can_improve is False
        assert audit.failures == ()

    def test_planilha_crua_pode_ser_melhorada(self) -> None:
        audit = audit_presentation(VENDAS)
        assert audit.verdict == "melhoravel"
        assert audit.can_improve is True
        pendencias = {c.key for c in audit.failures}
        assert {"cabecalho_destacado", "filtro", "painel_congelado"} <= pendencias

    def test_estrutura_com_mesclagem_e_ambigua(self) -> None:
        """Mesclagem na área de dados: o card não decide sozinho."""
        audit = audit_presentation(PESQUISA)
        assert audit.verdict == "ambigua"
        assert audit.can_improve is False

    def test_cada_criterio_traz_a_evidencia(self) -> None:
        audit = audit_presentation(VENDAS)
        assert all(c.detail for c in audit.criteria)
        assert {c.key for c in audit.criteria} >= {
            "cabecalho_presente",
            "estrutura_tabular",
            "larguras_adequadas",
            "formatos_consistentes",
            "alinhamento_coerente",
            "filtro",
            "painel_congelado",
            "cores_moderadas",
        }

    def test_veredito_e_serializavel(self) -> None:
        payload = audit_presentation(CONTRATOS).as_dict()
        assert payload["veredito"] == "organizada"
        assert payload["criterios"]
        assert payload["pendencias"] == []

    def test_avaliacao_nao_altera_o_arquivo(self) -> None:
        antes = hashlib.sha256(VENDAS.read_bytes()).hexdigest()
        audit_presentation(VENDAS)
        assert hashlib.sha256(VENDAS.read_bytes()).hexdigest() == antes


# ============================================================
# Abas
# ============================================================


class TestAbas:
    def test_classifica_todas_as_abas(self) -> None:
        abas = survey_sheets(ATENDIMENTOS)
        naturezas = {info.name: info.kind for info in abas}
        assert naturezas == {
            "Janeiro": "dados",
            "Fevereiro": "dados",
            "Leia-me": "apresentacao",
            "Rascunho": "vazia",
        }

    def test_duas_candidatas_exigem_escolha(self) -> None:
        abas = survey_sheets(ATENDIMENTOS)
        assert needs_sheet_choice(abas) is True
        assert {c.name for c in candidates(abas)} == {"Janeiro", "Fevereiro"}

    def test_uma_candidata_nao_pergunta(self) -> None:
        assert needs_sheet_choice(survey_sheets(FINANCEIRO)) is False

    def test_cada_aba_explica_a_classificacao(self) -> None:
        assert all(info.reason for info in survey_sheets(ATENDIMENTOS))


# ============================================================
# Organização (formatação opcional e confirmada)
# ============================================================


class TestOrganizacao:
    def test_organizar_resolve_as_pendencias(self, tmp_path: Path) -> None:
        destino = tmp_path / "planilha_organizada.xlsx"
        organize_workbook(VENDAS, destino, sheet="Vendas")
        assert audit_presentation(destino, sheet="Vendas").verdict == "organizada"

    def test_cada_mudanca_e_registrada(self, tmp_path: Path) -> None:
        resultado = organize_workbook(VENDAS, tmp_path / "o.xlsx", sheet="Vendas")
        tipos = {mudanca.kind for mudanca in resultado.changes}
        assert {
            "cabecalho_formatado",
            "largura_ajustada",
            "filtro_aplicado",
            "painel_congelado",
        } <= tipos
        assert all(mudanca.detail for mudanca in resultado.changes)

    def test_valores_nao_mudam_na_organizacao(self, tmp_path: Path) -> None:
        destino = tmp_path / "o.xlsx"
        organize_workbook(VENDAS, destino, sheet="Vendas")

        antes = load_workbook(VENDAS)["Vendas"]
        depois = load_workbook(destino)["Vendas"]
        for linha in range(1, antes.max_row + 1):
            for coluna in range(1, antes.max_column + 1):
                assert (
                    antes.cell(row=linha, column=coluna).value
                    == depois.cell(row=linha, column=coluna).value
                )

    def test_formulas_sobrevivem(self, tmp_path: Path) -> None:
        destino = tmp_path / "o.xlsx"
        organize_workbook(ESTOQUE, destino, sheet="Estoque")
        assert str(load_workbook(destino)["Estoque"]["E2"].value).startswith("=")

    def test_zeros_a_esquerda_sobrevivem(self, tmp_path: Path) -> None:
        destino = tmp_path / "o.xlsx"
        organize_workbook(PUBLICO, destino, sheet="Protocolos")
        assert load_workbook(destino)["Protocolos"]["A2"].value == "000123"

    def test_original_nunca_e_sobrescrito(self, tmp_path: Path) -> None:
        antes = hashlib.sha256(VENDAS.read_bytes()).hexdigest()
        organize_workbook(VENDAS, tmp_path / "o.xlsx", sheet="Vendas")
        assert hashlib.sha256(VENDAS.read_bytes()).hexdigest() == antes

    def test_csv_nao_entra_no_organizador(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="xlsx"):
            organize_workbook(CLIENTES, tmp_path / "o.xlsx")

    def test_correcoes_confirmadas_sao_aplicadas(self, tmp_path: Path) -> None:
        destino = tmp_path / "o.xlsx"
        resultado = organize_workbook(
            PUBLICO,
            destino,
            sheet="Protocolos",
            value_changes=[{"line": 12, "column": "Assunto", "after": "Exame"}],
        )
        assert resultado.value_changes_applied == 1
        assert load_workbook(destino)["Protocolos"]["D12"].value == "Exame"


# ============================================================
# Ordenação
# ============================================================


class TestOrdenacao:
    def test_sem_confirmacao_a_ordem_e_preservada(self, tmp_path: Path) -> None:
        destino = tmp_path / "o.xlsx"
        organize_workbook(PUBLICO, destino, sheet="Protocolos")

        antes = [
            load_workbook(PUBLICO)["Protocolos"].cell(row=linha, column=1).value
            for linha in range(2, 8)
        ]
        depois = [
            load_workbook(destino)["Protocolos"].cell(row=linha, column=1).value
            for linha in range(2, 8)
        ]
        assert antes == depois

    def test_ordenacao_confirmada_e_aplicada(self, tmp_path: Path) -> None:
        destino = tmp_path / "o.xlsx"
        resultado = organize_workbook(
            PUBLICO, destino, sheet="Protocolos", sort=SortRequest("Dias", ascending=False)
        )
        ws = load_workbook(destino)["Protocolos"]
        dias = [ws.cell(row=linha, column=6).value for linha in range(2, 6)]

        assert dias == sorted(dias, reverse=True)
        assert "decrescente" in resultado.sorted_by

    def test_ordenacao_e_recusada_com_formulas(self, tmp_path: Path) -> None:
        """Reordenar quebraria o que cada fórmula aponta."""
        resultado = organize_workbook(
            ESTOQUE, tmp_path / "o.xlsx", sheet="Estoque", sort=SortRequest("SKU")
        )
        assert resultado.sorted_by == ""
        assert any("fórmula" in motivo for motivo in resultado.refusals)

    def test_coluna_inexistente_e_recusada(self, tmp_path: Path) -> None:
        resultado = organize_workbook(
            VENDAS, tmp_path / "o.xlsx", sheet="Vendas", sort=SortRequest("Fantasma")
        )
        assert resultado.sorted_by == ""
        assert any("não existe" in motivo for motivo in resultado.refusals)


# ============================================================
# Indicadores: nada de gráfico inventado
# ============================================================


def _frame(caminho: Path, sheet: str | None = None) -> tuple[pd.DataFrame, list[dict]]:
    leitura = read_workbook(caminho, sheet=sheet)
    assert leitura.original_dataframe is not None
    colunas = [{"name": c.name, "inferred_type": c.inferred_type} for c in leitura.detected_columns]
    return leitura.original_dataframe, colunas


class TestIndicadores:
    def test_sugere_papeis_com_confianca(self) -> None:
        frame, colunas = _frame(VENDAS, "Vendas")
        sugestoes = {s.column: s for s in suggest_roles(frame, colunas)}

        assert sugestoes["Data"].role == "data"
        assert sugestoes["Vendedor"].role == "categoria"
        assert sugestoes["Valor"].role in {"valor", "quantidade"}
        assert all(s.reason for s in sugestoes.values())

    def test_resumo_e_oferecido_quando_ha_dimensao_e_medida(self) -> None:
        frame, colunas = _frame(VENDAS, "Vendas")
        assert summary_is_offerable(suggest_roles(frame, colunas)) is True

    def test_nada_e_calculado_sem_confirmacao(self) -> None:
        """Um pedido vazio não produz número nenhum."""
        frame, _ = _frame(VENDAS, "Vendas")
        assert build_indicators(frame, IndicatorRequest(value_column="")) == ()

    def test_indicador_confirmado_soma_certo(self) -> None:
        frame, _ = _frame(VENDAS, "Vendas")
        pedido = IndicatorRequest(
            value_column="Valor", category_column="Vendedor", date_column="Data"
        )
        indicadores = build_indicators(frame, pedido)

        assert len(indicadores) == 2
        por_vendedor = indicadores[0]
        assert por_vendedor.dimension == "Vendedor"

        # A soma é conferida contra a própria coluna, não contra um número
        # decorado: assim o teste continua válido se a fixture crescer.
        esperado = sum(float(str(v).replace(",", ".")) for v in frame["Valor"])
        assert por_vendedor.total == pytest.approx(esperado)
        assert sum(valor for _, valor in por_vendedor.rows) == pytest.approx(esperado)

    def test_indicador_por_mes_agrupa_por_competencia(self) -> None:
        frame, _ = _frame(VENDAS, "Vendas")
        pedido = IndicatorRequest(value_column="Valor", date_column="Data")
        (por_mes,) = build_indicators(frame, pedido)

        assert por_mes.dimension == "mês"
        assert [chave for chave, _ in por_mes.rows] == ["2026-01", "2026-02", "2026-03"]

    def test_coluna_de_valor_inexistente_nao_inventa(self) -> None:
        frame, _ = _frame(VENDAS, "Vendas")
        pedido = IndicatorRequest(value_column="Fantasma", category_column="Vendedor")
        assert build_indicators(frame, pedido) == ()

    def test_dominio_publico_tambem_e_suportado(self) -> None:
        frame, colunas = _frame(PUBLICO, "Protocolos")
        sugestoes = {s.column: s.role for s in suggest_roles(frame, colunas)}
        assert sugestoes["Orgao"] == "categoria"
        assert sugestoes["Abertura"] == "data"


# ============================================================
# Relatório de análise
# ============================================================


class TestRelatorio:
    def _entrada(self, **extra) -> ReportInput:
        return ReportInput(
            source_name=VENDAS.name,
            sheet="Vendas",
            rows=20,
            columns=6,
            audit=audit_presentation(VENDAS),
            sheets=survey_sheets(VENDAS),
            **extra,
        )

    def test_gera_o_arquivo_com_o_resumo(self, tmp_path: Path) -> None:
        destino = write_analysis_report(tmp_path / ANALYSIS_REPORT_NAME, self._entrada())
        wb = load_workbook(destino)

        assert "Resumo" in wb.sheetnames
        texto = "\n".join(
            str(v) for linha in wb["Resumo"].iter_rows(values_only=True) for v in linha if v
        )
        assert "pode ser melhorada" in texto
        assert VENDAS.name in texto

    def test_abas_vazias_nao_sao_escritas(self, tmp_path: Path) -> None:
        destino = write_analysis_report(tmp_path / "r.xlsx", self._entrada())
        wb = load_workbook(destino)
        assert "Antes e depois" not in wb.sheetnames

    def test_antes_e_depois_registra_valor_anterior_e_posterior(self, tmp_path: Path) -> None:
        entrada = self._entrada(
            cleaning_changes=[
                {
                    "line": 5,
                    "column": "Vendedor",
                    "before": "  Ana  ",
                    "after": "Ana",
                    "rules": ["espacos"],
                }
            ]
        )
        destino = write_analysis_report(tmp_path / "r.xlsx", entrada)
        ws = load_workbook(destino)["Antes e depois"]

        assert [c.value for c in ws[1]] == [
            "linha",
            "coluna",
            "valor anterior",
            "valor posterior",
            "tipo da alteração",
            "motivo",
        ]
        assert [c.value for c in ws[2]][:4] == [5, "Vendedor", "  Ana  ", "Ana"]

    def test_alteracoes_visuais_ficam_registradas(self, tmp_path: Path) -> None:
        resultado = organize_workbook(VENDAS, tmp_path / "o.xlsx", sheet="Vendas")
        destino = write_analysis_report(tmp_path / "r.xlsx", self._entrada(organize=resultado))
        ws = load_workbook(destino)["Alteracoes realizadas"]
        tipos = {linha[1] for linha in ws.iter_rows(min_row=2, values_only=True)}

        assert "filtro_aplicado" in tipos
        assert "cabecalho_formatado" in tipos

    def test_indicadores_so_aparecem_quando_confirmados(self, tmp_path: Path) -> None:
        sem = write_analysis_report(tmp_path / "sem.xlsx", self._entrada())
        assert "Indicadores confirmados" not in load_workbook(sem).sheetnames

        frame, _ = _frame(VENDAS, "Vendas")
        indicadores = build_indicators(
            frame, IndicatorRequest(value_column="Valor", category_column="Vendedor")
        )
        com = write_analysis_report(tmp_path / "com.xlsx", self._entrada(indicators=indicadores))
        wb = load_workbook(com)
        assert "Indicadores confirmados" in wb.sheetnames
        assert wb["Indicadores confirmados"]._charts  # o gráfico foi criado

    def test_abas_do_arquivo_listam_a_classificacao(self, tmp_path: Path) -> None:
        entrada = ReportInput(
            source_name=ATENDIMENTOS.name,
            sheet="Janeiro",
            sheets=survey_sheets(ATENDIMENTOS),
        )
        destino = write_analysis_report(tmp_path / "r.xlsx", entrada)
        ws = load_workbook(destino)["Abas do arquivo"]
        naturezas = {linha[0]: linha[1] for linha in ws.iter_rows(min_row=2, values_only=True)}

        assert naturezas["Rascunho"] == "vazia"
        assert naturezas["Leia-me"] == "apresentacao"


def test_fixtures_de_dominio_existem() -> None:
    for caminho in (
        VENDAS,
        FINANCEIRO,
        PUBLICO,
        ESTOQUE,
        CLIENTES,
        PESQUISA,
        ATENDIMENTOS,
        CONTRATOS,
    ):
        assert caminho.is_file(), caminho
