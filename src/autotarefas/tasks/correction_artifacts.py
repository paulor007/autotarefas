"""
Artefatos das correcoes por regras confirmadas (RF-PLA-010).

- ``planilha_corrigida.xlsx``  — a planilha com as correcoes aplicadas.
  Quando a entrada e XLSX, sai preservando a apresentacao original
  (PLA-009): so as celulas corrigidas sao reescritas.
- ``planilha_corrigida.csv``   — o mesmo conteudo para o proximo passo do fluxo.
- ``itens_para_revisao.csv``   — o que ficou FORA das regras declaradas.
- ``correcoes_report.json``    — o relatorio com as quatro naturezas
  separadas, como a ficha exige.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pandas as pd
from openpyxl import Workbook

from autotarefas.tasks.corrections import CorrectionResult
from autotarefas.tasks.presentation import (
    PreservationReport,
    supports_presentation,
    write_treated_xlsx,
)
from autotarefas.tasks.xlsx_style import write_dataframe_sheet

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

CORRECTED_XLSX_NAME = "planilha_corrigida.xlsx"
CORRECTED_CSV_NAME = "planilha_corrigida.csv"
REVIEW_CSV_NAME = "itens_para_revisao.csv"
JSON_REPORT_NAME = "correcoes_report.json"

_SHEET_DADOS = "Dados corrigidos"

#: Rotulos legiveis das quatro naturezas da ficha.
NATURE_LABELS: dict[str, str] = {
    "automatico_seguro": "automatico seguro (conversao de tipo pelo leitor)",
    "normalizacao": "normalizacao (espacos, caixa, formato)",
    "regra_confirmada": "regra confirmada pelo usuario",
    "revisao": "item para revisao (fora das regras)",
}


def corrected_frame(rows: Sequence[dict[str, str]], columns: Sequence[str]) -> pd.DataFrame:
    """As linhas corrigidas como DataFrame, na ordem original das colunas."""
    return pd.DataFrame(list(rows), columns=list(columns), dtype=str).fillna("")


def review_frame(result: CorrectionResult) -> pd.DataFrame:
    """Os itens que ficaram fora das regras declaradas."""
    linhas: list[dict[str, Any]] = [
        {
            "linha": item.row,
            "coluna": item.column,
            "valor": item.before,
            "motivo": item.rule,
        }
        for item in result.review
    ]
    return pd.DataFrame(linhas, columns=["linha", "coluna", "valor", "motivo"])


def changes_frame(result: CorrectionResult) -> pd.DataFrame:
    """Uma linha por celula corrigida, com a regra que justificou."""
    linhas: list[dict[str, Any]] = [
        {
            "linha": change.row,
            "coluna": change.column,
            "antes": change.before,
            "depois": change.after,
            "natureza": NATURE_LABELS.get(change.nature, change.nature),
            "regra": change.rule,
        }
        for change in result.changes
    ]
    return pd.DataFrame(linhas, columns=["linha", "coluna", "antes", "depois", "natureza", "regra"])


def build_report_payload(
    result: CorrectionResult,
    source_name: str,
    reader_conversions: int = 0,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Monta o ``correcoes_report.json``.

    ``reader_conversions`` sao as conversoes automaticas seguras que o
    leitor ja tinha feito (numero como texto, data serial): elas entram no
    resumo para que as quatro naturezas apareçam separadas no MESMO lugar.
    """
    contagem = dict(result.counts)
    contagem["automatico_seguro"] = reader_conversions

    payload: dict[str, Any] = dict(meta or {})
    payload.update(
        {
            "requisito": "RF-PLA-010",
            "arquivo": source_name,
            "regras": [rule.describe() for rule in result.rules],
            "resumo": contagem,
            "naturezas": NATURE_LABELS,
            "correcoes": [
                {
                    "linha": c.row,
                    "coluna": c.column,
                    "antes": c.before,
                    "depois": c.after,
                    "natureza": c.nature,
                    "regra": c.rule,
                }
                for c in result.changes
            ],
            "para_revisao": [
                {
                    "linha": item.row,
                    "coluna": item.column,
                    "valor": item.before,
                    "motivo": item.rule,
                }
                for item in result.review
            ],
            "avisos": list(result.warnings),
            "limitacoes": [
                "nenhuma correcao acontece fora das regras declaradas no arquivo de regras",
                "valor que nao casa com a regra vai para revisao (ou fica intacto, "
                "se a regra declarar 'fora_da_regra: manter')",
                "o arquivo de entrada nunca e alterado",
            ],
        }
    )
    return payload


def write_json_report(
    result: CorrectionResult,
    path: Path,
    source_name: str,
    reader_conversions: int = 0,
    meta: dict[str, Any] | None = None,
) -> None:
    """Grava o relatorio das correcoes em JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_report_payload(result, source_name, reader_conversions, meta)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def write_corrected_xlsx(  # noqa: PLR0913 - dois opcionais keyword-only
    source: Path,
    destination: Path,
    result: CorrectionResult,
    frame: pd.DataFrame,
    *,
    header_row: int = 1,
    sheet: str | None = None,
) -> PreservationReport | None:
    """
    Grava a planilha corrigida.

    Com entrada XLSX, reusa a preservacao do PLA-009 (so as celulas
    corrigidas sao reescritas sobre uma copia do original). Com CSV, gera
    uma planilha nova com a formatacao profissional do PLA-007.

    Returns:
        O relatorio de preservacao quando houve preservacao; None no
        caminho CSV (nao ha apresentacao a preservar).
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    if supports_presentation(source):
        mudancas = [{"line": c.row, "column": c.column, "after": c.after} for c in result.changes]
        return write_treated_xlsx(
            source,
            destination,
            mudancas,
            dataframe=None,
            header_row=header_row,
            sheet=sheet,
        )

    workbook = Workbook()
    worksheet = workbook.active
    if worksheet is None:  # pragma: no cover
        worksheet = workbook.create_sheet()
    worksheet.title = _SHEET_DADOS
    write_dataframe_sheet(worksheet, frame)
    workbook.save(destination)
    return None


def generate_summary(result: CorrectionResult, *, max_rows: int = 10) -> str:
    """Resumo das correcoes para o terminal."""
    contagem = result.counts
    partes: list[str] = [
        f"Regras confirmadas aplicadas: {len(result.rules)}",
        *(f"  - {rule.describe()}" for rule in result.rules),
        "",
        f"  Correcoes por regra   {contagem['regra_confirmada']}",
        f"  Itens para revisao    {contagem['revisao']}",
    ]

    if result.changes:
        partes.append("")
        partes.append(f"Correcoes ({len(result.changes)}):")
        for change in result.changes[:max_rows]:
            partes.append(
                f"  - linha {change.row}, {change.column}: "
                f"'{change.before}'  ->  '{change.after}' ({change.rule})"
            )
        if len(result.changes) > max_rows:
            partes.append(f"  ... e mais {len(result.changes) - max_rows}")

    if result.review:
        partes.append("")
        partes.append(f"Para revisao ({len(result.review)}) — nada foi alterado nestes casos:")
        for item in result.review[:max_rows]:
            partes.append(f"  - linha {item.row}, {item.column}: '{item.before}' ({item.rule})")
        if len(result.review) > max_rows:
            partes.append(f"  ... e mais {len(result.review) - max_rows}")

    if result.warnings:
        partes.append("")
        partes.append("Avisos:")
        partes.extend(f"  - {aviso}" for aviso in result.warnings)

    return "\n".join(partes)


def write_correction_artifacts(  # noqa: PLR0913 - tres opcionais keyword-only
    source: Path,
    out_dir: Path,
    result: CorrectionResult,
    frame: pd.DataFrame,
    *,
    header_row: int = 1,
    sheet: str | None = None,
    reader_conversions: int = 0,
    meta: dict[str, Any] | None = None,
) -> tuple[Path, ...]:
    """
    Gera os artefatos das correcoes em ``out_dir`` (nomes fixos).

    Returns:
        Caminhos criados: XLSX corrigido, CSV corrigido, itens para revisao,
        relatorio JSON.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    xlsx = out_dir / CORRECTED_XLSX_NAME
    write_corrected_xlsx(source, xlsx, result, frame, header_row=header_row, sheet=sheet)

    csv = out_dir / CORRECTED_CSV_NAME
    frame.to_csv(csv, index=False, encoding="utf-8-sig")

    revisao = out_dir / REVIEW_CSV_NAME
    review_frame(result).to_csv(revisao, index=False, encoding="utf-8-sig")

    relatorio = out_dir / JSON_REPORT_NAME
    write_json_report(result, relatorio, source.name, reader_conversions, meta)

    return (xlsx, csv, revisao, relatorio)


__all__ = [
    "CORRECTED_CSV_NAME",
    "CORRECTED_XLSX_NAME",
    "JSON_REPORT_NAME",
    "NATURE_LABELS",
    "REVIEW_CSV_NAME",
    "build_report_payload",
    "changes_frame",
    "corrected_frame",
    "generate_summary",
    "review_frame",
    "write_corrected_xlsx",
    "write_correction_artifacts",
    "write_json_report",
]
