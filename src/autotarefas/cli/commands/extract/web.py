"""
Subcomando `extract web`: extracao via web scraping (HTML).

Destino deste arquivo:
    src/autotarefas/cli/commands/extract/web.py
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.extract_web import ExtractWebTask

if TYPE_CHECKING:
    from autotarefas.cli.context import CLIContext

# Exit codes
_EXIT_USAGE = 2
_EXIT_FAILURE = 1

_SEP = "=" * 60


def _parse_fields(itens: tuple[str, ...]) -> dict[str, str]:
    """
    Converte ('nome=td.nome', 'preco=td.preco') em {coluna: seletor}.

    Levanta ValidationError se algum item nao estiver no formato 'k=v'.
    """
    fields: dict[str, str] = {}
    for item in itens:
        chave, sep, seletor = item.partition("=")
        chave = chave.strip()
        seletor = seletor.strip()
        if not sep or not chave or not seletor:
            msg = f"--field deve ser no formato coluna=seletor (recebi '{item}')"
            raise ValidationError(msg)
        fields[chave] = seletor
    return fields


@click.command(name="web")
@click.option(
    "--url",
    "-u",
    required=True,
    help="URL da pagina a raspar (http:// ou https://).",
)
@click.option(
    "--output",
    "-o",
    "output",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Arquivo de saida (.csv, .xlsx ou .json).",
)
@click.option(
    "--row-selector",
    "-r",
    required=True,
    help='Seletor CSS de cada linha/item (ex: "tr.produto").',
)
@click.option(
    "--field",
    "-f",
    "field",
    multiple=True,
    required=True,
    help="Coluna a extrair, no formato coluna=seletor. Repita por coluna "
    '(ex: -f "nome=td.nome" -f "preco=td.preco").',
)
@click.option(
    "--next-selector",
    "-n",
    default=None,
    help='Seletor CSS do link "proxima pagina" (ex: "a.next"). '
    "Sem ele, raspa so a primeira pagina.",
)
@click.option(
    "--max-pages",
    default=None,
    type=int,
    help="Limite de paginas a seguir (default: todas).",
)
@click.option(
    "--delay",
    default=0.0,
    type=float,
    show_default=True,
    help="Pausa entre paginas em segundos (rate limit).",
)
@click.option(
    "--timeout",
    default=30.0,
    type=float,
    show_default=True,
    help="Timeout por request em segundos.",
)
@click.option(
    "--max-retries",
    default=3,
    type=int,
    show_default=True,
    help="Tentativas por pagina em erro temporario.",
)
@click.pass_obj
def web_command(
    ctx: CLIContext,
    url: str,
    output: Path,
    row_selector: str,
    field: tuple[str, ...],
    next_selector: str | None,
    max_pages: int | None,
    delay: float,
    timeout: float,
    max_retries: int,
) -> None:
    """
    Extrai dados de uma pagina HTML por seletores CSS (web scraping).

    Percorre cada elemento que casa --row-selector e, dentro dele, pega o
    texto de cada --field. Se houver --next-selector, segue a paginacao.

    \b
    Exemplo:
      autotarefas extract web -u http://localhost:5555/catalogo -o produtos.csv \\
        -r "tr.produto" -f "nome=td.nome" -f "preco=td.preco" -n "a.next"
    """
    # Validacao de URL (erro de uso -> exit 2)
    if not url.startswith(("http://", "https://")):
        click.secho(
            "Erro: a URL deve comecar com http:// ou https://",
            fg="red",
            err=True,
        )
        raise SystemExit(_EXIT_USAGE)

    # Parse dos campos (erro de uso -> exit 2)
    try:
        fields = _parse_fields(field)
    except ValidationError as exc:
        click.secho(f"Erro: {exc}", fg="red", err=True)
        raise SystemExit(_EXIT_USAGE) from exc

    dry_run = bool(ctx.dry_run)

    # Header
    click.echo(_SEP)
    click.secho(" Extracao via Web (scraping)", bold=True)
    click.echo(_SEP)
    click.echo(f"URL:    {url}")
    click.echo(f"Saida:  {output}")
    click.echo(f"Linhas: {row_selector}  ({len(fields)} campos)")
    modo = "dry-run (preview, nao salva)" if dry_run else "normal"
    click.echo(f"Modo:   {modo}")
    click.echo("")

    def _on_progress(info: dict[str, object]) -> None:
        click.echo(
            f"  Pagina {info['page']} ... {info['page_count']} itens (total: {info['total']})",
        )

    # Cria a task (ValidationError -> exit 2)
    try:
        task = ExtractWebTask(
            url=url,
            output_path=output,
            row_selector=row_selector,
            fields=fields,
            next_selector=next_selector,
            max_pages=max_pages,
            delay_s=delay,
            timeout_s=timeout,
            max_retries=max_retries,
            on_progress=None if dry_run else _on_progress,
            dry_run=dry_run,
        )
    except ValidationError as exc:
        click.secho(f"Erro de configuracao: {exc}", fg="red", err=True)
        raise SystemExit(_EXIT_USAGE) from exc

    result = task.run()

    # Resultado
    click.echo("")
    click.echo(_SEP)

    if result.status == TaskStatus.SUCCESS:
        if dry_run:
            tem_proxima = "sim" if result.data.get("has_next") else "nao"
            click.secho(
                f"[dry-run] Extrairia ~{result.data.get('would_extract_first_page')} "
                f"itens na 1a pagina (tem proxima: {tem_proxima})",
                fg="cyan",
            )
        elif result.data.get("saved"):
            click.secho(
                f"Extraidos {result.rows_affected} itens -> {result.data.get('output_path')}",
                fg="green",
            )
        else:
            click.secho(
                "Nenhum item casou o seletor de linhas (nada salvo).",
                fg="yellow",
            )
        click.echo(_SEP)
        return

    # Failure -> exit 1
    click.secho(f"Falha: {result.error_message}", fg="red", err=True)
    click.echo(_SEP)
    raise SystemExit(_EXIT_FAILURE)


__all__ = ["web_command"]
