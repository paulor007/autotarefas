"""Testes dos contratos do leitor (result.py)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from autotarefas.reader.result import (
    ColumnInfo,
    Conversion,
    ReadWarning,
    SheetCandidate,
    WorkbookReadResult,
)


def _coluna(nome: str, tipo: str = "texto") -> ColumnInfo:
    return ColumnInfo(index=0, name=nome, inferred_type=tipo, type_confidence=1.0)  # type: ignore[arg-type]


class TestWorkbookReadResult:
    def test_ok_quando_nao_ha_recusa(self) -> None:
        r = WorkbookReadResult(source_file=Path("x.csv"), file_type="csv")
        assert r.ok is True

    def test_nao_ok_quando_recusado(self) -> None:
        r = WorkbookReadResult(
            source_file=Path("x.xlsx"),
            file_type="xlsx",
            rejected_reason="nao parece tabular",
        )
        assert r.ok is False

    def test_row_count_sem_dataframe(self) -> None:
        r = WorkbookReadResult(source_file=Path("x.csv"), file_type="csv")
        assert r.row_count == 0

    def test_row_count_com_dataframe(self) -> None:
        r = WorkbookReadResult(
            source_file=Path("x.csv"),
            file_type="csv",
            original_dataframe=pd.DataFrame({"a": ["1", "2", "3"]}),
        )
        assert r.row_count == 3

    def test_busca_coluna_por_nome(self) -> None:
        r = WorkbookReadResult(
            source_file=Path("x.csv"),
            file_type="csv",
            detected_columns=[_coluna("nome"), _coluna("idade", "inteiro")],
        )
        achada = r.column("idade")
        assert achada is not None
        assert achada.inferred_type == "inteiro"
        assert r.column("inexistente") is None


class TestContratosAuxiliares:
    def test_conversion_guarda_a_trilha(self) -> None:
        c = Conversion(
            row=5, column="preco", original="R$ 1.234,56", normalized="1234.56", rule="moeda_br"
        )
        assert c.row == 5
        assert c.rule == "moeda_br"

    def test_warning_pode_apontar_linha_e_coluna(self) -> None:
        w = ReadWarning(code="coluna_mista", message="tipos misturados", column="qtd")
        assert w.column == "qtd"
        assert w.row is None

    def test_sheet_candidate_tem_score_e_motivo(self) -> None:
        s = SheetCandidate(name="Plan1", score=0.9, reason="denso e regular", rows=10, cols=3)
        assert s.score == 0.9
        assert s.rows == 10

    def test_column_info_guarda_observacoes_sem_concluir(self) -> None:
        col = ColumnInfo(
            index=0,
            name="codigo",
            inferred_type="inteiro",
            type_confidence=1.0,
            observations=["possivel identificador (alta cardinalidade)"],
        )
        # "possivel" — o leitor OBSERVA, nao conclui
        assert "possivel" in col.observations[0]
        assert col.inferred_type == "inteiro"
