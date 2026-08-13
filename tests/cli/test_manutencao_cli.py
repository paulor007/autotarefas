"""Testes do comando manutencao expurgar."""

from __future__ import annotations

import importlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest
from click.testing import CliRunner

from autotarefas.cli.main import cli
from autotarefas.core.audit import AuditTrail


def _module() -> ModuleType:
    return importlib.import_module("autotarefas.cli.commands.manutencao")


def _isolate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[ModuleType, AuditTrail]:
    module = _module()
    trail = AuditTrail(db_path=tmp_path / "audit.db")

    monkeypatch.setattr(module, "audit", trail)
    monkeypatch.setattr(module.settings, "autotarefas_home", tmp_path)
    monkeypatch.setattr(module.settings, "environment", "dev")
    monkeypatch.setattr(module.settings, "audit_retention_days", None)

    return module, trail


def _old_log(tmp_path: Path) -> Path:
    path = tmp_path / "logs" / "autotarefas_2026-01-01.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("antigo", encoding="utf-8")
    timestamp = (datetime.now(UTC) - timedelta(days=10)).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path


def test_dry_run_nao_remove_nem_registra(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, trail = _isolate(monkeypatch, tmp_path)
    old_log = _old_log(tmp_path)

    result = CliRunner().invoke(
        cli,
        [
            "--dry-run",
            "manutencao",
            "expurgar",
            "--logs-days",
            "1",
            "--screenshots-days",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert old_log.exists()
    assert trail.query() == []
    assert "Nenhum dado foi removido" in result.output


def test_resposta_negativa_cancela_expurgo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, trail = _isolate(monkeypatch, tmp_path)
    old_log = _old_log(tmp_path)

    result = CliRunner().invoke(
        cli,
        [
            "manutencao",
            "expurgar",
            "--logs-days",
            "1",
            "--screenshots-days",
            "1",
        ],
        input="n\n",
    )

    assert result.exit_code == 0, result.output
    assert old_log.exists()
    assert trail.query() == []
    assert "Expurgo cancelado" in result.output


def test_yes_remove_e_registra(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, trail = _isolate(monkeypatch, tmp_path)
    old_log = _old_log(tmp_path)

    result = CliRunner().invoke(
        cli,
        [
            "--yes",
            "manutencao",
            "expurgar",
            "--logs-days",
            "1",
            "--screenshots-days",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert not old_log.exists()
    entries = trail.query()
    assert entries[0]["task_name"] == "manutencao.expurgar"
    assert "Expurgo concluido" in result.output


def test_comando_recusa_ambiente_demo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, _ = _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(module.settings, "environment", "demo")

    result = CliRunner().invoke(
        cli,
        ["--yes", "manutencao", "expurgar"],
    )

    assert result.exit_code == 2
    assert "exclusivo do modo real privado" in result.output
