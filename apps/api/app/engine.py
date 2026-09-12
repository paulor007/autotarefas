"""Motor de execucao: workspace efemero -> AutoTarefas real -> artefatos.

Live-1.3: execucao assincrona com stdout transmitido linha a linha (SSE). Cada
execucao roda num diretorio uuid isolado, com AUTOTAREFAS_HOME proprio, comando
montado por receita (sem shell, sem entrada do usuario como argumento), timeout
com kill, limites de stream e bloqueio de egress (defesa em profundidade).
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import hashlib
import os
import re
import shutil
import subprocess  # nosec B404
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from . import recipes, sanitize
from .config import settings

if TYPE_CHECKING:
    from .jobs import Job

# So estas automacoes executam ao vivo (mantidas da Live-1.2).
ACTIVE_AUTOMATIONS: tuple[str, ...] = (
    "validate",
    "backup",
    "organize",
    "extract_web",
    "extract_api",
    "send_api",
    "send_telegram",
    "sync_api",
    "send_email",
    "report",
    "dashboard",
)

_TIMEOUT_EXIT = 124

#: Espera maxima pela thread leitora depois que o processo morreu. Com o
#: stdout fechado ela sai de imediato; o teto evita travar para sempre.
_READER_JOIN_TIMEOUT_S = 5.0


def run_timeout_s() -> float:
    """
    Teto de tempo de uma execucao.

    E uma funcao, e nao `settings.run_timeout_s` direto, porque `settings` e
    um dataclass FROZEN: sem este ponto nao ha como um teste exercitar o
    caminho de timeout — que e justamente onde a thread leitora continuava
    viva depois de o processo ser morto.
    """
    return float(settings.run_timeout_s)


_VALIDATE_FAIL_EXIT = 1

#: `backup` sai 1 quando CONCLUIU e algum arquivo ficou de fora (travado pelo
#: Excel, sem permissao). O pacote existe e presta; chamar isso de erro
#: tecnico esconderia um backup bom e assustaria sem motivo.
_BACKUP_PARTIAL_EXIT = 1
_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
_DEAD_PROXY = "http://127.0.0.1:9"


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
    """Resultado consolidado de uma execucao real."""

    token: str
    outcome: str
    exit_code: int
    duration_ms: int
    stdout: str
    artifacts: list[Artifact] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    """
    O que a execucao precisa dizer alem do arquivo gerado.

    Hoje: os arquivos que NAO entraram no backup. Sem isto, o Live mostraria
    um pacote com cara de completo, e a ausencia so apareceria dentro do
    manifesto — que ninguem abre a tempo.
    """

    def as_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "outcome": self.outcome,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "stdout": self.stdout,
            "artifacts": [a.as_dict(self.token) for a in self.artifacts],
            "notes": self.notes,
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
            # A CLI escreve acentos. Sem isto o Python usa a pagina de codigo
            # do Windows no cano do subprocesso e "opcao" chega quebrado.
            "PYTHONIOENCODING": "utf-8",
            # A saida vai para uma TELA, nao para um terminal. A CLI usa isto
            # para nao imprimir instrucao de linha de comando nem aviso que so
            # faz sentido quando a pessoa escolheu origem e destino.
            "AUTOTAREFAS_UI": "web",
            # Sem isto o console quebra em 80 colunas e parte o caminho do
            # workspace em duas linhas — e um caminho partido escapa do
            # sanitizador, que trabalha linha a linha. Foi assim que o caminho
            # interno apareceu na tela.
            "COLUMNS": "400",
            # Token fake do bot: usado so contra o mock local; evita prompt que travaria o processo.
            "AUTOTAREFAS_TELEGRAM_TOKEN": "demo-fake-token-0000",  # nosec B105
        }
    )
    if settings.egress_lockdown:
        # Defesa em profundidade: o robo so fala com mocks locais; saida externa morre.
        env.update(
            {
                "HTTP_PROXY": _DEAD_PROXY,
                "HTTPS_PROXY": _DEAD_PROXY,
                "http_proxy": _DEAD_PROXY,
                "https_proxy": _DEAD_PROXY,
                "NO_PROXY": "127.0.0.1,localhost",
                "no_proxy": "127.0.0.1,localhost",
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
    """Empacota o resultado quando a automacao gera uma pasta (organize, validate)."""
    if automation_id == "organize":
        organized = workspace / "out" / "organizado"
        if organized.is_dir():
            shutil.make_archive(
                str(workspace / "out" / "organizado"), "zip", root_dir=str(organized)
            )
            shutil.rmtree(organized, ignore_errors=True)
        return

    if automation_id == "validate":
        # O pacote de evidencias da 1.7 e uma PASTA em out/. Vira um unico
        # .zip, pelo mesmo motivo do organize: `_collect` so expoe arquivos
        # diretos de out/, e o download so aceita nome simples (sem barras).
        # Sem isto, o pacote inteiro ficaria invisivel para o visitante.
        pacote = workspace / "out" / "pacote_execucao"
        if pacote.is_dir():
            shutil.make_archive(str(pacote), "zip", root_dir=str(pacote))
            shutil.rmtree(pacote, ignore_errors=True)
        return


#: Nome do manifesto dentro do pacote de backup (contrato do nucleo).
_MANIFEST_NAME = "MANIFESTO.csv"

#: Posicao do motivo na linha do manifesto.
_COLUNA_MOTIVO = 5


def _ressalvas_do_backup(out_dir: Path) -> list[str]:
    """
    Le o manifesto do pacote e devolve o que ficou de fora.

    A fonte e o ARTEFATO entregue, nao o texto do terminal: o que a tela
    afirma tem de sair do arquivo, senao uma troca de mensagem na CLI
    silenciaria a tela sem ninguem perceber.
    """
    pacotes = sorted(out_dir.glob("*.zip"))
    if not pacotes:
        return []
    try:
        with zipfile.ZipFile(pacotes[0]) as zf:
            if _MANIFEST_NAME not in zf.namelist():
                return []
            texto = zf.read(_MANIFEST_NAME).decode("utf-8", "replace")
    except (zipfile.BadZipFile, OSError):  # pragma: no cover - pacote ilegivel
        return []

    ressalvas: list[str] = []
    for linha in csv.reader(texto.splitlines()):
        if linha[:1] != ["NAO_LIDO"]:
            continue
        motivo = linha[_COLUNA_MOTIVO] if len(linha) > _COLUNA_MOTIVO else ""
        ressalvas.append(f"{linha[1]}: {motivo}" if motivo else linha[1])
    return ressalvas


def _should_postprocess(automation_id: str, exit_code: int, *, timed_out: bool) -> bool:
    """
    Decide se vale pos-processar a saida (zipar pastas geradas).

    A matriz, e o porque de cada linha:

        timeout                      -> NAO. O processo foi morto no meio; o
                                        que existe em out/ esta incompleto e
                                        empacotar isso entregaria evidencia
                                        pela metade como se fosse completa.
        exit 0                       -> SIM. Terminou bem, saida completa.
        validate exit 1              -> SIM. `caught_issue`: a validacao rodou
                                        inteira e ACHOU problemas nos dados.
                                        E justamente aqui que o pacote de
                                        evidencias mais importa.
        validate exit 2              -> NAO. Erro de USO/configuracao (schema
                                        invalido, arquivo recusado). Nao houve
                                        validacao; nao ha evidencia a empacotar.
        backup exit 1                -> SIM. O pacote foi gerado inteiro; o que
                                        mudou e que algum arquivo nao pode ser
                                        lido e virou ressalva.
        outra automacao, exit != 0   -> NAO. Falha tecnica: a saida nao e
                                        confiavel.
    """
    if timed_out:
        return False
    if exit_code == 0:
        return True
    # Saidas diferentes de zero que ainda deixam resultado completo.
    return _concluiu_com_ressalva(automation_id, exit_code)


def _concluiu_com_ressalva(automation_id: str, exit_code: int) -> bool:
    """A automacao terminou o trabalho, mas tem algo que a pessoa precisa ver."""
    if automation_id == "validate":
        return exit_code == _VALIDATE_FAIL_EXIT
    return automation_id == "backup" and exit_code == _BACKUP_PARTIAL_EXIT


def _outcome(automation_id: str, exit_code: int) -> str:
    if exit_code == 0:
        return "ok"
    if _concluiu_com_ressalva(automation_id, exit_code):
        return "caught_issue"
    return "error"


def _start_process(argv: list[str], workspace: Path) -> subprocess.Popen[str]:
    # Comando montado por receita (allowlist), sem shell nem entrada do usuario como argumento.
    return subprocess.Popen(  # nosec B603  # noqa: S603
        argv,
        cwd=str(workspace),
        env=_env_for(workspace),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )


def _pump(
    proc: subprocess.Popen[str],
    job: Job,
    loop: asyncio.AbstractEventLoop,
    done: asyncio.Event,
) -> None:
    """
    Le o stdout do processo (em thread) e enfileira as linhas sanitizadas.

    Todo contato com o event loop passa por `_no_loop`, porque a thread pode
    perder a corrida com o encerramento do loop. A coordenacao principal e o
    `join` em `run_streaming`; isto aqui e a rede de seguranca para o
    intervalo em que o loop ja fechou e a thread ainda nao percebeu.
    """

    def _no_loop(callback: Any, *args: Any) -> None:
        """Agenda no loop, tolerando que ele ja tenha fechado."""
        # Loop fechado: nao ha mais quem consuma o SSE. Perder a linha aqui e
        # correto — o resultado consolidado ja vive em `job.lines`.
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(callback, *args)

    stdout = proc.stdout
    if stdout is None:
        _no_loop(done.set)
        return
    streamed_bytes = 0
    truncated = False
    try:
        for raw in stdout:
            line = sanitize.sanitize(raw, job.workspace, settings.repo_root)
            if not line:
                continue
            if (
                len(job.lines) >= settings.max_stream_lines
                or streamed_bytes >= settings.max_stream_bytes
            ):
                if not truncated:
                    truncated = True
                    warn = "... saida truncada (limite de stream atingido) ..."
                    job.lines.append(warn)
                    _no_loop(job.queue.put_nowait, warn)
                continue
            streamed_bytes += len(line)
            job.lines.append(line)
            _no_loop(job.queue.put_nowait, line)
    finally:
        stdout.close()
        _no_loop(done.set)


async def _reset_demo_state(url: str) -> None:
    """
    Pre-hook: zera o estado do sistema de demonstracao antes da execucao.

    Sem isso, a demo degrada sozinha (cadastros da execucao anterior
    respondem 409 em cascata). Falha do reset nao derruba a execucao —
    se o mock estiver fora do ar, o proprio run reportara o erro real.
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(url)
    except httpx.HTTPError:
        pass  # nosec B110 - reset e melhor-esforco; o run reporta erros reais


def refresh_artifacts(job: Job) -> RunResult | None:
    """
    Relista os artefatos de `out/` sobre o resultado já existente.

    Existe para o pós-processamento da jornada de planilhas: os artefatos
    principais (planilha organizada, relatório) são montados EM PROCESSO,
    depois que o subprocesso terminou, e precisam entrar na mesma lista de
    downloads — com hash e tamanho reais, como todos os outros.
    """
    anterior = job.result
    if anterior is None:  # pragma: no cover - so apos uma execucao
        return None
    atualizado = RunResult(
        token=anterior.token,
        outcome=anterior.outcome,
        exit_code=anterior.exit_code,
        duration_ms=anterior.duration_ms,
        stdout=anterior.stdout,
        artifacts=_collect(job.workspace / "out"),
    )
    job.result = atualizado
    return atualizado


async def run_streaming(
    automation_id: str,
    inputs: list[Path],
    job: Job,
    journey: recipes.JourneyOptions | None = None,
) -> RunResult:
    """Executa a automacao de verdade, transmitindo o stdout linha a linha."""
    reset = recipes.reset_url(automation_id)
    if reset is not None:
        await _reset_demo_state(reset)
    recipes.seed_workspace(automation_id, job.workspace)

    argv = recipes.build_argv(automation_id, job.workspace, inputs, journey)
    loop = asyncio.get_running_loop()
    start = time.monotonic()
    timed_out = False

    proc = _start_process(argv, job.workspace)
    done = asyncio.Event()
    reader = threading.Thread(target=_pump, args=(proc, job, loop, done), daemon=True)
    reader.start()

    try:
        await asyncio.wait_for(done.wait(), timeout=run_timeout_s())
    except TimeoutError:
        timed_out = True
        proc.kill()

    await loop.run_in_executor(None, proc.wait)

    # A thread leitora TEM que terminar antes de sairmos: enquanto ela vive,
    # pode chamar `loop.call_soon_threadsafe`, e se o loop ja tiver fechado
    # (fim dos testes, shutdown do app) isso estoura em
    # "RuntimeError: Event loop is closed" DEPOIS do resumo do pytest —
    # ruido que esconde falha real. Com o processo morto, o stdout fecha e a
    # thread sai sozinha; o timeout aqui e so para nao travar para sempre.
    await loop.run_in_executor(None, reader.join, _READER_JOIN_TIMEOUT_S)

    exit_code = _TIMEOUT_EXIT if timed_out else (proc.returncode or 0)
    duration_ms = int((time.monotonic() - start) * 1000)

    if _should_postprocess(automation_id, exit_code, timed_out=timed_out):
        _postprocess(automation_id, job.workspace)

    artifacts = _collect(job.workspace / "out")
    outcome = "timeout" if timed_out else _outcome(automation_id, exit_code)
    notes = _ressalvas_do_backup(job.workspace / "out") if automation_id == "backup" else []
    result = RunResult(
        token=job.token,
        outcome=outcome,
        exit_code=exit_code,
        duration_ms=duration_ms,
        stdout="\n".join(job.lines),
        artifacts=artifacts,
        notes=notes,
    )
    job.result = result
    job.status = outcome
    job.queue.put_nowait(None)
    return result


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
