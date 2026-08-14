"""
Task de comparacao entre duas planilhas (RF-REC-001).

Orquestra o que ja existe: o leitor abre cada arquivo, o nucleo puro
(:mod:`autotarefas.reconcile.compare`) classifica, e o resultado sai como
`TaskResult` — com audit trail automatico, como toda task do projeto.

A task NAO grava artefato: quem decide gravar (e onde) e a CLI. Assim a
mesma comparacao serve para o terminal, para o Live e para um teste, sem
efeito colateral escondido.

Leitura pura: nenhum arquivo de entrada e aberto para escrita.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.reader import ReaderError, read_workbook
from autotarefas.reconcile.artifacts import build_report_payload
from autotarefas.reconcile.compare import compare_tables
from autotarefas.reconcile.errors import CompareError
from autotarefas.reconcile.merge import ReconcilePolicy, ReconciliationResult, reconcile_tables
from autotarefas.reconcile.merge_artifacts import (
    build_report_payload as build_reconciliation_payload,
)
from autotarefas.reconcile.result import ComparisonResult, TableSource
from autotarefas.reconcile.transfer import TransferPolicy, TransferResult, transfer_values
from autotarefas.reconcile.transfer_artifacts import (
    build_report_payload as build_transfer_payload,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from autotarefas.reconcile.tolerance import Tolerance

#: Falhas que significam "o arquivo esta ruim", nao "o programa esta errado"
#: (mesma leitura que `services/analysis.py` faz do assunto). A lista e
#: fechada de proposito: um `except Exception` esconderia defeito nosso sob
#: a fachada de "planilha invalida".
_CORRUPT_FILE_ERRORS = (
    zipfile.BadZipFile,
    UnicodeDecodeError,
    ValueError,
    KeyError,
    OSError,
)


@dataclass(frozen=True, slots=True)
class SourceSelection:
    """Qual arquivo comparar — e, se preciso, qual aba e qual cabecalho."""

    path: Path
    sheet: str | None = None
    header_row: int | None = None


def _read_source(selection: SourceSelection, label: str) -> TableSource:
    """
    Le uma das fontes e devolve a tabela FIEL (texto exato do arquivo).

    Qualquer recusa do leitor vira `CompareError`: para quem pediu a
    comparacao, "a fonte B nao pode ser lida" e um erro de USO, com o motivo
    em portugues, e nao uma excecao tecnica no meio do caminho.
    """
    try:
        leitura = read_workbook(
            selection.path,
            sheet=selection.sheet,
            header_row=selection.header_row,
        )
    except ReaderError as exc:
        msg = f"fonte {label} ({selection.path.name}): {exc}"
        raise CompareError(msg) from exc
    except _CORRUPT_FILE_ERRORS as exc:
        msg = (
            f"fonte {label} ({selection.path.name}): nao foi possivel ler este arquivo. "
            f"Ele pode estar corrompido, protegido ou nao ser uma planilha valida "
            f"({type(exc).__name__})."
        )
        raise CompareError(msg) from exc

    frame = leitura.original_dataframe
    if not leitura.ok or frame is None:
        motivo = leitura.rejected_reason or "arquivo nao processado"
        msg = f"fonte {label} ({selection.path.name}): {motivo}"
        raise CompareError(msg)

    return TableSource(
        name=selection.path.name,
        frame=frame,
        first_data_row=leitura.data_start_row,
        sheet=leitura.selected_sheet,
        skipped_empty_rows=leitura.skipped_empty_rows,
    )


class ComparisonTask(BaseTask):
    """
    Compara duas planilhas por chave e classifica cada registro.

    Uso:
        task = ComparisonTask(
            source_a=SourceSelection(Path("janeiro.xlsx")),
            source_b=SourceSelection(Path("fevereiro.xlsx")),
            key_columns=("codigo",),
        )
        result = task.run()
        task.comparison  # ComparisonResult, para gerar os artefatos
    """

    name = "comparar"
    description = "Compara duas planilhas por chave e aponta as diferencas"

    def __init__(  # noqa: PLR0913 - quatro opcionais keyword-only
        self,
        source_a: SourceSelection,
        source_b: SourceSelection,
        *,
        key_columns: Sequence[str],
        columns: Sequence[str] | None = None,
        normalizations: Sequence[str] = (),
        tolerances: Sequence[Tolerance] = (),
        dry_run: bool = False,
    ) -> None:
        """
        Inicializa a comparacao.

        Args:
            source_a: fonte A (arquivo + aba/cabecalho opcionais).
            source_b: fonte B.
            key_columns: colunas que identificam o registro (ordem irrelevante).
            columns: colunas a comparar. None = todas as comuns, menos a chave.
            normalizations: 'espacos', 'caixa' e/ou 'digitos' — so para comparar.
            tolerances: tolerancias declaradas por coluna (REC-002).
            dry_run: mantido por contrato do BaseTask; a comparacao nunca
                escreve nas fontes, entao o resultado e o mesmo.
        """
        super().__init__(dry_run=dry_run)
        self.source_a = source_a
        self.source_b = source_b
        self.key_columns = tuple(key_columns)
        self.columns = tuple(columns) if columns is not None else None
        self.normalizations = tuple(normalizations)
        self.tolerances = tuple(tolerances)

        self.comparison: ComparisonResult | None = None
        self.table_a: TableSource | None = None
        self.table_b: TableSource | None = None

    def _compare(self) -> ComparisonResult:
        """Le as duas fontes e compara (compartilhado com a reconciliacao)."""
        self.table_a = _read_source(self.source_a, "A")
        self.table_b = _read_source(self.source_b, "B")
        self.comparison = compare_tables(
            self.table_a,
            self.table_b,
            key_columns=self.key_columns,
            columns=self.columns,
            normalizations=self.normalizations,
            tolerances=self.tolerances,
        )
        return self.comparison

    def execute(self) -> TaskResult:
        """Le as duas fontes, compara e devolve o resultado classificado."""
        started_at = datetime.now(UTC)
        comparacao = self._compare()

        data: dict[str, Any] = build_report_payload(comparacao)
        return self._make_result(
            status=TaskStatus.SUCCESS,
            started_at=started_at,
            rows_affected=len(comparacao.records),
            data=data,
        )


class TransferTask(ComparisonTask):
    """
    Enriquece o destino com os campos autorizados da fonte (REC-003).

    O destino e o lado A da comparacao; a fonte, o lado B. O arquivo de
    destino nao e alterado: o resultado sai em `transfer.rows`.
    """

    name = "transferir"
    description = "Copia campos autorizados de uma planilha para outra"

    def __init__(  # noqa: PLR0913 - quatro opcionais keyword-only
        self,
        destination: SourceSelection,
        source: SourceSelection,
        *,
        key_columns: Sequence[str],
        policy: TransferPolicy,
        normalizations: Sequence[str] = (),
        tolerances: Sequence[Tolerance] = (),
        dry_run: bool = False,
    ) -> None:
        super().__init__(
            destination,
            source,
            key_columns=key_columns,
            normalizations=normalizations,
            tolerances=tolerances,
            dry_run=dry_run,
        )
        self.policy = policy
        self.transfer: TransferResult | None = None

    def execute(self) -> TaskResult:
        """Compara destino x fonte e aplica a transferencia autorizada."""
        started_at = datetime.now(UTC)
        comparacao = self._compare()
        if self.table_a is None or self.table_b is None:  # pragma: no cover - garantido acima
            msg = "as fontes nao foram lidas"
            raise CompareError(msg)

        transferencia = transfer_values(self.table_a, self.table_b, comparacao, self.policy)
        self.transfer = transferencia

        data: dict[str, Any] = build_transfer_payload(transferencia, self.table_b)
        return self._make_result(
            status=TaskStatus.SUCCESS,
            started_at=started_at,
            rows_affected=transferencia.changed_count,
            rows_failed=len(transferencia.not_found),
            data=data,
        )


class ReconciliationTask(ComparisonTask):
    """
    Compara e DECIDE: gera a base conciliada e a lista de revisao (REC-002).

    Herda a leitura e a comparacao; acrescenta a politica declarada (fonte
    principal, campos atualizaveis) e o resultado da conciliacao.
    """

    name = "conciliar"
    description = "Reconcilia duas planilhas por regras declaradas"

    def __init__(  # noqa: PLR0913 - cinco opcionais keyword-only
        self,
        source_a: SourceSelection,
        source_b: SourceSelection,
        *,
        key_columns: Sequence[str],
        policy: ReconcilePolicy | None = None,
        columns: Sequence[str] | None = None,
        normalizations: Sequence[str] = (),
        tolerances: Sequence[Tolerance] = (),
        dry_run: bool = False,
    ) -> None:
        super().__init__(
            source_a,
            source_b,
            key_columns=key_columns,
            columns=columns,
            normalizations=normalizations,
            tolerances=tolerances,
            dry_run=dry_run,
        )
        self.policy = policy if policy is not None else ReconcilePolicy()
        self.reconciliation: ReconciliationResult | None = None

    def execute(self) -> TaskResult:
        """Compara, aplica as regras declaradas e devolve o resultado."""
        started_at = datetime.now(UTC)
        comparacao = self._compare()
        if self.table_a is None or self.table_b is None:  # pragma: no cover - garantido acima
            msg = "as fontes nao foram lidas"
            raise CompareError(msg)

        conciliacao = reconcile_tables(self.table_a, self.table_b, comparacao, self.policy)
        self.reconciliation = conciliacao

        data: dict[str, Any] = build_reconciliation_payload(conciliacao)
        return self._make_result(
            status=TaskStatus.SUCCESS,
            started_at=started_at,
            rows_affected=len(conciliacao.records),
            rows_failed=len(conciliacao.review),
            data=data,
        )


__all__ = ["ComparisonTask", "ReconciliationTask", "SourceSelection", "TransferTask"]
