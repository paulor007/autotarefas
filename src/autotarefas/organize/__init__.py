"""
Análise e organização de planilhas — o núcleo do Card 01.

Quatro peças, cada uma com uma responsabilidade que não se mistura:

    sheets        inspeciona TODAS as abas e classifica cada uma
    presentation  avalia a apresentação por critérios verificáveis
    organizer     gera a versão organizada (apresentação + correções + ordem)
    insights      sugere papéis de coluna e calcula indicadores CONFIRMADOS
    dashboard     desenha o painel (tabelas + graficos) dos indicadores
    report        escreve o `relatorio_analise.xlsx`

A regra que atravessa o pacote: **nada muda sem confirmação**, e o arquivo
original nunca é sobrescrito.
"""

from autotarefas.organize.dashboard import describe_source, write_panel
from autotarefas.organize.insights import (
    Indicator,
    IndicatorRequest,
    RoleSuggestion,
    build_indicators,
    default_request,
    suggest_roles,
    summary_is_offerable,
)
from autotarefas.organize.organizer import (
    DASHBOARD_SHEET,
    ORGANIZED_XLSX_NAME,
    OrganizeResult,
    PresentationChange,
    SortRequest,
    organize_workbook,
)
from autotarefas.organize.presentation import (
    Criterion,
    PresentationAudit,
    Verdict,
    audit_presentation,
    date_format_notes,
)
from autotarefas.organize.report import (
    ANALYSIS_REPORT_NAME,
    ReportInput,
    write_analysis_report,
)
from autotarefas.organize.sheets import (
    SheetInfo,
    SheetKind,
    candidates,
    needs_sheet_choice,
    survey_sheets,
)

__all__ = [
    "ANALYSIS_REPORT_NAME",
    "DASHBOARD_SHEET",
    "ORGANIZED_XLSX_NAME",
    "Criterion",
    "Indicator",
    "IndicatorRequest",
    "OrganizeResult",
    "PresentationAudit",
    "PresentationChange",
    "ReportInput",
    "RoleSuggestion",
    "SheetInfo",
    "SheetKind",
    "SortRequest",
    "Verdict",
    "audit_presentation",
    "build_indicators",
    "candidates",
    "date_format_notes",
    "default_request",
    "describe_source",
    "needs_sheet_choice",
    "organize_workbook",
    "suggest_roles",
    "summary_is_offerable",
    "survey_sheets",
    "write_analysis_report",
    "write_panel",
]
