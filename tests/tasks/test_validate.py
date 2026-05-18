"""Testes para autotarefas.tasks.validate (Parte 3.1 + 3.2)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from autotarefas.core.base import TaskResult
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.validate import (
    ColumnSchema,
    Schema,
    ValidateTask,
    load_schema,
)
from autotarefas.tasks.validators import (
    CNPJValidator,
    CPFValidator,
    EnumValidator,
    RangeValidator,
    RegexValidator,
    TypeValidator,
)

# ============================================================
# Helpers
# ============================================================


def _make_csv(tmp_path: Path, content: str, name: str = "test.csv") -> Path:
    """Cria CSV temporario com conteudo dado."""
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _make_schema_yaml(tmp_path: Path, content: str) -> Path:
    """Cria YAML temporario."""
    path = tmp_path / "schema.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def _run_validation(
    tmp_path: Path,
    csv: str,
    schema: Schema,
    name: str = "test.csv",
) -> TaskResult:
    """Helper: cria CSV temporario e roda validacao. Retorna o TaskResult."""
    path = _make_csv(tmp_path, csv, name)
    return ValidateTask(file_path=path, schema=schema).run()


# ============================================================
# Tests: ColumnSchema (Parte 3.1 + novos da 3.2)
# ============================================================


class TestColumnSchema:
    """Testes do modelo ColumnSchema."""

    def test_basico(self) -> None:
        col = ColumnSchema(name="nome")
        assert col.name == "nome"
        assert col.required is True
        assert col.type == "str"
        assert col.nullable is False

    def test_nome_vazio_levanta(self) -> None:
        with pytest.raises(PydanticValidationError, match="at least 1 character"):
            ColumnSchema(name="")

    def test_type_invalido_levanta(self) -> None:
        with pytest.raises(PydanticValidationError, match="Input should be"):
            ColumnSchema(name="x", type="objeto")  # type: ignore[arg-type]

    def test_required_false(self) -> None:
        col = ColumnSchema(name="x", required=False)
        assert col.required is False

    # ===== Novos campos da Parte 3.2 =====

    def test_min_max_value_aceitos(self) -> None:
        col = ColumnSchema(name="x", type="int", min_value=0, max_value=150)
        assert col.min_value == 0
        assert col.max_value == 150

    def test_regex_aceito(self) -> None:
        col = ColumnSchema(name="cep", regex=r"\d{5}-?\d{3}")
        assert col.regex == r"\d{5}-?\d{3}"

    def test_regex_message_aceita(self) -> None:
        col = ColumnSchema(
            name="cep",
            regex=r"\d{5}-?\d{3}",
            regex_message="CEP invalido",
        )
        assert col.regex_message == "CEP invalido"

    def test_enum_values_lista_vira_tuple(self) -> None:
        """Pydantic converte list -> tuple automaticamente."""
        col = ColumnSchema(name="uf", enum_values=["SP", "RJ"])  # type: ignore[arg-type]
        assert col.enum_values == ("SP", "RJ")
        assert isinstance(col.enum_values, tuple)

    def test_validator_br_cpf_aceito(self) -> None:
        col = ColumnSchema(name="cpf", validator_br="cpf")
        assert col.validator_br == "cpf"

    def test_validator_br_cnpj_aceito(self) -> None:
        col = ColumnSchema(name="cnpj", validator_br="cnpj")
        assert col.validator_br == "cnpj"

    def test_validator_br_invalido_levanta(self) -> None:
        with pytest.raises(PydanticValidationError):
            ColumnSchema(name="x", validator_br="rg")  # type: ignore[arg-type]


# ============================================================
# Tests: ColumnSchema.get_validators (NOVO - Parte 3.2)
# ============================================================


class TestColumnSchemaGetValidators:
    """Testes do metodo get_validators() — geracao de validators."""

    def test_str_sem_extras_lista_vazia(self) -> None:
        """Coluna tipo str sem outras regras: nenhum validator."""
        col = ColumnSchema(name="x", type="str")
        assert col.get_validators() == []

    def test_int_gera_type_validator(self) -> None:
        col = ColumnSchema(name="x", type="int")
        validators = col.get_validators()
        assert len(validators) == 1
        assert isinstance(validators[0], TypeValidator)
        assert validators[0].expected_type == "int"

    @pytest.mark.parametrize("type_name", ["float", "date", "bool"])
    def test_outros_tipos_geram_type_validator(self, type_name: str) -> None:
        col = ColumnSchema(name="x", type=type_name)  # type: ignore[arg-type]
        validators = col.get_validators()
        assert any(isinstance(v, TypeValidator) for v in validators)

    def test_min_value_gera_range_validator(self) -> None:
        col = ColumnSchema(name="x", min_value=0)
        validators = col.get_validators()
        assert any(isinstance(v, RangeValidator) for v in validators)

    def test_max_value_gera_range_validator(self) -> None:
        col = ColumnSchema(name="x", max_value=100)
        validators = col.get_validators()
        assert any(isinstance(v, RangeValidator) for v in validators)

    def test_min_e_max_geram_um_range_validator(self) -> None:
        """min_value E max_value juntos geram UM unico RangeValidator."""
        col = ColumnSchema(name="x", min_value=0, max_value=100)
        validators = col.get_validators()
        ranges = [v for v in validators if isinstance(v, RangeValidator)]
        assert len(ranges) == 1
        assert ranges[0].min_value == 0
        assert ranges[0].max_value == 100

    def test_regex_gera_regex_validator(self) -> None:
        col = ColumnSchema(name="x", regex=r"\d+")
        validators = col.get_validators()
        assert any(isinstance(v, RegexValidator) for v in validators)

    def test_regex_com_message_custom(self) -> None:
        col = ColumnSchema(name="x", regex=r"\d+", regex_message="Apenas digitos")
        validators = col.get_validators()
        regex_v = next(v for v in validators if isinstance(v, RegexValidator))
        assert regex_v.message == "Apenas digitos"

    def test_enum_gera_enum_validator(self) -> None:
        col = ColumnSchema(name="x", enum_values=("A", "B"))
        validators = col.get_validators()
        assert any(isinstance(v, EnumValidator) for v in validators)

    def test_cpf_gera_cpf_validator(self) -> None:
        col = ColumnSchema(name="x", validator_br="cpf")
        validators = col.get_validators()
        assert any(isinstance(v, CPFValidator) for v in validators)

    def test_cnpj_gera_cnpj_validator(self) -> None:
        col = ColumnSchema(name="x", validator_br="cnpj")
        validators = col.get_validators()
        assert any(isinstance(v, CNPJValidator) for v in validators)

    def test_multiplos_validators_combinados(self) -> None:
        """type + range + cpf -> 3 validators."""
        col = ColumnSchema(
            name="x",
            type="int",
            min_value=0,
            max_value=99999999999,
            validator_br="cpf",
        )
        validators = col.get_validators()
        # 3 validators: Type, Range, CPF
        assert len(validators) == 3
        assert any(isinstance(v, TypeValidator) for v in validators)
        assert any(isinstance(v, RangeValidator) for v in validators)
        assert any(isinstance(v, CPFValidator) for v in validators)


# ============================================================
# Tests: Schema (Parte 3.1)
# ============================================================


class TestSchema:
    """Testes do modelo Schema."""

    def test_basico(self) -> None:
        schema = Schema(
            columns=[
                ColumnSchema(name="nome"),
                ColumnSchema(name="idade", type="int"),
            ]
        )
        assert len(schema.columns) == 2

    def test_sem_colunas_levanta(self) -> None:
        with pytest.raises(PydanticValidationError, match="at least 1 item"):
            Schema(columns=[])

    def test_column_names(self) -> None:
        schema = Schema(columns=[ColumnSchema(name="a"), ColumnSchema(name="b")])
        assert schema.column_names == ["a", "b"]

    def test_required_columns(self) -> None:
        schema = Schema(
            columns=[
                ColumnSchema(name="a", required=True),
                ColumnSchema(name="b", required=False),
                ColumnSchema(name="c", required=True),
            ]
        )
        assert schema.required_columns == ["a", "c"]

    def test_get_column_existente(self) -> None:
        schema = Schema(columns=[ColumnSchema(name="x")])
        col = schema.get_column("x")
        assert col is not None
        assert col.name == "x"

    def test_get_column_inexistente_retorna_none(self) -> None:
        schema = Schema(columns=[ColumnSchema(name="x")])
        assert schema.get_column("y") is None


# ============================================================
# Tests: load_schema (Parte 3.1 + novo na 3.2)
# ============================================================


class TestLoadSchema:
    """Testes de carregamento de schema YAML."""

    def test_carrega_yaml_basico(self, tmp_path: Path) -> None:
        yaml_content = """
columns:
  - name: nome
    required: true
    type: str
  - name: idade
    type: int
"""
        path = _make_schema_yaml(tmp_path, yaml_content)
        schema = load_schema(path)
        assert len(schema.columns) == 2
        assert schema.columns[0].name == "nome"
        assert schema.columns[1].type == "int"

    def test_arquivo_inexistente_levanta(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="nao encontrado"):
            load_schema(tmp_path / "nao-existe.yaml")

    def test_yaml_invalido_levanta(self, tmp_path: Path) -> None:
        path = _make_schema_yaml(tmp_path, "isto: [esta {quebrado")
        with pytest.raises(ValidationError, match="invalido"):
            load_schema(path)

    def test_yaml_nao_dict_levanta(self, tmp_path: Path) -> None:
        path = _make_schema_yaml(tmp_path, "- item1\n- item2")
        with pytest.raises(ValidationError, match="mapeamento"):
            load_schema(path)

    def test_schema_sem_columns_levanta(self, tmp_path: Path) -> None:
        path = _make_schema_yaml(tmp_path, "outras_coisas: []")
        with pytest.raises(ValidationError, match="invalido"):
            load_schema(path)

    # ===== Novo: Schema rico com todos os campos =====

    def test_carrega_schema_rico_com_todos_campos(self, tmp_path: Path) -> None:
        """Schema YAML com TODOS os campos da Parte 3.2."""
        yaml_content = """
columns:
  - name: nome
    type: str
    nullable: false

  - name: idade
    type: int
    min_value: 0
    max_value: 150

  - name: cpf
    validator_br: cpf

  - name: cnpj
    validator_br: cnpj

  - name: uf
    enum_values: [SP, RJ, MG]

  - name: cep
    regex: '\\d{5}-?\\d{3}'
    regex_message: CEP invalido
"""
        path = _make_schema_yaml(tmp_path, yaml_content)
        schema = load_schema(path)

        assert len(schema.columns) == 6

        # Verifica cada coluna
        idade = schema.get_column("idade")
        assert idade is not None
        assert idade.min_value == 0
        assert idade.max_value == 150

        cpf = schema.get_column("cpf")
        assert cpf is not None
        assert cpf.validator_br == "cpf"

        uf = schema.get_column("uf")
        assert uf is not None
        assert uf.enum_values == ("SP", "RJ", "MG")

        cep = schema.get_column("cep")
        assert cep is not None
        assert cep.regex == r"\d{5}-?\d{3}"


# ============================================================
# Tests: ValidateTask — Estrutura (Parte 3.1)
# ============================================================


class TestValidateTaskEstrutura:
    """Testes de validacao estrutural (estrutura: extensao, encoding, colunas)."""

    def test_csv_valido_retorna_success(self, tmp_path: Path) -> None:
        csv = "nome,idade\nAlice,30\nBob,25\n"
        schema = Schema(
            columns=[
                ColumnSchema(name="nome"),
                ColumnSchema(name="idade", type="int", nullable=True),
            ]
        )
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_success
        assert result.rows_affected == 2

    def test_csv_com_coluna_extra_ok(self, tmp_path: Path) -> None:
        """Colunas extras (fora do schema) nao causam erro."""
        csv = "nome,idade,extra\nAlice,30,foo\n"
        schema = Schema(columns=[ColumnSchema(name="nome")])
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_success

    def test_csv_vazio_mas_com_header_ok(self, tmp_path: Path) -> None:
        csv = "nome,idade\n"
        schema = Schema(columns=[ColumnSchema(name="nome", required=False)])
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_success
        assert result.rows_affected == 0

    def test_arquivo_inexistente(self, tmp_path: Path) -> None:
        schema = Schema(columns=[ColumnSchema(name="x")])
        task = ValidateTask(file_path=tmp_path / "inexistente.csv", schema=schema)
        result = task.run()
        assert result.is_failure
        assert "nao encontrado" in (result.error_message or "")

    def test_extensao_nao_suportada(self, tmp_path: Path) -> None:
        path = tmp_path / "teste.txt"
        path.write_text("oi", encoding="utf-8")
        schema = Schema(columns=[ColumnSchema(name="x")])
        result = ValidateTask(file_path=path, schema=schema).run()
        assert result.is_failure
        assert "Extensao" in (result.error_message or "")

    def test_coluna_obrigatoria_faltando(self, tmp_path: Path) -> None:
        csv = "nome\nAlice\n"
        schema = Schema(
            columns=[
                ColumnSchema(name="nome"),
                ColumnSchema(name="idade", required=True),
            ]
        )
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_failure
        assert result.error_type == "MissingColumnsError"
        assert "idade" in result.data["missing"]

    def test_coluna_opcional_faltando_ok(self, tmp_path: Path) -> None:
        csv = "nome\nAlice\n"
        schema = Schema(
            columns=[
                ColumnSchema(name="nome"),
                ColumnSchema(name="email", required=False),
            ]
        )
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_success


# ============================================================
# Tests: ValidateTask — Encodings (Parte 3.1)
# ============================================================


class TestValidateTaskEncodings:
    """Testes de tolerancia a multiplos encodings."""

    def test_csv_utf8(self, tmp_path: Path) -> None:
        path = tmp_path / "test.csv"
        path.write_text("nome\nJoão\nMaría\n", encoding="utf-8")
        schema = Schema(columns=[ColumnSchema(name="nome")])
        assert ValidateTask(path, schema).run().is_success

    def test_csv_latin1(self, tmp_path: Path) -> None:
        path = tmp_path / "test.csv"
        path.write_text("nome\nJoão\nMaría\n", encoding="latin-1")
        schema = Schema(columns=[ColumnSchema(name="nome")])
        assert ValidateTask(path, schema).run().is_success

    def test_csv_utf8_com_bom(self, tmp_path: Path) -> None:
        path = tmp_path / "test.csv"
        path.write_text("nome\nAlice\n", encoding="utf-8-sig")
        schema = Schema(columns=[ColumnSchema(name="nome")])
        assert ValidateTask(path, schema).run().is_success


# ============================================================
# Tests: ValidateTask — Delimitador (Parte 3.1)
# ============================================================


class TestValidateTaskDelimitador:
    """Testes de auto-deteccao de delimitador."""

    def test_csv_virgula(self, tmp_path: Path) -> None:
        schema = Schema(columns=[ColumnSchema(name="a")])
        result = _run_validation(tmp_path, "a,b\n1,2\n", schema)
        assert result.is_success

    def test_csv_ponto_e_virgula(self, tmp_path: Path) -> None:
        schema = Schema(columns=[ColumnSchema(name="a")])
        result = _run_validation(tmp_path, "a;b\n1;2\n", schema)
        assert result.is_success

    def test_tsv_tab(self, tmp_path: Path) -> None:
        schema = Schema(columns=[ColumnSchema(name="a")])
        result = _run_validation(tmp_path, "a\tb\n1\t2\n", schema, name="test.tsv")
        assert result.is_success


# ============================================================
# Tests: ValidateTask — Nullability (NOVO Parte 3.2)
# ============================================================


class TestValidateTaskNullability:
    """Testes do controle de nullability (nullable: true/false)."""

    def test_nullable_true_aceita_vazio(self, tmp_path: Path) -> None:
        csv = "nome,email\nAlice,\nBob,bob@x.com\n"
        schema = Schema(
            columns=[
                ColumnSchema(name="nome"),
                ColumnSchema(name="email", nullable=True),
            ]
        )
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_success

    def test_nullable_false_e_vazio_gera_issue(self, tmp_path: Path) -> None:
        """Coluna nao-nullable com valor vazio: issue na linha."""
        csv = 'nome\nAlice\n""\nCarla\n'  # linha 3 com celula vazia
        schema = Schema(columns=[ColumnSchema(name="nome", nullable=False)])
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_failure
        # linha 3 do arquivo (header=1, Alice=2, vazio=3)
        assert any(i["line"] == 3 and "obrigatorio" in i["message"] for i in result.data["issues"])

    def test_nullable_false_e_so_espacos_gera_issue(self, tmp_path: Path) -> None:
        """Valor com so whitespace conta como vazio."""
        csv = 'nome\nAlice\n"   "\n'
        schema = Schema(columns=[ColumnSchema(name="nome", nullable=False)])
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_failure

    def test_nullable_false_mas_valor_presente_passa(self, tmp_path: Path) -> None:
        csv = "nome\nAlice\nBob\n"
        schema = Schema(columns=[ColumnSchema(name="nome", nullable=False)])
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_success


# ============================================================
# Tests: ValidateTask — Conteudo (NOVO Parte 3.2)
# ============================================================


class TestValidateTaskConteudo:
    """Testes de validacao de conteudo celula-a-celula."""

    def test_dados_validos_sem_issues(self, tmp_path: Path) -> None:
        csv = "nome,idade\nAlice,30\nBob,25\n"
        schema = Schema(
            columns=[
                ColumnSchema(name="nome"),
                ColumnSchema(name="idade", type="int", min_value=0, max_value=150),
            ]
        )
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_success
        assert result.data["total_issues"] == 0

    def test_type_int_invalido_gera_issue(self, tmp_path: Path) -> None:
        csv = "idade\n30\nabc\n"
        schema = Schema(columns=[ColumnSchema(name="idade", type="int", nullable=True)])
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_failure
        issues = result.data["issues"]
        assert len(issues) == 1
        assert issues[0]["line"] == 3
        assert issues[0]["column"] == "idade"
        assert "int valido" in issues[0]["message"]

    def test_cpf_invalido_gera_issue(self, tmp_path: Path) -> None:
        csv = "cpf\n529.982.247-25\n111.111.111-11\n"
        schema = Schema(columns=[ColumnSchema(name="cpf", validator_br="cpf")])
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_failure
        assert any(i["line"] == 3 and "CPF invalido" in i["message"] for i in result.data["issues"])

    def test_cnpj_invalido_gera_issue(self, tmp_path: Path) -> None:
        csv = "cnpj\n11.222.333/0001-81\n00.000.000/0000-00\n"
        schema = Schema(columns=[ColumnSchema(name="cnpj", validator_br="cnpj")])
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_failure
        assert any("CNPJ invalido" in i["message"] for i in result.data["issues"])

    def test_range_acima_max_gera_issue(self, tmp_path: Path) -> None:
        csv = "idade\n30\n200\n"
        schema = Schema(
            columns=[
                ColumnSchema(name="idade", type="int", min_value=0, max_value=150, nullable=True)
            ]
        )
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_failure
        assert any("maior que o maximo" in i["message"] for i in result.data["issues"])

    def test_range_abaixo_min_gera_issue(self, tmp_path: Path) -> None:
        csv = "idade\n30\n-5\n"
        schema = Schema(
            columns=[
                ColumnSchema(name="idade", type="int", min_value=0, max_value=150, nullable=True)
            ]
        )
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_failure
        assert any("menor que o minimo" in i["message"] for i in result.data["issues"])

    def test_enum_fora_da_lista_gera_issue(self, tmp_path: Path) -> None:
        csv = "uf\nSP\nXX\n"
        schema = Schema(
            columns=[ColumnSchema(name="uf", enum_values=("SP", "RJ", "MG"), nullable=True)]
        )
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_failure
        assert any("nao esta entre os aceitos" in i["message"] for i in result.data["issues"])

    def test_regex_no_match_gera_issue(self, tmp_path: Path) -> None:
        csv = "cep\n01310-100\nabc\n"
        schema = Schema(
            columns=[
                ColumnSchema(
                    name="cep",
                    regex=r"\d{5}-?\d{3}",
                    regex_message="CEP invalido",
                    nullable=True,
                )
            ]
        )
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_failure
        assert any("CEP invalido" in i["message"] for i in result.data["issues"])

    def test_acumula_multiplos_erros(self, tmp_path: Path) -> None:
        """Multiplos validators na mesma linha geram multiplos issues."""
        csv = "idade,cpf\n200,111.111.111-11\n"
        schema = Schema(
            columns=[
                ColumnSchema(name="idade", type="int", min_value=0, max_value=150, nullable=True),
                ColumnSchema(name="cpf", validator_br="cpf", nullable=True),
            ]
        )
        result = _run_validation(tmp_path, csv, schema)
        assert result.is_failure
        # 2 issues na linha 2: range + cpf
        assert result.data["total_issues"] == 2

    def test_data_inclui_metadados(self, tmp_path: Path) -> None:
        """O TaskResult.data tem todos os campos esperados pra Parte 3.3."""
        csv = "x\n1\n"
        schema = Schema(columns=[ColumnSchema(name="x", nullable=True)])
        result = _run_validation(tmp_path, csv, schema)
        assert "file" in result.data
        assert "rows" in result.data
        assert "columns" in result.data
        assert "total_issues" in result.data
        assert "total_errors" in result.data
        assert "total_warnings" in result.data
        assert "issues" in result.data


# ============================================================
# Tests: Helpers estaticos (NOVO Parte 3.2)
# ============================================================


class TestValidateTaskHelpers:
    """Testes dos metodos auxiliares estaticos."""

    def test_cell_to_str_string(self) -> None:
        assert ValidateTask._cell_to_str("oi") == "oi"

    def test_cell_to_str_int(self) -> None:
        assert ValidateTask._cell_to_str(42) == "42"

    def test_cell_to_str_float(self) -> None:
        assert ValidateTask._cell_to_str(3.14) == "3.14"

    def test_cell_to_str_nan_vira_vazio(self) -> None:
        assert ValidateTask._cell_to_str(math.nan) == ""

    def test_cell_to_str_none_vira_vazio(self) -> None:
        assert ValidateTask._cell_to_str(None) == ""

    def test_issue_to_dict_basico(self) -> None:
        from autotarefas.tasks.issues import (
            IssueSeverity,
            ValidationIssue,
        )

        issue = ValidationIssue(
            line=5,
            column="cpf",
            message="CPF invalido",
            severity=IssueSeverity.ERROR,
            value="111",
        )
        d: dict[str, Any] = ValidateTask._issue_to_dict(issue)
        assert d["line"] == 5
        assert d["column"] == "cpf"
        assert d["message"] == "CPF invalido"
        assert d["severity"] == "error"
        assert d["value"] == "111"


# ============================================================
# Tests: ValidateTask — Atributos (Parte 3.1)
# ============================================================


class TestValidateTaskAtributos:
    """Testes dos atributos da task."""

    def test_name(self) -> None:
        assert ValidateTask.name == "validate"

    def test_description(self) -> None:
        assert ValidateTask.description

    def test_dry_run_padrao_false(self, tmp_path: Path) -> None:
        path = _make_csv(tmp_path, "a\n1\n")
        schema = Schema(columns=[ColumnSchema(name="a", nullable=True)])
        task = ValidateTask(path, schema)
        assert task.dry_run is False

    def test_dry_run_propagado(self, tmp_path: Path) -> None:
        path = _make_csv(tmp_path, "a\n1\n")
        schema = Schema(columns=[ColumnSchema(name="a", nullable=True)])
        task = ValidateTask(path, schema, dry_run=True)
        result = task.run()
        assert result.dry_run is True
