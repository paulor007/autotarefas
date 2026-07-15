"""
Apresentacao de um perfil: terminal e JSON.

Tudo aqui e construido DINAMICAMENTE a partir dos contratos
(`WorkbookReadResult` e `ProfileResult`). Nao existe nome de coluna, texto
ou metrica fixada no codigo: se o usuario enviar uma planilha de vendas,
de estoque ou de qualquer outra coisa, a saida se monta sozinha a partir
do que foi encontrado.

Ha um teste que percorre a AST deste modulo e falha o build se um termo de
dominio (cpf, sku, venda, estoque...) aparecer aqui dentro.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from autotarefas import __version__

if TYPE_CHECKING:
    from pathlib import Path

    from autotarefas.profiling.result import ColumnProfile, Finding, ProfileResult
    from autotarefas.reader.result import WorkbookReadResult

#: Nome do artefato. Fixo — o usuario escolhe a PASTA, nunca o nome do arquivo
#: (nome controlado pelo usuario e vetor de path traversal).
JSON_REPORT_NAME = "analise_report.json"

#: Quantas conversoes acompanham o relatorio (a lista completa pode ter milhares).
MAX_CONVERSIONS_IN_REPORT = 20

_PREVIEW_MAX_WIDTH = 15
#: Planilhas muito largas nao cabem no terminal: mostra as primeiras e conta o resto.
_PREVIEW_MAX_COLS = 8
_SEVERITY_TITLES = {
    "problema": "Problemas",
    "aviso": "Avisos",
    "informacao": "Informacoes",
}
_SEVERITY_ORDER = ("problema", "aviso", "informacao")
_DATE_TYPES = ("data", "data_hora")


def _num(valor: int) -> str:
    """7089 -> '7.089' (separador de milhar brasileiro)."""
    return f"{valor:,}".replace(",", ".")


# --- Terminal ----------------------------------------------------------------


def _column_line(col: ColumnProfile) -> str:
    """
    Uma linha por coluna — montada a partir do que a coluna E.

    Nunca a partir do que ela se chama.
    """
    partes = [col.inferred_type, f"{_num(col.distinct_count)} valores distintos"]

    if col.minimum is not None and col.maximum is not None:
        if col.inferred_type in _DATE_TYPES:
            partes.append(f"de {col.minimum} ate {col.maximum}")
        else:
            partes.append(f"minimo {col.minimum}, maximo {col.maximum}")

    if col.fill_rate < 1.0:
        partes.append(f"{col.fill_rate:.0%} preenchida")

    return f"  - {col.name}: {', '.join(partes)}"


def _findings_section(findings: list[Finding]) -> list[str]:
    """Achados agrupados por severidade. So aparece o que existe."""
    linhas: list[str] = []
    for severidade in _SEVERITY_ORDER:
        do_grupo = [f for f in findings if f.severity == severidade]
        if not do_grupo:
            continue
        linhas.append("")
        linhas.append(_SEVERITY_TITLES[severidade])
        for achado in do_grupo:
            linhas.append(f"  - {achado.message}")
    return linhas


def generate_summary(leitura: WorkbookReadResult, perfil: ProfileResult) -> str:
    """Resumo legivel do que foi encontrado. Sem jargao, sem julgamento."""
    linhas: list[str] = [
        f"Arquivo:    {leitura.source_file.name}",
    ]
    if leitura.selected_sheet and leitura.file_type != "csv":
        linhas.append(f"Aba:        {leitura.selected_sheet}")
    linhas.append(f"Cabecalho:  linha {perfil.header_row}")
    linhas.append("")

    linhas.append("Estrutura")
    linhas.append(f"  - Registros: {_num(perfil.row_count)}")
    linhas.append(f"  - Colunas: {perfil.column_count}")
    linhas.append(f"  - Preenchimento: {perfil.fill_rate:.0%}")
    linhas.append(f"  - Linhas completamente duplicadas: {_num(perfil.duplicate_row_count)}")
    linhas.append(f"  - Colunas com tipos misturados: {perfil.mixed_type_column_count}")
    linhas.append(f"  - Erros do Excel: {_num(perfil.excel_error_count)}")
    if perfil.conversion_count:
        linhas.append(f"  - Conversoes seguras aplicadas: {_num(perfil.conversion_count)}")
    linhas.append("")

    linhas.append("Colunas")
    for col in perfil.columns:
        linhas.append(_column_line(col))
        for obs in col.observations:
            linhas.append(f"      {obs}")

    linhas.extend(_findings_section(perfil.findings))
    return "\n".join(linhas)


def _cell_text(valor: object) -> str:
    """Valor da previa como texto curto (data a meia-noite vira so a data)."""
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        if (valor.hour, valor.minute, valor.second) == (0, 0, 0):
            return valor.date().isoformat()
        return valor.isoformat(sep=" ")
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def generate_preview(leitura: WorkbookReadResult, rows: int) -> str:
    """
    As primeiras linhas, como o LEITOR as interpretou.

    Serve para o usuario conferir se a aba e o cabecalho estao certos antes
    de confiar no diagnostico. Nao modifica nada.

    Larga o suficiente para ser util, estreita o suficiente para caber num
    terminal: colunas e valores sao truncados, e planilhas muito largas
    mostram as primeiras colunas com um contador do que ficou de fora.
    """
    df = leitura.normalized_dataframe
    if df is None or df.empty or rows <= 0:
        return ""

    recorte = df.head(rows)
    todas = [str(c) for c in recorte.columns]
    colunas = todas[:_PREVIEW_MAX_COLS]
    ocultas = len(todas) - len(colunas)

    valores = {c: [_cell_text(v) for v in recorte[c]] for c in colunas}
    larguras = [
        min(
            max(len(c), *(len(v) for v in valores[c])) if valores[c] else len(c), _PREVIEW_MAX_WIDTH
        )
        for c in colunas
    ]

    def _celula(texto: str, largura: int) -> str:
        if len(texto) > largura:
            return texto[: largura - 1] + "~"
        return texto.ljust(largura)

    linhas = ["  " + " | ".join(_celula(c, w) for c, w in zip(colunas, larguras, strict=True))]
    linhas.append("  " + "-+-".join("-" * w for w in larguras))
    for i in range(len(recorte)):
        linhas.append(
            "  "
            + " | ".join(_celula(valores[c][i], w) for c, w in zip(colunas, larguras, strict=True))
        )
    if ocultas:
        linhas.append(f"  (+{ocultas} coluna(s) nao exibida(s) na previa)")
    return "\n".join(linhas)


def generate_rejection(leitura: WorkbookReadResult) -> str:
    """
    Mensagem de recusa — usando as alternativas que o LEITOR ja produziu.

    A CLI nao re-detecta nada: se ela tentasse adivinhar de novo, teriamos
    duas logicas de deteccao e duas respostas possiveis.
    """
    linhas = [leitura.rejected_reason or "arquivo nao pode ser analisado"]

    if leitura.available_sheets:
        linhas.append("")
        linhas.append("Abas encontradas:")
        for aba in leitura.available_sheets:
            linhas.append(f"  - {aba.name}: {aba.reason}")

    if leitura.header_alternatives:
        alternativas = ", ".join(str(i) for i in leitura.header_alternatives)
        linhas.append("")
        linhas.append(f"Linhas que poderiam ser o cabecalho: {alternativas}")

    linhas.append("")
    linhas.append("Rode de novo indicando a estrutura, por exemplo:")
    nome_aba = leitura.available_sheets[0].name if leitura.available_sheets else "NOME_DA_ABA"
    linhas.append(
        f'  autotarefas analisar "{leitura.source_file.name}" --sheet "{nome_aba}" --header-row 1'
    )
    return "\n".join(linhas)


# --- JSON --------------------------------------------------------------------


def _column_payload(col: ColumnProfile) -> dict[str, Any]:
    return {
        "name": col.name,
        "inferred_type": col.inferred_type,
        "type_confidence": col.type_confidence,
        "total_count": col.total_count,
        "filled_count": col.filled_count,
        "empty_count": col.empty_count,
        "fill_rate": col.fill_rate,
        "distinct_count": col.distinct_count,
        "uniqueness_rate": col.uniqueness_rate,
        "duplicate_value_count": col.duplicate_value_count,
        "mixed_types": col.mixed_types,
        "excel_error_count": col.excel_error_count,
        "whitespace_issue_count": col.whitespace_issue_count,
        "minimum": col.minimum,
        "maximum": col.maximum,
        "sample_values": col.sample_values,
        "observations": col.observations,
    }


def _finding_payload(achado: Finding) -> dict[str, Any]:
    return {
        "code": achado.code,
        "severity": achado.severity,
        "message": achado.message,
        "column": achado.column,
        "row": achado.row,
        "count": achado.count,
        "samples": achado.samples,
    }


def build_report(leitura: WorkbookReadResult, perfil: ProfileResult) -> dict[str, Any]:
    """
    Payload do relatorio. Estruturado, sem DataFrame, com amostras limitadas.

    O `source_file` guarda so o NOME do arquivo — o caminho completo do
    disco do cliente nao tem valor no relatorio e pode ser sensivel.
    """
    return {
        "metadata": {
            "tool": "autotarefas",
            "tool_version": __version__,
            "generated_at": datetime.now(UTC).isoformat(),
            "source_file": leitura.source_file.name,
            "file_type": leitura.file_type,
        },
        "leitura": {
            "selected_sheet": leitura.selected_sheet,
            "header_row": leitura.header_row,
            "header_confidence": leitura.header_confidence,
            "header_alternatives": leitura.header_alternatives,
            "data_start_row": leitura.data_start_row,
            "data_end_row": leitura.data_end_row,
            "confidence": leitura.confidence,
            "available_sheets": [
                {"name": s.name, "score": s.score, "rows": s.rows, "cols": s.cols}
                for s in leitura.available_sheets
            ],
            "conversion_count": len(leitura.conversions),
            "conversions_sample": [
                {
                    "row": c.row,
                    "column": c.column,
                    "original": c.original,
                    "normalized": c.normalized,
                    "rule": c.rule,
                }
                for c in leitura.conversions[:MAX_CONVERSIONS_IN_REPORT]
            ],
        },
        "estrutura": {
            "row_count": perfil.row_count,
            "column_count": perfil.column_count,
            "total_cells": perfil.total_cells,
            "filled_cells": perfil.filled_cells,
            "empty_cells": perfil.empty_cells,
            "fill_rate": perfil.fill_rate,
            "duplicate_row_count": perfil.duplicate_row_count,
            "completely_empty_row_count": perfil.completely_empty_row_count,
            "completely_empty_column_count": perfil.completely_empty_column_count,
            "mixed_type_column_count": perfil.mixed_type_column_count,
            "excel_error_count": perfil.excel_error_count,
        },
        "columns": [_column_payload(c) for c in perfil.columns],
        "findings": [_finding_payload(f) for f in perfil.findings],
        "reader_warnings": [
            {"code": w.code, "message": w.message, "column": w.column, "row": w.row}
            for w in leitura.warnings
        ],
        "rejected_reason": perfil.rejected_reason,
    }


def write_json_report(payload: dict[str, Any], destino: Path) -> Path:
    """Escreve o relatorio. Cria o diretorio se preciso."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return destino


__all__ = [
    "JSON_REPORT_NAME",
    "MAX_CONVERSIONS_IN_REPORT",
    "build_report",
    "generate_preview",
    "generate_rejection",
    "generate_summary",
    "write_json_report",
]
