"""
Perfilagem generica de planilhas.

Recebe o que o leitor produziu e devolve um diagnostico — sem schema, sem
perfil de dominio e sem julgamento:

    from autotarefas.reader import read_workbook
    from autotarefas.profiling import profile_workbook

    leitura = read_workbook(Path("planilha.xlsx"))
    perfil = profile_workbook(leitura)

    print(perfil.row_count, perfil.column_count, perfil.fill_rate)
    for f in perfil.by_severity("aviso"):
        print(f.code, f.message)

A regra: a perfilagem OBSERVA. Valor repetido nao e erro. Coluna com
vazios nao e erro. Codigo numerico nao e chave. Transformar observacao em
regra e trabalho do perfil e do schema — nunca daqui.
"""

from .profiler import profile_workbook
from .result import (
    ColumnProfile,
    Finding,
    ProfileResult,
    Severity,
)

__all__ = [
    "ColumnProfile",
    "Finding",
    "ProfileResult",
    "Severity",
    "profile_workbook",
]
