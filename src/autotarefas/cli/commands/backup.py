"""
Comando ``backup``: compacta arquivos/pastas em ZIP com hash SHA-256.

Uso:
    # Backup simples
    autotarefas backup pasta --output backup.zip

    # Multiplas fontes
    autotarefas backup pasta1 pasta2 arquivo.txt --output full.zip

    # Excludes adicionais
    autotarefas backup projeto --output proj.zip \\
        --exclude "*.log" --exclude "tmp/*"

    # Sem excludes padrao (inclui __pycache__, .git, etc)
    autotarefas backup projeto --output proj.zip --no-default-excludes

    # Modo simulacao (nao cria ZIP)
    autotarefas --dry-run backup projeto --output proj.zip
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.core.base import TaskStatus
from autotarefas.tasks.backup import BackupTask, rotate_backups, timestamped_name

# ============================================================
# Helpers de formatacao
# ============================================================

#: Quantos arquivos do preview mostrar em dry-run.
_DRY_RUN_PREVIEW_COUNT = 5

#: Quantos arquivos nao lidos listar antes de resumir.
_UNREADABLE_PREVIEW_COUNT = 10

#: Quantos atalhos listar antes de resumir.
_LINK_PREVIEW_COUNT = 10

#: Saida 1 = concluido COM RESSALVAS. Backup roda em tarefa agendada, e sem
#: um codigo proprio ninguem fica sabendo que algo ficou de fora.
_EXIT_PARTIAL = 1

#: Saida 2 = falhou, nenhum pacote gerado.
_EXIT_FAILURE = 2

#: Limites para formatacao de tamanho.
_KB = 1024
_MB = _KB * 1024
_GB = _MB * 1024


def _format_size(bytes_count: int) -> str:
    """
    Formata bytes em unidade legivel (B, KB, MB, GB).

    Examples:
        >>> _format_size(500)
        '500 B'
        >>> _format_size(2048)
        '2.0 KB'
        >>> _format_size(5_242_880)
        '5.0 MB'
    """
    if bytes_count < _KB:
        return f"{bytes_count} B"
    if bytes_count < _MB:
        return f"{bytes_count / _KB:.1f} KB"
    if bytes_count < _GB:
        return f"{bytes_count / _MB:.1f} MB"
    return f"{bytes_count / _GB:.2f} GB"


def _resumo_da_operacao(
    console: Console,
    sources: tuple[Path, ...],
    output: Path,
    exclude: tuple[str, ...],
    no_default_excludes: bool,
    *,
    na_tela: bool = False,
) -> None:
    """Diz o que vai acontecer, antes de acontecer."""
    plural = "s" if len(sources) > 1 else ""
    destino = output.name if na_tela else str(output)
    console.info(f"Backup de {len(sources)} source{plural} -> {destino}")
    if exclude:
        console.info(f"Excludes adicionais: {', '.join(exclude)}")
    if no_default_excludes:
        console.warning(
            "Excludes padrao DESABILITADOS (__pycache__, .git, node_modules serao incluidos)."
        )
    console.info("")


def _relatar_dry_run(console: Console, output: Path, dados: dict[str, Any]) -> None:
    """Mostra o que seria feito, sem criar nada."""
    file_count: int = dados["file_count"]
    console.warning(f"[DRY-RUN] Backup NAO criado: {output}")
    console.info(f"Arquivos a incluir: {file_count}")
    console.info(f"Arquivos a excluir: {dados['skipped_count']}")

    preview: list[str] = dados.get("files_preview") or []
    if not preview:
        return
    console.info("")
    console.info("Preview dos primeiros arquivos:")
    for file_path in preview[:_DRY_RUN_PREVIEW_COUNT]:
        console.info(f"  - {file_path}")
    restantes = file_count - min(file_count, _DRY_RUN_PREVIEW_COUNT)
    if restantes > 0:
        console.info(f"  ... e mais {restantes}.")


def _relatar_volume(console: Console, fontes: list[str], *, na_tela: bool = False) -> None:
    """
    Avisa que origem e backup estao no mesmo disco.

    So avisa: exigir confirmacao quebraria o backup agendado, que roda de
    madrugada sem ninguem por perto.

    No Live (`na_tela`) o aviso seria falso: quem enviou arquivos pelo
    navegador nao escolheu disco nenhum, e a origem e o destino sao a mesma
    pasta temporaria do servidor por construcao. Dizer "prefira outro disco"
    ali sugere um erro que a pessoa nao cometeu e nao pode corrigir. A
    protecao do nucleo continua inteira para a CLI e para o agente.
    """
    if na_tela:
        console.info("Destino externo: não aplicável ao upload avulso.")
        console.info("")
        return
    if not fontes:
        return
    console.warning(f"Origem e destino no MESMO disco ({', '.join(fontes)}).")
    console.info("  Backup no mesmo volume nao protege contra defeito do disco,")
    console.info("  e pode nao proteger contra ransomware, que cifra o que alcanca.")
    console.info("  Prefira outro disco, um destino de rede ou uma midia externa.")
    console.info("")


def _relatar_links(console: Console, links: list[dict[str, Any]]) -> None:
    """Diz quais atalhos foram encontrados, para onde vao, e o que houve."""
    if not links:
        return
    seguidos = [link for link in links if link["seguido"]]
    console.info("")
    if seguidos:
        console.warning(f"{len(seguidos)} atalho(s) SEGUIDOS por --seguir-links:")
    else:
        console.info(f"{len(links)} atalho(s) encontrados e NAO seguidos:")
    for link in links[:_LINK_PREVIEW_COUNT]:
        marca = "fora da origem" if link["fora_da_origem"] else "dentro da origem"
        console.info(f"  - {link['atalho']} -> {link['destino']} ({marca})")
    restantes = len(links) - _LINK_PREVIEW_COUNT
    if restantes > 0:
        console.info(f"  ... e mais {restantes}. A lista completa esta no manifesto.")


def _relatar_nao_lidos(console: Console, nao_lidos: list[dict[str, Any]]) -> None:
    """
    Lista o que NAO entrou no pacote.

    Fica em destaque de proposito: a ausencia precisa ser tao visivel quanto
    a presenca, senao a pessoa acha que tem o arquivo e so descobre que nao
    tem no pior dia possivel.
    """
    console.info("")
    console.warning(f"{len(nao_lidos)} arquivo(s) NAO entraram no backup:")
    for item in nao_lidos[:_UNREADABLE_PREVIEW_COUNT]:
        console.warning(f"  - {item['arquivo']}: {item['motivo']}")
    restantes = len(nao_lidos) - _UNREADABLE_PREVIEW_COUNT
    if restantes > 0:
        console.warning(f"  ... e mais {restantes}. A lista completa esta no manifesto.")
    console.info("")
    console.info(
        "Arquivo aberto no Excel ou no Word nao pode ser copiado. "
        "Feche os arquivos, ou agende o backup fora do horario de uso."
    )


def _anunciar_pacote(console: Console, output: Path, *, com_ressalvas: bool, na_tela: bool) -> None:
    """
    Anuncia o pacote criado.

    Na tela o caminho e do SERVIDOR: nao ajuda quem esta olhando e ainda
    expoe disco, usuario do sistema e pasta temporaria. O nome basta.
    """
    rotulo = output.name if na_tela else str(output)
    if com_ressalvas:
        console.warning(f"Backup criado COM RESSALVAS: {rotulo}")
    else:
        console.success(f"Backup criado: {rotulo}")


def _como_conferir(console: Console, output: Path, *, na_tela: bool) -> None:
    """
    Diz como conferir o pacote depois — pelo caminho que a pessoa tem.

    Quem esta na tela nao tem terminal: mandar digitar comando seria mandar
    a lugar nenhum. O botao existe, e chama o mesmo verificador.
    """
    console.info("")
    if na_tela:
        console.info('Pacote gerado. Use a opção "Verificar este pacote" na área de artefatos.')
    else:
        console.info(f"Para conferir depois: autotarefas verificar {output}")


def _aplicar_retencao(console: Console, output: Path, manter: int) -> None:
    """Apaga os backups datados mais antigos, avisando quais sairam."""
    removidos = rotate_backups(output, manter)
    if not removidos:
        return
    console.info("")
    console.info(
        f"Retencao: mantidos os {manter} mais recentes; "
        f"{len(removidos)} backup(s) antigo(s) removido(s)."
    )
    for antigo in removidos:
        console.info(f"  - {antigo.name}")


# ============================================================
# Comando
# ============================================================


@click.command(name="backup")
@click.argument(
    "sources",
    nargs=-1,
    required=True,
    type=click.Path(
        exists=True,
        readable=True,
        path_type=Path,
    ),
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Caminho do arquivo ZIP de saida.",
)
@click.option(
    "--exclude",
    "-e",
    multiple=True,
    help="Padrao adicional de exclusao (fnmatch). Pode repetir.",
)
@click.option(
    "--seguir-links",
    is_flag=True,
    default=False,
    help=(
        "Entra em junções e links de pasta. Desligado por padrao: um atalho "
        "para fora da origem colocaria dados de terceiros no pacote."
    ),
)
@click.option(
    "--com-data",
    is_flag=True,
    default=False,
    help="Inclui data e hora no nome (backup_2026-08-20_1730.zip).",
)
@click.option(
    "--manter",
    type=click.IntRange(min=0),
    default=0,
    help=(
        "Mantem apenas os N backups datados mais recentes desta mesma base, "
        "apagando os mais antigos. Exige --com-data. 0 = nao apaga nada."
    ),
)
@click.option(
    "--no-default-excludes",
    is_flag=True,
    default=False,
    help=("Desabilita os padroes de exclusao default (__pycache__, .git, node_modules, etc)."),
)
@click.pass_obj
def backup(
    ctx: CLIContext,
    sources: tuple[Path, ...],
    output: Path,
    exclude: tuple[str, ...],
    seguir_links: bool,
    com_data: bool,
    manter: int,
    no_default_excludes: bool,
) -> None:
    """Compacta SOURCES em um ZIP verificavel, com manifesto."""
    console = Console(ctx)

    if manter and not com_data:
        console.error("--manter exige --com-data: sem data no nome nao ha o que rotacionar.")
        raise click.exceptions.Exit(_EXIT_FAILURE)

    if com_data:
        output = timestamped_name(output)

    # ============================================================
    # 1. Resumo da operacao
    # ============================================================
    _resumo_da_operacao(console, sources, output, exclude, no_default_excludes, na_tela=ctx.na_tela)

    # ============================================================
    # 2. Executa a task (BaseTask faz audit automatico)
    # ============================================================
    task = BackupTask(
        sources=list(sources),
        destination=output,
        exclude_patterns=list(exclude) if exclude else None,
        include_default_excludes=not no_default_excludes,
        follow_links=seguir_links,
        dry_run=ctx.dry_run,
    )
    result = task.run()

    # ============================================================
    # 3. Reporta resultado por status
    # ============================================================

    # 3a. SKIPPED — nada pra fazer (aviso, nao erro)
    if result.status == TaskStatus.SKIPPED:
        console.warning(f"Nada para fazer backup: {result.error_message or 'lista vazia'}")
        return  # exit 0

    # 3b. FAILURE — algo deu errado (source inexistente, I/O error)
    if result.is_failure:
        console.error(f"Backup falhou: {result.error_message}")
        for item in result.data.get("unreadable", [])[:_UNREADABLE_PREVIEW_COUNT]:
            console.error(f"  - {item['arquivo']}: {item['motivo']}")
        raise click.exceptions.Exit(_EXIT_FAILURE)

    # 3c. DRY_RUN — mostra preview sem criar
    file_count = result.data["file_count"]
    skipped_count = result.data["skipped_count"]

    if result.status == TaskStatus.DRY_RUN:
        _relatar_dry_run(console, output, result.data)
        return  # exit 0

    # 3d. SUCCESS ou PARTIAL — o pacote existe
    size_str = _format_size(result.data["size_bytes"])
    nao_lidos = result.data.get("unreadable", [])

    _anunciar_pacote(console, output, com_ressalvas=bool(nao_lidos), na_tela=ctx.na_tela)

    console.info(f"Arquivos incluidos: {file_count}")
    if skipped_count > 0:
        console.info(f"Excluidos por regra: {skipped_count}")
    console.info(f"Tamanho: {size_str}")
    console.info(f"SHA-256: {result.data['sha256']}")
    console.info(f"Manifesto: {result.data['manifest']} (dentro do pacote)")

    _relatar_volume(console, result.data.get("same_volume", []), na_tela=ctx.na_tela)
    _relatar_links(console, result.data.get("links", []))

    if nao_lidos:
        _relatar_nao_lidos(console, nao_lidos)

    if manter:
        _aplicar_retencao(console, output, manter)

    _como_conferir(console, output, na_tela=ctx.na_tela)

    if nao_lidos:
        raise click.exceptions.Exit(_EXIT_PARTIAL)


__all__ = ["backup"]
