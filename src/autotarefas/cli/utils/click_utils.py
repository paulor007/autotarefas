"""
Utils de CLI (Click/Rich) do AutoTarefas.

Centraliza helpers usados por vários comandos da CLI:
- obter Console via ctx.obj
- detectar dry-run
- parse de parâmetros (ex.: -p chave valor)
- helpers de conversão simples (str -> bool/int/float/None)

Uso:
    from autotarefas.cli.utils.click_utils import (
        get_console, is_dry_run, params_tuple_to_dict
    )
"""

from __future__ import annotations

from typing import Any

import click
from rich.console import Console

_DEFAULT_CONSOLE = Console()


def get_console(ctx: click.Context) -> Console:
    """
    Retorna o Console armazenado em ctx.obj["console"], se existir.
    Caso não exista, retorna um Console padrão.

    Isso permite que o `main.py` injete um Console customizado (tema, width, etc.)
    e que todos os comandos usem o mesmo.
    """
    obj = getattr(ctx, "obj", None) or {}
    c = obj.get("console")
    return c if isinstance(c, Console) else _DEFAULT_CONSOLE


def is_dry_run(ctx: click.Context) -> bool:
    """
    True se a execução estiver em modo dry-run (simulação).

    Convenção: ctx.obj["dry_run"] = True/False
    """
    obj = getattr(ctx, "obj", None) or {}
    return bool(obj.get("dry_run", False))


def parse_value(value: str) -> Any:
    """
    Faz um parse leve de string para tipos simples.

    Regras:
    - "true"/"false" (case-insensitive) -> bool
    - "none"/"null" -> None
    - inteiro -> int
    - float (com '.' ou ',') -> float
    - fallback -> string original
    """
    v = value.strip()

    lower = v.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if lower in {"none", "null"}:
        return None

    # int?
    if v.isdigit() or (v.startswith("-") and v[1:].isdigit()):
        try:
            return int(v)
        except ValueError:
            pass

    # float?
    if "." in v or "," in v:
        try:
            return float(v.replace(",", "."))
        except ValueError:
            pass

    return value


def params_tuple_to_dict(params: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    """
    Converte múltiplos (-p chave valor) em dict[str, Any].

    Também valida:
    - chave vazia
    - chave duplicada
    """
    out: dict[str, Any] = {}

    for k, v in params:
        key = k.strip()
        if not key:
            raise click.BadParameter("Chave de parâmetro vazia em -p/--param.")
        if key in out:
            raise click.BadParameter(f"Parâmetro duplicado: '{key}'.")
        out[key] = parse_value(v)

    return out


__all__ = ["get_console", "is_dry_run", "parse_value", "params_tuple_to_dict"]
