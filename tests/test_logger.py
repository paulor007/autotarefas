"""
Testes do módulo de logging do AutoTarefas.

Escopo:
    - Import do logger do projeto (Loguru)
    - API mínima esperada (bind/opt/exception)
    - Configuração via configure_from_settings()
    - Escrita de logs em arquivo (via fixture capture_logs)
    - Logging de exceção com traceback

Observação:
    Não re-testamos funcionalidades internas do Loguru (rotação, enqueue, serialize, etc.).
    Esses comportamentos já são cobertos pela biblioteca e tendem a gerar testes instáveis.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ============================================================================
# Importação e API mínima
# ============================================================================


class TestLoggerImport:
    """Testes de importação e contrato mínimo do logger do projeto."""

    def test_logger_import(self) -> None:
        """Deve importar logger do projeto sem erro."""
        from autotarefas.core.logger import logger

        assert logger is not None

    def test_logger_has_loguru_api(self) -> None:
        """Logger deve expor API padrão do Loguru (bind/opt/exception)."""
        from autotarefas.core.logger import logger

        assert hasattr(logger, "bind")
        assert hasattr(logger, "opt")
        assert hasattr(logger, "exception")

    def test_configure_from_settings_exists(self) -> None:
        """Módulo deve expor função de configurar logger."""
        from autotarefas.core import logger as logger_module

        assert hasattr(logger_module, "configure_from_settings")


# ============================================================================
# Escrita básica (arquivo)
# ============================================================================


class TestLoggingToFile:
    """Testes de escrita básica no arquivo de logs capturado (fixture)."""

    def test_info_is_written(self, capture_logs: Path) -> None:
        """logger.info deve escrever no arquivo."""
        from autotarefas.core.logger import logger

        logger.info("Info message - test_logger")

        content = capture_logs.read_text(encoding="utf-8")
        assert "Info message - test_logger" in content

    def test_warning_is_written(self, capture_logs: Path) -> None:
        """logger.warning deve escrever no arquivo."""
        from autotarefas.core.logger import logger

        logger.warning("Warning message - test_logger")

        content = capture_logs.read_text(encoding="utf-8")
        assert "Warning message - test_logger" in content

    def test_error_is_written(self, capture_logs: Path) -> None:
        """logger.error deve escrever no arquivo."""
        from autotarefas.core.logger import logger

        logger.error("Error message - test_logger")

        content = capture_logs.read_text(encoding="utf-8")
        assert "Error message - test_logger" in content


# ============================================================================
# Contexto e opções
# ============================================================================


class TestLogContext:
    """Testes de contexto (bind) e opções (opt)."""

    def test_bind_does_not_crash(self, capture_logs: Path) -> None:
        """bind() deve funcionar e não quebrar o logger."""
        from autotarefas.core.logger import logger

        logger.bind(task="backup", user="test").info("Bound log - test_logger")

        content = capture_logs.read_text(encoding="utf-8")
        assert "Bound log - test_logger" in content

    def test_opt_exception_true_logs_message(self, capture_logs: Path) -> None:
        """opt(exception=True) deve escrever a mensagem no log."""
        from autotarefas.core.logger import logger

        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.opt(exception=True).error("Error with traceback - test_logger")

        content = capture_logs.read_text(encoding="utf-8")
        assert "Error with traceback - test_logger" in content


# ============================================================================
# Logging de exceções
# ============================================================================


class TestExceptionLogging:
    """Testes do logger.exception()."""

    def test_exception_method_writes(self, capture_logs: Path) -> None:
        """logger.exception() deve registrar mensagem e contexto de erro."""
        from autotarefas.core.logger import logger

        try:
            raise RuntimeError("Runtime error - test_logger")
        except RuntimeError:
            logger.exception("Caught exception - test_logger")

        content = capture_logs.read_text(encoding="utf-8")
        assert "Caught exception - test_logger" in content
        # Traceback/erro pode variar, mas normalmente aparece o tipo
        assert "RuntimeError" in content or "Traceback" in content


# ============================================================================
# Configuração via settings (smoke test)
# ============================================================================


class TestConfigureFromSettings:
    """Smoke tests para configuração do logger via settings do projeto."""

    @pytest.mark.usefixtures("isolated_env")
    def test_configure_from_settings_does_not_crash(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        configure_from_settings() não deve quebrar.

        Usa env isolado e diretórios temporários para evitar escrita fora do projeto.
        """
        # Ajusta paths para um local seguro (compatível com seu config.py atual)
        monkeypatch.setenv("LOG_PATH", str(temp_dir / "logs"))
        monkeypatch.setenv("TEMP_PATH", str(temp_dir / "temp"))
        monkeypatch.setenv("REPORTS_PATH", str(temp_dir / "reports"))
        monkeypatch.setenv("DATA_DIR", str(temp_dir / ".autotarefas"))
        monkeypatch.setenv("BACKUP_PATH", str(temp_dir / "backups"))

        from autotarefas.core.logger import configure_from_settings

        configure_from_settings()  # não deve levantar exceção
