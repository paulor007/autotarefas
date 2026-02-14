"""
Armazenamento de Jobs Agendados do AutoTarefas.

Persiste jobs em formato JSON para recuperação entre execuções:
    - JobStatus: Estados possíveis de um job
    - Job: Representa um job agendado
    - JobStore: Gerencia persistência de jobs

Uso:
    from autotarefas.core.storage.job_store import JobStore, JobStatus

    store = JobStore()
    job = store.create(
        name="backup_diario",
        task="backup",
        schedule="0 2 * * *",
        params={"source": "/home/user/docs"}
    )
    store.save(job)

    # Recuperar
    job = store.get(job.id)
    jobs = store.list_all()
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final

from autotarefas.core.logger import logger
from autotarefas.utils.datetime_utils import dt_to_iso, parse_dt, utc_now
from autotarefas.utils.json_utils import atomic_write_json

# =============================================================================
# Modelos
# =============================================================================


class JobStatus(Enum):
    """
    Status possíveis de um job.

    Valores:
        ACTIVE: Job ativo e será executado no próximo agendamento
        PAUSED: Job pausado manualmente (não executa)
        DISABLED: Job desabilitado (não executa)
        COMPLETED: Job de execução única já executado
        FAILED: Última execução falhou
    """

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class Job:
    """
    Representa um job agendado persistido.

    Attributes:
        id: Identificador único (UUID)
        name: Nome descritivo do job
        task: Nome da task a executar
        schedule: Expressão de agendamento
        schedule_type: Tipo do agendamento
        params: Parâmetros da task
        status: Status atual do job
        description: Descrição opcional
        tags: Tags para organização
        created_at: Data de criação (UTC)
        updated_at: Última atualização (UTC)
        last_run: Última execução
        next_run: Próxima execução
        run_count: Total de execuções
        success_count: Execuções com sucesso
        error_count: Execuções com erro
        last_error: Última mensagem de erro
        last_duration: Duração da última execução
        max_retries: Máximo de tentativas
        retry_delay: Delay entre tentativas
        timeout: Timeout da task
        enabled: Se o job está habilitado
    """

    id: str
    name: str
    task: str
    schedule: str
    schedule_type: str = "cron"
    params: dict[str, Any] = field(default_factory=dict)

    status: JobStatus = JobStatus.ACTIVE
    description: str = ""
    tags: list[str] = field(default_factory=list)

    # Timestamps (UTC)
    created_at: Any = field(default_factory=utc_now)
    updated_at: Any = field(default_factory=utc_now)
    last_run: Any = None
    next_run: Any = None

    # Estatísticas
    run_count: int = 0
    success_count: int = 0
    error_count: int = 0
    last_error: str | None = None
    last_duration: float = 0.0

    # Configurações
    max_retries: int = 3
    retry_delay: int = 60
    timeout: int = 3600
    enabled: bool = True

    def __post_init__(self) -> None:
        """
        Normaliza campos após criação:

        - Converte status para enum
        - Garante datetimes timezone-aware em UTC
        """
        if isinstance(self.status, str):
            self.status = JobStatus(self.status)

        self.created_at = parse_dt(self.created_at) or utc_now()
        self.updated_at = parse_dt(self.updated_at) or utc_now()
        self.last_run = parse_dt(self.last_run)
        self.next_run = parse_dt(self.next_run)

    @property
    def success_rate(self) -> float:
        """
        Retorna a taxa de sucesso do job.

        Returns:
            Float entre 0.0 e 1.0
        """
        return 0.0 if self.run_count == 0 else self.success_count / self.run_count

    def mark_updated(self) -> None:
        """
        Atualiza timestamp de modificação.
        """
        self.updated_at = utc_now()

    def mark_executed(
        self,
        success: bool,
        duration: float,
        *,
        error: str | None = None,
        next_run: Any = None,
    ) -> None:
        """
        Registra uma execução do job.

        Args:
            success: Se a execução foi bem sucedida
            duration: Duração em segundos
            error: Mensagem de erro (se houver)
            next_run: Próxima execução (datetime ou ISO string)
        """
        self.last_run = utc_now()
        self.run_count += 1
        self.last_duration = float(duration)
        self.next_run = parse_dt(next_run)

        if success:
            self.success_count += 1
            self.last_error = None
            self.status = JobStatus.ACTIVE
        else:
            self.error_count += 1
            self.last_error = error
            self.status = JobStatus.FAILED

        self.mark_updated()

    def to_dict(self) -> dict[str, Any]:
        """
        Converte o job para dicionário serializável.

        Returns:
            Dicionário pronto para JSON
        """
        return {
            "id": self.id,
            "name": self.name,
            "task": self.task,
            "schedule": self.schedule,
            "schedule_type": self.schedule_type,
            "params": self.params,
            "status": self.status.value,
            "description": self.description,
            "tags": self.tags,
            "created_at": dt_to_iso(self.created_at),
            "updated_at": dt_to_iso(self.updated_at),
            "last_run": dt_to_iso(self.last_run),
            "next_run": dt_to_iso(self.next_run),
            "run_count": self.run_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_duration": self.last_duration,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "timeout": self.timeout,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        """
        Cria um Job a partir de um dicionário.

        Args:
            data: Dicionário de dados

        Returns:
            Instância de Job
        """
        status_raw = data.get("status", JobStatus.ACTIVE.value)
        status = JobStatus(status_raw) if isinstance(status_raw, str) else status_raw

        return cls(
            id=str(data.get("id") or uuid.uuid4()),
            name=str(data["name"]),
            task=str(data["task"]),
            schedule=str(data["schedule"]),
            schedule_type=str(data.get("schedule_type", "cron")),
            params=dict(data.get("params", {})),
            status=status,
            description=str(data.get("description", "")),
            tags=list(data.get("tags", [])),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            last_run=data.get("last_run"),
            next_run=data.get("next_run"),
            run_count=int(data.get("run_count", 0)),
            success_count=int(data.get("success_count", 0)),
            error_count=int(data.get("error_count", 0)),
            last_error=data.get("last_error"),
            last_duration=float(data.get("last_duration", 0.0)),
            max_retries=int(data.get("max_retries", 3)),
            retry_delay=int(data.get("retry_delay", 60)),
            timeout=int(data.get("timeout", 3600)),
            enabled=bool(data.get("enabled", True)),
        )


# =============================================================================
# Store (JSON)
# =============================================================================


class JobStore:
    """
    Gerenciador de persistência de jobs em JSON.

    Armazena jobs em disco e mantém cache em memória.
    """

    DEFAULT_FILENAME: Final[str] = "jobs.json"
    FILE_VERSION: Final[str] = "1.0"

    def __init__(self, filepath: str | Path | None = None) -> None:
        """
        Inicializa o JobStore.

        Args:
            filepath: Caminho do arquivo JSON (opcional)
        """
        if filepath:
            self.filepath = Path(filepath)
        else:
            from autotarefas.config import settings

            data_dir = getattr(settings, "DATA_DIR", Path(settings.data_dir))
            data_dir.mkdir(parents=True, exist_ok=True)
            self.filepath = data_dir / self.DEFAULT_FILENAME

        self._jobs: dict[str, Job] = {}
        self._load()

    def _load(self) -> None:
        """
        Carrega jobs do arquivo JSON.
        """
        if not self.filepath.exists():
            logger.debug(f"Arquivo de jobs não existe: {self.filepath}")
            return

        try:
            with open(self.filepath, encoding="utf-8") as f:
                payload = json.load(f)

            for item in payload.get("jobs", []):
                job = Job.from_dict(item)
                self._jobs[job.id] = job

            logger.info(f"Carregados {len(self._jobs)} job(s) de {self.filepath}")

        except Exception as e:
            logger.exception(f"Erro ao carregar jobs: {e}")

    def _save(self) -> None:
        """
        Salva jobs no arquivo JSON usando escrita atômica.
        """
        payload = {
            "version": self.FILE_VERSION,
            "updated_at": dt_to_iso(utc_now()),
            "jobs": [job.to_dict() for job in self._jobs.values()],
        }
        atomic_write_json(self.filepath, payload)

    # -------------------------------------------------------------------------
    # API pública
    # -------------------------------------------------------------------------

    def create(
        self,
        name: str,
        task: str,
        schedule: str,
        schedule_type: str = "cron",
        params: dict[str, Any] | None = None,
        description: str = "",
        tags: list[str] | None = None,
        enabled: bool = True,
    ) -> Job:
        """
        Cria um novo job (não salva automaticamente).

        Raises:
            ValueError: Se já existir job com mesmo nome
        """
        if self.get_by_name(name):
            raise ValueError(f"Já existe um job com nome '{name}'")

        return Job(
            id=str(uuid.uuid4()),
            name=name,
            task=task,
            schedule=schedule,
            schedule_type=schedule_type,
            params=params or {},
            description=description,
            tags=tags or [],
            enabled=enabled,
        )

    def save(self, job: Job) -> None:
        """
        Salva ou atualiza um job.
        """
        job.mark_updated()
        self._jobs[job.id] = job
        self._save()

    def get(self, job_id: str) -> Job | None:
        """
        Obtém job pelo ID.
        """
        return self._jobs.get(job_id)

    def get_by_name(self, name: str) -> Job | None:
        """
        Obtém job pelo nome.
        """
        return next((j for j in self._jobs.values() if j.name == name), None)

    def delete(self, job_id: str) -> bool:
        """
        Remove um job.
        """
        job = self._jobs.pop(job_id, None)
        if not job:
            return False
        self._save()
        return True

    def list_all(self) -> list[Job]:
        """
        Lista todos os jobs ordenados por nome.
        """
        return sorted(self._jobs.values(), key=lambda j: j.name)

    def list_enabled(self) -> list[Job]:
        """
        Lista apenas jobs habilitados.
        """
        return [j for j in self._jobs.values() if j.enabled]

    def update_status(self, job_id: str, status: JobStatus) -> bool:
        """
        Atualiza status de um job.
        """
        job = self.get(job_id)
        if not job:
            return False
        job.status = status
        job.enabled = status == JobStatus.ACTIVE
        self.save(job)
        return True

    def clear(self) -> int:
        """
        Remove todos os jobs.

        Returns:
            Quantidade removida
        """
        count = len(self._jobs)
        self._jobs.clear()
        self._save()
        return count


__all__ = ["JobStatus", "Job", "JobStore"]
