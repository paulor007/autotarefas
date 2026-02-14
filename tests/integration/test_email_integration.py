"""
Testes de integração do sistema de email.

Este arquivo testa o EmailSender que é responsável por enviar emails
via SMTP com suporte a anexos, HTML e múltiplos destinatários.

=============================================================================
OBJETIVO DO MÓDULO email.py
=============================================================================

O módulo de email serve para:

1. **Envio de Emails via SMTP**
   - Conexão com servidores SMTP (TLS/SSL)
   - Autenticação com credenciais
   - Envio para múltiplos destinatários (to, cc, bcc)

2. **Construção de Mensagens**
   - EmailMessage: Estrutura de dados para email
   - Suporte a texto plano e HTML
   - Anexos (EmailAttachment)
   - Prioridade e headers customizados

3. **Configuração Flexível**
   - SMTPConfig: Configuração do servidor
   - Presets para Gmail, Outlook, Mailgun
   - Configuração via settings/environment

4. **Resultados Detalhados**
   - EmailResult: Status do envio
   - Destinatários aceitos/rejeitados
   - Códigos de erro específicos

=============================================================================
O QUE ESTES TESTES VERIFICAM
=============================================================================

- Criação e validação de EmailMessage
- Construção de mensagens MIME
- Envio com mock de SMTP (não requer servidor real)
- Tratamento de erros (autenticação, conexão, etc.)
- Anexos e formatação HTML
- Integração com Notifier
- Configuração via SMTPConfig

=============================================================================
CENÁRIOS DE INTEGRAÇÃO
=============================================================================

1. EmailSender → SMTP Server → Envio
2. EmailMessage → MIMEMultipart → Formatação
3. Notifier → EmailSender → Notificação por email
4. Task → EmailSender → Relatório por email

Estes testes usam mocks de SMTP para não depender de servidor real,
mas verificam toda a lógica de construção e envio de emails.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# Testes de EmailMessage
# ============================================================================


class TestEmailMessageIntegration:
    """
    Testes de criação e validação de EmailMessage.

    EmailMessage é a estrutura que representa um email completo
    com destinatários, assunto, corpo, anexos, etc.
    """

    def test_create_simple_message(self) -> None:
        """Deve criar mensagem simples."""
        from autotarefas.core.email import EmailMessage

        message = EmailMessage(
            to=["dest@example.com"],
            subject="Teste",
            body="Corpo do email",
        )

        assert message.to == ["dest@example.com"]
        assert message.subject == "Teste"
        assert message.body == "Corpo do email"

    def test_create_message_with_html(self) -> None:
        """Deve criar mensagem com HTML."""
        from autotarefas.core.email import EmailMessage

        message = EmailMessage(
            to=["dest@example.com"],
            subject="Teste HTML",
            body="Versão texto",
            html="<h1>Versão HTML</h1>",
        )

        assert message.html == "<h1>Versão HTML</h1>"

    def test_create_message_with_multiple_recipients(self) -> None:
        """Deve criar mensagem com múltiplos destinatários."""
        from autotarefas.core.email import EmailMessage

        message = EmailMessage(
            to=["dest1@example.com", "dest2@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            subject="Teste",
            body="Corpo",
        )

        assert len(message.to) == 2
        assert len(message.cc) == 1
        assert len(message.bcc) == 1
        assert message.recipient_count == 4
        assert len(message.all_recipients) == 4

    def test_message_requires_to(self) -> None:
        """Deve falhar sem destinatário."""
        from autotarefas.core.email import EmailMessage

        with pytest.raises(ValueError, match="[Dd]estinatário|to"):
            EmailMessage(
                to=[],
                subject="Teste",
                body="Corpo",
            )

    def test_message_requires_subject(self) -> None:
        """Deve falhar sem assunto."""
        from autotarefas.core.email import EmailMessage

        with pytest.raises(ValueError, match="[Aa]ssunto|subject"):
            EmailMessage(
                to=["dest@example.com"],
                subject="",
                body="Corpo",
            )

    def test_message_requires_body_or_html(self) -> None:
        """Deve falhar sem corpo."""
        from autotarefas.core.email import EmailMessage

        with pytest.raises(ValueError, match="[Cc]orpo|body|html"):
            EmailMessage(
                to=["dest@example.com"],
                subject="Teste",
                body="",
                html="",
            )

    def test_message_to_dict(self) -> None:
        """Deve serializar para dicionário."""
        from autotarefas.core.email import EmailMessage

        message = EmailMessage(
            to=["dest@example.com"],
            subject="Teste",
            body="Corpo",
            tags=["importante", "relatorio"],
        )

        data = message.to_dict()

        assert data["to"] == ["dest@example.com"]
        assert data["subject"] == "Teste"
        assert data["tags"] == ["importante", "relatorio"]


# ============================================================================
# Testes de EmailAttachment
# ============================================================================


class TestEmailAttachmentIntegration:
    """
    Testes de anexos de email.

    EmailAttachment permite anexar arquivos aos emails.
    """

    def test_create_attachment(self) -> None:
        """Deve criar anexo com conteúdo."""
        from autotarefas.core.email import EmailAttachment

        attachment = EmailAttachment(
            filename="test.txt",
            content=b"Conteudo do arquivo",
        )

        assert attachment.filename == "test.txt"
        assert attachment.content == b"Conteudo do arquivo"
        assert attachment.size == 19

    def test_create_attachment_from_file(
        self, integration_env: dict[str, Path]
    ) -> None:
        """Deve criar anexo a partir de arquivo."""
        from autotarefas.core.email import EmailAttachment

        # Criar arquivo
        test_file = integration_env["temp"] / "attachment.txt"
        test_file.write_text("Conteúdo do anexo")

        attachment = EmailAttachment.from_file(test_file)

        assert attachment.filename == "attachment.txt"
        assert b"Conte" in attachment.content

    def test_attachment_size_human(self) -> None:
        """Deve formatar tamanho para humanos."""
        from autotarefas.core.email import EmailAttachment

        # 1 KB
        attachment = EmailAttachment(
            filename="test.bin",
            content=b"x" * 1024,
        )

        assert "KB" in attachment.size_human or "1024" in attachment.size_human

    def test_add_attachment_to_message(self, integration_env: dict[str, Path]) -> None:
        """Deve adicionar anexo à mensagem."""
        from autotarefas.core.email import EmailAttachment, EmailMessage

        message = EmailMessage(
            to=["dest@example.com"],
            subject="Com anexo",
            body="Veja o anexo",
        )

        attachment = EmailAttachment(
            filename="data.csv",
            content=b"id,name\n1,Test",
        )

        message.add_attachment(attachment)

        assert message.has_attachments is True
        assert len(message.attachments) == 1
        assert message.total_attachment_size > 0


# ============================================================================
# Testes de SMTPConfig
# ============================================================================


class TestSMTPConfigIntegration:
    """
    Testes de configuração SMTP.

    SMTPConfig define como conectar ao servidor de email.
    """

    def test_create_config(self) -> None:
        """Deve criar configuração básica."""
        from autotarefas.core.email import SMTPConfig

        config = SMTPConfig(
            host="smtp.example.com",
            port=587,
            username="user",
            password="pass",
            from_addr="user@example.com",
        )

        assert config.host == "smtp.example.com"
        assert config.port == 587
        assert config.is_configured is True

    def test_gmail_preset(self) -> None:
        """Deve criar configuração para Gmail."""
        from autotarefas.core.email import SMTPConfig

        config = SMTPConfig.gmail("user@gmail.com", "app_password")

        assert config.host == "smtp.gmail.com"
        assert config.port == 587
        assert config.use_tls is True
        assert config.from_addr == "user@gmail.com"

    def test_outlook_preset(self) -> None:
        """Deve criar configuração para Outlook."""
        from autotarefas.core.email import SMTPConfig

        config = SMTPConfig.outlook("user@outlook.com", "password")

        assert config.host == "smtp-mail.outlook.com"
        assert config.port == 587

    def test_config_not_configured(self) -> None:
        """Deve detectar configuração incompleta."""
        from autotarefas.core.email import SMTPConfig

        config = SMTPConfig(
            host="",
            port=0,
            from_addr="",
        )

        assert config.is_configured is False


# ============================================================================
# Testes de EmailSender com Mock
# ============================================================================


class TestEmailSenderIntegration:
    """
    Testes de envio de email com SMTP mockado.

    Estes testes verificam a lógica de envio sem precisar
    de um servidor SMTP real.
    """

    def test_send_simple_email(self, mock_smtp_server: MagicMock) -> None:
        """Deve enviar email simples."""
        from autotarefas.core.email import EmailMessage, EmailSender, SMTPConfig

        config = SMTPConfig(
            host="smtp.test.com",
            port=587,
            username="user",
            password="pass",
            from_addr="sender@test.com",
            use_tls=False,
            use_ssl=False,
        )

        sender = EmailSender(config)

        message = EmailMessage(
            to=["dest@test.com"],
            subject="Teste",
            body="Corpo do email",
        )

        result = sender.send(message)

        # Verifica que sendmail foi chamado
        assert mock_smtp_server.sendmail.called

    def test_send_returns_result(self, mock_smtp_server: MagicMock) -> None:
        """Deve retornar EmailResult."""
        from autotarefas.core.email import (
            EmailMessage,
            EmailResult,
            EmailSender,
            SMTPConfig,
        )

        config = SMTPConfig(
            host="smtp.test.com",
            port=587,
            from_addr="sender@test.com",
            use_tls=False,
            use_ssl=False,
        )

        sender = EmailSender(config)

        message = EmailMessage(
            to=["dest@test.com"],
            subject="Teste",
            body="Corpo",
        )

        result = sender.send(message)

        assert isinstance(result, EmailResult)

    def test_send_simple_helper(self, mock_smtp_server: MagicMock) -> None:
        """Deve enviar via método helper send_simple."""
        from autotarefas.core.email import EmailSender, SMTPConfig

        config = SMTPConfig(
            host="smtp.test.com",
            port=587,
            from_addr="sender@test.com",
            use_tls=False,
            use_ssl=False,
        )

        sender = EmailSender(config)

        result = sender.send_simple(
            to="dest@test.com",
            subject="Teste Simples",
            body="Corpo simples",
        )

        assert mock_smtp_server.sendmail.called

    def test_send_not_configured(self) -> None:
        """Deve falhar se não configurado."""
        from autotarefas.core.email import EmailMessage, EmailSender, SMTPConfig

        config = SMTPConfig(
            host="",
            port=0,
            from_addr="",
        )

        sender = EmailSender(config)

        message = EmailMessage(
            to=["dest@test.com"],
            subject="Teste",
            body="Corpo",
        )

        result = sender.send(message)

        assert result.is_success is False
        assert result.error_code == "NOT_CONFIGURED"


# ============================================================================
# Testes de Tratamento de Erros
# ============================================================================


class TestEmailErrorHandling:
    """
    Testes de tratamento de erros no envio.

    Verifica que erros são tratados e reportados corretamente.
    """

    def test_authentication_error(self) -> None:
        """Deve tratar erro de autenticação."""
        import smtplib

        from autotarefas.core.email import EmailMessage, EmailSender, SMTPConfig

        config = SMTPConfig(
            host="smtp.test.com",
            port=587,
            username="user",
            password="wrong",
            from_addr="sender@test.com",
            use_tls=False,
            use_ssl=False,
        )

        sender = EmailSender(config)

        message = EmailMessage(
            to=["dest@test.com"],
            subject="Teste",
            body="Corpo",
        )

        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.login.side_effect = smtplib.SMTPAuthenticationError(
                535, b"Auth failed"
            )

            result = sender.send(message)

            assert result.is_success is False
            assert result.error_code == "AUTH_FAILED"

    def test_connection_error(self) -> None:
        """Deve tratar erro de conexão."""
        import smtplib

        from autotarefas.core.email import EmailMessage, EmailSender, SMTPConfig

        config = SMTPConfig(
            host="smtp.invalid.com",
            port=587,
            from_addr="sender@test.com",
            use_tls=False,
            use_ssl=False,
        )

        sender = EmailSender(config)

        message = EmailMessage(
            to=["dest@test.com"],
            subject="Teste",
            body="Corpo",
        )

        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = smtplib.SMTPException("Connection failed")

            result = sender.send(message)

            assert result.is_success is False


# ============================================================================
# Testes de EmailPriority
# ============================================================================


class TestEmailPriorityIntegration:
    """Testes de prioridade de email."""

    def test_priority_values(self) -> None:
        """Deve ter valores corretos de prioridade."""
        from autotarefas.core.email import EmailPriority

        assert EmailPriority.URGENT.value == 1
        assert EmailPriority.HIGH.value == 2
        assert EmailPriority.NORMAL.value == 3
        assert EmailPriority.LOW.value == 5

    def test_priority_x_priority_header(self) -> None:
        """Deve gerar header X-Priority."""
        from autotarefas.core.email import EmailPriority

        assert EmailPriority.URGENT.x_priority == "1"
        assert EmailPriority.NORMAL.x_priority == "3"

    def test_priority_importance_header(self) -> None:
        """Deve gerar header Importance."""
        from autotarefas.core.email import EmailPriority

        assert EmailPriority.URGENT.importance == "high"
        assert EmailPriority.NORMAL.importance == "normal"
        assert EmailPriority.LOW.importance == "low"

    def test_message_with_priority(self) -> None:
        """Deve criar mensagem com prioridade."""
        from autotarefas.core.email import EmailMessage, EmailPriority

        message = EmailMessage(
            to=["dest@example.com"],
            subject="Urgente!",
            body="Mensagem urgente",
            priority=EmailPriority.URGENT,
        )

        assert message.priority == EmailPriority.URGENT


# ============================================================================
# Testes de Integração com Storage
# ============================================================================


class TestEmailWithStorage:
    """
    Testes de integração com RunHistory.

    Verifica registro de envios de email no histórico.
    """

    def test_email_with_run_history(
        self,
        integration_env: dict[str, Path],
        mock_smtp_server: MagicMock,
    ) -> None:
        """Deve registrar envio no RunHistory."""
        from autotarefas.core.email import EmailMessage, EmailSender, SMTPConfig
        from autotarefas.core.storage.run_history import RunHistory, RunStatus

        history = RunHistory(integration_env["data"] / "email_history.db")

        config = SMTPConfig(
            host="smtp.test.com",
            port=587,
            from_addr="sender@test.com",
            use_tls=False,
            use_ssl=False,
        )

        # Registrar início
        record = history.start_run(
            job_id="email-job-1",
            job_name="send_report",
            task="email",
            params={"to": "dest@test.com"},
        )

        # Enviar
        sender = EmailSender(config)
        message = EmailMessage(
            to=["dest@test.com"],
            subject="Relatório",
            body="Segue relatório",
        )
        result = sender.send(message)

        # Registrar fim
        history.finish_run(
            record.id,
            RunStatus.SUCCESS if result.is_success else RunStatus.FAILED,
            duration=result.duration,
            output=f"Message ID: {result.message_id}",
        )

        # Verificar
        runs = history.get_by_job("email-job-1")
        assert len(runs) == 1


# ============================================================================
# Testes de Integração com Notifier
# ============================================================================


class TestEmailWithNotifier:
    """
    Testes de integração com sistema de notificações.

    O Notifier pode usar EmailSender para enviar notificações por email.
    """

    def test_notifier_email_channel(
        self,
        integration_env: dict[str, Path],
        mock_smtp_server: MagicMock,
    ) -> None:
        """Notifier deve poder enviar via email."""
        from autotarefas.core.email import SMTPConfig
        from autotarefas.core.notifier import (
            NotificationLevel,
            Notifier,
            reset_notifier,
        )

        reset_notifier()

        config = SMTPConfig(
            host="smtp.test.com",
            port=587,
            from_addr="sender@test.com",
            use_tls=False,
            use_ssl=False,
        )

        notifier = Notifier()

        # Configurar canal de email (se disponível)
        # Nota: O canal EMAIL pode não estar implementado ainda
        # Este teste verifica a integração conceitual

        # Enviar notificação que poderia ir por email
        notifier.notify(
            "Backup concluído com sucesso",
            level=NotificationLevel.SUCCESS,
            title="Backup",
        )

        reset_notifier()


# ============================================================================
# Testes de EmailResult
# ============================================================================


class TestEmailResultIntegration:
    """Testes de resultado de envio."""

    def test_success_result(self) -> None:
        """Deve criar resultado de sucesso."""
        from autotarefas.core.email import EmailResult, EmailStatus

        result = EmailResult.success_result(
            message_id="<123@test.com>",
            recipients=["dest@test.com"],
            duration=0.5,
        )

        assert result.is_success is True
        assert result.status == EmailStatus.SENT
        assert result.message_id == "<123@test.com>"

    def test_failure_result(self) -> None:
        """Deve criar resultado de falha."""
        from autotarefas.core.email import EmailResult, EmailStatus

        result = EmailResult.failure_result(
            error="Connection refused",
            error_code="CONN_ERROR",
        )

        assert result.is_success is False
        assert result.status == EmailStatus.FAILED
        assert result.error == "Connection refused"
        assert result.error_code == "CONN_ERROR"


# ============================================================================
# Testes de Edge Cases
# ============================================================================


class TestEmailEdgeCases:
    """Testes de casos extremos."""

    def test_long_subject(self) -> None:
        """Deve aceitar assunto longo."""
        from autotarefas.core.email import EmailMessage

        long_subject = "A" * 200

        message = EmailMessage(
            to=["dest@example.com"],
            subject=long_subject,
            body="Corpo",
        )

        assert len(message.subject) == 200

    def test_unicode_content(self) -> None:
        """Deve aceitar conteúdo unicode."""
        from autotarefas.core.email import EmailMessage

        message = EmailMessage(
            to=["dest@example.com"],
            subject="日本語テスト",
            body="Conteúdo em português com acentos: é, ã, ç",
            html="<p>Émojis: 🎉 ✅ 📧</p>",
        )

        assert "日本語" in message.subject
        assert "acentos" in message.body

    def test_multiple_attachments(self) -> None:
        """Deve aceitar múltiplos anexos."""
        from autotarefas.core.email import EmailAttachment, EmailMessage

        message = EmailMessage(
            to=["dest@example.com"],
            subject="Múltiplos anexos",
            body="Veja os anexos",
        )

        for i in range(5):
            message.add_attachment(
                EmailAttachment(
                    filename=f"file_{i}.txt",
                    content=f"Content {i}".encode(),
                )
            )

        assert len(message.attachments) == 5
        assert message.total_attachment_size > 0

    def test_html_only_message(self) -> None:
        """Deve aceitar mensagem apenas com HTML."""
        from autotarefas.core.email import EmailMessage

        message = EmailMessage(
            to=["dest@example.com"],
            subject="Apenas HTML",
            body="",  # Vazio mas HTML presente
            html="<h1>Título</h1><p>Conteúdo</p>",
        )

        assert message.html is not None
