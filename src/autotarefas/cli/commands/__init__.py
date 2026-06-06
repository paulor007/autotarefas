"""
Comando ``init``: inicializa a estrutura do AutoTarefas.

Cria as pastas necessárias em ``~/.autotarefas/`` e gera um template
``.env`` para configuração inicial.

Uso:
    autotarefas init                          # cria em ~/.autotarefas/
    autotarefas init --force                  # sobrescreve .env existente
    autotarefas init --data-dir ./meu-dir     # diretorio custom
    autotarefas init --dry-run                # mostra sem fazer
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import click

from autotarefas.cli.console import Console
from autotarefas.cli.context import CLIContext
from autotarefas.core import audit, settings

# ============================================================
# Template do .env gerado pelo init
# ============================================================

ENV_TEMPLATE = """# AutoTarefas — Configuracoes locais
# Gerado automaticamente por `autotarefas init`
#
# Edite este arquivo para configurar suas credenciais e preferencias.
# Veja documentacao em: https://github.com/paulor007/autotarefas

# Ambiente: dev, demo, homolog ou prod
ENVIRONMENT=dev

# Log level: TRACE, DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO

# Email (opcional - pra notificacoes futuras)
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_USER=
# EMAIL_PASSWORD=

# RPA (opcional - pra automacao web)
# RPA_HEADLESS=true
# RPA_DEFAULT_TIMEOUT=10

# Audit (recomendado pra producao)
# Gere uma chave forte com:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
# AUDIT_SECRET_KEY=
"""


def _resolve_base_dir(data_dir: str | None) -> Path:
    """
    Determina o diretorio base do AutoTarefas.

    Args:
        data_dir: Caminho custom (do --data-dir). Se None, usa default.

    Returns:
        Path do diretorio base (ex: ~/.autotarefas/).
    """
    if data_dir:
        return Path(data_dir).expanduser()
    # ``settings.logs_dir`` aponta pra ``~/.autotarefas/logs/``
    # Pegamos o pai pra ter ``~/.autotarefas/``
    return settings.logs_dir.parent


@click.command(name="init")
@click.option(
    "--data-dir",
    type=click.Path(),
    default=None,
    help="Diretorio base (default: ~/.autotarefas).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Sobrescreve .env existente (default: preserva).",
)
@click.pass_obj
def init(ctx: CLIContext, data_dir: str | None, force: bool) -> None:
    """Inicializa a estrutura do AutoTarefas (~/.autotarefas/)."""
    console = Console(ctx)
    started_at = datetime.now(UTC)

    base_dir = _resolve_base_dir(data_dir)

    console.info(f"Inicializando AutoTarefas em: {base_dir}")
    console.info("")

    created_count = 0
    skipped_count = 0

    # ============================================================
    # 1. Criar diretorios
    # ============================================================
    dirs_to_create = {
        "logs": base_dir / "logs",
        "screenshots": base_dir / "screenshots",
        "reports": base_dir / "reports",
    }

    for name, path in dirs_to_create.items():
        if path.exists():
            console.info(f"  [SKIP] {name}/ (ja existe)")
            skipped_count += 1
        elif ctx.dry_run:
            console.warning(f"  [DRY-RUN] Criaria {name}/")
        else:
            path.mkdir(parents=True, exist_ok=True)
            console.success(f"Criado: {name}/")
            created_count += 1

    # ============================================================
    # 2. Criar .env (se nao existir ou se --force)
    # ============================================================
    env_path = base_dir / ".env"

    if env_path.exists() and not force:
        console.info("  [SKIP] .env (ja existe — use --force pra sobrescrever)")
        skipped_count += 1
    elif ctx.dry_run:
        action = "Sobrescreveria" if env_path.exists() else "Criaria"
        console.warning(f"  [DRY-RUN] {action} .env")
    else:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(ENV_TEMPLATE, encoding="utf-8")
        action = "Sobrescrito" if force and env_path.exists() else "Criado"
        console.success(f"{action}: .env")
        created_count += 1

    # ============================================================
    # 3. Resumo + audit
    # ============================================================
    console.info("")
    console.success(
        f"Inicializacao concluida: {created_count} criados, {skipped_count} ja existiam."
    )

    if not ctx.dry_run and created_count > 0:
        console.info("")
        console.info(f"Proximo passo: edite {env_path} pra configurar.")

    # Registra no audit (best-effort, nao propaga erros)
    duration_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
    audit.record(
        task_name="init",
        status="dry_run" if ctx.dry_run else "success",
        started_at=started_at,
        duration_ms=duration_ms,
        rows_affected=created_count,
        args={"data_dir": str(base_dir), "force": force},
    )


__all__ = ["init"]
