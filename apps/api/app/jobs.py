"""Registro em memoria dos jobs de execucao (Live-1.3).

Cada POST /api/run cria um Job com uma fila de linhas (stdout ao vivo) e o
resultado consolidado. O registro e efemero por design: reiniciar o servidor
zera tudo, e os jobs expiram junto com o TTL do workspace.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .engine import RunResult


def _new_queue() -> asyncio.Queue[str | None]:
    """Fila de linhas do stdout; o sentinela None marca o fim do stream."""
    return asyncio.Queue()


#: Estados da jornada de planilhas (1.8B-2B). Sao distintos do `status` do
#: job, que fala da EXECUCAO; estes falam de onde a pessoa esta na jornada.
JourneyStatus = Literal[
    "analyzing",
    "needs_selection",
    "analysis_ready",
    "rejected_file",
    "schema_ready",
    "validating",
    "completed",
    "completed_with_issues",
    "invalid_configuration",
    "technical_failure",
    "timed_out",
]


@dataclass
class Journey:
    """
    O que o visitante ja decidiu na jornada de planilhas.

    Vive dentro do Job, entao morre com ele no TTL — nada de estado global
    paralelo e nada indexado por nome de arquivo. Guarda CAMINHOS internos e
    o resultado da analise; a API nunca devolve esses caminhos.

    `analysis` e o payload estruturado (dict) que o servico da 1.8B-1
    produziu. O DataFrame NAO fica aqui: ele seria uma copia grande e sem
    uso — a validacao le o arquivo de novo, no subprocesso isolado.
    """

    status: JourneyStatus
    source_path: Path
    """Arquivo do visitante, dentro de `<workspace>/in/`. Nunca alterado."""
    analysis: dict[str, Any] = field(default_factory=dict)
    preview: str = ""
    ambiguities: list[dict[str, Any]] = field(default_factory=list)
    sheet: str | None = None
    """Aba CONFIRMADA pelo visitante (None = deixar o leitor detectar)."""
    header_row: int | None = None
    """Linha de cabecalho CONFIRMADA (None = deixar o leitor detectar)."""
    sheet_options: list[str] = field(default_factory=list)
    """Abas que a analise ofereceu — a selecao e validada contra esta lista."""
    header_options: list[int] = field(default_factory=list)
    schema_path: Path | None = None
    """Schema confirmado, em `<workspace>/config/schema_confirmado.yaml`."""
    schema_origin: str | None = None
    """"suggested", "profile" ou "uploaded" — de onde o schema confirmado veio."""
    apply_cleaning: bool = False
    """Correcoes seguras CONFIRMADAS na revisao (modo limpeza na execucao)."""
    flag_duplicate_rows: bool = True
    """Linhas 100% repetidas sao SEMPRE verificadas (contrato do Card 01)."""
    presentation_verdict: str = ""
    """'organizada', 'melhoravel' ou 'ambigua' — o que a analise concluiu."""
    organize: bool = False
    """Organizacao visual CONFIRMADA na revisao."""
    sort_column: str = ""
    sort_desc: bool = False
    indicator_request: tuple[str, str, str] = ("", "", "")
    dashboard: bool = False
    """(valor, categoria, data) CONFIRMADOS para o resumo. Vazio = sem resumo."""
    profile_id: str | None = None
    """Perfil que originou o schema, quando a origem foi um perfil."""
    profile_version: int | None = None
    profile_mapping: dict[str, str] = field(default_factory=dict)
    """Mapeamento EFETIVAMENTE aplicado (campo conceitual -> coluna real)."""
    profile_omitted: list[str] = field(default_factory=list)
    """Campos opcionais que o visitante decidiu nao usar."""
    """"suggested" ou "uploaded" — de onde o schema confirmado veio."""
    rejection: str | None = None


@dataclass
class Job:
    """Estado de uma execucao em andamento ou concluida."""

    token: str
    automation_id: str
    workspace: Path
    status: str = "running"  # running | ok | caught_issue | error | timeout
    created_at: float = field(default_factory=time.time)
    queue: asyncio.Queue[str | None] = field(default_factory=_new_queue)
    lines: list[str] = field(default_factory=list)
    result: RunResult | None = None
    #: Estado da jornada de planilhas. None nos jobs das automacoes antigas.
    journey: Journey | None = None


_jobs: dict[str, Job] = {}


def create(token: str, automation_id: str, workspace: Path) -> Job:
    """Registra um novo job e o devolve."""
    job = Job(token=token, automation_id=automation_id, workspace=workspace)
    _jobs[token] = job
    return job


def get(token: str) -> Job | None:
    """Recupera um job pelo token (None se nao existir)."""
    return _jobs.get(token)


def active_count() -> int:
    """Quantos jobs ainda estao executando."""
    return sum(1 for job in _jobs.values() if job.status == "running")


def sweep_expired(ttl_min: int) -> int:
    """Remove jobs mais velhos que o TTL. Retorna quantos sairam."""
    ttl_seconds = ttl_min * 60
    now = time.time()
    expired = [token for token, job in _jobs.items() if now - job.created_at > ttl_seconds]
    for token in expired:
        _jobs.pop(token, None)
    return len(expired)
