# type: ignore
"""
AutoTarefas - Exemplo: Plugin de Notificação Slack
==================================================

Este plugin adiciona suporte a notificações via Slack.

Configuração:
    plugin.configure({
        "webhook_url": "https://hooks.slack.com/services/...",
        "channel": "#autotarefas",
        "username": "AutoTarefas Bot",
    })

Uso:
    notifier = SlackNotifierPlugin()
    notifier.configure({"webhook_url": "..."})
    notifier.send("Backup concluído com sucesso!")
"""

import json
import urllib.request
from typing import Any

from autotarefas.plugins import HookManager, NotifierPlugin, PluginInfo, register_notifier


class SlackNotifierPlugin(NotifierPlugin):
    """Plugin de notificação via Slack."""

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="slack-notifier",
            version="1.0.0",
            description="Notificações via Slack webhooks",
            author="AutoTarefas Team",
            tags=["notification", "slack", "webhook"],
            requires=["requests"],  # Opcional, usa urllib como fallback
        )

    def activate(self) -> None:
        """Registra o notifier ao ativar."""
        register_notifier("slack", self.__class__, plugin=self.name)

        # Registrar hook para notificar em falhas
        HookManager.register(
            "task.on_failure",
            self._on_task_failure,
            name="slack_failure_notify",
            plugin=self.name,
        )

        print(f"[{self.name}] Plugin ativado!")

    def deactivate(self) -> None:
        """Limpa recursos ao desativar."""
        print(f"[{self.name}] Plugin desativado!")

    def send(self, message: str, **kwargs: Any) -> bool:
        """
        Envia mensagem para o Slack.

        Args:
            message: Mensagem a enviar
            **kwargs: Opções adicionais (channel, username, icon_emoji)

        Returns:
            True se enviou com sucesso
        """
        webhook_url = self.get_config("webhook_url")
        if not webhook_url:
            print(f"[{self.name}] webhook_url não configurado!")
            return False

        payload = {
            "text": message,
            "channel": kwargs.get("channel", self.get_config("channel", "#general")),
            "username": kwargs.get("username", self.get_config("username", "AutoTarefas")),
            "icon_emoji": kwargs.get("icon_emoji", self.get_config("icon_emoji", ":robot_face:")),
        }

        # Adicionar attachments se fornecidos
        if "attachments" in kwargs:
            payload["attachments"] = kwargs["attachments"]

        try:
            # Tentar usar requests se disponível
            try:
                import requests

                response = requests.post(webhook_url, json=payload, timeout=10)
                return response.status_code == 200
            except ImportError:
                pass

            # Fallback para urllib
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200

        except Exception as e:
            print(f"[{self.name}] Erro ao enviar: {e}")
            return False

    def send_rich(
        self,
        title: str,
        message: str,
        color: str = "#36a64f",
        fields: list[dict[str, str]] | None = None,
    ) -> bool:
        """
        Envia mensagem rica com formatação.

        Args:
            title: Título da mensagem
            message: Corpo da mensagem
            color: Cor da barra lateral (hex)
            fields: Campos adicionais [{title, value, short}]

        Returns:
            True se enviou com sucesso
        """
        attachment = {
            "color": color,
            "title": title,
            "text": message,
            "ts": int(__import__("time").time()),
        }

        if fields:
            attachment["fields"] = fields

        return self.send("", attachments=[attachment])

    def _on_task_failure(self, task_name: str, error: str = "", **_kwargs: Any) -> None:
        """Hook para notificar falhas de tasks."""
        if not self.get_config("notify_on_failure", True):
            return

        self.send_rich(
            title=f"❌ Task Falhou: {task_name}",
            message=error or "Erro desconhecido",
            color="#dc3545",
            fields=[
                {"title": "Task", "value": task_name, "short": True},
                {"title": "Status", "value": "FAILURE", "short": True},
            ],
        )

    def notify_success(self, task_name: str, message: str = "") -> bool:
        """Notifica sucesso de uma task."""
        return self.send_rich(
            title=f"✅ Task Concluída: {task_name}",
            message=message or "Executada com sucesso!",
            color="#28a745",
        )

    def notify_warning(self, task_name: str, message: str) -> bool:
        """Notifica um aviso."""
        return self.send_rich(
            title=f"⚠️ Aviso: {task_name}",
            message=message,
            color="#ffc107",
        )
