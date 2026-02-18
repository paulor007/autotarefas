# type: ignore
"""
AutoTarefas - Hook System
=========================

Sistema de hooks para eventos do AutoTarefas.

Eventos disponíveis:
    - task.before_run: Antes de executar uma task
    - task.after_run: Após executar uma task
    - task.on_success: Quando task termina com sucesso
    - task.on_failure: Quando task falha
    - scheduler.job_added: Job adicionado ao scheduler
    - scheduler.job_removed: Job removido do scheduler
    - scheduler.job_executed: Job executado
    - backup.before_create: Antes de criar backup
    - backup.after_create: Após criar backup
    - backup.before_restore: Antes de restaurar backup
    - backup.after_restore: Após restaurar backup
    - plugin.activated: Plugin ativado
    - plugin.deactivated: Plugin desativado

Exemplo de uso:
    from autotarefas.plugins import HookManager, hook

    # Registrar via decorator
    @hook("task.after_run")
    def meu_hook(task_name, result):
        print(f"Task {task_name} executada!")

    # Registrar manualmente
    HookManager.register("task.before_run", minha_funcao)

    # Disparar evento
    HookManager.trigger("task.after_run", task_name="backup", result=result)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


class HookPriority(Enum):
    """Prioridade de execução de hooks."""

    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


@dataclass
class HookEntry:
    """Entrada de um hook registrado."""

    callback: Callable
    priority: HookPriority = HookPriority.NORMAL
    name: str | None = None
    plugin: str | None = None
    is_async: bool = False
    registered_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.name is None:
            self.name = getattr(self.callback, "__name__", str(self.callback))
        self.is_async = asyncio.iscoroutinefunction(self.callback)


class HookManager:
    """
    Gerenciador global de hooks.

    Permite registrar, desregistrar e disparar eventos
    em todo o sistema AutoTarefas.
    """

    _hooks: dict[str, list[HookEntry]] = {}
    _enabled: bool = True

    # Eventos padrão do sistema
    EVENTS = {
        # Tasks
        "task.before_run",
        "task.after_run",
        "task.on_success",
        "task.on_failure",
        "task.on_skip",
        # Scheduler
        "scheduler.started",
        "scheduler.stopped",
        "scheduler.job_added",
        "scheduler.job_removed",
        "scheduler.job_executed",
        "scheduler.job_failed",
        # Backup
        "backup.before_create",
        "backup.after_create",
        "backup.before_restore",
        "backup.after_restore",
        # Cleaner
        "cleaner.before_clean",
        "cleaner.after_clean",
        "cleaner.file_deleted",
        # Monitor
        "monitor.threshold_exceeded",
        "monitor.alert_triggered",
        # Plugins
        "plugin.discovered",
        "plugin.activated",
        "plugin.deactivated",
        "plugin.error",
        # Sistema
        "system.startup",
        "system.shutdown",
    }

    @classmethod
    def register(
        cls,
        event: str,
        callback: Callable,
        priority: HookPriority = HookPriority.NORMAL,
        name: str | None = None,
        plugin: str | None = None,
    ) -> None:
        """
        Registra um hook para um evento.

        Args:
            event: Nome do evento
            callback: Função a ser chamada
            priority: Prioridade de execução
            name: Nome identificador do hook
            plugin: Nome do plugin que registrou
        """
        if event not in cls._hooks:
            cls._hooks[event] = []

        entry = HookEntry(
            callback=callback,
            priority=priority,
            name=name,
            plugin=plugin,
        )

        cls._hooks[event].append(entry)
        cls._hooks[event].sort(key=lambda h: h.priority.value, reverse=True)

        logger.debug(f"Hook registrado: {event} -> {entry.name}")

    @classmethod
    def unregister(cls, event: str, callback: Callable) -> bool:
        """
        Remove um hook de um evento.

        Args:
            event: Nome do evento
            callback: Função a ser removida

        Returns:
            True se removeu com sucesso
        """
        if event not in cls._hooks:
            return False

        for entry in cls._hooks[event]:
            if entry.callback == callback:
                cls._hooks[event].remove(entry)
                logger.debug(f"Hook removido: {event} -> {entry.name}")
                return True

        return False

    @classmethod
    def unregister_plugin(cls, plugin_name: str) -> int:
        """
        Remove todos os hooks de um plugin.

        Args:
            plugin_name: Nome do plugin

        Returns:
            Número de hooks removidos
        """
        count = 0
        for event in cls._hooks:
            original_len = len(cls._hooks[event])
            cls._hooks[event] = [h for h in cls._hooks[event] if h.plugin != plugin_name]
            count += original_len - len(cls._hooks[event])

        if count > 0:
            logger.debug(f"Removidos {count} hooks do plugin: {plugin_name}")

        return count

    @classmethod
    def trigger(cls, event: str, **kwargs: Any) -> list[Any]:
        """
        Dispara um evento, executando todos os hooks registrados.

        Args:
            event: Nome do evento
            **kwargs: Argumentos para os hooks

        Returns:
            Lista de resultados dos hooks
        """
        if not cls._enabled:
            return []

        if event not in cls._hooks:
            return []

        results = []
        for entry in cls._hooks[event]:
            try:
                # Se for async, isso retorna uma coroutine; para aguardar, use trigger_async.
                result = entry.callback(**kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Erro no hook {entry.name} ({event}): {e}")
                results.append(None)

        return results

    @classmethod
    async def trigger_async(cls, event: str, **kwargs: Any) -> list[Any]:
        """
        Dispara um evento de forma assíncrona.

        Args:
            event: Nome do evento
            **kwargs: Argumentos para os hooks

        Returns:
            Lista de resultados dos hooks
        """
        if not cls._enabled:
            return []

        if event not in cls._hooks:
            return []

        results = []
        for entry in cls._hooks[event]:
            try:
                if entry.is_async:
                    result = await entry.callback(**kwargs)
                else:
                    result = entry.callback(**kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Erro no hook {entry.name} ({event}): {e}")
                results.append(None)

        return results

    @classmethod
    def get_hooks(cls, event: str) -> list[HookEntry]:
        """
        Retorna hooks registrados para um evento.

        Args:
            event: Nome do evento

        Returns:
            Lista de HookEntry
        """
        return cls._hooks.get(event, [])

    @classmethod
    def get_all_events(cls) -> list[str]:
        """Retorna todos os eventos com hooks registrados."""
        return list(cls._hooks.keys())

    @classmethod
    def clear(cls, event: str | None = None) -> None:
        """
        Remove todos os hooks.

        Args:
            event: Se fornecido, limpa apenas este evento
        """
        if event:
            cls._hooks.pop(event, None)
        else:
            cls._hooks.clear()

    @classmethod
    def enable(cls) -> None:
        """Habilita o sistema de hooks."""
        cls._enabled = True

    @classmethod
    def disable(cls) -> None:
        """Desabilita o sistema de hooks."""
        cls._enabled = False

    @classmethod
    def is_enabled(cls) -> bool:
        """Verifica se o sistema está habilitado."""
        return cls._enabled

    @classmethod
    def stats(cls) -> dict[str, Any]:
        """Retorna estatísticas dos hooks."""
        total_hooks = sum(len(hooks) for hooks in cls._hooks.values())
        return {
            "enabled": cls._enabled,
            "total_events": len(cls._hooks),
            "total_hooks": total_hooks,
            "events": {event: len(hooks) for event, hooks in cls._hooks.items()},
        }


def hook(
    event: str,
    priority: HookPriority = HookPriority.NORMAL,
    name: str | None = None,
    plugin: str | None = None,
) -> Callable:
    """
    Decorator para registrar uma função como hook.

    Args:
        event: Nome do evento
        priority: Prioridade de execução
        name: Nome identificador
        plugin: Nome do plugin

    Example:
        @hook("task.after_run")
        def log_task_result(task_name, result):
            print(f"Task {task_name}: {result.status}")
    """

    def decorator(func: Callable) -> Callable:
        HookManager.register(
            event=event,
            callback=func,
            priority=priority,
            name=name or func.__name__,
            plugin=plugin,
        )

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Aliases para facilitar uso
on = hook  # @on("task.after_run")
emit = HookManager.trigger
emit_async = HookManager.trigger_async
