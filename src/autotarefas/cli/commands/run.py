"""
Comando ``run``: a operacao inteira em um arquivo (RF-CORE-006 / RF-REC-004).

A conferencia mensal e sempre a mesma sequencia com os mesmos parametros.
Este comando le essa sequencia de um YAML e executa na ordem — sem
redigitar nada, e sem nenhuma credencial dentro do arquivo.

Uso:
    autotarefas run fluxo.yaml
    autotarefas run fluxo.yaml --out-dir saida/     # vence o out_dir do arquivo
    autotarefas --dry-run run fluxo.yaml            # confere sem gravar
    autotarefas run fluxo.yaml --listar             # so mostra os passos

Formato:
    nome: Conferencia mensal
    out_dir: saida
    passos:
      - tipo: comparar
        a: sistema.xlsx
        b: planilha.xlsx
        chave: [codigo]
        tolerancia: ["valor=0,01"]

Caminhos relativos sao resolvidos a partir da pasta do proprio arquivo de
fluxo, para que o mesmo YAML funcione de qualquer diretorio.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.markup import escape

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.core.exceptions import ConfigError
from autotarefas.flow import describe_flow, load_flow, run_flow

_EXIT_USAGE = 2


@click.command(name="run")
@click.argument(
    "fluxo",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
)
@click.option(
    "--out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Diretorio de saida (vence o 'out_dir' do arquivo). Cada passo grava em sua pasta.",
)
@click.option(
    "--listar",
    is_flag=True,
    default=False,
    help="So mostra os passos declarados, sem executar.",
)
@click.pass_obj
def run(ctx: CLIContext, fluxo: Path, out_dir: Path | None, listar: bool) -> None:
    """Executa um fluxo declarado em YAML (analise, comparacao, conciliacao...)."""
    console = Console(ctx)

    try:
        config = load_flow(fluxo)
    except ConfigError as exc:
        console.error(str(exc))
        raise click.exceptions.Exit(_EXIT_USAGE) from exc

    console.info(escape(describe_flow(config)))
    console.info("")
    if listar:
        return

    resultado = run_flow(
        config,
        base_dir=fluxo.parent,
        out_dir=out_dir,
        dry_run=ctx.dry_run,
    )

    for aviso in resultado.warnings:
        console.warning(aviso)

    for passo in resultado.steps:
        titulo = f"[{passo.index}/{len(config.passos)}] {passo.name}"
        if not passo.ok:
            console.error(f"{titulo}: {passo.error}")
            continue
        console.success(titulo)
        if passo.summary:
            console.info(escape(passo.summary))
        for artefato in passo.artifacts:
            console.info(f"  artefato: {artefato}")
        console.info("")

    contagem = resultado.counts
    if resultado.ok and contagem["passos"] == len(config.passos):
        console.success(f"Fluxo concluido: {contagem['concluidos']} passo(s).")
        return

    console.error(
        f"Fluxo interrompido no passo {contagem['concluidos'] + 1}: "
        f"{contagem['concluidos']} de {len(config.passos)} concluido(s)."
    )
    raise click.exceptions.Exit(1)


__all__ = ["run"]
