"""
Testes do módulo de email.

Testa:
    - EmailStatus: Status de envio
    - EmailPriority: Prioridade com X-Priority e Importance
    - EmailAttachment: Anexos (content_type, from_file, size)
    - EmailMessage: Mensagem (validação, recipients, to_dict)
    - EmailResult: Resultado (success_result, failure_result, to_dict)
    - SMTPConfig: Configuração (presets Gmail/Outlook, is_configured)
    - EmailSender: Envio (send, send_simple, send_template, test_connection)
    - Singleton: get_email_sender, reset_email_sender
"""

from __future__ import annotations

import smtplib
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# Testes de EmailStatus
# ============================================================================


class TestEmailStatus:
    """Testes do enum EmailStatus."""

    def test_status_values(self) -> None:
        """Deve ter todos os status esperados."""
        from autotarefas.core.email import EmailStatus

        assert EmailStatus.PENDING.value == "pending"
        assert EmailStatus.SENDING.value == "sending"
        assert EmailStatus.SENT.value == "sent"
        assert EmailStatus.FAILED.value == "failed"
        assert EmailStatus.QUEUED.value == "queued"
        assert EmailStatus.CANCELLED.value == "cancelled"

    def test_status_from_value(self) -> None:
        """Deve converter string para enum."""
        from autotarefas.core.email import EmailStatus

        assert EmailStatus("sent") == EmailStatus.SENT
        assert EmailStatus("failed") == EmailStatus.FAILED


# ============================================================================
# Testes de EmailPriority
# ============================================================================


class TestEmailPriority:
    """Testes do enum EmailPriority."""

    def test_priority_values(self) -> None:
        """Deve ter prioridades corretas."""
        from autotarefas.core.email import EmailPriority

        assert EmailPriority.URGENT.value == 1
        assert EmailPriority.HIGH.value == 2
        assert EmailPriority.NORMAL.value == 3
        assert EmailPriority.LOW.value == 5

    def test_x_priority_header(self) -> None:
        """x_priority deve retornar valor para X-Priority header."""
        from autotarefas.core.email import EmailPriority

        assert EmailPriority.URGENT.x_priority == "1"
        assert EmailPriority.NORMAL.x_priority == "3"
        assert EmailPriority.LOW.x_priority == "5"

    def test_importance_header(self) -> None:
        """importance deve retornar valor para Importance header."""
        from autotarefas.core.email import EmailPriority

        assert EmailPriority.URGENT.importance == "high"
        assert EmailPriority.HIGH.importance == "high"
        assert EmailPriority.NORMAL.importance == "normal"
        assert EmailPriority.LOW.importance == "low"


# ============================================================================
# Testes de EmailAttachment
# ============================================================================


class TestEmailAttachment:
    """Testes da dataclass EmailAttachment."""

    def test_attachment_creation(self) -> None:
        """Deve criar anexo corretamente."""
        from autotarefas.core.email import EmailAttachment

        att = EmailAttachment(
            filename="test.pdf",
            content=b"PDF content here",
        )

        assert att.filename == "test.pdf"
        assert att.content == b"PDF content here"

    def test_auto_detect_content_type_pdf(self) -> None:
        """Deve detectar content_type para PDF."""
        from autotarefas.core.email import EmailAttachment

        att = EmailAttachment(filename="doc.pdf", content=b"data")
        assert att.content_type == "application/pdf"

    def test_auto_detect_content_type_txt(self) -> None:
        """Deve detectar content_type para TXT."""
        from autotarefas.core.email import EmailAttachment

        att = EmailAttachment(filename="file.txt", content=b"data")
        assert att.content_type is not None
        assert "text" in att.content_type.lower()

    def test_auto_detect_content_type_unknown(self) -> None:
        """Deve usar octet-stream para tipo desconhecido."""
        from autotarefas.core.email import EmailAttachment

        att = EmailAttachment(filename="file.xyz123", content=b"data")
        assert att.content_type == "application/octet-stream"

    def test_explicit_content_type(self) -> None:
        """Deve aceitar content_type explícito."""
        from autotarefas.core.email import EmailAttachment

        att = EmailAttachment(
            filename="data.bin",
            content=b"\x00\x01",
            content_type="application/custom",
        )

        assert att.content_type == "application/custom"

    def test_size_property(self) -> None:
        """size deve retornar tamanho correto."""
        from autotarefas.core.email import EmailAttachment

        att = EmailAttachment(filename="test.bin", content=b"12345")
        assert att.size == 5

    def test_size_human_bytes(self) -> None:
        """size_human deve formatar bytes."""
        from autotarefas.core.email import EmailAttachment

        att = EmailAttachment(filename="test.bin", content=b"x" * 500)
        assert "500" in att.size_human and "B" in att.size_human

    def test_size_human_kb(self) -> None:
        """size_human deve formatar KB."""
        from autotarefas.core.email import EmailAttachment

        att = EmailAttachment(filename="test.bin", content=b"x" * 2048)
        assert "KB" in att.size_human

    def test_from_file(self, temp_dir: Path) -> None:
        """from_file deve criar anexo a partir de arquivo."""
        from autotarefas.core.email import EmailAttachment

        filepath = temp_dir / "test_file.txt"
        filepath.write_text("Hello attachment!")

        att = EmailAttachment.from_file(filepath)

        assert att.filename == "test_file.txt"
        assert att.content == b"Hello attachment!"

    def test_from_file_custom_name(self, temp_dir: Path) -> None:
        """from_file deve aceitar nome customizado."""
        from autotarefas.core.email import EmailAttachment

        filepath = temp_dir / "original.txt"
        filepath.write_text("content")

        att = EmailAttachment.from_file(filepath, filename="custom_name.txt")
        assert att.filename == "custom_name.txt"

    def test_from_file_not_found(self) -> None:
        """from_file deve falhar com arquivo inexistente."""
        from autotarefas.core.email import EmailAttachment

        with pytest.raises(FileNotFoundError):
            EmailAttachment.from_file("/nonexistent/file.txt")

    def test_content_id_for_inline(self) -> None:
        """Deve aceitar content_id para imagens inline."""
        from autotarefas.core.email import EmailAttachment

        att = EmailAttachment(
            filename="logo.png",
            content=b"PNG data",
            content_id="logo123",
        )

        assert att.content_id == "logo123"


# ============================================================================
# Testes de EmailMessage
# ============================================================================


class TestEmailMessage:
    """Testes da dataclass EmailMessage."""

    def test_message_creation(self) -> None:
        """Deve criar mensagem corretamente."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(
            to=["user@example.com"],
            subject="Test Subject",
            body="Hello World!",
        )

        assert msg.to == ["user@example.com"]
        assert msg.subject == "Test Subject"
        assert msg.body == "Hello World!"

    def test_message_with_all_fields(self) -> None:
        """Deve aceitar todos os campos."""
        from autotarefas.core.email import EmailMessage, EmailPriority

        msg = EmailMessage(
            to=["user@example.com"],
            subject="Full Message",
            body="Plain text",
            html="<h1>HTML</h1>",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            reply_to="reply@example.com",
            priority=EmailPriority.HIGH,
            headers={"X-Custom": "value"},
            tags=["test"],
        )

        assert msg.cc == ["cc@example.com"]
        assert msg.bcc == ["bcc@example.com"]
        assert msg.reply_to == "reply@example.com"
        assert msg.priority == EmailPriority.HIGH
        assert msg.headers == {"X-Custom": "value"}

    def test_message_validation_no_to(self) -> None:
        """Deve falhar sem destinatário."""
        from autotarefas.core.email import EmailMessage

        with pytest.raises(ValueError, match="[Dd]estinatário|to"):
            EmailMessage(to=[], subject="Test", body="Content")

    def test_message_validation_no_subject(self) -> None:
        """Deve falhar sem assunto."""
        from autotarefas.core.email import EmailMessage

        with pytest.raises(ValueError, match="[Aa]ssunto|subject"):
            EmailMessage(to=["user@test.com"], subject="   ", body="Content")

    def test_message_validation_no_body(self) -> None:
        """Deve falhar sem corpo."""
        from autotarefas.core.email import EmailMessage

        with pytest.raises(ValueError, match="[Cc]orpo|body|html"):
            EmailMessage(to=["user@test.com"], subject="Test", body="", html="")

    def test_message_html_only_valid(self) -> None:
        """Deve aceitar apenas HTML como corpo."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(
            to=["user@test.com"],
            subject="HTML Only",
            body="",
            html="<p>Content</p>",
        )

        assert msg.html == "<p>Content</p>"

    def test_all_recipients(self) -> None:
        """all_recipients deve incluir to + cc + bcc."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(
            to=["a@test.com"],
            subject="Test",
            body="Content",
            cc=["b@test.com"],
            bcc=["c@test.com"],
        )

        all_rcpt = msg.all_recipients
        assert len(all_rcpt) == 3
        assert "a@test.com" in all_rcpt
        assert "b@test.com" in all_rcpt
        assert "c@test.com" in all_rcpt

    def test_recipient_count(self) -> None:
        """recipient_count deve contar todos."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(
            to=["a@t.com", "b@t.com"],
            subject="Test",
            body="Hi",
            cc=["c@t.com"],
        )

        assert msg.recipient_count == 3

    def test_has_attachments_false(self) -> None:
        """has_attachments deve ser False sem anexos."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(to=["x@t.com"], subject="T", body="B")
        assert msg.has_attachments is False

    def test_has_attachments_true(self) -> None:
        """has_attachments deve ser True com anexos."""
        from autotarefas.core.email import EmailAttachment, EmailMessage

        att = EmailAttachment(filename="f.txt", content=b"data")
        msg = EmailMessage(to=["x@t.com"], subject="T", body="B", attachments=[att])
        assert msg.has_attachments is True

    def test_add_attachment(self) -> None:
        """add_attachment deve adicionar anexo."""
        from autotarefas.core.email import EmailAttachment, EmailMessage

        msg = EmailMessage(to=["x@t.com"], subject="T", body="B")
        msg.add_attachment(EmailAttachment(filename="f.txt", content=b"data"))

        assert len(msg.attachments) == 1

    def test_total_attachment_size(self) -> None:
        """total_attachment_size deve somar tamanhos."""
        from autotarefas.core.email import EmailAttachment, EmailMessage

        msg = EmailMessage(to=["x@t.com"], subject="T", body="B")
        msg.add_attachment(EmailAttachment(filename="a.txt", content=b"12345"))
        msg.add_attachment(EmailAttachment(filename="b.txt", content=b"67890"))

        assert msg.total_attachment_size == 10

    def test_to_dict(self) -> None:
        """to_dict deve retornar dicionário completo."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(
            to=["user@test.com"],
            subject="Test",
            body="Content",
            tags=["important"],
        )

        data = msg.to_dict()

        assert isinstance(data, dict)
        assert data["to"] == ["user@test.com"]
        assert data["subject"] == "Test"
        assert data["tags"] == ["important"]

    def test_to_dict_masks_bcc(self) -> None:
        """to_dict deve mascarar BCC."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(
            to=["user@test.com"],
            subject="Test",
            body="Content",
            bcc=["secret@test.com", "another@test.com"],
        )

        data = msg.to_dict()
        assert "secret@test.com" not in str(data["bcc"])
        assert len(data["bcc"]) == 2


# ============================================================================
# Testes de EmailResult
# ============================================================================


class TestEmailResult:
    """Testes da dataclass EmailResult."""

    def test_result_creation(self) -> None:
        """Deve criar resultado corretamente."""
        from autotarefas.core.email import EmailResult, EmailStatus

        result = EmailResult(success=True, status=EmailStatus.SENT)

        assert result.is_success is True
        assert result.status == EmailStatus.SENT

    def test_success_result_factory(self) -> None:
        """success_result deve criar resultado de sucesso."""
        from autotarefas.core.email import EmailResult, EmailStatus

        result = EmailResult.success_result(
            message_id="<msg123@test.com>",
            recipients=["user@test.com"],
            duration=1.5,
        )

        assert result.is_success is True
        assert result.status == EmailStatus.SENT
        assert result.message_id == "<msg123@test.com>"
        assert result.duration == 1.5
        assert result.sent_at is not None

    def test_failure_result_factory(self) -> None:
        """failure_result deve criar resultado de falha."""
        from autotarefas.core.email import EmailResult, EmailStatus

        result = EmailResult.failure_result(
            error="Connection refused",
            error_code="SMTP_ERROR",
        )

        assert result.is_success is False
        assert result.status == EmailStatus.FAILED
        assert result.error == "Connection refused"
        assert result.error_code == "SMTP_ERROR"

    def test_failure_result_with_rejected(self) -> None:
        """failure_result deve aceitar recipients_rejected."""
        from autotarefas.core.email import EmailResult

        result = EmailResult.failure_result(
            error="Some rejected",
            recipients_rejected={"bad@test.com": "550 User not found"},
        )

        assert "bad@test.com" in result.recipients_rejected

    def test_to_dict(self) -> None:
        """to_dict deve retornar dicionário."""
        from autotarefas.core.email import EmailResult

        result = EmailResult.success_result(
            message_id="<msg@test.com>",
            recipients=["user@test.com"],
        )

        data = result.to_dict()

        assert isinstance(data, dict)
        assert data["success"] is True
        assert data["status"] == "sent"
        assert data["message_id"] == "<msg@test.com>"


# ============================================================================
# Testes de SMTPConfig
# ============================================================================


class TestSMTPConfig:
    """Testes da dataclass SMTPConfig."""

    def test_default_config(self) -> None:
        """Deve ter defaults razoáveis."""
        from autotarefas.core.email import SMTPConfig

        config = SMTPConfig()

        assert config.host == "localhost"
        assert config.port == 587
        assert config.use_tls is True
        assert config.use_ssl is False

    def test_gmail_preset(self) -> None:
        """Preset Gmail deve ter valores corretos."""
        from autotarefas.core.email import SMTPConfig

        config = SMTPConfig.gmail("user@gmail.com", "app_password")

        assert config.host == "smtp.gmail.com"
        assert config.port == 587
        assert config.username == "user@gmail.com"
        assert config.password == "app_password"
        assert config.use_tls is True
        assert config.from_addr == "user@gmail.com"

    def test_outlook_preset(self) -> None:
        """Preset Outlook deve ter valores corretos."""
        from autotarefas.core.email import SMTPConfig

        config = SMTPConfig.outlook("user@outlook.com", "password")

        assert "outlook" in config.host.lower()
        assert config.port == 587
        assert config.use_tls is True

    def test_mailgun_preset(self) -> None:
        """Preset Mailgun deve ter valores corretos."""
        from autotarefas.core.email import SMTPConfig

        config = SMTPConfig.mailgun("example.com", "api_key_123")

        assert config.host == "smtp.mailgun.org"
        assert config.username is not None
        assert "postmaster@example.com" in config.username
        assert config.password == "api_key_123"

    def test_is_configured_false(self) -> None:
        """is_configured deve ser False sem host/from."""
        from autotarefas.core.email import SMTPConfig

        config = SMTPConfig(host="", port=0, from_addr="")
        assert config.is_configured is False

    def test_is_configured_true(self) -> None:
        """is_configured deve ser True com configuração mínima."""
        from autotarefas.core.email import SMTPConfig

        config = SMTPConfig(
            host="smtp.test.com",
            port=587,
            from_addr="test@test.com",
        )
        assert config.is_configured is True

    def test_ssl_disables_tls(self) -> None:
        """Se SSL é True, TLS deve ser desabilitado."""
        from autotarefas.core.email import SMTPConfig

        config = SMTPConfig(
            host="smtp.test.com",
            port=465,
            use_ssl=True,
            use_tls=True,  # Será desabilitado
        )

        assert config.use_ssl is True
        assert config.use_tls is False


# ============================================================================
# Testes de EmailSender
# ============================================================================


class TestEmailSender:
    """Testes da classe EmailSender."""

    def test_sender_creation(self) -> None:
        """Deve criar sender."""
        from autotarefas.core.email import EmailSender, SMTPConfig

        config = SMTPConfig(host="smtp.test.com", port=587, from_addr="test@test.com")
        sender = EmailSender(config)

        assert sender is not None
        assert sender.is_configured is True

    def test_sender_not_configured(self) -> None:
        """Deve reportar quando não configurado."""
        from autotarefas.core.email import EmailMessage, EmailSender, SMTPConfig

        config = SMTPConfig(host="", port=0, from_addr="")
        sender = EmailSender(config)

        assert sender.is_configured is False

        msg = EmailMessage(to=["user@test.com"], subject="Test", body="Hi")
        result = sender.send(msg)

        assert result.is_success is False
        assert result.error_code == "NOT_CONFIGURED"


class TestEmailSenderSend:
    """Testes de envio do EmailSender."""

    @pytest.fixture
    def mock_sender(self) -> Any:
        """Cria sender com SMTP mockado."""
        from autotarefas.core.email import EmailSender, SMTPConfig

        config = SMTPConfig(
            host="smtp.test.com",
            port=587,
            username="user@test.com",
            password="password",
            from_addr="sender@test.com",
        )
        return EmailSender(config)

    def test_send_success(self, mock_sender: Any) -> None:
        """Deve enviar com sucesso."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(to=["dest@test.com"], subject="Test Email", body="Hello!")

        with patch.object(mock_sender, "_create_connection") as mock_conn:
            smtp_mock = MagicMock()
            smtp_mock.sendmail.return_value = {}
            mock_conn.return_value = smtp_mock

            result = mock_sender.send(msg)

        assert result.is_success is True
        smtp_mock.sendmail.assert_called_once()
        smtp_mock.quit.assert_called_once()

    def test_send_with_html(self, mock_sender: Any) -> None:
        """Deve enviar com HTML."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(
            to=["dest@test.com"],
            subject="HTML Email",
            body="Plain text fallback",
            html="<h1>Hello!</h1>",
        )

        with patch.object(mock_sender, "_create_connection") as mock_conn:
            smtp_mock = MagicMock()
            smtp_mock.sendmail.return_value = {}
            mock_conn.return_value = smtp_mock

            result = mock_sender.send(msg)

        assert result.is_success is True

    def test_send_auth_failure(self, mock_sender: Any) -> None:
        """Deve tratar falha de autenticação."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(to=["dest@test.com"], subject="Test", body="Hi")

        with patch.object(mock_sender, "_create_connection") as mock_conn:
            mock_conn.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")

            result = mock_sender.send(msg)

        assert result.is_success is False
        assert result.error_code == "AUTH_FAILED"

    def test_send_smtp_error(self, mock_sender: Any) -> None:
        """Deve tratar erro SMTP genérico."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(to=["dest@test.com"], subject="Test", body="Hi")

        with patch.object(mock_sender, "_create_connection") as mock_conn:
            mock_conn.side_effect = smtplib.SMTPException("Connection failed")

            result = mock_sender.send(msg)

        assert result.is_success is False
        assert result.error_code == "SMTP_ERROR"

    def test_send_recipients_refused(self, mock_sender: Any) -> None:
        """Deve tratar destinatários recusados."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(to=["bad@test.com"], subject="Test", body="Hi")

        with patch.object(mock_sender, "_create_connection") as mock_conn:
            error = smtplib.SMTPRecipientsRefused(
                {"bad@test.com": (550, b"User not found")}
            )
            mock_conn.side_effect = error

            result = mock_sender.send(msg)

        assert result.is_success is False
        assert result.error_code == "RECIPIENTS_REFUSED"

    def test_send_simple(self, mock_sender: Any) -> None:
        """send_simple deve funcionar como atalho."""
        with patch.object(mock_sender, "_create_connection") as mock_conn:
            smtp_mock = MagicMock()
            smtp_mock.sendmail.return_value = {}
            mock_conn.return_value = smtp_mock

            result = mock_sender.send_simple(
                to="dest@test.com",
                subject="Simple Test",
                body="Hello!",
            )

        assert result.is_success is True

    def test_send_template(self, mock_sender: Any) -> None:
        """send_template deve substituir variáveis."""
        with patch.object(mock_sender, "_create_connection") as mock_conn:
            smtp_mock = MagicMock()
            smtp_mock.sendmail.return_value = {}
            mock_conn.return_value = smtp_mock

            result = mock_sender.send_template(
                to="dest@test.com",
                subject="Template Test",
                template="<h1>Hello {{name}}!</h1>",
                context={"name": "World"},
            )

        assert result.is_success is True


class TestEmailSenderConnection:
    """Testes de conexão do EmailSender."""

    def test_test_connection_not_configured(self) -> None:
        """test_connection deve falhar se não configurado."""
        from autotarefas.core.email import EmailSender, SMTPConfig

        config = SMTPConfig(host="", port=0, from_addr="")
        sender = EmailSender(config)

        success, message = sender.test_connection()
        assert success is False

    def test_test_connection_success(self) -> None:
        """test_connection deve retornar sucesso com SMTP mockado."""
        from autotarefas.core.email import EmailSender, SMTPConfig

        config = SMTPConfig(host="smtp.test.com", port=587, from_addr="test@test.com")
        sender = EmailSender(config)

        with patch.object(sender, "_create_connection") as mock_conn:
            smtp_mock = MagicMock()
            smtp_mock.noop.return_value = (250, b"OK")
            mock_conn.return_value = smtp_mock

            success, message = sender.test_connection()

        assert success is True


# ============================================================================
# Testes de Edge Cases
# ============================================================================


class TestEmailEdgeCases:
    """Testes de casos extremos."""

    def test_large_attachment(self) -> None:
        """Deve tratar anexo grande."""
        from autotarefas.core.email import EmailAttachment

        large_content = b"x" * (5 * 1024 * 1024)  # 5 MB
        att = EmailAttachment(filename="large.bin", content=large_content)

        assert att.size == 5 * 1024 * 1024
        assert "MB" in att.size_human

    def test_unicode_subject_and_body(self) -> None:
        """Deve tratar unicode."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(
            to=["user@test.com"],
            subject="Relatório de ação — 日本語",
            body="Conteúdo com acentuação: ção, ñ, ü, ß",
        )

        assert "ação" in msg.subject
        assert "ção" in msg.body

    def test_multiple_recipients(self) -> None:
        """Deve aceitar múltiplos destinatários."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(
            to=["a@t.com", "b@t.com", "c@t.com"],
            subject="Multi",
            body="Content",
            cc=["d@t.com"],
            bcc=["e@t.com"],
        )

        assert msg.recipient_count == 5

    def test_empty_attachment_content(self) -> None:
        """Deve aceitar anexo vazio."""
        from autotarefas.core.email import EmailAttachment

        att = EmailAttachment(filename="empty.txt", content=b"")
        assert att.size == 0

    def test_subject_strips_whitespace(self) -> None:
        """Subject deve ter whitespace removido."""
        from autotarefas.core.email import EmailMessage

        msg = EmailMessage(
            to=["user@test.com"],
            subject="  Spaced Subject  ",
            body="Content",
        )

        assert msg.subject == "Spaced Subject"
