# type: ignore
"""
AutoTarefas - Dashboard Server
==============================

Servidor completo com API e Frontend.

Executar:
    python server.py

Acessar:
    http://localhost:8000
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)
FRONTEND_DIR = Path(__file__).parent / "frontend"

# Verificar autotarefas
AUTOTAREFAS_AVAILABLE = False
try:
    from autotarefas.tasks.monitor import MonitorTask

    AUTOTAREFAS_AVAILABLE = True
except ImportError:
    MonitorTask = None


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Dashboard iniciando...")
    yield
    logger.info("Dashboard encerrando...")


app = FastAPI(title="AutoTarefas Dashboard", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        content = content.replace("const API_URL = 'http://localhost:8000';", "const API_URL = window.location.origin;")
        return HTMLResponse(content=content)
    return HTMLResponse("<h1>Dashboard não encontrado</h1>", status_code=404)


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/system")
async def get_system():
    import platform
    import sys

    try:
        import psutil

        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": sys.version,
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "autotarefas_available": AUTOTAREFAS_AVAILABLE,
        }
    except ImportError:
        return {
            "platform": platform.system(),
            "python_version": sys.version,
            "autotarefas_available": AUTOTAREFAS_AVAILABLE,
        }


@app.get("/api/tasks")
async def list_tasks():
    return {
        "tasks": [
            {
                "id": "backup",
                "name": "BackupTask",
                "description": "Backup de arquivos",
                "available": AUTOTAREFAS_AVAILABLE,
            },
            {
                "id": "cleaner",
                "name": "CleanerTask",
                "description": "Limpeza de arquivos",
                "available": AUTOTAREFAS_AVAILABLE,
            },
            {
                "id": "monitor",
                "name": "MonitorTask",
                "description": "Monitoramento do sistema",
                "available": AUTOTAREFAS_AVAILABLE,
            },
        ]
    }


@app.post("/api/tasks/{task_id}/run")
async def run_task(task_id: str, params: dict[str, Any] | None = None):
    if not AUTOTAREFAS_AVAILABLE:
        raise HTTPException(503, "autotarefas não disponível")
    if task_id == "monitor" and MonitorTask:
        task = MonitorTask(name="api_monitor", **(params or {}))
        result = task.run()
        return {
            "task_id": task_id,
            "status": result.status.value if result.status else "unknown",
            "message": result.message,
            "data": result.data,
        }
    raise HTTPException(400, f"Task '{task_id}' não pode ser executada via API")


@app.get("/api/monitor")
async def get_metrics():
    try:
        import psutil

        cpu_freq = psutil.cpu_freq()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "percent": psutil.cpu_percent(interval=0.1),
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
            "network": {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv},
        }
    except ImportError as e:
        raise HTTPException(503, "psutil não instalado") from e


@app.get("/api/monitor/processes")
async def get_processes(limit: int = 10):
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
        processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
        return {"processes": processes[:limit]}

    except ImportError as e:
        raise HTTPException(503, "psutil não instalado") from e


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            try:
                import psutil

                await websocket.send_json(
                    {
                        "type": "metrics",
                        "timestamp": datetime.now().isoformat(),
                        "cpu_percent": psutil.cpu_percent(interval=0),
                        "memory_percent": psutil.virtual_memory().percent,
                        "disk_percent": psutil.disk_usage("/").percent,
                    }
                )
            except ImportError:
                await websocket.send_json({"type": "error", "message": "psutil não disponível"})
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.exception_handler(Exception)
async def exception_handler(_request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


if __name__ == "__main__":
    import uvicorn

    print("=" * 50)
    print("AutoTarefas Dashboard")
    print("=" * 50)
    print("Acesse: http://localhost:8000")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
