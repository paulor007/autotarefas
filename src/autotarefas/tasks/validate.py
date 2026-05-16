"""
Task de validação de planilhas (CSV, TSV, Excel).

Esta é a **primeira subclasse real** de ``BaseTask`` do projeto.
Valida arquivos contra um schema YAML, reportando erros por linha/coluna.

Parte 3.1 (atual): estrutura base — carregamento e validação de colunas.
Parte 3.2: validadores específicos (tipo, regex, CPF/CNPJ).
Parte 3.3: relatório de erros + comando CLI.

Uso:
    from pathlib import Path
    from autotarefas.tasks.validate import (
        Schema, ColumnSchema, ValidateTask, load_schema
    )

    schema = load_schema(Path("schema.yaml"))
    task = ValidateTask(file_path=Path("dados.csv"), schema=schema)
    result = task.run()

    if result.is_success:
        print(f"OK! {result.rows_affected} linhas validadas.")
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, Literal

import pandas as pd
import yaml
from pydantic import BaseModel, Field

from autotarefas.core import BaseTask, TaskResult, TaskStatus, ValidationError

# ============================================================
# Schema (modelo declarativo das regras de validação)
# ============================================================

#: Tipos suportados pelas colunas. Será expandido na Parte 3.2.
ColumnType = Literal["str", "int", "float", "date", "bool"]


class ColumnSchema(BaseModel):
    """
    Define as regras de validação de uma coluna.

    Attributes:
        name: Nome da coluna (case-sensitive, deve bater com cabeçalho).
        required: Se True (default), a coluna deve estar presente no arquivo.
        type: Tipo esperado dos valores (default "str"). Parte 3.2 valida.
        nullable: Se True, valores vazios são permitidos (default False).
    """

    name: str = Field(..., min_length=1)
    required: bool = True
    type: ColumnType = "str"
    nullable: bool = False


class Schema(BaseModel):
    """
    Schema completo de validação (carregado de YAML).

    Attributes:
        columns: Lista de definições de coluna (mínimo 1).
    """

    columns: list[ColumnSchema] = Field(..., min_length=1)

    @property
    def column_names(self) -> list[str]:
        """Nomes de todas as colunas declaradas no schema."""
        return [c.name for c in self.columns]

    @property
    def required_columns(self) -> list[str]:
        """Nomes das colunas obrigatórias."""
        return [c.name for c in self.columns if c.required]

    def get_column(self, name: str) -> ColumnSchema | None:
        """Busca coluna por nome. Retorna None se não encontrar."""
        for col in self.columns:
            if col.name == name:
                return col
        return None


def load_schema(path: Path) -> Schema:
    """
    Carrega um Schema a partir de arquivo YAML.

    Args:
        path: Caminho do arquivo YAML.

    Returns:
        Schema validado.

    Raises:
        ValidationError: Se o arquivo não existe ou o YAML é inválido.
    """
    if not path.exists():
        raise ValidationError(f"Schema nao encontrado: {path}", field="schema_path")

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValidationError(f"YAML invalido em {path}: {e}", field="schema_yaml") from e

    if not isinstance(data, dict):
        raise ValidationError(
            f"Schema deve ser um mapeamento YAML (dict), nao {type(data).__name__}",
            field="schema_yaml",
        )

    try:
        return Schema.model_validate(data)
    except Exception as e:
        raise ValidationError(f"Schema invalido em {path}: {e}", field="schema_validation") from e


# ============================================================
# ValidateTask
# ============================================================


class ValidateTask(BaseTask):
    """
    Valida uma planilha (CSV, TSV ou Excel) contra um Schema.

    **Parte 3.1**: valida apenas estrutura (extensão, decodificação, colunas
    obrigatórias presentes). Validações de conteúdo vêm na Parte 3.2.
    """

    name = "validate"
    description = "Valida planilha CSV/Excel contra schema YAML"

    #: Extensões suportadas.
    SUPPORTED_EXTENSIONS: ClassVar[frozenset[str]] = frozenset({".csv", ".tsv", ".xlsx", ".xls"})

    #: Encodings tentados para CSV (em ordem). utf-8-sig lida com BOM
    #: e funciona como UTF-8 normal quando não há BOM.
    CSV_ENCODINGS: ClassVar[tuple[str, ...]] = (
        "utf-8-sig",  # PRIMEIRO: lida com BOM e UTF-8 sem BOM
        "latin-1",
        "cp1252",  # Windows
    )

    #: Delimitadores possíveis para auto-detecção (csv.Sniffer).
    #: NÃO inclui letras — evita o bug do pandas sep=None.
    CSV_DELIMITERS: ClassVar[str] = ",;\t|"

    def __init__(
        self,
        file_path: Path,
        schema: Schema,
        *,
        dry_run: bool = False,
    ) -> None:
        """
        Inicializa ValidateTask.

        Args:
            file_path: Caminho da planilha a validar.
            schema: Schema com as regras.
            dry_run: Se True, não persiste relatório (Parte 3.3).
        """
        super().__init__(dry_run=dry_run)
        self.file_path = file_path
        self.schema = schema

    def execute(self) -> TaskResult:
        """Executa a validação."""
        started_at = datetime.now(UTC)

        # 1. Existência
        if not self.file_path.exists():
            raise ValidationError(
                f"Arquivo nao encontrado: {self.file_path}",
                field="file_path",
                value=str(self.file_path),
            )

        # 2. Extensão suportada
        ext = self.file_path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValidationError(
                f"Extensao nao suportada: '{ext}'. Suportadas: "
                f"{sorted(self.SUPPORTED_EXTENSIONS)}",
                field="file_path",
                value=str(self.file_path),
            )

        # 3. Carrega arquivo
        df = self._load_file(ext)

        # 4. Verifica colunas obrigatórias
        missing = self._missing_required_columns(df)
        if missing:
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=(f"Colunas obrigatorias faltando: {missing}"),
                error_type="MissingColumnsError",
                data={
                    "file": str(self.file_path),
                    "expected_columns": self.schema.column_names,
                    "actual_columns": list(df.columns),
                    "missing": missing,
                },
            )

        # 5. Estrutura OK (validações de conteúdo virão na Parte 3.2)
        return self._make_result(
            status=TaskStatus.SUCCESS,
            started_at=started_at,
            rows_affected=len(df),
            data={
                "file": str(self.file_path),
                "rows": len(df),
                "columns": list(df.columns),
            },
        )

    # ========================================================
    # Carregamento
    # ========================================================

    def _load_file(self, ext: str) -> pd.DataFrame:
        """Decide entre CSV/TSV ou Excel baseado na extensão."""
        if ext in {".csv", ".tsv"}:
            return self._load_csv()
        # ext in {".xlsx", ".xls"} — já validado antes
        return self._load_excel()

    def _load_csv(self) -> pd.DataFrame:
        """
        Carrega CSV com auto-detecção segura.

        - **Encoding**: tenta ``utf-8-sig`` (lida com BOM) → ``latin-1`` → ``cp1252``.
        - **Delimitador**: usa ``csv.Sniffer`` restrito a `,`, `;`, `\\t`, `|`
          (evita o bug do pandas ``sep=None`` que aceita qualquer letra).

        Raises:
            ValidationError: Se nenhum encoding funcionar.
        """
        last_error: Exception | None = None

        for encoding in self.CSV_ENCODINGS:
            # Lê amostra pra detectar delimitador
            try:
                with open(self.file_path, encoding=encoding) as f:
                    sample = f.read(8192)
            except UnicodeDecodeError as e:
                last_error = e
                continue

            sep = self._detect_delimiter(sample)

            try:
                return pd.read_csv(
                    self.file_path,
                    encoding=encoding,
                    sep=sep,
                )
            except UnicodeDecodeError as e:
                last_error = e
                continue
            except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
                raise ValidationError(
                    f"Erro ao ler CSV: {e}",
                    field="file_format",
                    value=str(self.file_path),
                ) from e

        raise ValidationError(
            f"Nao foi possivel decodificar {self.file_path} "
            f"(encodings tentados: {self.CSV_ENCODINGS})",
            field="encoding",
            value=str(self.file_path),
        ) from last_error

    @staticmethod
    def _detect_delimiter(sample: str) -> str:
        """
        Detecta delimitador do CSV usando csv.Sniffer.

        Restringe aos delimitadores comuns (`,`, `;`, `\\t`, `|`) — evita
        que o sniffer detecte letras como delimitadores (bug que afeta
        arquivos com 1 coluna).

        Args:
            sample: Amostra de texto do arquivo (primeiros KB).

        Returns:
            Delimitador detectado, ou `,` como fallback.
        """
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            # Fallback: vírgula (mais comum). Acontece quando arquivo
            # tem só 1 coluna (sem delimitadores na amostra).
            return ","
        return dialect.delimiter

    def _load_excel(self) -> pd.DataFrame:
        """Carrega arquivo Excel (.xlsx, .xls)."""
        try:
            return pd.read_excel(self.file_path)
        except (ValueError, OSError) as e:
            raise ValidationError(
                f"Erro ao ler Excel: {e}",
                field="file_format",
                value=str(self.file_path),
            ) from e

    # ========================================================
    # Validações de estrutura
    # ========================================================

    def _missing_required_columns(self, df: pd.DataFrame) -> list[str]:
        """Retorna lista de colunas obrigatórias faltando no DataFrame."""
        actual_columns = set(df.columns)
        return [
            col.name
            for col in self.schema.columns
            if col.required and col.name not in actual_columns
        ]


__all__ = [
    "ColumnSchema",
    "ColumnType",
    "Schema",
    "ValidateTask",
    "load_schema",
]
