"""
Testes End-to-End dos comandos de email do AutoTarefas.

Este arquivo testa os comandos da CLI relacionados a email e notificações,
verificando que funcionam corretamente do ponto de vista do usuário.

=============================================================================
O QUE O test_cli_email.py TESTA
=============================================================================

Este arquivo testa os **comandos de email e notificação** da CLI:

1. **email status** - Mostra status da configuração
   - Exibe configuração SMTP (host, porta, TLS, etc.)
   - Exibe canais de notificação ativos

2. **email test** - Testa conexão SMTP
   - Opções: --send, --to
   - Valida conexão sem enviar ou envia email de teste

3. **email send** - Envia email
   - Argumentos: TO (um ou mais destinatários)
   - Opções: --subject, --message, --file, --html, --attach, --cc, --bcc

4. **email notify** - Envia notificação multi-canal
   - Argumentos: MESSAGE
   - Opções: --title, --level, --source, --channel, --tag, --data

5. **email history** - Histórico de notificações
   - Opções: --limit, --level, --clear
   - Lista ou limpa histórico

6. **email channels** - Gerencia canais de notificação
   - Opções: --add, --remove, --enable, --disable
   - Configura canais (console, email, file, webhook)

=============================================================================
NÍVEIS DE NOTIFICAÇÃO
=============================================================================

| Nível    | Uso                              |
|----------|----------------------------------|
| debug    | Informações de depuração         |
| info     | Informações gerais               |
| success  | Operação bem-sucedida            |
| warning  | Avisos (não críticos)            |
| error    | Erros (requer atenção)           |
| critical | Erros críticos (urgente)         |

=============================================================================
CANAIS DE NOTIFICAÇÃO
=============================================================================

| Canal   | Descrição                         |
|---------|-----------------------------------|
| console | Saída no terminal                 |
| email   | Envio por email                   |
| file    | Gravação em arquivo de log        |
| webhook | Envio para URL externa            |

=============================================================================
POR QUE ESTES TESTES SÃO IMPORTANTES
=============================================================================

Comandos de email são importantes porque:
- Notificações são essenciais para automação
- Configuração SMTP pode ser complexa
- Erros devem ser claros para o usuário
- Multi-canal permite flexibilidade
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from click.testing import Result


# ============================================================================
# Testes de Help
# ============================================================================


class TestEmailHelp:
    """Testes de help dos comandos de email."""

    def test_email_help(self, cli_invoke: Callable[..., Result]) -> None:
        """email --help deve mostrar subcomandos."""
        result = cli_invoke("email", "--help")

        assert result.exit_code == 0
        assert "status" in result.output
        assert "test" in result.output
        assert "send" in result.output
        assert "notify" in result.output

    def test_email_status_help(self, cli_invoke: Callable[..., Result]) -> None:
        """email status --help deve funcionar."""
        result = cli_invoke("email", "status", "--help")

        assert result.exit_code == 0

    def test_email_test_help(self, cli_invoke: Callable[..., Result]) -> None:
        """email test --help deve mostrar opções."""
        result = cli_invoke("email", "test", "--help")

        assert result.exit_code == 0
        assert "--send" in result.output or "-s" in result.output
        assert "--to" in result.output or "-t" in result.output

    def test_email_send_help(self, cli_invoke: Callable[..., Result]) -> None:
        """email send --help deve mostrar opções."""
        result = cli_invoke("email", "send", "--help")

        assert result.exit_code == 0
        assert "--subject" in result.output or "-s" in result.output
        assert "--message" in result.output or "-m" in result.output
        assert "--attach" in result.output or "-a" in result.output

    def test_email_notify_help(self, cli_invoke: Callable[..., Result]) -> None:
        """email notify --help deve mostrar opções."""
        result = cli_invoke("email", "notify", "--help")

        assert result.exit_code == 0
        assert "--level" in result.output or "-l" in result.output
        assert "--channel" in result.output or "-c" in result.output

    def test_email_history_help(self, cli_invoke: Callable[..., Result]) -> None:
        """email history --help deve mostrar opções."""
        result = cli_invoke("email", "history", "--help")

        assert result.exit_code == 0
        assert "--limit" in result.output or "-n" in result.output
        assert "--clear" in result.output

    def test_email_channels_help(self, cli_invoke: Callable[..., Result]) -> None:
        """email channels --help deve mostrar opções."""
        result = cli_invoke("email", "channels", "--help")

        assert result.exit_code == 0
        assert "--add" in result.output or "-a" in result.output
        assert "--remove" in result.output or "-r" in result.output


# ============================================================================
# Testes de email status
# ============================================================================


class TestEmailStatus:
    """Testes do comando email status."""

    def test_email_status(self, cli_invoke: Callable[..., Result]) -> None:
        """email status deve mostrar configuração."""
        result = cli_invoke("email", "status")

        assert result.exit_code == 0
        # Deve mostrar informações de configuração
        output_lower = result.output.lower()
        assert (
            "smtp" in output_lower or "email" in output_lower or "host" in output_lower
        )

    def test_email_status_shows_smtp(self, cli_invoke: Callable[..., Result]) -> None:
        """email status deve mostrar configuração SMTP."""
        result = cli_invoke("email", "status")

        assert result.exit_code == 0
        # Deve mencionar configuração
        output_lower = result.output.lower()
        assert any(
            word in output_lower
            for word in ["configurado", "configured", "host", "porta", "port"]
        )


# ============================================================================
# Testes de email test
# ============================================================================


class TestEmailTest:
    """Testes do comando email test."""

    def test_email_test_dry_run(self, cli_invoke: Callable[..., Result]) -> None:
        """email test em dry-run deve simular."""
        result = cli_invoke("--dry-run", "email", "test")

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()

    def test_email_test_with_send_dry_run(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """email test --send em dry-run deve simular envio."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "test",
            "--send",
            "--to",
            "test@example.com",
        )

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()


# ============================================================================
# Testes de email send
# ============================================================================


class TestEmailSend:
    """Testes do comando email send."""

    def test_email_send_requires_to(self, cli_invoke: Callable[..., Result]) -> None:
        """email send deve exigir destinatário."""
        result = cli_invoke("email", "send", "-s", "Teste")

        assert result.exit_code != 0

    def test_email_send_requires_subject(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """email send deve exigir assunto."""
        result = cli_invoke("email", "send", "test@example.com")

        assert result.exit_code != 0

    def test_email_send_dry_run(self, cli_invoke: Callable[..., Result]) -> None:
        """email send em dry-run deve simular."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "send",
            "test@example.com",
            "-s",
            "Assunto Teste",
            "-m",
            "Corpo do email",
        )

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()

    def test_email_send_with_cc(self, cli_invoke: Callable[..., Result]) -> None:
        """email send deve aceitar --cc."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "send",
            "test@example.com",
            "-s",
            "Teste",
            "-m",
            "Corpo",
            "--cc",
            "cc@example.com",
        )

        assert result.exit_code == 0

    def test_email_send_multiple_recipients(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """email send deve aceitar múltiplos destinatários."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "send",
            "test1@example.com",
            "test2@example.com",
            "-s",
            "Teste",
            "-m",
            "Corpo",
        )

        assert result.exit_code == 0


# ============================================================================
# Testes de email notify
# ============================================================================


class TestEmailNotify:
    """Testes do comando email notify."""

    def test_email_notify_requires_message(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """email notify deve exigir mensagem."""
        result = cli_invoke("email", "notify")

        assert result.exit_code != 0

    def test_email_notify_dry_run(self, cli_invoke: Callable[..., Result]) -> None:
        """email notify em dry-run deve simular."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "notify",
            "Teste de notificação",
        )

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()

    def test_email_notify_with_level(self, cli_invoke: Callable[..., Result]) -> None:
        """email notify deve aceitar --level."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "notify",
            "Backup concluído!",
            "--level",
            "success",
        )

        assert result.exit_code == 0

    def test_email_notify_with_title(self, cli_invoke: Callable[..., Result]) -> None:
        """email notify deve aceitar --title."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "notify",
            "Operação concluída",
            "--title",
            "Backup",
        )

        assert result.exit_code == 0

    def test_email_notify_with_channel(self, cli_invoke: Callable[..., Result]) -> None:
        """email notify deve aceitar --channel."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "notify",
            "Teste",
            "--channel",
            "console",
        )

        assert result.exit_code == 0


# ============================================================================
# Testes de email history
# ============================================================================


class TestEmailHistory:
    """Testes do comando email history."""

    def test_email_history(self, cli_invoke: Callable[..., Result]) -> None:
        """email history deve listar histórico."""
        result = cli_invoke("email", "history")

        assert result.exit_code == 0
        # Pode mostrar histórico vazio ou com registros
        output_lower = result.output.lower()
        assert (
            "histórico" in output_lower
            or "history" in output_lower
            or "nenhum" in output_lower
        )

    def test_email_history_with_limit(self, cli_invoke: Callable[..., Result]) -> None:
        """email history deve aceitar --limit."""
        result = cli_invoke("email", "history", "--limit", "5")

        assert result.exit_code == 0

    def test_email_history_with_level(self, cli_invoke: Callable[..., Result]) -> None:
        """email history deve aceitar --level."""
        result = cli_invoke("email", "history", "--level", "error")

        assert result.exit_code == 0

    def test_email_history_clear_dry_run(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """email history --clear em dry-run deve simular."""
        result = cli_invoke("--dry-run", "email", "history", "--clear")

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()


# ============================================================================
# Testes de email channels
# ============================================================================


class TestEmailChannels:
    """Testes do comando email channels."""

    def test_email_channels_list(self, cli_invoke: Callable[..., Result]) -> None:
        """email channels deve listar canais."""
        result = cli_invoke("email", "channels")

        assert result.exit_code == 0
        # Deve mostrar lista de canais ou tabela
        output_lower = result.output.lower()
        assert (
            "canal" in output_lower
            or "channel" in output_lower
            or "console" in output_lower
        )

    def test_email_channels_add_dry_run(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """email channels --add em dry-run deve simular."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "channels",
            "--add",
            "file",
        )

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()

    def test_email_channels_remove_dry_run(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """email channels --remove em dry-run deve simular."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "channels",
            "--remove",
            "webhook",
        )

        assert result.exit_code == 0

    def test_email_channels_enable_dry_run(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """email channels --enable em dry-run deve simular."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "channels",
            "--enable",
            "console",
        )

        assert result.exit_code == 0


# ============================================================================
# Testes de Níveis de Notificação
# ============================================================================


class TestNotificationLevels:
    """Testes dos níveis de notificação."""

    @pytest.mark.parametrize(
        "level",
        [
            "debug",
            "info",
            "success",
            "warning",
            "error",
            "critical",
        ],
    )
    def test_all_levels_accepted(
        self,
        cli_invoke: Callable[..., Result],
        level: str,
    ) -> None:
        """Todos os níveis de notificação devem ser aceitos."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "notify",
            "Teste",
            "--level",
            level,
        )

        assert result.exit_code == 0

    def test_invalid_level_rejected(self, cli_invoke: Callable[..., Result]) -> None:
        """Nível inválido deve ser rejeitado."""
        result = cli_invoke(
            "email",
            "notify",
            "Teste",
            "--level",
            "invalid_level",
        )

        assert result.exit_code != 0


# ============================================================================
# Testes de Canais de Notificação
# ============================================================================


class TestNotificationChannels:
    """Testes dos canais de notificação."""

    @pytest.mark.parametrize(
        "channel",
        [
            "console",
            "email",
            "file",
            "webhook",
        ],
    )
    def test_all_channels_accepted(
        self,
        cli_invoke: Callable[..., Result],
        channel: str,
    ) -> None:
        """Todos os canais devem ser aceitos."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "notify",
            "Teste",
            "--channel",
            channel,
        )

        assert result.exit_code == 0

    def test_invalid_channel_rejected(self, cli_invoke: Callable[..., Result]) -> None:
        """Canal inválido deve ser rejeitado."""
        result = cli_invoke(
            "email",
            "notify",
            "Teste",
            "--channel",
            "invalid_channel",
        )

        assert result.exit_code != 0


# ============================================================================
# Testes de Edge Cases
# ============================================================================


class TestEmailEdgeCases:
    """Testes de casos extremos."""

    def test_email_with_verbose(self, cli_invoke: Callable[..., Result]) -> None:
        """Comandos devem funcionar com --verbose global."""
        result = cli_invoke("--verbose", "email", "status")

        assert result.exit_code == 0

    def test_email_with_quiet(self, cli_invoke: Callable[..., Result]) -> None:
        """Comandos devem funcionar com --quiet global."""
        result = cli_invoke("--quiet", "email", "status")

        assert result.exit_code == 0

    def test_invalid_subcommand(self, cli_invoke: Callable[..., Result]) -> None:
        """Subcomando inválido deve dar erro."""
        result = cli_invoke("email", "invalid_command")

        assert result.exit_code != 0

    def test_notify_with_tags(self, cli_invoke: Callable[..., Result]) -> None:
        """email notify deve aceitar múltiplas --tag."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "notify",
            "Teste",
            "--tag",
            "backup",
            "--tag",
            "importante",
        )

        assert result.exit_code == 0

    def test_notify_with_data_json(self, cli_invoke: Callable[..., Result]) -> None:
        """email notify deve aceitar --data JSON."""
        result = cli_invoke(
            "--dry-run",
            "email",
            "notify",
            "Teste",
            "--data",
            '{"key": "value"}',
        )

        assert result.exit_code == 0
