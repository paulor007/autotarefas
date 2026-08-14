"""
Testes da `ComparisonTask` sobre as fixtures plantadas (RF-REC-001).

Aqui a comparacao passa pelo leitor de verdade: arquivos XLSX e CSV, com
zeros a esquerda, chave repetida e registro novo/removido. E o teste que
prova o criterio de aceite da ficha — classificacao 100% correta e fontes
intocadas.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from autotarefas.reconcile.task import ComparisonTask, SourceSelection

FIXTURES = Path(__file__).parent.parent / "fixtures" / "comparacao"
BASE_A = FIXTURES / "base_a.xlsx"
BASE_B = FIXTURES / "base_b.xlsx"
BASE_B_CSV = FIXTURES / "base_b.csv"


def _rodar(
    arquivo_a: Path = BASE_A,
    arquivo_b: Path = BASE_B,
    **kwargs: object,
) -> ComparisonTask:
    task = ComparisonTask(
        SourceSelection(path=arquivo_a),
        SourceSelection(path=arquivo_b),
        key_columns=kwargs.pop("key_columns", ("codigo",)),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )
    task.run()
    return task


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestCasosPlantados:
    def test_classificacao_das_fixtures(self) -> None:
        task = _rodar()
        assert task.comparison is not None
        assert task.comparison.counts == {
            "identico": 1,  # 00123
            "divergente": 2,  # 00124 (valor) e 00127 (espacos/caixa)
            "somente_a": 1,  # 00125 removido em B
            "somente_b": 1,  # 00128 novo em B
            "conflitos": 1,  # 00126 repetido em B
        }

    def test_zeros_a_esquerda_sobrevivem_na_chave(self) -> None:
        task = _rodar()
        assert task.comparison is not None
        chaves = {r.key[0] for r in task.comparison.records}
        assert "00123" in chaves

    def test_divergencia_de_uma_coluna(self) -> None:
        task = _rodar()
        assert task.comparison is not None
        (registro,) = [r for r in task.comparison.by_category("divergente") if r.key == ("00124",)]
        assert [(d.column, d.value_a, d.value_b) for d in registro.differences] == [
            ("valor", "250,00", "275,00")
        ]

    def test_normalizacao_resolve_a_divergencia_de_forma(self) -> None:
        task = _rodar(normalizations=("espacos", "caixa"))
        assert task.comparison is not None
        assert task.comparison.counts["divergente"] == 1

    def test_xlsx_contra_csv_da_o_mesmo_resultado(self) -> None:
        so_xlsx = _rodar()
        com_csv = _rodar(arquivo_b=BASE_B_CSV)
        assert so_xlsx.comparison is not None
        assert com_csv.comparison is not None
        assert so_xlsx.comparison.counts == com_csv.comparison.counts

    def test_conflito_aponta_as_duas_linhas_repetidas(self) -> None:
        task = _rodar()
        assert task.comparison is not None
        (conflito,) = task.comparison.conflicts
        assert conflito.key == ("00126",)
        assert conflito.rows_b == (4, 5)


class TestResultadoDaTask:
    def test_status_de_sucesso_mesmo_com_diferencas(self) -> None:
        """Base diferente nao e falha de execucao: e o resultado do trabalho."""
        task = ComparisonTask(
            SourceSelection(path=BASE_A),
            SourceSelection(path=BASE_B),
            key_columns=("codigo",),
        )
        result = task.run()
        assert result.is_success
        assert result.rows_affected == 5

    def test_data_carrega_o_relatorio_completo(self) -> None:
        task = ComparisonTask(
            SourceSelection(path=BASE_A),
            SourceSelection(path=BASE_B),
            key_columns=("codigo",),
        )
        result = task.run()
        assert result.data["requisito"] == "RF-REC-001"
        assert result.data["resumo"]["divergente"] == 2
        assert result.data["limitacoes"]

    def test_fontes_ficam_intocadas(self) -> None:
        antes = (_sha256(BASE_A), _sha256(BASE_B))
        _rodar()
        assert (_sha256(BASE_A), _sha256(BASE_B)) == antes


class TestFalhas:
    def test_chave_inexistente_vira_falha_com_motivo(self) -> None:
        task = ComparisonTask(
            SourceSelection(path=BASE_A),
            SourceSelection(path=BASE_B),
            key_columns=("nao_existe",),
        )
        result = task.run()
        assert result.is_failure
        assert result.error_type == "CompareError"
        assert "nao_existe" in str(result.error_message)

    def test_arquivo_recusado_pelo_leitor(self, tmp_path: Path) -> None:
        ruim = tmp_path / "nao_tabular.txt"
        ruim.write_text("isto nao e uma planilha", encoding="utf-8")

        task = ComparisonTask(
            SourceSelection(path=BASE_A),
            SourceSelection(path=ruim),
            key_columns=("codigo",),
        )
        result = task.run()
        assert result.is_failure
        assert "fonte B" in str(result.error_message)

    def test_arquivo_inexistente(self, tmp_path: Path) -> None:
        task = ComparisonTask(
            SourceSelection(path=tmp_path / "sumiu.xlsx"),
            SourceSelection(path=BASE_B),
            key_columns=("codigo",),
        )
        result = task.run()
        assert result.is_failure
        assert "fonte A" in str(result.error_message)

    def test_xlsx_corrompido(self, tmp_path: Path) -> None:
        falso = tmp_path / "corrompido.xlsx"
        falso.write_bytes(b"isto nao e um zip")

        task = ComparisonTask(
            SourceSelection(path=falso),
            SourceSelection(path=BASE_B),
            key_columns=("codigo",),
        )
        result = task.run()
        assert result.is_failure
        assert "corrompido" in str(result.error_message)


class TestSelecaoDeAbaECabecalho:
    def test_aba_inexistente_e_erro_de_uso(self) -> None:
        task = ComparisonTask(
            SourceSelection(path=BASE_A, sheet="Inexistente"),
            SourceSelection(path=BASE_B),
            key_columns=("codigo",),
        )
        result = task.run()
        assert result.is_failure
        assert "fonte A" in str(result.error_message)

    def test_cabecalho_explicito_e_respeitado(self) -> None:
        task = ComparisonTask(
            SourceSelection(path=BASE_A, sheet="Plan1", header_row=1),
            SourceSelection(path=BASE_B, header_row=1),
            key_columns=("codigo",),
        )
        result = task.run()
        assert result.is_success
        assert task.table_a is not None
        assert task.table_a.first_data_row == 2


@pytest.mark.parametrize("fixture", [BASE_A, BASE_B, BASE_B_CSV])
def test_fixtures_existem(fixture: Path) -> None:
    """As fixtures sao versionadas: sem elas, os testes acima nao provam nada."""
    assert fixture.exists()
