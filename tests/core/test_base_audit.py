"""
Testes da integracao do audit no BaseTask.

Confirma o fix da Fase 8: BaseTask.run() chama _record_audit(), de
modo que TODA task que herda de BaseTask eh registrada no audit
trail automaticamente (sucesso, falha, skipped, dry-run).

ESTRATEGIA:
- Tasks fake (definidas aqui) cobrindo cada status
- Mock de audit.record para capturar chamadas (sem tocar DB real)
- Confirma que erro no audit NAO quebra a task

Complementa test_base.py (que testa run/execute/hooks/_make_result).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.core.exceptions import AutoTarefasError

# ============================================================
# Tasks fake (uma por cenario)
# ============================================================


class _SuccessTask(BaseTask):
    """Task que sempre retorna SUCCESS."""

    name = "fake_success"
    description = "Task de teste que da sucesso"

    def execute(self) -> TaskResult:
        started_at = datetime.now(UTC)
        return self._make_result(
            status=TaskStatus.SUCCESS,
            started_at=started_at,
            rows_affected=10,
            rows_failed=2,
        )


class _SkippedTask(BaseTask):
    """Task que retorna SKIPPED."""

    name = "fake_skipped"
    description = "Task de teste que da skipped"

    def execute(self) -> TaskResult:
        started_at = datetime.now(UTC)
        return self._make_result(
            status=TaskStatus.SKIPPED,
            started_at=started_at,
        )


class _DryRunTask(BaseTask):
    """Task que retorna DRY_RUN."""

    name = "fake_dryrun"
    description = "Task de teste que retorna DRY_RUN"

    def execute(self) -> TaskResult:
        started_at = datetime.now(UTC)
        return self._make_result(
            status=TaskStatus.DRY_RUN,
            started_at=started_at,
        )


class _FailingTask(BaseTask):
    """Task que levanta AutoTarefasError."""

    name = "fake_failing"
    description = "Task de teste que falha"

    def execute(self) -> TaskResult:
        raise AutoTarefasError("erro proposital de teste")


# ============================================================
# Fixture: captura audit.record
# ============================================================


@pytest.fixture
def audit_records(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """
    Substitui audit.record por um captador. Retorna a lista de
    chamadas (cada item eh o dict de kwargs passado a record).

    Como retorna valor (a lista usada nos testes), eh fixture comum.
    """
    records: list[dict[str, Any]] = []

    def fake_record(**kwargs: Any) -> None:
        records.append(kwargs)

    monkeypatch.setattr(
        "autotarefas.core.base.audit.record",
        fake_record,
    )
    return records


# ============================================================
# Testes: cada status grava no audit
# ============================================================


class TestAuditRecordedPerStatus:
    """Toda task grava no audit, qualquer que seja o status."""

    def test_success_grava(
        self,
        audit_records: list[dict[str, Any]],
    ) -> None:
        _SuccessTask().run()
        assert len(audit_records) == 1
        assert audit_records[0]["task_name"] == "fake_success"
        assert audit_records[0]["status"] == "success"

    def test_skipped_grava(
        self,
        audit_records: list[dict[str, Any]],
    ) -> None:
        _SkippedTask().run()
        assert len(audit_records) == 1
        assert audit_records[0]["status"] == "skipped"

    def test_dry_run_grava(
        self,
        audit_records: list[dict[str, Any]],
    ) -> None:
        _DryRunTask().run()
        assert len(audit_records) == 1
        assert audit_records[0]["status"] == "dry_run"

    def test_failure_grava(
        self,
        audit_records: list[dict[str, Any]],
    ) -> None:
        result = _FailingTask().run()
        # run() captura AutoTarefasError e retorna FAILURE
        assert result.status == TaskStatus.FAILURE
        assert len(audit_records) == 1
        assert audit_records[0]["status"] == "failure"


# ============================================================
# Testes: conteudo do record
# ============================================================


class TestAuditRecordContent:
    """O record contem os campos esperados."""

    def test_record_tem_campos_principais(
        self,
        audit_records: list[dict[str, Any]],
    ) -> None:
        _SuccessTask().run()
        rec = audit_records[0]
        assert "task_name" in rec
        assert "status" in rec
        assert "started_at" in rec
        assert "duration_ms" in rec

    def test_record_propaga_rows(
        self,
        audit_records: list[dict[str, Any]],
    ) -> None:
        """rows_affected e rows_failed do result vao pro audit."""
        _SuccessTask().run()
        rec = audit_records[0]
        assert rec["rows_affected"] == 10
        assert rec["rows_failed"] == 2

    def test_failure_record_tem_error_message(
        self,
        audit_records: list[dict[str, Any]],
    ) -> None:
        _FailingTask().run()
        rec = audit_records[0]
        assert rec["error_message"] is not None
        assert "proposital" in rec["error_message"]


# ============================================================
# Teste: erro no audit nao quebra a task
# ============================================================


class TestAuditRobustness:
    """Falha no audit.record nao deve interromper a task."""

    def test_erro_no_audit_nao_propaga(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Se audit.record levanta, a task ainda retorna o result."""

        def fake_record_raises(**kwargs: Any) -> None:
            raise RuntimeError("audit DB offline")

        monkeypatch.setattr(
            "autotarefas.core.base.audit.record",
            fake_record_raises,
        )

        # Nao deve propagar a excecao do audit
        result = _SuccessTask().run()
        assert result.status == TaskStatus.SUCCESS

    def test_erro_no_audit_nao_quebra_em_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Mesmo no fluxo de falha, erro no audit nao propaga."""

        def fake_record_raises(**kwargs: Any) -> None:
            raise RuntimeError("audit DB offline")

        monkeypatch.setattr(
            "autotarefas.core.base.audit.record",
            fake_record_raises,
        )

        # Task falha (AutoTarefasError) E audit falha - mas run() retorna
        # FAILURE normalmente, sem propagar o erro do audit
        result = _FailingTask().run()
        assert result.status == TaskStatus.FAILURE
