# type: ignore
"""
AutoTarefas - Plugin System
===========================

Sistema de plugins para extensão do AutoTarefas.

Criando um Plugin:
    1. Crie uma classe que herda de PluginBase
    2. Implemente a propriedade `info` com PluginInfo
    3. Implemente os métodos `activate()` e `deactivate()`
    4. Registre via entry point ou diretório local

Exemplo básico:
    from autotarefas.plugins import PluginBase, PluginInfo

    class MeuPlugin(PluginBase):
        @property
        def info(self) -> PluginInfo:
            return PluginInfo(
                name="meu-plugin",
                version="1.0.0",
                description="Meu plugin customizado",
                author="Seu Nome",
            )

        def activate(self) -> None:
            # Registrar hooks, tasks, etc
            pass

        def deactivate(self) -> None:
            # Limpar recursos
            pass

Entry Point (pyproject.toml):
    [project.entry-points."autotarefas.plugins"]
    meu-plugin = "meu_pacote:MeuPlugin"

Uso do PluginManager:
    from autotarefas.plugins import PluginManager

    manager = PluginManager()
    manager.discover()           # Descobrir plugins
    manager.activate_all()       # Ativar todos
    manager.list_plugins()       # Listar plugins

Sistema de Hooks:
    from autotarefas.plugins import hook, HookManager

    @hook("task.after_run")
    def meu_hook(task_name, result):
        print(f"Task {task_name} executada!")

    # Disparar evento manualmente
    HookManager.trigger("task.after_run", task_name="backup", result=result)
"""

from .base import NotifierPlugin, PluginBase, PluginInfo, PluginState, PluginStatus, StoragePlugin, TaskPlugin
from .hooks import HookEntry, HookManager, HookPriority, emit, emit_async, hook, on
from .manager import ENTRY_POINT_GROUP, PluginError, PluginManager, get_plugin_manager
from .registry import (
    ComponentRegistry,
    get_command,
    get_notifier,
    get_storage,
    get_task,
    list_commands,
    list_notifiers,
    list_storage,
    list_tasks,
    register_command,
    register_notifier,
    register_storage,
    register_task,
    registry,
)

__all__ = [
    # Base
    "PluginBase",
    "PluginInfo",
    "PluginState",
    "PluginStatus",
    "TaskPlugin",
    "NotifierPlugin",
    "StoragePlugin",
    # Manager
    "PluginManager",
    "PluginError",
    "get_plugin_manager",
    "ENTRY_POINT_GROUP",
    # Hooks
    "HookManager",
    "HookEntry",
    "HookPriority",
    "hook",
    "on",
    "emit",
    "emit_async",
    # Registry
    "ComponentRegistry",
    "registry",
    "register_task",
    "register_notifier",
    "register_storage",
    "register_command",
    "get_task",
    "get_notifier",
    "get_storage",
    "get_command",
    "list_tasks",
    "list_notifiers",
    "list_storage",
    "list_commands",
]

__version__ = "1.0.0"
