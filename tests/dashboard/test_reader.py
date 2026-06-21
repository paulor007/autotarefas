"""
Testes da camada de leitura do audit (``dashboard.reader``).

Usa o audit DB isolado por teste (fixture autouse ``_isolate_audit_db``
do conftest): cada teste grava via ``audit.record`` e le via
``dashboard.reader``, num banco temporario limpo.

Cobertura:
- leitura do audit (``read_entries``)
- execucoes estruturadas (``AuditEntry`` tipada)
- resumo por status (``summarize``)
- verificacao do input_hash: valida e invalida/adulterada
- banco vazio e banco indisponivel

Destino deste arquivo:
    tests/dashboard/test_reader.py
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from autotarefas.core.audit import audit
from autotarefas.dashboard.reader import (
    AuditEntry,
    read_entries,
    summarize,
    verify_input_hash,
)


def _record(status: str = "success", task_name: str = "validate", **kw: Any) -> None:
    """Helper: grava uma execucao no audit DB isolado do teste."""
    audit.record(
        task_name=task_name,
        status=status,
        started_at=datetime.now(UTC),
        duration_ms=10,
        **kw,
    )


# ============================================================
# Leitura e estrutura
# ============================================================


class TestReadEntries:
    """read_entries le execucoes e devolve AuditEntry."""

    def test_le_execucoes_gravadas(self) -> None:
        _record(task_name="backup")
        _record(task_name="validate")

        entries = read_entries()

        assert len(entries) == 2
        assert all(isinstance(e, AuditEntry) for e in entries)

    def test_entry_estruturada(self) -> None:
        _record(task_name="backup", status="success", rows_affected=42)

        entry = read_entries()[0]

        assert entry.task_name == "backup"
        assert entry.status == "success"
        assert entry.rows_affected == 42
        assert isinstance(entry.timestamp, datetime)

    def test_filtra_por_status(self) -> None:
        _record(status="success")
        _record(status="failure")

        apenas_falha = read_entries(status="failure")

        assert len(apenas_falha) == 1
        assert apenas_falha[0].status == "failure"


# ============================================================
# Resumo por status
# ============================================================


class TestSummarize:
    """summarize agrega total e contagem por status."""

    def test_resumo_por_status(self) -> None:
        _record(status="success")
        _record(status="success")
        _record(status="failure")

        resumo = summarize(read_entries())

        assert resumo.total == 3
        assert resumo.by_status == {"success": 2, "failure": 1}

    def test_resumo_vazio(self) -> None:
        resumo = summarize([])

        assert resumo.total == 0
        assert resumo.by_status == {}


# ============================================================
# Verificacao do input_hash (HMAC do input)
# ============================================================


class TestVerifyInputHash:
    """verify_input_hash confirma um input contra o hash registrado."""

    def test_hash_valido(self) -> None:
        entrada = {"arquivo": "dados.csv", "linhas": 10}
        _record(input_data=entrada)

        entry = read_entries()[0]

        assert entry.input_hash  # foi registrado
        assert verify_input_hash(entry, entrada) is True

    def test_hash_invalido_input_diferente(self) -> None:
        _record(input_data={"arquivo": "dados.csv"})

        entry = read_entries()[0]

        assert verify_input_hash(entry, {"arquivo": "OUTRO.csv"}) is False

    def test_hash_adulterado(self) -> None:
        _record(input_data={"x": 1})

        entry = read_entries()[0]
        # Simula linha adulterada: troca o input_hash por outro valor.
        adulterada = replace(entry, input_hash="0" * 64)

        assert verify_input_hash(adulterada, {"x": 1}) is False

    def test_sem_input_hash_retorna_false(self) -> None:
        _record()  # sem input_data -> input_hash vazio

        entry = read_entries()[0]

        assert entry.input_hash == ""
        assert verify_input_hash(entry, {"qualquer": "coisa"}) is False


# ============================================================
# Banco vazio / indisponivel
# ============================================================


class TestBancoIndisponivel:
    """read_entries degrada para [] sem dados ou sem banco."""

    def test_banco_vazio(self) -> None:
        # Nada gravado neste teste (DB isolado limpo).
        assert read_entries() == []

    def test_banco_inexistente(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        # Caminho cujo diretorio nao existe -> query trata o erro e da [].
        inexistente = tmp_path / "nao-existe" / "audit.db"
        monkeypatch.setattr(audit, "db_path", inexistente)

        assert read_entries() == []
