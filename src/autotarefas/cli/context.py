"""
Contexto global da CLI, passado entre comandos pelo Click.

O ``CLIContext`` carrega as opções globais (``--verbose``, ``--quiet``,
``--dry-run``, ``--yes``) e expõe propriedades derivadas como ``log_level``.

Uso:
    @cli.command()
    @click.pass_obj
    def meu_comando(ctx: CLIContext) -> None:
        if ctx.dry_run:
            click.echo("Modo simulação")
"""

from __future__ import annotations

import os
from dataclasses import dataclass

#: Variavel de ambiente que o AutoTarefas Live define antes de executar a CLI.
_VAR_INTERFACE = "AUTOTAREFAS_UI"


@dataclass
class CLIContext:
    """
    Contexto compartilhado entre comandos da CLI.

    Attributes:
        verbose: Nível de verbosidade (0=normal, 1=-v=INFO,
            2=-vv=DEBUG, 3=-vvv=TRACE).
        quiet: Nível de silêncio (0=normal, 1=-q=WARNING, 2=-qq=ERROR).
        dry_run: Se True, comandos simulam sem fazer mudanças reais.
        yes: Se True, assume "sim" em todas as confirmações.
    """

    verbose: int = 0
    quiet: int = 0
    dry_run: bool = False
    yes: bool = False

    @property
    def na_tela(self) -> bool:
        """
        Diz se a saida vai para uma TELA do produto, e nao para um terminal.

        O Live executa exatamente esta CLI e mostra o texto na interface. Duas
        coisas nao fazem sentido ali: mandar a pessoa digitar um comando (ela
        nao tem terminal) e avisar sobre o disco de destino (ela nao escolheu
        destino nenhum — enviou arquivos pelo navegador). Sem esta distincao,
        so restaria apagar as mensagens do nucleo, e ai quem usa a CLI de
        verdade, ou o agente instalado na maquina, perderia o aviso.
        """
        return os.environ.get(_VAR_INTERFACE, "").strip().lower() == "web"

    @property
    def log_level(self) -> str:
        """
        Determina o log level com base em ``verbose``/``quiet``.

        ``quiet`` tem **prioridade** sobre ``verbose`` (princípio do
        "menos surpresa" — se o usuário pediu silêncio explicitamente,
        respeitar).

        Mapeamento:
            -qq           → ERROR
            -q            → WARNING
            (nada/padrão) → INFO
            -v            → INFO (não muda — apenas confirma)
            -vv           → DEBUG
            -vvv ou +     → TRACE

        Returns:
            String do log level (compatível com loguru).
        """
        if self.quiet >= 2:  # noqa: PLR2004
            return "ERROR"
        if self.quiet == 1:
            return "WARNING"
        if self.verbose >= 3:  # noqa: PLR2004
            return "TRACE"
        if self.verbose == 2:  # noqa: PLR2004
            return "DEBUG"
        return "INFO"


__all__ = ["CLIContext"]
