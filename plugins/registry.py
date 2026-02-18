# type: ignore
"""
AutoTarefas - Plugin Registry
=============================

Registro centralizado de componentes fornecidos por plugins.

Componentes registráveis:
    - Tasks: Novas tarefas
    - Notifiers: Canais de notificação
    - Storage: Backends de armazenamento
    - Commands: Comandos CLI

Exemplo de uso:
    from autotarefas.plugins import registry

    # Registrar task
    registry.register_task("minha_task", MinhaTask)

    # Obter task
    task_class = registry.get_task("minha_task")

    # Listar tasks
    tasks = registry.list_tasks()
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class ComponentRegistry:
    """
    Registro central de componentes do AutoTarefas.

    Armazena tasks, notifiers, storage backends e outros
    componentes fornecidos por plugins.
    """

    def __init__(self):
        self._tasks: dict[str, type] = {}
        self._notifiers: dict[str, type] = {}
        self._storage: dict[str, type] = {}
        self._commands: dict[str, Callable] = {}
        self._custom: dict[str, dict[str, Any]] = {}

    # ==================== TASKS ====================

    def register_task(
        self,
        name: str,
        task_class: type,
        plugin: str | None = None,
        overwrite: bool = False,
    ) -> bool:
        """
        Registra uma task.

        Args:
            name: Nome identificador da task
            task_class: Classe da task
            plugin: Nome do plugin que registrou
            overwrite: Se True, sobrescreve existente

        Returns:
            True se registrou com sucesso
        """
        if name in self._tasks and not overwrite:
            logger.warning(f"Task já registrada: {name}")
            return False

        self._tasks[name] = task_class
        logger.debug(f"Task registrada: {name} (plugin: {plugin})")
        return True

    def unregister_task(self, name: str) -> bool:
        """Remove uma task do registro."""
        if name in self._tasks:
            del self._tasks[name]
            return True
        return False

    def get_task(self, name: str) -> type | None:
        """Obtém uma task pelo nome."""
        return self._tasks.get(name)

    def list_tasks(self) -> list[str]:
        """Lista nomes de todas as tasks."""
        return list(self._tasks.keys())

    def has_task(self, name: str) -> bool:
        """Verifica se uma task existe."""
        return name in self._tasks

    # ==================== NOTIFIERS ====================

    def register_notifier(
        self,
        name: str,
        notifier_class: type,
        plugin: str | None = None,
        overwrite: bool = False,
    ) -> bool:
        """Registra um notifier."""
        if name in self._notifiers and not overwrite:
            logger.warning(f"Notifier já registrado: {name}")
            return False

        self._notifiers[name] = notifier_class
        logger.debug(f"Notifier registrado: {name} (plugin: {plugin})")
        return True

    def unregister_notifier(self, name: str) -> bool:
        """Remove um notifier do registro."""
        if name in self._notifiers:
            del self._notifiers[name]
            return True
        return False

    def get_notifier(self, name: str) -> type | None:
        """Obtém um notifier pelo nome."""
        return self._notifiers.get(name)

    def list_notifiers(self) -> list[str]:
        """Lista nomes de todos os notifiers."""
        return list(self._notifiers.keys())

    def has_notifier(self, name: str) -> bool:
        """Verifica se um notifier existe."""
        return name in self._notifiers

    # ==================== STORAGE ====================

    def register_storage(
        self,
        name: str,
        storage_class: type,
        plugin: str | None = None,
        overwrite: bool = False,
    ) -> bool:
        """Registra um storage backend."""
        if name in self._storage and not overwrite:
            logger.warning(f"Storage já registrado: {name}")
            return False

        self._storage[name] = storage_class
        logger.debug(f"Storage registrado: {name} (plugin: {plugin})")
        return True

    def unregister_storage(self, name: str) -> bool:
        """Remove um storage do registro."""
        if name in self._storage:
            del self._storage[name]
            return True
        return False

    def get_storage(self, name: str) -> type | None:
        """Obtém um storage pelo nome."""
        return self._storage.get(name)

    def list_storage(self) -> list[str]:
        """Lista nomes de todos os storage backends."""
        return list(self._storage.keys())

    def has_storage(self, name: str) -> bool:
        """Verifica se um storage existe."""
        return name in self._storage

    # ==================== COMMANDS ====================

    def register_command(
        self,
        name: str,
        command_func: Callable,
        plugin: str | None = None,
        overwrite: bool = False,
    ) -> bool:
        """Registra um comando CLI."""
        if name in self._commands and not overwrite:
            logger.warning(f"Comando já registrado: {name}")
            return False

        self._commands[name] = command_func
        logger.debug(f"Comando registrado: {name} (plugin: {plugin})")
        return True

    def unregister_command(self, name: str) -> bool:
        """Remove um comando do registro."""
        if name in self._commands:
            del self._commands[name]
            return True
        return False

    def get_command(self, name: str) -> Callable | None:
        """Obtém um comando pelo nome."""
        return self._commands.get(name)

    def list_commands(self) -> list[str]:
        """Lista nomes de todos os comandos."""
        return list(self._commands.keys())

    def has_command(self, name: str) -> bool:
        """Verifica se um comando existe."""
        return name in self._commands

    # ==================== CUSTOM ====================

    def register_custom(
        self,
        category: str,
        name: str,
        component: Any,
        plugin: str | None = None,
        overwrite: bool = False,
    ) -> bool:
        """
        Registra um componente customizado.

        Args:
            category: Categoria do componente
            name: Nome identificador
            component: O componente
            plugin: Nome do plugin
            overwrite: Se True, sobrescreve existente
        """
        if category not in self._custom:
            self._custom[category] = {}

        if name in self._custom[category] and not overwrite:
            logger.warning(f"Componente já registrado: {category}/{name}")
            return False

        self._custom[category][name] = component
        logger.debug(f"Componente registrado: {category}/{name} (plugin: {plugin})")
        return True

    def get_custom(self, category: str, name: str) -> Any | None:
        """Obtém um componente customizado."""
        return self._custom.get(category, {}).get(name)

    def list_custom(self, category: str) -> list[str]:
        """Lista componentes de uma categoria."""
        return list(self._custom.get(category, {}).keys())

    def list_categories(self) -> list[str]:
        """Lista todas as categorias customizadas."""
        return list(self._custom.keys())

    # ==================== UTILS ====================

    def clear(self) -> None:
        """Limpa todos os registros."""
        self._tasks.clear()
        self._notifiers.clear()
        self._storage.clear()
        self._commands.clear()
        self._custom.clear()

    def clear_plugin(self, _plugin: str) -> int:
        """
        Remove todos os componentes de um plugin.

        Note: Requer que os componentes tenham sido registrados
        com o parâmetro plugin.

        Returns:
            Número de componentes removidos
        """
        # Não implementado completamente - requer tracking de plugin
        logger.warning("clear_plugin requer implementação de tracking")
        return 0

    def stats(self) -> dict[str, int]:
        """Retorna estatísticas do registro."""
        custom_count = sum(len(v) for v in self._custom.values())
        return {
            "tasks": len(self._tasks),
            "notifiers": len(self._notifiers),
            "storage": len(self._storage),
            "commands": len(self._commands),
            "custom_categories": len(self._custom),
            "custom_components": custom_count,
            "total": len(self._tasks) + len(self._notifiers) + len(self._storage) + len(self._commands) + custom_count,
        }


# Instância global (singleton)
registry = ComponentRegistry()

# Aliases para acesso direto
register_task = registry.register_task
register_notifier = registry.register_notifier
register_storage = registry.register_storage
register_command = registry.register_command
get_task = registry.get_task
get_notifier = registry.get_notifier
get_storage = registry.get_storage
get_command = registry.get_command
list_tasks = registry.list_tasks
list_notifiers = registry.list_notifiers
list_storage = registry.list_storage
list_commands = registry.list_commands
