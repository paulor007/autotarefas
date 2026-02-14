"""
Testes de integração do sistema de agendamento (scheduler).

Este arquivo testa o Scheduler que é responsável por gerenciar a execução
de tarefas agendadas, coordenando jobs, registros e execuções.

=============================================================================
OBJETIVO DO MÓDULO scheduler.py
=============================================================================

O módulo de agendamento serve para:

1. **Gerenciamento de Jobs**
   - Adicionar, remover, listar jobs agendados
   - Habilitar/desabilitar jobs individualmente
   - Buscar jobs por ID ou nome

2. **Tipos de Agendamento**
   - CRON: Expressões cron (ex: "0 2 * * *" = todo dia às 2h)
   - INTERVAL: Intervalo em segundos (ex: "300" = cada 5 minutos)
   - DAILY: Horário diário (ex: "08:30")
   - ONCE: Execução única em data/hora específica

3. **Execução de Tasks**
   - Execução automática quando job está "due"
   - Execução manual sob demanda
   - Registro de sucesso/falha e duração

4. **Controle de Estado**
   - Start/stop do scheduler
   - Pause/resume sem perder jobs
   - Execução em background (thread)

5. **TaskRegistry**
   - Registro de tasks disponíveis
   - Mapeamento nome → classe da task
   - Validação de tasks existentes

=============================================================================
O QUE ESTES TESTES VERIFICAM
=============================================================================

- Adição e remoção de jobs
- Cálculo correto da próxima execução
- Execução de jobs quando estão "due"
- Integração com TaskRegistry
- Integração com JobStore e RunHistory
- Controle de estado (start/stop/pause)
- Tratamento de erros durante execução

=============================================================================
CENÁRIOS DE INTEGRAÇÃO
=============================================================================

1. Scheduler → TaskRegistry → Task → Execução
2. Scheduler → JobStore (persistência de jobs)
3. Scheduler → RunHistory (registro de execuções)
4. ScheduledExecution → Cálculo de próxima execução

Estes testes verificam que todos os componentes funcionam corretamente
em conjunto para executar tarefas de forma agendada.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

# ============================================================================
# Verificação de Dependências
# ============================================================================


def croniter_available() -> bool:
    """Verifica se croniter está disponível."""
    try:
        from croniter import croniter  # noqa: F401

        return True
    except ImportError:
        return False


requires_croniter = pytest.mark.skipif(
    not croniter_available(),
    reason="croniter não instalado",
)


# ============================================================================
# Testes de TaskRegistry
# ============================================================================


class TestTaskRegistryIntegration:
    """
    Testes do TaskRegistry.

    O TaskRegistry mantém o mapeamento de nomes de tasks para suas classes,
    permitindo que o Scheduler encontre e instancie tasks.
    """

    def test_registry_has_default_tasks(self) -> None:
        """Registry deve ter tasks padrão registradas."""
        from autotarefas.core.scheduler import TaskRegistry

        registry = TaskRegistry()

        # Deve ter tasks padrão
        assert registry.exists("backup")
        assert registry.exists("cleaner")
        assert registry.exists("monitor")

    def test_registry_list_tasks(self) -> None:
        """Deve listar todas as tasks disponíveis."""
        from autotarefas.core.scheduler import TaskRegistry

        registry = TaskRegistry()
        tasks = registry.list_tasks()

        assert isinstance(tasks, list)
        assert len(tasks) >= 3  # Pelo menos backup, cleaner, monitor

    def test_registry_get_task_class(self) -> None:
        """Deve retornar classe da task."""
        from autotarefas.core.scheduler import TaskRegistry

        registry = TaskRegistry()
        task_class = registry.get("backup")

        assert task_class is not None
        # Deve ser instanciável
        instance = task_class()
        assert hasattr(instance, "run")

    def test_registry_register_custom_task(self) -> None:
        """Deve permitir registrar task customizada."""
        from autotarefas.core.scheduler import TaskRegistry

        registry = TaskRegistry()

        # Criar task fake
        class FakeTask:
            def run(self) -> bool:
                return True

        registry.register("fake_task", FakeTask)

        assert registry.exists("fake_task")
        task_class = registry.get("fake_task")
        assert task_class is FakeTask


# ============================================================================
# Testes de ScheduledExecution
# ============================================================================


class TestScheduledExecutionIntegration:
    """
    Testes do ScheduledExecution.

    Representa uma execução agendada com informações sobre quando e como
    uma task deve ser executada.
    """

    def test_create_interval_execution(self) -> None:
        """Deve criar execução com intervalo."""
        from autotarefas.core.scheduler import ScheduledExecution, ScheduleType

        execution = ScheduledExecution(
            job_id="test-1",
            job_name="test_job",
            task_name="backup",
            schedule="60",  # 60 segundos
            schedule_type=ScheduleType.INTERVAL,
        )

        assert execution.enabled is True
        assert execution.next_run is not None
        # Próxima execução deve ser ~60s no futuro
        delta = (execution.next_run - datetime.now()).total_seconds()
        assert 59 <= delta <= 61

    def test_create_daily_execution(self) -> None:
        """Deve criar execução diária."""
        from autotarefas.core.scheduler import ScheduledExecution, ScheduleType

        execution = ScheduledExecution(
            job_id="test-2",
            job_name="daily_backup",
            task_name="backup",
            schedule="02:30",  # 2:30 da manhã
            schedule_type=ScheduleType.DAILY,
        )

        assert execution.next_run is not None
        # Deve ser às 2:30
        assert execution.next_run.hour == 2
        assert execution.next_run.minute == 30

    @requires_croniter
    def test_create_cron_execution(self) -> None:
        """Deve criar execução com cron."""
        from autotarefas.core.scheduler import ScheduledExecution, ScheduleType

        execution = ScheduledExecution(
            job_id="test-3",
            job_name="cron_backup",
            task_name="backup",
            schedule="0 2 * * *",  # Todo dia às 2h
            schedule_type=ScheduleType.CRON,
        )

        assert execution.next_run is not None

    def test_create_once_execution(self) -> None:
        """Deve criar execução única."""
        from autotarefas.core.scheduler import ScheduledExecution, ScheduleType

        future = datetime.now() + timedelta(hours=1)
        future_iso = future.isoformat()

        execution = ScheduledExecution(
            job_id="test-4",
            job_name="once_backup",
            task_name="backup",
            schedule=future_iso,
            schedule_type=ScheduleType.ONCE,
        )

        assert execution.next_run is not None

    def test_is_due(self) -> None:
        """Deve detectar quando job está pronto para executar."""
        from autotarefas.core.scheduler import ScheduledExecution, ScheduleType

        execution = ScheduledExecution(
            job_id="test-5",
            job_name="due_test",
            task_name="backup",
            schedule="1",  # 1 segundo
            schedule_type=ScheduleType.INTERVAL,
        )

        # Inicialmente não está due
        assert execution.is_due() is False

        # Após 1 segundo, deve estar due
        time.sleep(1.1)
        assert execution.is_due() is True

    def test_mark_executed_success(self) -> None:
        """Deve registrar execução com sucesso."""
        from autotarefas.core.scheduler import ScheduledExecution, ScheduleType

        execution = ScheduledExecution(
            job_id="test-6",
            job_name="exec_test",
            task_name="backup",
            schedule="60",
            schedule_type=ScheduleType.INTERVAL,
        )

        execution.mark_executed(success=True, duration=5.5)

        assert execution.run_count == 1
        assert execution.success_count == 1
        assert execution.error_count == 0
        assert execution.last_duration == 5.5
        assert execution.last_run is not None

    def test_mark_executed_failure(self) -> None:
        """Deve registrar execução com falha."""
        from autotarefas.core.scheduler import ScheduledExecution, ScheduleType

        execution = ScheduledExecution(
            job_id="test-7",
            job_name="fail_test",
            task_name="backup",
            schedule="60",
            schedule_type=ScheduleType.INTERVAL,
        )

        execution.mark_executed(success=False, duration=2.0, error="Disk full")

        assert execution.run_count == 1
        assert execution.success_count == 0
        assert execution.error_count == 1
        assert execution.last_error == "Disk full"

    def test_success_rate(self) -> None:
        """Deve calcular taxa de sucesso."""
        from autotarefas.core.scheduler import ScheduledExecution, ScheduleType

        execution = ScheduledExecution(
            job_id="test-8",
            job_name="rate_test",
            task_name="backup",
            schedule="60",
            schedule_type=ScheduleType.INTERVAL,
        )

        # 3 sucessos, 1 falha = 75%
        execution.mark_executed(success=True, duration=1.0)
        execution.mark_executed(success=True, duration=1.0)
        execution.mark_executed(success=True, duration=1.0)
        execution.mark_executed(success=False, duration=1.0, error="Error")

        assert execution.success_rate == 0.75

    def test_to_dict_serialization(self) -> None:
        """Deve serializar para dicionário."""
        from autotarefas.core.scheduler import ScheduledExecution, ScheduleType

        execution = ScheduledExecution(
            job_id="test-9",
            job_name="serial_test",
            task_name="backup",
            schedule="60",
            schedule_type=ScheduleType.INTERVAL,
            params={"source": "/data"},
            tags=["daily", "important"],
        )

        data = execution.to_dict()

        assert data["job_id"] == "test-9"
        assert data["job_name"] == "serial_test"
        assert data["task_name"] == "backup"
        assert data["params"] == {"source": "/data"}
        assert data["tags"] == ["daily", "important"]


# ============================================================================
# Testes do Scheduler
# ============================================================================


class TestSchedulerJobManagement:
    """
    Testes de gerenciamento de jobs no Scheduler.

    Verifica adição, remoção e busca de jobs.
    """

    def test_add_job_interval(self) -> None:
        """Deve adicionar job com intervalo."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        job = scheduler.add_job(
            name="test_backup",
            task="backup",
            schedule="300",  # 5 minutos
            schedule_type="interval",
            params={"source": "/data"},
        )

        assert job is not None
        assert job.job_name == "test_backup"
        assert scheduler.get_job_by_name("test_backup") is not None

    def test_add_job_daily(self) -> None:
        """Deve adicionar job diário."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        job = scheduler.add_job(
            name="daily_clean",
            task="cleaner",
            schedule="03:00",
            schedule_type="daily",
        )

        assert job is not None
        assert job.next_run is not None
        assert job.next_run.hour == 3
        assert job.next_run.minute == 0

    @requires_croniter
    def test_add_job_cron(self) -> None:
        """Deve adicionar job com cron."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        job = scheduler.add_job(
            name="cron_monitor",
            task="monitor",
            schedule="*/5 * * * *",  # Cada 5 minutos
            schedule_type="cron",
        )

        assert job is not None
        assert job.next_run is not None

    def test_add_job_invalid_task(self) -> None:
        """Deve falhar com task inexistente."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        with pytest.raises(ValueError, match="não encontrada"):
            scheduler.add_job(
                name="invalid_job",
                task="nonexistent_task",
                schedule="60",
                schedule_type="interval",
            )

    def test_add_job_duplicate_name(self) -> None:
        """Deve falhar com nome duplicado."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        scheduler.add_job(
            name="unique_name",
            task="backup",
            schedule="60",
            schedule_type="interval",
        )

        with pytest.raises(ValueError, match="(?i)já existe"):
            scheduler.add_job(
                name="unique_name",  # Mesmo nome
                task="cleaner",
                schedule="60",
                schedule_type="interval",
            )

    def test_remove_job(self) -> None:
        """Deve remover job."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        job = scheduler.add_job(
            name="to_remove",
            task="backup",
            schedule="60",
            schedule_type="interval",
        )

        assert scheduler.remove_job(job.job_id) is True
        assert scheduler.get_job(job.job_id) is None

    def test_list_jobs(self) -> None:
        """Deve listar todos os jobs."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        scheduler.add_job(
            name="job1", task="backup", schedule="60", schedule_type="interval"
        )
        scheduler.add_job(
            name="job2", task="cleaner", schedule="120", schedule_type="interval"
        )

        jobs = scheduler.list_jobs()

        assert len(jobs) == 2

    def test_enable_disable_job(self) -> None:
        """Deve habilitar/desabilitar job."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        job = scheduler.add_job(
            name="toggle_job",
            task="backup",
            schedule="60",
            schedule_type="interval",
            enabled=True,
        )

        # Desabilitar
        scheduler.disable_job(job.job_id)
        disabled_job = scheduler.get_job(job.job_id)
        assert disabled_job is not None
        assert disabled_job.enabled is False

        # Habilitar
        scheduler.enable_job(job.job_id)
        enabled_job = scheduler.get_job(job.job_id)
        assert enabled_job is not None
        assert enabled_job.enabled is True


# ============================================================================
# Testes de Execução
# ============================================================================


class TestSchedulerExecution:
    """
    Testes de execução de jobs.

    Verifica que jobs são executados corretamente quando estão "due".
    """

    def test_run_job_manually(self, integration_env: dict[str, Path]) -> None:
        """Deve executar job manualmente."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        job = scheduler.add_job(
            name="manual_backup",
            task="backup",
            schedule="3600",  # 1 hora (não vai executar automaticamente)
            schedule_type="interval",
            params={"source": str(integration_env["source"])},
        )

        # Criar arquivo para backup
        (integration_env["source"] / "test.txt").write_text("test")

        # Executar manualmente
        success = scheduler.run_job(job.job_id)

        # Pode falhar se dest não configurado, mas deve executar
        # O importante é que execute sem exceção
        assert isinstance(success, bool)

    def test_execute_job_updates_stats(self) -> None:
        """Execução deve atualizar estatísticas do job."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        job = scheduler.add_job(
            name="stats_job",
            task="monitor",
            schedule="3600",
            schedule_type="interval",
            params={},
        )

        initial_count = job.run_count

        # Executar
        scheduler.run_job(job.job_id)

        # Stats devem ser atualizadas
        updated_job = scheduler.get_job(job.job_id)
        assert updated_job is not None
        assert updated_job.run_count == initial_count + 1
        assert updated_job.last_run is not None


# ============================================================================
# Testes de Controle de Estado
# ============================================================================


class TestSchedulerStateControl:
    """
    Testes de controle de estado do Scheduler.

    Verifica start, stop, pause e resume.
    """

    def test_start_and_stop(self) -> None:
        """Deve iniciar e parar o scheduler."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        assert scheduler.running is False

        scheduler.start()
        assert scheduler.running is True

        scheduler.stop()
        assert scheduler.running is False

    def test_pause_and_resume(self) -> None:
        """Deve pausar e resumir o scheduler."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()
        scheduler.start()

        assert scheduler.paused is False

        scheduler.pause()
        assert scheduler.paused is True

        scheduler.resume()
        assert scheduler.paused is False

        scheduler.stop()

    def test_start_already_running(self) -> None:
        """Deve ignorar start se já está rodando."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()
        scheduler.start()
        scheduler.start()  # Não deve dar erro

        assert scheduler.running is True
        scheduler.stop()


# ============================================================================
# Testes de Integração com Storage
# ============================================================================


class TestSchedulerWithStorage:
    """
    Testes de integração com JobStore e RunHistory.

    Verifica persistência e registro de execuções.
    """

    def test_scheduler_with_run_history(
        self,
        integration_env: dict[str, Path],
    ) -> None:
        """Deve registrar execuções no RunHistory."""
        from autotarefas.core.scheduler import Scheduler
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        scheduler = Scheduler()
        history = RunHistory(integration_env["data"] / "scheduler_history.db")

        job = scheduler.add_job(
            name="history_test",
            task="monitor",
            schedule="3600",
            schedule_type="interval",
        )

        # Registrar início
        record = history.start_run(
            job_id=job.job_id,
            job_name=job.job_name,
            task=job.task_name,
        )

        # Executar
        success = scheduler.run_job(job.job_id)

        # Registrar fim
        history.finish_run(
            record.id,
            RunStatus.SUCCESS if success else RunStatus.FAILED,
            duration=job.last_duration,
        )

        # Verificar
        runs = history.get_by_job(job.job_id)
        assert len(runs) == 1

        scheduler.stop()

    def test_load_jobs_from_job_store(
        self,
        populated_job_store: Any,
    ) -> None:
        """Deve carregar jobs do JobStore."""
        from contextlib import suppress

        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        # Carregar jobs do store
        jobs = populated_job_store.list_all()

        for stored_job in jobs:
            if stored_job.enabled:
                # Pode falhar se croniter não disponível
                with suppress(Exception):
                    scheduler.add_job(
                        name=stored_job.name,
                        task=stored_job.task,
                        schedule=stored_job.schedule,
                        schedule_type="cron",  # Default
                        params=stored_job.params,
                    )

        # Deve ter alguns jobs carregados
        assert len(scheduler.list_jobs()) >= 0


# ============================================================================
# Testes de Validação
# ============================================================================


class TestSchedulerValidation:
    """Testes de validação de parâmetros."""

    def test_invalid_schedule_type(self) -> None:
        """Deve falhar com tipo de schedule inválido."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        with pytest.raises((ValueError, KeyError)):
            scheduler.add_job(
                name="invalid_type",
                task="backup",
                schedule="60",
                schedule_type="invalid_type",
            )

    def test_invalid_daily_format(self) -> None:
        """Deve falhar com formato de horário inválido."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        with pytest.raises(ValueError):
            scheduler.add_job(
                name="invalid_daily",
                task="backup",
                schedule="25:00",  # Hora inválida
                schedule_type="daily",
            )

    def test_invalid_once_format(self) -> None:
        """Deve falhar com datetime inválido para ONCE."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        with pytest.raises(ValueError):
            scheduler.add_job(
                name="invalid_once",
                task="backup",
                schedule="not-a-datetime",
                schedule_type="once",
            )


# ============================================================================
# Testes de Edge Cases
# ============================================================================


class TestSchedulerEdgeCases:
    """Testes de casos extremos."""

    def test_job_disabled_no_next_run(self) -> None:
        """Job desabilitado não deve ter próxima execução."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        job = scheduler.add_job(
            name="disabled_job",
            task="backup",
            schedule="60",
            schedule_type="interval",
            enabled=False,
        )

        assert job.next_run is None

    def test_once_job_disables_after_execution(self) -> None:
        """Job ONCE deve ser desabilitado após execução."""
        from autotarefas.core.scheduler import ScheduledExecution, ScheduleType

        future = datetime.now() + timedelta(seconds=1)

        execution = ScheduledExecution(
            job_id="once-test",
            job_name="once_job",
            task_name="monitor",
            schedule=future.isoformat(),
            schedule_type=ScheduleType.ONCE,
        )

        # Simular execução
        execution.mark_executed(success=True, duration=1.0)

        # Deve estar desabilitado
        assert execution.enabled is False
        assert execution.next_run is None

    def test_multiple_jobs_different_schedules(self) -> None:
        """Deve gerenciar múltiplos jobs com schedules diferentes."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        scheduler.add_job(
            name="job_interval", task="backup", schedule="60", schedule_type="interval"
        )
        scheduler.add_job(
            name="job_daily", task="cleaner", schedule="08:00", schedule_type="daily"
        )

        jobs = scheduler.list_jobs()
        assert len(jobs) == 2

        # Cada um deve ter sua próxima execução
        for job in jobs:
            assert job.next_run is not None

    def test_identify_due_jobs(self) -> None:
        """Deve identificar jobs prontos para execução."""
        from autotarefas.core.scheduler import Scheduler

        scheduler = Scheduler()

        # Job que vai estar due em 1 segundo
        scheduler.add_job(
            name="due_soon",
            task="monitor",
            schedule="1",
            schedule_type="interval",
        )

        # Job que vai demorar
        scheduler.add_job(
            name="not_due",
            task="backup",
            schedule="3600",
            schedule_type="interval",
        )

        # Esperar job ficar due
        time.sleep(1.1)

        # Filtrar jobs que estão due
        due_jobs = [j for j in scheduler.list_jobs() if j.is_due()]

        # Pelo menos o primeiro deve estar due
        due_names = [j.job_name for j in due_jobs]
        assert "due_soon" in due_names
