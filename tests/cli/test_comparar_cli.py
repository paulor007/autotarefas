"""Testes para o comando CLI `autotarefas comparar` (RF-REC-001)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from autotarefas.cli.commands.comparar import comparar
from autotarefas.cli.context import CLIContext
from autotarefas.reconcile.artifacts import (
    JSON_REPORT_NAME,
    ONLY_A_CSV_NAME,
    ONLY_B_CSV_NAME,
    XLSX_NAME,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "comparacao"
BASE_A = str(FIXTURES / "base_a.xlsx")
BASE_B = str(FIXTURES / "base_b.xlsx")
BASE_B_CSV = str(FIXTURES / "base_b.csv")


@pytest.fixture
def cli_ctx() -> CLIContext:
    return CLIContext()


@pytest.fixture
def cli_ctx_dry_run() -> CLIContext:
    return CLIContext(dry_run=True)


class TestExecucaoBasica:
    def test_exit_0_mesmo_com_diferencas(self, cli_ctx: CLIContext) -> None:
        """Diferenca nao e falha: e a resposta que o usuario pediu."""
        result = CliRunner().invoke(comparar, [BASE_A, BASE_B, "--chave", "codigo"], obj=cli_ctx)
        assert result.exit_code == 0

    def test_resumo_no_terminal(self, cli_ctx: CLIContext) -> None:
        result = CliRunner().invoke(comparar, [BASE_A, BASE_B, "--chave", "codigo"], obj=cli_ctx)
        assert "Comparacao por chave: codigo" in result.output
        assert "Divergentes" in result.output
        assert "Conflitos de chave" in result.output

    def test_compara_xlsx_com_csv(self, cli_ctx: CLIContext) -> None:
        result = CliRunner().invoke(
            comparar, [BASE_A, BASE_B_CSV, "--chave", "codigo"], obj=cli_ctx
        )
        assert result.exit_code == 0
        assert "base_b.csv" in result.output

    def test_bases_equivalentes(self, cli_ctx: CLIContext) -> None:
        result = CliRunner().invoke(comparar, [BASE_A, BASE_A, "--chave", "codigo"], obj=cli_ctx)
        assert result.exit_code == 0
        assert "equivalentes" in result.output

    def test_normalizar_reduz_divergencias(self, cli_ctx: CLIContext) -> None:
        sem = CliRunner().invoke(comparar, [BASE_A, BASE_B, "--chave", "codigo"], obj=cli_ctx)
        com = CliRunner().invoke(
            comparar,
            [
                BASE_A,
                BASE_B,
                "--chave",
                "codigo",
                "--normalizar",
                "espacos",
                "--normalizar",
                "caixa",
            ],
            obj=cli_ctx,
        )
        assert "2 divergente(s)" in sem.output
        assert "1 divergente(s)" in com.output

    def test_tolerancia_absorve_a_diferenca_de_centavos(
        self, cli_ctx: CLIContext, tmp_path: Path
    ) -> None:
        """Um centavo de arredondamento nao pode virar divergencia (REC-002)."""
        a = tmp_path / "a.csv"
        b = tmp_path / "b.csv"
        a.write_text("codigo,valor\n1,1000.00\n", encoding="utf-8")
        b.write_text("codigo,valor\n1,1000.01\n", encoding="utf-8")

        result = CliRunner().invoke(
            comparar,
            [str(a), str(b), "--chave", "codigo", "--tolerancia", "valor=0,01"],
            obj=cli_ctx,
        )
        assert result.exit_code == 0
        assert "equivalentes" in result.output
        assert "Toleradas" in result.output

    def test_tolerancia_invalida_e_erro_de_uso(self, cli_ctx: CLIContext) -> None:
        result = CliRunner().invoke(
            comparar,
            [BASE_A, BASE_B, "--chave", "codigo", "--tolerancia", "valor"],
            obj=cli_ctx,
        )
        assert result.exit_code == 2

    def test_coluna_restringe_a_comparacao(self, cli_ctx: CLIContext) -> None:
        result = CliRunner().invoke(
            comparar,
            [BASE_A, BASE_B, "--chave", "codigo", "--coluna", "cidade"],
            obj=cli_ctx,
        )
        assert "Colunas comparadas: cidade" in result.output
        assert "0 divergente(s)" in result.output


class TestArtefatos:
    def test_out_dir_gera_os_quatro_arquivos(self, cli_ctx: CLIContext, tmp_path: Path) -> None:
        result = CliRunner().invoke(
            comparar,
            [BASE_A, BASE_B, "--chave", "codigo", "--out-dir", str(tmp_path)],
            obj=cli_ctx,
        )
        assert result.exit_code == 0
        for nome in (JSON_REPORT_NAME, XLSX_NAME, ONLY_A_CSV_NAME, ONLY_B_CSV_NAME):
            assert (tmp_path / nome).exists(), nome

    def test_relatorio_tem_metadados_da_execucao(self, cli_ctx: CLIContext, tmp_path: Path) -> None:
        CliRunner().invoke(
            comparar,
            [BASE_A, BASE_B, "--chave", "codigo", "--out-dir", str(tmp_path)],
            obj=cli_ctx,
        )
        payload = json.loads((tmp_path / JSON_REPORT_NAME).read_text(encoding="utf-8"))
        assert payload["task_name"] == "comparar"
        assert payload["status"] == "success"
        assert payload["resumo"]["conflitos"] == 1

    def test_dry_run_nao_grava(self, cli_ctx_dry_run: CLIContext, tmp_path: Path) -> None:
        destino = tmp_path / "saida"
        result = CliRunner().invoke(
            comparar,
            [BASE_A, BASE_B, "--chave", "codigo", "--out-dir", str(destino)],
            obj=cli_ctx_dry_run,
        )
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output
        assert not destino.exists()


class TestCodigosDeSaida:
    def test_falhar_se_diferente_sai_1(self, cli_ctx: CLIContext) -> None:
        result = CliRunner().invoke(
            comparar,
            [BASE_A, BASE_B, "--chave", "codigo", "--falhar-se-diferente"],
            obj=cli_ctx,
        )
        assert result.exit_code == 1

    def test_falhar_se_diferente_sai_0_com_bases_iguais(self, cli_ctx: CLIContext) -> None:
        result = CliRunner().invoke(
            comparar,
            [BASE_A, BASE_A, "--chave", "codigo", "--falhar-se-diferente"],
            obj=cli_ctx,
        )
        assert result.exit_code == 0

    def test_chave_inexistente_e_erro_de_uso(self, cli_ctx: CLIContext) -> None:
        result = CliRunner().invoke(comparar, [BASE_A, BASE_B, "--chave", "fantasma"], obj=cli_ctx)
        assert result.exit_code == 2

    def test_chave_obrigatoria(self, cli_ctx: CLIContext) -> None:
        result = CliRunner().invoke(comparar, [BASE_A, BASE_B], obj=cli_ctx)
        assert result.exit_code == 2

    def test_arquivo_inexistente(self, cli_ctx: CLIContext, tmp_path: Path) -> None:
        result = CliRunner().invoke(
            comparar,
            [BASE_A, str(tmp_path / "sumiu.xlsx"), "--chave", "codigo"],
            obj=cli_ctx,
        )
        assert result.exit_code == 2

    def test_normalizacao_invalida_e_rejeitada_pelo_click(self, cli_ctx: CLIContext) -> None:
        result = CliRunner().invoke(
            comparar,
            [BASE_A, BASE_B, "--chave", "codigo", "--normalizar", "arredondar"],
            obj=cli_ctx,
        )
        assert result.exit_code == 2


def test_comando_registrado_na_cli() -> None:
    from autotarefas.cli.main import cli

    assert "comparar" in cli.commands
