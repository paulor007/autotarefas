"""Testes do motor de execucao (Live-1.3), isolados da suite principal.

Cobrem o fluxo real em duas fases: POST inicia o job -> SSE transmite o stdout ->
evento final com artefatos -> download. Mais os caminhos de seguranca (id
invalido, automacao inativa, extensao proibida, path traversal). As automacoes
de extracao (rede) ficam no roteiro de validacao manual.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from live_demo.backend.app import engine
from live_demo.backend.app.main import app

warnings.filterwarnings("ignore")

HTTP_OK = 200
HTTP_NOT_FOUND = 404
HTTP_NOT_IMPLEMENTED = 501
HTTP_UNSUPPORTED_MEDIA = 415
VALIDATE_FAIL_EXIT = 1
DATA_PREFIX = "data: "


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _run_and_collect(client: TestClient, automation_id: str, **params: str) -> dict[str, Any]:
    """Inicia um job, consome o SSE ate o evento final e devolve o resultado."""
    started = client.post(f"/api/run/{automation_id}", params=params)
    assert started.status_code == HTTP_OK, started.text
    body = started.json()
    assert body["status"] == "running"
    assert body["stream_url"].endswith(body["token"])

    with client.stream("GET", f"/api/stream/{body['token']}") as response:
        assert response.status_code == HTTP_OK
        lines = list(response.iter_lines())

    for index, line in enumerate(lines):
        if line.startswith(("event: done", "event: timeout")):
            parsed: dict[str, Any] = json.loads(lines[index + 1][len(DATA_PREFIX) :])
            return parsed
    pytest.fail(f"stream sem evento final: {lines!r}")


def test_catalog_e_health(client: TestClient) -> None:
    catalog = client.get("/api/catalog").json()
    assert len(catalog["categories"]) == 7
    assert len(catalog["automations"]) == 13

    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert set(health["active_automations"]) == set(engine.ACTIVE_AUTOMATIONS)
    assert health["limits"]["max_concurrent_runs"] == 4
    assert health["limits"]["egress_lockdown"] is True


def test_validate_stream_caught_issue(client: TestClient) -> None:
    result = _run_and_collect(client, "validate", use_sample="true")
    assert result["outcome"] == "caught_issue"
    assert result["exit_code"] == VALIDATE_FAIL_EXIT
    assert "validate_report.json" in [a["name"] for a in result["artifacts"]]


def test_backup_stream_zip(client: TestClient) -> None:
    result = _run_and_collect(client, "backup", use_sample="true")
    assert result["outcome"] == "ok"
    assert "backup.zip" in [a["name"] for a in result["artifacts"]]


def test_organize_stream_zip(client: TestClient) -> None:
    result = _run_and_collect(client, "organize", use_sample="true")
    assert result["outcome"] == "ok"
    assert "organizado.zip" in [a["name"] for a in result["artifacts"]]


def test_download_apos_run(client: TestClient) -> None:
    result = _run_and_collect(client, "validate", use_sample="true")
    download = client.get(result["artifacts"][0]["download_url"])
    assert download.status_code == HTTP_OK
    assert download.content


def test_run_desconhecida_404(client: TestClient) -> None:
    assert client.post("/api/run/naoexiste").status_code == HTTP_NOT_FOUND


def test_run_nao_ativa_501(client: TestClient) -> None:
    # send_api existe no catalogo, mas nao esta ativa na Live-1.3
    assert client.post("/api/run/send_api").status_code == HTTP_NOT_IMPLEMENTED


def test_upload_extensao_proibida(client: TestClient) -> None:
    files = {"files": ("malicioso.exe", b"MZ", "application/octet-stream")}
    resp = client.post("/api/run/validate", files=files)
    assert resp.status_code == HTTP_UNSUPPORTED_MEDIA, resp.text


def test_resolve_artifact_barra_traversal() -> None:
    assert engine.resolve_artifact("naoehex", "x") is None
    assert engine.resolve_artifact("a" * 32, "../secret") is None
    assert engine.resolve_artifact("a" * 32, "naoexiste.csv") is None
