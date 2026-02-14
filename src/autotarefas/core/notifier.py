"""
Sistema de Notificações do AutoTarefas.

Este módulo fornece notificações multi-canal (console, email, arquivo, webhook e callbacks),
com filtro por nível mínimo de severidade em cada canal, histórico em memória e funções de
conveniência.

Principais componentes:
    - NotificationLevel: níveis de severidade (DEBUG/INFO/SUCCESS/WARNING/ERROR/CRITICAL)
    - NotificationChannel: canais disponíveis (CONSOLE/EMAIL/FILE/WEBHOOK/CALLBACK)
    - Notification: entidade de notificação (título, mensagem, nível, origem, dados)
    - NotificationResult: resultado por canal (success/error/details)
    - Notifier: orquestrador de envio multi-canal
    - get_notifier(): singleton do Notifier
    - notify(): função de conveniência para uso rápido

Exemplos:
    from autotarefas.core.notifier import notify, NotificationLevel

    # Notificação simples
    notify("Backup concluído com sucesso!", level=NotificationLevel.SUCCESS)

    # Notificação com canais configurados
    from autotarefas.core.notifier import get_notifier, NotificationChannel

    n = get_notifier()
    n.add_channel(NotificationChannel.EMAIL, min_level=NotificationLevel.ERROR, recipients=["ops@exemplo.com"])
    n.notify("Serviço iniciado", level=NotificationLevel.INFO)
"""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from autotarefas.core.logger import logger

# =============================================================================
# Helpers
# =============================================================================


def _utcnow() -> datetime:
    """Retorna datetime em UTC (timezone-aware)."""
    return datetime.now(UTC)


def _ensure_list_str(value: Any) -> list[str]:
    """
    Normaliza entradas comuns para list[str].

    Regras:
        - None -> []
        - str -> [str] (se não vazia)
        - list/tuple -> filtra e normaliza strings não vazias
        - outros -> []
    """
    if value is None:
        return []

    if isinstance(value, str):
        v = value.strip()
        return [v] if v else []

    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                s = item.strip()
                if s:
                    out.append(s)
        return out

    return []


def _safe_int(value: Any, default: int) -> int:
    """Converte value para int de forma segura."""
    try:
        return int(value)
    except Exception:
        return default


# =============================================================================
# Enums
# =============================================================================


class NotificationLevel(Enum):
    """
    Nível de severidade/importance da notificação.

    Valores:
        DEBUG: informações de debug (desenvolvimento)
        INFO: informação geral
        SUCCESS: operação concluída com sucesso
        WARNING: aviso
        ERROR: erro
        CRITICAL: erro crítico (alta prioridade)
    """

    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def emoji(self) -> str:
        """Emoji correspondente ao nível."""
        return _LEVEL_EMOJIS.get(self, "📢")

    @property
    def color(self) -> str:
        """Cor correspondente ao nível (para HTML/Rich)."""
        return _LEVEL_COLORS.get(self, "#000000")

    @property
    def priority(self) -> int:
        """Prioridade numérica (maior = mais importante)."""
        return _LEVEL_PRIORITIES.get(self, 1)


_LEVEL_EMOJIS: dict[NotificationLevel, str] = {
    NotificationLevel.DEBUG: "🔍",
    NotificationLevel.INFO: "ℹ️",
    NotificationLevel.SUCCESS: "✅",
    NotificationLevel.WARNING: "⚠️",
    NotificationLevel.ERROR: "❌",
    NotificationLevel.CRITICAL: "🚨",
}

_LEVEL_COLORS: dict[NotificationLevel, str] = {
    NotificationLevel.DEBUG: "#6c757d",
    NotificationLevel.INFO: "#0dcaf0",
    NotificationLevel.SUCCESS: "#198754",
    NotificationLevel.WARNING: "#ffc107",
    NotificationLevel.ERROR: "#dc3545",
    NotificationLevel.CRITICAL: "#dc3545",
}

_LEVEL_PRIORITIES: dict[NotificationLevel, int] = {
    NotificationLevel.DEBUG: 0,
    NotificationLevel.INFO: 1,
    NotificationLevel.SUCCESS: 2,
    NotificationLevel.WARNING: 3,
    NotificationLevel.ERROR: 4,
    NotificationLevel.CRITICAL: 5,
}


class NotificationChannel(Enum):
    """
    Canal de notificação.

    Valores:
        CONSOLE: imprime no console (Rich, quando disponível)
        EMAIL: envia por e-mail (usa autotarefas.core.email)
        FILE: grava em arquivo (texto ou jsonl)
        WEBHOOK: envia para webhook (POST JSON)
        CALLBACK: executa callbacks registrados
    """

    CONSOLE = "console"
    EMAIL = "email"
    FILE = "file"
    WEBHOOK = "webhook"
    CALLBACK = "callback"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass(slots=True)
class Notification:
    """
    Representa uma notificação.

    Attributes:
        title: Título da notificação.
        message: Mensagem principal.
        level: Nível de severidade.
        source: Origem (ex: "backup", "scheduler").
        timestamp: Data/hora (UTC por padrão).
        data: Dados adicionais (estruturados).
        tags: Tags para categorização.
        metadata: Metadados extras (livre).

        email_to: Destinatários específicos para EMAIL (opcional).
        email_template: Nome de template HTML (opcional).
    """

    title: str
    message: str
    level: NotificationLevel = NotificationLevel.INFO
    source: str = "autotarefas"
    timestamp: datetime = field(default_factory=_utcnow)
    data: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    email_to: list[str] = field(default_factory=list)
    email_template: str | None = None

    def __post_init__(self) -> None:
        self.title = (self.title or "").strip()
        self.message = (self.message or "").strip()
        self.source = (self.source or "autotarefas").strip()

        if not self.title:
            self.title = self.level.value.title()
        if not self.message:
            self.message = "(mensagem vazia)"

        # Normaliza destinos
        self.email_to = _ensure_list_str(self.email_to)

    @property
    def formatted_title(self) -> str:
        """Título formatado com emoji."""
        return f"{self.level.emoji} {self.title}"

    @property
    def formatted_message(self) -> str:
        """Mensagem formatada com source."""
        return f"[{self.source}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário (serializável)."""
        return {
            "title": self.title,
            "message": self.message,
            "level": self.level.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Notification:
        """
        Cria Notification a partir de um dicionário.

        Espera chaves compatíveis com to_dict(). Campos ausentes ganham defaults.
        """
        ts = payload.get("timestamp")
        if isinstance(ts, str):
            try:
                timestamp = datetime.fromisoformat(ts)
            except ValueError:
                timestamp = _utcnow()
        elif isinstance(ts, datetime):
            timestamp = ts
        else:
            timestamp = _utcnow()

        raw_level = payload.get("level", NotificationLevel.INFO.value)
        try:
            level = (
                raw_level
                if isinstance(raw_level, NotificationLevel)
                else NotificationLevel(str(raw_level))
            )
        except Exception:
            level = NotificationLevel.INFO

        return cls(
            title=str(payload.get("title", "") or ""),
            message=str(payload.get("message", "") or ""),
            level=level,
            source=str(payload.get("source", "autotarefas") or "autotarefas"),
            timestamp=timestamp,
            data=payload.get("data", {}) or {},
            tags=_ensure_list_str(payload.get("tags")),
            metadata=payload.get("metadata", {}) or {},
            email_to=_ensure_list_str(payload.get("email_to")),
            email_template=payload.get("email_template"),
        )

    def to_json(self) -> str:
        """Converte para JSON (pretty)."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass(slots=True)
class NotificationResult:
    """
    Resultado do envio de notificação.

    Attributes:
        success: Se o envio foi bem sucedido.
        channel: Canal utilizado.
        error: Mensagem de erro (quando fail).
        sent_at: Timestamp (UTC).
        details: Informações adicionais (ex: status_code, message_id).
    """

    success: bool
    channel: NotificationChannel
    error: str | None = None
    sent_at: datetime = field(default_factory=_utcnow)
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_result(
        cls, channel: NotificationChannel, **details: Any
    ) -> NotificationResult:
        return cls(success=True, channel=channel, details=details)

    @classmethod
    def failure_result(
        cls, channel: NotificationChannel, error: str
    ) -> NotificationResult:
        return cls(success=False, channel=channel, error=error)

    @property
    def is_success(self) -> bool:
        """Alias para success (compatibilidade com TaskResult)."""
        return self.success


@dataclass(slots=True)
class ChannelConfig:
    """
    Configuração de um canal.

    Attributes:
        enabled: Se o canal está ativo.
        min_level: Nível mínimo para permitir envio.
        options: Opções específicas do canal (ex: recipients, path, url, format).
    """

    enabled: bool = True
    min_level: NotificationLevel = NotificationLevel.INFO
    options: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Notifier
# =============================================================================


class Notifier:
    """
    Gerenciador de notificações multi-canal.

    Permite configurar canais, definir nível mínimo por canal e disparar notificações
    para um ou vários canais em uma chamada.

    - Histórico fica em memória (padrão: 1000 entradas).
    - Thread-safe para configuração/histórico.
    """

    def __init__(self) -> None:
        self._channels: dict[NotificationChannel, ChannelConfig] = {}
        self._callbacks: dict[str, Callable[[Notification], None]] = {}

        self._history: list[tuple[Notification, list[NotificationResult]]] = []
        self._history_max_size = 1000

        # Defaults globais (podem ser sobrescritos via add_channel/options)
        self._file_path: Path | None = None
        self._webhook_url: str | None = None
        self._email_recipients: list[str] = []

        self._lock = threading.Lock()
        logger.debug("[notifier] Notifier inicializado")

    # -------------------------------------------------------------------------
    # Configuração de canais
    # -------------------------------------------------------------------------

    def add_channel(
        self,
        channel: NotificationChannel,
        enabled: bool = True,
        min_level: NotificationLevel = NotificationLevel.INFO,
        **options: Any,
    ) -> None:
        """
        Adiciona/atualiza a configuração de um canal.

        Args:
            channel: Canal alvo.
            enabled: Se o canal estará habilitado.
            min_level: Nível mínimo para envio.
            **options: Opções do canal.
                - EMAIL: recipients (list[str] ou str)
                - FILE: path (str/Path), format ("text"|"jsonl")
                - WEBHOOK: url (str), timeout (int)
        """
        cfg = ChannelConfig(enabled=enabled, min_level=min_level, options=dict(options))
        with self._lock:
            self._channels[channel] = cfg
        logger.debug(
            f"[notifier] Canal configurado: {channel.value} (min={min_level.value} enabled={enabled})"
        )

    def remove_channel(self, channel: NotificationChannel) -> bool:
        """Remove um canal configurado."""
        with self._lock:
            if channel in self._channels:
                del self._channels[channel]
                return True
        return False

    def enable_channel(self, channel: NotificationChannel) -> bool:
        """Habilita um canal."""
        with self._lock:
            cfg = self._channels.get(channel)
            if cfg:
                cfg.enabled = True
                return True
        return False

    def disable_channel(self, channel: NotificationChannel) -> bool:
        """Desabilita um canal."""
        with self._lock:
            cfg = self._channels.get(channel)
            if cfg:
                cfg.enabled = False
                return True
        return False

    def set_min_level(
        self, channel: NotificationChannel, level: NotificationLevel
    ) -> bool:
        """Define o nível mínimo de severidade para um canal."""
        with self._lock:
            cfg = self._channels.get(channel)
            if cfg:
                cfg.min_level = level
                return True
        return False

    def list_channels(self) -> list[dict[str, Any]]:
        """Lista canais configurados."""
        with self._lock:
            items = list(self._channels.items())

        return [
            {
                "channel": ch.value,
                "enabled": cfg.enabled,
                "min_level": cfg.min_level.value,
                "options": dict(cfg.options),
            }
            for ch, cfg in items
        ]

    # -------------------------------------------------------------------------
    # Configurações globais (atalhos)
    # -------------------------------------------------------------------------

    def set_file_path(self, path: str | Path) -> None:
        """Define caminho padrão para FILE (quando canal não define path)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._file_path = p

    def set_webhook_url(self, url: str) -> None:
        """Define URL padrão para WEBHOOK (quando canal não define url)."""
        self._webhook_url = (url or "").strip()

    def set_email_recipients(self, recipients: list[str] | str) -> None:
        """Define destinatários padrão para EMAIL (quando canal não define recipients)."""
        self._email_recipients = _ensure_list_str(recipients)

    def add_callback(self, name: str, callback: Callable[[Notification], None]) -> None:
        """Registra um callback (usado pelo canal CALLBACK)."""
        self._callbacks[name] = callback

    def remove_callback(self, name: str) -> bool:
        """Remove um callback registrado."""
        if name in self._callbacks:
            del self._callbacks[name]
            return True
        return False

    # -------------------------------------------------------------------------
    # Envio
    # -------------------------------------------------------------------------

    def notify(
        self,
        message: str,
        title: str | None = None,
        level: NotificationLevel = NotificationLevel.INFO,
        source: str = "autotarefas",
        data: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        channels: list[NotificationChannel] | None = None,
        email_to: list[str] | str | None = None,
        email_template: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[NotificationResult]:
        """
        Envia uma notificação.

        Args:
            message: Mensagem principal.
            title: Título (default: level.title()).
            level: Nível de severidade.
            source: Origem (ex: "backup", "scheduler").
            data: Dados estruturados.
            tags: Tags.
            channels: Se informado, limita aos canais da lista. Se None, usa todos configurados.
            email_to: Destinatários específicos para esse envio (apenas canal EMAIL).
            email_template: Nome do template HTML (apenas canal EMAIL).
            metadata: Metadados adicionais.

        Returns:
            Lista de NotificationResult (um por canal que tentou enviar).
        """
        notif = Notification(
            title=title or level.value.title(),
            message=message,
            level=level,
            source=source,
            data=data or {},
            tags=tags or [],
            metadata=metadata or {},
            email_to=_ensure_list_str(email_to),
            email_template=email_template,
        )

        with self._lock:
            channels_snapshot = dict(self._channels)

        target_channels = channels or list(channels_snapshot.keys())

        results: list[NotificationResult] = []
        for ch in target_channels:
            cfg = channels_snapshot.get(ch)
            if not cfg:
                continue
            if not cfg.enabled:
                continue
            if notif.level.priority < cfg.min_level.priority:
                continue

            results.append(self._send_to_channel(notif, ch, cfg))

        self._add_to_history(notif, results)
        return results

    def _send_to_channel(
        self,
        notification: Notification,
        channel: NotificationChannel,
        config: ChannelConfig,
    ) -> NotificationResult:
        """Roteia a notificação para o handler do canal."""
        try:
            if channel == NotificationChannel.CONSOLE:
                return self._send_console(notification)
            if channel == NotificationChannel.EMAIL:
                return self._send_email(notification, config)
            if channel == NotificationChannel.FILE:
                return self._send_file(notification, config)
            if channel == NotificationChannel.WEBHOOK:
                return self._send_webhook(notification, config)
            if channel == NotificationChannel.CALLBACK:
                return self._send_callbacks(notification)
            return NotificationResult.failure_result(
                channel, f"Canal não suportado: {channel.value}"
            )
        except Exception as e:
            logger.exception(f"[notifier] Erro ao enviar para {channel.value}: {e}")
            return NotificationResult.failure_result(channel, str(e))

    # -------------------------------------------------------------------------
    # Implementações por canal
    # -------------------------------------------------------------------------

    def _send_console(self, notification: Notification) -> NotificationResult:
        """
        Envia para console usando Rich quando disponível; caso contrário, fallback em print().
        """
        try:
            from rich.console import Console
            from rich.panel import Panel

            console = Console()

            content = notification.message
            if notification.data:
                content += f"\n\n[dim]Dados: {notification.data}[/dim]"

            styles: dict[NotificationLevel, str] = {
                NotificationLevel.DEBUG: "dim",
                NotificationLevel.INFO: "cyan",
                NotificationLevel.SUCCESS: "green",
                NotificationLevel.WARNING: "yellow",
                NotificationLevel.ERROR: "red",
                NotificationLevel.CRITICAL: "bold red",
            }
            style = styles.get(notification.level, "white")

            subtitle = f"[dim]{notification.source} • {notification.timestamp.astimezone().strftime('%H:%M:%S')}[/dim]"
            console.print(
                Panel(
                    content,
                    title=notification.formatted_title,
                    subtitle=subtitle,
                    border_style=style,
                )
            )
            return NotificationResult.success_result(NotificationChannel.CONSOLE)

        except Exception:
            # Fallback sem Rich
            print(
                f"[{notification.level.value.upper()}] {notification.title}: {notification.message}"
            )
            return NotificationResult.success_result(NotificationChannel.CONSOLE)

    def _send_email(
        self, notification: Notification, config: ChannelConfig
    ) -> NotificationResult:
        """
        Envia por email.

        Regras de destinatários (ordem):
            1) notification.email_to
            2) self._email_recipients
            3) config.options["recipients"]
            4) settings.email.to_addr (se existir)
        """
        from autotarefas.core.email import EmailMessage, EmailPriority, get_email_sender

        recipients = (
            _ensure_list_str(notification.email_to)
            or _ensure_list_str(self._email_recipients)
            or _ensure_list_str(config.options.get("recipients"))
        )

        if not recipients:
            try:
                from autotarefas.config import settings

                recipients = _ensure_list_str(getattr(settings.email, "to_addr", ""))
            except Exception:
                recipients = []

        if not recipients:
            return NotificationResult.failure_result(
                NotificationChannel.EMAIL, "Nenhum destinatário configurado para EMAIL."
            )

        # Prioridade baseada no nível
        priority = EmailPriority.NORMAL
        if notification.level in (
            NotificationLevel.WARNING,
            NotificationLevel.ERROR,
            NotificationLevel.CRITICAL,
        ):
            priority = EmailPriority.HIGH

        html = self._render_email_html(notification)

        msg = EmailMessage(
            to=recipients,
            subject=f"[{notification.level.value.upper()}] {notification.title}",
            body=notification.message,
            html=html,
            priority=priority,
            tags=notification.tags,
        )

        result = get_email_sender().send(msg)
        if result.success:
            return NotificationResult.success_result(
                NotificationChannel.EMAIL,
                message_id=result.message_id,
                recipients=result.recipients_accepted,
            )

        return NotificationResult.failure_result(
            NotificationChannel.EMAIL,
            result.error or "Erro desconhecido ao enviar email.",
        )

    def _send_file(
        self, notification: Notification, config: ChannelConfig
    ) -> NotificationResult:
        """
        Salva em arquivo.

        Options:
            path: caminho do arquivo
            format: "text" (default) ou "jsonl"
        """
        file_path = self._file_path or config.options.get("path")
        if not file_path:
            return NotificationResult.failure_result(
                NotificationChannel.FILE, "Caminho do arquivo não configurado."
            )

        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        fmt = str(config.options.get("format", "text")).strip().lower()

        try:
            if fmt == "jsonl":
                line = json.dumps(notification.to_dict(), ensure_ascii=False) + "\n"
            else:
                line = (
                    f"[{notification.timestamp.isoformat()}] "
                    f"[{notification.level.value.upper()}] "
                    f"[{notification.source}] "
                    f"{notification.title}: {notification.message}\n"
                )

            with p.open("a", encoding="utf-8") as f:
                f.write(line)

            return NotificationResult.success_result(
                NotificationChannel.FILE, path=str(p), format=fmt
            )

        except Exception as e:
            return NotificationResult.failure_result(NotificationChannel.FILE, str(e))

    def _send_webhook(
        self, notification: Notification, config: ChannelConfig
    ) -> NotificationResult:
        """
        Envia para webhook via POST JSON.

        Options:
            url: URL do webhook
            timeout: timeout (segundos)
        """
        url = (self._webhook_url or config.options.get("url") or "").strip()
        if not url:
            return NotificationResult.failure_result(
                NotificationChannel.WEBHOOK, "URL do webhook não configurada."
            )

        timeout = _safe_int(config.options.get("timeout"), 10)

        payload = {
            "title": notification.title,
            "level": notification.level.value,
            "source": notification.source,
            "message": notification.message,
            "timestamp": notification.timestamp.isoformat(),
            "data": notification.data,
            "tags": notification.tags,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return NotificationResult.success_result(
                    NotificationChannel.WEBHOOK,
                    status_code=getattr(response, "status", None),
                )
        except Exception as e:
            return NotificationResult.failure_result(
                NotificationChannel.WEBHOOK, str(e)
            )

    def _send_callbacks(self, notification: Notification) -> NotificationResult:
        """
        Executa callbacks registrados.
        """
        if not self._callbacks:
            return NotificationResult.failure_result(
                NotificationChannel.CALLBACK, "Nenhum callback registrado."
            )

        executed: list[str] = []
        errors: list[str] = []

        for name, cb in list(self._callbacks.items()):
            try:
                cb(notification)
                executed.append(name)
            except Exception as e:
                errors.append(f"{name}: {e}")

        if errors:
            return NotificationResult.failure_result(
                NotificationChannel.CALLBACK, "; ".join(errors)
            )

        return NotificationResult.success_result(
            NotificationChannel.CALLBACK, callbacks_executed=executed
        )

    # -------------------------------------------------------------------------
    # Templates de email
    # -------------------------------------------------------------------------

    def _render_email_html(self, notification: Notification) -> str:
        """
        Renderiza HTML do email.

        - Se notification.email_template existir, tenta carregar em resources/templates/email/
        - Caso contrário, usa template inline simples (default)
        """
        if notification.email_template:
            template_path = self._get_template_path(notification.email_template)
            if template_path and template_path.exists():
                try:
                    return self._render_template(template_path, notification)
                except Exception as e:
                    logger.warning(
                        f"[notifier] Falha ao renderizar template '{notification.email_template}': {e}"
                    )

        data_block = ""
        if notification.data:
            data_block = f'<div class="data"><pre>{json.dumps(notification.data, indent=2, ensure_ascii=False)}</pre></div>'

        ts = notification.timestamp.astimezone().strftime("%d/%m/%Y %H:%M:%S")

        return f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; }}
    .notification {{ border-left: 4px solid {notification.level.color}; padding: 15px; background: #f8f9fa; }}
    .title {{ font-size: 18px; font-weight: bold; color: {notification.level.color}; }}
    .message {{ margin-top: 10px; color: #333; }}
    .meta {{ margin-top: 15px; font-size: 12px; color: #666; }}
    .data {{ margin-top: 10px; padding: 10px; background: #fff; border-radius: 6px; border: 1px solid #eee; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; }}
  </style>
</head>
<body>
  <div class="notification">
    <div class="title">{notification.level.emoji} {notification.title}</div>
    <div class="message">{notification.message}</div>
    {data_block}
    <div class="meta">Origem: {notification.source} • {ts}</div>
  </div>
</body>
</html>
"""

    def _get_template_path(self, template_name: str) -> Path | None:
        """
        Busca template em: src/autotarefas/resources/templates/email/

        Observação:
            Usa Path(__file__) para não depender de import do pacote.
        """
        name = (template_name or "").strip()
        if not name:
            return None
        if not name.endswith(".html"):
            name += ".html"

        # core/notifier.py -> autotarefas/core -> parents[1] = autotarefas
        base = Path(__file__).resolve().parents[1]
        path = base / "resources" / "templates" / "email" / name
        return path if path.exists() else None

    def _render_template(self, template_path: Path, notification: Notification) -> str:
        """
        Renderiza um template HTML (substituição simples via {{var}}).

        Variáveis disponíveis:
            title, message, level, level_emoji, level_color, source, timestamp, data, tags
        """
        template = template_path.read_text(encoding="utf-8")

        context = {
            "title": notification.title,
            "message": notification.message,
            "level": notification.level.value,
            "level_emoji": notification.level.emoji,
            "level_color": notification.level.color,
            "source": notification.source,
            "timestamp": notification.timestamp.astimezone().strftime(
                "%d/%m/%Y %H:%M:%S"
            ),
            "data": (
                json.dumps(notification.data, indent=2, ensure_ascii=False)
                if notification.data
                else ""
            ),
            "tags": ", ".join(notification.tags) if notification.tags else "",
        }

        for key, value in context.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))
            template = template.replace(f"{{{{ {key} }}}}", str(value))

        return template

    # -------------------------------------------------------------------------
    # Histórico
    # -------------------------------------------------------------------------

    def _add_to_history(
        self, notification: Notification, results: list[NotificationResult]
    ) -> None:
        """Adiciona ao histórico (com limite)."""
        with self._lock:
            self._history.append((notification, results))
            if len(self._history) > self._history_max_size:
                self._history = self._history[-self._history_max_size :]

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Obtém histórico de notificações (últimas N)."""
        n = max(int(limit), 1)
        with self._lock:
            snapshot = self._history[-n:]

        return [
            {
                "notification": notif.to_dict(),
                "results": [
                    {
                        "channel": r.channel.value,
                        "success": r.success,
                        "error": r.error,
                        "details": r.details,
                        "sent_at": r.sent_at.isoformat(),
                    }
                    for r in results
                ],
            }
            for notif, results in snapshot
        ]

    def clear_history(self) -> int:
        """Limpa o histórico e retorna a quantidade removida."""
        with self._lock:
            count = len(self._history)
            self._history.clear()
        return count

    # -------------------------------------------------------------------------
    # Conveniências
    # -------------------------------------------------------------------------

    def debug(self, message: str, **kwargs: Any) -> list[NotificationResult]:
        return self.notify(message, level=NotificationLevel.DEBUG, **kwargs)

    def info(self, message: str, **kwargs: Any) -> list[NotificationResult]:
        return self.notify(message, level=NotificationLevel.INFO, **kwargs)

    def success(self, message: str, **kwargs: Any) -> list[NotificationResult]:
        return self.notify(message, level=NotificationLevel.SUCCESS, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> list[NotificationResult]:
        return self.notify(message, level=NotificationLevel.WARNING, **kwargs)

    def error(self, message: str, **kwargs: Any) -> list[NotificationResult]:
        return self.notify(message, level=NotificationLevel.ERROR, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> list[NotificationResult]:
        return self.notify(message, level=NotificationLevel.CRITICAL, **kwargs)

    def get_status(self) -> dict[str, Any]:
        """Retorna um snapshot de status do notifier."""
        with self._lock:
            history_size = len(self._history)
        return {
            "channels": self.list_channels(),
            "callbacks": list(self._callbacks.keys()),
            "history_size": history_size,
            "file_path": str(self._file_path) if self._file_path else None,
            "webhook_configured": bool(self._webhook_url),
            "email_recipients": list(self._email_recipients),
        }


# =============================================================================
# Singleton
# =============================================================================

_notifier_instance: Notifier | None = None
_notifier_lock = threading.Lock()


def get_notifier() -> Notifier:
    """
    Obtém instância singleton do Notifier.

    Thread-safe. Cria nova instância com console habilitado na primeira chamada.
    """
    global _notifier_instance

    if _notifier_instance is None:
        with _notifier_lock:
            if _notifier_instance is None:
                _notifier_instance = Notifier()
                _notifier_instance.add_channel(NotificationChannel.CONSOLE)
                logger.debug(
                    "[notifier] Instância singleton criada (console habilitado)"
                )

    return _notifier_instance


def reset_notifier() -> None:
    """Reseta a instância singleton (útil para testes)."""
    global _notifier_instance

    with _notifier_lock:
        _notifier_instance = None
        logger.debug("[notifier] Instância singleton resetada")


# =============================================================================
# Função de conveniência
# =============================================================================


def notify(
    message: str,
    title: str | None = None,
    level: NotificationLevel = NotificationLevel.INFO,
    **kwargs: Any,
) -> list[NotificationResult]:
    """
    Envia uma notificação usando o notifier global.

    Exemplo:
        notify("Backup concluído!", level=NotificationLevel.SUCCESS)
        notify("Erro ao processar arquivo", level=NotificationLevel.ERROR)
    """
    return get_notifier().notify(message, title=title, level=level, **kwargs)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "NotificationLevel",
    "NotificationChannel",
    # Dataclasses
    "Notification",
    "NotificationResult",
    "ChannelConfig",
    # Classes
    "Notifier",
    # Funções
    "get_notifier",
    "reset_notifier",
    "notify",
]
