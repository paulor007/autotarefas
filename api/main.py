# type: ignore
"""
AutoTarefas - Dashboard API
===========================

API REST e WebSocket para o dashboard web.

Requisitos:
    pip install fastapi uvicorn websockets python-multipart

Executar:
    uvicorn autotarefas.api.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Imports opcionais do autotarefas
AUTOTAREFAS_AVAILABLE = False
try:
    from autotarefas.core.base import TaskStatus
    from autotarefas.tasks.backup import BackupTask
    from autotarefas.tasks.cleaner import CleanerTask
    from autotarefas.tasks.monitor import MonitorTask

    AUTOTAREFAS_AVAILABLE = True
except ImportError:
    TaskStatus = None
    BackupTask = None
    CleanerTask = None
    MonitorTask = None


# WebSocket manager para conexões ativas
class ConnectionManager:
    """Gerencia conexões WebSocket ativas."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]):
        """Envia mensagem para todas as conexões ativas."""
        for connection in self.active_connections:
            with suppress(Exception):
                await connection.send_json(message)


manager = ConnectionManager()


# Lifespan para startup/shutdown
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Gerencia ciclo de vida da aplicação."""
    logger.info("Dashboard API iniciando...")
    yield
    logger.info("Dashboard API encerrando...")


# Criar app FastAPI
app = FastAPI(
    title="AutoTarefas Dashboard",
    description="API para gerenciamento de tarefas automatizadas",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS para permitir frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== ENDPOINTS ====================


@app.get("/")
async def root():
    """Endpoint raiz com informações da API."""
    return {
        "name": "AutoTarefas Dashboard API",
        "version": "1.0.0",
        "status": "online",
        "autotarefas_available": AUTOTAREFAS_AVAILABLE,
        "endpoints": {
            "health": "/health",
            "system": "/api/system",
            "tasks": "/api/tasks",
            "monitor": "/api/monitor",
            "websocket": "/ws/metrics",
        },
    }


@app.get("/health")
async def health_check():
    """Health check da API."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ==================== SYSTEM ====================


@app.get("/api/system")
async def get_system_info():
    """Retorna informações do sistema."""
    import platform
    import sys

    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": sys.version,
            "cpu_percent": cpu_percent,
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
            },
            "disk": {
                "total": disk.total,
                "free": disk.free,
                "percent": disk.percent,
            },
            "autotarefas_available": AUTOTAREFAS_AVAILABLE,
        }
    except ImportError:
        return {
            "platform": platform.system(),
            "python_version": sys.version,
            "autotarefas_available": AUTOTAREFAS_AVAILABLE,
            "error": "psutil não instalado",
        }


# ==================== TASKS ====================


@app.get("/api/tasks")
async def list_tasks():
    """Lista todas as tasks disponíveis."""
    tasks = [
        {
            "id": "backup",
            "name": "BackupTask",
            "description": "Backup de arquivos e diretórios",
            "available": AUTOTAREFAS_AVAILABLE and BackupTask is not None,
        },
        {
            "id": "cleaner",
            "name": "CleanerTask",
            "description": "Limpeza de arquivos antigos",
            "available": AUTOTAREFAS_AVAILABLE and CleanerTask is not None,
        },
        {
            "id": "monitor",
            "name": "MonitorTask",
            "description": "Monitoramento do sistema",
            "available": AUTOTAREFAS_AVAILABLE and MonitorTask is not None,
        },
    ]
    return {"tasks": tasks}


@app.post("/api/tasks/{task_id}/run")
async def run_task(task_id: str, params: dict[str, Any] | None = None):
    """Executa uma task específica."""
    if not AUTOTAREFAS_AVAILABLE:
        raise HTTPException(status_code=503, detail="autotarefas não disponível")

    params = params or {}

    try:
        if task_id == "monitor":
            task = MonitorTask(name="api_monitor", **params)
            result = task.run()
            return {
                "task_id": task_id,
                "status": result.status.value if result.status else "unknown",
                "message": result.message,
                "data": result.data,
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Task '{task_id}' não pode ser executada via API sem parâmetros",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ==================== MONITOR ====================


@app.get("/api/monitor")
async def get_monitor_metrics():
    """Retorna métricas de monitoramento."""
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_freq = psutil.cpu_freq()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()

        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "percent": cpu_percent,
                "frequency_mhz": cpu_freq.current if cpu_freq else None,
                "cores": psutil.cpu_count(),
            },
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "percent": memory.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "percent": disk.percent,
            },
            "network": {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
            },
        }
    except ImportError as e:
        raise HTTPException(status_code=503, detail="psutil não instalado") from e


@app.get("/api/monitor/processes")
async def get_top_processes(limit: int = 10):
    """Retorna os processos que mais consomem recursos."""
    try:
        import psutil

        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                info = proc.info
                processes.append(
                    {
                        "pid": info["pid"],
                        "name": info["name"],
                        "cpu_percent": info["cpu_percent"] or 0,
                        "memory_percent": round(info["memory_percent"] or 0, 2),
                    }
                )

        # Ordenar por CPU
        processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
        return {"processes": processes[:limit]}
    except ImportError as e:
        raise HTTPException(status_code=503, detail="psutil não instalado") from e


# ==================== WEBSOCKET ====================


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """WebSocket para métricas em tempo real."""
    await manager.connect(websocket)
    try:
        while True:
            try:
                import psutil

                metrics = {
                    "type": "metrics",
                    "timestamp": datetime.now().isoformat(),
                    "cpu_percent": psutil.cpu_percent(interval=0),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_percent": psutil.disk_usage("/").percent,
                }
                await websocket.send_json(metrics)
            except ImportError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "psutil não disponível",
                    }
                )

            await asyncio.sleep(2)  # Atualiza a cada 2 segundos
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ==================== ERROR HANDLERS ====================


@app.exception_handler(Exception)
async def generic_exception_handler(_request: Request, exc: Exception):
    """Handler genérico de exceções."""
    logger.error(f"Erro não tratado: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor", "error": str(exc)},
    )


# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
