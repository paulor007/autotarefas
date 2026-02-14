"""
Sistema de Email do AutoTarefas.

Fornece envio de emails com suporte a múltiplos provedores:
    - EmailStatus: Status de envio
    - EmailPriority: Prioridade do email
    - EmailAttachment: Anexo de email
    - EmailMessage: Mensagem de email
    - EmailResult: Resultado do envio
    - EmailSender: Gerenciador de envio
    - get_email_sender(): Singleton do sender

Uso:
    from autotarefas.core.email import EmailSender, EmailMessage, get_email_sender

    sender = get_email_sender()

    message = EmailMessage(
        to=["usuario@exemplo.com"],
        subject="Relatório Diário",
        body="Segue o relatório em anexo.",
        html="<h1>Relatório</h1><p>Segue em anexo.</p>"
    )

    result = sender.send(message)
    if result.success:
        print(f"Email enviado! ID: {result.message_id}")
"""

from __future__ import annotations

import mimetypes
import re
import smtplib
import ssl
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from enum import Enum
from pathlib import Path
from typing import Any

from autotarefas.core.logger import logger

# =============================================================================
# Enums
# =============================================================================


class EmailStatus(Enum):
    """
    Status de envio de email.

    Valores:
        PENDING: Aguardando envio
        SENDING: Enviando
        SENT: Enviado com sucesso
        FAILED: Falhou no envio
        QUEUED: Na fila para envio
        CANCELLED: Cancelado
    """

    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    QUEUED = "queued"
    CANCELLED = "cancelled"


class EmailPriority(Enum):
    """
    Prioridade do email.

     Observação:
    - X-Priority costuma usar escala 1..5 (1 = mais alta prioridade).
    - Importance costuma aceitar: low/normal/high.
    """

    URGENT = 1
    HIGH = 2
    NORMAL = 3
    LOW = 5

    @property
    def x_priority(self) -> str:
        """Valor para o header X-Priority (1..5)."""
        return str(self.value)

    @property
    def importance(self) -> str:
        """Valor para o header Importance."""
        if self in (EmailPriority.URGENT, EmailPriority.HIGH):
            return "high"
        if self == EmailPriority.LOW:
            return "low"
        return "normal"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class EmailAttachment:
    """
    Anexo de email.

    Attributes:
        filename: Nome do arquivo
        content: Conteúdo em bytes
        content_type: MIME type (auto-detectado se não informado)
        content_id: ID para referência inline (opcional)
    """

    filename: str
    content: bytes
    content_type: str | None = None
    content_id: str | None = None

    def __post_init__(self):
        """Auto-detecta content_type se não informado."""
        if self.content_type is None:
            mime_type, _ = mimetypes.guess_type(self.filename)
            self.content_type = mime_type or "application/octet-stream"

    @classmethod
    def from_file(
        cls, filepath: str | Path, filename: str | None = None
    ) -> EmailAttachment:
        """
        Cria anexo a partir de arquivo.

        Args:
            filepath: Caminho do arquivo
            filename: Nome do anexo (usa nome do arquivo se não informado)

        Returns:
            EmailAttachment
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")

        content = path.read_bytes()
        return cls(filename=filename or path.name, content=content)

    @property
    def size(self) -> int:
        """Tamanho do anexo em bytes."""
        return len(self.content)

    @property
    def size_human(self) -> str:
        """Tamanho formatado para humanos."""
        size = float(self.size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


@dataclass
class EmailMessage:
    """
    Mensagem de email.

    Attributes:
        to: Lista de destinatários
        subject: Assunto
        body: Corpo em texto plano
        html: Corpo em HTML (opcional)
        cc: Lista de cópias
        bcc: Lista de cópias ocultas
        reply_to: Endereço para resposta
        attachments: Lista de anexos
        priority: Prioridade do email
        headers: Headers customizados
        tags: Tags para categorização
        metadata: Dados adicionais
    """

    to: list[str]
    subject: str
    body: str
    html: str | None = None
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: str | None = None
    attachments: list[EmailAttachment] = field(default_factory=list)
    priority: EmailPriority = EmailPriority.NORMAL
    headers: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Campos preenchidos automaticamente
    from_addr: str | None = None
    from_name: str | None = None
    message_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self):
        """Valida campos obrigatórios."""
        if not self.to:
            raise ValueError("Destinatário (to) é obrigatório")
        if not self.subject.strip():
            raise ValueError("Assunto (subject) é obrigatório")
        if (not self.body or not self.body.strip()) and (
            not self.html or not self.html.strip()
        ):
            raise ValueError("Corpo (body ou html) é obrigatório")

        # Normaliza espaços
        self.subject = self.subject.strip()
        self.body = self.body or ""

    @property
    def all_recipients(self) -> list[str]:
        """Retorna todos os destinatários (to + cc + bcc)."""
        return [*self.to, *self.cc, *self.bcc]

    @property
    def recipient_count(self) -> int:
        """Número total de destinatários."""
        return len(self.all_recipients)

    @property
    def has_attachments(self) -> bool:
        """Se tem anexos."""
        return bool(self.attachments)

    @property
    def total_attachment_size(self) -> int:
        """Tamanho total dos anexos em bytes."""
        return sum(att.size for att in self.attachments)

    def add_attachment(self, attachment: EmailAttachment) -> None:
        """Adiciona um anexo."""
        self.attachments.append(attachment)

    def add_attachment_from_file(
        self, filepath: str | Path, filename: str | None = None
    ) -> None:
        """Adiciona anexo a partir de arquivo."""
        self.attachments.append(EmailAttachment.from_file(filepath, filename))

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário."""
        return {
            "to": self.to,
            "subject": self.subject,
            "body": self.body,
            "html": self.html,
            "cc": self.cc,
            "bcc": ["***"] * len(self.bcc),  # evita vazar bcc em logs/export
            "reply_to": self.reply_to,
            "attachments": [att.filename for att in self.attachments],
            "priority": self.priority.name,
            "from_addr": self.from_addr,
            "from_name": self.from_name,
            "message_id": self.message_id,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
        }


@dataclass(slots=True)
class EmailResult:
    """
    Resultado do envio de email.

    Attributes:
        success: Se o envio foi bem sucedido
        message_id: ID da mensagem (se enviado)
        status: Status do envio
        error: Mensagem de erro (se falhou)
        error_code: Código de erro
        sent_at: Data/hora do envio
        recipients_accepted: Destinatários aceitos
        recipients_rejected: Destinatários rejeitados
        smtp_response: Resposta do servidor SMTP
        duration: Tempo de envio em segundos
    """

    success: bool
    message_id: str | None = None
    status: EmailStatus = EmailStatus.PENDING
    error: str | None = None
    error_code: str | None = None
    sent_at: datetime | None = None
    recipients_accepted: list[str] = field(default_factory=list)
    recipients_rejected: dict[str, str] = field(default_factory=dict)
    smtp_response: str | None = None
    duration: float = 0.0

    @classmethod
    def success_result(
        cls,
        message_id: str,
        recipients: list[str],
        duration: float = 0.0,
        smtp_response: str | None = None,
    ) -> EmailResult:
        """Cria resultado de sucesso."""
        return cls(
            success=True,
            message_id=message_id,
            status=EmailStatus.SENT,
            sent_at=datetime.now(UTC),
            recipients_accepted=recipients,
            duration=duration,
            smtp_response=smtp_response,
        )

    @classmethod
    def failure_result(
        cls,
        error: str,
        error_code: str | None = None,
        recipients_rejected: dict[str, str] | None = None,
    ) -> EmailResult:
        """Cria resultado de falha."""
        return cls(
            success=False,
            status=EmailStatus.FAILED,
            error=error,
            error_code=error_code,
            recipients_rejected=recipients_rejected or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário."""
        return {
            "success": self.success,
            "message_id": self.message_id,
            "status": self.status.value,
            "error": self.error,
            "error_code": self.error_code,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "recipients_accepted": self.recipients_accepted,
            "recipients_rejected": self.recipients_rejected,
            "duration": self.duration,
        }

    @property
    def is_success(self) -> bool:
        """Alias para success (compatibilidade com TaskResult)."""
        return self.success


# =============================================================================
# SMTP Config
# =============================================================================


@dataclass
class SMTPConfig:
    """
    Configuração SMTP.

    Attributes:
        host: Servidor SMTP
        port: Porta (587 para TLS, 465 para SSL, 25 para sem criptografia)
        username: Usuário para autenticação
        password: Senha para autenticação
        use_tls: Usar STARTTLS
        use_ssl: Usar SSL/TLS direto
        timeout: Timeout em segundos
        from_addr: Endereço de envio padrão
        from_name: Nome de exibição padrão
    """

    host: str = "localhost"
    port: int = 587
    username: str | None = None
    password: str | None = None
    use_tls: bool = True  # STARTTLS
    use_ssl: bool = False  # SSL direto (geralmente 465)
    timeout: int = 30
    from_addr: str | None = None
    from_name: str = "AutoTarefas"

    def __post_init__(self) -> None:
        # Normalização de flags (se SSL direto, STARTTLS não se aplica)
        if self.use_ssl and self.use_tls:
            self.use_tls = False

    @classmethod
    def from_settings(cls) -> SMTPConfig:
        """Cria configuração a partir das settings."""
        from autotarefas.config import settings

        timeout = getattr(settings, "smtp_timeout_seconds", 30)

        return cls(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_tls,
            use_ssl=settings.smtp_ssl,
            timeout=int(timeout),
            from_addr=settings.smtp_from,
            from_name=settings.smtp_from_name,
        )

    @classmethod
    def gmail(cls, username: str, password: str) -> SMTPConfig:
        """Configuração para Gmail."""
        return cls(
            host="smtp.gmail.com",
            port=587,
            username=username,
            password=password,
            use_tls=True,
            use_ssl=False,
            from_addr=username,
        )

    @classmethod
    def outlook(cls, username: str, password: str) -> SMTPConfig:
        """Configuração para Outlook/Hotmail."""
        return cls(
            host="smtp-mail.outlook.com",
            port=587,
            username=username,
            password=password,
            use_tls=True,
            use_ssl=False,
            from_addr=username,
        )

    @classmethod
    def mailgun(cls, domain: str, api_key: str) -> SMTPConfig:
        """Configuração para Mailgun."""
        return cls(
            host="smtp.mailgun.org",
            port=587,
            username=f"postmaster@{domain}",
            password=api_key,
            use_tls=True,
            use_ssl=False,
            from_addr=f"noreply@{domain}",
        )

    @property
    def is_configured(self) -> bool:
        """Verifica se está configurado minimamente."""
        return bool(self.host and self.port and self.from_addr)


# =============================================================================
# EmailSender
# =============================================================================


def _ensure_list(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else value


def _html_to_text(html: str) -> str:
    # simples e suficiente para CLI; templates (6.2) podem melhorar depois
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class EmailSender:
    """
    Gerenciador de envio de emails.

    Suporta envio via SMTP com TLS/SSL, anexos e templates HTML.

    Exemplo:
        >>> config = SMTPConfig.gmail("user@gmail.com", "app_password")
        >>> sender = EmailSender(config)
        >>>
        >>> message = EmailMessage(
        ...     to=["dest@exemplo.com"],
        ...     subject="Teste",
        ...     body="Olá!"
        ... )
        >>>
        >>> result = sender.send(message)
        >>> print(f"Enviado: {result.success}")

    Attributes:
        config: Configuração SMTP
        _connection: Conexão SMTP reutilizável
    """

    def __init__(self, config: SMTPConfig | None = None) -> None:
        """
        Inicializa o EmailSender.

        Args:
            config: Configuração SMTP (usa settings se não informado)
        """
        self.config = config or SMTPConfig.from_settings()
        self._lock = threading.Lock()

        # Não logar senha/credenciais
        logger.debug(
            f"EmailSender inicializado: host={self.config.host} port={self.config.port} ssl={self.config.use_ssl} tls={self.config.use_tls}"
        )

    @property
    def is_configured(self) -> bool:
        """Verifica se o sender está configurado."""
        return self.config.is_configured

    def _create_connection(self) -> smtplib.SMTP | smtplib.SMTP_SSL:
        """
        Cria conexão SMTP.

        Returns:
            Conexão SMTP
        """
        if self.config.use_ssl:
            context = ssl.create_default_context()
            conn = smtplib.SMTP_SSL(
                self.config.host,
                self.config.port,
                timeout=self.config.timeout,
                context=context,
            )
        else:
            conn = smtplib.SMTP(
                self.config.host,
                self.config.port,
                timeout=self.config.timeout,
            )
            conn.ehlo()
            if self.config.use_tls:
                context = ssl.create_default_context()
                conn.starttls(context=context)
                conn.ehlo()

        # Autenticação
        if self.config.username and self.config.password:
            conn.login(self.config.username, self.config.password)

        return conn

    def _build_mime_message(self, message: EmailMessage) -> MIMEMultipart:
        """
        Constrói mensagem MIME.

        Args:
            message: EmailMessage

        Returns:
            MIMEMultipart pronto para envio
        """
        # Determina tipo de mensagem
        has_html = bool(message.html)
        has_attachments = bool(message.attachments)

        if has_attachments:
            root = MIMEMultipart("mixed")
            alt = MIMEMultipart("alternative")
            root.attach(alt)
            content = alt
        elif has_html:
            root = MIMEMultipart("alternative")
            content = root
        else:
            root = MIMEMultipart()
            content = root

        from_addr = message.from_addr or self.config.from_addr
        from_name = message.from_name or self.config.from_name
        if not from_addr:
            raise ValueError("from_addr não configurado (SMTPConfig.from_addr)")

        root["From"] = formataddr((from_name, from_addr)) if from_name else from_addr
        root["To"] = ", ".join(message.to)
        root["Subject"] = message.subject
        root["Date"] = formatdate(localtime=True)

        if message.cc:
            root["Cc"] = ", ".join(message.cc)

        if message.reply_to:
            root["Reply-To"] = message.reply_to

        # Prioridade (apenas se não for NORMAL)
        if message.priority != EmailPriority.NORMAL:
            root["X-Priority"] = message.priority.x_priority
            root["Importance"] = message.priority.importance

        # Headers custom
        for k, v in message.headers.items():
            root[k] = v

        # Message-ID (garante sempre)
        if not message.message_id:
            message.message_id = make_msgid(
                domain=(from_addr.split("@")[1] if "@" in from_addr else None)
            )
        root["Message-ID"] = message.message_id

        # Texto
        if message.body.strip():
            content.attach(MIMEText(message.body, "plain", "utf-8"))

        # HTML
        if message.html and message.html.strip():
            content.attach(MIMEText(message.html, "html", "utf-8"))

        # Anexos
        for attachment in message.attachments:
            ctype = attachment.content_type or "application/octet-stream"
            if "/" not in ctype:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)

            part = MIMEBase(maintype, subtype)
            part.set_payload(attachment.content)
            encoders.encode_base64(part)

            # Inline se tiver content_id, caso contrário attachment
            disposition = "inline" if attachment.content_id else "attachment"
            part.add_header(
                "Content-Disposition", disposition, filename=attachment.filename
            )

            if attachment.content_id:
                part.add_header("Content-ID", f"<{attachment.content_id}>")

            root.attach(part)

        return root

    def send(self, message: EmailMessage) -> EmailResult:
        """
        Envia um email.

        Args:
            message: Mensagem a enviar

        Returns:
            EmailResult com status do envio
        """
        if not self.is_configured:
            return EmailResult.failure_result(
                error="EmailSender não configurado. Configure SMTP nas settings.",
                error_code="NOT_CONFIGURED",
            )

        start = time.time()

        # Preenche defaults de From se faltarem
        from_addr = message.from_addr or self.config.from_addr
        if not from_addr:
            return EmailResult.failure_result(
                error="Remetente (from_addr) não configurado. Defina EMAIL_FROM/EMAIL_USER nas settings.",
                error_code="MISSING_FROM_ADDR",
            )

        message.from_addr = from_addr  # agora é str, o type-checker fica feliz

        # Default de nome do remetente
        if not message.from_name:
            message.from_name = self.config.from_name

        # Garanta Message-ID
        if not message.message_id:
            domain = from_addr.split("@")[1] if "@" in from_addr else None
            message.message_id = make_msgid(domain=domain)

        try:
            mime_msg = self._build_mime_message(message)

            with self._lock:
                conn = self._create_connection()
                try:
                    rejected = conn.sendmail(
                        from_addr,
                        message.all_recipients,
                        mime_msg.as_string(),
                    )
                finally:
                    conn.quit()

            duration = time.time() - start

            # Alguns servidores retornam dict com rejeitados
            if rejected:
                logger.warning(f"[email] Alguns destinatários rejeitados: {rejected}")
                accepted = [r for r in message.all_recipients if r not in rejected]
                return EmailResult(
                    success=True,
                    message_id=message.message_id,
                    status=EmailStatus.SENT,
                    sent_at=datetime.now(UTC),
                    recipients_accepted=accepted,
                    recipients_rejected={str(k): str(v) for k, v in rejected.items()},
                    duration=duration,
                )

            logger.info(
                f"[email] Enviado: subject='{message.subject}' to={len(message.to)} cc={len(message.cc)} bcc={len(message.bcc)}"
            )
            return EmailResult.success_result(
                message_id=message.message_id,
                recipients=message.all_recipients,
                duration=duration,
            )

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"[email] Autenticação SMTP falhou: {e}")
            return EmailResult.failure_result(
                error="Falha na autenticação SMTP (verifique usuário/senha).",
                error_code="AUTH_FAILED",
            )

        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"[email] Destinatários recusados: {e}")
            rejected_map = {
                str(k): str(v) for k, v in getattr(e, "recipients", {}).items()
            }
            return EmailResult.failure_result(
                error="Todos os destinatários foram recusados.",
                error_code="RECIPIENTS_REFUSED",
                recipients_rejected=rejected_map,
            )

        except smtplib.SMTPException as e:
            logger.error(f"[email] Erro SMTP: {e}")
            return EmailResult.failure_result(
                error=f"Erro SMTP: {e}",
                error_code="SMTP_ERROR",
            )

        except Exception as e:
            logger.exception(f"[email] Erro inesperado ao enviar email: {e}")
            return EmailResult.failure_result(
                error=f"Erro inesperado: {e}",
                error_code="UNKNOWN_ERROR",
            )

    def send_simple(
        self, to: str | list[str], subject: str, body: str, html: str | None = None
    ) -> EmailResult:
        """
        Envia email simples.

        Args:
            to: Destinatário(s)
            subject: Assunto
            body: Corpo em texto
            html: Corpo em HTML (opcional)

        Returns:
            EmailResult
        """
        recipients = _ensure_list(to)
        msg = EmailMessage(to=recipients, subject=subject, body=body, html=html)
        return self.send(msg)

    def send_template(
        self,
        to: str | list[str],
        subject: str,
        template: str,
        context: dict[str, Any] | None = None,
        **kwargs,
    ) -> EmailResult:
        """
        Envia email usando template HTML.

        Args:
            to: Destinatário(s)
            subject: Assunto
            template: Conteúdo HTML do template
            context: Variáveis para substituição no template
            **kwargs: Argumentos adicionais para EmailMessage

        Returns:
            EmailResult
        """
        recipients = _ensure_list(to)

        html = template
        if context:
            for key, value in context.items():
                # aceita {{key}} e {{ key }}
                html = html.replace(f"{{{{{key}}}}}", str(value))
                html = html.replace(f"{{{{ {key} }}}}", str(value))

        body = _html_to_text(html)

        msg = EmailMessage(
            to=recipients,
            subject=subject,
            body=body,
            html=html,
            **kwargs,
        )
        return self.send(msg)

    def test_connection(self) -> tuple[bool, str]:
        """
        Testa conexão com servidor SMTP.

        Returns:
            Tupla (sucesso, mensagem)
        """
        if not self.is_configured:
            return False, "EmailSender não configurado."

        try:
            conn = self._create_connection()
            try:
                conn.noop()
            finally:
                conn.quit()

            logger.info(
                f"[email] Conexão SMTP OK: {self.config.host}:{self.config.port}"
            )
            return True, f"Conexão OK com {self.config.host}:{self.config.port}"

        except smtplib.SMTPAuthenticationError:
            return False, "Falha na autenticação (verifique usuário/senha)."

        except smtplib.SMTPConnectError:
            return (
                False,
                f"Não foi possível conectar em {self.config.host}:{self.config.port}",
            )

        except Exception as e:
            return False, f"Erro: {e}"

    def get_status(self) -> dict[str, Any]:
        """
        Retorna status do sender.

        Returns:
            Dicionário com informações de status
        """
        return {
            "configured": self.is_configured,
            "host": self.config.host,
            "port": self.config.port,
            "from_addr": self.config.from_addr,
            "from_name": self.config.from_name,
            "use_tls": self.config.use_tls,
            "use_ssl": self.config.use_ssl,
            "has_auth": bool(self.config.username),
            "timeout": self.config.timeout,
        }


# =============================================================================
# Singleton
# =============================================================================

_email_sender_instance: EmailSender | None = None
_email_sender_lock = threading.Lock()


def get_email_sender(config: SMTPConfig | None = None) -> EmailSender:
    """
    Obtém instância singleton do EmailSender.

    Thread-safe. Cria nova instância na primeira chamada.

    Args:
        config: Configuração SMTP (opcional, usa settings se não informado)

    Returns:
        Instância global do EmailSender
    """
    global _email_sender_instance

    if _email_sender_instance is None:
        with _email_sender_lock:
            if _email_sender_instance is None:
                _email_sender_instance = EmailSender(config)
                logger.debug("[email] Instância singleton do EmailSender criada")

    return _email_sender_instance


def reset_email_sender() -> None:
    """
    Reseta a instância singleton (útil para testes).
    """
    global _email_sender_instance

    with _email_sender_lock:
        _email_sender_instance = None
        logger.debug("[email] Instância singleton do EmailSender resetada")


# =============================================================================
# Função de conveniência
# =============================================================================


def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    html: str | None = None,
    attachments: list[str | Path] | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    priority: EmailPriority = EmailPriority.NORMAL,
) -> EmailResult:
    """
    Envia email usando o sender global.

    Função de conveniência para envio rápido.

    Args:
        to: Destinatário(s)
        subject: Assunto
        body: Corpo em texto
        html: Corpo em HTML (opcional)
        attachments: Lista de caminhos de arquivos para anexar
        cc: Cópias
        bcc: Cópias ocultas
        priority: Prioridade

    Returns:
        EmailResult

    Exemplo:
        >>> result = send_email(
        ...     to="usuario@exemplo.com",
        ...     subject="Relatório",
        ...     body="Segue relatório em anexo",
        ...     attachments=["/path/to/report.pdf"]
        ... )
    """
    recipients = _ensure_list(to)

    email_attachments: list[EmailAttachment] = []
    if attachments:
        for filepath in attachments:
            try:
                email_attachments.append(EmailAttachment.from_file(filepath))
            except FileNotFoundError:
                logger.warning(f"[email] Anexo não encontrado: {filepath}")

    msg = EmailMessage(
        to=recipients,
        subject=subject,
        body=body,
        html=html,
        cc=cc or [],
        bcc=bcc or [],
        attachments=email_attachments,
        priority=priority,
    )

    return get_email_sender().send(msg)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Enums
    "EmailStatus",
    "EmailPriority",
    # Dataclasses
    "EmailAttachment",
    "EmailMessage",
    "EmailResult",
    "SMTPConfig",
    # Classes
    "EmailSender",
    # Funções
    "get_email_sender",
    "reset_email_sender",
    "send_email",
]
