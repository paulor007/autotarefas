"""
Comando ``cofre``: gera e confere a chave mestra da plataforma.

A chave mestra protege os segredos guardados pelo AutoTarefas — a chave de
assinatura do manifesto, a senha de criptografia, as credenciais de destino.
Ela **nunca** e gravada pelo produto: quem a guarda e voce, no ambiente do
servidor ou no cofre do sistema operacional.

Uso:
    # Gera uma chave nova para colar na configuracao do servidor
    autotarefas cofre nova-chave

    # Confere se a chave configurada esta valida
    autotarefas cofre conferir
"""

from __future__ import annotations

import base64
import os
import secrets

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext

#: Mesma variavel que o servidor le. Repetida aqui de proposito: a CLI nao
#: importa o backend, para continuar funcionando numa maquina que so tem o
#: nucleo instalado — o Agente, por exemplo.
VAR_CHAVE = "AUTOTAREFAS_MASTER_KEY"  # nosec B105 — nome da variavel, nao valor

#: AES-256 pede 32 bytes.
TAMANHO_CHAVE = 32

_EXIT_PROBLEMA = 1


@click.group(name="cofre")
def cofre() -> None:
    """Chave mestra que protege os segredos da plataforma."""


@cofre.command(name="nova-chave")
@click.pass_obj
def nova_chave(ctx: CLIContext) -> None:
    """
    Sorteia uma chave mestra nova.

    A chave e impressa uma vez so e nao fica gravada em lugar nenhum. Guarde-a
    antes de fechar o terminal: sem ela, os segredos ja cifrados nao abrem
    mais — e isso e proposital, nao um defeito.
    """
    console = Console(ctx)
    chave = base64.urlsafe_b64encode(secrets.token_bytes(TAMANHO_CHAVE)).decode("ascii")

    console.info("Chave mestra nova (guarde agora; ela nao sera mostrada de novo):")
    console.info("")
    console.info(f"  {VAR_CHAVE}={chave}")
    console.info("")
    console.warning("Sem esta chave, os segredos ja guardados NAO poderao ser abertos.")
    console.info("Defina a variavel no servidor, ou guarde-a no cofre do sistema.")


@cofre.command(name="conferir")
@click.pass_obj
def conferir(ctx: CLIContext) -> None:
    """
    Diz se a chave configurada serve, sem mostra-la.

    Saida 0 = chave valida. Saida 1 = ausente ou malformada.
    """
    console = Console(ctx)
    bruta = os.environ.get(VAR_CHAVE, "").strip()

    if not bruta:
        console.error(f"{VAR_CHAVE} nao esta definida: o cofre esta trancado.")
        console.info("Gere uma com: autotarefas cofre nova-chave")
        raise click.exceptions.Exit(_EXIT_PROBLEMA)

    try:
        chave = base64.urlsafe_b64decode(bruta.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        console.error(f"{VAR_CHAVE} nao esta em base64 urlsafe.")
        raise click.exceptions.Exit(_EXIT_PROBLEMA) from None

    if len(chave) != TAMANHO_CHAVE:
        console.error(f"{VAR_CHAVE} tem {len(chave)} bytes; precisa de {TAMANHO_CHAVE}.")
        raise click.exceptions.Exit(_EXIT_PROBLEMA)

    console.success("Chave mestra valida. O cofre pode abrir e guardar segredos.")


__all__ = ["cofre"]
