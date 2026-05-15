"""
Helpers de confirmação para a CLI.

Funções utilitárias usadas pelos comandos:

- ``confirm()`` — confirmação simples sim/não
- ``confirm_bulk()`` — confirmação em massa que exige escrita explícita do
  número (Princípio de Segurança 1.6)

Princípio de Segurança 1.6 (Confirmação contextualizada):

    > "Operações em massa exigem que o usuário digite o número exato de
    > itens afetados antes de prosseguir. Isso evita o reflexo de 'sim,
    > sim, sim' automático que leva a deletes acidentais."

Uso:
    from autotarefas.cli.helpers import confirm, confirm_bulk

    # Confirmação simples
    if confirm("Continuar?", yes=ctx.yes):
        do_stuff()

    # Confirmação em massa (Princípio 1.6)
    if confirm_bulk("deletar arquivos antigos", count=42, yes=ctx.yes):
        delete_files()
"""

from __future__ import annotations

import click


def confirm(prompt: str, *, yes: bool = False, default: bool = False) -> bool:
    """
    Confirmação simples sim/não.

    Args:
        prompt: Pergunta a fazer ao usuário.
        yes: Se True (flag --yes), pula a pergunta e retorna True.
        default: Resposta default se usuário só apertar Enter.

    Returns:
        True se confirmado, False caso contrário.
    """
    if yes:
        return True
    # bool() explícito: click.confirm é tipado como Any nos stubs,
    # mypy strict rejeita "retornar Any onde se promete bool"
    return bool(click.confirm(prompt, default=default))


def confirm_bulk(action: str, count: int, *, yes: bool = False) -> bool:
    """
    Confirmação para operações em massa (Princípio de Segurança 1.6).

    **Exige que o usuário ESCREVA o número exato de itens** afetados.
    Evita o reflexo "sim/sim/sim" que leva a perdas acidentais.

    Args:
        action: Descrição da ação (ex: "deletar arquivos antigos").
        count: Número de itens afetados.
        yes: Se True (flag --yes), pula a confirmação e retorna True.

    Returns:
        True se o usuário digitou o número correto, False caso contrário.

    Example:
        if confirm_bulk("deletar logs antigos", count=42):
            delete_old_logs()
    """
    if yes:
        return True

    click.echo("")
    click.echo(f"[ATENCAO] Voce esta prestes a: {action}")
    click.echo(f"[ATENCAO] Itens afetados:      {count}")

    try:
        answer = click.prompt(
            f"Digite o numero {count} para confirmar",
            default="",
            show_default=False,
        )
    except click.Abort:
        return False

    return str(answer).strip() == str(count)


__all__ = ["confirm", "confirm_bulk"]
