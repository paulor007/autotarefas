"""Testes para autotarefas.core.audit."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from autotarefas.core.audit import AuditTrail, _hash_input


def _make_audit(tmp_path: Path) -> AuditTrail:
    """Cria AuditTrail isolado em tmp_path (não polui o sistema)."""
    return AuditTrail(db_path=tmp_path / "test_audit.db")


class TestAuditInit:
    """Testes da inicialização da AuditTrail."""

    def test_cria_db_se_nao_existir(self, tmp_path: Path) -> None:
        """AuditTrail cria o arquivo DB se ele não existe."""
        db_path = tmp_path / "novo" / "audit.db"
        AuditTrail(db_path=db_path)
        assert db_path.exists()

    def test_db_path_armazenado(self, tmp_path: Path) -> None:
        """db_path é armazenado corretamente."""
        db_path = tmp_path / "audit.db"
        audit = AuditTrail(db_path=db_path)
        assert audit.db_path == db_path

    def test_reinit_nao_apaga_dados(self, tmp_path: Path) -> None:
        """Inicializar AuditTrail 2x não apaga dados existentes."""
        db_path = tmp_path / "audit.db"

        audit1 = AuditTrail(db_path=db_path)
        audit1.record(
            task_name="test",
            status="success",
            started_at=datetime.now(UTC),
            duration_ms=10,
        )

        # Re-cria — não deve apagar
        audit2 = AuditTrail(db_path=db_path)
        entries = audit2.query()
        assert len(entries) == 1


class TestAuditRecord:
    """Testes do método record()."""

    def test_record_basico(self, tmp_path: Path) -> None:
        audit = _make_audit(tmp_path)
        audit.record(
            task_name="test_task",
            status="success",
            started_at=datetime.now(UTC),
            duration_ms=100,
        )

        entries = audit.query()
        assert len(entries) == 1
        assert entries[0]["task_name"] == "test_task"
        assert entries[0]["status"] == "success"
        assert entries[0]["duration_ms"] == 100

    def test_record_com_dados_completos(self, tmp_path: Path) -> None:
        audit = _make_audit(tmp_path)
        audit.record(
            task_name="big_task",
            status="failure",
            started_at=datetime.now(UTC),
            duration_ms=500,
            rows_affected=10,
            rows_failed=5,
            error_message="erro teste",
            args={"key": "value"},
        )
        entries = audit.query()
        assert len(entries) == 1
        assert entries[0]["rows_affected"] == 10
        assert entries[0]["rows_failed"] == 5
        assert entries[0]["error_message"] == "erro teste"

    def test_record_grava_user_default(self, tmp_path: Path) -> None:
        """Sem user explícito, pega do SO."""
        audit = _make_audit(tmp_path)
        audit.record(
            task_name="t",
            status="success",
            started_at=datetime.now(UTC),
            duration_ms=10,
        )
        entries = audit.query()
        # User vai ser USER, USERNAME ou 'unknown' — todos são str
        assert isinstance(entries[0]["user"], str)
        assert entries[0]["user"]  # não vazio

    def test_record_user_explicito(self, tmp_path: Path) -> None:
        audit = _make_audit(tmp_path)
        audit.record(
            task_name="t",
            status="success",
            started_at=datetime.now(UTC),
            duration_ms=10,
            user="custom_user",
        )
        entries = audit.query()
        assert entries[0]["user"] == "custom_user"

    def test_record_grava_environment(self, tmp_path: Path) -> None:
        """environment é gravado (vem do settings)."""
        audit = _make_audit(tmp_path)
        audit.record(
            task_name="t",
            status="success",
            started_at=datetime.now(UTC),
            duration_ms=10,
        )
        entries = audit.query()
        assert entries[0]["environment"]  # não vazio

    def test_record_multiplas_entradas(self, tmp_path: Path) -> None:
        audit = _make_audit(tmp_path)
        now = datetime.now(UTC)
        for i in range(5):
            audit.record(
                task_name=f"task_{i}",
                status="success",
                started_at=now,
                duration_ms=10,
            )
        entries = audit.query()
        assert len(entries) == 5


class TestAuditQuery:
    """Testes do método query()."""

    def test_query_vazio_retorna_lista_vazia(self, tmp_path: Path) -> None:
        audit = _make_audit(tmp_path)
        assert audit.query() == []

    def test_query_filtra_por_task_name(self, tmp_path: Path) -> None:
        audit = _make_audit(tmp_path)
        now = datetime.now(UTC)
        audit.record(task_name="a", status="success", started_at=now, duration_ms=10)
        audit.record(task_name="b", status="success", started_at=now, duration_ms=10)
        audit.record(task_name="a", status="failure", started_at=now, duration_ms=10)

        entries = audit.query(task_name="a")
        assert len(entries) == 2
        for entry in entries:
            assert entry["task_name"] == "a"

    def test_query_filtra_por_status(self, tmp_path: Path) -> None:
        audit = _make_audit(tmp_path)
        now = datetime.now(UTC)
        audit.record(task_name="a", status="success", started_at=now, duration_ms=10)
        audit.record(task_name="b", status="failure", started_at=now, duration_ms=10)

        entries = audit.query(status="success")
        assert len(entries) == 1
        assert entries[0]["status"] == "success"

    def test_query_combinacao_filtros(self, tmp_path: Path) -> None:
        audit = _make_audit(tmp_path)
        now = datetime.now(UTC)
        audit.record(task_name="a", status="success", started_at=now, duration_ms=10)
        audit.record(task_name="a", status="failure", started_at=now, duration_ms=10)
        audit.record(task_name="b", status="success", started_at=now, duration_ms=10)

        entries = audit.query(task_name="a", status="success")
        assert len(entries) == 1
        assert entries[0]["task_name"] == "a"
        assert entries[0]["status"] == "success"

    def test_query_limit(self, tmp_path: Path) -> None:
        audit = _make_audit(tmp_path)
        now = datetime.now(UTC)
        for i in range(20):
            audit.record(
                task_name=f"task_{i}",
                status="success",
                started_at=now,
                duration_ms=10,
            )

        entries = audit.query(limit=5)
        assert len(entries) == 5

    def test_query_ordenado_desc(self, tmp_path: Path) -> None:
        """Resultados mais recentes primeiro."""
        audit = _make_audit(tmp_path)
        now = datetime.now(UTC)
        audit.record(task_name="primeira", status="success", started_at=now, duration_ms=10)
        audit.record(task_name="ultima", status="success", started_at=now, duration_ms=10)

        entries = audit.query()
        assert entries[0]["task_name"] == "ultima"
        assert entries[1]["task_name"] == "primeira"


class TestHashInput:
    """Testes do helper _hash_input."""

    def test_none_retorna_string_vazia(self) -> None:
        assert _hash_input(None) == ""

    def test_string_simples(self) -> None:
        h = _hash_input("teste")
        assert len(h) == 64  # SHA-256 hex

    def test_dict_e_string_diferentes(self) -> None:
        h1 = _hash_input("teste")
        h2 = _hash_input({"key": "teste"})
        assert h1 != h2

    def test_consistencia(self) -> None:
        """Mesmo input → mesmo hash."""
        h1 = _hash_input({"a": 1, "b": 2})
        h2 = _hash_input({"b": 2, "a": 1})
        # sort_keys=True garante mesma ordem → mesmo hash
        assert h1 == h2

    def test_secret_muda_hash(self) -> None:
        h_sem_secret = _hash_input("teste")
        h_com_secret = _hash_input("teste", secret="chave")
        assert h_sem_secret != h_com_secret
