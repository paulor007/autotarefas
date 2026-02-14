"""
Ponto de entrada principal da CLI do AutoTarefas.

Este módulo define o grupo principal de comandos e configura
a interface de linha de comando usando Click e Rich.

Uso:
    $ autotarefas --help
    $ autotarefas --version
    $ autotarefas backup run /path/to/source
"""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autotarefas import __version__
from autotarefas.core.logger import configure_from_settings, logger

# Console global para output formatado (também disponível via ctx.obj["console"])
console = Console()

_COMMANDS_REGISTERED = False

# Configurações de contexto do Click
CONTEXT_SETTINGS: dict[str, object] = {
    "help_option_names": ["-h", "--help"],
    "max_content_width": 120,
}

# Metadados opcionais para deixar o help mais informativo
COMMAND_META: dict[str, dict[str, object]] = {
    "init": {
        "desc": "Inicializa configuração do AutoTarefas",
        "examples": ["autotarefas init"],
    },
    "backup": {
        "desc": "Gerencia backups de arquivos e diretórios",
        "examples": ["autotarefas backup run ~/Documents -d /backups"],
    },
    "clean": {
        "desc": "Limpa arquivos temporários e lixo",
        "examples": ["autotarefas clean run /tmp --profile temp_files"],
    },
    "organize": {
        "desc": "Organiza arquivos em pastas por tipo",
        "examples": ["autotarefas organize run ~/Downloads"],
    },
    "monitor": {
        "desc": "Monitora recursos do sistema",
        "examples": ["autotarefas monitor status --all"],
    },
    "report": {
        "desc": "Gera relatórios",
        "examples": ["autotarefas report sales --format html"],
    },
    "schedule": {
        "desc": "Gerencia agendamento de tarefas",
        "examples": ["autotarefas schedule list"],
    },
    "email": {
        "desc": "Gerencia emails e notificações",
        "examples": ["autotarefas email --help"],
    },
}


def _make_table(*, left_style: str = "green") -> Table:
    """
    Cria uma tabela simples (sem bordas) para o help.

    Args:
        left_style: estilo Rich da primeira coluna.

    Returns:
        Uma instância de Table configurada para o help.
    """
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style=left_style, no_wrap=True)
    table.add_column()
    return table


class RichGroup(click.Group):
    """
    Grupo Click customizado com formatação Rich.

    Sobrescreve a renderização do `--help` para exibir um painel e tabelas
    com comandos/opções de forma mais amigável.
    """

    def format_help(
        self, ctx: click.Context, _formatter: click.HelpFormatter
    ) -> None:  # noqa: ARG002
        """Renderiza o help usando Rich (painel + tabelas)."""
        console.print()
        console.print(
            Panel.fit(
                f"[bold blue]AutoTarefas[/] [dim]v{__version__}[/] - Sistema de Automação de Tarefas",
                border_style="blue",
            )
        )
        console.print()

        # Uso
        console.print("[bold]Uso:[/] autotarefas [OPTIONS] COMMAND [ARGS]...")
        console.print()

        # Opções globais
        console.print("[bold]Opções Globais:[/]")
        options = _make_table(left_style="cyan")
        options.add_row("-v, --verbose", "Modo verboso (mais detalhes no log)")
        options.add_row("-q, --quiet", "Modo silencioso (apenas erros)")
        options.add_row("--dry-run", "Simula execução sem fazer alterações")
        options.add_row("--version", "Mostra versão e sai")
        options.add_row("-h, --help", "Mostra esta mensagem e sai")
        console.print(options)
        console.print()

        # Comandos disponíveis (apenas os realmente registrados)
        console.print("[bold]Comandos disponíveis:[/]")
        cmd_table = _make_table(left_style="green")

        for cmd_name in sorted(self.list_commands(ctx)):
            cmd = self.get_command(ctx, cmd_name)
            if cmd is None:
                continue

            meta = COMMAND_META.get(cmd_name, {})
            desc = str(meta.get("desc") or cmd.get_short_help_str() or "")
            cmd_table.add_row(cmd_name, desc)

        console.print(cmd_table)
        console.print()

        # Exemplos (somente de comandos registrados)
        examples: list[str] = []
        for cmd_name in sorted(self.list_commands(ctx)):
            meta = COMMAND_META.get(cmd_name, {})
            exs = meta.get("examples") or []
            if isinstance(exs, list):
                examples.extend([str(x) for x in exs])

        if examples:
            console.print("[bold]Exemplos:[/]")
            for ex in examples:
                console.print(f"  {ex}")
            console.print()


def _print_version(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """
    Callback do Click para a opção `--version`.

    Mostra a versão e encerra a execução.
    """
    if not value or ctx.resilient_parsing:
        return

    console.print()
    console.print(
        Panel.fit(
            f"[bold blue]AutoTarefas[/] versão [green]{__version__}[/]",
            border_style="blue",
        )
    )
    console.print()
    ctx.exit()


def _setup_logging(*, verbose: bool, quiet: bool) -> None:
    """
    Configura logging baseado nas flags globais.

    Regras:
    - `--verbose` e `--quiet` juntos não são permitidos.
    - `configure_from_settings()` é chamado sempre (garante handlers).
    - `--quiet` desabilita logs do namespace `autotarefas`.
    """
    if verbose and quiet:
        raise click.UsageError("Você não pode usar --verbose e --quiet ao mesmo tempo.")

    configure_from_settings()

    if quiet:
        logger.disable("autotarefas")
    else:
        logger.enable("autotarefas")

    _ = verbose  # reservado para evoluções (nível/diagnóstico em runtime)


@click.group(cls=RichGroup, context_settings=CONTEXT_SETTINGS)
@click.option("-v", "--verbose", is_flag=True, default=False, help="Modo verboso")
@click.option("-q", "--quiet", is_flag=True, default=False, help="Modo silencioso")
@click.option(
    "--dry-run", is_flag=True, default=False, help="Simula execução sem alterar nada"
)
@click.option(
    "--version",
    is_flag=True,
    callback=_print_version,
    expose_value=False,
    is_eager=True,
    help="Mostra versão e sai",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool, dry_run: bool) -> None:
    """
    AutoTarefas - Sistema de Automação de Tarefas.

    Execute tarefas de backup, limpeza, monitoramento e mais
    de forma automatizada e confiável.
    """
    ctx.ensure_object(dict)

    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    ctx.obj["dry_run"] = dry_run
    ctx.obj["console"] = console

    _setup_logging(verbose=verbose, quiet=quiet)


def _register_commands() -> None:
    """
    Importa e registra comandos.

    Import dentro da função:
    - evita imports circulares
    - evita E402
    - centraliza registro

    Também protege contra registro duplicado.
    """
    global _COMMANDS_REGISTERED

    if _COMMANDS_REGISTERED:
        return

    from autotarefas.cli.commands.backup import backup as backup_cmd
    from autotarefas.cli.commands.cleaner import clean as clean_cmd
    from autotarefas.cli.commands.email import email as email_cmd
    from autotarefas.cli.commands.init import init as init_cmd
    from autotarefas.cli.commands.monitor import monitor as monitor_cmd
    from autotarefas.cli.commands.organizer import organize as organize_cmd
    from autotarefas.cli.commands.reporter import report as report_cmd
    from autotarefas.cli.commands.scheduler import schedule as schedule_cmd

    cli.add_command(init_cmd, name="init")
    cli.add_command(backup_cmd, name="backup")
    cli.add_command(clean_cmd, name="clean")
    cli.add_command(organize_cmd, name="organize")
    cli.add_command(monitor_cmd, name="monitor")
    cli.add_command(report_cmd, name="report")
    cli.add_command(schedule_cmd, name="schedule")
    cli.add_command(email_cmd, name="email")

    _COMMANDS_REGISTERED = True


_register_commands()


def main(argv: list[str] | None = None) -> int:
    """
    Função principal de entrada.

    Args:
        argv: lista de argumentos (sem o nome do programa). Se None, usa sys.argv[1:].

    Returns:
        Código de saída:
        - 0: sucesso
        - 1: erro geral
        - 2: erro de uso (parâmetros inválidos)
        - 130: interrompido (Ctrl+C)
    """
    args = argv if argv is not None else sys.argv[1:]

    try:
        cli.main(args=args, prog_name="autotarefas", standalone_mode=False)
        return 0

    except click.UsageError as e:
        console.print(f"\n[red]Erro de uso:[/] {e}")
        console.print("Use [bold]autotarefas --help[/] para ver os comandos e opções.")
        return 2

    except click.ClickException as e:
        e.show()
        return 1

    except click.Abort:
        console.print("\n[yellow]Operação cancelada pelo usuário.[/]")
        return 1

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrompido pelo usuário.[/]")
        return 130

    except Exception as e:  # noqa: BLE001
        console.print(f"\n[red]Erro inesperado:[/] {e}")
        logger.exception("Erro não tratado na CLI")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
