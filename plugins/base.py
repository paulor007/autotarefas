# type: ignore
"""
AutoTarefas - Plugin Base
=========================

Classe base para criação de plugins.

Exemplo de uso:
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
            print("Plugin ativado!")

        def deactivate(self) -> None:
            print("Plugin desativado!")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PluginStatus(Enum):
    """Status possíveis de um plugin."""

    INACTIVE = "inactive"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class PluginInfo:
    """Informações de um plugin."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    email: str = ""
    url: str = ""
    license: str = "MIT"
    requires: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    min_autotarefas_version: str = "1.0.0"

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "email": self.email,
            "url": self.url,
            "license": self.license,
            "requires": self.requires,
            "tags": self.tags,
            "min_autotarefas_version": self.min_autotarefas_version,
        }


@dataclass
class PluginState:
    """Estado atual de um plugin."""

    status: PluginStatus = PluginStatus.INACTIVE
    activated_at: datetime | None = None
    deactivated_at: datetime | None = None
    error_message: str | None = None
    config: dict[str, Any] = field(default_factory=dict)


class PluginBase(ABC):
    """
    Classe base abstrata para plugins do AutoTarefas.

    Todos os plugins devem herdar desta classe e implementar
    os métodos abstratos.
    """

    def __init__(self):
        self._state = PluginState()
        self._hooks: dict[str, list[Callable]] = {}

    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Retorna informações do plugin."""
        return None

    @property
    def state(self) -> PluginState:
        """Retorna o estado atual do plugin."""
        return self._state

    @property
    def is_active(self) -> bool:
        """Verifica se o plugin está ativo."""
        return self._state.status == PluginStatus.ACTIVE

    @property
    def name(self) -> str:
        """Nome do plugin (atalho)."""
        return self.info.name

    @property
    def version(self) -> str:
        """Versão do plugin (atalho)."""
        return self.info.version

    def activate(self) -> None:
        """
        Ativa o plugin.

        Sobrescreva este método para executar ações na ativação.
        """
        return None

    def deactivate(self) -> None:
        """
        Desativa o plugin.

        Sobrescreva este método para executar ações na desativação.
        """
        return None

    def configure(self, config: dict[str, Any]) -> None:
        """
        Configura o plugin.

        Args:
            config: Dicionário de configurações
        """
        self._state.config.update(config)

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Obtém uma configuração do plugin.

        Args:
            key: Chave da configuração
            default: Valor padrão se não existir

        Returns:
            Valor da configuração
        """
        return self._state.config.get(key, default)

    def register_hook(self, event: str, callback: Callable) -> None:
        """
        Registra um hook para um evento.

        Args:
            event: Nome do evento
            callback: Função a ser chamada
        """
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)

    def unregister_hook(self, event: str, callback: Callable) -> None:
        """
        Remove um hook de um evento.

        Args:
            event: Nome do evento
            callback: Função a ser removida
        """
        if event in self._hooks and callback in self._hooks[event]:
            self._hooks[event].remove(callback)

    def get_hooks(self, event: str) -> list[Callable]:
        """
        Retorna hooks registrados para um evento.

        Args:
            event: Nome do evento

        Returns:
            Lista de callbacks
        """
        return self._hooks.get(event, [])

    def __repr__(self) -> str:
        return f"<Plugin: {self.info.name} v{self.info.version} ({self._state.status.value})>"


class TaskPlugin(PluginBase):
    """
    Plugin que adiciona novas tasks ao AutoTarefas.

    Exemplo:
        class MeuTaskPlugin(TaskPlugin):
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(name="meu-task-plugin", version="1.0.0")

            def get_tasks(self) -> dict[str, type]:
                return {"minha_task": MinhaTask}
    """

    @abstractmethod
    def get_tasks(self) -> dict[str, type]:
        """
        Retorna as tasks fornecidas pelo plugin.

        Returns:
            Dicionário {nome: classe_task}
        """
        pass


class NotifierPlugin(PluginBase):
    """
    Plugin para notificações customizadas.

    Exemplo:
        class SlackPlugin(NotifierPlugin):
            def send(self, message: str, **kwargs) -> bool:
                # Enviar para Slack
                return True
    """

    @abstractmethod
    def send(self, message: str, **kwargs: Any) -> bool:
        """
        Envia uma notificação.

        Args:
            message: Mensagem a enviar
            **kwargs: Argumentos adicionais

        Returns:
            True se enviou com sucesso
        """
        pass


class StoragePlugin(PluginBase):
    """
    Plugin para backends de armazenamento customizados.

    Exemplo:
        class FTPPlugin(StoragePlugin):
            def upload(self, local_path, remote_path) -> bool:
                # Upload via FTP
                return True
    """

    @abstractmethod
    def upload(self, local_path: str, remote_path: str, **kwargs: Any) -> bool:
        """Faz upload de arquivo."""
        pass

    @abstractmethod
    def download(self, remote_path: str, local_path: str, **kwargs: Any) -> bool:
        """Faz download de arquivo."""
        pass

    @abstractmethod
    def list_files(self, remote_path: str, **kwargs: Any) -> list[str]:
        """Lista arquivos remotos."""
        pass

    @abstractmethod
    def delete(self, remote_path: str, **kwargs: Any) -> bool:
        """Remove arquivo remoto."""
        pass
