"""
Testes End-to-End do CLI principal do AutoTarefas.

Este arquivo testa os comandos e opções principais da CLI,
verificando que a interface funciona corretamente do ponto
de vista do usuário.

=============================================================================
O QUE O test_cli_main.py TESTA
=============================================================================

Este arquivo testa a **interface principal** da CLI do AutoTarefas:

1. **Comando Help (--help, -h)**
   - Exibe ajuda formatada com Rich
   - Lista todos os comandos disponíveis
   - Mostra opções globais (--verbose, --quiet, --dry-run)

2. **Comando Version (--version)**
   - Exibe versão atual do AutoTarefas
   - Formato: "AutoTarefas vX.Y.Z"

3. **Opções Globais**
   - --verbose (-v): Modo verboso com mais detalhes
   - --quiet (-q): Modo silencioso sem output
   - --dry-run: Simula execução sem alterar nada

4. **Subcomandos Disponíveis**
   - init: Inicialização do sistema
   - backup: Gerenciamento de backups
   - clean: Limpeza de arquivos
   - monitor: Monitoramento do sistema
   - report: Geração de relatórios
   - schedule: Agendamento de tarefas
   - email: Envio de emails

5. **Tratamento de Erros**
   - Comando inválido → erro com sugestão
   - Opção inválida → erro de uso
   - Conflito de opções (--verbose + --quiet) → erro

=============================================================================
POR QUE ESTES TESTES SÃO IMPORTANTES
=============================================================================

Os testes E2E da CLI garantem que:

- A interface do usuário funciona como documentada
- Os comandos são registrados corretamente
- As mensagens de erro são úteis
- A experiência do usuário é consistente
- Mudanças no código não quebram a CLI

=============================================================================
COMO OS TESTES FUNCIONAM
=============================================================================

Usamos o CliRunner do Click para:
1. Invocar comandos como se fossem digitados no terminal
2. Capturar stdout/stderr
3. Verificar código de saída
4. Testar sem efeitos colaterais reais

Exemplo:
    result = cli_invoke("--help")
    assert result.exit_code == 0
    assert "backup" in result.output
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from click.testing import Result


# ============================================================================
# Testes de Help
# ============================================================================


class TestCliHelp:
    """
    Testes do comando --help.

    O help é a primeira coisa que um usuário vê, então deve ser
    claro, completo e bem formatado.
    """

    def test_help_shows_description(self, cli_invoke: Callable[..., Result]) -> None:
        """Help deve mostrar descrição do programa."""
        result = cli_invoke("--help")

        assert result.exit_code == 0
        # Deve mencionar AutoTarefas
        assert "autotarefas" in result.output.lower() or "AutoTarefas" in result.output

    def test_help_shows_version_option(self, cli_invoke: Callable[..., Result]) -> None:
        """Help deve mostrar opção --version."""
        result = cli_invoke("--help")

        assert result.exit_code == 0
        assert "--version" in result.output

    def test_help_shows_verbose_option(self, cli_invoke: Callable[..., Result]) -> None:
        """Help deve mostrar opção --verbose."""
        result = cli_invoke("--help")

        assert result.exit_code == 0
        assert "--verbose" in result.output or "-v" in result.output

    def test_help_shows_quiet_option(self, cli_invoke: Callable[..., Result]) -> None:
        """Help deve mostrar opção --quiet."""
        result = cli_invoke("--help")

        assert result.exit_code == 0
        assert "--quiet" in result.output or "-q" in result.output

    def test_help_shows_dry_run_option(self, cli_invoke: Callable[..., Result]) -> None:
        """Help deve mostrar opção --dry-run."""
        result = cli_invoke("--help")

        assert result.exit_code == 0
        assert "--dry-run" in result.output

    def test_help_short_flag(self, cli_invoke: Callable[..., Result]) -> None:
        """Flag -h deve funcionar como --help."""
        result = cli_invoke("-h")

        assert result.exit_code == 0
        # Deve ter conteúdo de help
        assert (
            "help" in result.output.lower()
            or "usage" in result.output.lower()
            or "Commands" in result.output
        )


# ============================================================================
# Testes de Subcomandos Listados
# ============================================================================


class TestCliSubcommands:
    """
    Testes que verificam se os subcomandos estão disponíveis.

    Cada comando principal deve aparecer no help.
    """

    def test_backup_command_listed(self, cli_invoke: Callable[..., Result]) -> None:
        """Comando backup deve estar listado."""
        result = cli_invoke("--help")

        assert result.exit_code == 0
        assert "backup" in result.output.lower()

    def test_clean_command_listed(self, cli_invoke: Callable[..., Result]) -> None:
        """Comando clean deve estar listado."""
        result = cli_invoke("--help")

        assert result.exit_code == 0
        assert "clean" in result.output.lower()

    def test_monitor_command_listed(self, cli_invoke: Callable[..., Result]) -> None:
        """Comando monitor deve estar listado."""
        result = cli_invoke("--help")

        assert result.exit_code == 0
        assert "monitor" in result.output.lower()

    def test_schedule_command_listed(self, cli_invoke: Callable[..., Result]) -> None:
        """Comando schedule deve estar listado."""
        result = cli_invoke("--help")

        assert result.exit_code == 0
        assert "schedule" in result.output.lower()

    def test_report_command_listed(self, cli_invoke: Callable[..., Result]) -> None:
        """Comando report deve estar listado."""
        result = cli_invoke("--help")

        assert result.exit_code == 0
        assert "report" in result.output.lower()

    def test_email_command_listed(self, cli_invoke: Callable[..., Result]) -> None:
        """Comando email deve estar listado."""
        result = cli_invoke("--help")

        assert result.exit_code == 0
        assert "email" in result.output.lower()

    def test_init_command_listed(self, cli_invoke: Callable[..., Result]) -> None:
        """Comando init deve estar listado."""
        result = cli_invoke("--help")

        assert result.exit_code == 0
        assert "init" in result.output.lower()


# ============================================================================
# Testes de Version
# ============================================================================


class TestCliVersion:
    """
    Testes do comando --version.

    A versão deve ser exibida corretamente e seguir semver.
    """

    def test_version_shows_number(self, cli_invoke: Callable[..., Result]) -> None:
        """--version deve mostrar número da versão."""
        result = cli_invoke("--version")

        assert result.exit_code == 0
        # Deve ter formato de versão (X.Y.Z)
        import re

        assert re.search(
            r"\d+\.\d+\.\d+", result.output
        ), f"Versão não encontrada em: {result.output}"

    def test_version_shows_name(self, cli_invoke: Callable[..., Result]) -> None:
        """--version deve mostrar nome do programa."""
        result = cli_invoke("--version")

        assert result.exit_code == 0
        assert "autotarefas" in result.output.lower() or "AutoTarefas" in result.output

    def test_version_current(self, cli_invoke: Callable[..., Result]) -> None:
        """Versão deve corresponder ao __version__ do pacote."""
        from autotarefas import __version__

        result = cli_invoke("--version")

        assert result.exit_code == 0
        assert __version__ in result.output


# ============================================================================
# Testes de Opções Globais
# ============================================================================


class TestCliGlobalOptions:
    """
    Testes das opções globais da CLI.

    Opções globais afetam todos os comandos.
    """

    def test_verbose_flag_accepted(self, cli_invoke: Callable[..., Result]) -> None:
        """Flag --verbose deve ser aceita."""
        result = cli_invoke("--verbose", "--help")

        # Não deve dar erro
        assert result.exit_code == 0

    def test_verbose_short_flag_accepted(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """Flag -v deve ser aceita."""
        result = cli_invoke("-v", "--help")

        assert result.exit_code == 0

    def test_quiet_flag_accepted(self, cli_invoke: Callable[..., Result]) -> None:
        """Flag --quiet deve ser aceita."""
        result = cli_invoke("--quiet", "--help")

        assert result.exit_code == 0

    def test_quiet_short_flag_accepted(self, cli_invoke: Callable[..., Result]) -> None:
        """Flag -q deve ser aceita."""
        result = cli_invoke("-q", "--help")

        assert result.exit_code == 0

    def test_dry_run_flag_accepted(self, cli_invoke: Callable[..., Result]) -> None:
        """Flag --dry-run deve ser aceita."""
        result = cli_invoke("--dry-run", "--help")

        assert result.exit_code == 0

    def test_verbose_and_quiet_conflict(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """--verbose e --quiet juntos devem dar erro."""
        result = cli_invoke("--verbose", "--quiet", "--help")

        # Deve falhar (conflito)
        assert (
            result.exit_code != 0
            or "erro" in result.output.lower()
            or "error" in result.output.lower()
        )


# ============================================================================
# Testes de Erros
# ============================================================================


class TestCliErrors:
    """
    Testes de tratamento de erros.

    A CLI deve dar mensagens úteis quando algo dá errado.
    """

    def test_invalid_command_error(self, cli_invoke: Callable[..., Result]) -> None:
        """Comando inválido deve dar erro."""
        result = cli_invoke("comando_inexistente")

        assert result.exit_code != 0

    def test_invalid_option_error(self, cli_invoke: Callable[..., Result]) -> None:
        """Opção inválida deve dar erro."""
        result = cli_invoke("--opcao-invalida")

        assert result.exit_code != 0

    def test_no_command_shows_help(self, cli_invoke: Callable[..., Result]) -> None:
        """Sem comando deve mostrar help ou lista de comandos."""
        result = cli_invoke()

        # Pode mostrar help ou dar erro pedindo comando
        # O importante é ter algum output útil
        assert result.output  # Tem algum output


# ============================================================================
# Testes de Subcomandos Help
# ============================================================================


class TestSubcommandHelp:
    """
    Testes de help dos subcomandos.

    Cada subcomando deve ter seu próprio --help.
    """

    def test_backup_help(self, cli_invoke: Callable[..., Result]) -> None:
        """backup --help deve funcionar."""
        result = cli_invoke("backup", "--help")

        assert result.exit_code == 0
        assert "backup" in result.output.lower()

    def test_clean_help(self, cli_invoke: Callable[..., Result]) -> None:
        """clean --help deve funcionar."""
        result = cli_invoke("clean", "--help")

        assert result.exit_code == 0
        assert "clean" in result.output.lower() or "limp" in result.output.lower()

    def test_monitor_help(self, cli_invoke: Callable[..., Result]) -> None:
        """monitor --help deve funcionar."""
        result = cli_invoke("monitor", "--help")

        assert result.exit_code == 0
        assert "monitor" in result.output.lower()

    def test_schedule_help(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule --help deve funcionar."""
        result = cli_invoke("schedule", "--help")

        assert result.exit_code == 0
        assert "schedule" in result.output.lower() or "agend" in result.output.lower()

    def test_report_help(self, cli_invoke: Callable[..., Result]) -> None:
        """report --help deve funcionar."""
        result = cli_invoke("report", "--help")

        assert result.exit_code == 0
        assert "report" in result.output.lower() or "relat" in result.output.lower()

    def test_email_help(self, cli_invoke: Callable[..., Result]) -> None:
        """email --help deve funcionar."""
        result = cli_invoke("email", "--help")

        assert result.exit_code == 0
        assert "email" in result.output.lower()

    def test_init_help(self, cli_invoke: Callable[..., Result]) -> None:
        """init --help deve funcionar."""
        result = cli_invoke("init", "--help")

        assert result.exit_code == 0
        assert "init" in result.output.lower()


# ============================================================================
# Testes de Integração Básica
# ============================================================================


class TestCliBasicIntegration:
    """
    Testes básicos de integração da CLI.

    Verificam que os comandos podem ser invocados sem erros críticos.
    """

    def test_cli_imports_correctly(self) -> None:
        """CLI deve importar sem erros."""
        from autotarefas.cli.main import cli, main

        assert cli is not None
        assert main is not None
        assert callable(main)

    def test_cli_has_commands(self) -> None:
        """CLI deve ter comandos registrados."""
        from autotarefas.cli.main import cli

        # Click groups têm atributo commands
        assert hasattr(cli, "commands")
        assert len(cli.commands) > 0

    def test_main_function_exists(self) -> None:
        """Função main deve existir e ser callable."""
        from autotarefas.cli.main import main

        assert callable(main)

    def test_console_exists(self) -> None:
        """Console Rich deve estar disponível."""
        from autotarefas.cli.main import console

        assert console is not None


# ============================================================================
# Testes de Códigos de Saída
# ============================================================================


class TestCliExitCodes:
    """
    Testes de códigos de saída.

    A CLI deve retornar códigos de saída padronizados.
    """

    def test_help_returns_zero(self, cli_invoke: Callable[..., Result]) -> None:
        """--help deve retornar código 0."""
        result = cli_invoke("--help")

        assert result.exit_code == 0

    def test_version_returns_zero(self, cli_invoke: Callable[..., Result]) -> None:
        """--version deve retornar código 0."""
        result = cli_invoke("--version")

        assert result.exit_code == 0

    def test_invalid_command_returns_nonzero(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """Comando inválido deve retornar código != 0."""
        result = cli_invoke("comando_que_nao_existe")

        assert result.exit_code != 0

    def test_invalid_option_returns_nonzero(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """Opção inválida deve retornar código != 0."""
        result = cli_invoke("--opcao-que-nao-existe")

        assert result.exit_code != 0
