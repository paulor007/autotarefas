"""Motor de execucao: workspace efemero -> AutoTarefas real -> artefatos.

Live-1.3: execucao assincrona com stdout transmitido linha a linha (SSE). Cada
execucao roda num diretorio uuid isolado, com AUTOTAREFAS_HOME proprio, comando
montado por receita (sem shell, sem entrada do usuario como argumento), timeout
com kill, limites de stream e bloqueio de egress (defesa em profundidade).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import subprocess  # nosec B404
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from . import recipes, sanitize
from .config import settings

if TYPE_CHECKING:
    from .jobs import Job

# So estas automacoes executam ao vivo (mantidas da Live-1.2).
ACTIVE_AUTOMATIONS: tuple[str, ...] = (
    "validate",
    "backup",
    "organize",
    "extract_web",
    "extract_api",
    "send_api",
    "send_telegram",
)

_TIMEOUT_EXIT = 124
_VALIDATE_FAIL_EXIT = 1
_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
_DEAD_PROXY = "http://127.0.0.1:9"


@dataclass
class Artifact:
    """Arquivo gerado por uma execucao."""

    name: str
    bytes: int
    sha256: str

    def as_dict(self, token: str) -> dict[str, Any]:
        return {
            "name": self.name,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "download_url": f"/api/download/{token}/{self.name}",
        }


@dataclass
class RunResult:
    """Resultado consolidado de uma execucao real."""

    token: str
    outcome: str
    exit_code: int
    duration_ms: int
    stdout: str
    artifacts: list[Artifact] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "outcome": self.outcome,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "stdout": self.stdout,
            "artifacts": [a.as_dict(self.token) for a in self.artifacts],
        }


class WorkspaceFull(Exception):
    """Limite de workspaces simultaneos atingido (vira 503)."""


def _root() -> Path:
    settings.workspaces_root.mkdir(parents=True, exist_ok=True)
    return settings.workspaces_root


def _count_workspaces() -> int:
    return sum(1 for p in _root().iterdir() if p.is_dir())


def create_workspace() -> tuple[str, Path]:
    """Cria um workspace efemero (in/out/home). Retorna (token, caminho)."""
    if _count_workspaces() >= settings.max_workspaces:
        raise WorkspaceFull
    token = uuid.uuid4().hex
    workspace = _root() / token
    for sub in ("in", "out", "home"):
        (workspace / sub).mkdir(parents=True, exist_ok=True)
    return token, workspace


def _env_for(workspace: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "AUTOTAREFAS_HOME": str(workspace / "home"),
            "ENVIRONMENT": "demo",
            "NO_COLOR": "1",
            "PYTHONUNBUFFERED": "1",
            # Token fake do bot: usado so contra o mock local; evita prompt que travaria o processo.
            "AUTOTAREFAS_TELEGRAM_TOKEN": "demo-fake-token-0000",  # nosec B105
        }
    )
    if settings.egress_lockdown:
        # Defesa em profundidade: o robo so fala com mocks locais; saida externa morre.
        env.update(
            {
                "HTTP_PROXY": _DEAD_PROXY,
                "HTTPS_PROXY": _DEAD_PROXY,
                "http_proxy": _DEAD_PROXY,
                "https_proxy": _DEAD_PROXY,
                "NO_PROXY": "127.0.0.1,localhost",
                "no_proxy": "127.0.0.1,localhost",
            }
        )
    return env


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect(out_dir: Path) -> list[Artifact]:
    artifacts: list[Artifact] = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file():
            artifacts.append(
                Artifact(name=path.name, bytes=path.stat().st_size, sha256=_sha256(path))
            )
    return artifacts


def _postprocess(automation_id: str, workspace: Path) -> None:
    """Empacota o resultado quando a automacao gera uma pasta (organize)."""
    if automation_id != "organize":
        return
    organized = workspace / "out" / "organizado"
    if organized.is_dir():
        shutil.make_archive(str(workspace / "out" / "organizado"), "zip", root_dir=str(organized))
        shutil.rmtree(organized, ignore_errors=True)


def _outcome(automation_id: str, exit_code: int) -> str:
    if exit_code == 0:
        return "ok"
    if automation_id == "validate" and exit_code == _VALIDATE_FAIL_EXIT:
        return "caught_issue"
    return "error"


def _start_process(argv: list[str], workspace: Path) -> subprocess.Popen[str]:
    # Comando montado por receita (allowlist), sem shell nem entrada do usuario como argumento.
    return subprocess.Popen(  # nosec B603  # noqa: S603
        argv,
        cwd=str(workspace),
        env=_env_for(workspace),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def _pump(
    proc: subprocess.Popen[str],
    job: Job,
    loop: asyncio.AbstractEventLoop,
    done: asyncio.Event,
) -> None:
    """Le o stdout do processo (em thread) e enfileira as linhas sanitizadas."""
    stdout = proc.stdout
    if stdout is None:
        loop.call_soon_threadsafe(done.set)
        return
    streamed_bytes = 0
    truncated = False
    try:
        for raw in stdout:
            line = sanitize.sanitize(raw, job.workspace, settings.repo_root)
            if not line:
                continue
            if (
                len(job.lines) >= settings.max_stream_lines
                or streamed_bytes >= settings.max_stream_bytes
            ):
                if not truncated:
                    truncated = True
                    warn = "... saida truncada (limite de stream atingido) ..."
                    job.lines.append(warn)
                    loop.call_soon_threadsafe(job.queue.put_nowait, warn)
                continue
            streamed_bytes += len(line)
            job.lines.append(line)
            loop.call_soon_threadsafe(job.queue.put_nowait, line)
    finally:
        stdout.close()
        loop.call_soon_threadsafe(done.set)


async def _reset_demo_state(url: str) -> None:
    """
    Pre-hook: zera o estado do sistema de demonstracao antes da execucao.

    Sem isso, a demo degrada sozinha (cadastros da execucao anterior
    respondem 409 em cascata). Falha do reset nao derruba a execucao —
    se o mock estiver fora do ar, o proprio run reportara o erro real.
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(url)
    except httpx.HTTPError:
        pass  # nosec B110 - reset e melhor-esforco; o run reporta erros reais


async def run_streaming(automation_id: str, inputs: list[Path], job: Job) -> RunResult:
    """Executa a automacao de verdade, transmitindo o stdout linha a linha."""
    reset = recipes.reset_url(automation_id)
    if reset is not None:
        await _reset_demo_state(reset)

    argv = recipes.build_argv(automation_id, job.workspace, inputs)
    loop = asyncio.get_running_loop()
    start = time.monotonic()
    timed_out = False

    proc = _start_process(argv, job.workspace)
    done = asyncio.Event()
    reader = threading.Thread(target=_pump, args=(proc, job, loop, done), daemon=True)
    reader.start()

    try:
        await asyncio.wait_for(done.wait(), timeout=settings.run_timeout_s)
    except TimeoutError:
        timed_out = True
        proc.kill()

    await loop.run_in_executor(None, proc.wait)
    exit_code = _TIMEOUT_EXIT if timed_out else (proc.returncode or 0)
    duration_ms = int((time.monotonic() - start) * 1000)

    if not timed_out and exit_code == 0:
        _postprocess(automation_id, job.workspace)

    artifacts = _collect(job.workspace / "out")
    outcome = "timeout" if timed_out else _outcome(automation_id, exit_code)
    result = RunResult(
        token=job.token,
        outcome=outcome,
        exit_code=exit_code,
        duration_ms=duration_ms,
        stdout="\n".join(job.lines),
        artifacts=artifacts,
    )
    job.result = result
    job.status = outcome
    job.queue.put_nowait(None)
    return result


def resolve_artifact(token: str, name: str) -> Path | None:
    """Resolve o caminho de um artefato, barrando path traversal. None se invalido."""
    if not _TOKEN_RE.match(token):
        return None
    safe = Path(name).name
    if safe != name or safe in {"", ".", ".."}:
        return None
    out_dir = (_root() / token / "out").resolve()
    candidate = (out_dir / safe).resolve()
    if not candidate.is_relative_to(out_dir) or not candidate.is_file():
        return None
    return candidate


def sweep_expired() -> int:
    """Apaga workspaces mais velhos que o TTL. Retorna quantos removeu."""
    ttl_seconds = settings.workspace_ttl_min * 60
    now = time.time()
    removed = 0
    for path in list(_root().iterdir()):
        if not path.is_dir():
            continue
        try:
            age = now - path.stat().st_mtime
        except OSError:
            continue
        if age > ttl_seconds:
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed
