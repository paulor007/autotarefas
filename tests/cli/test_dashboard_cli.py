"""
Testes do comando CLI ``autotarefas dashboard``.

ESTRATEGIA:
- CliRunner via grupo ``cli`` principal.
- Usa o audit DB isolado por teste (fixture autouse do conftest): grava
  com ``audit.record`` e roda o comando, que le pela camada ``reader``
  (mesmo singleton, mesmo banco temporario).
- Verifica o arquivo HTML gerado, a mensagem e a opcao ``--open`` (mock,
  sem abrir navegador de verdade).

Cobertura:
- --help
- gera HTML (arquivo criado; conteudo com resumo + tabela)
- caminho de saida customizado (cria diretorios pais)
- audit vazio (gera dashboard vazio + aviso)
- nao vaza dados sensiveis (so o input_hash, nunca o input cru)
- --open chama webbrowser.open (mock)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from click.testing import CliRunner

from autotarefas.cli.main import cli
from autotarefas.core.audit import audit

if TYPE_CHECKING:
    from pathlib import Path


def _record(status: str = "success", task_name: str = "validate", **kw: Any) -> None:
    """Helper: grava uma execucao no audit DB isolado do teste."""
    audit.record(
        task_name=task_name,
        status=status,
        started_at=datetime.now(UTC),
        duration_ms=10,
        **kw,
    )


class TestDashboardCommand:
    """Comando `autotarefas dashboard`."""

    def test_help(self) -> None:
        result = CliRunner().invoke(cli, ["dashboard", "--help"])

        assert result.exit_code == 0
        assert "dashboard" in result.output.lower()

    def test_gera_html(self, tmp_path: Path) -> None:
        _record(task_name="backup", status="success")
        _record(task_name="validate", status="failure")
        out = tmp_path / "dash.html"

        result = CliRunner().invoke(cli, ["dashboard", "-o", str(out)])

        assert result.exit_code == 0
        assert out.exists()
        html = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html
        assert "<table>" in html  # tabela de execucoes
        assert "Total" in html  # resumo
        assert "backup" in html
        assert "validate" in html

    def test_caminho_customizado(self, tmp_path: Path) -> None:
        _record()
        out = tmp_path / "sub" / "dir" / "audit.html"

        result = CliRunner().invoke(cli, ["dashboard", "--output", str(out)])

        assert result.exit_code == 0
        assert out.exists()  # diretorios pais criados
        assert "Dashboard gerado em" in result.output

    def test_audit_vazio(self, tmp_path: Path) -> None:
        out = tmp_path / "dash.html"

        result = CliRunner().invoke(cli, ["dashboard", "-o", str(out)])

        assert result.exit_code == 0
        assert out.exists()
        html = out.read_text(encoding="utf-8")
        assert "Nenhuma execucao registrada." in html
        assert "vazio" in result.output.lower()

    def test_nao_vaza_dados_sensiveis(self, tmp_path: Path) -> None:
        # O audit grava apenas o HMAC do input; o input cru nunca aparece.
        _record(input_data={"senha": "secreta123", "token": "xyz789"})
        out = tmp_path / "dash.html"

        result = CliRunner().invoke(cli, ["dashboard", "-o", str(out)])

        assert result.exit_code == 0
        html = out.read_text(encoding="utf-8")
        assert "secreta123" not in html
        assert "xyz789" not in html

    def test_open_chama_webbrowser(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _record()
        chamado: dict[str, str] = {}

        def fake_open(url: str, *args: Any, **kwargs: Any) -> bool:
            chamado["url"] = url
            return True

        monkeypatch.setattr(
            "autotarefas.cli.commands.dashboard.webbrowser.open",
            fake_open,
        )
        out = tmp_path / "dash.html"

        result = CliRunner().invoke(cli, ["dashboard", "-o", str(out), "--open"])

        assert result.exit_code == 0
        assert chamado.get("url", "").startswith("file://")
        assert chamado["url"].endswith("dash.html")
