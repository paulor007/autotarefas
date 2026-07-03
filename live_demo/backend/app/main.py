"""Backend do Live System do AutoTarefas (FastAPI).

Live-1.3: execucao em duas fases com stdout ao vivo.
  POST /api/run/{id}       -> inicia o job, retorna {token, stream_url, status}
  GET  /api/stream/{token} -> stdout ao vivo via SSE (event final: done/timeout)
  GET  /api/result/{token} -> resultado consolidado (fallback/reconexao)
  GET  /api/download/...    -> baixa artefato (anti path traversal)
Seguranca: rate limit por IP, limite de execucoes simultaneas, timeout com kill,
limites de stream e bloqueio de egress do robo (defesa em profundidade).
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import catalog, demo_servers, engine, jobs, ratelimit, samples, streaming, uploads
from .config import settings

_CLEANUP_INTERVAL_S = 300
_HTTP_ACCEPTED = 202
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

_background_tasks: set[asyncio.Task[None]] = set()

#: Extensoes aceitas por tipo de upload do catalogo. Tipos ausentes
#: (ex. "folder") caem na allowlist geral de settings.
_UPLOAD_EXTS: dict[str, tuple[str, ...]] = {
    "csv": (".csv",),
    "spreadsheet": (".csv", ".xlsx"),
}


def _browser_available() -> bool:
    """True se o Playwright/Chromium esta instalado (RPA e scraping-JS)."""
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


async def _cleanup_loop() -> None:
    """Varre e apaga workspaces e jobs expirados periodicamente."""
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL_S)
        with contextlib.suppress(Exception):
            engine.sweep_expired()
            jobs.sweep_expired(settings.workspace_ttl_min)


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
    """Saude do servico, limites ativos e estado dos mocks."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "browser_available": _browser_available(),
        "active_automations": list(engine.ACTIVE_AUTOMATIONS),
        "active_runs": jobs.active_count(),
        "limits": {
            "max_concurrent_runs": settings.max_concurrent_runs,
            "max_stream_lines": settings.max_stream_lines,
            "max_stream_bytes": settings.max_stream_bytes,
            "rate_limit_per_min": settings.rate_limit_per_min,
            "run_timeout_s": settings.run_timeout_s,
            "egress_lockdown": settings.egress_lockdown,
        },
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


async def _safe_run(automation_id: str, inputs: list[Path], job: jobs.Job) -> None:
    """Executa o job protegendo o registry de excecoes inesperadas."""
    try:
        await engine.run_streaming(automation_id, inputs, job)
    except Exception:  # noqa: BLE001
        job.status = "error"
        job.result = engine.RunResult(
            token=job.token,
            outcome="error",
            exit_code=-1,
            duration_ms=0,
            stdout="falha ao executar a automacao",
            artifacts=[],
        )
        job.queue.put_nowait(None)


def _precheck(automation_id: str, request: Request) -> JSONResponse | None:
    """Valida pre-condicoes: rate limit, catalogo, automacao ativa e concorrencia."""
    if not ratelimit.limiter.allow(ratelimit.client_ip(request)):
        return JSONResponse({"detail": "muitas requisicoes, aguarde um momento"}, status_code=429)
    item = catalog.get(automation_id)
    if item is None:
        return JSONResponse({"detail": "automacao desconhecida"}, status_code=404)
    if automation_id not in engine.ACTIVE_AUTOMATIONS:
        return JSONResponse({"detail": "automacao ainda nao disponivel ao vivo"}, status_code=501)
    if jobs.active_count() >= settings.max_concurrent_runs:
        return JSONResponse({"detail": "servidor ocupado, tente em instantes"}, status_code=429)
    return None


@app.post("/api/run/{automation_id}")
async def run_automation(
    automation_id: str,
    request: Request,
    files: list[UploadFile] = File(default=[]),  # noqa: B008
    use_sample: bool = False,
) -> JSONResponse:
    """Inicia uma execucao real e devolve o token + URL do stream (fase 1)."""
    rejection = _precheck(automation_id, request)
    if rejection is not None:
        return rejection

    item = catalog.get(automation_id)
    if item is None:  # ja validado em _precheck; redundancia para o type checker
        return JSONResponse({"detail": "automacao desconhecida"}, status_code=404)

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
                    files, workspace / "in", allowed_exts=_UPLOAD_EXTS.get(item.upload)
                )
    except uploads.UploadError as exc:
        shutil.rmtree(workspace, ignore_errors=True)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    job = jobs.create(token, automation_id, workspace)
    task = asyncio.create_task(_safe_run(automation_id, inputs, job))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return JSONResponse({"token": token, "stream_url": f"/api/stream/{token}", "status": "running"})


@app.get("/api/stream/{token}")
async def stream(token: str) -> Response:
    """Transmite o stdout ao vivo por SSE (fase 2)."""
    job = jobs.get(token)
    if job is None:
        return JSONResponse({"detail": "execucao nao encontrada"}, status_code=404)
    return StreamingResponse(
        streaming.sse_events(job), media_type="text/event-stream", headers=_SSE_HEADERS
    )


@app.get("/api/result/{token}")
def result(token: str) -> JSONResponse:
    """Resultado consolidado; 202 enquanto ainda executa."""
    job = jobs.get(token)
    if job is None:
        return JSONResponse({"detail": "execucao nao encontrada"}, status_code=404)
    if job.result is None:
        return JSONResponse({"token": token, "status": "running"}, status_code=_HTTP_ACCEPTED)
    return JSONResponse(job.result.as_dict())


@app.get("/api/download/{token}/{name}")
def download(token: str, name: str) -> Response:
    """Baixa um artefato gerado, restrito ao out/ do workspace (anti-traversal)."""
    path = engine.resolve_artifact(token, name)
    if path is None:
        return JSONResponse({"detail": "arquivo nao encontrado"}, status_code=404)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


# Front-end buildado (Vite) - montado automaticamente quando existir (Fase 2/deploy).
_frontend_dist = settings.repo_root / "live_demo" / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
