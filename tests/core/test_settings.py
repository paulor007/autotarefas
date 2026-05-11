"""Testes para autotarefas.core.settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr
from pydantic import ValidationError as PydanticValidationError

from autotarefas.core.settings import Settings


def make_settings(**overrides: Any) -> Settings:
    """
    Cria Settings sem ler o arquivo .env (helper local).

    Encapsula o argumento especial ``_env_file=None`` do pydantic-settings.
    Esse argumento é injetado dinamicamente pela metaclass do BaseSettings,
    então o mypy não consegue ver na assinatura visível da classe — daí o
    ``type: ignore[call-arg]`` ser necessário (em UM único lugar).

    Args:
        **overrides: Valores específicos pra sobrescrever defaults.

    Returns:
        Settings instance sem leitura do .env.
    """
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


class TestSettingsDefaults:
    """Testes dos valores default."""

    def test_environment_default_dev(self) -> None:
        s = make_settings()
        assert s.environment == "dev"

    def test_log_level_default_info(self) -> None:
        s = make_settings()
        assert s.log_level == "INFO"

    def test_email_port_default_587(self) -> None:
        s = make_settings()
        assert s.email_port == 587

    def test_rpa_headless_default_true(self) -> None:
        s = make_settings()
        assert s.rpa_headless is True

    def test_rpa_default_timeout_default_10(self) -> None:
        s = make_settings()
        assert s.rpa_default_timeout == 10


class TestSettingsLeEnvVars:
    """Testes que confirmam leitura de variáveis de ambiente."""

    def test_le_environment_de_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "prod")
        s = make_settings()
        assert s.environment == "prod"

    def test_le_log_level_de_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        s = make_settings()
        assert s.log_level == "DEBUG"

    def test_le_email_user_de_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL_USER", "test@example.com")
        s = make_settings()
        assert s.email_user == "test@example.com"


class TestSettingsValidation:
    """Testes de validação de tipos/valores."""

    def test_environment_invalido_levanta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "invalid_env")
        with pytest.raises(PydanticValidationError):
            make_settings()

    def test_log_level_invalido_levanta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "TRACE")
        with pytest.raises(PydanticValidationError):
            make_settings()

    def test_email_port_acima_do_maximo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL_PORT", "70000")
        with pytest.raises(PydanticValidationError):
            make_settings()

    def test_email_port_abaixo_do_minimo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL_PORT", "0")
        with pytest.raises(PydanticValidationError):
            make_settings()

    def test_rpa_default_timeout_acima_do_maximo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RPA_DEFAULT_TIMEOUT", "999")
        with pytest.raises(PydanticValidationError):
            make_settings()


class TestSettingsSecretStr:
    """Testes de SecretStr (senhas)."""

    def test_email_password_e_secret_str(self) -> None:
        s = make_settings()
        assert isinstance(s.email_password, SecretStr)

    def test_secret_str_esconde_em_repr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL_PASSWORD", "minha_senha_super_secreta")
        s = make_settings()
        # repr() não deve mostrar a senha real
        assert "minha_senha_super_secreta" not in repr(s)

    def test_secret_str_acessivel_via_get_secret_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EMAIL_PASSWORD", "senha123")
        s = make_settings()
        assert s.email_password.get_secret_value() == "senha123"


class TestSettingsProperties:
    """Testes das properties derivadas."""

    def test_logs_dir(self) -> None:
        s = make_settings()
        assert s.logs_dir == s.autotarefas_home / "logs"

    def test_audit_db_path(self) -> None:
        s = make_settings()
        assert s.audit_db_path == s.autotarefas_home / "audit.db"

    def test_screenshots_dir(self) -> None:
        s = make_settings()
        assert s.screenshots_dir == s.autotarefas_home / "screenshots"

    def test_reports_dir(self) -> None:
        s = make_settings()
        assert s.reports_dir == s.autotarefas_home / "reports"

    def test_is_production_em_prod(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "prod")
        s = make_settings()
        assert s.is_production is True

    def test_is_production_em_dev(self) -> None:
        s = make_settings()
        assert s.is_production is False


class TestSettingsExpandHome:
    """Testes do validator expand_home."""

    def test_til_expandido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTOTAREFAS_HOME", "~/myhome")
        s = make_settings()
        # ~ deve ter sido expandido
        assert "~" not in str(s.autotarefas_home)

    def test_caminho_absoluto_preservado(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Usa tmp_path do pytest em vez de /tmp hardcoded."""
        target = tmp_path / "teste_autotarefas"
        monkeypatch.setenv("AUTOTAREFAS_HOME", str(target))
        s = make_settings()
        assert str(s.autotarefas_home).endswith("teste_autotarefas")


class TestSettingsCaseInsensitive:
    """Testes de case_sensitive=False (env vars maiúsc/minúsc)."""

    def test_environment_minusculo_funciona(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # env var em minúsculo
        monkeypatch.setenv("environment", "homolog")
        s = make_settings()
        assert s.environment == "homolog"
