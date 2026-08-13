"""Testes da politica de retencao e do expurgo privado."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from autotarefas.core.audit import AuditTrail
from autotarefas.core.retention import build_purge_plan, execute_purge


def _write_with_age(
    path: Path,
    *,
    now: datetime,
    age_days: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("teste", encoding="utf-8")
    timestamp = (now - timedelta(days=age_days)).timestamp()
    os.utime(path, (timestamp, timestamp))


def test_plano_inclui_somente_arquivos_gerenciados_expirados(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC)
    logs = tmp_path / "logs"
    screenshots = tmp_path / "screenshots"
    trail = AuditTrail(db_path=tmp_path / "audit.db")

    old_log = logs / "autotarefas_2026-01-01.log"
    fresh_log = logs / "autotarefas_2026-08-13.log"
    unrelated = logs / "arquivo_do_operador.log"
    old_screenshot = screenshots / "execucao" / "pagina.png"
    unrelated_screenshot = screenshots / "notas.txt"

    _write_with_age(old_log, now=now, age_days=40)
    _write_with_age(fresh_log, now=now, age_days=1)
    _write_with_age(unrelated, now=now, age_days=100)
    _write_with_age(old_screenshot, now=now, age_days=40)
    _write_with_age(unrelated_screenshot, now=now, age_days=100)

    plan = build_purge_plan(
        audit=trail,
        logs_dir=logs,
        screenshots_dir=screenshots,
        log_retention_days=30,
        screenshot_retention_days=30,
        audit_retention_days=None,
        now=now,
    )

    assert plan.log_files == (old_log,)
    assert plan.screenshot_files == (old_screenshot,)
    assert plan.audit_rows == 0
    assert plan.total_items == 2

    assert old_log.exists()
    assert fresh_log.exists()
    assert unrelated.exists()
    assert old_screenshot.exists()
    assert unrelated_screenshot.exists()


def test_execucao_remove_exatamente_o_plano_e_registra_audit(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC)
    logs = tmp_path / "logs"
    screenshots = tmp_path / "screenshots"
    trail = AuditTrail(db_path=tmp_path / "audit.db")

    old_log = logs / "autotarefas_2026-01-01.log.zip"
    fresh_log = logs / "autotarefas_2026-08-13.log"
    old_screenshot = screenshots / "pagina.jpg"
    fresh_screenshot = screenshots / "pagina_nova.png"

    _write_with_age(old_log, now=now, age_days=40)
    _write_with_age(fresh_log, now=now, age_days=1)
    _write_with_age(old_screenshot, now=now, age_days=40)
    _write_with_age(fresh_screenshot, now=now, age_days=1)

    trail.record(
        task_name="antigo",
        status="success",
        started_at=now - timedelta(days=60),
        duration_ms=1,
    )
    trail.record(
        task_name="recente",
        status="success",
        started_at=now - timedelta(days=1),
        duration_ms=1,
    )

    plan = build_purge_plan(
        audit=trail,
        logs_dir=logs,
        screenshots_dir=screenshots,
        log_retention_days=30,
        screenshot_retention_days=30,
        audit_retention_days=30,
        now=now,
    )

    assert plan.audit_rows == 1

    result = execute_purge(plan, audit=trail)

    assert result.removed_logs == 1
    assert result.removed_screenshots == 1
    assert result.removed_audit_rows == 1
    assert result.partial is False

    assert not old_log.exists()
    assert fresh_log.exists()
    assert not old_screenshot.exists()
    assert fresh_screenshot.exists()

    entries = trail.query(limit=20)
    names = [entry["task_name"] for entry in entries]
    assert "antigo" not in names
    assert "recente" in names
    assert "manutencao.expurgar" in names

    maintenance = next(entry for entry in entries if entry["task_name"] == "manutencao.expurgar")
    args = json.loads(maintenance["args"])
    assert args["logs_removed"] == 1
    assert args["screenshots_removed"] == 1
    assert args["audit_rows_removed"] == 1


def test_audit_sem_prazo_permanece_intacto(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    trail = AuditTrail(db_path=tmp_path / "audit.db")
    trail.record(
        task_name="historico",
        status="success",
        started_at=now - timedelta(days=500),
        duration_ms=1,
    )

    plan = build_purge_plan(
        audit=trail,
        logs_dir=tmp_path / "logs",
        screenshots_dir=tmp_path / "screenshots",
        log_retention_days=30,
        screenshot_retention_days=30,
        audit_retention_days=None,
        now=now,
    )

    assert plan.audit_cutoff is None
    assert plan.audit_rows == 0
    assert trail.query()[0]["task_name"] == "historico"


def test_count_e_purge_do_audit_respeitam_o_limite(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=30)
    trail = AuditTrail(db_path=tmp_path / "audit.db")

    trail.record(
        task_name="antigo",
        status="success",
        started_at=now - timedelta(days=31),
        duration_ms=1,
    )
    trail.record(
        task_name="limite",
        status="success",
        started_at=cutoff,
        duration_ms=1,
    )
    trail.record(
        task_name="recente",
        status="success",
        started_at=now - timedelta(days=1),
        duration_ms=1,
    )

    assert trail.count_before(cutoff) == 1
    assert trail.purge_before(cutoff) == 1

    names = [entry["task_name"] for entry in trail.query()]
    assert names == ["recente", "limite"]
