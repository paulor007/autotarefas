"""
Contratos do leitor de planilhas.

O leitor entrega SEMPRE dois estados dos dados:

- ``original_dataframe``: fiel ao arquivo, tudo como texto. Nada e perdido
  (um identificador "00123" continua "00123").
- ``normalized_dataframe``: tipado, pronto para analise.

E, entre os dois, a trilha completa: toda diferenca entre o original e o
normalizado tem uma :class:`Conversion` correspondente. O leitor NUNCA
apaga linha, remove duplicata, descarta rodape ou inventa valor — ele
detecta, converte o que e seguro converter, e REGISTRA. Na duvida, avisa.

Este modulo (e todo o pacote ``reader``) e agnostico de dominio: ele nao
sabe o que e CPF, SKU ou venda. Quem da significado aos dados sao os
perfis e os schemas, uma camada acima.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd

#: Tipos que o leitor sabe reconhecer numa coluna.
CellType = Literal[
    "vazio",
    "erro",
    "booleano",
    "data",
    "data_hora",
    "identificador",
    "percentual",
    "moeda",
    "decimal",
    "inteiro",
    "texto",
    "misto",
]

#: Formatos de arquivo aceitos.
FileType = Literal["csv", "xlsx"]


@dataclass(frozen=True, slots=True)
class Conversion:
    """Uma mudanca entre o valor original e o normalizado."""

    row: int
    """Linha fisica na planilha (cabecalho = 1; 1a de dados = 2)."""
    column: str
    original: str
    normalized: str
    rule: str
    """Regra aplicada (ex.: 'moeda_br', 'data_ptbr', 'numero_texto')."""


@dataclass(frozen=True, slots=True)
class ReadWarning:
    """Algo que o usuario precisa saber — mas que o leitor NAO corrigiu."""

    code: str
    """Codigo estavel (ex.: 'rodape_suspeito', 'coluna_mista')."""
    message: str
    row: int | None = None
    column: str | None = None


@dataclass(frozen=True, slots=True)
class ColumnInfo:
    """O que o leitor descobriu sobre uma coluna."""

    index: int
    name: str
    """Exatamente como esta no arquivo."""
    inferred_type: CellType
    type_confidence: float
    observations: list[str] = field(default_factory=list)
    """Observacoes, NUNCA conclusoes (ex.: 'possivel identificador')."""
    excel_number_format: str | None = None
    sample_values: list[str] = field(default_factory=list)
    empty_count: int = 0
    type_counts: dict[str, int] = field(default_factory=dict)
    """Distribuicao dos tipos observados (ex.: {'inteiro': 95, 'texto': 5})."""


@dataclass(frozen=True, slots=True)
class SheetCandidate:
    """Uma aba e o quanto ela 'parece uma tabela'."""

    name: str
    score: float
    reason: str
    rows: int
    cols: int


@dataclass(frozen=True, slots=True)
class WorkbookReadResult:
    """Resultado completo da leitura de uma planilha."""

    source_file: Path
    file_type: FileType
    available_sheets: list[SheetCandidate] = field(default_factory=list)
    selected_sheet: str | None = None
    sheet_confidence: float = 0.0
    header_row: int | None = None
    """Linha FISICA do cabecalho (1-based, como no Excel)."""
    header_confidence: float = 0.0
    header_alternatives: list[int] = field(default_factory=list)
    data_start_row: int = 0
    data_end_row: int = 0
    detected_columns: list[ColumnInfo] = field(default_factory=list)
    original_dataframe: pd.DataFrame | None = None
    normalized_dataframe: pd.DataFrame | None = None
    conversions: list[Conversion] = field(default_factory=list)
    warnings: list[ReadWarning] = field(default_factory=list)
    skipped_empty_rows: int = 0
    """Linhas totalmente vazias na regiao de dados (nao sao registros)."""
    rejected_reason: str | None = None
    """Preenchido = o arquivo NAO foi processado (e o motivo)."""
    confidence: float = 0.0

    @property
    def ok(self) -> bool:
        """True se o arquivo foi lido (nao recusado)."""
        return self.rejected_reason is None

    @property
    def row_count(self) -> int:
        """Quantos registros (linhas de dados) foram lidos."""
        if self.original_dataframe is None:
            return 0
        return len(self.original_dataframe)

    def column(self, name: str) -> ColumnInfo | None:
        """Busca uma coluna pelo nome (ou None)."""
        for col in self.detected_columns:
            if col.name == name:
                return col
        return None


__all__ = [
    "CellType",
    "ColumnInfo",
    "Conversion",
    "FileType",
    "ReadWarning",
    "SheetCandidate",
    "WorkbookReadResult",
]
