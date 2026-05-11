"""Testes para autotarefas.core.exceptions."""

from __future__ import annotations

import pytest

from autotarefas.core.exceptions import (
    AuditError,
    AutoTarefasError,
    ConfigError,
    LoginError,
    RPAError,
    RPATimeoutError,
    SecurityError,
    SelectorNotFoundError,
    ValidationError,
)


class TestAutoTarefasError:
    """Testes da exceção raiz."""

    def test_pode_ser_lancada(self) -> None:
        """AutoTarefasError pode ser lançada e capturada."""
        with pytest.raises(AutoTarefasError):
            raise AutoTarefasError("erro genérico")

    def test_e_subclasse_de_exception(self) -> None:
        """Herda de Exception."""
        assert issubclass(AutoTarefasError, Exception)

    def test_message_acessivel_via_str(self) -> None:
        """Mensagem está em str(e)."""
        e = AutoTarefasError("mensagem teste")
        assert str(e) == "mensagem teste"


class TestConfigError:
    """Testes de ConfigError."""

    def test_e_subclasse_de_autotarefas_error(self) -> None:
        assert issubclass(ConfigError, AutoTarefasError)

    def test_com_config_key(self) -> None:
        """Atributo config_key pode ser passado."""
        e = ConfigError("falta var", config_key="EMAIL_USER")
        assert e.config_key == "EMAIL_USER"
        assert str(e) == "falta var"

    def test_sem_config_key_e_none(self) -> None:
        """Sem config_key, atributo é None."""
        e = ConfigError("erro qualquer")
        assert e.config_key is None


class TestValidationError:
    """Testes de ValidationError."""

    def test_e_subclasse_de_autotarefas_error(self) -> None:
        assert issubclass(ValidationError, AutoTarefasError)

    def test_attributes_completos(self) -> None:
        """Todos os atributos são guardados."""
        e = ValidationError("email inválido", field="email", row=42, value="abc")
        assert e.field == "email"
        assert e.row == 42
        assert e.value == "abc"
        assert str(e) == "email inválido"

    def test_attributes_default_none(self) -> None:
        """Sem args opcionais, atributos são None."""
        e = ValidationError("erro genérico")
        assert e.field is None
        assert e.row is None
        assert e.value is None

    def test_value_pode_ser_qualquer_tipo(self) -> None:
        """value aceita Any."""
        e1 = ValidationError("e", value=123)
        e2 = ValidationError("e", value=[1, 2])
        e3 = ValidationError("e", value=None)

        assert e1.value == 123
        assert e2.value == [1, 2]
        assert e3.value is None


class TestSecurityError:
    """Testes de SecurityError."""

    def test_e_subclasse_de_autotarefas_error(self) -> None:
        assert issubclass(SecurityError, AutoTarefasError)

    def test_pode_ser_lancada(self) -> None:
        with pytest.raises(SecurityError):
            raise SecurityError("path traversal detectado")


class TestAuditError:
    """Testes de AuditError."""

    def test_e_subclasse_de_autotarefas_error(self) -> None:
        assert issubclass(AuditError, AutoTarefasError)

    def test_pode_ser_lancada(self) -> None:
        with pytest.raises(AuditError):
            raise AuditError("falha ao gravar audit")


class TestRPAError:
    """Testes de RPAError e subclasses."""

    def test_e_subclasse_de_autotarefas_error(self) -> None:
        assert issubclass(RPAError, AutoTarefasError)

    def test_login_error_e_rpa_error(self) -> None:
        assert issubclass(LoginError, RPAError)
        assert issubclass(LoginError, AutoTarefasError)

    def test_selector_not_found_error_e_rpa_error(self) -> None:
        assert issubclass(SelectorNotFoundError, RPAError)

    def test_rpa_timeout_error_e_rpa_error(self) -> None:
        assert issubclass(RPATimeoutError, RPAError)


class TestSelectorNotFoundError:
    """Testes de SelectorNotFoundError."""

    def test_attributes_completos(self) -> None:
        e = SelectorNotFoundError(
            "seletor não encontrado",
            selector="#input-email",
            page_url="https://example.com",
        )
        assert e.selector == "#input-email"
        assert e.page_url == "https://example.com"

    def test_attributes_default_none(self) -> None:
        e = SelectorNotFoundError("erro")
        assert e.selector is None
        assert e.page_url is None


class TestRPATimeoutError:
    """Testes de RPATimeoutError."""

    def test_attributes_completos(self) -> None:
        e = RPATimeoutError(
            "timeout em page.goto",
            operation="page.goto",
            timeout_seconds=10.0,
        )
        assert e.operation == "page.goto"
        assert e.timeout_seconds == 10.0

    def test_attributes_default_none(self) -> None:
        e = RPATimeoutError("timeout")
        assert e.operation is None
        assert e.timeout_seconds is None
