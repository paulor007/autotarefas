"""Sobe e derruba os servidores de demonstracao (mocks Flask) das automacoes.

Os mocks rodam em localhost, dentro do mesmo container. O robo so conversa com
eles - nunca com a internet aberta (a allowlist de rede entra na Live-3). Aqui
no esqueleto subimos o mock primario (catalogo / clientes / telegram); o destino
do sync e o SMTP de teste entram na Live-2 junto com a execucao real.
"""

from __future__ import annotations

import http.client
import subprocess  # nosec B404
import sys
import time
from dataclasses import dataclass
from typing import Any

from .config import settings

_HTTP_OK: int = 200
_HEALTH_REQUEST_TIMEOUT_SECONDS: float = 1.0
_HEALTH_RETRY_SECONDS: float = 0.4


@dataclass
class DemoServer:
    """Handle de um mock em execucao."""

    name: str
    port: int
    process: subprocess.Popen[bytes] | None = None


_servers: list[DemoServer] = []


def _wait_health(port: int, timeout: float = 15.0) -> bool:
    """Aguarda o /health do mock responder 200 em HTTP local fixo."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        conn: http.client.HTTPConnection | None = None
        try:
            conn = http.client.HTTPConnection(
                "127.0.0.1",
                port,
                timeout=_HEALTH_REQUEST_TIMEOUT_SECONDS,
            )
            conn.request("GET", "/health")
            response = conn.getresponse()
            response.read()

            if response.status == _HTTP_OK:
                return True
        except (OSError, http.client.HTTPException):
            pass
        finally:
            if conn is not None:
                conn.close()

        time.sleep(_HEALTH_RETRY_SECONDS)

    return False


def start() -> list[DemoServer]:
    """Sobe o mock primario. Idempotente e respeita DEMO_SERVERS_AUTOSTART."""
    if not settings.autostart_demo_servers:
        return []
    if _servers:
        return _servers

    command = [sys.executable, "-m", "tools.demo_server"]
    # Bandit/Ruff: sobe apenas o mock local controlado, shell=False.
    process = subprocess.Popen(  # noqa: S603  # nosec B603
        command,
        cwd=str(settings.repo_root),
    )
    server = DemoServer(name="demo-primary", port=settings.demo_primary_port, process=process)
    _servers.append(server)
    _wait_health(server.port)
    return _servers


def status() -> list[dict[str, Any]]:
    """Estado atual dos mocks (para o /api/health)."""
    result: list[dict[str, Any]] = []
    for server in _servers:
        alive = server.process is not None and server.process.poll() is None
        result.append({"name": server.name, "port": server.port, "alive": alive})
    return result


def stop() -> None:
    """Encerra os mocks no shutdown."""
    for server in _servers:
        if server.process and server.process.poll() is None:
            server.process.terminate()
            try:
                server.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.process.kill()
    _servers.clear()
