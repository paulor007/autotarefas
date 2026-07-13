"""Testes da deteccao de tabela (aba e cabecalho) — tudo estrutural."""

from __future__ import annotations

from autotarefas.reader.table_detect import (
    MIN_SHEET_SCORE,
    find_header_row,
    looks_like_footer,
    score_sheet,
)
from autotarefas.reader.types import RawCell


def _grid(linhas: list[list[object]]) -> list[list[RawCell]]:
    largura = max((len(r) for r in linhas), default=0)
    return [[RawCell(value=(r[i] if i < len(r) else None)) for i in range(largura)] for r in linhas]


TABELA_LIMPA = _grid(
    [
        ["produto", "quantidade", "valor"],
        ["Camisa", "2", "100"],
        ["Calca", "1", "150"],
        ["Meia", "3", "20"],
    ]
)


class TestScoreSheet:
    def test_tabela_limpa_pontua_alto(self) -> None:
        score, _ = score_sheet(TABELA_LIMPA)
        assert score > MIN_SHEET_SCORE

    def test_aba_vazia_pontua_zero(self) -> None:
        score, motivo = score_sheet([])
        assert score == 0.0
        assert "vazia" in motivo

    def test_aba_esparsa_pontua_baixo(self) -> None:
        # celulas espalhadas (cara de painel, nao de tabela)
        # painel de verdade: as celulas preenchidas MUDAM DE LUGAR a cada linha
        esparsa = _grid(
            [
                ["PAINEL EXECUTIVO", None, None, None, None, None],
                [None, None, None, None, None, "Observacoes"],
                ["Faturamento", None, "1240000", None, None, None],
                [None, None, None, None, None, "Fechamento parcial"],
                ["Margem", None, "18%", None, None, None],
            ]
        )
        score, _ = score_sheet(esparsa)
        assert score < MIN_SHEET_SCORE


class TestFindHeaderRow:
    def test_cabecalho_na_primeira_linha(self) -> None:
        idx, conf, _ = find_header_row(TABELA_LIMPA)
        assert idx == 0
        assert conf > 0.5

    def test_cabecalho_apos_linhas_de_titulo(self) -> None:
        grid = _grid(
            [
                ["Relatorio de Vendas"],
                ["Gerado em 01/12/2019"],
                [],
                ["produto", "quantidade", "valor"],
                ["Camisa", "2", "100"],
                ["Calca", "1", "150"],
                ["Meia", "3", "20"],
            ]
        )
        idx, conf, _ = find_header_row(grid)
        assert idx == 3  # 0-based -> linha fisica 4
        assert conf > 0.5

    def test_grid_vazio(self) -> None:
        idx, conf, alts = find_header_row([])
        assert idx is None
        assert conf == 0.0
        assert alts == []


class TestLooksLikeFooter:
    def test_linha_de_total_e_detectada(self) -> None:
        grid = _grid(
            [
                ["produto", "quantidade", "valor"],
                ["Camisa", "2", "100"],
                ["TOTAL", "2", "100"],
            ]
        )
        assert looks_like_footer(grid, 2, n_cols=3) is True

    def test_linha_normal_nao_e_rodape(self) -> None:
        assert looks_like_footer(TABELA_LIMPA, 1, n_cols=3) is False

    def test_linha_esparsa_com_numero_e_suspeita(self) -> None:
        grid = _grid(
            [
                ["produto", "quantidade", "valor"],
                ["Camisa", "2", "100"],
                [None, None, "100"],
            ]
        )
        assert looks_like_footer(grid, 2, n_cols=3) is True
