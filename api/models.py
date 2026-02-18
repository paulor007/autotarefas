"""
AutoTarefas - API Models
========================

Schemas Pydantic para validação de dados da API.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ==================== ENUMS ====================


class TaskStatusEnum(StrEnum):
    """Status possíveis de uma task."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


# ==================== SYSTEM ====================


class SystemInfo(BaseModel):
    """Informações do sistema."""

    platform: str
    platform_version: str | None = None
    python_version: str
    cpu_percent: float | None = None
    memory: dict[str, Any] | None = None
    disk: dict[str, Any] | None = None
    autotarefas_available: bool = False


class HealthCheck(BaseModel):
    """Resposta do health check."""

    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.now)


# ==================== TASKS ====================


class TaskInfo(BaseModel):
    """Informações de uma task."""

    id: str
    name: str
    description: str
    available: bool = True


class TaskListResponse(BaseModel):
    """Lista de tasks disponíveis."""

    tasks: list[TaskInfo]


class TaskRunRequest(BaseModel):
    """Request para executar uma task."""

    params: dict[str, Any] = Field(default_factory=dict)


class TaskRunResponse(BaseModel):
    """Resposta da execução de uma task."""

    task_id: str
    status: TaskStatusEnum
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None


# ==================== MONITOR ====================


class CpuMetrics(BaseModel):
    """Métricas de CPU."""

    percent: float
    frequency_mhz: float | None = None
    cores: int | None = None


class MemoryMetrics(BaseModel):
    """Métricas de memória."""

    total_gb: float
    available_gb: float
    used_gb: float
    percent: float


class DiskMetrics(BaseModel):
    """Métricas de disco."""

    total_gb: float
    free_gb: float
    used_gb: float
    percent: float


class NetworkMetrics(BaseModel):
    """Métricas de rede."""

    bytes_sent: int
    bytes_recv: int


class MonitorMetrics(BaseModel):
    """Métricas completas de monitoramento."""

    timestamp: datetime
    cpu: CpuMetrics
    memory: MemoryMetrics
    disk: DiskMetrics
    network: NetworkMetrics


class ProcessInfo(BaseModel):
    """Informações de um processo."""

    pid: int
    name: str
    cpu_percent: float
    memory_percent: float


class ProcessListResponse(BaseModel):
    """Lista de processos."""

    processes: list[ProcessInfo]


# ==================== JOBS ====================


class JobInfo(BaseModel):
    """Informações de um job agendado."""

    id: str
    name: str
    task_type: str
    schedule: str
    enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None


class JobListResponse(BaseModel):
    """Lista de jobs agendados."""

    jobs: list[JobInfo]


class JobCreateRequest(BaseModel):
    """Request para criar um job."""

    name: str
    task_type: str
    schedule: str
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


# ==================== HISTORY ====================


class RunHistoryEntry(BaseModel):
    """Entrada no histórico de execuções."""

    id: str
    job_name: str
    task_type: str
    status: TaskStatusEnum
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    message: str | None = None


class RunHistoryResponse(BaseModel):
    """Histórico de execuções."""

    entries: list[RunHistoryEntry]
    total: int
    page: int = 1
    per_page: int = 20


# ==================== WEBSOCKET ====================


class WebSocketMessage(BaseModel):
    """Mensagem WebSocket."""

    type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    data: dict[str, Any] = Field(default_factory=dict)


class MetricsUpdate(BaseModel):
    """Atualização de métricas via WebSocket."""

    type: str = "metrics"
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_percent: float
