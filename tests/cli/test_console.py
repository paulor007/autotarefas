"""Testes para autotarefas.cli.console."""

from __future__ import annotations

import pytest

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext


class TestConsoleInfo:
    """Testes do método info()."""

    def test_info_aparece_no_modo_normal(self, capsys: pytest.CaptureFixture[str]) -> None:
        c = Console()
        c.info("mensagem teste")
        captured = capsys.readouterr()
        assert "mensagem teste" in captured.out

    def test_info_suprime_com_quiet_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = CLIContext(quiet=1)
        c = Console(ctx)
        c.info("nao deve aparecer")
        captured = capsys.readouterr()
        assert "nao deve aparecer" not in captured.out

    def test_info_suprime_com_quiet_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = CLIContext(quiet=2)
        c = Console(ctx)
        c.info("nao deve aparecer")
        captured = capsys.readouterr()
        assert "nao deve aparecer" not in captured.out


class TestConsoleSuccess:
    """Testes do método success()."""

    def test_success_mostra_msg(self, capsys: pytest.CaptureFixture[str]) -> None:
        c = Console()
        c.success("tudo certo")
        captured = capsys.readouterr()
        assert "tudo certo" in captured.out

    def test_success_tem_marker_ok(self, capsys: pytest.CaptureFixture[str]) -> None:
        c = Console()
        c.success("ok")
        captured = capsys.readouterr()
        assert "OK" in captured.out

    def test_success_suprime_com_quiet(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = CLIContext(quiet=1)
        c = Console(ctx)
        c.success("nao deve aparecer")
        captured = capsys.readouterr()
        assert "nao deve aparecer" not in captured.out


class TestConsoleWarning:
    """Testes do método warning()."""

    def test_warning_mostra_msg(self, capsys: pytest.CaptureFixture[str]) -> None:
        c = Console()
        c.warning("atencao!")
        captured = capsys.readouterr()
        assert "atencao!" in captured.out

    def test_warning_tem_marker(self, capsys: pytest.CaptureFixture[str]) -> None:
        c = Console()
        c.warning("alerta")
        captured = capsys.readouterr()
        assert "AVISO" in captured.out

    def test_warning_aparece_com_quiet_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        """-q (quiet=1) ainda mostra warnings."""
        ctx = CLIContext(quiet=1)
        c = Console(ctx)
        c.warning("aviso importante")
        captured = capsys.readouterr()
        assert "aviso importante" in captured.out

    def test_warning_suprime_com_quiet_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        """-qq (quiet=2) suprime warnings."""
        ctx = CLIContext(quiet=2)
        c = Console(ctx)
        c.warning("nao deve aparecer")
        captured = capsys.readouterr()
        assert "nao deve aparecer" not in captured.out


class TestConsoleError:
    """Testes do método error()."""

    def test_error_mostra_msg_no_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        c = Console()
        c.error("falhou")
        captured = capsys.readouterr()
        # Error vai pro stderr (convenção Unix)
        assert "falhou" in captured.err

    def test_error_tem_marker(self, capsys: pytest.CaptureFixture[str]) -> None:
        c = Console()
        c.error("erro")
        captured = capsys.readouterr()
        assert "ERRO" in captured.err

    def test_error_aparece_mesmo_com_quiet_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Errors sempre aparecem, mesmo com -qq."""
        ctx = CLIContext(quiet=2)
        c = Console(ctx)
        c.error("sempre aparece")
        captured = capsys.readouterr()
        assert "sempre aparece" in captured.err


class TestConsoleDebug:
    """Testes do método debug()."""

    def test_debug_nao_aparece_modo_normal(self, capsys: pytest.CaptureFixture[str]) -> None:
        c = Console()
        c.debug("debug interno")
        captured = capsys.readouterr()
        assert "debug interno" not in captured.out

    def test_debug_nao_aparece_verbose_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        """-v (verbose=1) ainda não mostra debug."""
        ctx = CLIContext(verbose=1)
        c = Console(ctx)
        c.debug("nao deve aparecer")
        captured = capsys.readouterr()
        assert "nao deve aparecer" not in captured.out

    def test_debug_aparece_verbose_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        """-vv (verbose=2) mostra debug."""
        ctx = CLIContext(verbose=2)
        c = Console(ctx)
        c.debug("debug visivel")
        captured = capsys.readouterr()
        assert "debug visivel" in captured.out

    def test_debug_aparece_verbose_3(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = CLIContext(verbose=3)
        c = Console(ctx)
        c.debug("trace")
        captured = capsys.readouterr()
        assert "trace" in captured.out


class TestConsoleAnnounceAction:
    """Testes do método announce_action()."""

    def test_announce_normal(self, capsys: pytest.CaptureFixture[str]) -> None:
        c = Console()
        c.announce_action("Processando 10 arquivos")
        captured = capsys.readouterr()
        assert "Processando 10 arquivos" in captured.out
        assert "DRY-RUN" not in captured.out

    def test_announce_dry_run_adiciona_prefixo(self, capsys: pytest.CaptureFixture[str]) -> None:
        ctx = CLIContext(dry_run=True)
        c = Console(ctx)
        c.announce_action("Processando 10 arquivos")
        captured = capsys.readouterr()
        assert "DRY-RUN" in captured.out
        assert "nao executado" in captured.out


class TestConsoleSemContext:
    """Testes do Console sem ctx (defaults)."""

    def test_console_sem_ctx_usa_defaults(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Console() sem args usa CLIContext default."""
        c = Console()
        c.info("hello")
        captured = capsys.readouterr()
        assert "hello" in captured.out
