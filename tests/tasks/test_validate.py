"""Testes para autotarefas.tasks.validate."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.validate import (
    ColumnSchema,
    Schema,
    ValidateTask,
    load_schema,
)

# ============================================================
# Helpers
# ============================================================


def _make_csv(tmp_path: Path, content: str, name: str = "test.csv") -> Path:
    """Cria CSV temporário com conteúdo dado."""
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _make_schema_yaml(tmp_path: Path, content: str) -> Path:
    """Cria YAML temporário."""
    path = tmp_path / "schema.yaml"
    path.write_text(content, encoding="utf-8")
    return path


# ============================================================
# Tests: ColumnSchema (pydantic)
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


# ============================================================
# Tests: Schema
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
        schema = Schema(
            columns=[
                ColumnSchema(name="a"),
                ColumnSchema(name="b"),
            ]
        )
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
# Tests: load_schema
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
        """YAML deve ser um mapping (dict), não lista ou string."""
        path = _make_schema_yaml(tmp_path, "- item1\n- item2")
        with pytest.raises(ValidationError, match="mapeamento"):
            load_schema(path)

    def test_schema_sem_columns_levanta(self, tmp_path: Path) -> None:
        path = _make_schema_yaml(tmp_path, "outras_coisas: []")
        with pytest.raises(ValidationError, match="invalido"):
            load_schema(path)


# ============================================================
# Tests: ValidateTask — Sucesso e estrutura
# ============================================================


class TestValidateTaskSucesso:
    """Testes do caminho feliz."""

    def test_csv_valido_retorna_success(self, tmp_path: Path) -> None:
        csv = "nome,idade\nAlice,30\nBob,25\n"
        path = _make_csv(tmp_path, csv)
        schema = Schema(
            columns=[
                ColumnSchema(name="nome"),
                ColumnSchema(name="idade", type="int"),
            ]
        )
        task = ValidateTask(file_path=path, schema=schema)
        result = task.run()

        assert result.is_success
        assert result.rows_affected == 2
        assert result.data["rows"] == 2
        assert "nome" in result.data["columns"]
        assert "idade" in result.data["columns"]

    def test_csv_com_coluna_extra_ok(self, tmp_path: Path) -> None:
        """Colunas extras (fora do schema) não causam erro."""
        csv = "nome,idade,extra\nAlice,30,foo\n"
        path = _make_csv(tmp_path, csv)
        schema = Schema(columns=[ColumnSchema(name="nome")])
        task = ValidateTask(file_path=path, schema=schema)
        result = task.run()
        assert result.is_success

    def test_csv_vazio_mas_com_header_ok(self, tmp_path: Path) -> None:
        csv = "nome,idade\n"  # só cabeçalho
        path = _make_csv(tmp_path, csv)
        schema = Schema(columns=[ColumnSchema(name="nome")])
        task = ValidateTask(file_path=path, schema=schema)
        result = task.run()
        assert result.is_success
        assert result.rows_affected == 0


# ============================================================
# Tests: ValidateTask — Erros de estrutura
# ============================================================


class TestValidateTaskErros:
    """Testes dos cenários de falha."""

    def test_arquivo_inexistente(self, tmp_path: Path) -> None:
        """AutoTarefasError → run() retorna FAILURE."""
        schema = Schema(columns=[ColumnSchema(name="x")])
        task = ValidateTask(
            file_path=tmp_path / "inexistente.csv",
            schema=schema,
        )
        result = task.run()
        assert result.is_failure
        assert "nao encontrado" in (result.error_message or "")

    def test_extensao_nao_suportada(self, tmp_path: Path) -> None:
        path = tmp_path / "teste.txt"
        path.write_text("oi", encoding="utf-8")
        schema = Schema(columns=[ColumnSchema(name="x")])
        task = ValidateTask(file_path=path, schema=schema)
        result = task.run()
        assert result.is_failure
        assert "Extensao" in (result.error_message or "")

    def test_coluna_obrigatoria_faltando(self, tmp_path: Path) -> None:
        csv = "nome\nAlice\n"
        path = _make_csv(tmp_path, csv)
        schema = Schema(
            columns=[
                ColumnSchema(name="nome"),
                ColumnSchema(name="idade", required=True),
            ]
        )
        task = ValidateTask(file_path=path, schema=schema)
        result = task.run()

        assert result.is_failure
        assert result.error_type == "MissingColumnsError"
        assert "idade" in result.data["missing"]
        assert "nome" not in result.data["missing"]

    def test_coluna_opcional_faltando_ok(self, tmp_path: Path) -> None:
        """Colunas required=False podem estar faltando."""
        csv = "nome\nAlice\n"
        path = _make_csv(tmp_path, csv)
        schema = Schema(
            columns=[
                ColumnSchema(name="nome"),
                ColumnSchema(name="email", required=False),
            ]
        )
        task = ValidateTask(file_path=path, schema=schema)
        result = task.run()
        assert result.is_success


# ============================================================
# Tests: ValidateTask — Encodings
# ============================================================


class TestValidateTaskEncodings:
    """Testes de tolerância a múltiplos encodings."""

    def test_csv_utf8(self, tmp_path: Path) -> None:
        csv = "nome\nJoão\nMaría\n"
        path = tmp_path / "test.csv"
        path.write_text(csv, encoding="utf-8")
        schema = Schema(columns=[ColumnSchema(name="nome")])
        task = ValidateTask(file_path=path, schema=schema)
        assert task.run().is_success

    def test_csv_latin1(self, tmp_path: Path) -> None:
        """CSV em latin-1 também deve ser carregado."""
        path = tmp_path / "test.csv"
        path.write_text("nome\nJoão\nMaría\n", encoding="latin-1")
        schema = Schema(columns=[ColumnSchema(name="nome")])
        task = ValidateTask(file_path=path, schema=schema)
        assert task.run().is_success

    def test_csv_utf8_com_bom(self, tmp_path: Path) -> None:
        """CSV em UTF-8 com BOM (gerado pelo Excel)."""
        path = tmp_path / "test.csv"
        path.write_text("nome\nAlice\n", encoding="utf-8-sig")
        schema = Schema(columns=[ColumnSchema(name="nome")])
        task = ValidateTask(file_path=path, schema=schema)
        assert task.run().is_success


# ============================================================
# Tests: ValidateTask — Auto-detect delimitador
# ============================================================


class TestValidateTaskDelimitador:
    """Testes de auto-detecção de delimitador (sep=None)."""

    def test_csv_virgula(self, tmp_path: Path) -> None:
        path = _make_csv(tmp_path, "a,b\n1,2\n")
        schema = Schema(columns=[ColumnSchema(name="a")])
        assert ValidateTask(path, schema).run().is_success

    def test_csv_ponto_e_virgula(self, tmp_path: Path) -> None:
        """Padrão BR/Excel."""
        path = _make_csv(tmp_path, "a;b\n1;2\n")
        schema = Schema(columns=[ColumnSchema(name="a")])
        assert ValidateTask(path, schema).run().is_success

    def test_tsv_tab(self, tmp_path: Path) -> None:
        path = _make_csv(tmp_path, "a\tb\n1\t2\n", name="test.tsv")
        schema = Schema(columns=[ColumnSchema(name="a")])
        assert ValidateTask(path, schema).run().is_success


# ============================================================
# Tests: ValidateTask — Atributos
# ============================================================


class TestValidateTaskAtributos:
    """Testes dos atributos da task."""

    def test_name(self) -> None:
        assert ValidateTask.name == "validate"

    def test_description(self) -> None:
        assert ValidateTask.description

    def test_dry_run_padrao_false(self, tmp_path: Path) -> None:
        path = _make_csv(tmp_path, "a\n1\n")
        schema = Schema(columns=[ColumnSchema(name="a")])
        task = ValidateTask(path, schema)
        assert task.dry_run is False

    def test_dry_run_propagado(self, tmp_path: Path) -> None:
        path = _make_csv(tmp_path, "a\n1\n")
        schema = Schema(columns=[ColumnSchema(name="a")])
        task = ValidateTask(path, schema, dry_run=True)
        result = task.run()
        assert result.dry_run is True
