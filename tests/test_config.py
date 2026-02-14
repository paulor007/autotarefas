"""
Testes do módulo de configuração.

Cobertura:
    - Defaults e instância global `settings`
    - Leitura de variáveis de ambiente (Settings/EmailSettings)
    - Normalizações (ex.: TLS+SSL)
    - Coerção (ex.: LOG_LEVEL / BACKUP_COMPRESSION)
    - Criação de diretórios no __post_init__
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

# ============================================================================
# Helpers
# ============================================================================


def _set_paths_env(monkeypatch: pytest.MonkeyPatch, base: Path) -> None:
    """Aplica paths de teste para evitar escrita fora do diretório temporário."""
    monkeypatch.setenv("LOG_PATH", str(base / "logs"))
    monkeypatch.setenv("TEMP_PATH", str(base / "temp"))
    monkeypatch.setenv("REPORTS_PATH", str(base / "reports"))
    monkeypatch.setenv("DATA_DIR", str(base / ".autotarefas"))
    monkeypatch.setenv("BACKUP_PATH", str(base / "backups"))


def _build_settings(monkeypatch: pytest.MonkeyPatch, base: Path):
    """Cria uma instância de Settings com paths isolados."""
    _set_paths_env(monkeypatch, base)
    from autotarefas.config import Settings  # import local p/ pegar env atualizado

    return Settings()


# ============================================================================
# Testes da instância global / import
# ============================================================================


@pytest.mark.usefixtures("isolated_env", "isolated_fs")
class TestSettingsGlobal:
    """Testes relacionados ao import e à instância global `settings`."""

    def test_import_settings(self) -> None:
        """Deve importar settings sem erro."""
        from autotarefas.config import settings

        assert settings is not None

    def test_settings_singleton_instance_on_import(self) -> None:
        """Importar `settings` duas vezes deve apontar para o mesmo objeto."""
        from autotarefas.config import settings as s1
        from autotarefas.config import settings as s2

        assert s1 is s2

    def test_reload_recreates_settings(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """Recarregar o módulo deve recriar o settings com o ambiente atual."""
        # Nota: config.py usa AUTOTAREFAS_APP_NAME quando rodando sob pytest
        monkeypatch.setenv("AUTOTAREFAS_APP_NAME", "AutoTarefas-Test")
        _set_paths_env(monkeypatch, temp_dir)

        import autotarefas.config as config

        importlib.reload(config)

        assert config.settings.APP_NAME == "AutoTarefas-Test"

        # Cleanup: remove a env var e recarrega para não afetar outros testes
        monkeypatch.delenv("AUTOTAREFAS_APP_NAME", raising=False)
        importlib.reload(config)


# ============================================================================
# Testes básicos de defaults
# ============================================================================


class TestSettingsDefaults:
    """Testes dos valores padrão (defaults) quando não há env específica."""

    @pytest.mark.usefixtures("isolated_env", "isolated_fs")
    def test_default_app_name(self) -> None:
        """APP_NAME padrão deve ser AutoTarefas."""
        from autotarefas.config import settings

        assert settings.APP_NAME == "AutoTarefas"

    @pytest.mark.usefixtures("isolated_env", "isolated_fs")
    def test_default_env_is_development(self) -> None:
        """APP_ENV padrão deve ser development."""
        from autotarefas.config import settings

        assert settings.APP_ENV == "development"
        assert settings.is_development is True
        assert settings.is_production is False

    @pytest.mark.usefixtures("isolated_env", "isolated_fs")
    def test_default_log_level_is_info(self) -> None:
        """LOG_LEVEL padrão deve ser INFO (coerção)."""
        from autotarefas.config import settings

        assert settings.LOG_LEVEL == "INFO"


# ============================================================================
# Testes de diretórios / paths
# ============================================================================


@pytest.mark.usefixtures("isolated_env")
class TestSettingsDirectories:
    """Testes de criação e tipos de paths."""

    def test_paths_are_created(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """__post_init__ deve criar diretórios necessários."""
        s = _build_settings(monkeypatch, temp_dir)

        assert s.LOG_PATH.exists() and s.LOG_PATH.is_dir()
        assert s.TEMP_PATH.exists() and s.TEMP_PATH.is_dir()
        assert s.REPORTS_PATH.exists() and s.REPORTS_PATH.is_dir()
        assert s.DATA_DIR.exists() and s.DATA_DIR.is_dir()
        assert s.backup.path.exists() and s.backup.path.is_dir()

    def test_data_dir_alias(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """settings.data_dir deve ser um alias para DATA_DIR."""
        s = _build_settings(monkeypatch, temp_dir)
        assert isinstance(s.data_dir, Path)
        assert s.data_dir == s.DATA_DIR


# ============================================================================
# Testes de EmailSettings
# ============================================================================


@pytest.mark.usefixtures("isolated_env")
class TestEmailSettings:
    """Testes de configuração de email (EmailSettings + properties SMTP)."""

    def test_email_defaults_exist(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """EmailSettings deve existir e ter campos básicos."""
        s = _build_settings(monkeypatch, temp_dir)

        assert hasattr(s, "email")
        assert isinstance(s.email.host, str)
        assert isinstance(s.email.port, int)
        assert isinstance(s.email.enabled, bool)

    def test_email_env_overrides(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """Vars EMAIL_* devem sobrescrever os defaults."""
        monkeypatch.setenv("EMAIL_ENABLED", "true")
        monkeypatch.setenv("EMAIL_HOST", "smtp.test.com")
        monkeypatch.setenv("EMAIL_PORT", "465")
        monkeypatch.setenv("EMAIL_USER", "user@test.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "secret")
        monkeypatch.setenv("EMAIL_FROM", "noreply@test.com")
        monkeypatch.setenv("EMAIL_FROM_NAME", "AutoTarefas QA")
        monkeypatch.setenv("EMAIL_TO", "dest@test.com")
        monkeypatch.setenv("EMAIL_USE_TLS", "false")
        monkeypatch.setenv("EMAIL_USE_SSL", "true")
        monkeypatch.setenv("EMAIL_TIMEOUT", "20")

        s = _build_settings(monkeypatch, temp_dir)

        assert s.email.enabled is True
        assert s.email.host == "smtp.test.com"
        assert s.email.port == 465
        assert s.email.user == "user@test.com"
        assert s.email.password == "secret"
        assert s.email.from_addr == "noreply@test.com"
        assert s.email.from_name == "AutoTarefas QA"
        assert s.email.to_addr == "dest@test.com"
        assert s.email.use_ssl is True
        assert s.email.use_tls is False
        assert s.email.timeout_seconds == 20

    def test_tls_ssl_normalization(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """TLS+SSL True deve desativar TLS (prioriza SSL)."""
        monkeypatch.setenv("EMAIL_USE_TLS", "true")
        monkeypatch.setenv("EMAIL_USE_SSL", "true")

        s = _build_settings(monkeypatch, temp_dir)

        assert s.email.use_ssl is True
        assert s.email.use_tls is False

    def test_smtp_from_prefers_from_addr(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """smtp_from deve preferir email.from_addr; senão, cair para email.user."""
        monkeypatch.setenv("EMAIL_USER", "user@test.com")
        monkeypatch.setenv("EMAIL_FROM", "from@test.com")
        s = _build_settings(monkeypatch, temp_dir)
        assert s.smtp_from == "from@test.com"

        monkeypatch.setenv("EMAIL_FROM", "")
        s2 = _build_settings(monkeypatch, temp_dir)
        assert s2.smtp_from == "user@test.com"


# ============================================================================
# Testes de Settings via variáveis de ambiente
# ============================================================================


@pytest.mark.usefixtures("isolated_env")
class TestSettingsFromEnv:
    """Testes de leitura de env para Settings (APP_*, DEBUG, LOG_LEVEL etc.)."""

    def test_env_override_debug(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """DEBUG deve respeitar valores truthy/falsey."""
        monkeypatch.setenv("DEBUG", "true")
        s = _build_settings(monkeypatch, temp_dir)
        assert s.DEBUG is True

        monkeypatch.setenv("DEBUG", "false")
        s2 = _build_settings(monkeypatch, temp_dir)
        assert s2.DEBUG is False

    def test_env_override_app_env(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """APP_ENV deve ser lido como string."""
        monkeypatch.setenv("APP_ENV", "production")
        s = _build_settings(monkeypatch, temp_dir)
        assert s.APP_ENV == "production"
        assert s.is_production is True

        monkeypatch.setenv("APP_ENV", "invalid_env")
        s2 = _build_settings(monkeypatch, temp_dir)
        assert s2.APP_ENV == "invalid_env"


# ============================================================================
# Testes de coerção / valores com conjunto permitido
# ============================================================================


@pytest.mark.usefixtures("isolated_env")
class TestSettingsCoercion:
    """Testes de coerção para valores com conjunto permitido."""

    def test_invalid_log_level_falls_back_to_info(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """LOG_LEVEL inválido deve virar INFO."""
        monkeypatch.setenv("LOG_LEVEL", "NOPE")
        s = _build_settings(monkeypatch, temp_dir)
        assert s.LOG_LEVEL == "INFO"

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_valid_log_levels(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path, level: str
    ) -> None:
        """LOG_LEVEL deve aceitar valores válidos."""
        monkeypatch.setenv("LOG_LEVEL", level)
        s = _build_settings(monkeypatch, temp_dir)
        assert level == s.LOG_LEVEL

    def test_backup_compression_invalid_falls_back_to_zip(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """BACKUP_COMPRESSION inválido deve virar zip."""
        monkeypatch.setenv("BACKUP_COMPRESSION", "rar")
        s = _build_settings(monkeypatch, temp_dir)
        assert s.backup.compression == "zip"

    @pytest.mark.parametrize("comp", ["zip", "tar", "tar.gz"])
    def test_backup_compression_valid(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path, comp: str
    ) -> None:
        """BACKUP_COMPRESSION deve aceitar valores válidos."""
        monkeypatch.setenv("BACKUP_COMPRESSION", comp)
        s = _build_settings(monkeypatch, temp_dir)
        assert s.backup.compression == comp


# ============================================================================
# Edge cases
# ============================================================================


@pytest.mark.usefixtures("isolated_env")
class TestEdgeCases:
    """Testes de casos extremos previsíveis no parser de env."""

    def test_email_port_invalid_uses_default(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """EMAIL_PORT inválido deve cair no default (587)."""
        monkeypatch.setenv("EMAIL_PORT", "invalid")
        s = _build_settings(monkeypatch, temp_dir)
        assert s.email.port == 587

    def test_email_port_negative_is_kept(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """EMAIL_PORT negativo não é validado/clampado (fica -1)."""
        monkeypatch.setenv("EMAIL_PORT", "-1")
        s = _build_settings(monkeypatch, temp_dir)
        assert s.email.port == -1

    def test_empty_email_host_is_allowed(
        self, monkeypatch: pytest.MonkeyPatch, temp_dir: Path
    ) -> None:
        """EMAIL_HOST vazio deve resultar em string vazia."""
        monkeypatch.setenv("EMAIL_HOST", "")
        s = _build_settings(monkeypatch, temp_dir)
        assert s.email.host == ""
