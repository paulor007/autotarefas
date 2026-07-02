"""
Task de validação de planilhas (CSV, TSV, Excel) — VERSAO PARTE 3.2.

A primeira subclasse real de BaseTask. Valida arquivos contra um schema
YAML, reportando erros estruturados com linha e coluna.

Histórico:
- Parte 3.1: validacao de estrutura (extensao, encoding, colunas obrigatorias)
- Parte 3.2 (atual): + validacao de conteudo celula-a-celula
- Parte 3.3 (proxima): + relatorio JSON/CSV + comando CLI

Uso basico:
    from pathlib import Path
    from autotarefas.tasks.validate import (
        Schema, ColumnSchema, ValidateTask, load_schema
    )

    schema = load_schema(Path("schema.yaml"))
    task = ValidateTask(file_path=Path("dados.csv"), schema=schema)
    result = task.run()

    if result.is_success:
        print(f"OK! {result.rows_affected} linhas validas.")
    else:
        issues = result.data["issues"]
        print(f"{len(issues)} problemas encontrados:")
        for issue in issues:
            print(f"  Linha {issue['line']}, coluna {issue['column']}: {issue['message']}")
"""

from __future__ import annotations

import csv
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

import pandas as pd
import yaml
from pydantic import BaseModel, Field

from autotarefas.core import BaseTask, TaskResult, TaskStatus, ValidationError
from autotarefas.tasks.artifacts import count_issues_by_category
from autotarefas.tasks.cleaning import CleaningChange, clean_cell
from autotarefas.tasks.duplicates import (
    find_duplicate_rows,
    find_duplicate_values,
    normalize_digits,
    normalize_text,
)
from autotarefas.tasks.issues import (
    IssueCollector,
    IssueSeverity,
    ValidationIssue,
)
from autotarefas.tasks.validators import (
    CNPJValidator,
    CPFValidator,
    EmailValidator,
    EnumValidator,
    MinLengthValidator,
    PhoneValidator,
    RangeValidator,
    RegexValidator,
    TypeValidator,
    Validator,
)

# ============================================================
# Schema (modelo declarativo das regras de validação)
# ============================================================

#: Tipos suportados pelas colunas.
ColumnType = Literal["str", "int", "float", "date", "bool"]

#: Validadores brasileiros disponiveis no schema.
BRValidatorType = Literal["cpf", "cnpj"]

#: Formatos de alto nivel reconhecidos pelo schema (alem do type tecnico).
FormatType = Literal["email", "phone"]

#: Modos de operacao da auditoria de planilha.
ValidationMode = Literal["auditoria", "limpeza", "bloqueio"]


class ColumnSchema(BaseModel):
    """
    Define as regras de validacao de uma coluna.

    Suporta validacoes:
    - **Estruturais** (nome, required, nullable)
    - **De tipo** (int, float, date, bool — "str" passa sempre)
    - **De intervalo numerico** (min_value, max_value)
    - **De formato** (regex customizada)
    - **De enumeracao** (lista de valores aceitos)
    - **Brasileiras** (CPF, CNPJ)

    Combine livremente: ex. `type=int` + `min_value=0` + `max_value=150`.

    Attributes:
        name: Nome da coluna (case-sensitive).
        required: Se True (default), coluna deve estar no arquivo.
        type: Tipo esperado dos valores (default "str").
        nullable: Se True, valores vazios permitidos (default False).
        min_value: Valor minimo (inclusive). Aplica RangeValidator.
        max_value: Valor maximo (inclusive). Aplica RangeValidator.
        regex: Padrao regex. Aplica RegexValidator com `re.fullmatch`.
        regex_message: Mensagem custom do erro de regex.
        enum_values: Lista de valores aceitos. Aplica EnumValidator.
        validator_br: "cpf" ou "cnpj". Aplica validator brasileiro.
        format: "email" ou "phone". Aplica EmailValidator/PhoneValidator.
        min_length: Comprimento minimo de texto. Aplica MinLengthValidator.
        unique: Se True, valores repetidos nesta coluna viram erro
            (deteccao cross-row feita pela ValidateTask).
    """

    name: str = Field(..., min_length=1)
    required: bool = True
    type: ColumnType = "str"
    nullable: bool = False

    # Novos campos da Parte 3.2
    min_value: float | None = None
    max_value: float | None = None
    regex: str | None = None
    regex_message: str | None = None
    enum_values: tuple[str, ...] | None = None
    validator_br: BRValidatorType | None = None

    # Novos campos (Auditoria de planilha)
    format: FormatType | None = None
    min_length: int | None = None
    unique: bool = False

    def get_validators(self) -> list[Validator]:
        """
        Cria lista de validators a aplicar nesta coluna.

        Cada campo do schema gera um validator correspondente. Validators
        sao acumulativos — se a coluna tem type=int e min_value=0, vai ter
        TypeValidator + RangeValidator.

        Returns:
            Lista de validators (pode ser vazia se for coluna `type=str`
            sem mais nada).
        """
        validators: list[Validator] = []

        # 1. TypeValidator (exceto 'str' que passa qualquer coisa)
        # match-case faz type narrowing automatico — mypy reconhece
        # que self.type ja foi reduzido a ValidatableType.
        match self.type:
            case "int" | "float" | "date" | "bool":
                validators.append(TypeValidator(expected_type=self.type))
            case "str":
                pass  # str passa qualquer coisa — sem validador

        # 2. RegexValidator
        if self.regex is not None:
            validators.append(
                RegexValidator(
                    pattern=re.compile(self.regex),
                    message=self.regex_message or "Formato invalido",
                )
            )

        # 3. RangeValidator (so se min ou max definidos)
        if self.min_value is not None or self.max_value is not None:
            validators.append(
                RangeValidator(
                    min_value=self.min_value,
                    max_value=self.max_value,
                )
            )

        # 4. EnumValidator
        if self.enum_values is not None:
            validators.append(EnumValidator(allowed_values=self.enum_values))

        # 5. CPF/CNPJ
        if self.validator_br == "cpf":
            validators.append(CPFValidator())
        elif self.validator_br == "cnpj":
            validators.append(CNPJValidator())

        # 6. Formato de alto nivel (email/telefone)
        if self.format == "email":
            validators.append(EmailValidator())
        elif self.format == "phone":
            validators.append(PhoneValidator())

        # 7. Comprimento minimo de texto
        if self.min_length is not None:
            validators.append(MinLengthValidator(min_length=self.min_length))

        return validators


class Schema(BaseModel):
    """
    Schema completo de validacao (carregado de YAML).

    Attributes:
        columns: Lista de definicoes de coluna (minimo 1).
        detect_duplicate_rows: Se True, linhas 100% identicas viram
            warning (a 1a ocorrencia e considerada o original).
    """

    columns: list[ColumnSchema] = Field(..., min_length=1)
    detect_duplicate_rows: bool = False

    @property
    def column_names(self) -> list[str]:
        """Nomes de todas as colunas declaradas no schema."""
        return [c.name for c in self.columns]

    @property
    def required_columns(self) -> list[str]:
        """Nomes das colunas obrigatorias."""
        return [c.name for c in self.columns if c.required]

    def get_column(self, name: str) -> ColumnSchema | None:
        """Busca coluna por nome. Retorna None se nao encontrar."""
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
        ValidationError: Se o arquivo nao existe ou o YAML e invalido.
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

    Fluxo de validacao:
    1. Verifica existencia do arquivo
    2. Verifica extensao suportada
    3. Carrega o arquivo (com encoding e delimitador auto-detectados)
    4. Verifica colunas obrigatorias presentes
    5. **Valida conteudo** (novo na Parte 3.2):
       - Para cada coluna do schema presente no arquivo
       - Para cada linha de dados
       - Aplica validators acumulando issues
    6. Retorna SUCCESS se sem erros, FAILURE caso contrario

    Warnings nao invalidam (is_valid=True ainda).
    """

    name = "validate"
    description = "Valida planilha CSV/Excel contra schema YAML"

    #: Extensoes suportadas.
    SUPPORTED_EXTENSIONS: ClassVar[frozenset[str]] = frozenset({".csv", ".tsv", ".xlsx", ".xls"})

    #: Encodings tentados para CSV (em ordem).
    CSV_ENCODINGS: ClassVar[tuple[str, ...]] = (
        "utf-8-sig",
        "latin-1",
        "cp1252",
    )

    #: Delimitadores possiveis para auto-deteccao (csv.Sniffer).
    CSV_DELIMITERS: ClassVar[str] = ",;\t|"

    def __init__(
        self,
        file_path: Path,
        schema: Schema,
        *,
        mode: ValidationMode = "auditoria",
        dry_run: bool = False,
    ) -> None:
        """
        Inicializa ValidateTask.

        Args:
            file_path: Caminho da planilha a validar.
            schema: Schema com as regras.
            mode: Modo de operacao:
                - "auditoria" (default): so aponta problemas, nao altera dados.
                - "limpeza": normaliza dados seguros antes de validar e
                  registra o audit trail (antes/depois). Nunca inventa dado.
                - "bloqueio": nao altera dados; usado em pipelines, onde o
                  exit code diferente de zero deve barrar o proximo passo.
            dry_run: Se True, nao persiste relatorio.
        """
        super().__init__(dry_run=dry_run)
        self.file_path = file_path
        self.schema = schema
        self.mode = mode
        #: DataFrame apos processamento (normalizado no modo limpeza).
        #: Preenchido em execute(); usado pelo CLI para gerar artefatos.
        self.processed_dataframe: pd.DataFrame | None = None

    def execute(self) -> TaskResult:
        """Executa a validacao."""
        started_at = datetime.now(UTC)

        # 1. Existencia
        if not self.file_path.exists():
            raise ValidationError(
                f"Arquivo nao encontrado: {self.file_path}",
                field="file_path",
                value=str(self.file_path),
            )

        # 2. Extensao suportada
        ext = self.file_path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValidationError(
                f"Extensao nao suportada: '{ext}'. Suportadas: {sorted(self.SUPPORTED_EXTENSIONS)}",
                field="file_path",
                value=str(self.file_path),
            )

        # 3. Carrega arquivo
        df = self._load_file(ext)

        # 4. Verifica colunas obrigatorias
        missing = self._missing_required_columns(df)
        if missing:
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=f"Colunas obrigatorias faltando: {missing}",
                error_type="MissingColumnsError",
                data={
                    "file": str(self.file_path),
                    "expected_columns": self.schema.column_names,
                    "actual_columns": list(df.columns),
                    "missing": missing,
                },
            )

        # 4b. Modo limpeza: normaliza dados seguros ANTES de validar,
        # de modo que valores como "  Ana@X.COM " deixem de falhar por
        # espacos/caixa. CPF/telefone invalidos permanecem intactos.
        cleaning_changes: list[CleaningChange] = []
        if self.mode == "limpeza":
            df, cleaning_changes = self._clean_dataframe(df)

        # Guarda o DataFrame processado (normalizado no modo limpeza) para
        # o CLI poder gerar os artefatos de separacao (validos/invalidos).
        self.processed_dataframe = df

        # 5. Validacao de conteudo
        collector = self._validate_content(df)

        # 5b. Deteccao de duplicatas (cross-row)
        self._validate_duplicates(df, collector)

        # 6. Separacao: uma linha e invalida se tem >=1 problema ERROR.
        error_lines = {i.line for i in collector.errors if i.line >= 2}  # noqa: PLR2004
        total_invalid = len(error_lines)

        # 7. Monta resultado final
        issue_dicts = [self._issue_to_dict(i) for i in collector.issues]
        base_data: dict[str, Any] = {
            "file": str(self.file_path),
            "mode": self.mode,
            "rows": len(df),
            "columns": list(df.columns),
            "total_issues": len(collector),
            "total_errors": len(collector.errors),
            "total_warnings": len(collector.warnings),
            "total_valid": len(df) - total_invalid,
            "total_invalid": total_invalid,
            "issues": issue_dicts,
            "issues_by_category": count_issues_by_category(issue_dicts),
            "cleaning_changes": [self._change_to_dict(c) for c in cleaning_changes],
            "total_cleaned": len(cleaning_changes),
        }

        if collector.is_valid:
            return self._make_result(
                status=TaskStatus.SUCCESS,
                started_at=started_at,
                rows_affected=len(df),
                data=base_data,
            )

        return self._make_result(
            status=TaskStatus.FAILURE,
            started_at=started_at,
            error_message=(f"{len(collector.errors)} erro(s) de validacao encontrado(s)"),
            error_type="ValidationIssuesError",
            data=base_data,
        )

    # ========================================================
    # Carregamento
    # ========================================================

    def _load_file(self, ext: str) -> pd.DataFrame:
        """Decide entre CSV/TSV ou Excel baseado na extensao."""
        if ext in {".csv", ".tsv"}:
            return self._load_csv()
        return self._load_excel()

    def _load_csv(self) -> pd.DataFrame:
        """Carrega CSV com auto-deteccao de encoding e delimitador."""
        last_error: Exception | None = None

        for encoding in self.CSV_ENCODINGS:
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
        """Detecta delimitador via csv.Sniffer (restrito a ,;\\t|)."""
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
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
    # Validacao de estrutura
    # ========================================================

    def _missing_required_columns(self, df: pd.DataFrame) -> list[str]:
        """Retorna lista de colunas obrigatorias faltando."""
        actual_columns = set(df.columns)
        return [
            col.name
            for col in self.schema.columns
            if col.required and col.name not in actual_columns
        ]

    # ========================================================
    # Normalizacao segura (modo limpeza)
    # ========================================================

    def _clean_dataframe(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[CleaningChange]]:
        """
        Aplica normalizacao segura (modo limpeza) coluna-a-coluna.

        Para cada coluna do schema presente no DataFrame, deriva quais
        normalizacoes se aplicam (email → minusculo; cpf/cnpj → mascara
        canonica *quando o documento e valido*; phone → mascara *quando
        valido*; e sempre remocao/colapso de espacos). Registra em
        `CleaningChange` apenas as celulas que de fato mudaram.

        Nunca inventa dado: CPF/telefone invalidos permanecem intactos e
        continuarao sendo apontados pela validacao.

        Returns:
            Tupla ``(df_normalizado, audit_trail)``. O DataFrame original
            nao e mutado (opera sobre uma copia).
        """
        cleaned = df.copy()
        changes: list[CleaningChange] = []

        for col_schema in self.schema.columns:
            if col_schema.name not in cleaned.columns:
                continue

            lowercase = col_schema.format == "email"
            phone = col_schema.format == "phone"
            cpf = col_schema.validator_br == "cpf"
            cnpj = col_schema.validator_br == "cnpj"

            new_values: list[str] = []
            col_changes: list[CleaningChange] = []
            for offset, raw in enumerate(cleaned[col_schema.name]):
                before = self._cell_to_str(raw)
                after, rules = clean_cell(
                    before, lowercase=lowercase, cpf=cpf, cnpj=cnpj, phone=phone
                )
                new_values.append(after)
                if rules:
                    col_changes.append(
                        CleaningChange(
                            line=offset + 2,
                            column=col_schema.name,
                            before=before,
                            after=after,
                            rules=rules,
                        )
                    )

            # So reescreve a coluna se houve alguma alteracao real.
            if col_changes:
                cleaned[col_schema.name] = new_values
                changes.extend(col_changes)

        return cleaned, changes

    # ========================================================
    # Validacao de conteudo (NOVO na Parte 3.2)
    # ========================================================

    def _validate_content(self, df: pd.DataFrame) -> IssueCollector:
        """
        Aplica validators linha-a-linha, coluna-a-coluna.

        Para cada coluna do schema presente no DataFrame:
        1. Gera lista de validators (via `col_schema.get_validators()`)
        2. Para cada celula, converte pra string
        3. Se `nullable=False` e valor vazio → issue de obrigatoriedade
        4. Senao, aplica todos os validators

        Args:
            df: DataFrame ja carregado.

        Returns:
            IssueCollector com todos os issues encontrados.
        """
        collector = IssueCollector()

        for col_schema in self.schema.columns:
            # Pula colunas opcionais que nao estao no DataFrame
            if col_schema.name not in df.columns:
                continue

            validators = col_schema.get_validators()
            column_series = df[col_schema.name]

            for offset, raw_value in enumerate(column_series):
                # +2: offset comeca em 0, header esta na linha 1,
                # primeira linha de dados e a 2.
                line_number = offset + 2
                str_value = self._cell_to_str(raw_value)

                # 1. Nullability check
                if not col_schema.nullable and not str_value.strip():
                    collector.add(
                        line=line_number,
                        column=col_schema.name,
                        message="Valor obrigatorio nao informado",
                        severity=IssueSeverity.ERROR,
                    )
                    # Se valor obrigatorio falta, nao aplica outros
                    # validators (evita cascata de erros redundantes)
                    continue

                # 2. Apply validators (cada um decide ignorar vazio ou nao)
                for validator in validators:
                    validator.validate(
                        value=str_value,
                        line=line_number,
                        column=col_schema.name,
                        collector=collector,
                    )

        return collector

    def _validate_duplicates(self, df: pd.DataFrame, collector: IssueCollector) -> None:
        """
        Detecta duplicatas cross-row e adiciona issues ao collector.

        - Colunas com ``unique=True``: valores repetidos viram ERROR. A
          comparacao normaliza por tipo — CPF/CNPJ por digitos (a mascara
          nao importa), demais por texto (ignora caixa e espacos).
        - ``detect_duplicate_rows=True``: linhas 100% identicas viram
          WARNING, a partir da 2a ocorrencia (a 1a e o "original").

        Indices 0-based vindos de `duplicates` viram numero de linha
        somando +2 (offset 0 + cabecalho na linha 1 → 1a linha de dados
        e a 2), mesma convencao do `_validate_content`.
        """
        # Colunas declaradas como unicas.
        for col_schema in self.schema.columns:
            if not col_schema.unique or col_schema.name not in df.columns:
                continue

            values = [self._cell_to_str(v) for v in df[col_schema.name]]
            key = normalize_digits if col_schema.validator_br in {"cpf", "cnpj"} else normalize_text

            for indices in find_duplicate_values(values, key=key).values():
                lines = [i + 2 for i in indices]
                where = ", ".join(str(n) for n in lines)
                for line in lines:
                    collector.add(
                        line=line,
                        column=col_schema.name,
                        message=(f"Valor duplicado na coluna '{col_schema.name}' (linhas {where})"),
                        severity=IssueSeverity.ERROR,
                    )

        # Linhas inteiras identicas.
        if self.schema.detect_duplicate_rows:
            rows = [
                tuple(self._cell_to_str(v) for v in row)
                for row in df.itertuples(index=False, name=None)
            ]
            for group in find_duplicate_rows(rows):
                lines = [i + 2 for i in group]
                original = lines[0]
                for line in lines[1:]:
                    collector.add(
                        line=line,
                        column=None,
                        message=f"Linha duplicada (identica a linha {original})",
                        severity=IssueSeverity.WARNING,
                    )

    @staticmethod
    def _cell_to_str(value: Any) -> str:
        """
        Converte celula do pandas em string.

        Pandas pode retornar varios tipos (int, float, datetime, str, NaN).
        Padronizamos pra string antes de passar pros validators.

        NaN/None viram string vazia.

        Args:
            value: Valor bruto da celula (qualquer tipo).

        Returns:
            String — vazia se NaN/None.

        Nota sobre `# noqa: ANN401`:
            ANN401 proibe `Any` em parametros, mas aqui e justificavel —
            pandas retorna `Any` literalmente, e o objetivo desta funcao
            e exatamente normalizar para `str`.
        """
        if pd.isna(value):
            return ""
        return str(value)

    @staticmethod
    def _issue_to_dict(issue: ValidationIssue) -> dict[str, Any]:
        """
        Serializa ValidationIssue em dict (para incluir no TaskResult.data).

        Usado para o relatorio JSON/CSV na Parte 3.3.

        IssueSeverity (StrEnum) e convertido via str() para evitar
        comparacoes ambiguas com strings literais.
        """
        return {
            "line": issue.line,
            "column": issue.column,
            "message": issue.message,
            "severity": str(issue.severity),
            "value": issue.value,
        }

    @staticmethod
    def _change_to_dict(change: CleaningChange) -> dict[str, Any]:
        """Serializa CleaningChange em dict (para o relatorio e o data)."""
        return {
            "line": change.line,
            "column": change.column,
            "before": change.before,
            "after": change.after,
            "rules": list(change.rules),
        }


__all__ = [
    "BRValidatorType",
    "ColumnSchema",
    "ColumnType",
    "FormatType",
    "Schema",
    "ValidateTask",
    "ValidationMode",
    "load_schema",
]
