"""Linha de comando do Agente.

Nao e o caminho do cliente: quem instala o Agente vai fazer isso por um
instalador guiado (G.8), que chama exatamente estes comandos por baixo. Ela
existe porque o instalador precisa de algo para chamar, e porque quem opera
servidor precisa de um jeito de conferir o estado sem abrir a interface.

`parear` e o unico que muda alguma coisa. `estado` so mostra — e mostra
inclusive o que esta ruim, como a chave guardada em arquivo em vez do cofre do
sistema.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from . import identidade as ident
from . import pareamento, raizes
from .config import Local

_SAIDA_PROBLEMA = 1


def _local(pasta: Path | None) -> tuple[Local, ident.Guarda]:
    destino = pasta or ident.pasta_padrao()
    return Local(pasta=destino), ident.Guarda(destino)


@click.group()
@click.version_option(pareamento.VERSAO, prog_name="autotarefas-agente")
def cli() -> None:
    """Agente do AutoTarefas: executa backup nesta maquina."""


@cli.command(name="parear")
@click.option(
    "--servidor", required=True, help="Endereco do Live (ex.: https://live.suaempresa.com.br)."
)
@click.option("--codigo", required=True, help="Codigo de pareamento gerado no Live.")
@click.option("--nome", default="", help="Nome desta maquina na tela de dispositivos.")
@click.option(
    "--pasta-de-configuracao",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Onde guardar a configuracao. Padrao: pasta do sistema.",
)
def parear(servidor: str, codigo: str, nome: str, pasta_de_configuracao: Path | None) -> None:
    """Registra esta maquina numa organizacao, com um codigo temporario."""
    local, guarda = _local(pasta_de_configuracao)
    try:
        resultado = pareamento.parear(
            servidor=servidor, codigo=codigo, guarda=guarda, local=local, nome=nome
        )
    except pareamento.PareamentoFalhou as erro:
        click.echo(f"[ERRO] {erro}", err=True)
        sys.exit(_SAIDA_PROBLEMA)

    click.echo("Dispositivo pareado.")
    click.echo(f"  Nome:      {resultado.nome}")
    click.echo(f"  Impressao: {resultado.impressao}")
    click.echo("")
    click.echo("Confira se esta impressao e a mesma que aparece no Live.")
    click.echo("Nenhuma pasta esta autorizada ainda: autorize pelo Agente, nesta maquina.")


@cli.command(name="autorizar")
@click.argument("pasta", type=click.Path(path_type=Path))
@click.option(
    "--pasta-de-configuracao",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
def autorizar(pasta: Path, pasta_de_configuracao: Path | None) -> None:
    """
    Autoriza o Agente a ler uma pasta DESTA maquina.

    So funciona aqui, no computador. Nao ha comando remoto que autorize pasta:
    se houvesse, comprometer a conta do Live — ou o servidor — daria acesso a
    qualquer arquivo de qualquer maquina da frota.
    """
    local, _ = _local(pasta_de_configuracao)
    try:
        configuracao = raizes.autorizar(local, pasta)
    except raizes.AutorizacaoRecusada as erro:
        click.echo(f"[ERRO] {erro}", err=True)
        sys.exit(_SAIDA_PROBLEMA)

    click.echo(f"Autorizada: {pasta.resolve()}")
    click.echo(f"Pastas autorizadas agora: {len(configuracao.raizes)}")


@cli.command(name="revogar-pasta")
@click.argument("pasta", type=click.Path(path_type=Path))
@click.option(
    "--pasta-de-configuracao",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
def revogar_pasta(pasta: Path, pasta_de_configuracao: Path | None) -> None:
    """Tira a autorizacao de uma pasta."""
    local, _ = _local(pasta_de_configuracao)
    configuracao = raizes.revogar(local, pasta)

    click.echo(f"Revogada: {pasta}")
    if not configuracao.raizes:
        click.echo("Nenhuma pasta autorizada: este dispositivo nao copiaria nada.")


@cli.command(name="estado")
@click.option(
    "--pasta-de-configuracao",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
def estado(pasta_de_configuracao: Path | None) -> None:
    """Mostra o que este dispositivo sabe sobre si mesmo."""
    local, guarda = _local(pasta_de_configuracao)
    configuracao = local.carregar()

    click.echo(f"Configuracao:   {local.arquivo}")
    click.echo(f"Servidor:       {configuracao.servidor or '(nao pareado)'}")
    click.echo(f"Dispositivo:    {configuracao.dispositivo_id or '(nao pareado)'}")
    click.echo(f"Chave privada:  {guarda.onde_guarda()}")

    try:
        click.echo(f"Impressao:      {ident.carregar(guarda).impressao}")
    except ident.SemIdentidade:
        click.echo("Impressao:      (sem identidade nesta maquina)")

    if configuracao.raizes:
        click.echo(f"Pastas autorizadas ({len(configuracao.raizes)}):")
        for raiz in configuracao.raizes:
            click.echo(f"  - {raiz}")
    else:
        # Dito em voz alta: um Agente pareado sem pasta autorizada nao copia
        # nada, e isso e facil de confundir com "esta funcionando".
        click.echo("Pastas autorizadas: NENHUMA - este dispositivo nao copiaria nada.")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
