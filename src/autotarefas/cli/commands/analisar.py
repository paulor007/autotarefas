"""
Comando ``analisar``: diagnostica uma planilha SEM schema.

    arquivo -> read_workbook -> WorkbookReadResult
                             -> profile_workbook -> ProfileResult
                             -> resumo no terminal + analise_report.json

E o primeiro comando do novo produto: o usuario manda a planilha DELE —
de vendas, de estoque, de pessoal, de qualquer coisa — e recebe um
diagnostico da estrutura e da qualidade dos dados. Sem configurar nada.

O comando nao conhece nenhuma coluna: tudo o que ele imprime e montado a
partir do ProfileResult. Uma planilha com colunas que o AutoTarefas nunca
viu funciona igual.

O ``validate`` continua existindo e inalterado.

Uso:
    autotarefas analisar planilha.xlsx
    autotarefas analisar planilha.xlsx --out-dir resultado/
    autotarefas analisar planilha.xlsx --sheet "Dados" --header-row 4
    autotarefas analisar dados.csv --preview 10
"""

from __future__ import annotations

from pathlib import Path

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.profiling import profile_workbook
from autotarefas.profiling.report import (
    JSON_REPORT_NAME,
    build_report,
    generate_preview,
    generate_rejection,
    generate_summary,
    write_json_report,
)
from autotarefas.reader import ReaderError, read_workbook

#: Exit codes — mesma convencao dos demais comandos (extract, sync, send).
_EXIT_FAILURE = 1
_EXIT_USAGE = 2

#: Extensoes que o leitor aceita.
_SUPPORTED = (".csv", ".xlsx", ".xlsm")
_DEFAULT_PREVIEW = 5


@click.command(name="analisar")
@click.argument(
    "arquivo",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
)
@click.option(
    "--out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=f"Diretorio de saida do relatorio ({JSON_REPORT_NAME}).",
)
@click.option(
    "--json",
    "json_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Caminho exato do relatorio JSON (alternativa ao --out-dir).",
)
@click.option(
    "--sheet",
    type=str,
    default=None,
    help="Aba a analisar. Sem isto, o AutoTarefas escolhe a que parece uma tabela.",
)
@click.option(
    "--header-row",
    type=click.IntRange(min=1),
    default=None,
    help="Linha do cabecalho (a mesma numeracao do Excel). Sem isto, e detectada.",
)
@click.option(
    "--preview",
    type=click.IntRange(min=0),
    default=_DEFAULT_PREVIEW,
    show_default=True,
    help="Quantas linhas mostrar na previa (0 desliga).",
)
@click.option(
    "--strict-warnings",
    is_flag=True,
    default=False,
    help="Trata avisos como falha (exit 1). Util em pipeline.",
)
@click.pass_obj
def analisar(
    ctx: CLIContext,
    arquivo: Path,
    out_dir: Path | None,
    json_path: Path | None,
    sheet: str | None,
    header_row: int | None,
    preview: int,
    strict_warnings: bool,
) -> None:
    """Analisa uma planilha (CSV/XLSX) e descreve a estrutura e a qualidade dos dados."""
    console = Console(ctx)

    _check_extension(arquivo, console)

    # ------------------------------------------------------------------
    # 1. Leitura (a CLI NAO abre a planilha: quem le e o reader)
    # ------------------------------------------------------------------
    try:
        leitura = read_workbook(arquivo, sheet=sheet, header_row=header_row)
    except ReaderError as exc:
        console.error(f"Nao foi possivel ler o arquivo: {exc}")
        raise click.exceptions.Exit(_EXIT_USAGE) from exc

    # ------------------------------------------------------------------
    # 2. Recusa: NAO perfila, NAO inventa metrica, NAO gera relatorio de sucesso
    # ------------------------------------------------------------------
    if not leitura.ok:
        console.error("O arquivo nao parece conter uma tabela identificavel.")
        console.info("")
        console.info(generate_rejection(leitura))
        console.info("")
        console.info(
            "O AutoTarefas trabalha com CSV/XLSX que tenham uma linha de cabecalho "
            "e registros organizados em linhas."
        )
        raise click.exceptions.Exit(_EXIT_USAGE)

    # ------------------------------------------------------------------
    # 3. Perfilagem
    # ------------------------------------------------------------------
    perfil = profile_workbook(leitura)

    if preview:
        console.info("Previa (como o AutoTarefas interpretou):")
        console.info(generate_preview(leitura, preview))
        console.info("")

    console.info(generate_summary(leitura, perfil))
    console.info("")

    # ------------------------------------------------------------------
    # 4. Relatorio
    # ------------------------------------------------------------------
    destino = _report_path(arquivo, out_dir, json_path, console)
    if destino is not None:
        if ctx.dry_run:
            console.warning(f"[DRY-RUN] Geraria o relatorio em: {destino}")
        else:
            try:
                escrito = write_json_report(build_report(leitura, perfil), destino)
                console.success(f"Relatorio: {escrito}")
            except OSError as exc:
                console.error(f"Erro ao gravar o relatorio: {exc}")
                raise click.exceptions.Exit(_EXIT_FAILURE) from exc

    # ------------------------------------------------------------------
    # 5. Status final
    # ------------------------------------------------------------------
    problemas = perfil.by_severity("problema")
    avisos = perfil.by_severity("aviso")

    if problemas:
        console.error(f"Analise concluida com {len(problemas)} problema(s) observado(s).")
        raise click.exceptions.Exit(_EXIT_FAILURE)

    if avisos:
        if strict_warnings:
            console.error(f"Analise falhou: {len(avisos)} aviso(s) (--strict-warnings ativo).")
            raise click.exceptions.Exit(_EXIT_FAILURE)
        console.warning(f"Analise concluida com {len(avisos)} aviso(s) — nada foi alterado.")
        return  # exit 0

    console.success("Analise concluida.")


def _check_extension(arquivo: Path, console: Console) -> None:
    """Extensao aceita? O .xls antigo ganha mensagem propria."""
    sufixo = arquivo.suffix.lower()
    if sufixo in _SUPPORTED:
        return

    if sufixo == ".xls":
        console.error(
            "O formato .xls (Excel antigo) nao e suportado. Abra no Excel e salve como .xlsx."
        )
    else:
        aceitas = ", ".join(_SUPPORTED)
        console.error(f"Extensao nao suportada: {sufixo or '(sem extensao)'}. Use: {aceitas}")
    raise click.exceptions.Exit(_EXIT_USAGE)


def _report_path(
    arquivo: Path,
    out_dir: Path | None,
    json_path: Path | None,
    console: Console,
) -> Path | None:
    """
    Onde gravar o relatorio (ou None: so terminal).

    Duas guardas: nunca escrever por cima da planilha de entrada, e nunca
    sobrescrever um relatorio existente em silencio.
    """
    if out_dir is not None and json_path is not None:
        console.error("Use --out-dir OU --json, nao os dois.")
        raise click.exceptions.Exit(_EXIT_USAGE)

    destino = (
        json_path
        if json_path is not None
        else (out_dir / JSON_REPORT_NAME if out_dir is not None else None)
    )
    if destino is None:
        return None

    if destino.resolve() == arquivo.resolve():
        console.error("O relatorio nao pode sobrescrever a planilha de entrada.")
        raise click.exceptions.Exit(_EXIT_USAGE)

    if destino.exists():
        console.warning(f"Sobrescrevendo o relatorio existente: {destino}")

    return destino


__all__ = ["analisar"]
