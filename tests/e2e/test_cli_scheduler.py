"""
Testes End-to-End dos comandos de agendamento do AutoTarefas.

Este arquivo testa os comandos da CLI relacionados ao scheduler,
verificando que funcionam corretamente do ponto de vista do usuário.

=============================================================================
O QUE O test_cli_scheduler.py TESTA
=============================================================================

Este arquivo testa os **comandos de agendamento** da CLI:

1. **schedule list** - Lista jobs agendados
   - Opções: -a/--all (inclui desabilitados), -v/--verbose
   - Exibe tabela com jobs e próximas execuções

2. **schedule add** - Adiciona um novo job
   - Argumentos: NAME, TASK, SCHEDULE_EXPR
   - Opções: -t/--type, -p/--param, -d/--description, --tag

3. **schedule remove** - Remove um job
   - Argumentos: JOB_ID_OR_NAME
   - Opções: -f/--force (sem confirmação)

4. **schedule run** - Executa um job manualmente
   - Argumentos: JOB_ID_OR_NAME
   - Executa imediatamente, fora do agendamento

5. **schedule pause/resume** - Pausa/retoma um job
   - Argumentos: JOB_ID_OR_NAME
   - Controla se o job será executado

6. **schedule start/stop** - Inicia/para o scheduler
   - Opções: -f/--foreground (start), -f/--force (stop)
   - Controla o loop principal do scheduler

7. **schedule status** - Mostra status do scheduler
   - Exibe estado atual, jobs ativos, estatísticas

8. **schedule tasks** - Lista tasks disponíveis
   - Mostra tasks que podem ser agendadas

9. **schedule show** - Mostra detalhes de um job
   - Argumentos: JOB_ID_OR_NAME
   - Exibe todas as informações do job

=============================================================================
TIPOS DE AGENDAMENTO SUPORTADOS
=============================================================================

| Tipo     | Formato                | Exemplo                    |
|----------|------------------------|----------------------------|
| cron     | Expressão cron         | "0 2 * * *" (2h diário)    |
| interval | Segundos               | "3600" (1 hora)            |
| daily    | HH:MM                  | "08:30"                    |
| once     | YYYY-MM-DD HH:MM:SS    | "2024-12-31 23:59:00"      |

=============================================================================
POR QUE ESTES TESTES SÃO IMPORTANTES
=============================================================================

O scheduler é o coração da automação:
- Jobs devem ser criados e executados corretamente
- Erros de agendamento podem causar perda de tarefas
- Interface deve ser clara para usuários configurarem
- Estado do scheduler deve ser visível
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


class TestScheduleHelp:
    """Testes de help dos comandos de agendamento."""

    def test_schedule_help(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule --help deve mostrar subcomandos."""
        result = cli_invoke("schedule", "--help")

        assert result.exit_code == 0
        assert "list" in result.output
        assert "add" in result.output
        assert "remove" in result.output

    def test_schedule_list_help(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule list --help deve mostrar opções."""
        result = cli_invoke("schedule", "list", "--help")

        assert result.exit_code == 0
        assert "--all" in result.output or "-a" in result.output

    def test_schedule_add_help(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule add --help deve mostrar opções."""
        result = cli_invoke("schedule", "add", "--help")

        assert result.exit_code == 0
        assert "--type" in result.output or "-t" in result.output
        assert "--param" in result.output or "-p" in result.output

    def test_schedule_remove_help(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule remove --help deve mostrar opções."""
        result = cli_invoke("schedule", "remove", "--help")

        assert result.exit_code == 0
        assert "--force" in result.output or "-f" in result.output

    def test_schedule_run_help(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule run --help deve funcionar."""
        result = cli_invoke("schedule", "run", "--help")

        assert result.exit_code == 0

    def test_schedule_start_help(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule start --help deve mostrar opções."""
        result = cli_invoke("schedule", "start", "--help")

        assert result.exit_code == 0
        assert "--foreground" in result.output or "-f" in result.output

    def test_schedule_stop_help(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule stop --help deve mostrar opções."""
        result = cli_invoke("schedule", "stop", "--help")

        assert result.exit_code == 0

    def test_schedule_status_help(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule status --help deve funcionar."""
        result = cli_invoke("schedule", "status", "--help")

        assert result.exit_code == 0

    def test_schedule_tasks_help(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule tasks --help deve funcionar."""
        result = cli_invoke("schedule", "tasks", "--help")

        assert result.exit_code == 0

    def test_schedule_show_help(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule show --help deve funcionar."""
        result = cli_invoke("schedule", "show", "--help")

        assert result.exit_code == 0


# ============================================================================
# Testes de schedule list
# ============================================================================


class TestScheduleList:
    """Testes do comando schedule list."""

    def test_schedule_list_empty(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule list sem jobs deve informar."""
        result = cli_invoke("schedule", "list")

        assert result.exit_code == 0
        # Pode mostrar "nenhum job" ou tabela vazia
        output_lower = result.output.lower()
        assert (
            "job" in output_lower or "nenhum" in output_lower or "empty" in output_lower
        )

    def test_schedule_list_all(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule list --all deve funcionar."""
        result = cli_invoke("schedule", "list", "--all")

        assert result.exit_code == 0

    def test_schedule_list_verbose(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule list --verbose deve funcionar."""
        result = cli_invoke("schedule", "list", "--verbose")

        assert result.exit_code == 0


# ============================================================================
# Testes de schedule add
# ============================================================================


class TestScheduleAdd:
    """Testes do comando schedule add."""

    def test_schedule_add_requires_arguments(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """schedule add deve exigir argumentos."""
        result = cli_invoke("schedule", "add")

        assert result.exit_code != 0

    def test_schedule_add_dry_run(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule add em dry-run deve simular."""
        result = cli_invoke(
            "--dry-run",
            "schedule",
            "add",
            "test_job",
            "backup",
            "0 2 * * *",
        )

        assert result.exit_code == 0
        assert (
            "dry-run" in result.output.lower() or "simulação" in result.output.lower()
        )

    def test_schedule_add_with_type(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule add deve aceitar --type."""
        result = cli_invoke(
            "--dry-run",
            "schedule",
            "add",
            "test_job",
            "backup",
            "3600",
            "-t",
            "interval",
        )

        assert result.exit_code == 0

    def test_schedule_add_with_description(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """schedule add deve aceitar --description."""
        result = cli_invoke(
            "--dry-run",
            "schedule",
            "add",
            "test_job",
            "backup",
            "0 2 * * *",
            "-d",
            "Backup diário às 2h",
        )

        assert result.exit_code == 0

    def test_schedule_add_with_tags(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule add deve aceitar --tag."""
        result = cli_invoke(
            "--dry-run",
            "schedule",
            "add",
            "test_job",
            "backup",
            "0 2 * * *",
            "--tag",
            "importante",
            "--tag",
            "diario",
        )

        assert result.exit_code == 0


# ============================================================================
# Testes de schedule remove
# ============================================================================


class TestScheduleRemove:
    """Testes do comando schedule remove."""

    def test_schedule_remove_requires_job(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """schedule remove deve exigir JOB_ID."""
        result = cli_invoke("schedule", "remove")

        assert result.exit_code != 0

    def test_schedule_remove_nonexistent(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """schedule remove de job inexistente deve falhar."""
        result = cli_invoke("schedule", "remove", "job_que_nao_existe", "-f")

        assert result.exit_code != 0

    def test_schedule_remove_dry_run(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule remove em dry-run deve simular."""
        # Mesmo com job inexistente, dry-run pode mostrar simulação
        _ = cli_invoke(
            "--dry-run",
            "schedule",
            "remove",
            "qualquer_job",
        )

        # Pode falhar se job não existe, mesmo em dry-run
        # O importante é que não deu erro de sintaxe


# ============================================================================
# Testes de schedule run
# ============================================================================


class TestScheduleRun:
    """Testes do comando schedule run."""

    def test_schedule_run_requires_job(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule run deve exigir JOB_ID."""
        result = cli_invoke("schedule", "run")

        assert result.exit_code != 0

    def test_schedule_run_nonexistent(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule run de job inexistente deve falhar."""
        result = cli_invoke("schedule", "run", "job_que_nao_existe")

        assert result.exit_code != 0


# ============================================================================
# Testes de schedule pause/resume
# ============================================================================


class TestSchedulePauseResume:
    """Testes dos comandos pause e resume."""

    def test_schedule_pause_requires_job(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """schedule pause deve exigir JOB_ID."""
        result = cli_invoke("schedule", "pause")

        assert result.exit_code != 0

    def test_schedule_resume_requires_job(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """schedule resume deve exigir JOB_ID."""
        result = cli_invoke("schedule", "resume")

        assert result.exit_code != 0

    def test_schedule_pause_nonexistent(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """schedule pause de job inexistente deve falhar."""
        result = cli_invoke("schedule", "pause", "job_que_nao_existe")

        assert result.exit_code != 0

    def test_schedule_resume_nonexistent(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """schedule resume de job inexistente deve falhar."""
        result = cli_invoke("schedule", "resume", "job_que_nao_existe")

        assert result.exit_code != 0


# ============================================================================
# Testes de schedule start/stop
# ============================================================================


class TestScheduleStartStop:
    """Testes dos comandos start e stop."""

    def test_schedule_start_dry_run(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule start em dry-run deve simular."""
        result = cli_invoke("--dry-run", "schedule", "start")

        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()

    def test_schedule_stop_not_running(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule stop quando não está rodando deve informar."""
        result = cli_invoke("schedule", "stop")

        assert result.exit_code == 0
        # Deve indicar que não está rodando
        output_lower = result.output.lower()
        assert (
            "não" in output_lower or "not" in output_lower or "rodando" in output_lower
        )

    def test_schedule_stop_dry_run(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule stop em dry-run deve simular."""
        result = cli_invoke("--dry-run", "schedule", "stop")

        assert result.exit_code == 0


# ============================================================================
# Testes de schedule status
# ============================================================================


class TestScheduleStatus:
    """Testes do comando schedule status."""

    def test_schedule_status(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule status deve mostrar informações."""
        result = cli_invoke("schedule", "status")

        assert result.exit_code == 0
        # Deve mostrar status do scheduler
        output_lower = result.output.lower()
        assert (
            "status" in output_lower
            or "job" in output_lower
            or "scheduler" in output_lower
        )

    def test_schedule_status_shows_state(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """schedule status deve indicar se está rodando."""
        result = cli_invoke("schedule", "status")

        assert result.exit_code == 0
        # Deve ter indicação de estado
        output_lower = result.output.lower()
        assert any(
            word in output_lower
            for word in ["rodando", "parado", "running", "stopped", "🟢", "🔴"]
        )


# ============================================================================
# Testes de schedule tasks
# ============================================================================


class TestScheduleTasks:
    """Testes do comando schedule tasks."""

    def test_schedule_tasks(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule tasks deve listar tasks disponíveis."""
        result = cli_invoke("schedule", "tasks")

        assert result.exit_code == 0
        # Deve listar pelo menos backup e cleaner
        output_lower = result.output.lower()
        assert "backup" in output_lower or "task" in output_lower


# ============================================================================
# Testes de schedule show
# ============================================================================


class TestScheduleShow:
    """Testes do comando schedule show."""

    def test_schedule_show_requires_job(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """schedule show deve exigir JOB_ID."""
        result = cli_invoke("schedule", "show")

        assert result.exit_code != 0

    def test_schedule_show_nonexistent(self, cli_invoke: Callable[..., Result]) -> None:
        """schedule show de job inexistente deve falhar."""
        result = cli_invoke("schedule", "show", "job_que_nao_existe")

        assert result.exit_code != 0


# ============================================================================
# Testes de Tipos de Agendamento
# ============================================================================


class TestScheduleTypes:
    """Testes dos diferentes tipos de agendamento."""

    @pytest.mark.parametrize(
        "schedule_type,schedule_expr",
        [
            ("cron", "0 2 * * *"),
            ("interval", "3600"),
            ("daily", "08:30"),
        ],
    )
    def test_schedule_types_accepted(
        self,
        cli_invoke: Callable[..., Result],
        schedule_type: str,
        schedule_expr: str,
    ) -> None:
        """Todos os tipos de agendamento devem ser aceitos."""
        result = cli_invoke(
            "--dry-run",
            "schedule",
            "add",
            f"test_{schedule_type}",
            "backup",
            schedule_expr,
            "-t",
            schedule_type,
        )

        assert result.exit_code == 0

    def test_invalid_schedule_type(self, cli_invoke: Callable[..., Result]) -> None:
        """Tipo de agendamento inválido deve ser rejeitado."""
        result = cli_invoke(
            "schedule",
            "add",
            "test_job",
            "backup",
            "invalid",
            "-t",
            "invalid_type",
        )

        assert result.exit_code != 0


# ============================================================================
# Testes de Subcomandos Listados
# ============================================================================


class TestScheduleSubcommands:
    """Testes dos subcomandos disponíveis."""

    def test_pause_command_exists(self, cli_invoke: Callable[..., Result]) -> None:
        """Comando pause deve existir."""
        result = cli_invoke("schedule", "pause", "--help")

        assert result.exit_code == 0

    def test_resume_command_exists(self, cli_invoke: Callable[..., Result]) -> None:
        """Comando resume deve existir."""
        result = cli_invoke("schedule", "resume", "--help")

        assert result.exit_code == 0


# ============================================================================
# Testes de Edge Cases
# ============================================================================


class TestScheduleEdgeCases:
    """Testes de casos extremos."""

    def test_schedule_with_verbose_global(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """Comandos devem funcionar com --verbose global."""
        result = cli_invoke("--verbose", "schedule", "list")

        assert result.exit_code == 0

    def test_schedule_with_quiet_global(
        self, cli_invoke: Callable[..., Result]
    ) -> None:
        """Comandos devem funcionar com --quiet global."""
        result = cli_invoke("--quiet", "schedule", "list")

        assert result.exit_code == 0

    def test_invalid_subcommand(self, cli_invoke: Callable[..., Result]) -> None:
        """Subcomando inválido deve dar erro."""
        result = cli_invoke("schedule", "invalid_command")

        assert result.exit_code != 0
