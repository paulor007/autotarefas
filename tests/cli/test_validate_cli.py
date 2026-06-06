"""Testes para o comando CLI `autotarefas validate`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from autotarefas.cli.commands.validate import validate
from autotarefas.cli.context import CLIContext

# ============================================================
# Fixtures: contextos
# ============================================================


@pytest.fixture
def cli_ctx() -> CLIContext:
    """CLIContext padrao (sem dry-run, sem verbose)."""
    return CLIContext()


@pytest.fixture
def cli_ctx_dry_run() -> CLIContext:
    """CLIContext com dry-run ativo."""
    return CLIContext(dry_run=True)


# ============================================================
# Fixtures: schemas YAML
# ============================================================


@pytest.fixture
def schema_basico(tmp_path: Path) -> Path:
    """Schema simples: apenas nome e idade."""
    path = tmp_path / "schema.yaml"
    path.write_text(
        """
columns:
  - name: nome
    type: str
  - name: idade
    type: int
    min_value: 0
    max_value: 150
    nullable: true
""",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def schema_rico(tmp_path: Path) -> Path:
    """Schema com varias regras (cpf, enum, etc)."""
    path = tmp_path / "schema_rico.yaml"
    path.write_text(
        """
columns:
  - name: nome
    type: str

  - name: idade
    type: int
    min_value: 0
    max_value: 150
    nullable: true

  - name: cpf
    validator_br: cpf
    nullable: true

  - name: uf
    enum_values: [SP, RJ, MG]
    nullable: true
""",
        encoding="utf-8",
    )
    return path


# ============================================================
# Fixtures: CSVs
# ============================================================


@pytest.fixture
def csv_valido(tmp_path: Path) -> Path:
    """CSV sem problemas — passa em qualquer schema basico."""
    path = tmp_path / "valido.csv"
    path.write_text(
        "nome,idade\nAlice,30\nBob,25\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def csv_com_erros(tmp_path: Path) -> Path:
    """CSV com problemas em varias colunas."""
    path = tmp_path / "ruim.csv"
    path.write_text(
        "nome,idade,cpf,uf\n"
        "Alice,30,529.982.247-25,SP\n"
        "Bob,200,111.111.111-11,XX\n"  # idade fora range, CPF blacklist, UF nao listada
        '"",abc,12345,RJ\n',  # nome vazio, idade nao-int, CPF muito curto
        encoding="utf-8",
    )
    return path


# ============================================================
# Tests: Sucesso (exit 0)
# ============================================================


class TestValidateCommandSuccess:
    """Cenarios de sucesso — exit code 0."""

    def test_csv_valido_exit_0(
        self, csv_valido: Path, schema_basico: Path, cli_ctx: CLIContext
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            validate,
            [str(csv_valido), "--schema", str(schema_basico)],
            obj=cli_ctx,
        )
        assert result.exit_code == 0

    def test_csv_valido_mostra_mensagem_ok(
        self, csv_valido: Path, schema_basico: Path, cli_ctx: CLIContext
    ) -> None:
        """Output contem indicacao de validacao OK."""
        runner = CliRunner()
        result = runner.invoke(
            validate,
            [str(csv_valido), "--schema", str(schema_basico)],
            obj=cli_ctx,
        )
        # Deve aparecer "OK" ou "Sem problemas"
        assert "OK" in result.output or "Sem problemas" in result.output

    def test_csv_vazio_so_header(
        self, tmp_path: Path, schema_basico: Path, cli_ctx: CLIContext
    ) -> None:
        """CSV so com cabecalho (zero linhas) passa."""
        csv_path = tmp_path / "vazio.csv"
        csv_path.write_text("nome,idade\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            validate,
            [str(csv_path), "--schema", str(schema_basico)],
            obj=cli_ctx,
        )
        assert result.exit_code == 0

    def test_dados_completos_schema_rico_passa(
        self, tmp_path: Path, schema_rico: Path, cli_ctx: CLIContext
    ) -> None:
        """Schema rico (cpf, enum) com dados validos: exit 0."""
        csv_path = tmp_path / "completo.csv"
        csv_path.write_text(
            "nome,idade,cpf,uf\nAlice,30,529.982.247-25,SP\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(
            validate,
            [str(csv_path), "--schema", str(schema_rico)],
            obj=cli_ctx,
        )
        assert result.exit_code == 0

    def test_strict_warnings_sem_warnings_exit_0(
        self, csv_valido: Path, schema_basico: Path, cli_ctx: CLIContext
    ) -> None:
        """--strict-warnings sem warnings: exit 0 normal."""
        runner = CliRunner()
        result = runner.invoke(
            validate,
            [
                str(csv_valido),
                "--schema",
                str(schema_basico),
                "--strict-warnings",
            ],
            obj=cli_ctx,
        )
        assert result.exit_code == 0


# ============================================================
# Tests: Falha de validacao (exit 1)
# ============================================================


class TestValidateCommandFailure:
    """Cenarios de falha — exit code 1."""

    def test_csv_com_erros_exit_1(
        self, csv_com_erros: Path, schema_rico: Path, cli_ctx: CLIContext
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            validate,
            [str(csv_com_erros), "--schema", str(schema_rico)],
            obj=cli_ctx,
        )
        assert result.exit_code == 1

    def test_csv_com_erros_mostra_mensagem_falha(
        self, csv_com_erros: Path, schema_rico: Path, cli_ctx: CLIContext
    ) -> None:
        """Output indica que houve falha."""
        runner = CliRunner()
        result = runner.invoke(
            validate,
            [str(csv_com_erros), "--schema", str(schema_rico)],
            obj=cli_ctx,
        )
        # Deve mencionar erro ou falha
        assert "falhou" in result.output.lower() or "erro" in result.output.lower()

    def test_csv_com_erros_lista_problemas(
        self, csv_com_erros: Path, schema_rico: Path, cli_ctx: CLIContext
    ) -> None:
        """Lista os problemas encontrados (linha+coluna)."""
        runner = CliRunner()
        result = runner.invoke(
            validate,
            [str(csv_com_erros), "--schema", str(schema_rico)],
            obj=cli_ctx,
        )
        # Algumas evidencias da listagem
        assert "Linha" in result.output
        assert "idade" in result.output or "cpf" in result.output

    def test_coluna_obrigatoria_faltando_exit_1(
        self, tmp_path: Path, schema_basico: Path, cli_ctx: CLIContext
    ) -> None:
        """CSV sem coluna obrigatoria: exit 1."""
        csv_path = tmp_path / "sem_coluna.csv"
        csv_path.write_text("apenas_isso\nx\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            validate,
            [str(csv_path), "--schema", str(schema_basico)],
            obj=cli_ctx,
        )
        assert result.exit_code == 1


# ============================================================
# Tests: Erros de schema/uso (exit 2)
# ============================================================


class TestValidateCommandSchemaErrors:
    """Erros que devem retornar exit 2 (configuracao)."""

    def test_arquivo_inexistente_click_rejeita(
        self, schema_basico: Path, cli_ctx: CLIContext
    ) -> None:
        """Click valida arquivo antes da funcao — exit 2."""
        runner = CliRunner()
        result = runner.invoke(
            validate,
            ["/caminho/que/nao/existe.csv", "--schema", str(schema_basico)],
            obj=cli_ctx,
        )
        # Click retorna 2 para erros de argumento
        assert result.exit_code == 2

    def test_schema_inexistente_click_rejeita(self, csv_valido: Path, cli_ctx: CLIContext) -> None:
        """Click valida schema antes da funcao — exit 2."""
        runner = CliRunner()
        result = runner.invoke(
            validate,
            [str(csv_valido), "--schema", "/nao/existe.yaml"],
            obj=cli_ctx,
        )
        assert result.exit_code == 2

    def test_schema_yaml_quebrado_exit_2(
        self,
        tmp_path: Path,
        csv_valido: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Schema com YAML invalido: exit 2 (erro de uso)."""
        schema_path = tmp_path / "ruim.yaml"
        schema_path.write_text("nao [eh ]} um yaml: valido", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            validate,
            [str(csv_valido), "--schema", str(schema_path)],
            obj=cli_ctx,
        )
        assert result.exit_code == 2


# ============================================================
# Tests: Reports em arquivo
# ============================================================


class TestValidateReports:
    """Geracao de --report-json e --report-csv."""

    def test_report_json_cria_arquivo(
        self,
        tmp_path: Path,
        csv_valido: Path,
        schema_basico: Path,
        cli_ctx: CLIContext,
    ) -> None:
        out_json = tmp_path / "out.json"

        runner = CliRunner()
        runner.invoke(
            validate,
            [
                str(csv_valido),
                "--schema",
                str(schema_basico),
                "--report-json",
                str(out_json),
            ],
            obj=cli_ctx,
        )
        assert out_json.exists()

    def test_report_json_conteudo_valido(
        self,
        tmp_path: Path,
        csv_com_erros: Path,
        schema_rico: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """JSON gerado e parseavel e tem estrutura esperada."""
        out_json = tmp_path / "out.json"

        runner = CliRunner()
        runner.invoke(
            validate,
            [
                str(csv_com_erros),
                "--schema",
                str(schema_rico),
                "--report-json",
                str(out_json),
            ],
            obj=cli_ctx,
        )

        with open(out_json, encoding="utf-8") as f:
            data = json.load(f)

        assert data["task_name"] == "validate"
        assert "issues" in data
        assert len(data["issues"]) > 0  # tem problemas

    def test_report_csv_cria_arquivo(
        self,
        tmp_path: Path,
        csv_valido: Path,
        schema_basico: Path,
        cli_ctx: CLIContext,
    ) -> None:
        out_csv = tmp_path / "out.csv"

        runner = CliRunner()
        runner.invoke(
            validate,
            [
                str(csv_valido),
                "--schema",
                str(schema_basico),
                "--report-csv",
                str(out_csv),
            ],
            obj=cli_ctx,
        )
        assert out_csv.exists()

    def test_ambos_reports_simultaneos(
        self,
        tmp_path: Path,
        csv_valido: Path,
        schema_basico: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """--report-json e --report-csv juntos: cria os dois."""
        out_json = tmp_path / "out.json"
        out_csv = tmp_path / "out.csv"

        runner = CliRunner()
        runner.invoke(
            validate,
            [
                str(csv_valido),
                "--schema",
                str(schema_basico),
                "--report-json",
                str(out_json),
                "--report-csv",
                str(out_csv),
            ],
            obj=cli_ctx,
        )
        assert out_json.exists()
        assert out_csv.exists()

    def test_report_em_subpasta_criada(
        self,
        tmp_path: Path,
        csv_valido: Path,
        schema_basico: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Cria diretorio pai se nao existir."""
        out_json = tmp_path / "subpasta" / "outra" / "rel.json"

        runner = CliRunner()
        runner.invoke(
            validate,
            [
                str(csv_valido),
                "--schema",
                str(schema_basico),
                "--report-json",
                str(out_json),
            ],
            obj=cli_ctx,
        )
        assert out_json.exists()


# ============================================================
# Tests: Dry-run
# ============================================================


class TestValidateDryRun:
    """Comportamento em modo --dry-run."""

    def test_dry_run_nao_cria_json(
        self,
        tmp_path: Path,
        csv_valido: Path,
        schema_basico: Path,
        cli_ctx_dry_run: CLIContext,
    ) -> None:
        """Dry-run nao deve criar o arquivo JSON."""
        out_json = tmp_path / "naodeveexistir.json"

        runner = CliRunner()
        runner.invoke(
            validate,
            [
                str(csv_valido),
                "--schema",
                str(schema_basico),
                "--report-json",
                str(out_json),
            ],
            obj=cli_ctx_dry_run,
        )
        assert not out_json.exists()

    def test_dry_run_nao_cria_csv(
        self,
        tmp_path: Path,
        csv_valido: Path,
        schema_basico: Path,
        cli_ctx_dry_run: CLIContext,
    ) -> None:
        out_csv = tmp_path / "naodeveexistir.csv"

        runner = CliRunner()
        runner.invoke(
            validate,
            [
                str(csv_valido),
                "--schema",
                str(schema_basico),
                "--report-csv",
                str(out_csv),
            ],
            obj=cli_ctx_dry_run,
        )
        assert not out_csv.exists()

    def test_dry_run_mostra_que_salvaria(
        self,
        tmp_path: Path,
        csv_valido: Path,
        schema_basico: Path,
        cli_ctx_dry_run: CLIContext,
    ) -> None:
        """Output indica que esta em dry-run."""
        out_json = tmp_path / "x.json"

        runner = CliRunner()
        result = runner.invoke(
            validate,
            [
                str(csv_valido),
                "--schema",
                str(schema_basico),
                "--report-json",
                str(out_json),
            ],
            obj=cli_ctx_dry_run,
        )
        assert "DRY-RUN" in result.output or "Salvaria" in result.output


# ============================================================
# Tests: Output / Formato
# ============================================================


class TestValidateOutput:
    """Verificacoes do output no terminal."""

    def test_mostra_caminho_do_arquivo(
        self, csv_valido: Path, schema_basico: Path, cli_ctx: CLIContext
    ) -> None:
        """Output menciona o arquivo validado."""
        runner = CliRunner()
        result = runner.invoke(
            validate,
            [str(csv_valido), "--schema", str(schema_basico)],
            obj=cli_ctx,
        )
        # O nome do arquivo deve aparecer (path completo ou parcial)
        assert csv_valido.name in result.output

    def test_mostra_caminho_do_schema(
        self, csv_valido: Path, schema_basico: Path, cli_ctx: CLIContext
    ) -> None:
        """Output menciona o schema carregado."""
        runner = CliRunner()
        result = runner.invoke(
            validate,
            [str(csv_valido), "--schema", str(schema_basico)],
            obj=cli_ctx,
        )
        assert schema_basico.name in result.output

    def test_max_issues_limita_listagem(
        self,
        tmp_path: Path,
        schema_basico: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Com --max-issues 1, lista no maximo 1 issue."""
        # CSV com varias linhas problematicas
        csv_path = tmp_path / "muitos.csv"
        csv_path.write_text(
            "nome,idade\nA,abc\nB,xyz\nC,foo\nD,bar\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(
            validate,
            [
                str(csv_path),
                "--schema",
                str(schema_basico),
                "--max-issues",
                "1",
            ],
            obj=cli_ctx,
        )
        # Deve mostrar "e mais X" indicando truncamento
        assert "e mais" in result.output

    def test_max_issues_zero_nao_lista_individuais(
        self,
        tmp_path: Path,
        schema_basico: Path,
        cli_ctx: CLIContext,
    ) -> None:
        """Com --max-issues 0, mostra so estatisticas."""
        csv_path = tmp_path / "x.csv"
        csv_path.write_text(
            "nome,idade\nA,abc\nB,xyz\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(
            validate,
            [
                str(csv_path),
                "--schema",
                str(schema_basico),
                "--max-issues",
                "0",
            ],
            obj=cli_ctx,
        )
        # Nao deve listar [ERROR] tags individuais
        assert "[ERROR]" not in result.output

    def test_max_issues_negativo_rejeitado(
        self, csv_valido: Path, schema_basico: Path, cli_ctx: CLIContext
    ) -> None:
        """Click rejeita --max-issues -1 (IntRange min=0)."""
        runner = CliRunner()
        result = runner.invoke(
            validate,
            [
                str(csv_valido),
                "--schema",
                str(schema_basico),
                "--max-issues",
                "-1",
            ],
            obj=cli_ctx,
        )
        assert result.exit_code == 2  # erro de uso
