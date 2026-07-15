"""
Testes do comando ``autotarefas analisar``.

O criterio central desta subetapa nao e "funciona com a planilha de
vendas". E: **funciona com uma planilha que o AutoTarefas nunca viu**.
Por isso a classe `TestAntiOverfitting` roda o comando contra tres
dominios completamente diferentes — se alguma regra, texto ou metrica
tivesse sido escrita pensando na fixture de vendas, elas quebrariam.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from autotarefas.cli.commands.analisar import analisar
from autotarefas.cli.context import CLIContext
from autotarefas.profiling.report import JSON_REPORT_NAME

FIXTURES = Path(__file__).parent.parent / "fixtures" / "planilhas"

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def ctx() -> CLIContext:
    return CLIContext()


def rodar(runner: CliRunner, ctx: CLIContext, *args: str) -> Result:
    return runner.invoke(analisar, list(args), obj=ctx)


# ============================================================
# Entradas validas
# ============================================================


class TestEntradasValidas:
    def test_xlsx(self, runner: CliRunner, ctx: CLIContext) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "02_xlsx_limpo.xlsx"))
        assert r.exit_code == EXIT_OK
        assert "Registros: 3" in r.output
        assert "Colunas: 3" in r.output

    def test_csv(self, runner: CliRunner, ctx: CLIContext) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "01_csv_limpo.csv"))
        assert r.exit_code == EXIT_OK
        assert "Registros: 3" in r.output

    def test_sheet_explicito(self, runner: CliRunner, ctx: CLIContext) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "07_tres_abas.xlsx"), "--sheet", "Estoque")
        assert r.exit_code == EXIT_OK
        assert "Estoque" in r.output

    def test_header_row_explicito(self, runner: CliRunner, ctx: CLIContext) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "06_cabecalho_linha_4.xlsx"), "--header-row", "4")
        assert r.exit_code == EXIT_OK
        assert "linha 4" in r.output

    def test_volume(self, runner: CliRunner, ctx: CLIContext) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "28_vendas_sintetica.xlsx"), "--preview", "0")
        assert r.exit_code == EXIT_OK
        assert "Registros: 245" in r.output


# ============================================================
# ANTI-OVERFITTING — o criterio essencial
# ============================================================


class TestAntiOverfitting:
    """Estruturas que o AutoTarefas nunca viu. Nenhuma regra de vendas."""

    @pytest.mark.parametrize(
        ("fixture", "colunas"),
        [
            (
                "30_administrativa.xlsx",
                ["Funcionario", "Departamento", "Data de Admissao", "Status"],
            ),
            (
                "31_estoque.xlsx",
                ["Codigo Interno", "Descricao", "Saldo", "Localizacao", "Ultima Atualizacao"],
            ),
            ("32_servicos.csv", ["Numero", "Servico", "Responsavel", "Prazo", "Situacao"]),
        ],
    )
    def test_dominio_desconhecido_e_analisado(
        self, runner: CliRunner, ctx: CLIContext, fixture: str, colunas: list[str]
    ) -> None:
        r = rodar(runner, ctx, str(FIXTURES / fixture), "--preview", "0")
        assert r.exit_code == EXIT_OK
        assert "Registros: 4" in r.output
        # a saida e montada com os nomes REAIS do arquivo
        for nome in colunas:
            assert nome in r.output

    def test_saida_nao_contem_nada_de_vendas(self, runner: CliRunner, ctx: CLIContext) -> None:
        """Nenhum texto do dominio de vendas vaza para uma planilha de RH."""
        r = rodar(runner, ctx, str(FIXTURES / "30_administrativa.xlsx"))
        proibidos = ("Codigo Venda", "Valor Final", "Valor Unitario", "faturamento", "SKU")
        for termo in proibidos:
            assert termo.lower() not in r.output.lower()

    def test_json_de_dominio_desconhecido_tem_as_colunas_reais(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        saida = tmp_path / "out"
        r = rodar(runner, ctx, str(FIXTURES / "31_estoque.xlsx"), "--out-dir", str(saida))
        assert r.exit_code == EXIT_OK
        dados = json.loads((saida / JSON_REPORT_NAME).read_text(encoding="utf-8"))
        nomes = [c["name"] for c in dados["columns"]]
        assert nomes == [
            "Codigo Interno",
            "Descricao",
            "Saldo",
            "Localizacao",
            "Ultima Atualizacao",
        ]


# ============================================================
# Erros de uso
# ============================================================


class TestErrosDeUso:
    def test_arquivo_inexistente(self, runner: CliRunner, ctx: CLIContext) -> None:
        r = rodar(runner, ctx, "nao_existe.xlsx")
        assert r.exit_code == EXIT_USAGE

    def test_extensao_nao_suportada(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        alvo = tmp_path / "dados.txt"
        alvo.write_text("a,b\n1,2\n", encoding="utf-8")
        r = rodar(runner, ctx, str(alvo))
        assert r.exit_code == EXIT_USAGE
        assert "nao suportada" in r.output

    def test_xls_antigo_orienta_conversao(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        alvo = tmp_path / "antigo.xls"
        alvo.write_bytes(b"\xd0\xcf\x11\xe0")
        r = rodar(runner, ctx, str(alvo))
        assert r.exit_code == EXIT_USAGE
        assert ".xlsx" in r.output

    def test_aba_inexistente(self, runner: CliRunner, ctx: CLIContext) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "07_tres_abas.xlsx"), "--sheet", "Inexistente")
        assert r.exit_code == EXIT_USAGE
        assert "Inexistente" in r.output

    def test_header_row_invalido(self, runner: CliRunner, ctx: CLIContext) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "02_xlsx_limpo.xlsx"), "--header-row", "999")
        assert r.exit_code == EXIT_USAGE

    def test_nao_tabular_e_recusado_sem_metricas_falsas(
        self, runner: CliRunner, ctx: CLIContext
    ) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "25_nao_tabular.xlsx"))
        assert r.exit_code == EXIT_USAGE
        assert "nao parece conter uma tabela" in r.output
        assert "Registros:" not in r.output  # nenhuma metrica inventada

    def test_abas_ambiguas_pedem_escolha(self, runner: CliRunner, ctx: CLIContext) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "07_tres_abas.xlsx"))
        assert r.exit_code == EXIT_USAGE
        assert "--sheet" in r.output
        assert "Abas encontradas:" in r.output

    def test_out_dir_e_json_juntos(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        r = rodar(
            runner,
            ctx,
            str(FIXTURES / "02_xlsx_limpo.xlsx"),
            "--out-dir",
            str(tmp_path),
            "--json",
            str(tmp_path / "r.json"),
        )
        assert r.exit_code == EXIT_USAGE


# ============================================================
# Exit codes
# ============================================================


class TestExitCodes:
    def test_sucesso_sem_avisos(self, runner: CliRunner, ctx: CLIContext) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "02_xlsx_limpo.xlsx"))
        assert r.exit_code == EXIT_OK
        assert "Analise concluida." in r.output

    def test_avisos_nao_impedem_o_relatorio(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        """Linha duplicada e AVISO: o relatorio sai e o exit code e 0."""
        r = rodar(
            runner, ctx, str(FIXTURES / "21_linhas_duplicadas.xlsx"), "--out-dir", str(tmp_path)
        )
        assert r.exit_code == EXIT_OK
        assert (tmp_path / JSON_REPORT_NAME).exists()
        assert "aviso" in r.output.lower()

    def test_strict_warnings_transforma_aviso_em_falha(
        self, runner: CliRunner, ctx: CLIContext
    ) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "21_linhas_duplicadas.xlsx"), "--strict-warnings")
        assert r.exit_code == EXIT_FAILURE

    def test_problema_observado_gera_exit_1_mas_relatorio_sai(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        """Erro do Excel e PROBLEMA — mas o diagnostico ainda e entregue."""
        r = rodar(runner, ctx, str(FIXTURES / "20_erros_excel.xlsx"), "--out-dir", str(tmp_path))
        assert r.exit_code == EXIT_FAILURE
        assert (tmp_path / JSON_REPORT_NAME).exists()
        assert "problema" in r.output.lower()


# ============================================================
# Relatorio JSON
# ============================================================


class TestRelatorioJSON:
    def test_criado_com_nome_consistente(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        saida = tmp_path / "resultado"
        r = rodar(runner, ctx, str(FIXTURES / "02_xlsx_limpo.xlsx"), "--out-dir", str(saida))
        assert r.exit_code == EXIT_OK
        assert (saida / "analise_report.json").exists()

    def test_json_valido_e_completo(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        rodar(runner, ctx, str(FIXTURES / "28_vendas_sintetica.xlsx"), "--out-dir", str(tmp_path))
        dados = json.loads((tmp_path / JSON_REPORT_NAME).read_text(encoding="utf-8"))

        assert set(dados) >= {
            "metadata",
            "leitura",
            "estrutura",
            "columns",
            "findings",
            "reader_warnings",
            "rejected_reason",
        }
        assert dados["metadata"]["tool_version"]
        assert dados["metadata"]["generated_at"]
        assert dados["metadata"]["file_type"] == "xlsx"
        assert dados["estrutura"]["row_count"] == 245
        assert len(dados["columns"]) == 7

    def test_json_NAO_contem_o_dataframe_inteiro(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        """245 linhas x 7 colunas nao podem vazar para o relatorio."""
        rodar(runner, ctx, str(FIXTURES / "28_vendas_sintetica.xlsx"), "--out-dir", str(tmp_path))
        bruto = (tmp_path / JSON_REPORT_NAME).read_text(encoding="utf-8")
        dados = json.loads(bruto)

        for coluna in dados["columns"]:
            assert len(coluna["sample_values"]) <= 5
        for achado in dados["findings"]:
            assert len(achado["samples"]) <= 5
        assert len(dados["leitura"]["conversions_sample"]) <= 20
        # sem o corpo da planilha, o arquivo e pequeno
        assert len(bruto) < 20_000

    def test_caminho_exato_com_json(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        alvo = tmp_path / "meu_relatorio.json"
        r = rodar(runner, ctx, str(FIXTURES / "01_csv_limpo.csv"), "--json", str(alvo))
        assert r.exit_code == EXIT_OK
        assert alvo.exists()

    def test_deterministico_ignorando_o_timestamp(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        a, b = tmp_path / "a", tmp_path / "b"
        rodar(runner, ctx, str(FIXTURES / "28_vendas_sintetica.xlsx"), "--out-dir", str(a))
        rodar(runner, ctx, str(FIXTURES / "28_vendas_sintetica.xlsx"), "--out-dir", str(b))

        d1 = json.loads((a / JSON_REPORT_NAME).read_text(encoding="utf-8"))
        d2 = json.loads((b / JSON_REPORT_NAME).read_text(encoding="utf-8"))
        d1["metadata"].pop("generated_at")
        d2["metadata"].pop("generated_at")
        assert d1 == d2

    def test_dry_run_nao_grava(self, runner: CliRunner, tmp_path: Path) -> None:
        r = runner.invoke(
            analisar,
            [str(FIXTURES / "02_xlsx_limpo.xlsx"), "--out-dir", str(tmp_path)],
            obj=CLIContext(dry_run=True),
        )
        assert r.exit_code == EXIT_OK
        assert not (tmp_path / JSON_REPORT_NAME).exists()
        assert "DRY-RUN" in r.output


# ============================================================
# Seguranca e preservacao
# ============================================================


class TestSeguranca:
    def test_arquivo_original_nao_e_alterado(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        copia = tmp_path / "entrada.xlsx"
        shutil.copy(FIXTURES / "28_vendas_sintetica.xlsx", copia)
        antes = copia.read_bytes()

        rodar(runner, ctx, str(copia), "--out-dir", str(tmp_path / "saida"))

        assert copia.read_bytes() == antes

    def test_relatorio_nao_sobrescreve_a_entrada(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        copia = tmp_path / "entrada.csv"
        shutil.copy(FIXTURES / "01_csv_limpo.csv", copia)
        r = rodar(runner, ctx, str(copia), "--json", str(copia))
        assert r.exit_code == EXIT_USAGE
        assert "sobrescrever a planilha" in r.output

    def test_avisa_ao_sobrescrever_relatorio_existente(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        rodar(runner, ctx, str(FIXTURES / "01_csv_limpo.csv"), "--out-dir", str(tmp_path))
        r = rodar(runner, ctx, str(FIXTURES / "01_csv_limpo.csv"), "--out-dir", str(tmp_path))
        assert "Sobrescrevendo" in r.output

    def test_diretorio_de_saida_e_criado(
        self, runner: CliRunner, ctx: CLIContext, tmp_path: Path
    ) -> None:
        fundo = tmp_path / "a" / "b" / "c"
        r = rodar(runner, ctx, str(FIXTURES / "01_csv_limpo.csv"), "--out-dir", str(fundo))
        assert r.exit_code == EXIT_OK
        assert (fundo / JSON_REPORT_NAME).exists()


# ============================================================
# Previa
# ============================================================


class TestPrevia:
    def test_previa_limitada(self, runner: CliRunner, ctx: CLIContext) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "28_vendas_sintetica.xlsx"), "--preview", "2")
        previa = r.output.split("Arquivo:")[0]
        # cabecalho + separador + 2 linhas
        assert previa.count("|") > 0
        assert "70001" in previa

    def test_previa_desligada(self, runner: CliRunner, ctx: CLIContext) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "02_xlsx_limpo.xlsx"), "--preview", "0")
        assert "Previa" not in r.output

    def test_previa_nao_despeja_a_planilha_inteira(
        self, runner: CliRunner, ctx: CLIContext
    ) -> None:
        r = rodar(runner, ctx, str(FIXTURES / "28_vendas_sintetica.xlsx"), "--preview", "5")
        previa = r.output.split("Arquivo:")[0]
        # a 1a linha aparece; uma linha do meio da planilha, nunca
        assert "70001" in previa
        assert "70060" not in previa
        assert previa.count("\n") < 30  # 245 linhas dariam 245+


# ============================================================
# Compatibilidade
# ============================================================


class TestCompatibilidade:
    def test_validate_continua_existindo(self) -> None:
        from autotarefas.cli.main import cli

        assert "validate" in cli.commands
        assert "analisar" in cli.commands
