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
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.app import engine, recipes
from apps.api.app.main import app

warnings.filterwarnings("ignore")

HTTP_OK = 200

#: Tentativas de apagar o log temporario do demo_server (Windows libera o
#: handle com alguns milissegundos de atraso) e pausa entre elas.
_LOG_UNLINK_TRIES = 5
_LOG_UNLINK_DELAY_S = 0.1
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
    # Auditoria de planilha gera os 4 artefatos avulsos no out/...
    assert "validacao_report.json" in names
    assert "planilha_validada.xlsx" in names
    assert "registros_validos.csv" in names
    assert "registros_invalidos.csv" in names
    # ...e o pacote de evidencias da 1.7 como um unico .zip baixavel.
    assert "pacote_execucao.zip" in names


def test_validate_pacote_zip_tem_manifesto_e_schema_efetivo(client: TestClient) -> None:
    """
    O pacote de evidencias (1.7) chega ao visitante, com manifesto e schema.

    Vale mesmo com problemas (exit 1): e o caso em que as evidencias mais
    importam, e o pos-processamento tem que rodar assim mesmo.

    Comprova tambem que NAO ha procedencia inventada: o schema da demo e
    escrito a mao, entao `generated_from` fica ausente no manifesto e no
    relatorio. `generated_from` so existe em schema realmente gerado por
    `autotarefas perfis exportar`.
    """
    import io
    import zipfile

    result = _run_and_collect(client, "validate", use_sample="true")
    zip_art = next(a for a in result["artifacts"] if a["name"] == "pacote_execucao.zip")

    baixado = client.get(zip_art["download_url"])
    assert baixado.status_code == HTTP_OK

    pacote = zipfile.ZipFile(io.BytesIO(baixado.content))
    nomes = set(pacote.namelist())
    assert {
        "manifest.json",
        "schema_efetivo.yaml",
        "problemas.csv",
        "registros_validos.csv",
        "registros_para_revisao.csv",
    } <= nomes

    # o schema efetivo dentro do pacote tambem nao carrega procedencia falsa
    schema_efetivo = pacote.read("schema_efetivo.yaml").decode("utf-8")
    assert "generated_from" not in schema_efetivo
    assert "demo_clientes" not in schema_efetivo

    manifesto = json.loads(pacote.read("manifest.json"))
    # O schema da demo e MANUAL: nao foi exportado por perfil nenhum, entao
    # `generated_from` fica ausente. Procedencia so aparece quando existe de
    # verdade — um rotulo inventado seria pior que a ausencia.
    assert manifesto["configuration"]["generated_from"] is None
    # classificacao real, com as linhas de revisao contadas
    assert manifesto["result"]["review_rows"] >= 1

    # e o relatorio que o frontend consome tambem omite procedencia
    report_art = next(a for a in result["artifacts"] if a["name"] == "validacao_report.json")
    assert "generated_from" not in client.get(report_art["download_url"]).json()


def test_validate_report_json_omite_procedencia_de_schema_manual(
    client: TestClient,
) -> None:
    """
    O relatorio que o frontend consome nao inventa procedencia.

    O schema da demo e escrito a mao; `generated_from` existe apenas em
    schemas realmente gerados por `autotarefas perfis exportar`.
    """
    result = _run_and_collect(client, "validate", use_sample="true")
    report_art = next(a for a in result["artifacts"] if a["name"] == "validacao_report.json")
    report = client.get(report_art["download_url"]).json()
    assert "generated_from" not in report


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
    """
    O card descreve o que a ferramenta REALMENTE faz.

    O texto anterior dizia "Valida, limpa e separa": prometia limpeza, que o
    fluxo atual nao executa. O contrato e analisar, deixar a pessoa confirmar
    as regras, validar e separar — sem inventar regra de negocio.
    """
    catalog = client.get("/api/catalog").json()
    validate = next(a for a in catalog["automations"] if a["id"] == "validate")
    assert validate["title"] == "Análise e organização de planilhas"
    assert validate["upload"] == "spreadsheet"
    assert ".xlsx" in validate["upload_hint"]
    texto = f"{validate['subtitle']} {validate['description']}".lower()
    assert "limpa" not in texto
    assert "corrige" not in texto


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

    O `cwd` e obrigatorio: `tools.demo_server.app` e um modulo da RAIZ do
    projeto, entao sem ele a fixture so funcionava quando o pytest era
    chamado de la. Rodando de `apps/api` o subprocesso morria com
    ModuleNotFoundError — e, como a saida ia para DEVNULL, o teste falhava
    dizendo apenas "nao subiu", escondendo a causa. A raiz e derivada de
    `__file__` (mesma convencao do conftest), nunca de caminho absoluto nem
    do diretorio atual.
    """
    import subprocess
    import sys
    import tempfile
    import time as time_module

    import httpx

    from apps.api.app.config import settings

    # tests/ -> api/ -> apps/ -> raiz  (igual ao _REPO do conftest)
    raiz = Path(__file__).resolve().parents[3]
    port = settings.demo_primary_port
    base = f"http://127.0.0.1:{port}"

    # Log em arquivo (nao PIPE): se o servidor escrever mais que o buffer do
    # pipe e ninguem estiver lendo, o processo travaria. Com arquivo, a saida
    # fica disponivel para o diagnostico sem risco de deadlock.
    log = tempfile.NamedTemporaryFile(  # noqa: SIM115
        mode="w+", suffix=".log", prefix="demo_server_", delete=False
    )

    def _saida() -> str:
        log.flush()
        return Path(log.name).read_text(encoding="utf-8", errors="replace").strip()

    def _remover_log() -> None:
        """
        Apaga o log temporario, tolerando o atraso do Windows.

        No Windows o handle do arquivo pode levar alguns milissegundos para
        ser liberado DEPOIS que o processo morreu e o objeto foi fechado — e
        nesse intervalo o unlink levanta PermissionError (WinError 32). Um
        gate funcionalmente aprovado nao pode virar erro de teardown por
        causa disso: tentamos algumas vezes e, se continuar bloqueado,
        avisamos em vez de falhar. E um temporario do sistema, nao um
        resultado da execucao.

        Erro que NAO seja PermissionError sobe: esconder falha de remocao em
        geral mascararia problema real.
        """
        caminho = Path(log.name)
        for tentativa in range(_LOG_UNLINK_TRIES):
            try:
                caminho.unlink(missing_ok=True)
                return
            except PermissionError:
                if tentativa == _LOG_UNLINK_TRIES - 1:
                    warnings.warn(
                        f"log temporario do demo_server continuou bloqueado; "
                        f"nao foi removido: {caminho}",
                        ResourceWarning,
                        stacklevel=2,
                    )
                    return
                time_module.sleep(_LOG_UNLINK_DELAY_S)

    proc = subprocess.Popen(
        [sys.executable, "-m", "tools.demo_server.app"],
        cwd=str(raiz),
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for _ in range(30):
            # Se o processo morreu, nao ha por que esperar os 15s restantes:
            # falha agora, mostrando a saida real.
            if proc.poll() is not None:
                pytest.fail(
                    f"demo_server encerrou com codigo {proc.returncode} antes de "
                    f"responder. Saida do processo:\n{_saida()}"
                )
            try:
                if httpx.get(f"{base}/health", timeout=1.0).status_code == HTTP_OK:
                    break
            except httpx.HTTPError:
                pass
            time_module.sleep(0.5)
        else:
            pytest.fail(
                f"demo_server nao respondeu em {base}/health apos 15s. "
                f"Saida do processo:\n{_saida()}"
            )
        yield
    finally:
        # Encerramento sem orfao: pede para sair, e se nao sair, mata. Um
        # timeout DEPOIS do kill sobe como erro — processo que nao morre e
        # problema real, nao ruido de teardown.
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        log.close()
        _remover_log()


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


def test_postprocess_zipa_pacote_de_validate_mesmo_sem_pasta(tmp_path: Path) -> None:
    """
    _postprocess do validate: zipa a pasta do pacote quando ela existe, e e
    inofensivo quando nao existe (defensivo). Regressao do bug em que o
    pos-processamento so rodava com exit 0 e o pacote de uma validacao com
    problemas nunca era empacotado.
    """
    import zipfile

    out = tmp_path / "out"
    pacote = out / "pacote_execucao"
    pacote.mkdir(parents=True)
    (pacote / "manifest.json").write_text('{"ok": true}', encoding="utf-8")

    engine._postprocess("validate", tmp_path)

    assert (out / "pacote_execucao.zip").is_file()
    assert not pacote.exists()  # a pasta original e removida apos zipar
    z = zipfile.ZipFile(out / "pacote_execucao.zip")
    assert "manifest.json" in z.namelist()

    # sem a pasta, nao explode e nao cria nada
    engine._postprocess("validate", tmp_path / "vazio")


@pytest.mark.parametrize(
    ("automation_id", "exit_code", "timed_out", "esperado"),
    [
        ("validate", 0, False, True),  # terminou bem
        ("validate", 1, False, True),  # caught_issue: achou problemas nos dados
        ("validate", 2, False, False),  # erro de uso/configuracao: nada a empacotar
        ("organize", 0, False, True),  # outra automacao, sucesso
        ("organize", 1, False, False),  # outra automacao, falha tecnica
        ("organize", 5, False, False),
        ("validate", 1, True, False),  # timeout: saida incompleta
        ("validate", 0, True, False),
    ],
)
def test_matriz_do_pos_processamento(
    automation_id: str, exit_code: int, timed_out: bool, esperado: bool
) -> None:
    """
    Quando o pos-processamento (zipar pastas) pode rodar.

    O ponto delicado e `validate` exit 1: a validacao rodou inteira e ACHOU
    problemas, entao a saida esta completa e o pacote de evidencias deve ser
    entregue. Ja o exit 2 e erro de uso — nao houve validacao. Uma condicao
    apenas "exit_code == 0" perderia o primeiro caso; uma condicao apenas
    "not timed_out" aceitaria os outros dois indevidamente.
    """
    assert engine._should_postprocess(automation_id, exit_code, timed_out=timed_out) is esperado


# ============================================================
# Card 02.A — o Live precisa dizer a verdade sobre o backup
# ============================================================


def test_backup_com_ressalva_nao_e_erro_tecnico() -> None:
    """
    Regressao: o mapeamento so abria excecao para `validate`, entao um backup
    que CONCLUIU pulando um arquivo travado aparecia como falha tecnica. O
    pacote existe e presta — chamar isso de erro esconderia um backup bom.
    """
    assert engine._outcome("backup", 1) == "caught_issue"
    assert engine._outcome("backup", 0) == "ok"
    assert engine._outcome("backup", 2) == "error"
    # As outras automacoes seguem estritas: exit != 0 continua sendo erro.
    assert engine._outcome("organize", 1) == "error"


def test_backup_com_ressalva_ainda_empacota_a_saida() -> None:
    assert engine._should_postprocess("backup", 1, timed_out=False) is True
    assert engine._should_postprocess("backup", 1, timed_out=True) is False


def test_live_le_do_manifesto_o_que_nao_entrou(tmp_path: Path) -> None:
    """
    A tela mostra o que saiu do ARTEFATO, nao do texto do terminal: uma troca
    de mensagem na CLI nao pode silenciar o aviso sem ninguem perceber.
    """
    out = tmp_path / "out"
    out.mkdir()
    with zipfile.ZipFile(out / "backup.zip", "w") as zf:
        zf.writestr("dados/nota.txt", "nota")
        zf.writestr(
            "MANIFESTO.csv",
            "# backup,autotarefas\n"
            "situacao,arquivo,bytes,modificado_em,sha256,motivo\n"
            "incluido,dados/nota.txt,4,2026-08-20T00:00:00+00:00,abc,\n"
            'NAO_LIDO,dados/planilha.xlsx,,,,"aberto por outro programa"\n',
        )

    ressalvas = engine._ressalvas_do_backup(out)

    assert ressalvas == ["dados/planilha.xlsx: aberto por outro programa"]


def test_pacote_sem_manifesto_nao_inventa_ressalva(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    with zipfile.ZipFile(out / "alheio.zip", "w") as zf:
        zf.writestr("a.txt", "conteudo")

    assert engine._ressalvas_do_backup(out) == []
