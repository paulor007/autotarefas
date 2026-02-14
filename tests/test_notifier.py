"""
Testes do módulo de notificações (notifier).

Testa:
    - NotificationLevel: Níveis de severidade
    - NotificationChannel: Canais disponíveis
    - Notification: Entidade de notificação
    - NotificationResult: Resultado por canal
    - ChannelConfig: Configuração de canal
    - Notifier: Orquestrador multi-canal
    - Singleton: get_notifier, reset_notifier
    - Conveniência: notify()
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

# ============================================================================
# Testes de NotificationLevel
# ============================================================================


class TestNotificationLevel:
    """Testes do enum NotificationLevel."""

    def test_level_values(self) -> None:
        """Deve ter todos os níveis esperados."""
        from autotarefas.core.notifier import NotificationLevel

        assert NotificationLevel.DEBUG.value == "debug"
        assert NotificationLevel.INFO.value == "info"
        assert NotificationLevel.SUCCESS.value == "success"
        assert NotificationLevel.WARNING.value == "warning"
        assert NotificationLevel.ERROR.value == "error"
        assert NotificationLevel.CRITICAL.value == "critical"

    def test_level_emoji(self) -> None:
        """Cada nível deve ter emoji."""
        from autotarefas.core.notifier import NotificationLevel

        for level in NotificationLevel:
            assert level.emoji is not None
            assert len(level.emoji) > 0

    def test_level_color(self) -> None:
        """Cada nível deve ter cor."""
        from autotarefas.core.notifier import NotificationLevel

        for level in NotificationLevel:
            assert level.color is not None
            assert level.color.startswith("#")

    def test_level_priority_ordering(self) -> None:
        """Prioridades devem estar ordenadas."""
        from autotarefas.core.notifier import NotificationLevel

        assert NotificationLevel.DEBUG.priority < NotificationLevel.INFO.priority
        assert NotificationLevel.INFO.priority <= NotificationLevel.SUCCESS.priority
        assert NotificationLevel.WARNING.priority < NotificationLevel.ERROR.priority
        assert NotificationLevel.ERROR.priority < NotificationLevel.CRITICAL.priority

    def test_level_from_string(self) -> None:
        """Deve converter string para enum."""
        from autotarefas.core.notifier import NotificationLevel

        assert NotificationLevel("info") == NotificationLevel.INFO
        assert NotificationLevel("error") == NotificationLevel.ERROR


# ============================================================================
# Testes de NotificationChannel
# ============================================================================


class TestNotificationChannel:
    """Testes do enum NotificationChannel."""

    def test_channel_values(self) -> None:
        """Deve ter todos os canais esperados."""
        from autotarefas.core.notifier import NotificationChannel

        assert NotificationChannel.CONSOLE.value == "console"
        assert NotificationChannel.EMAIL.value == "email"
        assert NotificationChannel.FILE.value == "file"
        assert NotificationChannel.WEBHOOK.value == "webhook"
        assert NotificationChannel.CALLBACK.value == "callback"


# ============================================================================
# Testes de Notification
# ============================================================================


class TestNotification:
    """Testes da dataclass Notification."""

    def test_notification_creation(self) -> None:
        """Deve criar notificação corretamente."""
        from autotarefas.core.notifier import Notification, NotificationLevel

        notif = Notification(
            title="Test Alert",
            message="Something happened",
            level=NotificationLevel.WARNING,
        )

        assert notif.title == "Test Alert"
        assert notif.message == "Something happened"
        assert notif.level == NotificationLevel.WARNING

    def test_notification_defaults(self) -> None:
        """Deve ter valores padrão corretos."""
        from autotarefas.core.notifier import Notification, NotificationLevel

        notif = Notification(title="Test", message="Msg")

        assert notif.level == NotificationLevel.INFO
        assert notif.source == "autotarefas"
        assert notif.data == {}
        assert notif.tags == []
        assert isinstance(notif.timestamp, datetime)

    def test_notification_empty_title_gets_default(self) -> None:
        """Título vazio deve receber default do nível."""
        from autotarefas.core.notifier import Notification, NotificationLevel

        notif = Notification(title="", message="Content", level=NotificationLevel.ERROR)

        assert notif.title != ""

    def test_notification_empty_message_gets_default(self) -> None:
        """Mensagem vazia deve receber placeholder."""
        from autotarefas.core.notifier import Notification

        notif = Notification(title="Alert", message="")

        assert notif.message != ""

    def test_formatted_title(self) -> None:
        """formatted_title deve incluir emoji."""
        from autotarefas.core.notifier import Notification, NotificationLevel

        notif = Notification(
            title="Alert", message="Msg", level=NotificationLevel.SUCCESS
        )

        assert notif.level.emoji in notif.formatted_title

    def test_formatted_message(self) -> None:
        """formatted_message deve incluir source."""
        from autotarefas.core.notifier import Notification

        notif = Notification(title="Test", message="Content", source="backup")

        assert "backup" in notif.formatted_message

    def test_to_dict(self) -> None:
        """to_dict deve retornar dicionário serializável."""
        from autotarefas.core.notifier import Notification, NotificationLevel

        notif = Notification(
            title="Test",
            message="Content",
            level=NotificationLevel.INFO,
            source="monitor",
            tags=["daily"],
            data={"cpu": 95.0},
        )

        data = notif.to_dict()

        assert isinstance(data, dict)
        assert data["title"] == "Test"
        assert data["level"] == "info"
        assert data["source"] == "monitor"
        assert data["tags"] == ["daily"]

    def test_from_dict(self) -> None:
        """from_dict deve recriar notificação."""
        from autotarefas.core.notifier import Notification, NotificationLevel

        payload = {
            "title": "From Dict",
            "message": "Recreated",
            "level": "warning",
            "source": "scheduler",
            "tags": ["test"],
        }

        notif = Notification.from_dict(payload)

        assert notif.title == "From Dict"
        assert notif.level == NotificationLevel.WARNING
        assert notif.source == "scheduler"

    def test_roundtrip(self) -> None:
        """to_dict -> from_dict deve preservar dados."""
        from autotarefas.core.notifier import Notification, NotificationLevel

        original = Notification(
            title="Roundtrip",
            message="Test message",
            level=NotificationLevel.ERROR,
            source="backup",
            data={"files": 42},
            tags=["important"],
        )

        data = original.to_dict()
        restored = Notification.from_dict(data)

        assert restored.title == original.title
        assert restored.level == original.level
        assert restored.source == original.source

    def test_to_json(self) -> None:
        """to_json deve retornar JSON válido."""
        from autotarefas.core.notifier import Notification

        notif = Notification(title="JSON Test", message="Content")
        json_str = notif.to_json()

        parsed = json.loads(json_str)
        assert parsed["title"] == "JSON Test"


# ============================================================================
# Testes de NotificationResult
# ============================================================================


class TestNotificationResult:
    """Testes da dataclass NotificationResult."""

    def test_result_creation(self) -> None:
        """Deve criar resultado corretamente."""
        from autotarefas.core.notifier import NotificationChannel, NotificationResult

        result = NotificationResult(
            success=True,
            channel=NotificationChannel.CONSOLE,
        )

        assert result.is_success is True
        assert result.channel == NotificationChannel.CONSOLE

    def test_success_result_factory(self) -> None:
        """success_result deve criar resultado de sucesso."""
        from autotarefas.core.notifier import NotificationChannel, NotificationResult

        result = NotificationResult.success_result(
            NotificationChannel.FILE,
            path="/tmp/log.txt",
        )

        assert result.is_success is True
        assert result.channel == NotificationChannel.FILE
        assert "path" in result.details

    def test_failure_result_factory(self) -> None:
        """failure_result deve criar resultado de falha."""
        from autotarefas.core.notifier import NotificationChannel, NotificationResult

        result = NotificationResult.failure_result(
            NotificationChannel.EMAIL,
            error="SMTP connection refused",
        )

        assert result.is_success is False
        assert result.error == "SMTP connection refused"


# ============================================================================
# Testes de ChannelConfig
# ============================================================================


class TestChannelConfig:
    """Testes da dataclass ChannelConfig."""

    def test_config_defaults(self) -> None:
        """Deve ter defaults corretos."""
        from autotarefas.core.notifier import ChannelConfig, NotificationLevel

        config = ChannelConfig()

        assert config.enabled is True
        assert config.min_level == NotificationLevel.INFO
        assert config.options == {}

    def test_config_with_options(self) -> None:
        """Deve aceitar opções."""
        from autotarefas.core.notifier import ChannelConfig, NotificationLevel

        config = ChannelConfig(
            enabled=True,
            min_level=NotificationLevel.ERROR,
            options={"recipients": ["admin@test.com"]},
        )

        assert config.min_level == NotificationLevel.ERROR
        assert "recipients" in config.options


# ============================================================================
# Testes de Notifier
# ============================================================================


class TestNotifier:
    """Testes da classe Notifier."""

    def test_notifier_creation(self) -> None:
        """Deve criar notifier."""
        from autotarefas.core.notifier import Notifier

        notifier = Notifier()
        assert notifier is not None

    def test_add_channel(self) -> None:
        """Deve adicionar canal."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)

        channels = notifier.list_channels()
        assert len(channels) == 1
        assert channels[0]["channel"] == "console"

    def test_add_multiple_channels(self) -> None:
        """Deve suportar múltiplos canais."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)
        notifier.add_channel(NotificationChannel.FILE, path="/tmp/notif.log")

        channels = notifier.list_channels()
        assert len(channels) == 2

    def test_remove_channel(self) -> None:
        """Deve remover canal."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)

        result = notifier.remove_channel(NotificationChannel.CONSOLE)
        assert result is True
        assert len(notifier.list_channels()) == 0

    def test_remove_nonexistent_channel(self) -> None:
        """Deve retornar False para canal inexistente."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        result = notifier.remove_channel(NotificationChannel.WEBHOOK)
        assert result is False

    def test_enable_disable_channel(self) -> None:
        """Deve habilitar/desabilitar canal."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)

        notifier.disable_channel(NotificationChannel.CONSOLE)
        channels = notifier.list_channels()
        assert channels[0]["enabled"] is False

        notifier.enable_channel(NotificationChannel.CONSOLE)
        channels = notifier.list_channels()
        assert channels[0]["enabled"] is True

    def test_set_min_level(self) -> None:
        """Deve definir nível mínimo."""
        from autotarefas.core.notifier import (
            NotificationChannel,
            NotificationLevel,
            Notifier,
        )

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)

        notifier.set_min_level(NotificationChannel.CONSOLE, NotificationLevel.ERROR)

        channels = notifier.list_channels()
        assert channels[0]["min_level"] == "error"


class TestNotifierSend:
    """Testes de envio de notificações."""

    @pytest.fixture
    def notifier_with_console(self) -> Any:
        """Cria notifier com console habilitado."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)
        return notifier

    def test_notify_console(self, notifier_with_console: Any) -> None:
        """Deve enviar para console."""
        results = notifier_with_console.notify("Test message")

        assert len(results) == 1
        assert results[0].is_success is True

    def test_notify_respects_min_level(self) -> None:
        """Deve respeitar nível mínimo do canal."""
        from autotarefas.core.notifier import (
            NotificationChannel,
            NotificationLevel,
            Notifier,
        )

        notifier = Notifier()
        notifier.add_channel(
            NotificationChannel.CONSOLE,
            min_level=NotificationLevel.ERROR,
        )

        # INFO deve ser filtrado (abaixo de ERROR)
        results = notifier.notify("Debug msg", level=NotificationLevel.INFO)
        assert len(results) == 0

        # ERROR deve passar
        results = notifier.notify("Error msg", level=NotificationLevel.ERROR)
        assert len(results) == 1

    def test_notify_disabled_channel(self) -> None:
        """Canal desabilitado não deve enviar."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE, enabled=False)

        results = notifier.notify("Test")
        assert len(results) == 0

    def test_notify_file_channel(self, temp_dir: Path) -> None:
        """Deve gravar em arquivo."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        log_path = temp_dir / "notifications.log"

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.FILE, path=str(log_path))

        results = notifier.notify("File test message")

        assert len(results) == 1
        assert results[0].is_success is True
        assert log_path.exists()

        content = log_path.read_text()
        assert "File test message" in content

    def test_notify_file_jsonl_format(self, temp_dir: Path) -> None:
        """Deve gravar em JSONL quando configurado."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        log_path = temp_dir / "notifications.jsonl"

        notifier = Notifier()
        notifier.add_channel(
            NotificationChannel.FILE, path=str(log_path), format="jsonl"
        )

        notifier.notify("JSONL test")

        content = log_path.read_text().strip()
        data = json.loads(content)
        assert data["message"] == "JSONL test"

    def test_notify_callback_channel(self) -> None:
        """Deve executar callbacks."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CALLBACK)

        received: list[str] = []
        notifier.add_callback("test_cb", lambda n: received.append(n.message))

        notifier.notify("Callback test")

        assert len(received) == 1
        assert received[0] == "Callback test"

    def test_notify_specific_channels(self) -> None:
        """Deve enviar apenas para canais especificados."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)
        notifier.add_channel(NotificationChannel.CALLBACK)

        received: list[Any] = []
        notifier.add_callback("test_cb", lambda n: received.append(n))

        # Enviar apenas para CALLBACK
        results = notifier.notify(
            "Specific channel",
            channels=[NotificationChannel.CALLBACK],
        )

        assert len(results) == 1
        assert results[0].channel == NotificationChannel.CALLBACK


class TestNotifierCallbacks:
    """Testes de callbacks do Notifier."""

    def test_add_callback(self) -> None:
        """Deve registrar callback."""
        from autotarefas.core.notifier import Notifier

        notifier = Notifier()
        notifier.add_callback("my_cb", lambda _n: None)

        status = notifier.get_status()
        assert "my_cb" in status["callbacks"]

    def test_remove_callback(self) -> None:
        """Deve remover callback."""
        from autotarefas.core.notifier import Notifier

        notifier = Notifier()
        notifier.add_callback("temp_cb", lambda _n: None)

        result = notifier.remove_callback("temp_cb")
        assert result is True

        result = notifier.remove_callback("temp_cb")
        assert result is False

    def test_multiple_callbacks(self) -> None:
        """Deve executar múltiplos callbacks."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CALLBACK)

        results_a: list[int] = []
        results_b: list[int] = []
        notifier.add_callback("cb_a", lambda _n: results_a.append(1))
        notifier.add_callback("cb_b", lambda _n: results_b.append(1))

        notifier.notify("Multi callback test")

        assert len(results_a) == 1
        assert len(results_b) == 1


class TestNotifierHistory:
    """Testes de histórico do Notifier."""

    def test_history_records(self) -> None:
        """Deve registrar no histórico."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)

        notifier.notify("History test 1")
        notifier.notify("History test 2")

        history = notifier.get_history()
        assert len(history) == 2

    def test_history_limit(self) -> None:
        """get_history deve respeitar limite."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)

        for i in range(10):
            notifier.notify(f"Message {i}")

        history = notifier.get_history(limit=3)
        assert len(history) == 3

    def test_clear_history(self) -> None:
        """clear_history deve limpar e retornar contagem."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)

        notifier.notify("Msg 1")
        notifier.notify("Msg 2")

        count = notifier.clear_history()
        assert count == 2
        assert len(notifier.get_history()) == 0

    def test_history_format(self) -> None:
        """Histórico deve ter formato correto."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)

        notifier.notify("Format test", title="Test Title")

        history = notifier.get_history()
        entry = history[0]

        assert "notification" in entry
        assert "results" in entry
        assert entry["notification"]["title"] == "Test Title"


class TestNotifierConvenience:
    """Testes de métodos de conveniência."""

    def test_level_shortcuts(self) -> None:
        """Atalhos devem funcionar (info, warning, error, etc)."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)

        notifier.info("Info msg")
        notifier.warning("Warning msg")
        notifier.error("Error msg")
        notifier.success("Success msg")
        notifier.critical("Critical msg")
        notifier.debug("Debug msg")

        history = notifier.get_history()
        assert len(history) == 6

    def test_get_status(self) -> None:
        """get_status deve retornar snapshot."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CONSOLE)
        notifier.add_callback("test", lambda _n: None)

        status = notifier.get_status()

        assert isinstance(status, dict)
        assert "channels" in status
        assert "callbacks" in status
        assert "history_size" in status

    def test_set_file_path(self, temp_dir: Path) -> None:
        """set_file_path deve configurar caminho padrão."""
        from autotarefas.core.notifier import Notifier

        notifier = Notifier()
        log_path = temp_dir / "default.log"
        notifier.set_file_path(log_path)

        status = notifier.get_status()
        assert str(log_path) in (status.get("file_path") or "")

    def test_set_email_recipients(self) -> None:
        """set_email_recipients deve configurar destinatários."""
        from autotarefas.core.notifier import Notifier

        notifier = Notifier()
        notifier.set_email_recipients(["admin@test.com"])

        status = notifier.get_status()
        assert "admin@test.com" in status["email_recipients"]


# ============================================================================
# Testes de Singleton
# ============================================================================


class TestNotifierSingleton:
    """Testes de get_notifier e reset_notifier."""

    def test_get_notifier_returns_instance(self) -> None:
        """Deve retornar instância."""
        from autotarefas.core.notifier import Notifier, get_notifier, reset_notifier

        reset_notifier()
        notifier = get_notifier()

        assert isinstance(notifier, Notifier)
        reset_notifier()

    def test_singleton_consistency(self) -> None:
        """Deve retornar mesma instância."""
        from autotarefas.core.notifier import get_notifier, reset_notifier

        reset_notifier()
        n1 = get_notifier()
        n2 = get_notifier()

        assert n1 is n2
        reset_notifier()

    def test_reset_creates_new(self) -> None:
        """reset deve criar nova instância."""
        from autotarefas.core.notifier import get_notifier, reset_notifier

        reset_notifier()
        n1 = get_notifier()
        reset_notifier()
        n2 = get_notifier()

        assert n1 is not n2
        reset_notifier()

    def test_singleton_has_console(self) -> None:
        """Singleton deve ter console habilitado por padrão."""
        from autotarefas.core.notifier import get_notifier, reset_notifier

        reset_notifier()
        notifier = get_notifier()

        channels = notifier.list_channels()
        channel_names = [c["channel"] for c in channels]
        assert "console" in channel_names

        reset_notifier()


# ============================================================================
# Testes da função notify()
# ============================================================================


class TestNotifyFunction:
    """Testes da função de conveniência notify()."""

    def test_notify_function(self) -> None:
        """notify() deve usar singleton."""
        from autotarefas.core.notifier import notify, reset_notifier

        reset_notifier()

        results = notify("Quick notification")

        assert isinstance(results, list)
        reset_notifier()

    def test_notify_with_level(self) -> None:
        """notify() deve aceitar nível."""
        from autotarefas.core.notifier import NotificationLevel, notify, reset_notifier

        reset_notifier()
        results = notify("Error!", level=NotificationLevel.ERROR)

        assert isinstance(results, list)
        reset_notifier()


# ============================================================================
# Testes de Edge Cases
# ============================================================================


class TestNotifierEdgeCases:
    """Testes de casos extremos."""

    def test_notification_with_large_data(self) -> None:
        """Deve tratar dados grandes."""
        from autotarefas.core.notifier import Notification

        large_data = {f"key_{i}": f"value_{i}" for i in range(1000)}

        notif = Notification(
            title="Large Data",
            message="Test",
            data=large_data,
        )

        assert len(notif.data) == 1000

    def test_notification_special_characters(self) -> None:
        """Deve tratar caracteres especiais."""
        from autotarefas.core.notifier import Notification

        notif = Notification(
            title="Título com <HTML> & 'aspas'",
            message="Mensagem com\nnova linha\te tab",
            source="módulo_ação",
        )

        assert "<HTML>" in notif.title
        assert "\n" in notif.message

    def test_file_channel_creates_directory(self, temp_dir: Path) -> None:
        """FILE deve criar diretório se não existir."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        deep_path = temp_dir / "deep" / "nested" / "notifications.log"

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.FILE, path=str(deep_path))

        notifier.notify("Deep directory test")

        assert deep_path.exists()

    def test_callback_error_handling(self) -> None:
        """Deve tratar erros em callbacks sem quebrar."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier.add_channel(NotificationChannel.CALLBACK)

        def bad_callback(n: Any) -> None:
            raise RuntimeError("Callback exploded!")

        notifier.add_callback("bad", bad_callback)

        # Não deve propagar exceção
        results = notifier.notify("Should not crash")
        assert isinstance(results, list)

    def test_history_max_size(self) -> None:
        """Histórico deve respeitar limite máximo."""
        from autotarefas.core.notifier import NotificationChannel, Notifier

        notifier = Notifier()
        notifier._history_max_size = 5
        notifier.add_channel(NotificationChannel.CONSOLE)

        for i in range(20):
            notifier.notify(f"Message {i}")

        history = notifier.get_history(limit=100)
        assert len(history) <= 5
