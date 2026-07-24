"""
Comando ``perfis``: lista, mostra e exporta perfis embutidos.

    autotarefas perfis listar
    autotarefas perfis ver cadastro_contatos
    autotarefas perfis exportar cadastro_contatos --planilha minha.xlsx --out schema.yaml

O fluxo e EXPORT-ONLY: o perfil gera um schema que o usuario revisa e usa no
`validate`. Nada aqui abre a planilha para validar — `--planilha` so serve
para LISTAR as colunas reais e ajudar o mapeamento, sem adivinhar nada.
"""

from __future__ import annotations

from pathlib import Path

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.profiles import (
    ProfileError,
    export_schema,
    list_profiles,
    load_profile,
)
from autotarefas.profiles.export import (
    MappingError,
    available_columns_lines,
    render_mapping,
)

_EXIT_USAGE = 2
_EXIT_FAILURE = 1


@click.group(name="perfis")
def perfis() -> None:
    """Perfis de validacao prontos, para gerar schemas sem escrever YAML do zero."""


@perfis.command(name="listar")
@click.pass_obj
def listar(ctx: CLIContext) -> None:
    """Lista os perfis disponiveis."""
    console = Console(ctx)
    ids = list_profiles()
    if not ids:
        console.warning("Nenhum perfil disponivel.")
        return

    console.info("Perfis disponiveis:")
    for pid in ids:
        try:
            perfil = load_profile(pid)
            console.info(f"  {pid}  —  {perfil.title}")
        except ProfileError:
            console.info(f"  {pid}")
    console.info("")
    console.info("Veja um perfil:   autotarefas perfis ver NOME")
    console.info("Gere um schema:   autotarefas perfis exportar NOME --out schema.yaml")


@perfis.command(name="ver")
@click.argument("profile_id")
@click.pass_obj
def ver(ctx: CLIContext, profile_id: str) -> None:
    """Mostra as regras de um perfil, antes de aplicar."""
    console = Console(ctx)
    try:
        perfil = load_profile(profile_id)
    except ProfileError as exc:
        console.error(str(exc))
        raise click.exceptions.Exit(_EXIT_USAGE) from exc

    console.info(f"{perfil.id} (v{perfil.version}) — {perfil.title}")
    if perfil.summary:
        console.info("")
        console.info(perfil.summary.strip())
    console.info("")
    console.info("Campos:")
    for campo in perfil.concept_fields:
        ficha = perfil.fields.get(campo)
        marca = " (obrigatorio)" if campo in perfil.required_fields else ""
        doc = f" — {ficha.doc}" if ficha and ficha.doc else ""
        console.info(f"  {campo}{marca}{doc}")

    regras = perfil.profile_schema
    if regras.group_checks or regras.derived_checks:
        console.info("")
        console.info("Regras entre colunas:")
        for g in regras.group_checks:
            console.info(f"  [grupo] {g.name}: {', '.join(g.consistent)} coerentes por grupo")
        for d in regras.derived_checks:
            console.info(f"  [calculo] {d.name}: {d.target} = {d.expression}")

    console.info("")
    console.info(f"Gere o schema:  autotarefas perfis exportar {perfil.id} --out schema.yaml")


@perfis.command(name="exportar")
@click.argument("profile_id")
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="Onde gravar o schema gerado.",
)
@click.option(
    "--map",
    "mapeamentos",
    multiple=True,
    metavar="CAMPO=COLUNA",
    help='Mapeia um campo do perfil para uma coluna real. Ex.: --map email="E-mail".',
)
@click.option(
    "--planilha",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Planilha de referencia: lista as colunas reais para ajudar o mapeamento.",
)
@click.pass_obj
def exportar(
    ctx: CLIContext,
    profile_id: str,
    out: Path,
    mapeamentos: tuple[str, ...],
    planilha: Path | None,
) -> None:
    """Gera um schema a partir de um perfil, aplicando o mapeamento de colunas."""
    console = Console(ctx)

    try:
        perfil = load_profile(profile_id)
    except ProfileError as exc:
        console.error(str(exc))
        raise click.exceptions.Exit(_EXIT_USAGE) from exc

    mapping = _parse_mapping(mapeamentos, console)

    # As colunas reais servem para CONFERIR o mapeamento (a coluna existe?) e
    # para listar o que ha no arquivo. Nunca para parear com os campos: parear
    # seria palpite.
    colunas_reais = _ler_colunas(planilha, console) if planilha is not None else None
    if colunas_reais:
        for linha in available_columns_lines(colunas_reais):
            console.info(linha)
        console.info("")

    # O export resolve o mapeamento UMA vez. O resumo abaixo e renderizado a
    # partir desse mesmo resultado — nao existe segunda fonte de verdade.
    try:
        resultado = export_schema(perfil, mapping, available_columns=colunas_reais)
    except MappingError as exc:
        console.error(str(exc))
        raise click.exceptions.Exit(_EXIT_USAGE) from exc

    for linha in render_mapping(resultado):
        console.info(linha)
    console.info("")

    destino = _resolve_out(out, planilha, console)

    if ctx.dry_run:
        estado = "pronto" if resultado.is_complete else "TEMPLATE (a completar)"
        console.warning(f"[DRY-RUN] Geraria o schema ({estado}) em: {destino}")
        return

    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(resultado.yaml_text, encoding="utf-8")
    except OSError as exc:
        console.error(f"Erro ao gravar: {exc}")
        raise click.exceptions.Exit(_EXIT_FAILURE) from exc

    if resultado.is_complete:
        console.success(f"Schema pronto: {destino}")
        console.info(f"  Use: autotarefas validate SUA_PLANILHA --schema {destino}")
    else:
        console.warning(f"Template gerado (ainda NAO esta pronto): {destino}")
        console.info(
            f"  Falta mapear: {', '.join(resultado.unmapped_required)}. "
            "Troque os marcadores PREENCHA_ no arquivo antes de validar."
        )


def _parse_mapping(entradas: tuple[str, ...], console: Console) -> dict[str, str]:
    """
    Converte `--map CAMPO=COLUNA` em dict.

    Aqui so trata a SINTAXE da opcao. Se o campo existe no perfil, se a coluna
    existe no arquivo e se dois campos colidem no mesmo destino sao perguntas
    de `resolve_mapping` — que e quem resolve o mapeamento de verdade. Validar
    nos dois lugares seria criar de novo duas fontes de verdade.

    Um `--map` repetido para o mesmo campo e recusado: silenciosamente ficar
    com o ultimo esconderia um erro de digitacao.
    """
    mapping: dict[str, str] = {}
    for entrada in entradas:
        if "=" not in entrada:
            console.error(f"--map invalido: {entrada!r}. Use CAMPO=COLUNA.")
            raise click.exceptions.Exit(_EXIT_USAGE)
        campo, _, coluna = entrada.partition("=")
        campo, coluna = campo.strip(), coluna.strip()
        if campo in mapping:
            console.error(
                f"o campo '{campo}' foi mapeado mais de uma vez ('{mapping[campo]}' e '{coluna}')."
            )
            raise click.exceptions.Exit(_EXIT_USAGE)
        mapping[campo] = coluna
    return mapping


def _ler_colunas(planilha: Path, console: Console) -> list[str] | None:
    """Le as colunas reais da planilha pelo reader. None se nao der para ler."""
    from autotarefas.reader import read_workbook

    leitura = read_workbook(planilha)
    if not leitura.ok or leitura.normalized_dataframe is None:
        console.warning(
            f"Nao consegui ler as colunas de '{planilha.name}' "
            "(a planilha pode nao ter uma tabela clara). Seguindo sem conferir os nomes."
        )
        return None
    return [str(c) for c in leitura.normalized_dataframe.columns]


def _resolve_out(out: Path, planilha: Path | None, console: Console) -> Path:
    """Guardas de caminho: nunca sobrescreve a planilha; avisa se ja existe."""
    if planilha is not None and out.resolve() == planilha.resolve():
        console.error("O schema nao pode sobrescrever a planilha de entrada.")
        raise click.exceptions.Exit(_EXIT_USAGE)
    if out.exists():
        console.warning(f"Sobrescrevendo arquivo existente: {out}")
    return out


__all__ = ["perfis"]
