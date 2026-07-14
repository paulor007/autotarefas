"""
Contratos da perfilagem.

A perfilagem OBSERVA e DESCREVE. Ela nao julga: um valor repetido nao e
erro, uma coluna com muitos vazios nao e erro, um codigo numerico nao e
uma chave. Quem transforma observacao em regra e o perfil ou o schema —
uma camada acima.

Por isso os achados tem SEVERIDADE, e a maioria e "informacao":

    informacao  o que a planilha e (fatos observados)
    aviso       algo que merece conferencia, mas pode ser legitimo
    problema    algo que impede ou prejudica a analise
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

    from autotarefas.reader.result import CellType

#: Severidade de um achado. A regra de produto: quase tudo e "informacao".
Severity = Literal["informacao", "aviso", "problema"]


@dataclass(frozen=True, slots=True)
class Finding:
    """Um achado da perfilagem (ou um aviso do leitor, consolidado aqui)."""

    code: str
    severity: Severity
    message: str
    column: str | None = None
    row: int | None = None
    """Linha FISICA da planilha, quando o achado aponta para uma linha."""
    count: int = 0
    samples: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    """O retrato de uma coluna — sem nenhuma conclusao de negocio."""

    name: str
    inferred_type: CellType
    type_confidence: float

    total_count: int
    filled_count: int
    empty_count: int
    fill_rate: float

    distinct_count: int
    uniqueness_rate: float
    """distintos / preenchidos. 1.0 = todos diferentes. Apenas INFORMACAO:
    o leitor nao conclui que a coluna deveria ser unica."""
    duplicate_value_count: int
    """Celulas cujo valor ja aparecera antes (preenchidos - distintos).
    Pode ser 100% legitimo (ex.: uma categoria que se repete)."""

    mixed_types: dict[str, int] = field(default_factory=dict)
    """Vazio quando a coluna tem um tipo so. Ex.: {'inteiro': 95, 'texto': 5}."""
    excel_error_count: int = 0
    whitespace_issue_count: int = 0

    minimum: str | None = None
    maximum: str | None = None
    """Minimo/maximo so fazem sentido para numero, moeda, percentual e data.
    Para identificador e texto ficam None — um codigo nao tem 'menor valor'."""

    sample_values: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProfileResult:
    """Diagnostico completo de uma planilha — sem schema e sem perfil."""

    source_file: Path
    selected_sheet: str | None
    header_row: int | None

    row_count: int
    column_count: int
    total_cells: int
    filled_cells: int
    empty_cells: int
    fill_rate: float

    duplicate_row_count: int
    """Linhas EXCEDENTES identicas a outra (a 1a ocorrencia nao conta)."""
    completely_empty_row_count: int
    completely_empty_column_count: int
    mixed_type_column_count: int
    excel_error_count: int

    conversion_count: int
    warning_count: int
    reader_confidence: float
    rejected_reason: str | None = None

    columns: list[ColumnProfile] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True se a planilha foi perfilada (nao recusada pelo leitor)."""
        return self.rejected_reason is None

    def column(self, name: str) -> ColumnProfile | None:
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]


__all__ = [
    "ColumnProfile",
    "Finding",
    "ProfileResult",
    "Severity",
]
