"""Receitas de execucao: mapeiam uma automacao curada para o argv real.

Esta e a allowlist de execucao. Todo caminho e resolvido pelo servidor para
dentro do workspace; nada vem do visitante como argumento (so bytes de arquivo).
NUNCA usar shell. Schemas e regras ficam fixos em ./assets.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .config import settings

ASSETS = Path(__file__).resolve().parent / "assets"
_SCHEMA = ASSETS / "schema_clientes.yaml"
_ORGANIZE_RULES = ASSETS / "organize_rules.yaml"

# Mock interno (sobe no lifespan); host/porta fixos no servidor.
_PRIMARY = f"http://127.0.0.1:{settings.demo_primary_port}"


def build_argv(automation_id: str, workspace: Path, inputs: list[Path]) -> list[str]:
    """Monta o argv real da automacao. Levanta KeyError se nao for curada."""
    base = [sys.executable, "-m", "autotarefas"]
    in_dir = workspace / "in"
    out_dir = workspace / "out"

    if automation_id == "validate":
        csv = inputs[0]
        return [
            *base,
            "validate",
            str(csv),
            "-s",
            str(_SCHEMA),
            "--report-json",
            str(out_dir / "validate_report.json"),
        ]
    if automation_id == "backup":
        return [*base, "backup", str(in_dir), "-o", str(out_dir / "backup.zip")]
    if automation_id == "organize":
        return [*base, "--yes", "organize", str(in_dir), "-r", str(_ORGANIZE_RULES)]
    if automation_id == "extract_web":
        return [
            *base,
            "extract",
            "web",
            "-u",
            f"{_PRIMARY}/catalogo",
            "-o",
            str(out_dir / "extract_web.csv"),
            "-r",
            "tr.produto",
            "-f",
            "nome=td.nome",
            "-f",
            "preco=td.preco",
            "-n",
            "a.next",
        ]
    if automation_id == "extract_api":
        return [
            *base,
            "extract",
            "api",
            "-u",
            f"{_PRIMARY}/api/clientes",
            "-o",
            str(out_dir / "extract_api.csv"),
        ]
    raise KeyError(automation_id)
