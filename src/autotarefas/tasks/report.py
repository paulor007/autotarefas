"""
Geracao de relatorios de validacao.

A partir de um `TaskResult` (gerado por `ValidateTask`), produz:
- **JSON** estruturado (machine-readable, pra integracoes)
- **CSV** compacto (human-readable, pra abrir no Excel)
- **Resumo textual** (pra mostrar no console)

Funcoes puras (sem state) — facil compor e testar.

Uso tipico:
    from autotarefas.tasks.report import (
        write_json_report, write_csv_report, generate_summary,
    )

    result = ValidateTask(...).run()

    # Salva relatorios
    write_json_report(result, Path("validacao.json"))
    write_csv_report(result, Path("validacao.csv"))

    # Mostra resumo no terminal
    print(generate_summary(result))
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from autotarefas.core.base import TaskResult

# ============================================================
# JSON Report
# ============================================================


#: Nome fixo do relatorio JSON gerado pelo --out-dir (artefato canonico
#: da Auditoria de planilha; o frontend do Live le este arquivo).
JSON_REPORT_NAME = "validacao_report.json"


def write_json_report(result: TaskResult, output_path: Path) -> None:
    """
    Salva relatorio em JSON estruturado.

    Inclui metadados (task, status, timestamps) + tudo do `result.data`
    (file, rows, issues, etc).

    Encoding: UTF-8 com `ensure_ascii=False` — permite caracteres
    nao-ASCII (portugues) sem escape unicode.

    Indentacao: 2 espacos — legivel mas compacto.

    Cria o diretorio pai se nao existir (defensive coding).

    Args:
        result: TaskResult da validacao.
        output_path: Caminho do arquivo .json a criar.
    """
    report: dict[str, Any] = {
        "task_name": result.task_name,
        "status": str(result.status),
        "started_at": result.started_at.isoformat(),
        "finished_at": (result.finished_at.isoformat() if result.finished_at else None),
        "duration_ms": result.duration_ms,
        "rows_affected": result.rows_affected,
        "error_message": result.error_message,
        "error_type": result.error_type,
        # Espalha todos os campos do data (file, rows, columns, issues...)
        **result.data,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


# ============================================================
# CSV Report
# ============================================================

#: Colunas do relatorio CSV (na ordem que aparecem).
CSV_FIELDNAMES: tuple[str, ...] = ("line", "column", "message", "severity", "value")


def write_csv_report(result: TaskResult, output_path: Path) -> None:
    """
    Salva relatorio em CSV (so a lista de issues).

    Foco no que importa pro usuario corrigir: linha, coluna, mensagem.
    Sem metadados — usa o JSON pra isso.

    Encoding: UTF-8 com BOM (utf-8-sig) — garante que o Excel abra
    com encoding correto no Windows (sem BOM, Excel-BR interpreta como
    latin-1 e quebra acentos).

    Args:
        result: TaskResult da validacao.
        output_path: Caminho do arquivo .csv a criar.
    """
    issues: list[dict[str, Any]] = result.data.get("issues", [])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # newline="" e importante no Windows — sem isso, csv.writer escreve
    # \r\n + \n duplicado, resultando em linhas em branco entre registros.
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(CSV_FIELDNAMES))
        writer.writeheader()
        writer.writerows(issues)


# ============================================================
# Summary Textual (pro console)
# ============================================================


def generate_summary(result: TaskResult, *, max_issues_shown: int = 10) -> str:
    """
    Gera resumo human-readable do resultado.

    Util pra mostrar no terminal apos validacao. Mostra:
    - Arquivo + total de linhas
    - Totais (issues, errors, warnings)
    - Primeiros N issues (default 10) — evita poluir o terminal

    Args:
        result: TaskResult da validacao.
        max_issues_shown: Maximo de issues a listar individualmente.
            Default 10. Se houver mais, mostra "... e mais X".

    Returns:
        String multi-linha com o resumo.
    """
    lines: list[str] = []

    # Cabecalho
    file_path = result.data.get("file", "N/A")
    rows = result.data.get("rows", 0)
    columns = result.data.get("columns", [])

    lines.append(f"Arquivo:  {file_path}")
    lines.append(f"Linhas:   {rows}")
    lines.append(f"Colunas:  {len(columns)}")
    lines.append("")

    # Status + totais
    total_issues = result.data.get("total_issues", 0)
    total_errors = result.data.get("total_errors", 0)
    total_warnings = result.data.get("total_warnings", 0)

    if total_issues == 0:
        lines.append("[OK] Sem problemas encontrados!")
    else:
        lines.append(f"Encontrados {total_issues} problema(s):")
        lines.append(f"  - {total_errors} erro(s)")
        lines.append(f"  - {total_warnings} aviso(s)")
        lines.append("")

        # Primeiros N issues
        issues: list[dict[str, Any]] = result.data.get("issues", [])
        shown = issues[:max_issues_shown]
        for issue in shown:
            severity_tag = "[ERROR]" if issue.get("severity") == "error" else "[WARN]"
            column = issue.get("column")
            local = "linha inteira" if column is None else f"coluna '{column}'"
            lines.append(f"  {severity_tag} Linha {issue['line']}, {local}: {issue['message']}")

        # Indica se truncou
        if len(issues) > max_issues_shown:
            remaining = len(issues) - max_issues_shown
            lines.append(f"  ... e mais {remaining} problema(s).")

    return "\n".join(lines)


# ============================================================
# Cleaning Summary (audit trail no console — modo limpeza)
# ============================================================


def generate_cleaning_summary(result: TaskResult, *, max_changes_shown: int = 10) -> str:
    """
    Gera resumo do audit trail de normalizacao (modo limpeza).

    Le `cleaning_changes` do `result.data` e lista as alteracoes
    antes→depois. Reforca que nenhum dado foi inventado. Se nao houve
    normalizacao, informa isso.

    Args:
        result: TaskResult da validacao (modo limpeza).
        max_changes_shown: Maximo de alteracoes a listar individualmente.

    Returns:
        String multi-linha com o resumo das normalizacoes.
    """
    changes: list[dict[str, Any]] = result.data.get("cleaning_changes", [])
    total = result.data.get("total_cleaned", len(changes))

    lines: list[str] = []
    if total == 0:
        lines.append("[LIMPEZA] Nenhuma normalizacao foi necessaria.")
        return "\n".join(lines)

    lines.append(
        f"[LIMPEZA] {total} valor(es) normalizado(s) com seguranca (nenhum dado foi inventado):"
    )
    for change in changes[:max_changes_shown]:
        rules = ", ".join(change.get("rules", []))
        lines.append(
            f"  Linha {change['line']}, coluna '{change['column']}': "
            f"'{change['before']}' -> '{change['after']}' (regras: {rules})"
        )

    if len(changes) > max_changes_shown:
        remaining = len(changes) - max_changes_shown
        lines.append(f"  ... e mais {remaining} normalizacao(oes).")

    return "\n".join(lines)


__all__ = [
    "CSV_FIELDNAMES",
    "JSON_REPORT_NAME",
    "generate_cleaning_summary",
    "generate_summary",
    "write_csv_report",
    "write_json_report",
]
