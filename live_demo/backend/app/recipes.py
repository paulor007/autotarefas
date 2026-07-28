"""Receitas de execucao: mapeiam uma automacao curada para o argv real.

Esta e a allowlist de execucao. Todo caminho e resolvido pelo servidor para
dentro do workspace; nada vem do visitante como argumento (so bytes de arquivo).
NUNCA usar shell. Schemas e regras ficam fixos em ./assets.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .config import settings

ASSETS = Path(__file__).resolve().parent / "assets"
_SCHEMA = ASSETS / "schema_clientes.yaml"
_ORGANIZE_RULES = ASSETS / "organize_rules.yaml"
_CONTATOS = ASSETS / "contatos_demo.csv"

# Mock interno (sobe no lifespan); host/porta fixos no servidor.
_PRIMARY = f"http://127.0.0.1:{settings.demo_primary_port}"


# build_argv e a allowlist de execucao: um ramo explicito e auditavel por automacao.
@dataclass(frozen=True, slots=True)
class JourneyOptions:
    """
    Escolhas CONFIRMADAS pelo visitante na jornada de planilhas (1.8B-2B).

    Chega aqui como dado tipado, nunca como argv: o navegador nao monta linha
    de comando. Os caminhos sao internos ao workspace, resolvidos pelo
    servidor — o cliente so manda nome de aba, numero de linha e flags.
    """

    schema_path: Path
    sheet: str | None = None
    header_row: int | None = None
    strict_warnings: bool = False
    max_issues: int | None = None


def build_argv(  # noqa: PLR0911
    automation_id: str,
    workspace: Path,
    inputs: list[Path],
    journey: JourneyOptions | None = None,
) -> list[str]:
    """
    Monta o argv real da automacao. Levanta KeyError se nao for curada.

    `journey` so e usado pelo `validate`: quando presente, a validacao roda
    com o schema e as escolhas que o visitante confirmou, em vez do schema
    fixo da demonstracao. Sem ele, o comportamento e o da 1.8A, byte a byte.
    """
    base = [sys.executable, "-m", "autotarefas"]
    in_dir = workspace / "in"
    out_dir = workspace / "out"

    if automation_id == "validate":
        planilha = inputs[0]
        if journey is not None:
            return _validate_journey_argv(base, planilha, out_dir, journey)
        return [
            *base,
            "validate",
            str(planilha),
            "-s",
            str(_SCHEMA),
            "--mode",
            "limpeza",
            # Artefatos avulsos (o front consome validacao_report.json daqui):
            "--out-dir",
            str(out_dir),
            # Pacote de evidencias da 1.7 (manifesto + hashes + classificacao).
            # Vai para uma subpasta; o engine a compacta num unico .zip, para
            # nao colidir com o registros_validos.csv que o --out-dir ja poe
            # na raiz e para o download respeitar a guarda de nome simples.
            "--artefatos",
            str(out_dir / "pacote_execucao"),
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
            f"{_PRIMARY}/api/catalogo",
            "--out-dir",
            str(out_dir),
            "--per-page",
            "10",
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


def _validate_journey_argv(
    base: list[str],
    planilha: Path,
    out_dir: Path,
    journey: JourneyOptions,
) -> list[str]:
    """
    Argv da validacao com as escolhas confirmadas pelo visitante.

    Mesma forma da receita da 1.8A (`--out-dir` para o resumo que o frontend
    ja consome + `--artefatos` para o pacote da 1.7), acrescentando `--sheet`
    e `--header-row` quando houve escolha. Cada valor vem de um campo tipado
    de `JourneyOptions`; nada e concatenado a partir de texto livre do
    navegador, e nenhum caminho e fornecido pelo cliente.
    """
    argv = [
        *base,
        "validate",
        str(planilha),
        "-s",
        str(journey.schema_path),
        "--mode",
        "auditoria",
        "--out-dir",
        str(out_dir),
        "--artefatos",
        str(out_dir / "pacote_execucao"),
    ]
    if journey.sheet is not None:
        argv += ["--sheet", journey.sheet]
    if journey.header_row is not None:
        argv += ["--header-row", str(journey.header_row)]
    if journey.strict_warnings:
        argv.append("--strict-warnings")
    if journey.max_issues is not None:
        argv += ["--max-issues", str(journey.max_issues)]
    return argv
