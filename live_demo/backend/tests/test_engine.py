"""Testes do motor de execucao (Live-1.2), isolados da suite principal.

Cobrem o fluxo real upload/exemplo -> workspace -> AutoTarefas -> artefatos ->
download, alem dos caminhos de seguranca (id invalido, automacao inativa,
extensao proibida, path traversal). As automacoes de extracao (rede) ficam no
roteiro de validacao manual.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterator

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


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_catalog_e_health(client: TestClient) -> None:
    catalog = client.get("/api/catalog").json()
    assert len(catalog["categories"]) == 7
    assert len(catalog["automations"]) == 13

    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert set(health["active_automations"]) == set(engine.ACTIVE_AUTOMATIONS)


def test_validate_sample_caught_issue(client: TestClient) -> None:
    resp = client.post("/api/run/validate", params={"use_sample": "true"})
    assert resp.status_code == HTTP_OK, resp.text
    body = resp.json()
    assert body["outcome"] == "caught_issue"
    assert body["exit_code"] == VALIDATE_FAIL_EXIT
    names = [a["name"] for a in body["artifacts"]]
    assert "validate_report.json" in names

    url = next(a["download_url"] for a in body["artifacts"] if a["name"] == "validate_report.json")
    download = client.get(url)
    assert download.status_code == HTTP_OK
    assert download.content


def test_backup_sample_zip(client: TestClient) -> None:
    resp = client.post("/api/run/backup", params={"use_sample": "true"})
    assert resp.status_code == HTTP_OK, resp.text
    body = resp.json()
    assert body["outcome"] == "ok"
    assert "backup.zip" in [a["name"] for a in body["artifacts"]]


def test_organize_sample_zip(client: TestClient) -> None:
    resp = client.post("/api/run/organize", params={"use_sample": "true"})
    assert resp.status_code == HTTP_OK, resp.text
    body = resp.json()
    assert body["outcome"] == "ok"
    assert "organizado.zip" in [a["name"] for a in body["artifacts"]]


def test_run_desconhecida_404(client: TestClient) -> None:
    assert client.post("/api/run/naoexiste").status_code == HTTP_NOT_FOUND


def test_run_nao_ativa_501(client: TestClient) -> None:
    # send_api existe no catalogo, mas nao esta ativa na Live-1.2
    assert client.post("/api/run/send_api").status_code == HTTP_NOT_IMPLEMENTED


def test_upload_extensao_proibida(client: TestClient) -> None:
    files = {"files": ("malicioso.exe", b"MZ", "application/octet-stream")}
    resp = client.post("/api/run/validate", files=files)
    assert resp.status_code == HTTP_UNSUPPORTED_MEDIA, resp.text


def test_resolve_artifact_barra_traversal() -> None:
    assert engine.resolve_artifact("naoehex", "x") is None
    assert engine.resolve_artifact("a" * 32, "../secret") is None
    assert engine.resolve_artifact("a" * 32, "naoexiste.csv") is None
