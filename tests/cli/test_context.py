"""Testes para autotarefas.cli.context."""

from __future__ import annotations

import pytest

from autotarefas.cli.context import CLIContext


class TestCLIContextDefaults:
    """Testes dos valores default."""

    def test_verbose_default_zero(self) -> None:
        ctx = CLIContext()
        assert ctx.verbose == 0

    def test_quiet_default_zero(self) -> None:
        ctx = CLIContext()
        assert ctx.quiet == 0

    def test_dry_run_default_false(self) -> None:
        ctx = CLIContext()
        assert ctx.dry_run is False

    def test_yes_default_false(self) -> None:
        ctx = CLIContext()
        assert ctx.yes is False


class TestCLIContextLogLevel:
    """Testes da propriedade log_level."""

    def test_default_info(self) -> None:
        ctx = CLIContext()
        assert ctx.log_level == "INFO"

    def test_verbose_1_info(self) -> None:
        """-v não muda do default (já é INFO)."""
        ctx = CLIContext(verbose=1)
        assert ctx.log_level == "INFO"

    def test_verbose_2_debug(self) -> None:
        ctx = CLIContext(verbose=2)
        assert ctx.log_level == "DEBUG"

    def test_verbose_3_trace(self) -> None:
        ctx = CLIContext(verbose=3)
        assert ctx.log_level == "TRACE"

    def test_verbose_alto_continua_trace(self) -> None:
        """-vvvv ou mais continua TRACE."""
        ctx = CLIContext(verbose=10)
        assert ctx.log_level == "TRACE"

    def test_quiet_1_warning(self) -> None:
        ctx = CLIContext(quiet=1)
        assert ctx.log_level == "WARNING"

    def test_quiet_2_error(self) -> None:
        ctx = CLIContext(quiet=2)
        assert ctx.log_level == "ERROR"

    def test_quiet_alto_continua_error(self) -> None:
        ctx = CLIContext(quiet=10)
        assert ctx.log_level == "ERROR"

    def test_quiet_tem_prioridade_sobre_verbose(self) -> None:
        """Se ambos forem passados, quiet ganha."""
        ctx = CLIContext(verbose=3, quiet=1)
        assert ctx.log_level == "WARNING"


class TestCLIContextConstructor:
    """Testes da construção com valores customizados."""

    def test_todos_valores_customizados(self) -> None:
        ctx = CLIContext(verbose=2, quiet=0, dry_run=True, yes=True)
        assert ctx.verbose == 2
        assert ctx.quiet == 0
        assert ctx.dry_run is True
        assert ctx.yes is True

    def test_mutavel(self) -> None:
        """CLIContext é dataclass mutável (Click usa pra setar atributos)."""
        ctx = CLIContext()
        ctx.verbose = 3
        ctx.dry_run = True
        assert ctx.verbose == 3
        assert ctx.dry_run is True


class TestNaTela:
    """
    `na_tela` separa o Live do terminal.

    Existe uma variavel de ambiente no meio porque a CLI e um processo
    separado, iniciado pelo servidor do Live: nao ha objeto para passar
    adiante, so o ambiente.
    """

    def test_por_padrao_e_terminal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AUTOTAREFAS_UI", raising=False)
        assert CLIContext().na_tela is False

    def test_web_e_tela(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTOTAREFAS_UI", "web")
        assert CLIContext().na_tela is True

    def test_aceita_espaco_e_caixa_alta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTOTAREFAS_UI", "  WEB  ")
        assert CLIContext().na_tela is True

    def test_valor_desconhecido_nao_vira_tela(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Na duvida, comporta-se como terminal: o aviso fica, e nada se perde."""
        monkeypatch.setenv("AUTOTAREFAS_UI", "qualquer-coisa")
        assert CLIContext().na_tela is False
