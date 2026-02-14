"""
Testes do módulo de armazenamento de jobs (job_store).

Testa:
    - JobStatus: Estados possíveis de um job
    - Job: Representação de um job agendado
    - JobStore: Gerenciador de persistência em JSON

O módulo job_store é responsável por PERSISTIR os jobs agendados em disco,
permitindo que o scheduler recupere os jobs entre reinicializações do sistema.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

# ============================================================================
# Testes de JobStatus
# ============================================================================


class TestJobStatus:
    """Testes do enum JobStatus."""

    def test_status_values(self) -> None:
        """Deve ter todos os status esperados."""
        from autotarefas.core.storage.job_store import JobStatus

        assert JobStatus.ACTIVE.value == "active"
        assert JobStatus.PAUSED.value == "paused"
        assert JobStatus.DISABLED.value == "disabled"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"

    def test_status_from_string(self) -> None:
        """Deve converter string para enum."""
        from autotarefas.core.storage.job_store import JobStatus

        assert JobStatus("active") == JobStatus.ACTIVE
        assert JobStatus("paused") == JobStatus.PAUSED
        assert JobStatus("failed") == JobStatus.FAILED

    def test_status_invalid_value(self) -> None:
        """Deve falhar com valor inválido."""
        from autotarefas.core.storage.job_store import JobStatus

        with pytest.raises(ValueError):
            JobStatus("invalid_status")


# ============================================================================
# Testes de Job
# ============================================================================


class TestJob:
    """Testes da dataclass Job."""

    def test_job_creation_minimal(self) -> None:
        """Deve criar job com campos mínimos."""
        from autotarefas.core.storage.job_store import Job, JobStatus

        job = Job(
            id="test-123",
            name="backup_diario",
            task="backup",
            schedule="0 2 * * *",
        )

        assert job.id == "test-123"
        assert job.name == "backup_diario"
        assert job.task == "backup"
        assert job.schedule == "0 2 * * *"
        assert job.status == JobStatus.ACTIVE
        assert job.enabled is True

    def test_job_creation_full(self) -> None:
        """Deve criar job com todos os campos."""
        from autotarefas.core.storage.job_store import Job, JobStatus

        job = Job(
            id="full-job",
            name="limpeza_temp",
            task="cleaner",
            schedule="0 3 * * *",
            schedule_type="cron",
            params={"path": "/tmp", "days": 7},
            status=JobStatus.PAUSED,
            description="Limpa arquivos temporários",
            tags=["manutenção", "diário"],
            max_retries=5,
            retry_delay=120,
            timeout=1800,
            enabled=False,
        )

        assert job.name == "limpeza_temp"
        assert job.params["path"] == "/tmp"
        assert job.status == JobStatus.PAUSED
        assert job.tags == ["manutenção", "diário"]
        assert job.max_retries == 5

    def test_job_defaults(self) -> None:
        """Deve ter valores padrão corretos."""
        from autotarefas.core.storage.job_store import Job, JobStatus

        job = Job(id="t", name="test", task="backup", schedule="* * * * *")

        assert job.schedule_type == "cron"
        assert job.params == {}
        assert job.status == JobStatus.ACTIVE
        assert job.description == ""
        assert job.tags == []
        assert job.run_count == 0
        assert job.success_count == 0
        assert job.error_count == 0
        assert job.last_error is None
        assert job.max_retries == 3
        assert job.retry_delay == 60
        assert job.timeout == 3600
        assert job.enabled is True

    def test_job_timestamps_auto_set(self) -> None:
        """created_at e updated_at devem ser definidos automaticamente."""
        from autotarefas.core.storage.job_store import Job

        job = Job(id="t", name="test", task="backup", schedule="* * * * *")

        assert job.created_at is not None
        assert job.updated_at is not None
        assert isinstance(job.created_at, datetime)

    def test_job_status_from_string(self) -> None:
        """Deve aceitar status como string e converter para enum."""
        from autotarefas.core.storage.job_store import Job, JobStatus

        job = Job(
            id="t",
            name="test",
            task="backup",
            schedule="* * * * *",
            status="paused",  # type: ignore
        )

        assert job.status == JobStatus.PAUSED


class TestJobSuccessRate:
    """Testes da propriedade success_rate."""

    def test_success_rate_no_runs(self) -> None:
        """Taxa deve ser 0 sem execuções."""
        from autotarefas.core.storage.job_store import Job

        job = Job(id="t", name="test", task="backup", schedule="* * * * *")
        assert job.success_rate == 0.0

    def test_success_rate_all_success(self) -> None:
        """Taxa deve ser 1.0 com 100% sucesso."""
        from autotarefas.core.storage.job_store import Job

        job = Job(
            id="t",
            name="test",
            task="backup",
            schedule="* * * * *",
            run_count=10,
            success_count=10,
        )
        assert job.success_rate == 1.0

    def test_success_rate_partial(self) -> None:
        """Taxa deve calcular corretamente."""
        from autotarefas.core.storage.job_store import Job

        job = Job(
            id="t",
            name="test",
            task="backup",
            schedule="* * * * *",
            run_count=10,
            success_count=7,
        )
        assert job.success_rate == 0.7


class TestJobMarkExecuted:
    """Testes do método mark_executed."""

    def test_mark_executed_success(self) -> None:
        """Deve registrar execução com sucesso."""
        from autotarefas.core.storage.job_store import Job, JobStatus

        job = Job(id="t", name="test", task="backup", schedule="* * * * *")

        job.mark_executed(success=True, duration=5.5)

        assert job.run_count == 1
        assert job.success_count == 1
        assert job.error_count == 0
        assert job.last_duration == 5.5
        assert job.last_error is None
        assert job.status == JobStatus.ACTIVE
        assert job.last_run is not None

    def test_mark_executed_failure(self) -> None:
        """Deve registrar execução com falha."""
        from autotarefas.core.storage.job_store import Job, JobStatus

        job = Job(id="t", name="test", task="backup", schedule="* * * * *")

        job.mark_executed(success=False, duration=2.0, error="Connection timeout")

        assert job.run_count == 1
        assert job.success_count == 0
        assert job.error_count == 1
        assert job.last_error == "Connection timeout"
        assert job.status == JobStatus.FAILED

    def test_mark_executed_with_next_run(self) -> None:
        """Deve definir próxima execução."""
        from autotarefas.core.storage.job_store import Job

        job = Job(id="t", name="test", task="backup", schedule="* * * * *")
        next_time = datetime.now()

        job.mark_executed(success=True, duration=1.0, next_run=next_time)

        assert job.next_run is not None

    def test_mark_executed_multiple(self) -> None:
        """Deve acumular estatísticas."""
        from autotarefas.core.storage.job_store import Job

        job = Job(id="t", name="test", task="backup", schedule="* * * * *")

        job.mark_executed(success=True, duration=1.0)
        job.mark_executed(success=True, duration=2.0)
        job.mark_executed(success=False, duration=3.0, error="Error")

        assert job.run_count == 3
        assert job.success_count == 2
        assert job.error_count == 1
        assert job.last_duration == 3.0


class TestJobSerialization:
    """Testes de to_dict e from_dict."""

    def test_to_dict(self) -> None:
        """to_dict deve retornar dicionário serializável."""
        from autotarefas.core.storage.job_store import Job, JobStatus

        job = Job(
            id="serial-test",
            name="backup_docs",
            task="backup",
            schedule="0 2 * * *",
            params={"source": "/docs"},
            status=JobStatus.ACTIVE,
            tags=["importante"],
        )

        data = job.to_dict()

        assert isinstance(data, dict)
        assert data["id"] == "serial-test"
        assert data["name"] == "backup_docs"
        assert data["status"] == "active"
        assert data["params"] == {"source": "/docs"}
        assert data["tags"] == ["importante"]

    def test_from_dict(self) -> None:
        """from_dict deve recriar job."""
        from autotarefas.core.storage.job_store import Job, JobStatus

        data = {
            "id": "from-dict-test",
            "name": "monitor_sistema",
            "task": "monitor",
            "schedule": "*/5 * * * *",
            "status": "paused",
            "params": {"threshold": 80},
            "run_count": 100,
            "success_count": 95,
        }

        job = Job.from_dict(data)

        assert job.id == "from-dict-test"
        assert job.name == "monitor_sistema"
        assert job.status == JobStatus.PAUSED
        assert job.params["threshold"] == 80
        assert job.run_count == 100
        assert job.success_count == 95

    def test_roundtrip(self) -> None:
        """to_dict -> from_dict deve preservar dados."""
        from autotarefas.core.storage.job_store import Job, JobStatus

        original = Job(
            id="roundtrip",
            name="relatorio",
            task="reporter",
            schedule="0 8 * * 1",
            params={"format": "html"},
            status=JobStatus.ACTIVE,
            tags=["semanal"],
            run_count=52,
            success_count=50,
            error_count=2,
        )

        data = original.to_dict()
        restored = Job.from_dict(data)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.task == original.task
        assert restored.status == original.status
        assert restored.run_count == original.run_count

    def test_from_dict_generates_id_if_missing(self) -> None:
        """from_dict deve gerar ID se não fornecido."""
        from autotarefas.core.storage.job_store import Job

        data = {
            "name": "sem_id",
            "task": "backup",
            "schedule": "* * * * *",
        }

        job = Job.from_dict(data)

        assert job.id is not None
        assert len(job.id) > 0


# ============================================================================
# Testes de JobStore
# ============================================================================


class TestJobStore:
    """Testes da classe JobStore."""

    def test_store_creation(self, temp_dir: Path) -> None:
        """Deve criar store com arquivo."""
        from autotarefas.core.storage.job_store import JobStore

        filepath = temp_dir / "test_jobs.json"
        store = JobStore(filepath)

        assert store is not None
        assert store.filepath == filepath

    def test_store_create_job(self, temp_dir: Path) -> None:
        """create deve criar job com campos corretos."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "jobs.json")

        job = store.create(
            name="backup_teste",
            task="backup",
            schedule="0 2 * * *",
            params={"source": "/home"},
        )

        assert job.name == "backup_teste"
        assert job.task == "backup"
        assert job.id is not None

    def test_store_create_duplicate_name_fails(self, temp_dir: Path) -> None:
        """create deve falhar se nome já existe."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "jobs.json")

        job1 = store.create(name="unico", task="backup", schedule="* * * * *")
        store.save(job1)

        with pytest.raises(ValueError, match="[Jj]á existe|already"):
            store.create(name="unico", task="cleaner", schedule="* * * * *")

    def test_store_save_and_get(self, temp_dir: Path) -> None:
        """save e get devem funcionar."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "jobs.json")

        job = store.create(name="save_test", task="backup", schedule="* * * * *")
        store.save(job)

        retrieved = store.get(job.id)

        assert retrieved is not None
        assert retrieved.name == "save_test"

    def test_store_get_nonexistent(self, temp_dir: Path) -> None:
        """get deve retornar None para ID inexistente."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "jobs.json")

        result = store.get("nonexistent-id")
        assert result is None

    def test_store_get_by_name(self, temp_dir: Path) -> None:
        """get_by_name deve encontrar job pelo nome."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "jobs.json")

        job = store.create(name="findme", task="backup", schedule="* * * * *")
        store.save(job)

        found = store.get_by_name("findme")

        assert found is not None
        assert found.id == job.id

    def test_store_get_by_name_not_found(self, temp_dir: Path) -> None:
        """get_by_name deve retornar None se não encontrar."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "jobs.json")

        result = store.get_by_name("inexistente")
        assert result is None

    def test_store_delete(self, temp_dir: Path) -> None:
        """delete deve remover job."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "jobs.json")

        job = store.create(name="deleteme", task="backup", schedule="* * * * *")
        store.save(job)

        result = store.delete(job.id)

        assert result is True
        assert store.get(job.id) is None

    def test_store_delete_nonexistent(self, temp_dir: Path) -> None:
        """delete deve retornar False para ID inexistente."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "jobs.json")

        result = store.delete("nonexistent-id")
        assert result is False

    def test_store_list_all(self, temp_dir: Path) -> None:
        """list_all deve retornar todos os jobs ordenados."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "jobs.json")

        job_c = store.create(name="charlie", task="backup", schedule="* * * * *")
        job_a = store.create(name="alpha", task="backup", schedule="* * * * *")
        job_b = store.create(name="bravo", task="backup", schedule="* * * * *")

        store.save(job_c)
        store.save(job_a)
        store.save(job_b)

        jobs = store.list_all()

        assert len(jobs) == 3
        assert jobs[0].name == "alpha"
        assert jobs[1].name == "bravo"
        assert jobs[2].name == "charlie"

    def test_store_list_enabled(self, temp_dir: Path) -> None:
        """list_enabled deve retornar apenas jobs habilitados."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "jobs.json")

        job1 = store.create(
            name="enabled1", task="backup", schedule="* * * * *", enabled=True
        )
        job2 = store.create(
            name="disabled1", task="backup", schedule="* * * * *", enabled=False
        )
        job3 = store.create(
            name="enabled2", task="backup", schedule="* * * * *", enabled=True
        )

        store.save(job1)
        store.save(job2)
        store.save(job3)

        enabled_jobs = store.list_enabled()

        assert len(enabled_jobs) == 2
        names = [j.name for j in enabled_jobs]
        assert "enabled1" in names
        assert "enabled2" in names
        assert "disabled1" not in names


class TestJobStoreUpdateStatus:
    """Testes de update_status."""

    def test_update_status_success(self, temp_dir: Path) -> None:
        """update_status deve atualizar status do job."""
        from autotarefas.core.storage.job_store import JobStatus, JobStore

        store = JobStore(temp_dir / "jobs.json")

        job = store.create(name="status_test", task="backup", schedule="* * * * *")
        store.save(job)

        result = store.update_status(job.id, JobStatus.PAUSED)

        assert result is True

        updated = store.get(job.id)
        assert updated is not None
        assert updated.status == JobStatus.PAUSED
        assert updated.enabled is False

    def test_update_status_to_active(self, temp_dir: Path) -> None:
        """Atualizar para ACTIVE deve habilitar o job."""
        from autotarefas.core.storage.job_store import JobStatus, JobStore

        store = JobStore(temp_dir / "jobs.json")

        job = store.create(
            name="reactivate", task="backup", schedule="* * * * *", enabled=False
        )
        store.save(job)

        store.update_status(job.id, JobStatus.ACTIVE)

        updated = store.get(job.id)
        assert updated is not None
        assert updated.status == JobStatus.ACTIVE
        assert updated.enabled is True

    def test_update_status_nonexistent(self, temp_dir: Path) -> None:
        """update_status deve retornar False para ID inexistente."""
        from autotarefas.core.storage.job_store import JobStatus, JobStore

        store = JobStore(temp_dir / "jobs.json")

        result = store.update_status("fake-id", JobStatus.PAUSED)
        assert result is False


class TestJobStoreClear:
    """Testes de clear."""

    def test_clear_removes_all(self, temp_dir: Path) -> None:
        """clear deve remover todos os jobs."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "jobs.json")

        for i in range(5):
            job = store.create(name=f"job_{i}", task="backup", schedule="* * * * *")
            store.save(job)

        count = store.clear()

        assert count == 5
        assert len(store.list_all()) == 0

    def test_clear_empty_store(self, temp_dir: Path) -> None:
        """clear em store vazio deve retornar 0."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "jobs.json")

        count = store.clear()
        assert count == 0


class TestJobStorePersistence:
    """Testes de persistência em disco."""

    def test_persistence_save_creates_file(self, temp_dir: Path) -> None:
        """save deve criar arquivo JSON."""
        from autotarefas.core.storage.job_store import JobStore

        filepath = temp_dir / "persist_test.json"
        store = JobStore(filepath)

        job = store.create(name="persist", task="backup", schedule="* * * * *")
        store.save(job)

        assert filepath.exists()

    def test_persistence_file_format(self, temp_dir: Path) -> None:
        """Arquivo deve ter formato JSON válido."""
        from autotarefas.core.storage.job_store import JobStore

        filepath = temp_dir / "format_test.json"
        store = JobStore(filepath)

        job = store.create(name="format", task="backup", schedule="* * * * *")
        store.save(job)

        with open(filepath) as f:
            data = json.load(f)

        assert "version" in data
        assert "jobs" in data
        assert isinstance(data["jobs"], list)
        assert len(data["jobs"]) == 1

    def test_persistence_reload(self, temp_dir: Path) -> None:
        """Jobs devem ser recuperados após reload."""
        from autotarefas.core.storage.job_store import JobStore

        filepath = temp_dir / "reload_test.json"

        # Criar e salvar
        store1 = JobStore(filepath)
        job = store1.create(
            name="reload_me",
            task="backup",
            schedule="0 2 * * *",
            params={"important": True},
        )
        store1.save(job)

        # Recarregar em nova instância
        store2 = JobStore(filepath)
        reloaded = store2.get_by_name("reload_me")

        assert reloaded is not None
        assert reloaded.task == "backup"
        assert reloaded.params["important"] is True

    def test_persistence_updates_preserved(self, temp_dir: Path) -> None:
        """Atualizações devem ser preservadas."""
        from autotarefas.core.storage.job_store import JobStore

        filepath = temp_dir / "update_persist.json"

        # Criar, executar e salvar
        store1 = JobStore(filepath)
        job = store1.create(name="updater", task="backup", schedule="* * * * *")
        store1.save(job)

        job.mark_executed(success=True, duration=5.0)
        store1.save(job)

        # Recarregar
        store2 = JobStore(filepath)
        reloaded = store2.get_by_name("updater")

        assert reloaded is not None
        assert reloaded.run_count == 1
        assert reloaded.success_count == 1


class TestJobStoreEdgeCases:
    """Testes de casos extremos."""

    def test_empty_file_handling(self, temp_dir: Path) -> None:
        """Deve tratar arquivo vazio graciosamente."""
        from autotarefas.core.storage.job_store import JobStore

        filepath = temp_dir / "empty.json"
        filepath.write_text("")

        # Não deve explodir
        store = JobStore(filepath)
        assert len(store.list_all()) == 0

    def test_corrupted_file_handling(self, temp_dir: Path) -> None:
        """Deve tratar arquivo corrompido graciosamente."""
        from autotarefas.core.storage.job_store import JobStore

        filepath = temp_dir / "corrupted.json"
        filepath.write_text("{ invalid json }")

        # Não deve explodir
        store = JobStore(filepath)
        assert len(store.list_all()) == 0

    def test_special_characters_in_name(self, temp_dir: Path) -> None:
        """Deve aceitar caracteres especiais no nome."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "special.json")

        job = store.create(
            name="backup_ação_日本語",
            task="backup",
            schedule="* * * * *",
            description="Descrição com acentuação: ção, ñ",
        )
        store.save(job)

        reloaded = store.get_by_name("backup_ação_日本語")
        assert reloaded is not None
        assert "ção" in reloaded.description

    def test_large_params(self, temp_dir: Path) -> None:
        """Deve tratar params grandes."""
        from autotarefas.core.storage.job_store import JobStore

        store = JobStore(temp_dir / "large_params.json")

        large_params = {f"key_{i}": f"value_{i}" for i in range(500)}

        job = store.create(
            name="large",
            task="backup",
            schedule="* * * * *",
            params=large_params,
        )
        store.save(job)

        reloaded = store.get_by_name("large")
        assert reloaded is not None
        assert len(reloaded.params) == 500
