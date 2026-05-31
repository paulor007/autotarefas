"""
Console wrapper do AutoTarefas (baseado em Rich).

Fornece uma interface de output **com cores** pra UX da CLI, respeitando
``CLIContext`` (``--verbose``, ``--quiet``).

**Diferença entre `Console` e `logger`**:

- ``logger`` (loguru) — logs estruturados pra arquivo + console com
  timestamps e mascaramento de dados sensíveis. Pra registro.
- ``Console`` (rich) — UX limpa pro usuário, com cores e símbolos.
  Pra interação.

Uso:
    from autotarefas.cli.console import Console
    from autotarefas.cli.context import CLIContext

    ctx = CLIContext(verbose=0, quiet=0)
    console = Console(ctx)

    console.info("Processando...")
    console.success("Concluido!")
    console.warning("Atencao: arquivo grande")
    console.error("Erro fatal")
    console.debug("Detalhe interno")  # só com -vv
"""

from __future__ import annotations

from rich.console import Console as RichConsole

from autotarefas.cli.context import CLIContext


class Console:
    """
    Console UX do AutoTarefas.

    Respeita os flags ``--verbose`` e ``--quiet`` do ``CLIContext``:

    | Método | Aparece com... |
    |---|---|
    | ``error()`` | sempre (até com -qq) |
    | ``warning()`` | normal ou -q (suprime com -qq) |
    | ``info()`` / ``success()`` | normal (suprime com -q ou -qq) |
    | ``debug()`` | só com -vv ou mais |
    """

    def __init__(self, ctx: CLIContext | None = None) -> None:
        """
        Inicializa Console.

        Args:
            ctx: Contexto da CLI. Se None, usa defaults (sem quiet/verbose).
        """
        self._ctx = ctx if ctx is not None else CLIContext()
        self._out = RichConsole()
        self._err = RichConsole(stderr=True)

    def info(self, msg: str) -> None:
        """Mensagem informativa normal (suprime com -q ou -qq)."""
        if self._ctx.quiet >= 1:
            return
        self._out.print(msg)

    def success(self, msg: str) -> None:
        """Mensagem de sucesso em verde (suprime com -q ou -qq)."""
        if self._ctx.quiet >= 1:
            return
        self._out.print(f"[green][OK][/green] {msg}")

    def warning(self, msg: str) -> None:
        """Mensagem de aviso em amarelo (suprime com -qq)."""
        if self._ctx.quiet >= 2:  # noqa: PLR2004
            return
        self._out.print(f"[yellow][AVISO][/yellow] {msg}")

    def error(self, msg: str) -> None:
        """Mensagem de erro em vermelho (sempre aparece, vai pro stderr)."""
        self._err.print(f"[red][ERRO][/red] {msg}")

    def debug(self, msg: str) -> None:
        """Mensagem de debug em cinza (só com -vv ou mais)."""
        if self._ctx.verbose < 2:  # noqa: PLR2004
            return
        self._out.print(f"[dim][DEBUG][/dim] {msg}")

    def announce_action(self, action: str) -> None:
        """
        Anuncia uma ação com prefixo ``[DRY-RUN]`` se aplicável.

        Args:
            action: Descrição da ação (ex: "Deletando 42 arquivos").
        """
        if self._ctx.dry_run:
            self.warning(f"[DRY-RUN] {action} (nao executado)")
        else:
            self.info(action)


__all__ = ["Console"]
