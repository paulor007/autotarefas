"""Sobe e derruba os servidores de demonstracao (mocks Flask) das automacoes.

Os mocks rodam em localhost, dentro do mesmo container. O robo so conversa com
eles - nunca com a internet aberta. O health check usa http.client direto contra
127.0.0.1:<porta>/health (sem urllib, para nao disparar B310 no Bandit).
"""

from __future__ import annotations

import http.client
import os
import socket
import subprocess  # nosec B404
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import settings

_HTTP_OK = 200


@dataclass
class DemoServer:
    """Handle de um mock em execucao."""

    name: str
    port: int
    process: subprocess.Popen[bytes] | None = None


_servers: list[DemoServer] = []


def _wait_health(port: int, timeout: float = 15.0) -> bool:
    """Aguarda o /health do mock responder 200, via http.client (host/porta locais)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        try:
            conn.request("GET", "/health")
            response = conn.getresponse()
            response.read()
            if response.status == _HTTP_OK:
                return True
        except OSError:
            time.sleep(0.4)
        finally:
            conn.close()
    return False


def _wait_tcp(port: int, timeout: float = 15.0) -> bool:
    """
    Aguarda uma porta aceitar conexao TCP.

    O mock de SMTP (aiosmtpd) nao tem `/health` HTTP — e um protocolo
    diferente. Um connect que fecha na hora ja confirma que o servidor
    esta escutando; nao precisamos falar SMTP de verdade so para checar.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.4)
    return False


def start() -> list[DemoServer]:
    """Sobe os mocks (Flask + SMTP). Idempotente e respeita DEMO_SERVERS_AUTOSTART."""
    if not settings.autostart_demo_servers:
        return []
    if _servers:
        return _servers

    # Comando fixo (python -m tools.demo_server), sem shell e sem entrada do usuario.
    primary_cmd = [sys.executable, "-m", "tools.demo_server"]
    primary_process = subprocess.Popen(  # nosec B603  # noqa: S603
        primary_cmd,
        cwd=str(settings.repo_root),
    )
    primary = DemoServer(
        name="demo-primary", port=settings.demo_primary_port, process=primary_process
    )
    _servers.append(primary)
    _wait_health(primary.port)

    # SMTP de debug (Notificacoes por e-mail). Instancia COMPARTILHADA entre
    # visitantes, como o mock Flask acima — por isso os .eml vao para o temp
    # do sistema, e nao para dentro do repositorio: um servidor de uso
    # comum nao pode escrever no diretorio de trabalho de quem o hospeda.
    save_dir = Path(tempfile.gettempdir()) / "autotarefas-demo-smtp"
    smtp_cmd = [sys.executable, "-m", "tools.smtp_debug"]
    smtp_process = subprocess.Popen(  # nosec B603  # noqa: S603
        smtp_cmd,
        cwd=str(settings.repo_root),
        env={
            **os.environ,
            "DEMO_SMTP_PORT": str(settings.smtp_port),
            "DEMO_SMTP_SAVE_DIR": str(save_dir),
        },
    )
    smtp = DemoServer(name="demo-smtp", port=settings.smtp_port, process=smtp_process)
    _servers.append(smtp)
    _wait_tcp(smtp.port)

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
