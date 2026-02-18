"""
Sistema de Agendamento do AutoTarefas.

Fornece agendamento de tarefas com expressões cron:
    - TaskRegistry: Registro de tasks disponíveis
    - ScheduledExecution: Representa uma execução agendada
    - Scheduler: Gerenciador central de agendamento
    - get_scheduler(): Obtém instância singleton

Suporta 4 tipos:
- CRON: expressão cron (requer croniter)
- INTERVAL: intervalo em segundos
- DAILY: horário diário HH:MM
- ONCE: execução única em um datetime ISO (ex: 2026-01-18T02:00:00)

Uso:
    from autotarefas.core.scheduler import get_scheduler

    scheduler = get_scheduler()
    scheduler.add_job(
        name="backup_diario",
        task="backup",
        schedule="0 2 * * *",
        schedule_type="cron",
        params={"source": "/home/user/docs"},
    )
    scheduler.start()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from autotarefas.core.logger import logger

# Croniter é opcional - permite expressões cron
try:
    from croniter import croniter  # type: ignore

    CRONITER_AVAILABLE = True
except ImportError:
    croniter = None  # type: ignore
    CRONITER_AVAILABLE = False


class ScheduleType(Enum):
    """
    Tipo de agendamento.

    Valores:
        CRON: Expressão cron (ex: "0 2 * * *")
        INTERVAL: Intervalo em segundos
        DAILY: Diário em horário específico
        ONCE: Execução única
    """

    CRON = "cron"
    INTERVAL = "interval"
    DAILY = "daily"
    ONCE = "once"


class TaskRegistry:
    """
    Registro de tasks disponíveis para agendamento.

    Mapeia nomes de tasks para suas classes/funções executáveis.
    Permite registrar tasks customizadas além das padrão.

    Exemplo:
        >>> registry = TaskRegistry()
        >>> registry.register("minha_task", MinhaTaskClass)
        >>> task_class = registry.get("minha_task")
        >>> task = task_class()
        >>> task.run()

    Attributes:
        _tasks: Dicionário de nome -> classe da task
    """

    def __init__(self):
        """Inicializa o registro com tasks padrão."""
        self._tasks: dict[str, type] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Registra tasks padrão do sistema."""
        try:
            from autotarefas.tasks import (
                BackupTask,
                CleanerTask,
                MonitorTask,
                OrganizerTask,
                SalesReportTask,
            )

            self._tasks = {
                "backup": BackupTask,
                "cleaner": CleanerTask,
                "clean": CleanerTask,  # Alias
                "organizer": OrganizerTask,
                "organize": OrganizerTask,  # Alias
                "monitor": MonitorTask,
                "sales_report": SalesReportTask,
                "sales": SalesReportTask,  # Alias
            }
            logger.debug("Tasks padrão registradas: %s", list(self._tasks.keys()))

        except ImportError as e:
            logger.warning("Erro ao registrar tasks padrão: %s", e)

    def register(self, name: str, task_class: type) -> None:
        """
        Registra uma task customizada.

        Args:
            name: Nome único da task (case-insensitive)
            task_class: Classe que implementa a task (deve ter método run())

        Raises:
            ValueError: Se a task já existe
        """
        name_lower = name.lower()
        if name_lower in self._tasks:
            logger.warning("Task '%s' já registrada, sobrescrevendo...", name)

        self._tasks[name_lower] = task_class
        logger.info("Task registrada: %s", name_lower)

    def unregister(self, name: str) -> bool:
        """
        Remove uma task do registro.

        Args:
            name: Nome da task

        Returns:
            True se removida, False se não existia
        """
        name_lower = name.lower()
        if name_lower in self._tasks:
            del self._tasks[name_lower]
            logger.info("Task removida: %s", name_lower)
            return True
        return False

    def get(self, name: str) -> type | None:
        """
        Obtém classe de uma task pelo nome.

        Args:
            name: Nome da task (case-insensitive)

        Returns:
            Classe da task ou None se não encontrada
        """
        return self._tasks.get(name.lower())

    def exists(self, name: str) -> bool:
        """Verifica se uma task está registrada."""
        return name.lower() in self._tasks

    def list_tasks(self) -> list[str]:
        """Lista nomes de todas as tasks registradas."""
        return sorted(self._tasks.keys())

    def get_all(self) -> dict[str, type]:
        """Retorna cópia do dicionário de tasks."""
        return self._tasks.copy()

    def __contains__(self, name: str) -> bool:
        """Permite usar 'in' para verificar se task existe."""
        return self.exists(name)

    def __len__(self) -> int:
        """Retorna número de tasks registradas."""
        return len(self._tasks)


def _parse_schedule_type(value: str | ScheduleType) -> ScheduleType:
    # Conversão: mensagem de erro clara.
    if isinstance(value, ScheduleType):
        return value
    try:
        return ScheduleType(value.strip().lower())
    except Exception as e:
        raise ValueError(
            f"schedule_type inválido: {value!r}. Use: cron, interval, daily, once."
        ) from e


def _validate_schedule(schedule_type: ScheduleType, schedule: str) -> None:
    # Validação antecipada.
    if not schedule or not schedule.strip():
        raise ValueError("schedule não pode ser vazio.")

    if schedule_type == ScheduleType.INTERVAL:
        try:
            seconds = int(schedule)
        except ValueError as e:
            raise ValueError(
                "INTERVAL exige um número inteiro em segundos (ex: '60')."
            ) from e
        if seconds <= 0:
            raise ValueError("INTERVAL deve ser > 0 (em segundos).")

    elif schedule_type == ScheduleType.DAILY:
        try:
            hour_str, minute_str = schedule.split(":")
            hour, minute = int(hour_str), int(minute_str)
        except Exception as e:
            raise ValueError("DAILY exige formato HH:MM (ex: '02:30').") from e
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("DAILY exige horário válido (00:00 até 23:59).")

    elif schedule_type == ScheduleType.CRON:
        if not CRONITER_AVAILABLE:
            # Não explode no import; explode quando realmente precisa.
            raise RuntimeError(
                "CRON requer 'croniter'. Instale com: pip install croniter"
            )

    elif schedule_type == ScheduleType.ONCE:
        # ONCE: aceitamos ISO datetime na schedule.
        try:
            datetime.fromisoformat(schedule)
        except Exception as e:
            raise ValueError(
                "ONCE exige um datetime ISO em schedule (ex: '2026-01-18T02:00:00')."
            ) from e


def _compute_next_run(
    schedule_type: ScheduleType,
    schedule: str,
    *,
    now: datetime,
) -> datetime | None:
    # Função pura para cálculo: facilita testes e reduz bugs.
    if schedule_type == ScheduleType.CRON:
        cron = croniter(schedule, now)  # type: ignore[misc]
        return cron.get_next(datetime)

    if schedule_type == ScheduleType.INTERVAL:
        seconds = int(schedule)
        return now + timedelta(seconds=seconds)

    if schedule_type == ScheduleType.DAILY:
        hour, minute = map(int, schedule.split(":"))
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if schedule_type == ScheduleType.ONCE:
        run_at = datetime.fromisoformat(schedule)
        return run_at

    return None


@dataclass
class ScheduledExecution:
    """
    Representa uma execução agendada de uma task.

    Contém informações sobre quando e como uma task deve ser executada,
    além do histórico de execuções anteriores.

    Attributes:
        job_id: Identificador único do job
        job_name: Nome descritivo do job
        task_name: Nome da task a executar
        schedule: Expressão de agendamento (cron ou intervalo)
        schedule_type: Tipo do agendamento
        params: Parâmetros para a task
        enabled: Se o job está ativo
        last_run: Timestamp da última execução
        next_run: Timestamp da próxima execução
        run_count: Número total de execuções
        success_count: Número de execuções com sucesso
        error_count: Número de execuções com erro
        last_error: Último erro ocorrido
        last_duration: Duração da última execução (segundos)
        created_at: Quando o job foi criado
        tags: Tags para organização
    """

    job_id: str
    job_name: str
    task_name: str
    schedule: str
    schedule_type: ScheduleType = ScheduleType.CRON
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    # Histórico de execução
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    success_count: int = 0
    error_count: int = 0
    last_error: str | None = None
    last_duration: float = 0.0

    # Metadados
    created_at: datetime = field(default_factory=datetime.now)
    tags: list[str] = field(default_factory=list)
    description: str = ""

    def __post_init__(self) -> None:
        """Calcula próxima execução após inicialização."""
        self.schedule_type = _parse_schedule_type(self.schedule_type)
        _validate_schedule(self.schedule_type, self.schedule)

        if self.next_run is None and self.enabled:
            self.calculate_next_run()

    def calculate_next_run(self) -> datetime | None:
        """
        Calcula a próxima execução baseada no schedule.

        Returns:
            Datetime da próxima execução ou None
        """
        if not self.enabled:
            self.next_run = None
            return None

        now = datetime.now()

        try:
            self.next_run = _compute_next_run(
                self.schedule_type, self.schedule, now=now
            )
        except Exception as e:
            # Erro fica registrado e job fica "sem next_run" para não travar o loop.
            logger.error(
                "Falha ao calcular próxima execução (%s): %s", self.job_name, e
            )
            self.last_error = str(e)
            self.next_run = None
        return self.next_run

    def mark_executed(
        self, success: bool, duration: float, error: str | None = None
    ) -> None:
        """
        Registra uma execução.

        Args:
            success: Se a execução foi bem sucedida
            duration: Duração em segundos
            error: Mensagem de erro se houver
        """
        self.last_run = datetime.now()
        self.run_count += 1
        self.last_duration = duration

        if success:
            self.success_count += 1
            self.last_error = None
        else:
            self.error_count += 1
            self.last_error = error

        # Calcula próxima execução (exceto para ONCE)
        if self.schedule_type == ScheduleType.ONCE:
            self.enabled = False
            self.next_run = None
        else:
            self.calculate_next_run()

    def is_due(self) -> bool:
        """
        Verifica se o job está pronto para executar.

        Returns:
            True se deve executar agora
        """
        if not self.enabled or self.next_run is None:
            return False
        return datetime.now() >= self.next_run

    @property
    def success_rate(self) -> float:
        """Taxa de sucesso (0.0 a 1.0)."""
        if self.run_count == 0:
            return 0.0
        return self.success_count / self.run_count

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário serializável."""
        return {
            "job_id": self.job_id,
            "job_name": self.job_name,
            "task_name": self.task_name,
            "schedule": self.schedule,
            "schedule_type": self.schedule_type.value,
            "params": self.params,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_duration": self.last_duration,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduledExecution:
        """Cria instância a partir de dicionário."""

        # Converte strings ISO para datetime
        def _dt(key: str) -> datetime | None:
            v = data.get(key)
            if not v:
                return None
            return datetime.fromisoformat(v)

        created_at = _dt("created_at") or datetime.now()

        return cls(
            job_id=data["job_id"],
            job_name=data["job_name"],
            task_name=data["task_name"],
            schedule=data["schedule"],
            schedule_type=_parse_schedule_type(data.get("schedule_type", "cron")),
            params=data.get("params", {}),
            enabled=bool(data.get("enabled", True)),
            last_run=_dt("last_run"),
            next_run=_dt("next_run"),
            run_count=int(data.get("run_count", 0)),
            success_count=int(data.get("success_count", 0)),
            error_count=int(data.get("error_count", 0)),
            last_error=data.get("last_error"),
            last_duration=float(data.get("last_duration", 0.0)),
            created_at=created_at,
            tags=list(data.get("tags", [])),
            description=str(data.get("description", "")),
        )


class Scheduler:
    """
    Gerenciador central de agendamento de tarefas.

    Coordena a execução de jobs agendados, gerenciando:
    - Registro e remoção de jobs
    - Loop de execução em background
    - Controle de estado (start/stop/pause)

    Exemplo:
        >>> scheduler = Scheduler()
        >>> scheduler.add_job(
        ...     name="backup_diario",
        ...     task="backup",
        ...     schedule="0 2 * * *"
        ... )
        >>> scheduler.start()
        >>> # ... scheduler roda em background ...
        >>> scheduler.stop()

    Attributes:
        registry: TaskRegistry com tasks disponíveis
        jobs: Dicionário de job_id -> ScheduledExecution
        running: Se o scheduler está rodando
        paused: Se o scheduler está pausado
    """

    def __init__(self, registry: TaskRegistry | None = None) -> None:
        """
        Inicializa o Scheduler.

        Args:
            registry: TaskRegistry customizado (opcional)
        """
        self.registry = registry or TaskRegistry()
        self.jobs: dict[str, ScheduledExecution] = {}

        self._running = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # RLock: permite reentrância segura se no futuro chamar métodos
        self._lock = threading.RLock()

        # Intervalo de verificação (segundos)
        self._check_interval = 1.0

        logger.debug("Scheduler inicializado")

    @property
    def running(self) -> bool:
        """Se o scheduler está rodando."""
        return self._running

    @property
    def paused(self) -> bool:
        """Se o scheduler está pausado."""
        return self._paused

    # ============================================================================
    # Gerenciamento de Jobs
    # ============================================================================

    def add_job(
        self,
        name: str,
        task: str,
        schedule: str,
        schedule_type: str | ScheduleType = ScheduleType.CRON,
        params: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        description: str = "",
        enabled: bool = True,
    ) -> ScheduledExecution:
        """
        Adiciona um novo job agendado.

        Args:
            name: Nome único do job
            task: Nome da task a executar
            schedule: Expressão de agendamento
            schedule_type: Tipo (cron, interval, daily, once)
            params: Parâmetros para a task
            tags: Tags para organização
            description: Descrição do job
            enabled: Se deve iniciar habilitado

        Returns:
            ScheduledExecution criado

        Raises:
            ValueError: Se task não existe ou nome duplicado
        """
        # Valida task
        task_key = task.lower().strip()
        if not self.registry.exists(task_key):
            available = ", ".join(self.registry.list_tasks())
            raise ValueError(f"Task '{task}' não encontrada. Disponíveis: {available}")

        # Converte schedule_type se string
        st = _parse_schedule_type(schedule_type)
        _validate_schedule(st, schedule)

        # Gera ID único

        job_id = str(uuid.uuid4())[:8]

        # Verifica nome duplicado
        for job in self.jobs.values():
            if job.job_name == name:
                raise ValueError(f"Já existe um job com nome '{name}'")

        with self._lock:
            # Nome duplicado verificado sob lock.
            for job in self.jobs.values():
                if job.job_name == name:
                    raise ValueError(f"Já existe um job com nome '{name}'")

            job_id = uuid.uuid4().hex[:8]

            execution = ScheduledExecution(
                job_id=job_id,
                job_name=name,
                task_name=task_key,
                schedule=schedule,
                schedule_type=st,
                params=params or {},
                enabled=enabled,
                tags=tags or [],
                description=description,
            )

            self.jobs[job_id] = execution

        logger.info(
            "Job adicionado: %s (%s) - próxima execução: %s",
            name,
            task_key,
            execution.next_run,
        )
        return execution

    def remove_job(self, job_id: str) -> bool:
        """
        Remove um job.

        Args:
            job_id: ID do job

        Returns:
            True se removido, False se não encontrado
        """
        with self._lock:
            job = self.jobs.pop(job_id, None)
        if job:
            logger.info("Job removido: %s", job.job_name)
            return True
        return False

    def get_job(self, job_id: str) -> ScheduledExecution | None:
        """Obtém um job pelo ID."""
        with self._lock:
            return self.jobs.get(job_id)

    def get_job_by_name(self, name: str) -> ScheduledExecution | None:
        """Obtém um job pelo nome."""
        with self._lock:
            for job in self.jobs.values():
                if job.job_name == name:
                    return job
        return None

    def list_jobs(self, enabled_only: bool = False) -> list[ScheduledExecution]:
        """
        Lista todos os jobs.

        Args:
            enabled_only: Se True, retorna apenas jobs habilitados

        Returns:
            Lista de ScheduledExecution
        """
        with self._lock:
            jobs = list(self.jobs.values())

        if enabled_only:
            jobs = [j for j in jobs if j.enabled]
        return sorted(jobs, key=lambda j: j.next_run or datetime.max)

    def enable_job(self, job_id: str) -> bool:
        """Habilita um job."""
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return False
            job.enabled = True
            job.calculate_next_run()
        logger.info("Job habilitado: %s", job.job_name)
        return True

    def disable_job(self, job_id: str) -> bool:
        """Desabilita um job."""
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return False
            job.enabled = False
            job.next_run = None
        logger.info("Job desabilitado: %s", job.job_name)
        return True

    # ============================================================================
    # Execução
    # ============================================================================

    def run_job(self, job_id: str) -> bool:
        """
        Executa um job manualmente (fora do agendamento).

        Args:
            job_id: ID do job

        Returns:
            True se executado com sucesso
        """
        job = self.get_job(job_id)
        if not job:
            logger.error("Job não encontrado: %s", job_id)
            return False
        return self._execute_job(job)

    def _execute_job(self, job: ScheduledExecution) -> bool:
        """
        Executa um job.

        Args:
            job: ScheduledExecution a executar

        Returns:
            True se sucesso
        """
        logger.info("Executando job: %s (%s)", job.job_name, job.task_name)

        start = time.perf_counter()
        success = False
        error_msg: str | None = None

        try:
            # Obtém classe da task
            task_class = self.registry.get(job.task_name)
            if not task_class:
                raise ValueError(f"Task '{job.task_name}' não encontrada")

            # Instancia e executa
            task_instance = task_class(**job.params)
            result = task_instance.run()

            # Verifica resultado
            # Verifica resultado (suporta DummyResult com atributo `success` e TaskResult do core.base)
            try:
                from autotarefas.core.base import TaskResult  # import local evita ciclos
            except Exception:
                TaskResult = None  # type: ignore

            if TaskResult is not None and isinstance(result, TaskResult):
                # TaskResult usa status (SUCCESS/FAILED/etc.)
                success = bool(getattr(result, "status", None) and result.status.is_success)
                if not success:
                    # Prioriza mensagem e depois a exceção
                    msg = getattr(result, "message", "") or ""
                    err = getattr(result, "error", None)
                    error_msg = msg.strip() or (str(err) if err else "task failed")
            elif hasattr(result, "success"):
                success = bool(result.success)
                if not success and hasattr(result, "error"):
                    error_msg = str(result.error)
            else:
                # Se não tem um formato de resultado conhecido, considera sucesso
                success = True

            logger.info(
                "Job %s concluído: %s", job.job_name, "sucesso" if success else "falha"
            )

        except Exception as e:
            error_msg = str(e)
            logger.exception("Erro ao executar job %s: %s", job.job_name, e)

        duration = time.perf_counter() - start
        job.mark_executed(success, duration, error_msg)

        return success

    # ============================================================================
    # Controle do Loop
    # ============================================================================

    def start(self, blocking: bool = False) -> None:
        """
        Inicia o scheduler.

        Args:
            blocking: Se True, bloqueia a thread atual
        """
        with self._lock:
            if self._running:
                logger.warning("Scheduler já está rodando")
                return

            self._running = True
            self._paused = False
            self._stop_event.clear()

        logger.info("Scheduler iniciado")

        if blocking:
            self._run_loop()

        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="autotarefas-scheduler"
        )
        self._thread.start()

    def stop(self, wait: bool = True, timeout: float = 5.0) -> None:
        """
        Para o scheduler.

        Args:
            wait: Se deve aguardar a thread terminar
            timeout: Timeout para aguardar (segundos)
        """
        with self._lock:
            if not self._running:
                return
            logger.info("Parando scheduler...")
            self._stop_event.set()

        t = self._thread
        if wait and t and t.is_alive():
            t.join(timeout=timeout)

        with self._lock:
            self._running = False
            self._paused = False

        logger.info("Scheduler parado")

    def pause(self) -> None:
        """Pausa o scheduler (não executa jobs, mas continua rodando)."""
        with self._lock:
            self._paused = True
        logger.info("Scheduler pausado")

    def resume(self) -> None:
        """Resume o scheduler após pausa."""
        with self._lock:
            self._paused = False
        logger.info("Scheduler resumido")

    def _run_loop(self) -> None:
        """Loop principal de execução."""
        logger.debug("Loop do scheduler iniciado")

        while not self._stop_event.is_set():
            # Lê paused sob lock para evitar condição de corrida.
            with self._lock:
                paused = self._paused

            if not paused:
                self._check_and_run_jobs()

            self._stop_event.wait(self._check_interval)

        logger.debug("Loop do scheduler encerrado")

    def _check_and_run_jobs(self) -> None:
        """Verifica e executa jobs pendentes."""
        with self._lock:
            due_jobs = [j for j in self.jobs.values() if j.is_due()]

        for job in due_jobs:
            self._execute_job(job)

    # ============================================================================
    # Status e Info
    # ============================================================================

    def get_status(self) -> dict[str, Any]:
        """
        Retorna status do scheduler.

        Returns:
            Dicionário com informações de status
        """
        with self._lock:
            enabled_jobs = [j for j in self.jobs.values() if j.enabled]
            next_job = min(
                enabled_jobs, key=lambda j: j.next_run or datetime.max, default=None
            )

            return {
                "running": self._running,
                "paused": self._paused,
                "total_jobs": len(self.jobs),
                "enabled_jobs": len(enabled_jobs),
                "next_execution": (
                    next_job.next_run.isoformat()
                    if next_job and next_job.next_run
                    else None
                ),
                "next_job": next_job.job_name if next_job else None,
            }

    def get_stats(self) -> dict[str, Any]:
        """
        Retorna estatísticas de execução.

        Returns:
            Dicionário com estatísticas
        """
        with self._lock:
            total_runs = sum(j.run_count for j in self.jobs.values())
            total_success = sum(j.success_count for j in self.jobs.values())
            total_errors = sum(j.error_count for j in self.jobs.values())

        return {
            "total_jobs": len(self.jobs),
            "total_runs": total_runs,
            "total_success": total_success,
            "total_errors": total_errors,
            "success_rate": (total_success / total_runs) if total_runs > 0 else 0.0,
        }


_scheduler_instance: Scheduler | None = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> Scheduler:
    """
    Obtém instância singleton do Scheduler.

    Thread-safe. Cria uma nova instância na primeira chamada.

    Returns:
        Instância global do Scheduler

    Exemplo:
        >>> scheduler = get_scheduler()
        >>> scheduler.add_job("backup", "backup", "0 2 * * *")
    """
    global _scheduler_instance

    if _scheduler_instance is None:
        with _scheduler_lock:
            if _scheduler_instance is None:
                _scheduler_instance = Scheduler()
                logger.debug("Instância singleton do Scheduler criada")

    return _scheduler_instance


def reset_scheduler() -> None:
    """
    Reseta a instância singleton (útil para testes).

    Atenção: Para o scheduler atual antes de resetar.
    """
    global _scheduler_instance

    with _scheduler_lock:
        if _scheduler_instance is not None:
            _scheduler_instance.stop(wait=True)
            _scheduler_instance = None
            logger.debug("Instância singleton do Scheduler resetada")


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Enums
    "ScheduleType",
    # Classes
    "TaskRegistry",
    "ScheduledExecution",
    "Scheduler",
    # Funções
    "get_scheduler",
    "reset_scheduler",
    # Constantes
    "CRONITER_AVAILABLE",
]
