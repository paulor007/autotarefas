"""
Peças compartilhadas pelos testes E2E que precisam do servidor demo.

O `test_extract_web_js_e2e.py` inaugurou este molde — servidor Flask numa porta
livre, em thread, com readiness por polling no `/health`. Quando o segundo
arquivo passou a precisar da mesma coisa (o RPA de cadastro), a fixture subiu
para cá em vez de virar cópia.

Nota de estado: aquele arquivo ainda traz a própria cópia da fixture, e ela
vence a daqui por proximidade. Não foi removida de propósito — ele é a
evidência **[C1]** do RF-WEB-002, recém-registrada, e mexer nele no mesmo
movimento em que se usa o seu resultado como prova é pedir para a evidência
ficar difícil de conferir. A limpeza é um `git rm` de trinta linhas, para
depois.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

import httpx
import pytest
from werkzeug.serving import make_server

if TYPE_CHECKING:
    from collections.abc import Generator

# Quanto tempo esperamos o servidor responder antes de desistir.
_TENTATIVAS = 100
_INTERVALO_S = 0.05


def esperar_online(base_url: str) -> None:
    """
    Aguarda o servidor responder ao `/health`.

    Readiness por polling curto, e não um sleep fixo: volta assim que o
    servidor responde 200, ou levanta se ele não subir dentro do limite. Um
    sleep fixo seria lento quando o servidor sobe rápido e frágil quando a
    máquina está carregada — os dois defeitos ao mesmo tempo.
    """
    ultimo_erro: Exception | None = None
    for _ in range(_TENTATIVAS):
        try:
            if httpx.get(f"{base_url}/health", timeout=0.2).status_code == 200:
                return
        except httpx.HTTPError as exc:  # ainda subindo
            ultimo_erro = exc
            time.sleep(_INTERVALO_S)
    msg = f"servidor demo nao respondeu a tempo: {ultimo_erro}"
    raise RuntimeError(msg)


@pytest.fixture(scope="module")
def servidor_demo() -> Generator[str, None, None]:
    """
    Sobe o servidor demo (Flask) numa porta livre, em thread, e devolve a URL
    base. Sem dependência nova (`werkzeug.make_server`). Encerra no fim.

    Porta 0 deixa o sistema escolher: dois arquivos de teste rodando na mesma
    máquina não brigam por um número fixo.
    """
    from tools.demo_server.app import app

    app.config["TESTING"] = True
    servidor = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{servidor.server_port}"
    try:
        esperar_online(base_url)
        yield base_url
    finally:
        servidor.shutdown()
        thread.join(timeout=5)
