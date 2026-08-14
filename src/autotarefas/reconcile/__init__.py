"""
Reconciliacao entre planilhas do AutoTarefas.

Comeca pela comparacao (RF-REC-001): duas versoes da mesma base, uma
chave, e a resposta para "o que mudou?" — sem conferencia visual lado a
lado e sem alterar nenhuma das fontes.

Uso:
    from pathlib import Path

    from autotarefas.reconcile import ComparisonTask, SourceSelection

    task = ComparisonTask(
        source_a=SourceSelection(Path("base_janeiro.xlsx")),
        source_b=SourceSelection(Path("base_fevereiro.xlsx")),
        key_columns=("codigo",),
    )
    resultado = task.run()
    task.comparison.counts  # {'identico': 3, 'divergente': 1, ...}

O nucleo (`compare_tables`) e puro e nao abre arquivo: da para comparar
qualquer par de tabelas ja carregadas. Os artefatos ficam em
`autotarefas.reconcile.artifacts`.

Limites desta primeira fatia estao declarados em `compare.LIMITATIONS` e
viajam dentro do proprio relatorio — tolerancias numericas e de data sao
da RF-REC-002.
"""

from autotarefas.reconcile.artifacts import (
    JSON_REPORT_NAME,
    ONLY_A_CSV_NAME,
    ONLY_B_CSV_NAME,
    XLSX_NAME,
    build_report_payload,
    write_comparison_artifacts,
)
from autotarefas.reconcile.compare import (
    LIMITATIONS,
    NORMALIZATION_OPTIONS,
    compare_tables,
)
from autotarefas.reconcile.errors import CompareError
from autotarefas.reconcile.merge import (
    FieldDecision,
    ReconciledRecord,
    ReconcilePolicy,
    ReconciliationResult,
    ReviewItem,
    reconcile_tables,
)
from autotarefas.reconcile.merge_artifacts import write_reconciliation_artifacts
from autotarefas.reconcile.result import (
    CellDifference,
    CompareWarning,
    ComparisonResult,
    KeyConflict,
    RecordComparison,
    SourceInfo,
    TableSource,
)
from autotarefas.reconcile.task import ComparisonTask, ReconciliationTask, SourceSelection
from autotarefas.reconcile.tolerance import Tolerance, parse_tolerance, parse_tolerances

__all__ = [
    "JSON_REPORT_NAME",
    "LIMITATIONS",
    "NORMALIZATION_OPTIONS",
    "ONLY_A_CSV_NAME",
    "ONLY_B_CSV_NAME",
    "XLSX_NAME",
    "CellDifference",
    "CompareError",
    "CompareWarning",
    "ComparisonResult",
    "ComparisonTask",
    "FieldDecision",
    "KeyConflict",
    "ReconcilePolicy",
    "ReconciledRecord",
    "ReconciliationResult",
    "ReconciliationTask",
    "RecordComparison",
    "ReviewItem",
    "SourceInfo",
    "SourceSelection",
    "TableSource",
    "Tolerance",
    "build_report_payload",
    "compare_tables",
    "parse_tolerance",
    "parse_tolerances",
    "reconcile_tables",
    "write_comparison_artifacts",
    "write_reconciliation_artifacts",
]
