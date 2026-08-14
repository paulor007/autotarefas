"""
Testes do comando `autotarefas transferir` sobre as fixtures reais (RF-REC-003).

Estes testes fecham o requisito de ponta a ponta: dois arquivos XLSX de
verdade entram, uma planilha enriquecida e as evidencias saem — e o
arquivo de destino continua byte a byte o mesmo.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from autotarefas.cli.commands.transferir import transferir
from autotarefas.cli.context import CLIContext
from autotarefas.reconcile.transfer_artifacts import (
    ENRICHED_CSV_NAME,
    ENRICHED_XLSX_NAME,
    JSON_REPORT_NAME,
    NOT_FOUND_CSV_NAME,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "transferencia"
DESTINO = FIXTURES / "destino_cadastro.xlsx"
FONTE = FIXTURES / "fonte_contatos.xlsx"


@pytest.fixture
def cli_ctx() -> CLIContext:
    return CLIContext()


def _run(args: list[str], ctx: CLIContext):
    return CliRunner().invoke(transferir, args, obj=ctx)


def _base_args(*extra: str) -> list[str]:
    return [
        str(DESTINO),
        "--de",
        str(FONTE),
        "--chave",
        "codigo",
        "--campo",
        "email",
        "--campo",
        "telefone",
        *extra,
    ]


class TestExecucao:
    def test_exit_0_e_resumo(self, cli_ctx: CLIContext) -> None:
        result = _run(_base_args(), cli_ctx)
        assert result.exit_code == 0
        assert "Campos preenchidos" in result.output
        assert "'bruno@antigo.com'  ->  'bruno@empresa.com'" in result.output

    def test_campo_obrigatorio(self, cli_ctx: CLIContext) -> None:
        result = _run([str(DESTINO), "--de", str(FONTE), "--chave", "codigo"], cli_ctx)
        assert result.exit_code == 2

    def test_campo_inexistente_e_erro_de_uso(self, cli_ctx: CLIContext) -> None:
        result = _run(
            [str(DESTINO), "--de", str(FONTE), "--chave", "codigo", "--campo", "fantasma"],
            cli_ctx,
        )
        assert result.exit_code == 2

    def test_falhar_se_nao_encontrado_sai_1(self, cli_ctx: CLIContext) -> None:
        result = _run(_base_args("--falhar-se-nao-encontrado"), cli_ctx)
        assert result.exit_code == 1


class TestArtefatos:
    def test_gera_os_quatro_artefatos(self, cli_ctx: CLIContext, tmp_path: Path) -> None:
        result = _run(_base_args("--out-dir", str(tmp_path)), cli_ctx)
        assert result.exit_code == 0
        for nome in (
            ENRICHED_XLSX_NAME,
            ENRICHED_CSV_NAME,
            NOT_FOUND_CSV_NAME,
            JSON_REPORT_NAME,
        ):
            assert (tmp_path / nome).exists(), nome

    def test_planilha_enriquecida_tem_os_valores_da_fonte(
        self, cli_ctx: CLIContext, tmp_path: Path
    ) -> None:
        _run(_base_args("--out-dir", str(tmp_path)), cli_ctx)
        base = pd.read_csv(tmp_path / ENRICHED_CSV_NAME, dtype=str).fillna("")

        assert base.loc[base["codigo"] == "00123", "email"].item() == "ana@empresa.com"
        assert base.loc[base["codigo"] == "00124", "telefone"].item() == "(21) 3344-5566"

    def test_coluna_nao_autorizada_fica_intacta(self, cli_ctx: CLIContext, tmp_path: Path) -> None:
        _run(_base_args("--out-dir", str(tmp_path)), cli_ctx)
        base = pd.read_csv(tmp_path / ENRICHED_CSV_NAME, dtype=str).fillna("")

        # a fonte tem "Ana L."; o destino mantem "Ana Lima"
        assert base.loc[base["codigo"] == "00123", "nome"].item() == "Ana Lima"

    def test_nao_encontrados_traz_a_chave_buscada(
        self, cli_ctx: CLIContext, tmp_path: Path
    ) -> None:
        _run(_base_args("--out-dir", str(tmp_path)), cli_ctx)
        nao_encontrados = pd.read_csv(tmp_path / NOT_FOUND_CSV_NAME, dtype=str)
        assert list(nao_encontrados["codigo"]) == ["00129"]

    def test_marcar_origem(self, cli_ctx: CLIContext, tmp_path: Path) -> None:
        _run(_base_args("--marcar-origem", "--out-dir", str(tmp_path)), cli_ctx)
        base = pd.read_csv(tmp_path / ENRICHED_CSV_NAME, dtype=str).fillna("")

        assert "_origem_email" in base.columns
        assert base.loc[base["codigo"] == "00123", "_origem_email"].item() == "fonte_contatos.xlsx"

    def test_relatorio_json(self, cli_ctx: CLIContext, tmp_path: Path) -> None:
        _run(_base_args("--out-dir", str(tmp_path)), cli_ctx)
        payload = json.loads((tmp_path / JSON_REPORT_NAME).read_text(encoding="utf-8"))

        assert payload["requisito"] == "RF-REC-003"
        assert payload["task_name"] == "transferir"
        assert payload["politica"]["campos_autorizados"] == ["email", "telefone"]
        assert payload["resumo"]["preenchidos"] == 2
        assert payload["resumo"]["atualizados"] == 1
        assert payload["nao_encontrados"][0]["chave"] == {"codigo": "00129"}

    def test_dry_run_nao_grava(self, tmp_path: Path) -> None:
        destino = tmp_path / "saida"
        result = _run(_base_args("--out-dir", str(destino)), CLIContext(dry_run=True))
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output
        assert not destino.exists()

    def test_somente_vazios_preserva_o_destino(self, cli_ctx: CLIContext, tmp_path: Path) -> None:
        _run(_base_args("--somente-vazios", "--out-dir", str(tmp_path)), cli_ctx)
        base = pd.read_csv(tmp_path / ENRICHED_CSV_NAME, dtype=str).fillna("")
        assert base.loc[base["codigo"] == "00124", "email"].item() == "bruno@antigo.com"


def test_arquivos_de_entrada_ficam_intocados(cli_ctx: CLIContext, tmp_path: Path) -> None:
    antes = (
        hashlib.sha256(DESTINO.read_bytes()).hexdigest(),
        hashlib.sha256(FONTE.read_bytes()).hexdigest(),
    )
    _run(_base_args("--out-dir", str(tmp_path)), cli_ctx)
    depois = (
        hashlib.sha256(DESTINO.read_bytes()).hexdigest(),
        hashlib.sha256(FONTE.read_bytes()).hexdigest(),
    )
    assert antes == depois


def test_comando_registrado_na_cli() -> None:
    from autotarefas.cli.main import cli

    assert "transferir" in cli.commands
