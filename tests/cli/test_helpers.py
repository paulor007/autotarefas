"""Testes para autotarefas.cli.helpers."""

from __future__ import annotations

import pytest

from autotarefas.cli.helpers import confirm, confirm_bulk


class TestConfirmYes:
    """Testes do flag yes (pula confirmação)."""

    def test_yes_retorna_true_sem_perguntar(self) -> None:
        """Com yes=True, retorna True sem pedir input."""
        assert confirm("ignored", yes=True) is True


class TestConfirmInterativo:
    """Testes do prompt interativo (sem yes)."""

    def test_user_responde_sim(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mock do click.confirm pra retornar True
        monkeypatch.setattr("click.confirm", lambda *a, **kw: True)
        assert confirm("ok?") is True

    def test_user_responde_nao(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("click.confirm", lambda *a, **kw: False)
        assert confirm("ok?") is False

    def test_default_passado_pro_click(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """default=True é passado pro click.confirm."""
        captured_kwargs: dict[str, object] = {}

        def fake_confirm(*args: object, **kwargs: object) -> bool:
            captured_kwargs.update(kwargs)
            return True

        monkeypatch.setattr("click.confirm", fake_confirm)
        confirm("ok?", default=True)
        assert captured_kwargs.get("default") is True


class TestConfirmBulkYes:
    """Testes do confirm_bulk com flag yes."""

    def test_yes_retorna_true_sem_perguntar(self) -> None:
        assert confirm_bulk("ignored", count=42, yes=True) is True


class TestConfirmBulkInterativo:
    """Testes do prompt do confirm_bulk."""

    def test_numero_correto_retorna_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """User digita o número exato → True."""
        monkeypatch.setattr("click.prompt", lambda *a, **kw: "42")
        assert confirm_bulk("deletar arquivos", count=42) is True

    def test_numero_errado_retorna_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """User digita número errado → False (rejeita confirmação)."""
        monkeypatch.setattr("click.prompt", lambda *a, **kw: "10")
        assert confirm_bulk("deletar arquivos", count=42) is False

    def test_resposta_vazia_retorna_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """User só apertou Enter → False."""
        monkeypatch.setattr("click.prompt", lambda *a, **kw: "")
        assert confirm_bulk("deletar arquivos", count=42) is False

    def test_string_em_vez_de_numero_retorna_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """User digitou 'sim' em vez do número → False."""
        monkeypatch.setattr("click.prompt", lambda *a, **kw: "sim")
        assert confirm_bulk("deletar arquivos", count=42) is False

    def test_numero_com_espacos_retorna_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """User digitou '  42  ' (com espaços) → True (faz strip)."""
        monkeypatch.setattr("click.prompt", lambda *a, **kw: "  42  ")
        assert confirm_bulk("deletar", count=42) is True

    def test_abort_retorna_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """User apertou Ctrl+C → click.Abort → False."""
        import click

        def raise_abort(*a: object, **kw: object) -> str:
            raise click.Abort

        monkeypatch.setattr("click.prompt", raise_abort)
        assert confirm_bulk("deletar", count=42) is False


class TestConfirmBulkPrintInfo:
    """Testes que o confirm_bulk mostra info ao usuário."""

    def test_mostra_action_e_count(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Antes de pedir input, mostra action e count."""
        monkeypatch.setattr("click.prompt", lambda *a, **kw: "42")
        confirm_bulk("deletar arquivos antigos", count=42)
        captured = capsys.readouterr()
        assert "deletar arquivos antigos" in captured.out
        assert "42" in captured.out
