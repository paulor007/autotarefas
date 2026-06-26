"""Motor de execucao: workspace efemero -> AutoTarefas real -> artefatos.

Sandbox seguro: cada execucao roda num diretorio uuid isolado, com
AUTOTAREFAS_HOME proprio, comando montado por receita (sem shell, sem entrada
do usuario como argumento), timeout, e coleta de artefatos com sha256.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess  # nosec B404
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import recipes, sanitize
from .config import settings

# So estas automacoes executam ao vivo na Live-1.2.
ACTIVE_AUTOMATIONS: tuple[str, ...] = (
    "validate",
    "backup",
    "organize",
    "extract_web",
    "extract_api",
)

_TIMEOUT_EXIT = 124
_VALIDATE_FAIL_EXIT = 1
_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")


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
    """Resultado de uma execucao real."""

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


def run(automation_id: str, inputs: list[Path], token: str, workspace: Path) -> RunResult:
    """Executa a automacao curada de verdade e devolve o resultado sanitizado."""
    argv = recipes.build_argv(automation_id, workspace, inputs)
    start = time.monotonic()
    timed_out = False
    try:
        # Comando montado por receita (allowlist), sem shell nem entrada do usuario como argumento.
        proc = subprocess.run(  # nosec B603  # noqa: S603
            argv,
            cwd=str(workspace),
            env=_env_for(workspace),
            capture_output=True,
            text=True,
            timeout=settings.run_timeout_s,
            check=False,
        )
        exit_code = proc.returncode
        raw = (proc.stdout or "") + (f"\n{proc.stderr}" if proc.stderr else "")
    except subprocess.TimeoutExpired as exc:
        exit_code = _TIMEOUT_EXIT
        raw = exc.stdout if isinstance(exc.stdout, str) else ""
        timed_out = True

    duration_ms = int((time.monotonic() - start) * 1000)

    if not timed_out and exit_code == 0:
        _postprocess(automation_id, workspace)

    artifacts = _collect(workspace / "out")
    stdout = sanitize.sanitize(raw, workspace, settings.repo_root)
    outcome = "timeout" if timed_out else _outcome(automation_id, exit_code)

    return RunResult(
        token=token,
        outcome=outcome,
        exit_code=exit_code,
        duration_ms=duration_ms,
        stdout=stdout,
        artifacts=artifacts,
    )


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
