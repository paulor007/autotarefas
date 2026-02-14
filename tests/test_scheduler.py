"""Tests for autotarefas.core.scheduler.

Cobre:
- ScheduleType: enum e valores
- TaskRegistry: registro, lookup e utilitários
- ScheduledExecution: validação, cálculo de next_run, is_due, mark_executed, (de)serialização
- Scheduler: CRUD de jobs, execução manual, stats/status, enable/disable, start/stop/pause/resume
- Singleton: get_scheduler() / reset_scheduler()

Observações:
- Para tornar os testes determinísticos, congelamos o relógio do módulo via monkeypatch
  (substituindo o símbolo `datetime` dentro de autotarefas.core.scheduler).
- Cron (ScheduleType.CRON) depende de croniter; os testes se adaptam via CRONITER_AVAILABLE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pytest

# =============================================================================
# Helpers de tempo (determinismo)
# =============================================================================


class _FixedDateTime(datetime):
    """Datetime congelado para testes (monkeypatch no módulo scheduler)."""

    _now: datetime = datetime(2026, 2, 1, 10, 0, 0)

    @classmethod
    def now(cls, tz=None):  # noqa: D401 (assinatura compatível)
        if tz is not None:
            return cls._now.replace(tzinfo=tz)
        return cls._now

    @classmethod
    def advance(
        cls, *, seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0
    ) -> None:
        cls._now = cls._now + timedelta(
            seconds=seconds, minutes=minutes, hours=hours, days=days
        )


@pytest.fixture()
def frozen_scheduler_time(monkeypatch):
    """Congela datetime.now() dentro de autotarefas.core.scheduler."""
    import autotarefas.core.scheduler as scheduler_mod

    _FixedDateTime._now = datetime(2026, 2, 1, 10, 0, 0)
    monkeypatch.setattr(scheduler_mod, "datetime", _FixedDateTime)

    return scheduler_mod


# =============================================================================
# ScheduleType
# =============================================================================


class TestScheduleType:
    """Testes do enum ScheduleType."""

    def test_values_exist(self):
        from autotarefas.core.scheduler import ScheduleType

        assert ScheduleType.CRON.value == "cron"
        assert ScheduleType.INTERVAL.value == "interval"
        assert ScheduleType.DAILY.value == "daily"
        assert ScheduleType.ONCE.value == "once"


# =============================================================================
# TaskRegistry
# =============================================================================


class TestTaskRegistry:
    """Testes do TaskRegistry."""

    def test_register_and_get(self):
        from autotarefas.core.scheduler import TaskRegistry

        class Dummy:
            def run(self):  # pragma: no cover - nunca chamado aqui
                return None

        registry = TaskRegistry()
        registry.register("dummy", Dummy)

        assert registry.exists("dummy")
        assert registry.get("DUMMY") is Dummy  # case-insensitive
        assert "dummy" in registry
        assert len(registry) >= 1

    def test_unregister(self):
        from autotarefas.core.scheduler import TaskRegistry

        class Dummy:
            def run(self):
                return None

        registry = TaskRegistry()
        registry.register("dummy", Dummy)

        assert registry.unregister("dummy") is True
        assert registry.unregister("dummy") is False
        assert registry.exists("dummy") is False

    def test_list_tasks_sorted(self):
        from autotarefas.core.scheduler import TaskRegistry

        class A:
            def run(self):
                return None

        class B:
            def run(self):
                return None

        registry = TaskRegistry()
        registry.register("b", B)
        registry.register("a", A)

        names = registry.list_tasks()
        assert names == sorted(names)


# =============================================================================
# ScheduledExecution
# =============================================================================


class TestScheduledExecution:
    """Testes da dataclass ScheduledExecution."""

    def test_interval_calculates_next_run(self, frozen_scheduler_time):
        scheduler_mod = frozen_scheduler_time
        job = scheduler_mod.ScheduledExecution(
            job_id="abcd1234",
            job_name="interval_job",
            task_name="backup",
            schedule="60",
            schedule_type=scheduler_mod.ScheduleType.INTERVAL,
        )

        assert job.next_run is not None
        assert job.next_run == _FixedDateTime.now() + timedelta(seconds=60)

    @pytest.mark.parametrize(
        ("now", "schedule", "expected"),
        [
            (datetime(2026, 2, 1, 10, 0, 0), "10:30", datetime(2026, 2, 1, 10, 30, 0)),
            (datetime(2026, 2, 1, 10, 0, 0), "09:00", datetime(2026, 2, 2, 9, 0, 0)),
        ],
    )
    def test_daily_calculates_next_run(
        self, monkeypatch, now: datetime, schedule: str, expected: datetime
    ):
        import autotarefas.core.scheduler as scheduler_mod

        _FixedDateTime._now = now
        monkeypatch.setattr(scheduler_mod, "datetime", _FixedDateTime)

        job = scheduler_mod.ScheduledExecution(
            job_id="abcd1234",
            job_name="daily_job",
            task_name="backup",
            schedule=schedule,
            schedule_type=scheduler_mod.ScheduleType.DAILY,
        )

        assert job.next_run == expected

    def test_once_parses_iso(self, frozen_scheduler_time):
        scheduler_mod = frozen_scheduler_time

        run_at = (_FixedDateTime.now() + timedelta(minutes=5)).isoformat()
        job = scheduler_mod.ScheduledExecution(
            job_id="abcd1234",
            job_name="once_job",
            task_name="backup",
            schedule=run_at,
            schedule_type="once",
        )

        assert job.next_run is not None
        assert job.next_run.isoformat() == run_at

    def test_is_due(self, frozen_scheduler_time):
        scheduler_mod = frozen_scheduler_time

        job = scheduler_mod.ScheduledExecution(
            job_id="abcd1234",
            job_name="due_job",
            task_name="backup",
            schedule="60",
            schedule_type="interval",
        )
        # força para o passado
        job.next_run = _FixedDateTime.now() - timedelta(seconds=1)

        assert job.is_due() is True

    def test_mark_executed_updates_counters_and_next_run(self, frozen_scheduler_time):
        scheduler_mod = frozen_scheduler_time

        job = scheduler_mod.ScheduledExecution(
            job_id="abcd1234",
            job_name="interval_job",
            task_name="backup",
            schedule="60",
            schedule_type="interval",
        )

        _FixedDateTime.advance(seconds=1)
        job.mark_executed(success=True, duration=0.12)

        assert job.run_count == 1
        assert job.success_count == 1
        assert job.error_count == 0
        assert job.last_error is None
        assert job.last_duration == pytest.approx(0.12, rel=1e-6)
        assert job.next_run is not None  # interval recalcula

    def test_mark_executed_once_disables_job(self, frozen_scheduler_time):
        scheduler_mod = frozen_scheduler_time

        run_at = (_FixedDateTime.now() + timedelta(minutes=1)).isoformat()
        job = scheduler_mod.ScheduledExecution(
            job_id="abcd1234",
            job_name="once_job",
            task_name="backup",
            schedule=run_at,
            schedule_type="once",
        )

        job.mark_executed(success=True, duration=0.01)
        assert job.enabled is False
        assert job.next_run is None

    def test_success_rate(self, frozen_scheduler_time):
        scheduler_mod = frozen_scheduler_time

        job = scheduler_mod.ScheduledExecution(
            job_id="abcd1234",
            job_name="stats_job",
            task_name="backup",
            schedule="60",
            schedule_type="interval",
        )

        job.mark_executed(success=True, duration=0.01)
        job.mark_executed(success=False, duration=0.01, error="boom")

        assert job.run_count == 2
        assert job.success_rate == pytest.approx(0.5)

    def test_to_dict_and_from_dict_roundtrip(self, frozen_scheduler_time):
        scheduler_mod = frozen_scheduler_time

        job = scheduler_mod.ScheduledExecution(
            job_id="abcd1234",
            job_name="roundtrip",
            task_name="backup",
            schedule="60",
            schedule_type="interval",
            params={"x": 1},
            tags=["a", "b"],
            description="desc",
        )

        data = job.to_dict()
        rebuilt = scheduler_mod.ScheduledExecution.from_dict(data)

        assert rebuilt.job_id == job.job_id
        assert rebuilt.job_name == job.job_name
        assert rebuilt.task_name == job.task_name
        assert rebuilt.schedule_type.value == "interval"
        assert rebuilt.params == {"x": 1}
        assert rebuilt.tags == ["a", "b"]
        assert rebuilt.description == "desc"


# =============================================================================
# Scheduler
# =============================================================================


@dataclass
class _DummyResult:
    success: bool
    error: str | None = None


class _DummyTask:
    """Task fake para testar execução."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def run(self):
        return _DummyResult(success=True)


class _FailTask:
    def run(self):
        return _DummyResult(success=False, error="nope")


class _BoomTask:
    def run(self):
        raise RuntimeError("boom")


class _TaskResultOkTask:
    def run(self):
        from autotarefas.core.base import TaskResult

        return TaskResult.success("ok")


class _TaskResultFailTask:
    def run(self):
        from autotarefas.core.base import TaskResult

        return TaskResult.failure("nope", error=RuntimeError("nope"))


@pytest.fixture()
def scheduler_with_dummy_task(frozen_scheduler_time):
    """Scheduler isolado com task dummy registrada."""
    scheduler_mod = frozen_scheduler_time

    registry = scheduler_mod.TaskRegistry()
    registry.register("dummy", _DummyTask)
    registry.register("fail", _FailTask)
    registry.register("boom", _BoomTask)
    registry.register("taskresult_ok", _TaskResultOkTask)
    registry.register("taskresult_fail", _TaskResultFailTask)

    sched = scheduler_mod.Scheduler(registry=registry)

    yield sched

    # limpeza defensiva (evita threads vazando)
    sched.stop(wait=True)


class TestSchedulerJobs:
    """Testes de CRUD de jobs."""

    def test_add_job_requires_existing_task(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task

        with pytest.raises(ValueError) as err:
            sched.add_job(
                name="x", task="does_not_exist", schedule="60", schedule_type="interval"
            )

        assert "não encontrada" in str(err.value).lower()

    def test_add_job_generates_hex_id_and_stores_job(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task

        job = sched.add_job(
            name="job1", task="dummy", schedule="60", schedule_type="interval"
        )

        assert job.job_id in sched.jobs
        assert re.fullmatch(r"[0-9a-f]{8}", job.job_id) is not None
        assert job.job_name == "job1"
        assert job.task_name == "dummy"
        assert job.next_run is not None

    def test_add_job_duplicate_name_raises(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task
        sched.add_job(name="dup", task="dummy", schedule="60", schedule_type="interval")

        with pytest.raises(ValueError) as err:
            sched.add_job(
                name="dup", task="dummy", schedule="60", schedule_type="interval"
            )

        assert "já existe" in str(err.value).lower()

    def test_get_job_by_name(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task
        job = sched.add_job(
            name="byname", task="dummy", schedule="60", schedule_type="interval"
        )

        fetched = sched.get_job_by_name("byname")
        assert fetched is not None
        assert fetched.job_id == job.job_id

    def test_remove_job(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task
        job = sched.add_job(
            name="toremove", task="dummy", schedule="60", schedule_type="interval"
        )

        assert sched.remove_job(job.job_id) is True
        assert sched.remove_job(job.job_id) is False
        assert sched.get_job(job.job_id) is None

    def test_disable_and_enable_job(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task
        job = sched.add_job(
            name="toggle", task="dummy", schedule="60", schedule_type="interval"
        )

        assert sched.disable_job(job.job_id) is True
        assert sched.get_job(job.job_id).enabled is False  # type: ignore[union-attr]
        assert sched.get_job(job.job_id).next_run is None  # type: ignore[union-attr]

        assert sched.enable_job(job.job_id) is True
        enabled_job = sched.get_job(job.job_id)
        assert enabled_job is not None
        assert enabled_job.enabled is True
        assert enabled_job.next_run is not None

    def test_list_jobs_enabled_only(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task
        a = sched.add_job(
            name="a",
            task="dummy",
            schedule="60",
            schedule_type="interval",
            enabled=True,
        )
        b = sched.add_job(
            name="b",
            task="dummy",
            schedule="60",
            schedule_type="interval",
            enabled=False,
        )

        enabled_jobs = sched.list_jobs(enabled_only=True)
        assert a.job_id in [j.job_id for j in enabled_jobs]
        assert b.job_id not in [j.job_id for j in enabled_jobs]


class TestSchedulerExecution:
    """Testes de execução manual e contadores."""

    def test_run_job_success_updates_stats(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task
        job = sched.add_job(
            name="exec_ok", task="dummy", schedule="60", schedule_type="interval"
        )

        ok = sched.run_job(job.job_id)
        assert ok is True

        updated = sched.get_job(job.job_id)
        assert updated is not None
        assert updated.run_count == 1
        assert updated.success_count == 1
        assert updated.error_count == 0

    def test_run_job_failure_updates_error(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task
        job = sched.add_job(
            name="exec_fail", task="fail", schedule="60", schedule_type="interval"
        )

        ok = sched.run_job(job.job_id)
        assert ok is False

        updated = sched.get_job(job.job_id)
        assert updated is not None
        assert updated.run_count == 1
        assert updated.success_count == 0
        assert updated.error_count == 1
        assert updated.last_error == "nope"

    def test_run_job_supports_taskresult_success(self, scheduler_with_dummy_task):
        """Deve interpretar TaskResult.success como sucesso."""
        sched = scheduler_with_dummy_task
        job = sched.add_job(
            name="exec_tr_ok",
            task="taskresult_ok",
            schedule="60",
            schedule_type="interval",
        )

        ok = sched.run_job(job.job_id)
        assert ok is True

        updated = sched.get_job(job.job_id)
        assert updated is not None
        assert updated.run_count == 1
        assert updated.success_count == 1
        assert updated.error_count == 0

    def test_run_job_supports_taskresult_failure(self, scheduler_with_dummy_task):
        """Deve interpretar TaskResult.failure como falha e registrar erro."""
        sched = scheduler_with_dummy_task
        job = sched.add_job(
            name="exec_tr_fail",
            task="taskresult_fail",
            schedule="60",
            schedule_type="interval",
        )

        ok = sched.run_job(job.job_id)
        assert ok is False

        updated = sched.get_job(job.job_id)
        assert updated is not None
        assert updated.run_count == 1
        assert updated.success_count == 0
        assert updated.error_count == 1
        assert "nope" in (updated.last_error or "")

    def test_run_job_exception_is_captured(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task
        job = sched.add_job(
            name="exec_boom", task="boom", schedule="60", schedule_type="interval"
        )

        ok = sched.run_job(job.job_id)
        assert ok is False

        updated = sched.get_job(job.job_id)
        assert updated is not None
        assert updated.run_count == 1
        assert updated.error_count == 1
        assert "boom" in (updated.last_error or "")

    def test_check_and_run_jobs_executes_due_jobs(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task

        job = sched.add_job(
            name="due", task="dummy", schedule="60", schedule_type="interval"
        )
        # Força next_run para o passado => due
        job.next_run = _FixedDateTime.now() - timedelta(seconds=1)

        called: list[str] = []

        def _fake_execute(j):
            called.append(j.job_id)
            j.mark_executed(True, 0.0)
            return True

        # patch método privado para não depender de tasks
        sched._execute_job = _fake_execute  # type: ignore[method-assign]

        sched._check_and_run_jobs()

        assert job.job_id in called


class TestSchedulerStatusAndLifecycle:
    """Testes de status e ciclo start/stop."""

    def test_get_status_and_stats(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task

        job = sched.add_job(
            name="one", task="dummy", schedule="60", schedule_type="interval"
        )
        sched.run_job(job.job_id)

        status = sched.get_status()
        assert set(status.keys()) >= {
            "running",
            "paused",
            "total_jobs",
            "enabled_jobs",
            "next_execution",
            "next_job",
        }

        stats = sched.get_stats()
        assert stats["total_jobs"] >= 1
        assert stats["total_runs"] >= 1
        assert stats["total_success"] >= 1
        assert stats["total_errors"] >= 0
        assert 0.0 <= stats["success_rate"] <= 1.0

    def test_start_pause_resume_stop(self, scheduler_with_dummy_task):
        sched = scheduler_with_dummy_task
        # acelera o loop
        sched._check_interval = 0.01

        sched.start()
        assert sched.running is True

        sched.pause()
        assert sched.paused is True

        sched.resume()
        assert sched.paused is False

        sched.stop(wait=True, timeout=1.0)
        assert sched.running is False


# =============================================================================
# Cron (croniter opcional)
# =============================================================================


class TestCronSupport:
    """Testes de CRON, condicionais ao croniter."""

    def test_cron_requires_croniter(self, frozen_scheduler_time):
        scheduler_mod = frozen_scheduler_time

        if scheduler_mod.CRONITER_AVAILABLE:
            pytest.skip("croniter disponível - este teste cobre o caminho sem croniter")

        with pytest.raises(RuntimeError):
            scheduler_mod.ScheduledExecution(
                job_id="abcd1234",
                job_name="cron_job",
                task_name="backup",
                schedule="0 2 * * *",
                schedule_type="cron",
            )

    def test_cron_next_run_when_available(self, frozen_scheduler_time):
        scheduler_mod = frozen_scheduler_time

        if not scheduler_mod.CRONITER_AVAILABLE:
            pytest.skip("croniter não instalado")

        job = scheduler_mod.ScheduledExecution(
            job_id="abcd1234",
            job_name="cron_job",
            task_name="backup",
            schedule="0 11 * * *",  # próximo 11:00
            schedule_type="cron",
        )

        assert job.next_run is not None
        # Como o now é 10:00, o próximo deve ser 11:00 no mesmo dia
        assert job.next_run.hour == 11
        assert job.next_run.minute == 0


# =============================================================================
# Singleton
# =============================================================================


class TestSchedulerSingleton:
    """Testes do singleton get_scheduler/reset_scheduler."""

    def test_get_scheduler_and_reset(self):
        from autotarefas.core.scheduler import get_scheduler, reset_scheduler

        s1 = get_scheduler()
        reset_scheduler()
        s2 = get_scheduler()

        assert s1 is not s2
        reset_scheduler()  # limpeza final
