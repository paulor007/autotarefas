"""
Testes do gerador de HTML do dashboard (``dashboard.renderer``).

Testes puros: constroem ``AuditEntry``/``AuditSummary`` em memoria e
verificam a string HTML resultante. Sem banco, sem servidor e sem
navegador (nenhum import de Playwright/BrowserSession).

Cobertura:
- HTML com resumo (cards de total e por status)
- HTML com tabela de execucoes
- escape de valores perigosos (anti-injection)
- lista vazia
- indicador de presenca/ausencia do input_hash
- metadados opcionais (generated_at)

Destino deste arquivo:
    tests/dashboard/test_renderer.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from autotarefas.dashboard import (
    AuditEntry,
    AuditSummary,
    render_dashboard,
)


def _entry(**kw: Any) -> AuditEntry:
    """Helper: AuditEntry com defaults sensatos, sobrescritos por kwargs."""
    base: dict[str, Any] = {
        "task_name": "validate",
        "status": "success",
        "timestamp": datetime(2026, 6, 20, 14, 30, 0, tzinfo=UTC),
        "duration_ms": 12,
        "rows_affected": 5,
        "rows_failed": 0,
        "error_message": None,
        "user": "paulo",
        "environment": "dev",
        "input_hash": "a" * 64,
    }
    base.update(kw)
    return AuditEntry(**base)


# ============================================================
# Resumo
# ============================================================


class TestResumo:
    """O resumo aparece como cards (total e por status)."""

    def test_html_com_resumo(self) -> None:
        entries = [
            _entry(status="success"),
            _entry(status="success"),
            _entry(status="failure"),
        ]
        summary = AuditSummary(total=3, by_status={"success": 2, "failure": 1})

        html = render_dashboard(entries, summary)

        assert "<!DOCTYPE html>" in html
        assert "Total" in html
        assert '<div class="value">3</div>' in html  # total
        assert '<div class="value">2</div>' in html  # success
        assert '<div class="value">1</div>' in html  # failure
        assert "success" in html


# ============================================================
# Tabela de execucoes
# ============================================================


class TestTabela:
    """As execucoes viram linhas de tabela."""

    def test_html_com_tabela(self) -> None:
        entries = [
            _entry(task_name="backup"),
            _entry(task_name="organize"),
        ]
        summary = AuditSummary(total=2, by_status={"success": 2})

        html = render_dashboard(entries, summary)

        assert "<table>" in html
        assert "backup" in html
        assert "organize" in html
        # uma linha de cabecalho + duas de dados
        assert html.count("<tr>") == 3

    def test_status_vira_badge(self) -> None:
        html = render_dashboard(
            [_entry(status="failure")],
            AuditSummary(total=1, by_status={"failure": 1}),
        )

        assert 'class="badge badge-failure"' in html


# ============================================================
# Escape / anti-injection
# ============================================================


class TestEscape:
    """Valores dinamicos sao escapados; nada de HTML cru do dado."""

    def test_escape_valores_perigosos(self) -> None:
        perigoso = "<script>alert('xss')</script>"
        html = render_dashboard(
            [_entry(task_name=perigoso, environment=perigoso)],
            AuditSummary(total=1, by_status={"success": 1}),
        )

        # o template nao emite <script>; logo, se aparecesse, seria do dado
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_escape_em_status(self) -> None:
        # status fora do conjunto conhecido cai em badge-unknown, mas o
        # texto continua escapado
        html = render_dashboard(
            [_entry(status="<b>x</b>")],
            AuditSummary(total=1, by_status={"<b>x</b>": 1}),
        )

        assert "<b>x</b>" not in html
        assert "&lt;b&gt;x&lt;/b&gt;" in html
        assert 'class="badge badge-unknown"' in html


# ============================================================
# Lista vazia
# ============================================================


class TestListaVazia:
    """Sem execucoes: mensagem amigavel, sem tabela, sem quebrar."""

    def test_lista_vazia(self) -> None:
        html = render_dashboard([], AuditSummary(total=0, by_status={}))

        assert "Nenhuma execucao registrada." in html
        assert "<table>" not in html
        assert '<div class="value">0</div>' in html  # total = 0


# ============================================================
# Indicador de input_hash
# ============================================================


class TestIndicadorInputHash:
    """A coluna do HMAC indica presenca ou ausencia do input_hash."""

    def test_input_hash_presente(self) -> None:
        html = render_dashboard(
            [_entry(input_hash="abcdef0123456789" * 4)],
            AuditSummary(total=1, by_status={"success": 1}),
        )

        assert 'class="hash-yes' in html
        assert "abcdef012345" in html  # primeiros 12 chars

    def test_input_hash_ausente(self) -> None:
        html = render_dashboard(
            [_entry(input_hash="")],
            AuditSummary(total=1, by_status={"success": 1}),
        )

        assert 'class="hash-no"' in html
        assert 'class="hash-yes' not in html


# ============================================================
# Metadados opcionais
# ============================================================


class TestMetadados:
    """generated_at e opcional e deterministico."""

    def test_com_generated_at(self) -> None:
        html = render_dashboard(
            [],
            AuditSummary(total=0, by_status={}),
            generated_at=datetime(2026, 6, 21, 9, 0, 0, tzinfo=UTC),
        )

        assert "Gerado em 2026-06-21 09:00:00" in html

    def test_sem_generated_at(self) -> None:
        html = render_dashboard([], AuditSummary(total=0, by_status={}))

        assert "Gerado em" not in html
