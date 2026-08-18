"""
Painel de indicadores: tabelas e graficos a partir de papeis CONFIRMADOS.

Este modulo desenha; ele nao decide. Quem decide o que significa cada coluna
e a pessoa, na tela de revisao — sem essa confirmacao, `build_indicators`
devolve vazio e aqui nao nasce grafico nenhum.

O mesmo desenho serve dois destinos:

    relatorio_analise.xlsx   aba "Indicadores confirmados"
    planilha_organizada.xlsx aba "Dashboard", quando a pessoa pede

Nos dois casos o painel vive numa aba SEPARADA. A aba dos dados nunca recebe
grafico, total nem coluna nova.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openpyxl.chart import BarChart, LineChart, Reference

from autotarefas.tasks.xlsx_style import DATA_FONT, LABEL_FONT, TITLE_FONT

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openpyxl.worksheet.worksheet import Worksheet

    from autotarefas.organize.insights import Indicator

#: Barras demais viram borrao. O topo ja conta a historia.
MAX_BARRAS = 15

#: Indicador por data vira linha do tempo; o resto, barra.
_DIMENSAO_TEMPORAL = "mês"


def _grafico(indicador: Indicator) -> BarChart | LineChart:
    """Linha para tempo, barra para o resto — a forma segue o dado."""
    temporal = _DIMENSAO_TEMPORAL in indicador.dimension.casefold()
    grafico: BarChart | LineChart = LineChart() if temporal else BarChart()
    grafico.title = indicador.title
    grafico.height = 7
    grafico.width = 16
    return grafico


def write_panel(
    ws: Worksheet,
    indicadores: Sequence[Indicator],
    *,
    heading: str = "",
    source_note: str = "",
) -> int:
    """
    Escreve as tabelas e os graficos dos indicadores confirmados.

    Args:
        ws: aba de destino (vazia, criada por quem chama).
        indicadores: o que `build_indicators` devolveu.
        heading: titulo da aba, quando ela for um painel autonomo.
        source_note: de quais colunas os numeros vieram. Sem isso alguem pode
            achar que o sistema adivinhou o significado das colunas.

    Returns:
        A ultima linha escrita.
    """
    linha = 1
    if heading:
        ws.cell(row=linha, column=1, value=heading).font = TITLE_FONT
        linha += 1
    if source_note:
        ws.cell(row=linha, column=1, value=source_note).font = DATA_FONT
        linha += 1
    if heading or source_note:
        linha += 1

    for indicador in indicadores:
        ws.cell(row=linha, column=1, value=indicador.title).font = LABEL_FONT
        linha += 1
        ws.cell(row=linha, column=1, value=indicador.dimension).font = DATA_FONT
        ws.cell(row=linha, column=2, value=indicador.measure).font = DATA_FONT
        primeira_dado = linha + 1

        for chave, valor in indicador.rows:
            linha += 1
            ws.cell(row=linha, column=1, value=chave).font = DATA_FONT
            ws.cell(row=linha, column=2, value=round(valor, 2)).font = DATA_FONT

        if indicador.rows:
            grafico = _grafico(indicador)
            ultima = min(linha, primeira_dado + MAX_BARRAS - 1)
            grafico.add_data(
                Reference(ws, min_col=2, min_row=primeira_dado - 1, max_row=ultima),
                titles_from_data=True,
            )
            grafico.set_categories(Reference(ws, min_col=1, min_row=primeira_dado, max_row=ultima))
            ws.add_chart(grafico, f"E{primeira_dado}")

        linha += 1
        ws.cell(row=linha, column=1, value="Total").font = LABEL_FONT
        ws.cell(row=linha, column=2, value=round(indicador.total, 2)).font = LABEL_FONT
        if indicador.ignored_rows:
            linha += 1
            ws.cell(
                row=linha,
                column=1,
                value=(
                    f"{indicador.ignored_rows} linha(s) ignorada(s): o valor não pôde "
                    "ser lido como número"
                ),
            ).font = DATA_FONT
        linha += 3

    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 18
    return linha


def describe_source(value: str, category: str, date: str) -> str:
    """Frase que declara de onde vieram os numeros do painel."""
    partes = [f"valor: {value}"]
    if category:
        partes.append(f"categoria: {category}")
    if date:
        partes.append(f"data: {date}")
    return "Calculado a partir das colunas que você confirmou — " + "; ".join(partes) + "."


__all__ = ["MAX_BARRAS", "describe_source", "write_panel"]
