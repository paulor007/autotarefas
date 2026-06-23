"""
Gerador do HTML estatico do dashboard (apresentacao, somente leitura).

Subetapa 2: transforma os dados da camada ``reader`` (``AuditEntry`` e
``AuditSummary``) num documento HTML **autocontido** — CSS embutido, sem
assets externos, sem servidor e sem dependencia nova.

Principios:
- **Funcoes puras**: recebem os dados como argumento e devolvem ``str``.
  Nao acessam o banco (isso e papel do ``reader``), o que mantem as
  camadas separadas e a renderizacao trivial de testar.
- **Escape sempre**: todo valor dinamico passa por ``html.escape``; a
  classe CSS do badge de status vem de um conjunto fechado, nunca do
  dado cru — evita HTML injection.

Escopo enxuto: cabecalho + resumo (cards) + tabela de execucoes com
indicacao do input_hash (HMAC). Sem servidor e sem CLI (proximas etapas).

Destino deste arquivo:
    src/autotarefas/dashboard/renderer.py
"""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from autotarefas.dashboard.reader import AuditEntry, AuditSummary

# Statuses com cor propria no CSS; outros caem em "unknown".
_KNOWN_STATUSES = frozenset(
    {"success", "failure", "partial", "dry_run", "skipped"},
)

_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  background: #f5f6f8; color: #1a1a1a; line-height: 1.5;
}
.container { max-width: 1100px; margin: 0 auto; padding: 2rem 1.25rem; }
h1 { font-size: 1.5rem; margin: 0 0 0.25rem; }
.meta { color: #666; font-size: 0.875rem; margin: 0 0 1.5rem; }
.cards { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 1.5rem; }
.card {
  background: #fff; border: 1px solid #e3e5e8; border-radius: 10px;
  padding: 0.75rem 1rem; min-width: 110px;
}
.card .label {
  font-size: 0.72rem; color: #666; text-transform: uppercase;
  letter-spacing: 0.03em;
}
.card .value { font-size: 1.4rem; font-weight: 600; }
table {
  width: 100%; border-collapse: collapse; background: #fff;
  border: 1px solid #e3e5e8; border-radius: 10px; overflow: hidden;
  font-size: 0.9rem;
}
thead th {
  background: #2b2f36; color: #fff; text-align: left;
  padding: 0.6rem 0.75rem; font-weight: 600;
}
tbody td { padding: 0.55rem 0.75rem; border-top: 1px solid #eceef1; }
tbody tr:nth-child(even) { background: #fafbfc; }
.badge {
  display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px;
  font-size: 0.78rem; font-weight: 600;
}
.badge-success { background: #e6f4ea; color: #1e7e34; }
.badge-failure { background: #fdecea; color: #c0392b; }
.badge-partial { background: #fff4e5; color: #b9770e; }
.badge-dry_run { background: #eef2f7; color: #4a5568; }
.badge-skipped { background: #eef2f7; color: #4a5568; }
.badge-unknown { background: #eef2f7; color: #4a5568; }
.hash-yes { color: #1e7e34; font-weight: 600; }
.hash-no { color: #999; }
.mono {
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.85rem;
}
.empty {
  background: #fff; border: 1px solid #e3e5e8; border-radius: 10px;
  padding: 2rem; text-align: center; color: #666;
}
"""

_DASH = "\u2014"  # em dash (—), usado para valores ausentes
_ELLIPSIS = "\u2026"  # reticencias (…)


# ============================================================
# Helpers de renderizacao (privados, puros)
# ============================================================


def _card(label: str, value: str) -> str:
    return (
        '<div class="card">'
        f'<div class="label">{escape(label)}</div>'
        f'<div class="value">{escape(value)}</div>'
        "</div>"
    )


def _render_meta(summary: AuditSummary, generated_at: datetime | None) -> str:
    parts: list[str] = []
    if generated_at is not None:
        parts.append(f"Gerado em {generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    plural = "execucao" if summary.total == 1 else "execucoes"
    parts.append(f"{summary.total} {plural}")
    return f'<p class="meta">{escape(" \u00b7 ".join(parts))}</p>'


def _render_summary(summary: AuditSummary) -> str:
    cards = [_card("Total", str(summary.total))]
    cards.extend(_card(status, str(count)) for status, count in sorted(summary.by_status.items()))
    return f'<section class="cards">{"".join(cards)}</section>'


def _status_badge(status: str) -> str:
    css = status if status in _KNOWN_STATUSES else "unknown"
    return f'<span class="badge badge-{css}">{escape(status)}</span>'


def _hash_indicator(input_hash: str) -> str:
    if input_hash:
        short = escape(input_hash[:12])
        full = escape(input_hash)
        return f'<span class="hash-yes mono" title="{full}">{short}{_ELLIPSIS}</span>'
    return f'<span class="hash-no">{_DASH}</span>'


def _render_row(entry: AuditEntry) -> str:
    when = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") if entry.timestamp else _DASH
    duration = f"{entry.duration_ms} ms" if entry.duration_ms is not None else _DASH
    return (
        "<tr>"
        f"<td>{escape(when)}</td>"
        f"<td>{escape(entry.task_name)}</td>"
        f"<td>{_status_badge(entry.status)}</td>"
        f"<td>{escape(duration)}</td>"
        f"<td>{entry.rows_affected}</td>"
        f"<td>{entry.rows_failed}</td>"
        f"<td>{_hash_indicator(entry.input_hash)}</td>"
        f"<td>{escape(entry.environment)}</td>"
        "</tr>"
    )


def _render_table(entries: Sequence[AuditEntry]) -> str:
    if not entries:
        return '<div class="empty">Nenhuma execucao registrada.</div>'
    header = (
        "<thead><tr>"
        "<th>Quando</th><th>Task</th><th>Status</th><th>Duracao</th>"
        "<th>OK</th><th>Falhas</th><th>Input (HMAC)</th><th>Ambiente</th>"
        "</tr></thead>"
    )
    rows = "".join(_render_row(entry) for entry in entries)
    return f"<table>{header}<tbody>{rows}</tbody></table>"


# ============================================================
# API publica
# ============================================================


def render_dashboard(
    entries: Sequence[AuditEntry],
    summary: AuditSummary,
    *,
    title: str = "AutoTarefas \u2014 Painel de Auditoria",
    generated_at: datetime | None = None,
) -> str:
    """
    Gera o HTML estatico autocontido do dashboard.

    Args:
        entries: execucoes a listar (ja lidas pela camada ``reader``).
        summary: resumo agregado (total e contagem por status).
        title: titulo exibido e usado na aba do navegador.
        generated_at: se fornecido, exibe a data/hora de geracao. Mantido
            como parametro (em vez de ``datetime.now()`` interno) para a
            renderizacao ser deterministica e testavel.

    Returns:
        Documento HTML completo, em uma unica string.
    """
    return (
        "<!DOCTYPE html>\n"
        '<html lang="pt-br">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        '<main class="container">\n'
        f"<h1>{escape(title)}</h1>\n"
        f"{_render_meta(summary, generated_at)}\n"
        f"{_render_summary(summary)}\n"
        f"{_render_table(entries)}\n"
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )


__all__ = ["render_dashboard"]
