"""
Leitor de planilhas do AutoTarefas.

Le CSV e XLSX de verdade: encontra a aba, encontra o cabecalho, descobre
os tipos e normaliza o que e seguro normalizar — registrando cada mudanca.

E AGNOSTICO DE DOMINIO por construcao: este pacote nao sabe o que e CPF,
SKU, venda ou estoque. Quem da significado aos dados sao os perfis e os
schemas, uma camada acima. (Ha um teste que falha o build se um termo de
dominio aparecer aqui dentro.)

Uso:
    from autotarefas.reader import read_workbook

    resultado = read_workbook(Path("planilha.xlsx"))
    if not resultado.ok:
        print(resultado.rejected_reason)   # o arquivo NAO foi processado
    else:
        print(resultado.selected_sheet, resultado.header_row)
        print(resultado.normalized_dataframe)
"""

from autotarefas.reader.result import (
    CellType,
    ColumnInfo,
    Conversion,
    FileType,
    ReadWarning,
    SheetCandidate,
    WorkbookReadResult,
)
from autotarefas.reader.workbook import ReaderError, read_workbook

__all__ = [
    "CellType",
    "ColumnInfo",
    "Conversion",
    "FileType",
    "ReadWarning",
    "ReaderError",
    "SheetCandidate",
    "WorkbookReadResult",
    "read_workbook",
]
