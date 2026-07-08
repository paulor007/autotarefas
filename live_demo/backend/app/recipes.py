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
_CONTATOS = ASSETS / "contatos_demo.csv"

# Mock interno (sobe no lifespan); host/porta fixos no servidor.
_PRIMARY = f"http://127.0.0.1:{settings.demo_primary_port}"


# build_argv e a allowlist de execucao: um ramo explicito e auditavel por automacao.
def build_argv(  # noqa: PLR0911
    automation_id: str,
    workspace: Path,
    inputs: list[Path],
) -> list[str]:
    """Monta o argv real da automacao. Levanta KeyError se nao for curada."""
    base = [sys.executable, "-m", "autotarefas"]
    in_dir = workspace / "in"
    out_dir = workspace / "out"

    if automation_id == "validate":
        planilha = inputs[0]
        return [
            *base,
            "validate",
            str(planilha),
            "-s",
            str(_SCHEMA),
            "--mode",
            "limpeza",
            "--out-dir",
            str(out_dir),
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
    if automation_id == "send_api":
        planilha = inputs[0]
        return [
            *base,
            "send",
            "api",
            "-p",
            str(planilha),
            "-u",
            f"{_PRIMARY}/api/clientes",
            "--out-dir",
            str(out_dir),
        ]
    if automation_id == "send_telegram":
        return [
            *base,
            "send",
            "telegram",
            "-p",
            str(_CONTATOS),
            "--text",
            "Ola {nome}! Sua solicitacao foi recebida e ja esta em processamento.",
            "--chat-id-column",
            "chat_id",
            "--base-url",
            _PRIMARY,
            "-r",
            str(out_dir / "send_telegram_report.json"),
        ]
    raise KeyError(automation_id)


def reset_url(automation_id: str) -> str | None:
    """
    URL de reset do sistema de demonstracao para uma automacao.

    O mock do CRM guarda cadastros entre execucoes; sem reset, a 2a demo
    seguida do Cadastro automatico responderia 409 em cascata (todos os
    CPFs "ja cadastrados"). O engine chama esta URL (POST) antes de rodar
    a automacao, garantindo que cada execucao comece do zero.

    Returns:
        URL para POST, ou None se a automacao nao precisa de reset.
    """
    if automation_id == "send_api":
        return f"{_PRIMARY}/limpar"
    return None
