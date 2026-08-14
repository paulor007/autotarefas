"""
Testes da configuracao de fluxo reutilizavel (RF-CORE-006 recorte + RF-REC-004).

O criterio da ficha: "a conferencia mensal roda por um comando, sem
redigitar parametros" — e sem nenhuma credencial dentro do arquivo.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from autotarefas.cli.commands.run import run
from autotarefas.cli.context import CLIContext
from autotarefas.core.exceptions import ConfigError
from autotarefas.flow import available_steps, describe_flow, load_flow, run_flow

FIXTURES = Path(__file__).parent / "fixtures" / "fluxo"
FLUXO = FIXTURES / "conferencia_mensal.yaml"


class TestLeituraDoFluxo:
    def test_le_o_fluxo_de_exemplo(self) -> None:
        config = load_flow(FLUXO)
        assert config.nome == "Conferencia mensal"
        assert [p.tipo for p in config.passos] == [
            "comparar",
            "conciliar",
            "transferir",
            "corrigir",
        ]

    def test_parametros_do_passo_ficam_disponiveis(self) -> None:
        primeiro = load_flow(FLUXO).passos[0]
        assert primeiro.params()["chave"] == ["codigo"]
        assert primeiro.params()["tolerancia"] == ["valor=0,01"]

    def test_descricao_lista_os_passos(self) -> None:
        texto = describe_flow(load_flow(FLUXO))
        assert "4 passo(s)" in texto
        assert "Base conciliada [conciliar]" in texto

    def test_tipo_desconhecido_e_recusado(self, tmp_path: Path) -> None:
        caminho = tmp_path / "f.yaml"
        caminho.write_text("passos:\n  - tipo: inventar\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="fluxo invalido"):
            load_flow(caminho)

    def test_fluxo_sem_passos(self, tmp_path: Path) -> None:
        caminho = tmp_path / "f.yaml"
        caminho.write_text("nome: vazio\npassos: []\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="fluxo invalido"):
            load_flow(caminho)

    def test_arquivo_ilegivel(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="nao foi possivel ler"):
            load_flow(tmp_path / "sumiu.yaml")

    def test_chave_desconhecida_no_topo(self, tmp_path: Path) -> None:
        caminho = tmp_path / "f.yaml"
        caminho.write_text(
            "passos:\n  - tipo: comparar\n    a: x\n    b: y\nqualquer: 1\n", encoding="utf-8"
        )
        with pytest.raises(ConfigError, match="fluxo invalido"):
            load_flow(caminho)

    def test_passos_conhecidos(self) -> None:
        assert set(available_steps()) == {"comparar", "conciliar", "transferir", "corrigir"}


class TestRecusaDeSegredo:
    @pytest.mark.parametrize(
        "linha",
        [
            "    api_key: abc123",
            "    token: abc123",
            "    senha: abc123",
            "    password: abc123",
        ],
    )
    def test_segredo_no_passo_e_recusado(self, tmp_path: Path, linha: str) -> None:
        caminho = tmp_path / "f.yaml"
        caminho.write_text(
            f"passos:\n  - tipo: comparar\n    a: x\n    b: y\n{linha}\n", encoding="utf-8"
        )
        with pytest.raises(ConfigError, match="segredo embutido"):
            load_flow(caminho)

    def test_mensagem_ensina_a_saida_certa(self, tmp_path: Path) -> None:
        caminho = tmp_path / "f.yaml"
        caminho.write_text(
            "passos:\n  - tipo: comparar\n    a: x\n    b: y\n    bearer: t\n", encoding="utf-8"
        )
        with pytest.raises(ConfigError, match="variavel de ambiente"):
            load_flow(caminho)

    def test_fluxo_de_exemplo_nao_tem_segredo(self) -> None:
        assert load_flow(FLUXO) is not None


class TestExecucao:
    def test_executa_todos_os_passos(self, tmp_path: Path) -> None:
        resultado = run_flow(load_flow(FLUXO), base_dir=FIXTURES, out_dir=tmp_path)

        assert resultado.ok
        assert resultado.counts == {"passos": 4, "concluidos": 4, "falhos": 0}

    def test_cada_passo_grava_no_proprio_diretorio(self, tmp_path: Path) -> None:
        run_flow(load_flow(FLUXO), base_dir=FIXTURES, out_dir=tmp_path)

        assert (tmp_path / "1-comparar" / "comparacao_report.json").exists()
        assert (tmp_path / "2-conciliar" / "base_conciliada.xlsx").exists()
        assert (tmp_path / "3-transferir" / "planilha_enriquecida.csv").exists()
        assert (tmp_path / "4-corrigir" / "correcoes_report.json").exists()

    def test_dry_run_nao_grava_nada(self, tmp_path: Path) -> None:
        destino = tmp_path / "saida"
        resultado = run_flow(load_flow(FLUXO), base_dir=FIXTURES, out_dir=destino, dry_run=True)

        assert resultado.ok
        assert not destino.exists()
        assert any("DRY-RUN" in aviso for aviso in resultado.warnings)

    def test_passo_com_arquivo_inexistente_interrompe_o_fluxo(self, tmp_path: Path) -> None:
        caminho = tmp_path / "f.yaml"
        caminho.write_text(
            "passos:\n"
            "  - tipo: comparar\n    a: sumiu.xlsx\n    b: sumiu.xlsx\n    chave: [x]\n"
            "  - tipo: corrigir\n    arquivo: a.xlsx\n    regras: r.yaml\n",
            encoding="utf-8",
        )
        resultado = run_flow(load_flow(caminho), base_dir=tmp_path, out_dir=None)

        assert resultado.ok is False
        assert len(resultado.steps) == 1  # nao seguiu para o segundo passo

    def test_parametro_obrigatorio_ausente_e_reportado(self, tmp_path: Path) -> None:
        caminho = tmp_path / "f.yaml"
        caminho.write_text("passos:\n  - tipo: comparar\n    a: x.xlsx\n", encoding="utf-8")
        resultado = run_flow(load_flow(caminho), base_dir=tmp_path)

        assert resultado.ok is False
        assert "parametro obrigatorio ausente" in resultado.steps[0].error

    def test_out_dir_da_cli_vence_o_do_arquivo(self, tmp_path: Path) -> None:
        correcoes = FIXTURES.parent / "correcoes"
        base = (correcoes / "base_para_corrigir.xlsx").as_posix()
        regras = (correcoes / "regras.yaml").as_posix()

        caminho = tmp_path / "f.yaml"
        caminho.write_text(
            "out_dir: do_arquivo\n"
            "passos:\n  - tipo: corrigir\n"
            f"    arquivo: {base}\n"
            f"    regras: {regras}\n",
            encoding="utf-8",
        )
        destino = tmp_path / "da_cli"
        resultado = run_flow(load_flow(caminho), base_dir=tmp_path, out_dir=destino)

        assert resultado.out_dir == destino
        assert (destino / "1-corrigir").exists()
        assert not (tmp_path / "do_arquivo").exists()


class TestComandoRun:
    def test_executa_e_sai_0(self, tmp_path: Path) -> None:
        result = CliRunner().invoke(run, [str(FLUXO), "--out-dir", str(tmp_path)], obj=CLIContext())
        assert result.exit_code == 0
        assert "Fluxo concluido: 4 passo(s)" in result.output

    def test_listar_nao_executa(self, tmp_path: Path) -> None:
        destino = tmp_path / "saida"
        result = CliRunner().invoke(
            run, [str(FLUXO), "--listar", "--out-dir", str(destino)], obj=CLIContext()
        )
        assert result.exit_code == 0
        assert "Base conciliada [conciliar]" in result.output
        assert not destino.exists()

    def test_dry_run(self, tmp_path: Path) -> None:
        destino = tmp_path / "saida"
        result = CliRunner().invoke(
            run, [str(FLUXO), "--out-dir", str(destino)], obj=CLIContext(dry_run=True)
        )
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output
        assert not destino.exists()

    def test_segredo_no_fluxo_e_erro_de_uso(self, tmp_path: Path) -> None:
        caminho = tmp_path / "f.yaml"
        caminho.write_text(
            "passos:\n  - tipo: comparar\n    a: x\n    b: y\n    api_key: k\n",
            encoding="utf-8",
        )
        result = CliRunner().invoke(run, [str(caminho)], obj=CLIContext())

        assert result.exit_code == 2
        assert "segredo embutido" in result.output

    def test_fluxo_interrompido_sai_1(self, tmp_path: Path) -> None:
        caminho = tmp_path / "f.yaml"
        caminho.write_text(
            "passos:\n  - tipo: comparar\n    a: sumiu.xlsx\n    b: sumiu.xlsx\n    chave: [x]\n",
            encoding="utf-8",
        )
        result = CliRunner().invoke(run, [str(caminho)], obj=CLIContext())
        assert result.exit_code == 1

    def test_comando_registrado_na_cli(self) -> None:
        from autotarefas.cli.main import cli

        assert "run" in cli.commands
