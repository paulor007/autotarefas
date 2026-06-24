#!/usr/bin/env python3
"""Capturador de execucoes reais do AutoTarefas para o Live System (SPA estatica).

Este script orquestra as automacoes do projeto contra servidores locais de
demonstracao, captura as saidas REAIS (stdout/stderr/exit code), confere o
trilho de auditoria gravado e produz dois artefatos para a SPA:

* ``runs.json``      -> dados estruturados de cada execucao (consumidos pelo front).
* ``dashboard.html`` -> painel de auditoria gerado pelo renderer oficial do projeto.

Principios:

* Reprodutibilidade: ambiente isolado (``AUTOTAREFAS_HOME`` dedicado, ``ENVIRONMENT=demo``,
  servidores com armazenamento proprio). Nenhum dado de producao e tocado.
* Honestidade: nada de saida fabricada. O nucleo (``BaseTask``) grava auditoria sem
  ``input_data``, entao ``stored_input_hash`` fica vazio de proposito; o HMAC do input
  e recalculado a parte (mesmo algoritmo de ``core.security.hash_string``) e exposto
  como ``input.hmac_sha256``, claramente rotulado.
* Seguranca: as saidas capturadas tem ANSI removido e CPFs mascarados. Tokens/segredos
  de demonstracao sao redigidos. E-mails ``@example.com`` sao ficticios e preservados.

Uso:
    python examples/capture_runs.py [--output-dir DIR] [--no-browser] [--no-publish]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import subprocess  # nosec B404 - script de demo orquestra comandos locais controlados.
import sys
import time
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:  # importado de verdade so em tempo de checagem (apos env no runtime)
    from autotarefas.dashboard.reader import AuditEntry

# ============================================================
# Constantes de ambiente e caminhos
# ============================================================

ROOT: Path = Path(__file__).resolve().parents[1]
FIXTURES: Path = ROOT / "examples" / "fixtures"
DOCS_ASSETS: Path = ROOT / "docs" / "live" / "assets"

CLIENTES_CSV: Path = FIXTURES / "clientes.csv"
SCHEMA_YAML: Path = FIXTURES / "schema_clientes.yaml"
ORGANIZE_RULES: Path = FIXTURES / "organize_rules.yaml"
DESORGANIZADO: Path = FIXTURES / "desorganizado"

# Servidores locais de demonstracao
SRC_PORT: int = 5555  # origem: API, catalogo, telegram-mock e cadastro (RPA)
DST_PORT: int = 5556  # destino: alvo do sync
SMTP_PORT: int = 8025  # servidor SMTP de debug (salva .eml em disco)

# Valores FAKE de demonstracao (nao sao segredos reais).
DEMO_AUDIT_SECRET: str = "demo-key-autotarefas-live-system-0001"
FAKE_TELEGRAM_TOKEN: str = "000000:DEMOFAKE-token-not-real-aaaaaaaaaaaaaaaa"

SCHEMA_VERSION: str = "1.0"
HTTP_OK: int = 200
HTTP_REDIRECTION_START: int = 300
TOOL_NAME: str = "autotarefas"

# Regex de saneamento
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_CPF_RE = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")
_REDACTIONS: tuple[str, ...] = (DEMO_AUDIT_SECRET, FAKE_TELEGRAM_TOKEN)

# Metadados das categorias (agrupamento na SPA)
CATEGORIES: list[dict[str, str]] = [
    {
        "key": "validacao",
        "title": "Validacao & Qualidade",
        "summary": "Valida planilhas contra schema YAML e barra dados fora do padrao.",
    },
    {
        "key": "arquivos",
        "title": "Backup & Organizacao",
        "summary": "Compacta com hash SHA-256 e classifica arquivos por tipo.",
    },
    {
        "key": "integracao",
        "title": "Integracao de API",
        "summary": "Envia, coleta e sincroniza registros entre APIs REST.",
    },
    {
        "key": "notificacoes",
        "title": "Notificacoes",
        "summary": "Disparos personalizados por e-mail (SMTP) e Telegram.",
    },
    {
        "key": "scraping",
        "title": "Web Scraping",
        "summary": "Raspa catalogos paginados, inclusive renderizados via JavaScript.",
    },
    {
        "key": "rpa",
        "title": "RPA (Navegador)",
        "summary": "Preenche formularios web automaticamente via Chromium headless.",
    },
    {
        "key": "auditoria",
        "title": "Auditoria",
        "summary": "Consolida o trilho append-only e gera o painel HTML.",
    },
]


# ============================================================
# Modelo de uma execucao a capturar
# ============================================================


@dataclass(frozen=True)
class RunSpec:
    """Descreve, de forma declarativa, uma execucao a ser capturada."""

    run_id: str
    category: str
    title: str
    subtitle: str
    argv: list[str]
    audit_task: str | None
    expected_status: str  # status de auditoria esperado: SUCCESS | FAILURE
    expected: str  # descricao humana do resultado esperado
    headline_ok: str
    headline_caught: str = ""
    requires_browser: bool = False
    needs: tuple[str, ...] = ()  # servidores necessarios: src | dst | smtp
    pre: tuple[str, ...] = ()  # passos previos: reset_src | reset_dst | reset_tg
    outputs: tuple[Path, ...] = ()
    identity: dict[str, Any] = field(default_factory=dict)
    preview_clientes: bool = False  # inclui preview mascarado de clientes.csv


# ============================================================
# Helpers de saneamento e fingerprint
# ============================================================


def _rel(path: Path) -> str:
    """Caminho relativo a raiz do projeto, em formato POSIX."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def scrub(text: str) -> str:
    """Remove ANSI, mascara CPFs e redige segredos/tokens de demonstracao."""
    cleaned = _ANSI_RE.sub("", text)
    cleaned = _CPF_RE.sub("***.***.***-**", cleaned)
    for secret in _REDACTIONS:
        if secret:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    return cleaned.strip("\n")


def _render_cmd(argv: Sequence[str]) -> str:
    """Renderiza o comando para exibicao, citando tokens com espacos."""
    parts: list[str] = []
    for token in argv:
        parts.append(f'"{token}"' if " " in token else token)
    return " ".join(parts)


def masked_clientes_preview(limit: int = 3) -> list[dict[str, str]]:
    """Le as primeiras linhas de clientes.csv com CPF mascarado (preview seguro)."""
    rows: list[dict[str, str]] = []
    if not CLIENTES_CSV.exists():
        return rows
    with CLIENTES_CSV.open(encoding="utf-8") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            if index >= limit:
                break
            rows.append(
                {
                    "nome": row.get("nome", ""),
                    "email": row.get("email", ""),
                    "cpf": _CPF_RE.sub("***.***.***-**", row.get("cpf", "")),
                    "chat_id": row.get("chat_id", ""),
                }
            )
    return rows


def fingerprint(path: Path) -> dict[str, Any] | None:
    """Gera metadados de um arquivo (SHA-256) ou diretorio (contagem/bytes)."""
    if not path.exists():
        return None
    if path.is_dir():
        files = [item for item in path.rglob("*") if item.is_file()]
        total = sum(item.stat().st_size for item in files)
        return {
            "path": _rel(path),
            "kind": "dir",
            "files": len(files),
            "bytes": total,
            "sha256": None,
        }
    data = path.read_bytes()
    return {
        "path": _rel(path),
        "kind": "file",
        "files": 1,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


# ============================================================
# Subprocessos e rede (servidores locais)
# ============================================================


def _subprocess_env(*, with_root_pythonpath: bool = False) -> dict[str, str]:
    """Copia o ambiente atual; opcionalmente coloca a raiz no PYTHONPATH (p/ ``tools``)."""
    env = dict(os.environ)
    if with_root_pythonpath:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(ROOT) + (os.pathsep + existing if existing else "")
    return env


def _wait_port(host: str, port: int, *, timeout: float) -> bool:
    """Aguarda ate a porta TCP aceitar conexao (ou estourar o timeout)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2.0):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def _local_http_path(url: str) -> tuple[str, int, str]:
    """Valida uma URL local HTTP e devolve host, porta e caminho."""
    parsed = urlparse(url)

    if parsed.scheme != "http":
        raise ValueError("A demo aceita apenas URLs HTTP locais.")

    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("A demo aceita apenas hosts locais.")

    if parsed.port is None:
        raise ValueError("A URL local precisa informar a porta.")

    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    return parsed.hostname, parsed.port, path


def _post(url: str, *, timeout: float = 5.0) -> bool:
    """Faz um POST simples apenas em endpoints HTTP locais de demonstracao."""
    conn: http.client.HTTPConnection | None = None
    try:
        host, port, path = _local_http_path(url)
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("POST", path, body=b"")
        response = conn.getresponse()
        response.read()
        return HTTP_OK <= response.status < HTTP_REDIRECTION_START
    except (ValueError, OSError, http.client.HTTPException):
        return False
    finally:
        if conn is not None:
            conn.close()


@contextmanager
def demo_server(*, port: int, data_dir: Path) -> Iterator[bool]:
    """Sobe um demo server Flask isolado (storage proprio). Cede True se saudavel.

    Usa um launcher inline que troca o ``storage`` global por uma instancia apontando
    para ``data_dir`` ANTES de ``app.run`` — assim cada servidor tem seu proprio
    ``cadastros.json`` e o arquivo versionado em ``tools/demo_server/data`` nunca e tocado.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    launcher = (
        "import sys; from pathlib import Path; "
        "import tools.demo_server.app as a; "
        "a.storage = a.Storage(data_dir=Path(sys.argv[1])); "
        "a.app.run(host='127.0.0.1', port=int(sys.argv[2]), debug=False)"
    )
    proc = subprocess.Popen(  # nosec B603 - argumentos locais/controlados, shell=False.  # noqa: S603
        [sys.executable, "-c", launcher, str(data_dir), str(port)],
        cwd=str(ROOT),
        env=_subprocess_env(with_root_pythonpath=True),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield _wait_port("127.0.0.1", port, timeout=15.0)
    finally:
        proc.terminate()
        with suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5.0)
        if proc.poll() is None:
            proc.kill()


@contextmanager
def smtp_server(*, port: int, output_dir: Path) -> Iterator[bool]:
    """Sobe o servidor SMTP de debug; salva os .eml em ``output_dir/emails_recebidos``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    # Bandit/Ruff: servidor SMTP local controlado, shell=False.
    proc = subprocess.Popen(  # nosec B603
        [sys.executable, "-m", "tools.smtp_debug"],
        cwd=str(output_dir),
        env=_subprocess_env(with_root_pythonpath=True),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield _wait_port("127.0.0.1", port, timeout=15.0)
    finally:
        proc.terminate()
        with suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5.0)
        if proc.poll() is None:
            proc.kill()


def detect_browser() -> tuple[bool, str]:
    """Detecta se o Chromium do Playwright esta disponivel (lanca e fecha rapido)."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001 - import pode falhar de varias formas
        return False, f"Playwright indisponivel: {type(exc).__name__}"
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            browser.close()
    except Exception as exc:  # noqa: BLE001 - launch falha se o binario nao esta instalado
        return False, f"Chromium indisponivel: {type(exc).__name__}"
    return True, "Chromium disponivel"


# ============================================================
# Integridade do input (HMAC) — honesto e rotulado
# ============================================================


def _canonical(identity: dict[str, Any]) -> str:
    """Serializa o input de forma canonica (igual ao que ``verify_input_hash`` usa)."""
    return json.dumps(identity, default=str, sort_keys=True)


def _hash_string(data: str) -> str:
    """HMAC-SHA256 com a chave de demonstracao (reusa ``core.security.hash_string``)."""
    from autotarefas.core.security import hash_string

    return hash_string(data, DEMO_AUDIT_SECRET)


# ============================================================
# Catalogo declarativo de execucoes
# ============================================================


def build_runs(out: Path) -> list[RunSpec]:
    """Monta a lista ordenada de execucoes a capturar (cada uma roda exatamente uma vez)."""
    src = f"http://127.0.0.1:{SRC_PORT}"
    dst = f"http://127.0.0.1:{DST_PORT}"
    return [
        RunSpec(
            run_id="validate",
            category="validacao",
            title="Validacao de planilha",
            subtitle="CSV x schema YAML (CPF, e-mail, idade)",
            argv=[
                "validate",
                str(CLIENTES_CSV),
                "-s",
                str(SCHEMA_YAML),
                "--report-json",
                str(out / "validate_report.json"),
            ],
            audit_task="validate",
            expected_status="FAILURE",
            expected="Detecta 1 CPF invalido (digito verificador) e retorna codigo 1.",
            headline_ok="Planilha valida",
            headline_caught="CPF invalido barrado pela validacao",
            outputs=(out / "validate_report.json",),
            identity={
                "task": "validate",
                "arquivo": "clientes.csv",
                "schema": "schema_clientes.yaml",
            },
            preview_clientes=True,
        ),
        RunSpec(
            run_id="backup",
            category="arquivos",
            title="Backup compactado",
            subtitle="ZIP com hash SHA-256",
            argv=["backup", str(FIXTURES), "-o", str(out / "backup_fixtures.zip")],
            audit_task="backup",
            expected_status="SUCCESS",
            expected="Compacta a pasta de fixtures e calcula o hash SHA-256 do pacote.",
            headline_ok="Pacote ZIP integro com hash SHA-256",
            outputs=(out / "backup_fixtures.zip",),
            identity={"task": "backup", "origem": "examples/fixtures"},
        ),
        RunSpec(
            run_id="organize",
            category="arquivos",
            title="Organizacao por tipo",
            subtitle="Classifica arquivos em subpastas",
            argv=[
                "--yes",
                "organize",
                str(DESORGANIZADO),
                "-r",
                str(ORGANIZE_RULES),
            ],
            audit_task="organize",
            expected_status="SUCCESS",
            expected="Copia os arquivos para documentos/, imagens/ e planilhas/.",
            headline_ok="Arquivos classificados por tipo",
            outputs=(out / "organizado",),
            identity={
                "task": "organize",
                "origem": "desorganizado",
                "regras": "organize_rules.yaml",
            },
        ),
        RunSpec(
            run_id="send_api",
            category="integracao",
            title="Envio via API",
            subtitle="POST de cada linha para /api/clientes",
            argv=[
                "send",
                "api",
                "-p",
                str(CLIENTES_CSV),
                "-u",
                f"{src}/api/clientes",
                "-r",
                str(out / "send_api_report.csv"),
            ],
            audit_task="send_api",
            expected_status="SUCCESS",
            expected="Envia as 5 linhas da planilha como JSON para a API local.",
            headline_ok="Registros enviados via API",
            needs=("src",),
            pre=("reset_src",),
            outputs=(out / "send_api_report.csv",),
            identity={"task": "send_api", "endpoint": "/api/clientes", "planilha": "clientes.csv"},
            preview_clientes=True,
        ),
        RunSpec(
            run_id="extract_api",
            category="integracao",
            title="Coleta via API",
            subtitle="GET paginado de /api/clientes",
            argv=[
                "extract",
                "api",
                "-u",
                f"{src}/api/clientes",
                "-o",
                str(out / "extract_api.csv"),
            ],
            audit_task="extract_api",
            expected_status="SUCCESS",
            expected="Le todas as paginas da API e grava um CSV consolidado.",
            headline_ok="Registros coletados da API",
            needs=("src",),
            outputs=(out / "extract_api.csv",),
            identity={"task": "extract_api", "endpoint": "/api/clientes"},
        ),
        RunSpec(
            run_id="sync_api",
            category="integracao",
            title="Sincronizacao de API",
            subtitle="Replica origem -> destino",
            argv=[
                "sync",
                "api",
                "-s",
                f"{src}/api/clientes",
                "-d",
                f"{dst}/api/clientes",
                "-r",
                str(out / "sync_report.csv"),
            ],
            audit_task="sync_api",
            expected_status="SUCCESS",
            expected="Copia os registros da origem (5555) para o destino (5556).",
            headline_ok="Origem replicada no destino",
            needs=("src", "dst"),
            pre=("reset_dst",),
            outputs=(out / "sync_report.csv",),
            identity={"task": "sync_api", "origem": "5555", "destino": "5556"},
        ),
        RunSpec(
            run_id="send_email",
            category="notificacoes",
            title="Disparo de e-mails",
            subtitle="SMTP local (.eml em disco)",
            argv=[
                "send",
                "email",
                "-p",
                str(CLIENTES_CSV),
                "--smtp-host",
                "localhost",
                "--smtp-port",
                str(SMTP_PORT),
                "--from",
                "robo@example.com",
                "--subject",
                "AutoTarefas — comunicado para {nome}",
                "--body",
                "Ola {nome}, este e um envio de demonstracao do AutoTarefas.",
                "--no-tls",
                "--email-column",
                "email",
                "-r",
                str(out / "send_email_report.csv"),
            ],
            audit_task="send_email",
            expected_status="SUCCESS",
            expected="Envia 5 e-mails personalizados ao servidor SMTP de debug.",
            headline_ok="E-mails entregues ao servidor SMTP",
            needs=("smtp",),
            outputs=(out / "send_email_report.csv", out / "emails_recebidos"),
            identity={"task": "send_email", "planilha": "clientes.csv", "destinatarios": 5},
            preview_clientes=True,
        ),
        RunSpec(
            run_id="send_telegram",
            category="notificacoes",
            title="Mensagens no Telegram",
            subtitle="Bot mock local (sendMessage)",
            argv=[
                "send",
                "telegram",
                "-p",
                str(CLIENTES_CSV),
                "--chat-id-column",
                "chat_id",
                "--base-url",
                src,
                "--text",
                "Ola {nome}! Mensagem de teste do AutoTarefas.",
                "-r",
                str(out / "send_telegram_report.csv"),
            ],
            audit_task="send_telegram",
            expected_status="SUCCESS",
            expected="Envia 5 mensagens ao endpoint mock /bot<token>/sendMessage.",
            headline_ok="Mensagens entregues ao bot (mock)",
            needs=("src",),
            pre=("reset_tg",),
            outputs=(out / "send_telegram_report.csv",),
            identity={"task": "send_telegram", "planilha": "clientes.csv", "destinatarios": 5},
        ),
        RunSpec(
            run_id="extract_web",
            category="scraping",
            title="Scraping de catalogo",
            subtitle="HTML paginado (48 itens)",
            argv=[
                "extract",
                "web",
                "-u",
                f"{src}/catalogo",
                "-o",
                str(out / "extract_web.csv"),
                "-r",
                "tr.produto",
                "-f",
                "nome=td.nome",
                "-f",
                "preco=td.preco",
                "-n",
                "a.next",
            ],
            audit_task="extract_web",
            expected_status="SUCCESS",
            expected="Percorre as paginas do catalogo e extrai 48 itens (nome/preco).",
            headline_ok="Catalogo paginado raspado",
            needs=("src",),
            outputs=(out / "extract_web.csv",),
            identity={"task": "extract_web", "url": "/catalogo", "row_selector": "tr.produto"},
        ),
        RunSpec(
            run_id="rpa_cadastro",
            category="rpa",
            title="RPA de cadastro",
            subtitle="Chromium headless preenche formulario",
            argv=[
                "rpa",
                "cadastro",
                "-p",
                str(CLIENTES_CSV),
                "-s",
                src,
                "--no-screenshot",
            ],
            audit_task="rpa_cadastro",
            expected_status="SUCCESS",
            expected="Abre o Chromium e preenche o formulario web para cada CPF valido.",
            headline_ok="Cadastros preenchidos via navegador",
            requires_browser=True,
            needs=("src",),
            outputs=(),
            identity={"task": "rpa_cadastro", "planilha": "clientes.csv", "site": "127.0.0.1:5555"},
            preview_clientes=True,
        ),
        RunSpec(
            run_id="extract_web_js",
            category="scraping",
            title="Scraping com JavaScript",
            subtitle="Catalogo renderizado via JS (3 itens)",
            argv=[
                "extract",
                "web",
                "-u",
                f"{src}/catalogo-js",
                "-o",
                str(out / "extract_web_js.csv"),
                "-r",
                "tr.produto",
                "-f",
                "nome=td.nome",
                "-f",
                "preco=td.preco",
                "--js",
            ],
            audit_task="extract_web",
            expected_status="SUCCESS",
            expected="Renderiza a pagina com Chromium e extrai os 3 itens injetados via JS.",
            headline_ok="Catalogo dinamico (JS) raspado",
            requires_browser=True,
            needs=("src",),
            outputs=(out / "extract_web_js.csv",),
            identity={"task": "extract_web", "url": "/catalogo-js", "js": True},
        ),
        RunSpec(
            run_id="report",
            category="auditoria",
            title="Relatorio de auditoria",
            subtitle="Resumo consolidado do trilho",
            argv=["report", "--days", "1", "--type", "summary", "--format", "table"],
            audit_task="report_audit",
            expected_status="SUCCESS",
            expected="Consolida as execucoes da ultima janela e imprime o resumo.",
            headline_ok="Relatorio de auditoria consolidado",
            outputs=(),
            identity={"task": "report_audit", "janela_dias": 1},
        ),
        RunSpec(
            run_id="dashboard",
            category="auditoria",
            title="Painel de auditoria",
            subtitle="HTML autocontido (renderer oficial)",
            argv=["dashboard", "-o", str(out / "dashboard.html"), "--limit", "100"],
            audit_task=None,  # leitura pura: nao grava auditoria
            expected_status="SUCCESS",
            expected="Le todo o trilho (inclusive o report_audit) e gera o painel HTML.",
            headline_ok="Painel HTML de auditoria gerado",
            outputs=(out / "dashboard.html",),
            identity={"task": "dashboard", "limite": 100},
        ),
    ]


# ============================================================
# Execucao e captura
# ============================================================


def run_command(argv: list[str], *, timeout: float = 180.0) -> tuple[int | None, str, str, int]:
    """Roda ``python -m autotarefas <argv>`` capturando saida; nunca levanta excecao."""
    start = time.monotonic()
    try:
        proc = subprocess.run(  # nosec B603 - executa CLI local com args definidos no catalogo, shell=False.  # noqa: S603
            [sys.executable, "-m", TOOL_NAME, *argv],
            cwd=str(ROOT),
            env=_subprocess_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        duration_ms = int((time.monotonic() - start) * 1000)
        return None, "", f"Tempo limite excedido ({timeout:.0f}s).", duration_ms
    duration_ms = int((time.monotonic() - start) * 1000)
    return proc.returncode, proc.stdout, proc.stderr, duration_ms


def _do_pre_steps(pre: Sequence[str]) -> None:
    """Executa passos previos (resets) nos servidores de demonstracao."""
    endpoints = {
        "reset_src": f"http://127.0.0.1:{SRC_PORT}/limpar",
        "reset_dst": f"http://127.0.0.1:{DST_PORT}/limpar",
        "reset_tg": f"http://127.0.0.1:{SRC_PORT}/telegram/limpar",
    }
    for step in pre:
        url = endpoints.get(step)
        if url is not None:
            _post(url)


def _build_input_block(spec: RunSpec) -> dict[str, Any]:
    """Monta o bloco ``input`` com identidade canonica, preview seguro e HMAC rotulado."""
    canonical = _canonical(spec.identity)
    digest = _hash_string(canonical)
    return {
        "descriptor": spec.subtitle,
        "identity": spec.identity,
        "preview": masked_clientes_preview() if spec.preview_clientes else None,
        "hmac_sha256": digest,
        "hmac_short": digest[:12],
        "hmac_algo": "HMAC-SHA256 (core.security.hash_string, chave de auditoria)",
    }


def capture_run(
    spec: RunSpec,
    *,
    server_health: dict[str, bool],
    browser_available: bool,
) -> dict[str, Any]:
    """Executa (ou pula honestamente) um spec e devolve o dicionario do run para o JSON."""
    base: dict[str, Any] = {
        "id": spec.run_id,
        "category": spec.category,
        "title": spec.title,
        "subtitle": spec.subtitle,
        "command": "python -m autotarefas " + _render_cmd(spec.argv),
        "requires_browser": spec.requires_browser,
        "expected_outcome": spec.expected,
        "input": _build_input_block(spec),
        "outputs": [],
    }

    # 1. Requer navegador e ele nao esta disponivel -> pula com transparencia.
    if spec.requires_browser and not browser_available:
        local_cmd = "python -m autotarefas " + _render_cmd(spec.argv)
        base.update(
            captured=False,
            exit_code=None,
            outcome="requires_browser",
            duration_ms=None,
            headline="Requer navegador (execucao local)",
            stdout=(
                "[execucao local necessaria] Esta etapa usa o Chromium (Playwright), "
                "indisponivel neste ambiente de captura.\n"
                f"Para reproduzir localmente:\n  {local_cmd}\n"
                f"Resultado esperado: {spec.expected}"
            ),
            stderr="",
        )
        return base

    # 2. Servidor necessario indisponivel -> marca erro de infraestrutura (sem rodar).
    missing = [name for name in spec.needs if not server_health.get(name, False)]
    if missing:
        nomes = ", ".join(missing)
        base.update(
            captured=False,
            exit_code=None,
            outcome="error",
            duration_ms=None,
            headline=f"Servidor de demonstracao indisponivel: {nomes}",
            stdout="",
            stderr=f"Pre-requisito ausente: servidor(es) {nomes} nao subiu(ram).",
        )
        return base

    # 3. Execucao real.
    _do_pre_steps(spec.pre)
    exit_code, stdout, stderr, duration_ms = run_command(spec.argv)
    base.update(
        captured=True,
        exit_code=exit_code,
        duration_ms=duration_ms,
        stdout=scrub(stdout),
        stderr=scrub(stderr),
        outputs=[fp for path in spec.outputs if (fp := fingerprint(path)) is not None],
    )

    # 4. Classifica o desfecho (caught_issue e um SUCESSO demonstrativo).
    if spec.expected_status == "FAILURE":
        if exit_code not in (0, None):
            base.update(outcome="caught_issue", headline=spec.headline_caught)
        else:
            base.update(outcome="error", headline="Esperava barrar dados invalidos, mas nao barrou")
    elif exit_code == 0:
        base.update(outcome="ok", headline=spec.headline_ok)
    else:
        base.update(outcome="error", headline=f"Falha inesperada (exit {exit_code})")
    return base


# ============================================================
# Auditoria: leitura in-process e casamento com os runs
# ============================================================


def read_audit_entries() -> list[AuditEntry]:
    """Le o trilho de auditoria in-process (mesmo ambiente/banco dos subprocessos)."""
    from autotarefas.dashboard.reader import read_entries

    return read_entries(limit=200)


def _entry_to_audit_block(entry: AuditEntry, identity: dict[str, Any]) -> dict[str, Any]:
    """Converte uma entrada de auditoria no bloco ``audit`` (honesto quanto ao input_hash)."""
    from autotarefas.dashboard.reader import verify_input_hash

    timestamp = entry.timestamp.isoformat() if entry.timestamp is not None else None
    return {
        "recorded": True,
        "task_name": entry.task_name,
        "status": entry.status,
        "timestamp": timestamp,
        "duration_ms": entry.duration_ms,
        "rows_affected": entry.rows_affected,
        "rows_failed": entry.rows_failed,
        "environment": entry.environment,
        # Valor REAL gravado no banco. O nucleo nao passa input_data ao audit,
        # entao fica vazio de proposito (ver notes.input_hash).
        "stored_input_hash": entry.input_hash,
        # reader.verify_input_hash recalcula o HMAC e compara com o gravado:
        # como o gravado e vazio, retorna False — exatamente o esperado.
        "verify_input_hash_against_stored": verify_input_hash(entry, identity),
    }


def attach_audit(
    results: list[dict[str, Any]],
    specs: Sequence[RunSpec],
    entries: Sequence[AuditEntry],
) -> None:
    """Casa cada execucao real com a entrada de auditoria correspondente (mais antiga primeiro).

    Como duas etapas podem compartilhar o mesmo ``task_name`` (ex.: extract_web e
    extract_web --js), consumimos as entradas em ordem cronologica seguindo a ordem
    de execucao, garantindo um pareamento 1:1 deterministico.
    """
    spec_by_id = {spec.run_id: spec for spec in specs}
    # read_entries devolve "mais recente primeiro"; aqui queremos o oposto.
    pool: list[AuditEntry] = list(reversed(list(entries)))

    for run in results:
        spec = spec_by_id[run["id"]]
        identity = run["input"]["identity"]

        if spec.audit_task is None:
            run["audit"] = {"recorded": False, "note": "Execucao read-only: nao grava auditoria."}
            continue
        if not run.get("captured", False):
            run["audit"] = {"recorded": False, "note": "Execucao nao realizada neste ambiente."}
            continue

        match: AuditEntry | None = None
        for index, entry in enumerate(pool):
            if entry.task_name == spec.audit_task:
                match = pool.pop(index)
                break

        if match is None:
            run["audit"] = {"recorded": False, "note": "Entrada de auditoria nao encontrada."}
            continue

        run["audit"] = _entry_to_audit_block(match, identity)
        _enrich_headline(run, match)


def _enrich_headline(run: dict[str, Any], entry: AuditEntry) -> None:
    """Acrescenta a contagem de linhas ao headline quando faz sentido."""
    if run.get("outcome") == "ok" and entry.rows_affected:
        run["headline"] = f"{run['headline']} ({entry.rows_affected} linha(s))"
    elif run.get("outcome") == "caught_issue" and entry.rows_failed:
        run["headline"] = f"{entry.rows_failed} registro(s) barrado(s) pela validacao"


# ============================================================
# Montagem do documento, publicacao e resumo
# ============================================================


def build_document(
    results: list[dict[str, Any]],
    *,
    browser_available: bool,
    browser_note: str,
) -> dict[str, Any]:
    """Monta o dicionario final do ``runs.json`` (versionado e amigavel a SPA)."""
    from autotarefas import __version__

    captured = sum(1 for run in results if run.get("captured"))
    requires_browser = sum(1 for run in results if run["outcome"] == "requires_browser")
    by_status: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    for run in results:
        by_outcome[run["outcome"]] = by_outcome.get(run["outcome"], 0) + 1
        audit = run.get("audit", {})
        if audit.get("recorded"):
            status = str(audit.get("status", ""))
            by_status[status] = by_status.get(status, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "tool": {"name": TOOL_NAME, "version": __version__},
        "environment": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "browser_available": browser_available,
            "browser_note": browser_note,
            "mode": "demo",
        },
        "summary": {
            "total": len(results),
            "captured": captured,
            "requires_browser": requires_browser,
            "by_status": by_status,
            "by_outcome": by_outcome,
        },
        "categories": CATEGORIES,
        "runs": results,
        "notes": {
            "input_hash": (
                "O nucleo (BaseTask) registra cada execucao sem passar input_data ao audit, "
                "entao a coluna input_hash do banco fica vazia por padrao. Para o painel, "
                "recalculamos o HMAC-SHA256 do input sanitizado (mesmo algoritmo de "
                "core.security.hash_string e dashboard.verify_input_hash) e o expomos em "
                "input.hmac_sha256. O campo stored_input_hash reflete fielmente o que esta "
                "gravado (vazio) e verify_input_hash_against_stored e, por isso, false."
            ),
            "sanitization": (
                "Saidas capturadas tem ANSI removido e CPFs mascarados (***.***.***-**). "
                "E-mails @example.com sao ficticios e preservados. Tokens/segredos de "
                "demonstracao sao redigidos."
            ),
            "reproducibility": (
                "Execucao isolada: AUTOTAREFAS_HOME dedicado, ENVIRONMENT=demo e servidores "
                "locais com armazenamento proprio. Nenhum dado de producao e tocado."
            ),
        },
    }


def publish_assets(out: Path) -> list[Path]:
    """Copia runs.json e dashboard.html para docs/live/assets/ (origem da SPA)."""
    DOCS_ASSETS.mkdir(parents=True, exist_ok=True)
    published: list[Path] = []
    for name in ("runs.json", "dashboard.html"):
        source = out / name
        if source.exists():
            target = DOCS_ASSETS / name
            shutil.copy2(source, target)
            published.append(target)
    return published


def print_summary(results: Sequence[dict[str, Any]]) -> None:
    """Imprime um resumo legivel das execucoes capturadas."""
    glyphs = {
        "ok": "[ OK ]",
        "caught_issue": "[CAUGHT]",
        "requires_browser": "[BROWSER]",
        "error": "[ERRO]",
    }
    print("\n" + "=" * 64)
    print("Resumo da captura")
    print("=" * 64)
    for run in results:
        mark = glyphs.get(run["outcome"], "[?]")
        print(f"{mark:>9}  {run['id']:<16} {run.get('headline', '')}")
    print("=" * 64)


# ============================================================
# Orquestracao principal
# ============================================================


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta os argumentos de linha de comando do capturador."""
    parser = argparse.ArgumentParser(
        prog="capture_runs.py",
        description="Captura execucoes reais do AutoTarefas e gera runs.json + dashboard.html.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "examples" / "output",
        help="Diretorio de saida (default: examples/output).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Forca pular as etapas que dependem do navegador.",
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Nao copia os artefatos para docs/live/assets/.",
    )
    return parser.parse_args(argv)


def _bootstrap_environment(out: Path) -> Path:
    """Prepara o ambiente isolado (limpa a saida e fixa as variaveis de ambiente)."""
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    home = out / ".home"
    os.environ.update(
        {
            "AUTOTAREFAS_HOME": str(home),
            "ENVIRONMENT": "demo",
            "AUDIT_SECRET_KEY": DEMO_AUDIT_SECRET,
            "LOG_LEVEL": "WARNING",
            "NO_COLOR": "1",
            "AUTOTAREFAS_TELEGRAM_TOKEN": FAKE_TELEGRAM_TOKEN,
            "PYTHONUNBUFFERED": "1",
            "PYTHONUTF8": "1",
        }
    )
    return home


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada: sobe servidores, captura execucoes e grava os artefatos."""
    args = parse_args(argv)
    out: Path = args.output_dir.resolve()

    print("AutoTarefas Live System — capturador de execucoes")
    print(f"Raiz do projeto : {ROOT}")
    print(f"Saida           : {out}")

    _bootstrap_environment(out)
    specs = build_runs(out)

    if args.no_browser:
        browser_available, browser_note = False, "Desabilitado via --no-browser"
    else:
        browser_available, browser_note = detect_browser()
    print(f"Navegador       : {browser_note}")

    results: list[dict[str, Any]] = []
    with ExitStack() as stack:
        print("Subindo servidores de demonstracao...")
        src_ok = stack.enter_context(demo_server(port=SRC_PORT, data_dir=out / ".demo_src"))
        dst_ok = stack.enter_context(demo_server(port=DST_PORT, data_dir=out / ".demo_dst"))
        smtp_ok = stack.enter_context(smtp_server(port=SMTP_PORT, output_dir=out))
        health = {"src": src_ok, "dst": dst_ok, "smtp": smtp_ok}
        print(f"  origem(5555)={src_ok}  destino(5556)={dst_ok}  smtp(8025)={smtp_ok}")

        print("Capturando execucoes...")
        for spec in specs:
            run = capture_run(spec, server_health=health, browser_available=browser_available)
            results.append(run)
            print(f"  - {spec.run_id}: {run['outcome']}")

    # Auditoria so e lida depois que os subprocessos terminaram de gravar.
    entries = read_audit_entries()
    attach_audit(results, specs, entries)

    document = build_document(
        results,
        browser_available=browser_available,
        browser_note=browser_note,
    )
    runs_path = out / "runs.json"
    payload = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    runs_path.write_text(payload, encoding="utf-8")
    print(f"\nArtefato gravado: {_rel(runs_path)}")

    if not args.no_publish:
        published = publish_assets(out)
        for target in published:
            print(f"Publicado       : {_rel(target)}")

    print_summary(results)

    infra_errors = [run for run in results if run["outcome"] == "error"]
    if infra_errors:
        print(f"\nFALHA: {len(infra_errors)} execucao(oes) com erro de infraestrutura.")
        return 1
    print("\nOK: captura concluida (caught_issue e requires_browser sao desfechos esperados).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
