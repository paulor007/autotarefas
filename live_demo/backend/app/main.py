"""Backend do Live System do AutoTarefas (FastAPI).

Live-1 (este esqueleto): catalogo curado, /api/health, e subida dos mocks no
ciclo de vida. A execucao real (upload -> workspace efemero -> rodar -> download)
e o streaming ao vivo (SSE) entram nas Live-2 e Live-3.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import catalog, demo_servers
from .config import settings


def _browser_available() -> bool:
    """True se o Playwright/Chromium esta instalado (RPA e scraping-JS)."""
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    demo_servers.start()
    try:
        yield
    finally:
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
    """Saude do servico e dos mocks (usado pelo front e por monitoramento)."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "browser_available": _browser_available(),
        "demo_servers": demo_servers.status(),
    }


@app.get("/api/catalog")
def get_catalog() -> dict[str, Any]:
    """Catalogo curado das automacoes (sem comandos nem caminhos)."""
    return catalog.public_catalog()


@app.post("/api/run/{automation_id}")
def run_automation(automation_id: str) -> JSONResponse:
    """Dispara uma automacao curada. Implementacao real entra na Live-2."""
    item = catalog.get(automation_id)
    if item is None:
        return JSONResponse({"detail": "automacao desconhecida"}, status_code=404)
    return JSONResponse(
        {"detail": "execucao ao vivo entra na Live-2", "automation": automation_id},
        status_code=501,
    )


@app.get("/api/download/{token}/{name}")
def download(token: str, name: str) -> JSONResponse:
    """Baixa um artefato gerado. Implementacao real (segura) entra na Live-2."""
    return JSONResponse({"detail": "download entra na Live-2"}, status_code=501)


# Front-end buildado (Vite) — montado automaticamente quando existir (Fase 2/deploy).
_frontend_dist = settings.repo_root / "live_demo" / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
