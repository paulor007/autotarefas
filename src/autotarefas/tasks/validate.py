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
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar, Literal

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from autotarefas.core import BaseTask, TaskResult, TaskStatus, ValidationError
from autotarefas.tasks.artifacts import count_issues_by_category
from autotarefas.tasks.cleaning import CleaningChange, clean_cell
from autotarefas.tasks.duplicates import (
    find_duplicate_rows,
    find_duplicate_values,
    normalize_digits,
    normalize_text,
)
from autotarefas.tasks.expressions import (
    ExpressionError,
    columns_used,
    parse_expression,
)
from autotarefas.tasks.issues import (
    IssueCollector,
    IssueSeverity,
    ValidationIssue,
)
from autotarefas.tasks.row_rules import (
    MAX_LINES_PER_VARIANT,
    GroupInconsistency,
    apply_derived,
    find_inconsistencies,
    index_groups,
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


#: Severidade escolhida pelo usuario numa regra.
RuleSeverity = Literal["error", "warning"]

#: Modelos das regras NOVAS sao estritos: um campo escrito errado
#: (`operaton:` em vez de `operation:`) e um erro de configuracao, nao
#: algo a ignorar em silencio. O `Schema` raiz continua permissivo, para
#: nao quebrar nenhum schema antigo que ja esteja em uso.
_STRICT = ConfigDict(extra="forbid")


class GroupKey(BaseModel):
    """
    Define o que forma um grupo de linhas relacionadas.

    A chave pode ser uma coluna so ou varias (chave composta). Ela PODE e
    normalmente VAI se repetir — e a repeticao que junta as linhas do
    mesmo grupo. Isso nao tem nada a ver com `unique`, nem com linha
    completamente duplicada.

    Exemplo:
        group_keys:
          - name: lote
            columns: ["Codigo", "Ano"]
    """

    model_config = _STRICT

    name: str = Field(..., min_length=1)
    columns: tuple[str, ...] = Field(..., min_length=1)


class GroupCheck(BaseModel):
    """
    Exige que certas colunas concordem dentro de cada grupo.

    Exemplo:
        group_checks:
          - name: coerencia_do_lote
            group_key: lote
            consistent: ["Responsavel", "Data"]
    """

    model_config = _STRICT

    name: str = Field(..., min_length=1)
    group_key: str = Field(..., min_length=1)
    consistent: tuple[str, ...] = Field(..., min_length=1)
    severity: RuleSeverity = "error"


class DerivedCheck(BaseModel):
    """
    Exige que uma coluna corresponda a uma conta feita com outras colunas.

    Exemplo:
        derived_checks:
          - name: total_da_linha
            target: "Total"
            expression: "[Base] * [Fator]"
            tolerance: 0

    Sobre `tolerance`: o padrao e ZERO — igualdade exata. As contas usam
    Decimal, entao `1.1 * 3` da exatamente `3.3` e a igualdade exata e
    alcancavel de verdade. Uma folga automatica aceitaria em silencio uma
    diferenca que o usuario nunca autorizou; quem precisa de margem
    (tipicamente por causa de divisao/arredondamento) declara.
    """

    model_config = _STRICT

    name: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    expression: str = Field(..., min_length=1)
    tolerance: Decimal = Decimal(0)
    severity: RuleSeverity = "error"

    @field_validator("tolerance", mode="before")
    @classmethod
    def _tolerance_exata(cls, valor: object) -> Decimal:
        """Converte via str: `Decimal(0.01)` traria o lixo binario do float."""
        if isinstance(valor, Decimal):
            return valor
        try:
            convertido = Decimal(str(valor))
        except (ArithmeticError, ValueError) as exc:
            msg = f"tolerance invalida: {valor!r}"
            raise ValueError(msg) from exc
        if convertido < 0:
            msg = f"tolerance nao pode ser negativa (recebido {convertido})"
            raise ValueError(msg)
        return convertido

    @field_validator("expression")
    @classmethod
    def _expressao_analisavel(cls, texto: str) -> str:
        """A expressao e analisada JA NA CARGA — erro aqui e de configuracao."""
        try:
            parse_expression(texto)
        except ExpressionError as exc:
            msg = f"expressao invalida ({exc})"
            raise ValueError(msg) from exc
        return texto


class Provenance(BaseModel):
    """
    De onde um schema veio. Opcional; presente so em schemas gerados por perfil.

    Nao muda nada na validacao — e um registro que o `ValidateTask` copia para
    o resultado, para que o relatorio consiga responder "que perfil e versao
    produziram este schema". Semente da linhagem, sem antecipar o resto.
    """

    model_config = ConfigDict(extra="allow")  # tolera campos futuros sem quebrar

    profile: str | None = None
    profile_version: int | None = None
    tool_version: str | None = None


class Schema(BaseModel):
    """
    Schema completo de validacao (carregado de YAML).

    Attributes:
        columns: Lista de definicoes de coluna (minimo 1).
        detect_duplicate_rows: Se True, linhas 100% identicas viram
            warning (a 1a ocorrencia e considerada o original).
        group_keys: Chaves que formam grupos de linhas relacionadas.
        group_checks: Colunas que devem concordar dentro de cada grupo.
        derived_checks: Colunas que devem bater com uma conta.

    As tres ultimas sao OPCIONAIS e vazias por padrao — um schema antigo
    carrega e se comporta exatamente como antes.
    """

    columns: list[ColumnSchema] = Field(..., min_length=1)
    detect_duplicate_rows: bool = False

    group_keys: tuple[GroupKey, ...] = ()
    group_checks: tuple[GroupCheck, ...] = ()
    derived_checks: tuple[DerivedCheck, ...] = ()

    #: Procedencia opcional: de onde este schema veio (perfil + versao). E a
    #: semente da linhagem que o roadmap pede — hoje so um registro, ecoado
    #: para o relatorio. Schemas escritos a mao simplesmente nao tem.
    generated_from: Provenance | None = None

    @model_validator(mode="after")
    def _regras_coerentes(self) -> Schema:
        """
        Confere as referencias entre as regras JA NA CARGA do schema.

        Assim um erro de configuracao aparece antes de qualquer linha ser
        lida, com o mesmo comportamento dos outros erros de schema.
        """
        declaradas = {c.name for c in self.columns}

        nomes_chave = [k.name for k in self.group_keys]
        if len(nomes_chave) != len(set(nomes_chave)):
            msg = "ha group_keys com o mesmo nome"
            raise ValueError(msg)

        nomes_regra = [c.name for c in self.group_checks] + [d.name for d in self.derived_checks]
        if len(nomes_regra) != len(set(nomes_regra)):
            msg = "ha regras com o mesmo nome"
            raise ValueError(msg)

        for chave in self.group_keys:
            faltando = [c for c in chave.columns if c not in declaradas]
            if faltando:
                msg = f"group_key '{chave.name}' usa coluna(s) que o schema nao declara: {faltando}"
                raise ValueError(msg)

        for check in self.group_checks:
            if check.group_key not in set(nomes_chave):
                msg = (
                    f"group_check '{check.name}' aponta para a group_key "
                    f"'{check.group_key}', que nao existe"
                )
                raise ValueError(msg)
            faltando = [c for c in check.consistent if c not in declaradas]
            if faltando:
                msg = (
                    f"group_check '{check.name}' usa coluna(s) que o schema nao declara: {faltando}"
                )
                raise ValueError(msg)

        for derivada in self.derived_checks:
            if derivada.target not in declaradas:
                msg = (
                    f"derived_check '{derivada.name}' aponta para a coluna "
                    f"'{derivada.target}', que o schema nao declara"
                )
                raise ValueError(msg)
            usadas = columns_used(parse_expression(derivada.expression))
            faltando = sorted(u for u in usadas if u not in declaradas)
            if faltando:
                msg = (
                    f"derived_check '{derivada.name}' usa na expressao coluna(s) que o "
                    f"schema nao declara: {faltando}"
                )
                raise ValueError(msg)

        return self

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


def _group_message(rule: str, key_name: str, achado: GroupInconsistency) -> str:
    """
    Mensagem de divergencia dentro de um grupo.

    Mostra TODOS os valores encontrados e as linhas de cada um — e nao
    elege nenhum como o correto. O AutoTarefas nao conhece a verdade do
    negocio; quem decide e quem conhece.
    """
    chave = ", ".join(achado.key)
    partes = []
    for valor, linhas in achado.variants:
        onde = ", ".join(str(i + 2) for i in linhas)
        reticencias = "..." if len(linhas) >= MAX_LINES_PER_VARIANT else ""
        mostrado = valor if valor else "(vazio)"
        partes.append(f"'{mostrado}' (linha(s) {onde}{reticencias})")

    restantes = achado.distinct_count - len(achado.variants)
    extra = f" e mais {restantes} valor(es)" if restantes > 0 else ""

    return (
        f"Regra '{rule}': no grupo {key_name}=[{chave}] com {achado.group_size} registro(s), "
        f"a coluna '{achado.column}' tem {achado.distinct_count} valores diferentes: "
        f"{'; '.join(partes)}{extra}. Confira qual e o correto."
    )


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

        # 5c. Regras opcionais entre colunas e entre linhas do mesmo grupo.
        # A configuracao e conferida ANTES de percorrer os registros: uma
        # regra que nao pode rodar e um erro explicito, nunca um silencio.
        erro_de_regra = self._missing_rule_columns(df)
        if erro_de_regra is not None:
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=erro_de_regra,
                error_type="RuleConfigError",
                data={
                    "file": str(self.file_path),
                    "actual_columns": list(df.columns),
                },
            )

        self._validate_group_checks(df, collector)
        self._validate_derived_checks(df, collector)

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

        # procedencia: se o schema veio de um perfil, o relatorio registra a
        # origem. Semente da linhagem; nao altera a validacao em nada.
        if self.schema.generated_from is not None:
            base_data["generated_from"] = self.schema.generated_from.model_dump(exclude_none=True)

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
                        category="duplicado",
                        related_lines=(original, line),
                    )

    def _missing_rule_columns(self, df: pd.DataFrame) -> str | None:
        """
        Confere se as colunas usadas pelas regras existem NO ARQUIVO.

        As referencias entre regras ja foram conferidas na carga do schema.
        Aqui fica o que so o arquivo pode responder. Uma regra que nao pode
        rodar e um ERRO DE CONFIGURACAO explicito — nunca uma regra
        silenciosamente ignorada, senao o cliente ficaria achando que ela
        passou.

        Returns:
            Mensagem do erro, ou None se estiver tudo no lugar.
        """
        presentes = set(df.columns)
        chaves = {k.name: k for k in self.schema.group_keys}
        faltas: list[str] = []

        for check in self.schema.group_checks:
            chave = chaves[check.group_key]
            ausentes = [c for c in (*chave.columns, *check.consistent) if c not in presentes]
            if ausentes:
                faltas.append(f"group_check '{check.name}' precisa de {ausentes}")

        for derivada in self.schema.derived_checks:
            usadas = columns_used(parse_expression(derivada.expression))
            ausentes = sorted(c for c in (derivada.target, *usadas) if c not in presentes)
            if ausentes:
                faltas.append(f"derived_check '{derivada.name}' precisa de {ausentes}")

        if not faltas:
            return None
        return "Regras nao puderam ser aplicadas — coluna(s) ausente(s) no arquivo: " + "; ".join(
            faltas
        )

    def _validate_group_checks(self, df: pd.DataFrame, collector: IssueCollector) -> None:
        """
        Confere a coerencia das colunas dentro de cada grupo.

        Um issue por (grupo, coluna divergente) — nao um por linha. A
        mensagem traz TODOS os valores encontrados e as linhas de cada um.
        O AutoTarefas nao elege o valor certo: ele nao conhece a verdade do
        negocio, e escolher seria inventar.

        O issue e ancorado na primeira linha do grupo apenas para ter uma
        posicao no relatorio — isso NAO significa que aquela linha e a errada.
        """
        chaves = {k.name: k for k in self.schema.group_keys}

        for check in self.schema.group_checks:
            chave = chaves[check.group_key]
            severidade = IssueSeverity.ERROR if check.severity == "error" else IssueSeverity.WARNING

            colunas_chave = list(chave.columns)
            valores_chave = [
                [self._cell_to_str(v) for v in linha]
                for linha in df[colunas_chave].itertuples(index=False, name=None)
            ]
            grupos, fora = index_groups(valores_chave)

            for solta in fora:
                vazias = [colunas_chave[i] for i in solta.empty_positions]
                detalhe = (
                    f"a chave '{chave.name}' esta vazia em {vazias}"
                    if solta.partial
                    else f"a chave '{chave.name}' esta totalmente vazia"
                )
                collector.add(
                    line=solta.index + 2,
                    column=colunas_chave[0],
                    message=(
                        f"Regra '{check.name}' nao pode ser verificada nesta linha: "
                        f"{detalhe} — a linha ficou fora do agrupamento"
                    ),
                    severity=IssueSeverity.WARNING,
                    rule=check.name,
                    category="grupo",
                )

            valores_por_coluna = {
                nome: [self._cell_to_str(v) for v in df[nome]] for nome in check.consistent
            }

            for achado in find_inconsistencies(grupos, valores_por_coluna, check.consistent):
                # `related_lines` carrega o grupo INTEIRO: um artefato de
                # revisao precisa de todas as linhas envolvidas, e a ancora
                # e apenas onde o issue aparece no relatorio.
                envolvidas = tuple(sorted({i + 2 for _, linhas in achado.variants for i in linhas}))
                collector.add(
                    line=achado.anchor_index + 2,
                    column=achado.column,
                    message=_group_message(check.name, chave.name, achado),
                    severity=severidade,
                    rule=check.name,
                    category="grupo",
                    related_lines=envolvidas,
                )

    def _validate_derived_checks(self, df: pd.DataFrame, collector: IssueCollector) -> None:
        """
        Confere as contas entre colunas.

        A expressao e analisada UMA vez por regra (nao por linha), e cada
        linha e percorrida no maximo uma vez.

        Duas situacoes diferentes, tratadas de forma diferente:
          - a conta foi feita e DIVERGIU -> severidade escolhida pelo usuario
          - a conta NAO PODE ser feita   -> sempre aviso. Dado faltando nao e
            o mesmo que conta errada; e quem quiser rigor total continua tendo
            o `--strict-warnings`.
        """
        for derivada in self.schema.derived_checks:
            arvore = parse_expression(derivada.expression)
            usadas = sorted(columns_used(arvore))
            severidade = (
                IssueSeverity.ERROR if derivada.severity == "error" else IssueSeverity.WARNING
            )

            alvo = list(df[derivada.target])
            colunas = {nome: list(df[nome]) for nome in usadas}

            for achado in apply_derived(arvore, alvo, colunas, derivada.tolerance):
                linha = achado.index + 2

                if achado.reason is not None:
                    collector.add(
                        line=linha,
                        column=derivada.target,
                        message=f"Regra '{derivada.name}' nao pode ser calculada: {achado.reason}",
                        severity=IssueSeverity.WARNING,
                        value=achado.observed,
                        rule=derivada.name,
                        category="calculo",
                    )
                    continue

                collector.add(
                    line=linha,
                    column=derivada.target,
                    message=(
                        f"Regra '{derivada.name}': o calculo nao confere — "
                        f"'{derivada.target}' tem {achado.observed}, mas "
                        f"{derivada.expression} da {achado.computed} "
                        f"(diferenca de {achado.difference})"
                    ),
                    severity=severidade,
                    value=achado.observed,
                    rule=derivada.name,
                    category="calculo",
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
            **({"rule": issue.rule} if issue.rule else {}),
            **({"category": issue.category} if issue.category else {}),
            **({"related_lines": list(issue.related_lines)} if issue.related_lines else {}),
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
