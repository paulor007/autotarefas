"""Testes para autotarefas.tasks.issues."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from autotarefas.tasks.issues import (
    IssueCollector,
    IssueSeverity,
    ValidationIssue,
)

# ============================================================
# Tests: IssueSeverity (StrEnum)
# ============================================================


class TestIssueSeverity:
    """Testes da enum IssueSeverity."""

    def test_valores(self) -> None:
        """Verifica que os valores estao corretos."""
        assert IssueSeverity.ERROR.value == "error"
        assert IssueSeverity.WARNING.value == "warning"

    def test_comparacao_com_string(self) -> None:
        """StrEnum permite comparar direto com string."""
        assert str(IssueSeverity.ERROR) == "error"
        assert str(IssueSeverity.WARNING) == "warning"

    def test_membros(self) -> None:
        """Verifica que so existem 2 membros (ninguem adicionou outro)."""
        assert len(IssueSeverity) == 2


# ============================================================
# Tests: ValidationIssue (frozen dataclass)
# ============================================================


class TestValidationIssue:
    """Testes do ValidationIssue (dataclass imutavel)."""

    def test_criacao_basica(self) -> None:
        issue = ValidationIssue(
            line=7,
            column="cpf",
            message="CPF invalido",
        )
        assert issue.line == 7
        assert issue.column == "cpf"
        assert issue.message == "CPF invalido"

    def test_default_severity_error(self) -> None:
        """severity default deve ser ERROR."""
        issue = ValidationIssue(line=1, column="x", message="msg")
        assert issue.severity == IssueSeverity.ERROR

    def test_default_value_none(self) -> None:
        """value default deve ser None."""
        issue = ValidationIssue(line=1, column="x", message="msg")
        assert issue.value is None

    def test_com_value(self) -> None:
        """Pode passar valor opcional."""
        issue = ValidationIssue(
            line=5,
            column="cpf",
            message="CPF invalido",
            value="123",
        )
        assert issue.value == "123"

    def test_warning_severity(self) -> None:
        """Pode criar com severity=WARNING."""
        issue = ValidationIssue(
            line=1,
            column="x",
            message="suspeito",
            severity=IssueSeverity.WARNING,
        )
        assert issue.severity == IssueSeverity.WARNING

    def test_column_none(self) -> None:
        """column=None significa erro global (ex: arquivo vazio)."""
        issue = ValidationIssue(line=0, column=None, message="Arquivo vazio")
        assert issue.column is None

    def test_imutavel_levanta_frozen_error(self) -> None:
        """Tentativa de modificar deve falhar (frozen=True)."""
        issue = ValidationIssue(line=1, column="x", message="msg")
        with pytest.raises(FrozenInstanceError):
            issue.line = 99  # type: ignore[misc]

    def test_is_error(self) -> None:
        """Property is_error funciona pra ERROR e nao pra WARNING."""
        err = ValidationIssue(line=1, column="x", message="msg")  # ERROR default
        warn = ValidationIssue(line=1, column="x", message="msg", severity=IssueSeverity.WARNING)
        assert err.is_error is True
        assert warn.is_error is False

    def test_is_warning(self) -> None:
        """Property is_warning funciona pra WARNING e nao pra ERROR."""
        err = ValidationIssue(line=1, column="x", message="msg")
        warn = ValidationIssue(line=1, column="x", message="msg", severity=IssueSeverity.WARNING)
        assert err.is_warning is False
        assert warn.is_warning is True

    def test_equality(self) -> None:
        """Dois issues com mesmos campos sao iguais (dataclass gera __eq__)."""
        a = ValidationIssue(line=1, column="x", message="msg")
        b = ValidationIssue(line=1, column="x", message="msg")
        assert a == b

    def test_inequality(self) -> None:
        """Issues com campos diferentes nao sao iguais."""
        a = ValidationIssue(line=1, column="x", message="msg")
        b = ValidationIssue(line=2, column="x", message="msg")  # line diferente
        assert a != b


# ============================================================
# Tests: IssueCollector (mutavel)
# ============================================================


class TestIssueCollector:
    """Testes do IssueCollector (acumulador)."""

    def test_collector_vazio(self) -> None:
        """Collector recem-criado nao tem issues."""
        c = IssueCollector()
        assert c.total == 0
        assert len(c) == 0
        assert c.errors == []
        assert c.warnings == []
        assert c.is_valid is True

    def test_collector_vazio_e_falsy(self) -> None:
        """bool(collector) == False quando vazio."""
        c = IssueCollector()
        assert not c  # __bool__ retorna False

    def test_add_basico(self) -> None:
        """add() adiciona um issue."""
        c = IssueCollector()
        c.add(line=7, column="cpf", message="CPF invalido")
        assert c.total == 1
        assert c.issues[0].line == 7
        assert c.issues[0].message == "CPF invalido"

    def test_add_default_severity_error(self) -> None:
        """add() sem severity cria ERROR."""
        c = IssueCollector()
        c.add(line=1, column="x", message="msg")
        assert c.issues[0].severity == IssueSeverity.ERROR

    def test_add_warning_explicito(self) -> None:
        """add() pode criar WARNING."""
        c = IssueCollector()
        c.add(
            line=1,
            column="x",
            message="msg",
            severity=IssueSeverity.WARNING,
        )
        assert c.issues[0].severity == IssueSeverity.WARNING

    def test_add_com_value(self) -> None:
        """add() aceita value opcional pra debug."""
        c = IssueCollector()
        c.add(line=1, column="cpf", message="invalido", value="123")
        assert c.issues[0].value == "123"

    def test_errors_filtra_apenas_error(self) -> None:
        """Property errors so retorna ERROR."""
        c = IssueCollector()
        c.add(line=1, column="a", message="msg1")  # ERROR
        c.add(line=2, column="b", message="msg2", severity=IssueSeverity.WARNING)
        c.add(line=3, column="c", message="msg3")  # ERROR

        errors = c.errors
        assert len(errors) == 2
        assert all(e.is_error for e in errors)

    def test_warnings_filtra_apenas_warning(self) -> None:
        """Property warnings so retorna WARNING."""
        c = IssueCollector()
        c.add(line=1, column="a", message="msg1")  # ERROR
        c.add(line=2, column="b", message="msg2", severity=IssueSeverity.WARNING)

        warnings = c.warnings
        assert len(warnings) == 1
        assert warnings[0].is_warning

    def test_is_valid_com_warnings_apenas(self) -> None:
        """is_valid=True se SO tem warnings (warnings nao invalidam)."""
        c = IssueCollector()
        c.add(line=1, column="x", message="aviso", severity=IssueSeverity.WARNING)
        assert c.is_valid is True

    def test_is_valid_falso_com_errors(self) -> None:
        """is_valid=False quando ha qualquer ERROR."""
        c = IssueCollector()
        c.add(line=1, column="x", message="erro")
        assert c.is_valid is False

    def test_total_conta_tudo(self) -> None:
        """total inclui errors E warnings."""
        c = IssueCollector()
        c.add(line=1, column="a", message="msg")  # ERROR
        c.add(line=2, column="b", message="msg", severity=IssueSeverity.WARNING)
        assert c.total == 2

    def test_len_igual_total(self) -> None:
        """__len__ retorna total."""
        c = IssueCollector()
        c.add(line=1, column="x", message="msg")
        c.add(line=2, column="x", message="msg")
        assert len(c) == 2
        assert len(c) == c.total

    def test_bool_truthy_com_issues(self) -> None:
        """bool(collector) == True quando tem issues."""
        c = IssueCollector()
        c.add(line=1, column="x", message="msg")
        assert bool(c) is True

    def test_ordem_preservada(self) -> None:
        """Issues sao retornados na ordem de adicao."""
        c = IssueCollector()
        c.add(line=1, column="a", message="primeiro")
        c.add(line=2, column="b", message="segundo")
        c.add(line=3, column="c", message="terceiro")
        assert [i.message for i in c.issues] == [
            "primeiro",
            "segundo",
            "terceiro",
        ]

    def test_collectors_independentes(self) -> None:
        """Cada collector tem sua propria lista (sem state compartilhado)."""
        c1 = IssueCollector()
        c2 = IssueCollector()
        c1.add(line=1, column="x", message="msg")
        assert c2.total == 0  # c2 nao foi afetado
