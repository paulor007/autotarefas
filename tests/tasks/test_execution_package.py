"""
Pacote operacional de execucao (1.7).

O teste central e `TestClassificacao::test_problema_de_grupo_leva_todas_as_linhas`:
antes da 1.7, uma divergencia de grupo marcava so a linha-ancora e as demais
linhas do mesmo grupo iam para "validos" carregando o mesmo problema.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from autotarefas.core import TaskResult
from autotarefas.tasks.execution_package import (
    MANIFEST_NAME,
    PROBLEMS_NAME,
    REVIEW_NAME,
    SCHEMA_NAME,
    SUMMARY_NAME,
    VALID_NAME,
    PackageError,
    PackageResult,
    build_package,
    classify_rows,
    count_formula_like,
    sha256_file,
)
from autotarefas.tasks.validate import ValidateTask, load_schema

SCHEMA_GRUPO = """
columns:
  - name: Pedido
  - name: Data
  - name: Item
  - name: Qtd
    type: int
  - name: Preco
    type: float
  - name: Total
    type: float
group_keys:
  - name: pedido
    columns: ["Pedido"]
group_checks:
  - name: coerencia
    group_key: pedido
    consistent: ["Data"]
derived_checks:
  - name: total
    target: Total
    expression: "[Qtd] * [Preco]"
"""

CSV_GRUPO = (
    "Pedido,Data,Item,Qtd,Preco,Total\n"
    "100,2026-01-05,A,2,10,20\n"  # linha 2 — grupo divergente
    "100,2026-02-09,B,1,5,5\n"  # linha 3 — mesmo grupo, mesma divergencia
    "101,2026-01-06,C,3,7,999\n"  # linha 4 — calculo errado
    "102,2026-01-07,D,1,4,4\n"  # linha 5 — limpa
)


def preparar(
    tmp_path: Path, csv_texto: str = CSV_GRUPO, schema_texto: str = SCHEMA_GRUPO
) -> tuple[Path, Path, ValidateTask, TaskResult]:
    entrada = tmp_path / "dados.csv"
    entrada.write_text(csv_texto, encoding="utf-8")
    esquema = tmp_path / "schema.yaml"
    esquema.write_text(schema_texto, encoding="utf-8")
    task = ValidateTask(entrada, load_schema(esquema), mode="auditoria")
    resultado = task.execute()
    return entrada, esquema, task, resultado


def frame(task: ValidateTask) -> pd.DataFrame:
    """O DataFrame processado, com o None ja descartado (o teste o exige)."""
    assert task.processed_dataframe is not None
    return task.processed_dataframe


def montar(tmp_path: Path, **kwargs: str) -> tuple[Path, Path, PackageResult]:
    entrada, esquema, task, resultado = preparar(tmp_path, **kwargs)
    destino = tmp_path / "pacote"
    pacote = build_package(
        destino,
        result=resultado,
        dataframe=frame(task),
        input_path=entrada,
        schema_path=esquema,
        options={"strict_warnings": False},
    )
    return entrada, esquema, pacote


# ============================================================
# Classificacao
# ============================================================


class TestClassificacao:
    def test_problema_de_grupo_leva_todas_as_linhas(self, tmp_path: Path) -> None:
        """
        O grupo 100 esta nas linhas 2 e 3; a mensagem ancora na 2.

        Se a classificacao usasse so a ancora, a linha 3 iria para validos
        carregando exatamente o mesmo problema.
        """
        _, _, _, resultado = preparar(tmp_path)
        c = classify_rows(resultado)
        assert 2 in c.review_lines
        assert 3 in c.review_lines
        assert 3 not in c.valid_lines

    def test_linha_com_erro_vai_para_revisao(self, tmp_path: Path) -> None:
        _, _, _, resultado = preparar(tmp_path)
        assert 4 in classify_rows(resultado).review_lines  # calculo errado

    def test_linha_limpa_fica_valida(self, tmp_path: Path) -> None:
        _, _, _, resultado = preparar(tmp_path)
        assert 5 in classify_rows(resultado).valid_lines

    def test_linha_so_com_aviso_continua_valida_mas_sinalizada(self, tmp_path: Path) -> None:
        """Politica documentada: aviso nao tira a linha do fluxo, mas aparece."""
        csv_texto = "A,B\nx,1\nx,1\n"
        schema = "columns:\n  - name: A\n  - name: B\ndetect_duplicate_rows: true\n"
        _, _, _, resultado = preparar(tmp_path, csv_texto=csv_texto, schema_texto=schema)
        c = classify_rows(resultado)
        assert c.review_lines == ()
        assert 3 in c.valid_lines
        assert 3 in c.warned_lines

    def test_arquivo_sem_problemas(self, tmp_path: Path) -> None:
        csv_texto = "A,B\n1,2\n3,4\n"
        schema = "columns:\n  - name: A\n  - name: B\n"
        _, _, _, resultado = preparar(tmp_path, csv_texto=csv_texto, schema_texto=schema)
        c = classify_rows(resultado)
        assert c.review_lines == ()
        assert len(c.valid_lines) == 2

    def test_multiplos_problemas_na_mesma_linha_nao_duplicam(self, tmp_path: Path) -> None:
        _, _, _, resultado = preparar(tmp_path)
        c = classify_rows(resultado)
        assert len(c.review_lines) == len(set(c.review_lines))

    def test_toda_linha_esta_em_exatamente_um_lado(self, tmp_path: Path) -> None:
        _, _, _, resultado = preparar(tmp_path)
        c = classify_rows(resultado)
        assert not set(c.valid_lines) & set(c.review_lines)
        assert len(c.valid_lines) + len(c.review_lines) == resultado.data["rows"]


# ============================================================
# Manifesto
# ============================================================


class TestManifesto:
    def test_campos_essenciais(self, tmp_path: Path) -> None:
        entrada, esquema, pacote = montar(tmp_path)
        m = json.loads((pacote.directory / MANIFEST_NAME).read_text(encoding="utf-8"))

        assert len(m["run_id"]) == 16
        assert m["tool"]["name"] == "autotarefas"
        assert m["tool"]["version"]
        assert m["input"]["sha256"] == sha256_file(entrada)
        assert m["configuration"]["schema_sha256"] == sha256_file(esquema)
        assert m["result"]["valid_rows"] == 1
        assert m["result"]["review_rows"] == 3
        assert m["status"] == "completed_with_issues"

    def test_lista_todos_os_artefatos_com_hash(self, tmp_path: Path) -> None:
        _, _, pacote = montar(tmp_path)
        m = json.loads((pacote.directory / MANIFEST_NAME).read_text(encoding="utf-8"))
        nomes = {a["filename"] for a in m["artifacts"]}
        assert nomes == {SUMMARY_NAME, PROBLEMS_NAME, VALID_NAME, REVIEW_NAME, SCHEMA_NAME}
        for entrada_art in m["artifacts"]:
            caminho = pacote.directory / entrada_art["filename"]
            assert entrada_art["sha256"] == sha256_file(caminho)
            assert entrada_art["size"] == caminho.stat().st_size

    def test_procedencia_do_perfil_e_preservada(self, tmp_path: Path) -> None:
        from autotarefas.profiles import export_schema, load_profile

        r = export_schema(load_profile("cadastro_contatos"), {"nome": "Nome"})
        esquema = tmp_path / "s.yaml"
        esquema.write_text(r.yaml_text, encoding="utf-8")
        entrada = tmp_path / "d.csv"
        entrada.write_text("Nome\nAna Silva\n", encoding="utf-8")

        task = ValidateTask(entrada, load_schema(esquema), mode="auditoria")
        resultado = task.execute()
        pacote = build_package(
            tmp_path / "pkg",
            result=resultado,
            dataframe=frame(task),
            input_path=entrada,
            schema_path=esquema,
        )
        m = json.loads((pacote.directory / MANIFEST_NAME).read_text(encoding="utf-8"))
        assert m["configuration"]["generated_from"]["profile"] == "cadastro_contatos"

    def test_status_sucesso_quando_nao_ha_erro(self, tmp_path: Path) -> None:
        _, _, pacote = montar(
            tmp_path,
            csv_texto="A,B\n1,2\n",
            schema_texto="columns:\n  - name: A\n  - name: B\n",
        )
        assert pacote.status == "success"


# ============================================================
# Arquivos tabulares
# ============================================================


class TestArquivosTabulares:
    def test_problemas_csv_usa_metadados_estruturais(self, tmp_path: Path) -> None:
        """`rule`, `category` e `related_lines` vem do issue, nao da mensagem."""
        _, _, pacote = montar(tmp_path)
        linhas = list(csv.DictReader((pacote.directory / PROBLEMS_NAME).open(encoding="utf-8-sig")))
        grupo = next(x for x in linhas if x["category"] == "grupo")
        assert grupo["rule"] == "coerencia"
        assert grupo["related_lines"] == "2 3"
        calculo = next(x for x in linhas if x["category"] == "calculo")
        assert calculo["rule"] == "total"

    def test_registros_preservam_ordem_e_valores_originais(self, tmp_path: Path) -> None:
        entrada, _, pacote = montar(tmp_path)
        original = entrada.read_text(encoding="utf-8").splitlines()
        validos = (pacote.directory / VALID_NAME).read_text(encoding="utf-8-sig").splitlines()
        assert validos[0] == original[0]  # mesmo cabecalho, mesma ordem
        assert validos[1] == original[4]  # a unica linha valida, intacta

    def test_revisao_tem_as_linhas_certas(self, tmp_path: Path) -> None:
        _, _, pacote = montar(tmp_path)
        revisao = (pacote.directory / REVIEW_NAME).read_text(encoding="utf-8-sig").splitlines()
        assert len(revisao) == 4  # cabecalho + 3 linhas
        assert "999" in revisao[3]

    def test_acentos_preservados(self, tmp_path: Path) -> None:
        csv_texto = "Descrição,Situação\nRelatório mensal,Não iniciado\n"
        schema = "columns:\n  - name: Descrição\n  - name: Situação\n"
        _, _, pacote = montar(tmp_path, csv_texto=csv_texto, schema_texto=schema)
        conteudo = (pacote.directory / VALID_NAME).read_text(encoding="utf-8-sig")
        assert "Relatório mensal" in conteudo
        assert "Não iniciado" in conteudo

    def test_schema_efetivo_e_copia_carregavel(self, tmp_path: Path) -> None:
        _, esquema, pacote = montar(tmp_path)
        copia = pacote.directory / SCHEMA_NAME
        assert copia.read_text(encoding="utf-8") == esquema.read_text(encoding="utf-8")
        assert len(load_schema(copia).columns) == 6

    def test_resumo_reusa_o_relatorio_json_existente(self, tmp_path: Path) -> None:
        """Nao ha segundo formato de relatorio: e o mesmo JSON do projeto."""
        _, _, pacote = montar(tmp_path)
        resumo = json.loads((pacote.directory / SUMMARY_NAME).read_text(encoding="utf-8"))
        assert resumo["task_name"] == "validate"
        assert "issues" in resumo
        assert "issues_by_category" in resumo


# ============================================================
# Original intacto, seguranca e falhas
# ============================================================


class TestSegurancaEIntegridade:
    def test_arquivo_original_nao_e_alterado(self, tmp_path: Path) -> None:
        entrada = tmp_path / "dados.csv"
        entrada.write_text(CSV_GRUPO, encoding="utf-8")
        antes = sha256_file(entrada)
        montar(tmp_path)
        assert sha256_file(entrada) == antes

    def test_destino_existente_nao_e_sobrescrito(self, tmp_path: Path) -> None:
        entrada, esquema, task, resultado = preparar(tmp_path)
        destino = tmp_path / "pacote"
        destino.mkdir()
        with pytest.raises(PackageError, match="ja existe"):
            build_package(
                destino,
                result=resultado,
                dataframe=frame(task),
                input_path=entrada,
                schema_path=esquema,
            )

    def test_falha_nao_deixa_pacote_pela_metade(self, tmp_path: Path) -> None:
        """Um destino impossivel nao pode deixar diretorio parcial para tras."""
        entrada, esquema, task, resultado = preparar(tmp_path)
        impossivel = tmp_path / "arquivo.txt" / "pacote"
        (tmp_path / "arquivo.txt").write_text("x", encoding="utf-8")
        with pytest.raises(PackageError):
            build_package(
                impossivel,
                result=resultado,
                dataframe=frame(task),
                input_path=entrada,
                schema_path=esquema,
            )
        assert not list(tmp_path.glob(".*parcial"))

    def test_celulas_com_cara_de_formula_sao_contadas_nao_alteradas(self, tmp_path: Path) -> None:
        csv_texto = 'A,B\n"=SOMA(1;2)",normal\n"@aqui",outro\n'
        schema = "columns:\n  - name: A\n  - name: B\n"
        _, _, pacote = montar(tmp_path, csv_texto=csv_texto, schema_texto=schema)
        assert pacote.formula_like_cells >= 2
        conteudo = (pacote.directory / VALID_NAME).read_text(encoding="utf-8-sig")
        assert "=SOMA(1;2)" in conteudo  # valor PRESERVADO, nao escapado
        m = json.loads((pacote.directory / MANIFEST_NAME).read_text(encoding="utf-8"))
        assert any("formula" in n for n in m["notes"])

    def test_count_formula_like_ignora_texto_comum(self, tmp_path: Path) -> None:
        import pandas as pd

        df = pd.DataFrame({"A": ["ok", "tudo bem"], "B": ["1", "2"]})
        assert count_formula_like(df) == 0


# ============================================================
# Determinismo
# ============================================================


class TestDeterminismo:
    def test_conteudo_tabular_e_reproduzivel(self, tmp_path: Path) -> None:
        entrada, esquema, task, resultado = preparar(tmp_path)
        hashes = []
        for i in range(2):
            pacote = build_package(
                tmp_path / f"p{i}",
                result=resultado,
                dataframe=frame(task),
                input_path=entrada,
                schema_path=esquema,
            )
            hashes.append(
                tuple(
                    sha256_file(pacote.directory / nome)
                    for nome in (PROBLEMS_NAME, VALID_NAME, REVIEW_NAME, SCHEMA_NAME)
                )
            )
        assert hashes[0] == hashes[1]

    def test_run_id_muda_entre_execucoes(self, tmp_path: Path) -> None:
        entrada, esquema, task, resultado = preparar(tmp_path)
        ids = []
        for i in range(2):
            pacote = build_package(
                tmp_path / f"r{i}",
                result=resultado,
                dataframe=frame(task),
                input_path=entrada,
                schema_path=esquema,
            )
            m = json.loads((pacote.directory / MANIFEST_NAME).read_text(encoding="utf-8"))
            ids.append(m["run_id"])
        assert ids[0] != ids[1]


# ============================================================
# CLI e compatibilidade
# ============================================================


class TestCLI:
    def test_sem_a_opcao_nada_muda(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from autotarefas.cli.main import cli

        entrada = tmp_path / "d.csv"
        entrada.write_text("A,B\n1,2\n", encoding="utf-8")
        esquema = tmp_path / "s.yaml"
        esquema.write_text("columns:\n  - name: A\n  - name: B\n", encoding="utf-8")

        r = CliRunner().invoke(cli, ["validate", str(entrada), "--schema", str(esquema)])
        assert r.exit_code == 0
        assert "Pacote" not in r.output
        assert not list(tmp_path.glob("*/manifest.json"))

    def test_com_a_opcao_gera_o_pacote(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from autotarefas.cli.main import cli

        entrada = tmp_path / "d.csv"
        entrada.write_text(CSV_GRUPO, encoding="utf-8")
        esquema = tmp_path / "s.yaml"
        esquema.write_text(SCHEMA_GRUPO, encoding="utf-8")
        destino = tmp_path / "saida"

        r = CliRunner().invoke(
            cli,
            [
                "validate",
                str(entrada),
                "--schema",
                str(esquema),
                "--artefatos",
                str(destino),
            ],
        )
        assert r.exit_code == 1  # ha erros de validacao
        assert (destino / MANIFEST_NAME).is_file()
        assert "para revisao" in r.output

    def test_destino_existente_falha_claramente(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from autotarefas.cli.main import cli

        entrada = tmp_path / "d.csv"
        entrada.write_text("A,B\n1,2\n", encoding="utf-8")
        esquema = tmp_path / "s.yaml"
        esquema.write_text("columns:\n  - name: A\n  - name: B\n", encoding="utf-8")
        destino = tmp_path / "ja_existe"
        destino.mkdir()

        r = CliRunner().invoke(
            cli,
            ["validate", str(entrada), "--schema", str(esquema), "--artefatos", str(destino)],
        )
        assert r.exit_code == 1
        assert "ja existe" in r.output


# ============================================================
# Anti-overfitting: tres dominios sinteticos
# ============================================================


class TestAntiOverfitting:
    @pytest.mark.parametrize(
        ("dominio", "csv_texto", "schema_texto", "revisao"),
        [
            (
                "administrativo",
                "Matricula,Setor\n1,RH\n1,TI\n2,RH\n",
                "columns:\n  - name: Matricula\n  - name: Setor\n"
                'group_keys:\n  - name: p\n    columns: ["Matricula"]\n'
                'group_checks:\n  - name: c\n    group_key: p\n    consistent: ["Setor"]\n',
                2,
            ),
            (
                "estoque",
                "Cod,Inicial,Entradas,Saidas,Final\nX,100,50,30,120\nY,200,10,5,999\n",
                "columns:\n  - name: Cod\n  - name: Inicial\n    type: float\n"
                "  - name: Entradas\n    type: float\n  - name: Saidas\n    type: float\n"
                "  - name: Final\n    type: float\n"
                "derived_checks:\n  - name: f\n    target: Final\n"
                '    expression: "[Inicial] + [Entradas] - [Saidas]"\n',
                1,
            ),
            (
                "servicos",
                "OS,Prazo\nA,10/01/2026\nB,31/02/2026\n",
                "columns:\n  - name: OS\n  - name: Prazo\n    type: date\n",
                1,
            ),
        ],
    )
    def test_pacote_funciona_em_dominios_diferentes(
        self, dominio: str, csv_texto: str, schema_texto: str, revisao: int, tmp_path: Path
    ) -> None:
        _, _, pacote = montar(tmp_path, csv_texto=csv_texto, schema_texto=schema_texto)
        assert pacote.classification is not None
        assert len(pacote.classification.review_lines) == revisao, dominio
        assert (pacote.directory / MANIFEST_NAME).is_file()
