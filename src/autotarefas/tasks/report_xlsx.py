"""
Geracao do artefato profissional da Auditoria: ``planilha_validada.xlsx``.

Monta, com openpyxl, uma pasta de trabalho de 4 abas pensada para o
cliente abrir no Excel:

- **Resumo**            — cabecalho, contadores (total/validos/invalidos/
  normalizados) e a tabela de erros por categoria.
- **Registros validos** — as linhas validas (ja normalizadas no modo
  limpeza), com cabecalho formatado, autofiltro e painel congelado.
- **Registros invalidos** — as linhas invalidas + coluna ``motivo``.
- **Auditoria**         — o audit trail (antes/depois/regras) do modo
  limpeza; nos demais modos, uma nota de que nada foi normalizado.

E um RELATORIO (retrato do resultado), nao um modelo editavel: os
contadores sao gravados como valores (fatos da auditoria), sem formulas.
Nao inventa dado — apenas organiza e apresenta o que a validacao produziu.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from autotarefas.core.base import TaskResult
from autotarefas.tasks.artifacts import REASON_COLUMN, split_valid_invalid
from autotarefas.tasks.xlsx_style import (
    ERROR_FILL as _ERROR_FILL,
)
from autotarefas.tasks.xlsx_style import (
    FONT_NAME as _FONT,
)
from autotarefas.tasks.xlsx_style import (
    HEADER_FILL as _HEADER_FILL,
)
from autotarefas.tasks.xlsx_style import (
    HEADER_FONT as _HEADER_FONT,
)
from autotarefas.tasks.xlsx_style import (
    LABEL_FONT as _LABEL_FONT,
)
from autotarefas.tasks.xlsx_style import (
    NEUTRAL_FILL as _NEUTRAL_FILL,
)
from autotarefas.tasks.xlsx_style import (
    OK_FILL as _OK_FILL,
)
from autotarefas.tasks.xlsx_style import (
    TITLE_FONT as _TITLE_FONT,
)
from autotarefas.tasks.xlsx_style import (
    write_dataframe_sheet as _write_dataframe,
)

#: Nome fixo do artefato XLSX.
XLSX_NAME = "planilha_validada.xlsx"

# ============================================================
# Abas (a paleta e a formatacao vivem em `tasks/xlsx_style.py`, para que
# este artefato e o `divergencias.xlsx` da comparacao tenham a mesma cara)
# ============================================================

_SHEET_RESUMO = "Resumo"
_SHEET_VALIDOS = "Registros validos"
_SHEET_INVALIDOS = "Registros invalidos"
_SHEET_AUDITORIA = "Auditoria"

#: Rotulos legiveis para as categorias de erro (aba Resumo).
_CATEGORY_LABELS = {
    "cpf": "CPF invalido",
    "cnpj": "CNPJ invalido",
    "email": "E-mail invalido",
    "telefone": "Telefone invalido",
    "obrigatorio": "Campo obrigatorio vazio",
    "duplicado": "Duplicados",
    "tamanho": "Texto muito curto",
    "intervalo": "Fora do intervalo",
    "enum": "Valor nao permitido",
    "tipo": "Tipo invalido",
    "formato": "Formato invalido",
    "outro": "Outros",
}


# ============================================================
# Helpers
# ============================================================


def _lines_to_indices(lines: list[int]) -> list[int]:
    return [n - 2 for n in lines]


def _rules_str(rules: object) -> str:
    """Junta as regras de uma alteracao em texto (lida com tipagem object)."""
    if isinstance(rules, list):
        return ", ".join(str(r) for r in rules)
    return ""


# ============================================================
# Abas
# ============================================================


def _build_resumo(ws: Worksheet, result: TaskResult, n_invalid: int, n_valid: int) -> None:
    data = result.data
    ws["A1"] = "Auditoria de planilha"
    ws["A1"].font = _TITLE_FONT

    rows: list[tuple[str, object]] = [
        ("Arquivo", str(data.get("file", ""))),
        ("Modo", str(data.get("mode", ""))),
        ("Total de registros", int(data.get("rows", 0))),
        ("Registros validos", n_valid),
        ("Registros invalidos", n_invalid),
        ("Valores normalizados", int(data.get("total_cleaned", 0))),
    ]
    fills = {
        "Registros validos": _OK_FILL,
        "Registros invalidos": _ERROR_FILL,
        "Valores normalizados": _NEUTRAL_FILL,
    }
    start = 3
    for offset, (label, value) in enumerate(rows):
        r = start + offset
        ws.cell(row=r, column=1, value=label).font = _LABEL_FONT
        cell = ws.cell(row=r, column=2, value=value)
        cell.font = Font(name=_FONT)
        if label in fills:
            ws.cell(row=r, column=1).fill = fills[label]
            cell.fill = fills[label]

    # Tabela de erros por categoria
    header_row = start + len(rows) + 1
    ws.cell(row=header_row, column=1, value="Erros por categoria").font = _LABEL_FONT
    ws.cell(row=header_row + 1, column=1, value="Categoria").font = _HEADER_FONT
    ws.cell(row=header_row + 1, column=1).fill = _HEADER_FILL
    ws.cell(row=header_row + 1, column=2, value="Quantidade").font = _HEADER_FONT
    ws.cell(row=header_row + 1, column=2).fill = _HEADER_FILL

    by_category: dict[str, int] = data.get("issues_by_category", {})
    line = header_row + 2
    if by_category:
        for category, count in by_category.items():
            label = _CATEGORY_LABELS.get(category, category)
            ws.cell(row=line, column=1, value=label).font = Font(name=_FONT)
            ws.cell(row=line, column=2, value=count).font = Font(name=_FONT)
            line += 1
    else:
        ws.cell(row=line, column=1, value="Nenhum problema encontrado").font = Font(name=_FONT)

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 60


def _build_auditoria(ws: Worksheet, result: TaskResult) -> None:
    changes: list[dict[str, object]] = result.data.get("cleaning_changes", [])
    mode = str(result.data.get("mode", ""))

    if not changes:
        note = (
            "Nenhuma normalizacao aplicada."
            if mode == "limpeza"
            else f"Modo '{mode}': dados nao sao alterados (sem normalizacao)."
        )
        ws["A1"] = note
        ws["A1"].font = Font(name=_FONT)
        ws.column_dimensions["A"].width = 60
        return

    audit_df = pd.DataFrame(
        {
            "linha": [c.get("line") for c in changes],
            "coluna": [c.get("column") for c in changes],
            "antes": [c.get("before") for c in changes],
            "depois": [c.get("after") for c in changes],
            "regras": [_rules_str(c.get("rules")) for c in changes],
        }
    )
    _write_dataframe(ws, audit_df)


# ============================================================
# Entry point
# ============================================================


def write_xlsx_report(dataframe: pd.DataFrame, result: TaskResult, path: Path) -> None:
    """
    Gera ``planilha_validada.xlsx`` com as 4 abas.

    Args:
        dataframe: DataFrame processado (normalizado no modo limpeza).
        result: TaskResult da validacao.
        path: Caminho do arquivo .xlsx a criar.
    """
    valid_lines, invalid_lines, reasons = split_valid_invalid(result)

    wb = Workbook()
    resumo = wb.active
    resumo.title = _SHEET_RESUMO
    _build_resumo(resumo, result, n_invalid=len(invalid_lines), n_valid=len(valid_lines))

    # Registros validos
    validos_df = dataframe.iloc[_lines_to_indices(valid_lines)]
    _write_dataframe(wb.create_sheet(_SHEET_VALIDOS), validos_df)

    # Registros invalidos (+ motivo)
    invalidos_df = dataframe.iloc[_lines_to_indices(invalid_lines)].copy()
    invalidos_df[REASON_COLUMN] = [" | ".join(reasons.get(n, [])) for n in invalid_lines]
    _write_dataframe(wb.create_sheet(_SHEET_INVALIDOS), invalidos_df)

    # Auditoria
    _build_auditoria(wb.create_sheet(_SHEET_AUDITORIA), result)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


__all__ = ["XLSX_NAME", "write_xlsx_report"]
