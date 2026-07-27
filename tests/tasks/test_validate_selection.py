"""
Selecao de aba e linha de cabecalho no validate (1.8B-2A).

Antes desta etapa o `validate` lia com `pd.read_excel(path)` — primeira aba,
primeira linha — sem opcao de escolher. Uma planilha de varias abas era
validada silenciosamente na aba errada, e uma com cabecalho deslocado era
invalidavel. O `analisar` ja aceitava `--sheet`/`--header-row`: os dois
comandos discordavam sobre o mesmo arquivo.

O grupo `TestLinhasFisicas` e o mais importante: todo o projeto convertia
indice do DataFrame em numero de linha somando 2, o que so vale com o
cabecalho na linha 1.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from autotarefas.cli.main import cli
from autotarefas.core import TaskStatus
from autotarefas.tasks.execution_package import build_package, classify_rows
from autotarefas.tasks.validate import (
    SelectionError,
    ValidateTask,
    load_schema,
)

if TYPE_CHECKING:
    from autotarefas.core import TaskResult

FX = Path(__file__).parent.parent / "fixtures" / "planilhas"

EXIT_USAGE = 2
EXIT_DATA_PROBLEM = 1

#: Cabecalho na linha 4, com uma linha VAZIA antes — o caso que quebra
#: `header=` do pandas (que conta linhas nao vazias) e exige `skiprows`.
CSV_CABECALHO_4 = (
    "Relatorio\n"  # 1
    "\n"  # 2 (vazia)
    "gerado hoje\n"  # 3
    "produto,qtd\n"  # 4 = cabecalho
    "A,naonumero\n"  # 5 = erro de tipo
    "B,2\n"  # 6
    "C,3\n"  # 7
    "C,3\n"  # 8 = duplicata da 7
)

SCHEMA_QTD = (
    "detect_duplicate_rows: true\ncolumns:\n  - name: produto\n  - name: qtd\n    type: int\n"
)


def escrever(tmp_path: Path, nome: str, conteudo: str) -> Path:
    alvo = tmp_path / nome
    alvo.write_text(conteudo, encoding="utf-8")
    return alvo


def validar(
    arquivo: Path, schema_texto: str, tmp_path: Path, **kwargs: object
) -> tuple[ValidateTask, TaskResult]:
    schema = load_schema(escrever(tmp_path, "schema.yaml", schema_texto))
    task = ValidateTask(arquivo, schema, mode="auditoria", **kwargs)  # type: ignore[arg-type]
    return task, task.execute()


# ============================================================
# Defaults — nada pode ter mudado
# ============================================================


class TestDefaults:
    def test_xlsx_sem_opcoes_le_a_primeira_aba(self, tmp_path: Path) -> None:
        task, _ = validar(
            FX / "07_tres_abas.xlsx",
            "columns:\n  - name: produto\n",
            tmp_path,
        )
        assert task.processed_dataframe is not None
        assert list(task.processed_dataframe.columns) == ["produto", "qtd", "valor"]

    def test_csv_sem_opcoes_usa_a_primeira_linha(self, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "d.csv", "produto,qtd\nA,1\n")
        task, r = validar(arquivo, SCHEMA_QTD, tmp_path)
        assert r.status == TaskStatus.SUCCESS
        assert task.processed_dataframe is not None
        assert list(task.processed_dataframe.columns) == ["produto", "qtd"]

    def test_erro_continua_na_linha_2(self, tmp_path: Path) -> None:
        """O contrato de sempre: 1o registro e a linha fisica 2."""
        arquivo = escrever(tmp_path, "d.csv", "produto,qtd\nA,naonumero\n")
        _, r = validar(arquivo, SCHEMA_QTD, tmp_path)
        assert r.data["issues"][0]["line"] == 2

    def test_header_row_ausente_registra_1(self, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "d.csv", "produto,qtd\nA,1\n")
        _, r = validar(arquivo, SCHEMA_QTD, tmp_path)
        assert r.data["header_row"] == 1

    def test_call_site_posicional_continua_valido(self, tmp_path: Path) -> None:
        """Os parametros novos sao keyword-only: assinatura antiga intacta."""
        schema = load_schema(escrever(tmp_path, "s.yaml", SCHEMA_QTD))
        arquivo = escrever(tmp_path, "d.csv", "produto,qtd\nA,1\n")
        task = ValidateTask(arquivo, schema)
        assert task.execute().status == TaskStatus.SUCCESS


# ============================================================
# Aba
# ============================================================


class TestAba:
    def test_aba_escolhida_e_respeitada(self, tmp_path: Path) -> None:
        task, r = validar(
            FX / "07_tres_abas.xlsx",
            "columns:\n  - name: sku\n  - name: saldo\n",
            tmp_path,
            sheet="Estoque",
        )
        assert r.status == TaskStatus.SUCCESS
        assert task.processed_dataframe is not None
        assert list(task.processed_dataframe.columns) == ["sku", "saldo"]

    def test_analisar_e_validate_leem_as_mesmas_colunas(self, tmp_path: Path) -> None:
        """A divergencia que a etapa existe para fechar."""
        from autotarefas.services import analyze_spreadsheet

        analise = analyze_spreadsheet(FX / "07_tres_abas.xlsx", sheet="Estoque")
        colunas_analise = [c["name"] for c in analise.report["columns"]]

        task, _ = validar(
            FX / "07_tres_abas.xlsx",
            "columns:\n  - name: sku\n  - name: saldo\n",
            tmp_path,
            sheet="Estoque",
        )
        assert task.processed_dataframe is not None
        assert list(task.processed_dataframe.columns) == colunas_analise

    def test_aba_inexistente_e_erro_de_uso(self, tmp_path: Path) -> None:
        with pytest.raises(SelectionError, match="nao existe"):
            validar(
                FX / "07_tres_abas.xlsx",
                "columns:\n  - name: produto\n",
                tmp_path,
                sheet="Fantasma",
            )

    def test_sheet_em_csv_e_recusado(self, tmp_path: Path) -> None:
        """Ignorar em silencio faria o usuario crer que a escolha valeu."""
        arquivo = escrever(tmp_path, "d.csv", "produto,qtd\nA,1\n")
        with pytest.raises(SelectionError, match="CSV"):
            validar(arquivo, SCHEMA_QTD, tmp_path, sheet="Plan1")

    def test_sheet_vazia_e_recusada(self, tmp_path: Path) -> None:
        with pytest.raises(SelectionError, match="vazio"):
            validar(
                FX / "07_tres_abas.xlsx",
                "columns:\n  - name: produto\n",
                tmp_path,
                sheet="   ",
            )

    def test_escolha_nao_altera_o_arquivo(self, tmp_path: Path) -> None:
        import hashlib

        alvo = FX / "07_tres_abas.xlsx"
        antes = hashlib.sha256(alvo.read_bytes()).hexdigest()
        validar(alvo, "columns:\n  - name: sku\n  - name: saldo\n", tmp_path, sheet="Estoque")
        assert hashlib.sha256(alvo.read_bytes()).hexdigest() == antes


# ============================================================
# Cabecalho
# ============================================================


class TestCabecalho:
    def test_xlsx_cabecalho_na_linha_4(self, tmp_path: Path) -> None:
        task, r = validar(
            FX / "06_cabecalho_linha_4.xlsx",
            "columns:\n  - name: produto\n  - name: quantidade\n  - name: valor\n",
            tmp_path,
            header_row=4,
        )
        assert r.status == TaskStatus.SUCCESS
        assert task.processed_dataframe is not None
        assert list(task.processed_dataframe.columns) == [
            "produto",
            "quantidade",
            "valor",
        ]

    def test_csv_cabecalho_na_linha_4_com_linha_vazia_antes(self, tmp_path: Path) -> None:
        """
        `skiprows`, nao `header=`: o pandas conta linhas NAO VAZIAS para
        `header`, entao com a linha 2 em branco ele pegaria a linha errada.
        """
        arquivo = escrever(tmp_path, "h4.csv", CSV_CABECALHO_4)
        task, _ = validar(arquivo, SCHEMA_QTD, tmp_path, header_row=4)
        assert task.processed_dataframe is not None
        assert list(task.processed_dataframe.columns) == ["produto", "qtd"]
        assert len(task.processed_dataframe) == 4

    def test_header_row_1_e_igual_ao_default(self, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "d.csv", "produto,qtd\nA,naonumero\n")
        _, com = validar(arquivo, SCHEMA_QTD, tmp_path, header_row=1)
        _, sem = validar(arquivo, SCHEMA_QTD, tmp_path)
        assert com.data["issues"][0]["line"] == sem.data["issues"][0]["line"]

    @pytest.mark.parametrize("valor", [0, -1, -99])
    def test_header_row_invalido(self, valor: int, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "d.csv", "produto,qtd\nA,1\n")
        with pytest.raises(SelectionError, match="1 ou maior"):
            validar(arquivo, SCHEMA_QTD, tmp_path, header_row=valor)

    def test_header_row_alem_do_fim(self, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "d.csv", "produto,qtd\nA,1\n")
        with pytest.raises(SelectionError, match="passa do fim"):
            validar(arquivo, SCHEMA_QTD, tmp_path, header_row=9999)


# ============================================================
# LINHAS FISICAS — o coracao da etapa
# ============================================================


class TestLinhasFisicas:
    def test_erro_no_primeiro_dado_aparece_na_linha_5(self, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "h4.csv", CSV_CABECALHO_4)
        _, r = validar(arquivo, SCHEMA_QTD, tmp_path, header_row=4)
        erros = [i for i in r.data["issues"] if i["severity"] == "error"]
        assert erros[0]["line"] == 5

    def test_duplicidade_usa_linhas_fisicas(self, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "h4.csv", CSV_CABECALHO_4)
        _, r = validar(arquivo, SCHEMA_QTD, tmp_path, header_row=4)
        dup = next(i for i in r.data["issues"] if "duplicada" in i["message"])
        assert dup["line"] == 8
        assert dup["related_lines"] == [7, 8]

    def test_group_e_derived_usam_linhas_fisicas(self, tmp_path: Path) -> None:
        arquivo = escrever(
            tmp_path,
            "g4.csv",
            "Titulo\nsub\nnota\n"
            "pedido,data,qtd,preco,total\n"
            "100,2026-01-01,2,10,20\n"
            "100,2026-02-09,1,5,5\n"
            "101,2026-01-02,3,7,999\n",
        )
        schema = """
columns:
  - name: pedido
  - name: data
  - name: qtd
    type: int
  - name: preco
    type: float
  - name: total
    type: float
group_keys:
  - name: p
    columns: ["pedido"]
group_checks:
  - name: coerencia
    group_key: p
    consistent: ["data"]
derived_checks:
  - name: tot
    target: total
    expression: "[qtd] * [preco]"
"""
        _, r = validar(arquivo, schema, tmp_path, header_row=4)
        grupo = next(i for i in r.data["issues"] if i.get("category") == "grupo")
        assert grupo["line"] == 5
        assert grupo["related_lines"] == [5, 6]
        assert "linha(s) 5" in grupo["message"]

        calculo = next(i for i in r.data["issues"] if i.get("category") == "calculo")
        assert calculo["line"] == 7

    def test_classificacao_nao_inclui_linhas_de_titulo(self, tmp_path: Path) -> None:
        """
        O bug que isto tranca: `range(2, total+2)` listava as linhas 2, 3 e 4
        (lixo e cabecalho) como registros validos.
        """
        arquivo = escrever(tmp_path, "h4.csv", CSV_CABECALHO_4)
        _, r = validar(arquivo, SCHEMA_QTD, tmp_path, header_row=4)
        c = classify_rows(r)
        assert min(c.valid_lines + c.review_lines) >= 5
        assert 4 not in c.valid_lines

    def test_pacote_exporta_os_dados_certos(self, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "h4.csv", CSV_CABECALHO_4)
        schema_path = escrever(tmp_path, "schema.yaml", SCHEMA_QTD)
        task = ValidateTask(arquivo, load_schema(schema_path), mode="auditoria", header_row=4)
        r = task.execute()
        assert task.processed_dataframe is not None
        pacote = build_package(
            tmp_path / "pkg",
            result=r,
            dataframe=task.processed_dataframe,
            input_path=arquivo,
            schema_path=schema_path,
        )
        revisao = (pacote.directory / "registros_para_revisao.csv").read_text(encoding="utf-8-sig")
        assert "naonumero" in revisao  # a linha com erro
        assert "Relatorio" not in revisao  # e nao a linha de titulo

        manifesto = json.loads((pacote.directory / "manifest.json").read_text())
        assert manifesto["configuration"]["header_row"] == 4


# ============================================================
# Evidencias
# ============================================================


class TestEvidencias:
    def test_xlsx_registra_a_aba(self, tmp_path: Path) -> None:
        _, r = validar(
            FX / "07_tres_abas.xlsx",
            "columns:\n  - name: sku\n  - name: saldo\n",
            tmp_path,
            sheet="Estoque",
        )
        assert r.data["selected_sheet"] == "Estoque"

    def test_csv_nao_inventa_aba(self, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "d.csv", "produto,qtd\nA,1\n")
        _, r = validar(arquivo, SCHEMA_QTD, tmp_path)
        assert "selected_sheet" not in r.data

    def test_header_row_efetivo_no_resultado(self, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "h4.csv", CSV_CABECALHO_4)
        _, r = validar(arquivo, SCHEMA_QTD, tmp_path, header_row=4)
        assert r.data["header_row"] == 4


# ============================================================
# CLI
# ============================================================


class TestCLI:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_help_documenta_as_opcoes(self) -> None:
        r = self.runner.invoke(cli, ["validate", "--help"])
        assert r.exit_code == 0
        assert "--sheet" in r.output
        assert "--header-row" in r.output
        assert "XLSX" in r.output

    def test_sheet_pela_cli(self, tmp_path: Path) -> None:
        schema = escrever(tmp_path, "s.yaml", "columns:\n  - name: sku\n  - name: saldo\n")
        r = self.runner.invoke(
            cli,
            [
                "validate",
                str(FX / "07_tres_abas.xlsx"),
                "--schema",
                str(schema),
                "--sheet",
                "Estoque",
            ],
        )
        assert r.exit_code == 0

    def test_header_row_pela_cli(self, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "h4.csv", CSV_CABECALHO_4.replace("naonumero", "1"))
        schema = escrever(tmp_path, "s.yaml", SCHEMA_QTD)
        r = self.runner.invoke(
            cli,
            [
                "validate",
                str(arquivo),
                "--schema",
                str(schema),
                "--header-row",
                "4",
            ],
        )
        assert r.exit_code == 0

    def test_sheet_em_csv_da_exit_2(self, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "d.csv", "produto,qtd\nA,1\n")
        schema = escrever(tmp_path, "s.yaml", SCHEMA_QTD)
        r = self.runner.invoke(
            cli,
            ["validate", str(arquivo), "--schema", str(schema), "--sheet", "X"],
        )
        assert r.exit_code == EXIT_USAGE

    def test_aba_inexistente_da_exit_2_e_nao_gera_pacote(self, tmp_path: Path) -> None:
        schema = escrever(tmp_path, "s.yaml", "columns:\n  - name: produto\n")
        destino = tmp_path / "pkg"
        r = self.runner.invoke(
            cli,
            [
                "validate",
                str(FX / "07_tres_abas.xlsx"),
                "--schema",
                str(schema),
                "--sheet",
                "Fantasma",
                "--artefatos",
                str(destino),
            ],
        )
        assert r.exit_code == EXIT_USAGE
        assert not destino.exists()  # nada que pareca execucao concluida

    def test_header_row_zero_recusado_pela_cli(self, tmp_path: Path) -> None:
        arquivo = escrever(tmp_path, "d.csv", "produto,qtd\nA,1\n")
        schema = escrever(tmp_path, "s.yaml", SCHEMA_QTD)
        r = self.runner.invoke(
            cli,
            [
                "validate",
                str(arquivo),
                "--schema",
                str(schema),
                "--header-row",
                "0",
            ],
        )
        assert r.exit_code == EXIT_USAGE

    def test_problema_nos_dados_continua_exit_1(self, tmp_path: Path) -> None:
        """Erro de uso e exit 2; arquivo com problemas segue sendo exit 1."""
        arquivo = escrever(tmp_path, "d.csv", "produto,qtd\nA,naonumero\n")
        schema = escrever(tmp_path, "s.yaml", SCHEMA_QTD)
        r = self.runner.invoke(cli, ["validate", str(arquivo), "--schema", str(schema)])
        assert r.exit_code == EXIT_DATA_PROBLEM

    def test_as_duas_opcoes_juntas(self, tmp_path: Path) -> None:
        schema = escrever(
            tmp_path,
            "s.yaml",
            "columns:\n  - name: produto\n  - name: quantidade\n  - name: valor\n",
        )
        r = self.runner.invoke(
            cli,
            [
                "validate",
                str(FX / "06_cabecalho_linha_4.xlsx"),
                "--schema",
                str(schema),
                "--sheet",
                "Plan1",
                "--header-row",
                "4",
            ],
        )
        assert r.exit_code == 0
