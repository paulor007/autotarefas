"""Testes do motor de execucao (Live-1.3), isolados da suite principal.

Cobrem o fluxo real em duas fases: POST inicia o job -> SSE transmite o stdout ->
evento final com artefatos -> download. Mais os caminhos de seguranca (id
invalido, automacao inativa, extensao proibida, path traversal). As automacoes
de extracao (rede) ficam no roteiro de validacao manual.
"""

from __future__ import annotations

import json
import re
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from live_demo.backend.app import engine, recipes
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
    assert len(health["active_automations"]) == 7
    assert health["limits"]["max_concurrent_runs"] == 4
    assert health["limits"]["egress_lockdown"] is True


def test_validate_stream_caught_issue(client: TestClient) -> None:
    result = _run_and_collect(client, "validate", use_sample="true")
    assert result["outcome"] == "caught_issue"
    assert result["exit_code"] == VALIDATE_FAIL_EXIT
    names = [a["name"] for a in result["artifacts"]]
    # Auditoria de planilha gera os 4 artefatos no out/
    assert "validacao_report.json" in names
    assert "planilha_validada.xlsx" in names
    assert "registros_validos.csv" in names
    assert "registros_invalidos.csv" in names


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
    # send_email existe no catalogo, mas ainda nao esta disponivel ao vivo
    assert client.post("/api/run/send_email").status_code == HTTP_NOT_IMPLEMENTED


def test_upload_extensao_proibida(client: TestClient) -> None:
    files = {"files": ("malicioso.exe", b"MZ", "application/octet-stream")}
    resp = client.post("/api/run/validate", files=files)
    assert resp.status_code == HTTP_UNSUPPORTED_MEDIA, resp.text


def test_resolve_artifact_barra_traversal() -> None:
    assert engine.resolve_artifact("naoehex", "x") is None
    assert engine.resolve_artifact("a" * 32, "../secret") is None
    assert engine.resolve_artifact("a" * 32, "naoexiste.csv") is None


def test_recipe_extract_api_argv(tmp_path: Path) -> None:
    argv = recipes.build_argv("extract_api", tmp_path, [])
    assert "extract" in argv
    assert "api" in argv
    assert any("/api/catalogo" in part for part in argv)
    assert "--out-dir" in argv
    assert any(part.endswith("out") for part in argv)


def test_recipe_send_api_argv(tmp_path: Path) -> None:
    argv = recipes.build_argv("send_api", tmp_path, [tmp_path / "in" / "leads.csv"])
    assert "send" in argv
    assert "api" in argv
    assert any("/api/clientes" in part for part in argv)
    assert "--out-dir" in argv
    assert any(part.endswith("out") for part in argv)


def test_reset_url_send_api() -> None:
    url = recipes.reset_url("send_api")
    assert url is not None
    assert url.endswith("/limpar")
    assert recipes.reset_url("validate") is None


def test_recipe_send_telegram_argv(tmp_path: Path) -> None:
    argv = recipes.build_argv("send_telegram", tmp_path, [])
    assert "send" in argv
    assert "telegram" in argv
    assert "--base-url" in argv
    assert any("contatos_demo.csv" in part for part in argv)
    assert any(part.endswith("send_telegram_report.json") for part in argv)


def test_recipe_validate_argv(tmp_path: Path) -> None:
    argv = recipes.build_argv("validate", tmp_path, [tmp_path / "in" / "clientes.csv"])
    assert "validate" in argv
    assert "--mode" in argv
    assert "limpeza" in argv
    assert "--out-dir" in argv
    assert any(part.endswith("out") for part in argv)


def test_catalogo_validate_reposicionado(client: TestClient) -> None:
    catalog = client.get("/api/catalog").json()
    validate = next(a for a in catalog["automations"] if a["id"] == "validate")
    assert validate["title"] == "Auditoria de planilha"
    assert validate["upload"] == "spreadsheet"
    assert ".xlsx" in validate["upload_hint"]


def test_upload_xlsx_roda_auditoria(client: TestClient) -> None:
    """Planilha .xlsx do visitante roda de ponta a ponta (upload liberado)."""
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["nome", "email", "telefone", "cpf", "idade"])
    ws.append(["Ana Lima", "ana.lima@example.com", "(11) 98765-4321", "104.332.181-00", 34])
    buffer = io.BytesIO()
    wb.save(buffer)

    files = {
        "files": (
            "minha_planilha.xlsx",
            buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    started = client.post("/api/run/validate", files=files)
    assert started.status_code == HTTP_OK, started.text
    token = started.json()["token"]

    with client.stream("GET", f"/api/stream/{token}") as response:
        lines = list(response.iter_lines())
    for index, line in enumerate(lines):
        if line.startswith("event: done"):
            result = json.loads(lines[index + 1][len(DATA_PREFIX) :])
            break
    else:
        pytest.fail("stream sem evento final")

    # planilha limpa: exit 0 e os 4 artefatos gerados
    assert result["outcome"] == "ok"
    names = [a["name"] for a in result["artifacts"]]
    assert "validacao_report.json" in names
    assert "planilha_validada.xlsx" in names


def test_catalogo_send_api_reposicionado(client: TestClient) -> None:
    catalog = client.get("/api/catalog").json()
    send = next(a for a in catalog["automations"] if a["id"] == "send_api")
    assert send["title"] == "Cadastro automático via planilha"
    assert send["upload"] == "spreadsheet"
    assert "Auditoria" in send["upload_hint"]


@pytest.fixture(scope="module")
def demo_crm() -> Iterator[None]:
    """
    Sobe o CRM de demonstracao (tools.demo_server) na porta primaria.

    Os E2E do send_api conversam com o mock DE VERDADE (validacao, 409,
    429 com Retry-After, idempotencia). O conftest desliga o autostart
    (DEMO_SERVERS_AUTOSTART=0), entao esta fixture sobe o servidor so
    para os testes que precisam dele.
    """
    import subprocess
    import sys
    import time as time_module

    import httpx

    from live_demo.backend.app.config import settings

    port = settings.demo_primary_port
    proc = subprocess.Popen(
        [sys.executable, "-m", "tools.demo_server.app"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(30):
            try:
                if httpx.get(f"{base}/health", timeout=1.0).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time_module.sleep(0.5)
        else:
            pytest.fail("demo_server nao subiu para os testes E2E do send_api")
        yield
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def _baixar_report(client: TestClient, result: dict[str, Any]) -> dict[str, Any]:
    art = next(a for a in result["artifacts"] if a["name"] == "importacao_report.json")
    report: dict[str, Any] = client.get(art["download_url"]).json()
    return report


@pytest.mark.usefixtures("demo_crm")
def test_send_api_stream_gera_artefatos(client: TestClient) -> None:
    result = _run_and_collect(client, "send_api", use_sample="true")
    # 2 falhas propositais no sample -> envio PARCIAL (exit 0 / outcome ok)
    assert result["outcome"] == "ok"
    names = sorted(a["name"] for a in result["artifacts"])
    assert names == [
        "importacao_report.json",
        "importacao_resultado.xlsx",
        "registros_enviados.csv",
        "registros_falhos.csv",
    ]
    report = _baixar_report(client, result)
    assert report["total"] == 8
    assert report["enviados"] == 6
    assert report["falhas"] == 2
    assert report["falhas_por_categoria"] == {"validacao": 1, "duplicado": 1}
    # o registro "instavel" recuperou no retry (2 tentativas)
    instavel = next(i for i in report["items"] if i["linha"] == 6)
    assert instavel["sucesso"] is True
    assert instavel["tentativas"] == 2


@pytest.mark.usefixtures("demo_crm")
def test_send_api_duas_execucoes_consistentes(client: TestClient) -> None:
    """O reset automatico impede a demo de degradar (409 em cascata)."""
    primeira = _baixar_report(client, _run_and_collect(client, "send_api", use_sample="true"))
    segunda = _baixar_report(client, _run_and_collect(client, "send_api", use_sample="true"))
    assert (primeira["enviados"], primeira["falhas"]) == (6, 2)
    assert (segunda["enviados"], segunda["falhas"]) == (6, 2)


def test_catalogo_extract_api_reposicionado(client: TestClient) -> None:
    catalog = client.get("/api/catalog").json()
    extract = next(a for a in catalog["automations"] if a["id"] == "extract_api")
    assert extract["title"] == "Exportação automática de dados"
    assert extract["output"] == "report"
    # sem upload -> o catalogo descreve a ORIGEM dos dados para o visitante
    assert extract["upload"] == "none"
    assert extract["upload_hint"]  # explicacao da demo (nao vazia)
    assert extract["source_label"] == "Catálogo empresarial simulado"
    assert "API interna segura" in extract["source_detail"]


@pytest.mark.usefixtures("demo_crm")
def test_extract_api_stream_gera_artefatos(client: TestClient) -> None:
    result = _run_and_collect(client, "extract_api", use_sample="true")
    assert result["outcome"] == "ok"
    names = sorted(a["name"] for a in result["artifacts"])
    assert names == [
        "dados_extraidos.csv",
        "dados_extraidos.xlsx",
        "extracao_report.json",
    ]
    art = next(a for a in result["artifacts"] if a["name"] == "extracao_report.json")
    report = client.get(art["download_url"]).json()
    # dataset-semente fixo: 47 produtos em 5 paginas (per_page=10)
    assert report["total_registros"] == 47
    assert report["paginas"] == 5


@pytest.mark.usefixtures("demo_crm")
def test_extract_api_independente_do_cadastro(client: TestClient) -> None:
    """A Exportacao usa dataset proprio: nao e afetada pelo reset do Cadastro."""
    # roda o Cadastro (que reseta o storage de clientes)...
    _run_and_collect(client, "send_api", use_sample="true")
    # ...e a Exportacao continua trazendo os 47 produtos do catalogo fixo
    result = _run_and_collect(client, "extract_api", use_sample="true")
    art = next(a for a in result["artifacts"] if a["name"] == "extracao_report.json")
    report = client.get(art["download_url"]).json()
    assert report["total_registros"] == 47


@pytest.mark.usefixtures("demo_crm")
def test_origem_da_demo_bate_com_a_extracao_real(client: TestClient) -> None:
    """
    Guarda anti-deriva: os numeros que o catalogo PROMETE ao visitante
    ("47 produtos - 5 paginas") tem que ser os que a execucao ENTREGA.
    Se o dataset do mock mudar, este teste quebra junto.
    """
    catalog = client.get("/api/catalog").json()
    extract = next(a for a in catalog["automations"] if a["id"] == "extract_api")
    prometidos = [int(n) for n in re.findall(r"\d+", extract["source_detail"])]

    result = _run_and_collect(client, "extract_api", use_sample="true")
    art = next(a for a in result["artifacts"] if a["name"] == "extracao_report.json")
    report = client.get(art["download_url"]).json()

    assert prometidos == [report["total_registros"], report["paginas"]]
