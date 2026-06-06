"""
Comando ``organize``: organiza arquivos em pastas conforme regras YAML.

Operacao DESTRUTIVA (move arquivos por padrao). Camadas de protecao:
- ``--dry-run`` global mostra o que seria feito (recomendado primeiro!)
- Confirmacao interativa se >N arquivos (default 50)
- ``--no-confirm`` pula a confirmacao
- ``--yes/-y`` global tambem pula

Uso:
    # Sempre comece com dry-run!
    autotarefas --dry-run organize ~/Downloads --rules downloads.yaml

    # Depois execute de verdade
    autotarefas organize ~/Downloads --rules downloads.yaml

    # Em CI/automacao: pula confirmacao
    autotarefas --yes organize ~/Downloads --rules downloads.yaml

    # Threshold customizado (so pede confirm se >100 arquivos)
    autotarefas organize ~/Downloads --rules x.yaml --confirm-threshold 100
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.core.base import TaskResult, TaskStatus
from autotarefas.core.exceptions import AutoTarefasError
from autotarefas.tasks.organize import OrganizeTask, load_rules

#: Quantas operacoes mostrar no preview de dry-run.
_PREVIEW_LIMIT = 10


# ============================================================
# Helpers de apresentacao
# ============================================================


def _mostrar_preview(console: Console, result: TaskResult) -> None:
    """
    Mostra preview das operacoes (primeiras N).

    Cada operacao aparece com tag indicativa do status:
    - [OK] sucesso
    - [SKIP] vai ser pulado (destino existe)
    - [ERR] erro
    - [N/A] arquivo sem rule que bate
    """
    operations: list[dict[str, Any]] = result.data.get("operations", [])
    if not operations:
        return

    console.info("")
    console.info("Preview das operacoes:")

    for op in operations[:_PREVIEW_LIMIT]:
        status = op["status"]
        source = op["source"]

        if status == "success":
            rule_name = op["rule_name"]
            dest = op["destination"]
            console.info(f"  [OK]   [{rule_name}] {source}")
            console.info(f"         -> {dest}")
        elif status == "skipped":
            console.info(f"  [SKIP] {source} (destino ja existe)")
        elif status == "error":
            error = op.get("error", "erro desconhecido")
            console.info(f"  [ERR]  {source}: {error}")
        elif status == "unmatched":
            console.info(f"  [N/A]  {source} (sem regra)")

    total = result.data["total_files"]
    if total > _PREVIEW_LIMIT:
        remaining = total - _PREVIEW_LIMIT
        console.info(f"  ... e mais {remaining} arquivo(s).")


def _mostrar_estatisticas_finais(console: Console, result: TaskResult, action: str) -> None:
    """Mostra contagens finais apos execucao."""
    moved = result.data["moved_count"]
    skipped = result.data["skipped_count"]
    errors = result.data["error_count"]
    unmatched = result.data["unmatched_count"]

    plural = "s" if moved != 1 else ""
    console.success(f"Organizacao concluida! {moved} arquivo{plural} {action}-ido{plural}.")

    if skipped > 0:
        console.info(f"Pulados (conflito): {skipped}")
    if errors > 0:
        console.info(f"Erros: {errors}")
    if unmatched > 0:
        console.info(f"Sem regra (mantidos no source): {unmatched}")


# ============================================================
# Comando
# ============================================================


@click.command(name="organize")
@click.argument(
    "source_dir",
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        path_type=Path,
    ),
)
@click.option(
    "--rules",
    "-r",
    required=True,
    type=click.Path(
        exists=True,
        dir_okay=False,
        readable=True,
        path_type=Path,
    ),
    help="Caminho do arquivo YAML com as regras de organizacao.",
)
@click.option(
    "--confirm-threshold",
    type=click.IntRange(min=0),
    default=50,
    show_default=True,
    help="Pede confirmacao se mais de N arquivos seriam afetados.",
)
@click.option(
    "--no-confirm",
    is_flag=True,
    default=False,
    help="Pula a confirmacao interativa (mesmo acima do threshold).",
)
@click.pass_obj
def organize(  # noqa: PLR0915
    ctx: CLIContext,
    source_dir: Path,
    rules: Path,
    confirm_threshold: int,
    no_confirm: bool,
) -> None:
    """Organiza arquivos de SOURCE_DIR em sub-pastas conforme regras YAML."""
    console = Console(ctx)

    # ============================================================
    # 1. Carrega regras
    # ============================================================
    console.info(f"Carregando regras: {rules}")
    try:
        ruleset = load_rules(rules)
    except AutoTarefasError as e:
        console.error(f"Erro ao carregar regras: {e}")
        raise click.exceptions.Exit(2) from e

    console.info(f"Regras carregadas: {len(ruleset.rules)} regra(s).")
    console.info("")

    # ============================================================
    # 2. Mostra cabecalho
    # ============================================================
    console.info(f"Source:      {source_dir}")
    console.info(f"Target root: {ruleset.target_root}")
    console.info(f"Action:      {ruleset.action}")
    console.info(f"On conflict: {ruleset.on_conflict}")
    console.info("")

    # ============================================================
    # 3. Decisao: precisamos do dry-run preliminar?
    # ============================================================
    # Skip pre-dry-run quando:
    # - Usuario passou --yes ou --no-confirm explicitamente
    # - Estamos em --dry-run global (so vamos rodar dry-run mesmo)
    needs_confirmation_check = not ctx.yes and not no_confirm and not ctx.dry_run

    if needs_confirmation_check:
        # Dry-run preliminar pra saber quantos arquivos seriam afetados
        console.info("Analisando arquivos (dry-run preliminar)...")
        preview = OrganizeTask(source_dir=source_dir, rules=ruleset, dry_run=True)
        preview_result = preview.run()

        if preview_result.is_failure:
            console.error(f"Falha na analise: {preview_result.error_message}")
            raise click.exceptions.Exit(1)

        if preview_result.status == TaskStatus.SKIPPED:
            console.warning(f"Nada para organizar: {preview_result.error_message or 'pasta vazia'}")
            return  # exit 0

        would_affect = preview_result.data["moved_count"]
        total_files = preview_result.data["total_files"]

        console.info(
            f"Arquivos analisados: {total_files} ({would_affect} seriam {ruleset.action}-idos)"
        )

        # ============================================================
        # 4. Confirmacao se acima do threshold
        # ============================================================
        if would_affect > confirm_threshold:
            console.warning("")
            console.warning(
                f"ATENCAO: Voce esta prestes a {ruleset.action} {would_affect} arquivo(s)."
            )

            if not click.confirm("Continuar?", default=False):
                console.info("Operacao cancelada pelo usuario.")
                return  # exit 0

    # ============================================================
    # 5. Execucao final
    # ============================================================
    console.info("")

    task = OrganizeTask(
        source_dir=source_dir,
        rules=ruleset,
        dry_run=ctx.dry_run,
    )
    result = task.run()

    # ============================================================
    # 6. Reporta resultado
    # ============================================================

    # 6a. SKIPPED
    if result.status == TaskStatus.SKIPPED:
        console.warning(f"Nada para organizar: {result.error_message or 'pasta vazia'}")
        return

    # 6b. FAILURE
    if result.is_failure:
        console.error(f"Organizacao falhou: {result.error_message}")
        raise click.exceptions.Exit(1)

    # 6c. DRY_RUN — mostra preview e termina
    if result.status == TaskStatus.DRY_RUN:
        console.warning("[DRY-RUN] Nenhuma alteracao foi feita.")
        moved = result.data["moved_count"]
        unmatched = result.data["unmatched_count"]
        console.info(f"Seriam {ruleset.action}-idos: {moved}")
        if unmatched > 0:
            console.info(f"Sem regra: {unmatched}")
        _mostrar_preview(console, result)
        return

    # 6d. SUCCESS
    _mostrar_estatisticas_finais(console, result, ruleset.action)

    # Erros durante execucao -> exit 1 (mas mensagem ja foi mostrada)
    if result.data["error_count"] > 0:
        raise click.exceptions.Exit(1)


__all__ = ["organize"]
