# type: ignore
"""
AutoTarefas - Plugin Manager
============================

Gerenciador de plugins com descoberta automática via entry points.

Descoberta de Plugins:
    1. Entry points (pyproject.toml ou setup.py)
    2. Diretório de plugins local
    3. Registro manual

Exemplo de entry point (pyproject.toml):
    [project.entry-points."autotarefas.plugins"]
    meu-plugin = "meu_pacote:MeuPlugin"

Exemplo de uso:
    from autotarefas.plugins import PluginManager

    manager = PluginManager()
    manager.discover()
    manager.activate_all()

    # Listar plugins
    for plugin in manager.list_plugins():
        print(plugin.info)
"""

from __future__ import annotations

import importlib
import importlib.metadata
import logging
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import PluginBase, PluginStatus
from .hooks import HookManager

logger = logging.getLogger(__name__)

# Entry point group para plugins
ENTRY_POINT_GROUP = "autotarefas.plugins"


class PluginError(Exception):
    """Erro relacionado a plugins."""

    pass


class PluginManager:
    """
    Gerenciador de plugins do AutoTarefas.

    Responsável por descobrir, carregar, ativar e desativar plugins.
    """

    def __init__(self, plugins_dir: Path | str | None = None):
        """
        Inicializa o gerenciador de plugins.

        Args:
            plugins_dir: Diretório opcional para plugins locais
        """
        self._plugins: dict[str, PluginBase] = {}
        self._plugins_dir = Path(plugins_dir) if plugins_dir else None
        self._discovered = False

    @property
    def plugins(self) -> dict[str, PluginBase]:
        """Retorna dicionário de plugins carregados."""
        return self._plugins.copy()

    @property
    def active_plugins(self) -> dict[str, PluginBase]:
        """Retorna apenas plugins ativos."""
        return {name: plugin for name, plugin in self._plugins.items() if plugin.is_active}

    def discover(self) -> int:
        """
        Descobre plugins disponíveis.

        Busca em:
        1. Entry points registrados
        2. Diretório de plugins local (se configurado)

        Returns:
            Número de plugins descobertos
        """
        count = 0

        # 1. Descobrir via entry points
        count += self._discover_entry_points()

        # 2. Descobrir em diretório local
        if self._plugins_dir:
            count += self._discover_local(self._plugins_dir)

        self._discovered = True
        logger.info(f"Descobertos {count} plugins")

        return count

    def _discover_entry_points(self) -> int:
        """Descobre plugins via entry points."""
        count = 0

        try:
            eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)

            for ep in eps:
                try:
                    plugin_class = ep.load()
                    if self._is_valid_plugin(plugin_class):
                        plugin = plugin_class()
                        self._register(plugin)
                        count += 1
                        logger.debug(f"Plugin descoberto (entry point): {plugin.name}")
                        HookManager.trigger("plugin.discovered", plugin=plugin)
                except Exception as e:
                    logger.error(f"Erro ao carregar plugin {ep.name}: {e}")

        except Exception as e:
            logger.error(f"Erro ao descobrir entry points: {e}")

        return count

    def _discover_local(self, directory: Path) -> int:
        """Descobre plugins em um diretório local."""
        count = 0

        if not directory.exists():
            logger.warning(f"Diretório de plugins não existe: {directory}")
            return 0

        # Adicionar diretório ao path
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))

        for path in directory.glob("*.py"):
            if path.name.startswith("_"):
                continue

            module_name = path.stem
            try:
                module = importlib.import_module(module_name)

                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, PluginBase)
                        and attr is not PluginBase
                        and self._is_valid_plugin(attr)
                    ):
                        plugin = attr()
                        self._register(plugin)
                        count += 1
                        logger.debug(f"Plugin descoberto (local): {plugin.name}")
                        HookManager.trigger("plugin.discovered", plugin=plugin)

            except Exception as e:
                logger.error(f"Erro ao carregar módulo {module_name}: {e}")

        return count

    def _is_valid_plugin(self, plugin_class: type) -> bool:
        """Verifica se uma classe é um plugin válido."""
        try:
            return (
                isinstance(plugin_class, type)
                and issubclass(plugin_class, PluginBase)
                and plugin_class is not PluginBase
                and hasattr(plugin_class, "info")
            )
        except Exception:
            return False

    def _register(self, plugin: PluginBase) -> None:
        """Registra um plugin no manager."""
        name = plugin.info.name

        if name in self._plugins:
            logger.warning(f"Plugin já registrado: {name}")
            return

        self._plugins[name] = plugin
        logger.debug(f"Plugin registrado: {name}")

    def register(self, plugin: PluginBase) -> bool:
        """
        Registra um plugin manualmente.

        Args:
            plugin: Instância do plugin

        Returns:
            True se registrou com sucesso
        """
        if not isinstance(plugin, PluginBase):
            raise PluginError("Plugin deve herdar de PluginBase")

        name = plugin.info.name
        if name in self._plugins:
            return False

        self._register(plugin)
        HookManager.trigger("plugin.discovered", plugin=plugin)
        return True

    def unregister(self, name: str) -> bool:
        """
        Remove um plugin do registro.

        Args:
            name: Nome do plugin

        Returns:
            True se removeu com sucesso
        """
        if name not in self._plugins:
            return False

        plugin = self._plugins[name]

        # Desativar se estiver ativo
        if plugin.is_active:
            self.deactivate(name)

        del self._plugins[name]
        logger.info(f"Plugin removido: {name}")
        return True

    def get(self, name: str) -> PluginBase | None:
        """
        Obtém um plugin pelo nome.

        Args:
            name: Nome do plugin

        Returns:
            Plugin ou None se não encontrado
        """
        return self._plugins.get(name)

    def activate(self, name: str) -> bool:
        """
        Ativa um plugin.

        Args:
            name: Nome do plugin

        Returns:
            True se ativou com sucesso
        """
        plugin = self._plugins.get(name)
        if not plugin:
            raise PluginError(f"Plugin não encontrado: {name}")

        if plugin.is_active:
            return True

        try:
            plugin.activate()
            plugin._state.status = PluginStatus.ACTIVE
            plugin._state.activated_at = datetime.now()
            plugin._state.error_message = None

            logger.info(f"Plugin ativado: {name}")
            HookManager.trigger("plugin.activated", plugin=plugin)
            return True

        except Exception as e:
            plugin._state.status = PluginStatus.ERROR
            plugin._state.error_message = str(e)
            logger.error(f"Erro ao ativar plugin {name}: {e}")
            HookManager.trigger("plugin.error", plugin=plugin, error=e)
            return False

    def deactivate(self, name: str) -> bool:
        """
        Desativa um plugin.

        Args:
            name: Nome do plugin

        Returns:
            True se desativou com sucesso
        """
        plugin = self._plugins.get(name)
        if not plugin:
            raise PluginError(f"Plugin não encontrado: {name}")

        if not plugin.is_active:
            return True

        try:
            # Remover hooks do plugin
            HookManager.unregister_plugin(name)

            plugin.deactivate()
            plugin._state.status = PluginStatus.INACTIVE
            plugin._state.deactivated_at = datetime.now()

            logger.info(f"Plugin desativado: {name}")
            HookManager.trigger("plugin.deactivated", plugin=plugin)
            return True

        except Exception as e:
            plugin._state.status = PluginStatus.ERROR
            plugin._state.error_message = str(e)
            logger.error(f"Erro ao desativar plugin {name}: {e}")
            return False

    def activate_all(self) -> dict[str, bool]:
        """
        Ativa todos os plugins.

        Returns:
            Dicionário {nome: sucesso}
        """
        results = {}
        for name in self._plugins:
            results[name] = self.activate(name)
        return results

    def deactivate_all(self) -> dict[str, bool]:
        """
        Desativa todos os plugins.

        Returns:
            Dicionário {nome: sucesso}
        """
        results = {}
        for name in list(self._plugins.keys()):
            results[name] = self.deactivate(name)
        return results

    def reload(self, name: str) -> bool:
        """
        Recarrega um plugin.

        Args:
            name: Nome do plugin

        Returns:
            True se recarregou com sucesso
        """
        was_active = self._plugins.get(name, None)
        if was_active and was_active.is_active:
            self.deactivate(name)

        # Re-descobrir
        self.discover()

        if was_active and name in self._plugins:
            return self.activate(name)

        return name in self._plugins

    def list_plugins(self) -> list[PluginBase]:
        """Retorna lista de todos os plugins."""
        return list(self._plugins.values())

    def list_active(self) -> list[PluginBase]:
        """Retorna lista de plugins ativos."""
        return [p for p in self._plugins.values() if p.is_active]

    def list_inactive(self) -> list[PluginBase]:
        """Retorna lista de plugins inativos."""
        return [p for p in self._plugins.values() if not p.is_active]

    def __iter__(self) -> Iterator[PluginBase]:
        """Permite iteração sobre plugins."""
        return iter(self._plugins.values())

    def __len__(self) -> int:
        """Retorna número de plugins."""
        return len(self._plugins)

    def __contains__(self, name: str) -> bool:
        """Verifica se plugin existe."""
        return name in self._plugins

    def stats(self) -> dict[str, Any]:
        """Retorna estatísticas dos plugins."""
        active = len(self.list_active())
        inactive = len(self.list_inactive())
        total = len(self._plugins)

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "discovered": self._discovered,
            "plugins": {
                name: {
                    "version": p.info.version,
                    "status": p.state.status.value,
                    "author": p.info.author,
                }
                for name, p in self._plugins.items()
            },
        }


# Instância global (singleton)
_manager: PluginManager | None = None


def get_plugin_manager(plugins_dir: Path | str | None = None) -> PluginManager:
    """
    Retorna o gerenciador global de plugins.

    Args:
        plugins_dir: Diretório de plugins (apenas na primeira chamada)

    Returns:
        Instância do PluginManager
    """
    global _manager
    if _manager is None:
        _manager = PluginManager(plugins_dir)
    return _manager
