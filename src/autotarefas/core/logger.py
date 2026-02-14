"""
Sistema de logging do AutoTarefas.

Usa Loguru para fornecer logs formatados, coloridos e com rotação automática.

Uso:
    from autotarefas.core.logger import logger

    logger.info("Mensagem informativa")
    logger.warning("Aviso!")
    logger.error("Erro ocorreu")
    logger.debug("Debug detalhado")
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger as _loguru_logger

if TYPE_CHECKING:
    from loguru import Logger


def setup_logger(
    level: str = "INFO",
    log_path: Path | str | None = None,
    rotation: str = "10 MB",
    retention: str = "30 days",
    compression: str = "zip",
    colorize: bool = True,
    diagnose: bool = True,
) -> Logger:
    """
    Configura o logger do sistema.

    Args:
        level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_path: Caminho para arquivo de log (None = apenas console)
        rotation: Quando rotacionar (ex: "10 MB", "1 day", "00:00")
        retention: Quanto tempo manter logs antigos
        compression: Compressão dos logs rotacionados (zip, gz, etc)
        colorize: Se deve colorir output no console
        diagnose: Se deve mostrar diagnóstico detalhado em erros

    Returns:
        Logger configurado
    """
    _loguru_logger.remove()

    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    file_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"

    _loguru_logger.add(
        sys.stderr,
        format=console_format,
        level=level.upper(),
        colorize=colorize,
        diagnose=diagnose,
        backtrace=True,
    )

    if log_path:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        _loguru_logger.add(
            str(log_path),
            format=file_format,
            level=level.upper(),
            rotation=rotation,
            retention=retention,
            compression=compression,
            encoding="utf-8",
            diagnose=diagnose,
            backtrace=True,
        )

    return _loguru_logger


def get_logger(name: str | None = None) -> Logger:
    """
    Obtém uma instância do logger, opcionalmente com contexto.

    Args:
        name: Nome do módulo/contexto (opcional)

    Returns:
        Logger (com bind se name for especificado)
    """
    if name:
        return _loguru_logger.bind(name=name)
    return _loguru_logger


def configure_from_settings(settings_obj=None) -> Logger:
    """
    Configura o logger a partir das settings do sistema.

    Args:
        settings_obj: opcional; permite injetar Settings em testes.
            Se None, importa `autotarefas.config.settings`.

    Returns:
        Logger configurado
    """
    if settings_obj is None:
        from autotarefas.config import settings as settings_obj  # import tardio

    log_file = settings_obj.LOG_PATH / "autotarefas.log"
    return setup_logger(
        level=settings_obj.LOG_LEVEL,
        log_path=log_file,
        diagnose=settings_obj.DEBUG,
    )


class LoggerProxy:
    """
    Proxy transparente para o Loguru Logger, adicionando extras de compat.

    Motivo:
        Alguns testes verificam `hasattr(autotarefas.core.logger, "configure_from_settings")`.
        O objeto `loguru.Logger` não declara esse atributo no tipo, e anexar via
        setattr causa erro do Pylance. Então usamos um proxy.
    """

    def __init__(self, inner: Logger):
        self._inner = inner

    def configure_from_settings(self, *args: Any, **kwargs: Any) -> Logger:
        return configure_from_settings(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class LoggerContext:
    """
    Context manager para logging de operações.

    Exemplo:
        >>> with LoggerContext("backup", task_id="123"):
        ...     logger.info("Processando...")
    """

    def __init__(self, operation: str, **context: str | int | float):
        self.operation = operation
        self.context = context

    def __enter__(self) -> Logger:
        # durante o contexto, use um logger com extras bindados
        bound = logger.bind(operation=self.operation, **self.context)
        bound.info(f"[{self.operation}] Iniciando...")
        return bound

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type:
            # Loguru já pega o traceback corretamente aqui
            logger.opt(exception=True).error(f"[{self.operation}] Erro: {exc_val}")
        else:
            logger.info(f"[{self.operation}] Concluído com sucesso")
        return False


# Export principal: proxy (passa no teste e não irrita o Pylance)
logger = LoggerProxy(_loguru_logger)

__all__ = [
    "logger",
    "setup_logger",
    "get_logger",
    "configure_from_settings",
    "LoggerContext",
]
