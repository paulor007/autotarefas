"""
AutoTarefas - Dashboard API
===========================

API REST e WebSocket para o dashboard web do AutoTarefas.

Uso:
    from autotarefas.api import app

    # Ou executar diretamente:
    # uvicorn autotarefas.api.main:app --reload
"""

from .main import app, manager
from .models import (
    CpuMetrics,
    DiskMetrics,
    HealthCheck,
    JobCreateRequest,
    JobInfo,
    JobListResponse,
    MemoryMetrics,
    MetricsUpdate,
    MonitorMetrics,
    NetworkMetrics,
    ProcessInfo,
    ProcessListResponse,
    RunHistoryEntry,
    RunHistoryResponse,
    SystemInfo,
    TaskInfo,
    TaskListResponse,
    TaskRunRequest,
    TaskRunResponse,
    TaskStatusEnum,
    WebSocketMessage,
)

__all__ = [
    # App
    "app",
    "manager",
    # Models
    "TaskStatusEnum",
    "SystemInfo",
    "HealthCheck",
    "TaskInfo",
    "TaskListResponse",
    "TaskRunRequest",
    "TaskRunResponse",
    "CpuMetrics",
    "MemoryMetrics",
    "DiskMetrics",
    "NetworkMetrics",
    "MonitorMetrics",
    "ProcessInfo",
    "ProcessListResponse",
    "JobInfo",
    "JobListResponse",
    "JobCreateRequest",
    "RunHistoryEntry",
    "RunHistoryResponse",
    "WebSocketMessage",
    "MetricsUpdate",
]
