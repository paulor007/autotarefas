"""Backend do Live System do AutoTarefas (FastAPI).

Live-1.2: executa as automacoes curadas DE VERDADE num sandbox isolado
(upload -> workspace efemero -> AutoTarefas real -> artefatos -> download).
O streaming ao vivo (SSE) e mais automacoes entram na Live-1.3.
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import catalog, demo_servers, engine, samples, uploads
from .config import settings

_CLEANUP_INTERVAL_S = 300


def _browser_available() -> bool:
    """True se o Playwright/Chromium esta instalado (RPA e scraping-JS)."""
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


async def _cleanup_loop() -> None:
    """Varre e apaga workspaces expirados periodicamente."""
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL_S)
        with contextlib.suppress(Exception):
            engine.sweep_expired()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    demo_servers.start()
    cleanup = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        cleanup.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup
        demo_servers.stop()


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Saude do servico, dos mocks e quais automacoes rodam ao vivo."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "browser_available": _browser_available(),
        "active_automations": list(engine.ACTIVE_AUTOMATIONS),
        "demo_servers": demo_servers.status(),
    }


@app.get("/api/catalog")
def get_catalog() -> dict[str, Any]:
    """Catalogo curado das automacoes (sem comandos nem caminhos)."""
    return catalog.public_catalog()


@app.get("/api/sample/{automation_id}")
def get_sample(automation_id: str) -> JSONResponse:
    """Metadados dos arquivos de exemplo de uma automacao."""
    item = catalog.get(automation_id)
    if item is None or not samples.has_sample(automation_id):
        return JSONResponse({"detail": "sem exemplo para esta automacao"}, status_code=404)
    return JSONResponse({"automation": automation_id, "files": samples.list_sample(automation_id)})


@app.post("/api/run/{automation_id}")
async def run_automation(
    automation_id: str,
    files: list[UploadFile] = File(default=[]),  # noqa: B008
    use_sample: bool = False,
) -> JSONResponse:
    """Executa uma automacao curada de verdade e devolve o resultado."""
    item = catalog.get(automation_id)
    if item is None:
        return JSONResponse({"detail": "automacao desconhecida"}, status_code=404)
    if automation_id not in engine.ACTIVE_AUTOMATIONS:
        return JSONResponse({"detail": "automacao ainda nao disponivel ao vivo"}, status_code=501)

    try:
        token, workspace = engine.create_workspace()
    except engine.WorkspaceFull:
        return JSONResponse({"detail": "servidor ocupado, tente em instantes"}, status_code=503)

    try:
        inputs: list[Path] = []
        if item.upload != "none":
            if use_sample:
                if not samples.has_sample(automation_id):
                    raise uploads.UploadError(400, "sem exemplo para esta automacao")
                inputs = samples.copy_sample_to(automation_id, workspace / "in")
            else:
                inputs = await uploads.save_uploads(
                    files, workspace / "in", require_csv=(item.upload == "csv")
                )
        result = engine.run(automation_id, inputs, token, workspace)
        return JSONResponse(result.as_dict())
    except uploads.UploadError as exc:
        shutil.rmtree(workspace, ignore_errors=True)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    except Exception:  # noqa: BLE001
        shutil.rmtree(workspace, ignore_errors=True)
        return JSONResponse({"detail": "falha ao executar a automacao"}, status_code=500)


@app.get("/api/download/{token}/{name}")
def download(token: str, name: str) -> Response:
    """Baixa um artefato gerado, restrito ao `out/` do workspace (anti-traversal)."""
    path = engine.resolve_artifact(token, name)
    if path is None:
        return JSONResponse({"detail": "arquivo nao encontrado"}, status_code=404)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


# Front-end buildado (Vite) — montado automaticamente quando existir (Fase 2/deploy).
_frontend_dist = settings.repo_root / "live_demo" / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
