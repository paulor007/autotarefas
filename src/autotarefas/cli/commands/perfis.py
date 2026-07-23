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
    Profile,
    ProfileError,
    export_schema,
    list_profiles,
    load_profile,
)
from autotarefas.profiles.export import columns_hint

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

    mapping = _parse_mapping(mapeamentos, perfil.concept_fields, console)

    if planilha is not None:
        _mostrar_colunas(perfil, planilha, console)

    resultado = export_schema(perfil, mapping)

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
        if resultado.unmapped_optional:
            console.info(
                f"  (campos opcionais nao usados: {', '.join(resultado.unmapped_optional)})"
            )
        console.info(f"  Use: autotarefas validate SUA_PLANILHA --schema {destino}")
    else:
        console.warning(f"Template gerado (ainda NAO esta pronto): {destino}")
        console.info(
            f"  Falta mapear: {', '.join(resultado.unmapped_required)}. "
            "Troque os marcadores PREENCHA_ no arquivo antes de validar."
        )


def _parse_mapping(
    entradas: tuple[str, ...], campos_validos: tuple[str, ...], console: Console
) -> dict[str, str]:
    """Converte --map CAMPO=COLUNA em dict, recusando campos que o perfil nao tem."""
    mapping: dict[str, str] = {}
    for entrada in entradas:
        if "=" not in entrada:
            console.error(f"--map invalido: {entrada!r}. Use CAMPO=COLUNA.")
            raise click.exceptions.Exit(_EXIT_USAGE)
        campo, _, coluna = entrada.partition("=")
        campo, coluna = campo.strip(), coluna.strip()
        if campo not in campos_validos:
            disponiveis = ", ".join(campos_validos)
            console.error(f"o perfil nao tem o campo '{campo}'. Campos: {disponiveis}")
            raise click.exceptions.Exit(_EXIT_USAGE)
        if not coluna:
            console.error(f"--map {campo}= veio sem o nome da coluna.")
            raise click.exceptions.Exit(_EXIT_USAGE)
        mapping[campo] = coluna
    return mapping


def _mostrar_colunas(perfil: Profile, planilha: Path, console: Console) -> None:
    """Le a planilha pelo reader e lista as colunas reais — sem adivinhar o mapa."""
    from autotarefas.reader import read_workbook

    leitura = read_workbook(planilha)
    if not leitura.ok or leitura.normalized_dataframe is None:
        console.warning(
            f"Nao consegui ler as colunas de '{planilha.name}' "
            "(a planilha pode nao ter uma tabela clara). Mapeie manualmente."
        )
        return

    colunas = [str(c) for c in leitura.normalized_dataframe.columns]
    console.info("")
    for linha in columns_hint(perfil, colunas):
        console.info(linha)
    console.info("")


def _resolve_out(out: Path, planilha: Path | None, console: Console) -> Path:
    """Guardas de caminho: nunca sobrescreve a planilha; avisa se ja existe."""
    if planilha is not None and out.resolve() == planilha.resolve():
        console.error("O schema nao pode sobrescrever a planilha de entrada.")
        raise click.exceptions.Exit(_EXIT_USAGE)
    if out.exists():
        console.warning(f"Sobrescrevendo arquivo existente: {out}")
    return out


__all__ = ["perfis"]
