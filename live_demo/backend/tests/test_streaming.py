"""Testes de seguranca da Live-1.3: rate limit, concorrencia, egress e endpoints.

Mantidos isolados e deterministicos: o rate limit e testado na unidade (com
limite proprio) e a concorrencia injetando jobs no registry, sem depender de
temporizacao real.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from live_demo.backend.app import engine, jobs
from live_demo.backend.app.config import settings
from live_demo.backend.app.main import app
from live_demo.backend.app.ratelimit import RateLimiter

warnings.filterwarnings("ignore")

HTTP_NOT_FOUND = 404
HTTP_TOO_MANY = 429
RATE_LIMIT = 3


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_rate_limiter_janela() -> None:
    limiter = RateLimiter(limit=RATE_LIMIT, window=60.0)
    assert all(limiter.allow("ip-a") for _ in range(RATE_LIMIT))
    assert limiter.allow("ip-a") is False
    # uma chave diferente nao e afetada pelo limite da outra
    assert limiter.allow("ip-b") is True


def test_concorrencia_429(client: TestClient) -> None:
    fakes = [f"{i:032x}" for i in range(settings.max_concurrent_runs)]
    for token in fakes:
        jobs._jobs[token] = jobs.Job(
            token=token,
            automation_id="validate",
            workspace=Path("/tmp/ws"),  # noqa: S108
        )
    try:
        resp = client.post("/api/run/validate", params={"use_sample": "true"})
        assert resp.status_code == HTTP_TOO_MANY
    finally:
        for token in fakes:
            jobs._jobs.pop(token, None)


def test_stream_token_inexistente_404(client: TestClient) -> None:
    assert client.get("/api/stream/naoexiste").status_code == HTTP_NOT_FOUND


def test_result_token_inexistente_404(client: TestClient) -> None:
    assert client.get("/api/result/naoexiste").status_code == HTTP_NOT_FOUND


def test_egress_env_lockdown() -> None:
    env = engine._env_for(Path("/tmp/ws"))  # noqa: S108
    assert env["HTTP_PROXY"] == "http://127.0.0.1:9"
    assert env["HTTPS_PROXY"] == "http://127.0.0.1:9"
    assert "127.0.0.1" in env["NO_PROXY"]
