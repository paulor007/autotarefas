"""Testes para o comando CLI `autotarefas conciliar` (RF-REC-002)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from autotarefas.cli.commands.conciliar import conciliar
from autotarefas.cli.context import CLIContext
from autotarefas.reconcile.merge_artifacts import (
    BASE_CSV_NAME,
    BASE_XLSX_NAME,
    JSON_REPORT_NAME,
    REVIEW_XLSX_NAME,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "comparacao"
BASE_A = str(FIXTURES / "base_a.xlsx")
BASE_B = str(FIXTURES / "base_b.xlsx")


@pytest.fixture
def cli_ctx() -> CLIContext:
    return CLIContext()


@pytest.fixture
def cli_ctx_dry_run() -> CLIContext:
    return CLIContext(dry_run=True)


def _run(args: list[str], ctx: CLIContext):
    return CliRunner().invoke(conciliar, args, obj=ctx)


class TestExecucao:
    def test_exit_0_com_pendencias(self, cli_ctx: CLIContext) -> None:
        """Caso para revisao nao e falha de execucao — e trabalho para uma pessoa."""
        result = _run([BASE_A, BASE_B, "--chave", "codigo"], cli_ctx)
        assert result.exit_code == 0

    def test_resumo_mostra_politica(self, cli_ctx: CLIContext) -> None:
        result = _run([BASE_A, BASE_B, "--chave", "codigo", "--atualizar", "valor"], cli_ctx)
        assert "fonte principal: A" in result.output
        assert "campos atualizaveis: valor" in result.output

    def test_atualizacao_autorizada_aparece(self, cli_ctx: CLIContext) -> None:
        result = _run([BASE_A, BASE_B, "--chave", "codigo", "--atualizar", "valor"], cli_ctx)
        assert "'250,00'  ->  '275,00'" in result.output

    def test_tolerancia_invalida_e_erro_de_uso(self, cli_ctx: CLIContext) -> None:
        result = _run([BASE_A, BASE_B, "--chave", "codigo", "--tolerancia", "valor"], cli_ctx)
        assert result.exit_code == 2
        assert "tolerancia invalida" in result.output

    def test_chave_inexistente_e_erro_de_uso(self, cli_ctx: CLIContext) -> None:
        result = _run([BASE_A, BASE_B, "--chave", "fantasma"], cli_ctx)
        assert result.exit_code == 2


class TestArtefatos:
    def test_gera_os_artefatos(self, cli_ctx: CLIContext, tmp_path: Path) -> None:
        result = _run(
            [
                BASE_A,
                BASE_B,
                "--chave",
                "codigo",
                "--atualizar",
                "valor",
                "--out-dir",
                str(tmp_path),
            ],
            cli_ctx,
        )
        assert result.exit_code == 0
        for nome in (BASE_XLSX_NAME, BASE_CSV_NAME, REVIEW_XLSX_NAME, JSON_REPORT_NAME):
            assert (tmp_path / nome).exists(), nome

    def test_base_conciliada_tem_o_valor_autorizado(
        self, cli_ctx: CLIContext, tmp_path: Path
    ) -> None:
        _run(
            [
                BASE_A,
                BASE_B,
                "--chave",
                "codigo",
                "--atualizar",
                "valor",
                "--out-dir",
                str(tmp_path),
            ],
            cli_ctx,
        )
        base = pd.read_csv(tmp_path / BASE_CSV_NAME, dtype=str)
        linha = base.loc[base["codigo"] == "00124"]
        assert linha["valor"].item() == "275,00"

    def test_relatorio_tem_metadados(self, cli_ctx: CLIContext, tmp_path: Path) -> None:
        _run([BASE_A, BASE_B, "--chave", "codigo", "--out-dir", str(tmp_path)], cli_ctx)
        payload = json.loads((tmp_path / JSON_REPORT_NAME).read_text(encoding="utf-8"))
        assert payload["task_name"] == "conciliar"
        assert payload["status"] == "success"

    def test_dry_run_nao_grava(self, cli_ctx_dry_run: CLIContext, tmp_path: Path) -> None:
        destino = tmp_path / "saida"
        result = _run(
            [BASE_A, BASE_B, "--chave", "codigo", "--out-dir", str(destino)], cli_ctx_dry_run
        )
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output
        assert not destino.exists()


class TestPoliticas:
    def test_revisar_novos_tira_o_registro_da_base(
        self, cli_ctx: CLIContext, tmp_path: Path
    ) -> None:
        _run(
            [
                BASE_A,
                BASE_B,
                "--chave",
                "codigo",
                "--revisar-novos",
                "--out-dir",
                str(tmp_path),
            ],
            cli_ctx,
        )
        base = pd.read_csv(tmp_path / BASE_CSV_NAME, dtype=str)
        assert "00128" not in list(base["codigo"])

    def test_principal_b_inverte_a_base(self, cli_ctx: CLIContext, tmp_path: Path) -> None:
        _run(
            [
                BASE_A,
                BASE_B,
                "--chave",
                "codigo",
                "--principal",
                "b",
                "--out-dir",
                str(tmp_path),
            ],
            cli_ctx,
        )
        base = pd.read_csv(tmp_path / BASE_CSV_NAME, dtype=str)
        assert base.loc[base["codigo"] == "00124", "valor"].item() == "275,00"

    def test_falhar_se_revisao_sai_1(self, cli_ctx: CLIContext) -> None:
        result = _run([BASE_A, BASE_B, "--chave", "codigo", "--falhar-se-revisao"], cli_ctx)
        assert result.exit_code == 1

    def test_sem_pendencias_sai_0_e_avisa(self, cli_ctx: CLIContext) -> None:
        result = _run([BASE_A, BASE_A, "--chave", "codigo", "--falhar-se-revisao"], cli_ctx)
        assert result.exit_code == 0
        assert "sem pendencias" in result.output


def test_comando_registrado_na_cli() -> None:
    from autotarefas.cli.main import cli

    assert "conciliar" in cli.commands
