"""
Geracao da versao ORGANIZADA de uma planilha (`planilha_organizada.xlsx`).

Parte de uma copia do arquivo original e aplica **apenas mudancas de
apresentacao seguras** — mais, quando confirmadas, as correcoes de valor e
uma ordenacao escolhida pela pessoa. Cada mudanca vira uma linha de
evidencia, para que o "antes e depois" do relatorio nao dependa de memoria.

O que NUNCA muda aqui:

    valores (fora das correcoes confirmadas)   formulas
    identificadores e zeros a esquerda         nomes das colunas
    ordem das linhas (sem confirmacao)         regras de negocio

Duas recusas explicitas, porque o silencio seria pior:

- **ordenar com formulas na aba**: uma formula que aponta para a linha 12
  passaria a apontar para outro registro. Recusamos e explicamos.
- **coluna de ordenacao inexistente**: erro de uso, nao "ordenou do jeito
  que deu".

O arquivo original nunca e sobrescrito.
"""

from __future__ import annotations

import math
import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from autotarefas.organize.dashboard import describe_source, write_panel
from autotarefas.tasks.presentation import PRESERVABLE_SUFFIXES

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from openpyxl.worksheet.worksheet import Worksheet

    from autotarefas.organize.insights import Indicator, IndicatorRequest

#: Nome do artefato principal desta jornada.
ORGANIZED_XLSX_NAME = "planilha_organizada.xlsx"

#: Aba do painel. Nasce SEPARADA: a aba dos dados nunca recebe grafico.
DASHBOARD_SHEET = "Dashboard"

#: Limites de largura: legivel sem empurrar a tabela para fora da tela.
LARGURA_MINIMA = 10
LARGURA_MAXIMA = 60

#: Estilo do cabecalho — discreto e profissional, sem "enfeite".
_CABECALHO_FILL = PatternFill("solid", fgColor="1F4E78")
_CABECALHO_FONT = Font(bold=True, color="FFFFFF")
_CABECALHO_ALINHAMENTO = Alignment(horizontal="center", vertical="center", wrap_text=False)

#: Formato de texto: marca um identificador. Nunca convertemos essas celulas.
_FORMATO_TEXTO = "@"


@dataclass(frozen=True, slots=True)
class PresentationChange:
    """Uma mudanca de APRESENTACAO (nenhum valor foi tocado)."""

    scope: str
    """Onde: 'planilha', 'cabeçalho' ou o nome da coluna."""
    kind: str
    """O que: largura_ajustada, filtro_aplicado, painel_congelado, ..."""
    detail: str


@dataclass(frozen=True, slots=True)
class SortRequest:
    """Ordenacao CONFIRMADA pela pessoa (coluna + direcao)."""

    column: str
    ascending: bool = True

    def describe(self) -> str:
        return f"{self.column} ({'crescente' if self.ascending else 'decrescente'})"


@dataclass(frozen=True, slots=True)
class OrganizeResult:
    """O que a organizacao fez — e o que se recusou a fazer."""

    path: Path
    sheet: str
    changes: tuple[PresentationChange, ...] = ()
    value_changes_applied: int = 0
    sorted_by: str = ""
    refusals: tuple[str, ...] = ()
    not_preserved: tuple[str, ...] = ()
    limitations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def touched(self) -> bool:
        """Alguma coisa mudou de fato?"""
        return bool(self.changes) or bool(self.sorted_by) or self.value_changes_applied > 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "arquivo": self.path.name,
            "aba": self.sheet,
            "mudancas_de_apresentacao": [
                {"onde": c.scope, "tipo": c.kind, "detalhe": c.detail} for c in self.changes
            ],
            "valores_corrigidos": self.value_changes_applied,
            "ordenado_por": self.sorted_by,
            "recusas": list(self.refusals),
            "nao_preservado": list(self.not_preserved),
        }


# ============================================================
# Fatos da aba
# ============================================================


def _titulos(ws: Worksheet, header_row: int) -> dict[str, int]:
    """Titulo -> indice da coluna (o primeiro vence, como no leitor)."""
    indices: dict[str, int] = {}
    for celula in ws[header_row]:
        if celula.value is None:
            continue
        nome = str(celula.value).strip()
        if nome and nome not in indices:
            indices[nome] = int(celula.column)
    return indices


def _tem_formula(ws: Worksheet, header_row: int) -> bool:
    for linha in ws.iter_rows(min_row=header_row + 1):
        for celula in linha:
            if isinstance(celula.value, str) and celula.value.startswith("="):
                return True
    return False


def _formato_dominante(ws: Worksheet, coluna: int, header_row: int, ultima: int) -> str | None:
    """O formato que a maioria das celulas da coluna ja usa."""
    contagem: dict[str, int] = {}
    for linha in range(header_row + 1, min(ultima, header_row + 200) + 1):
        celula = ws.cell(row=linha, column=coluna)
        if celula.value is None:
            continue
        contagem[celula.number_format] = contagem.get(celula.number_format, 0) + 1
    if not contagem:
        return None
    return max(contagem, key=lambda formato: contagem[formato])


def _largura_ideal(ws: Worksheet, coluna: int, ultima: int) -> int:
    maior = 0
    for linha in range(1, min(ultima, 200) + 1):
        valor = ws.cell(row=linha, column=coluna).value
        if valor is not None:
            maior = max(maior, len(str(valor)))
    return max(LARGURA_MINIMA, min(maior + 2, LARGURA_MAXIMA))


def _alinhamento_por_tipo(valor: Any, formato: str) -> str | None:
    """Números à direita, datas ao centro, texto à esquerda."""
    if formato == _FORMATO_TEXTO:
        return "left"
    if isinstance(valor, bool):
        return "center"
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return "right"
    if hasattr(valor, "year") and hasattr(valor, "month"):
        return "center"
    return "left"


# ============================================================
# Aplicacao
# ============================================================


def _aplicar_cabecalho(ws: Worksheet, header_row: int) -> list[PresentationChange]:
    mudancas: list[PresentationChange] = []
    tocou = False
    for celula in ws[header_row]:
        if celula.value is None:
            continue
        celula.font = _CABECALHO_FONT
        celula.fill = _CABECALHO_FILL
        celula.alignment = _CABECALHO_ALINHAMENTO
        tocou = True
    if tocou:
        mudancas.append(
            PresentationChange(
                "cabeçalho",
                "cabecalho_formatado",
                "títulos em negrito, fundo azul-escuro e centralizados",
            )
        )
    return mudancas


def _aplicar_larguras(
    ws: Worksheet, header_row: int, colunas: int, ultima: int
) -> list[PresentationChange]:
    mudancas: list[PresentationChange] = []
    for indice in range(1, colunas + 1):
        letra = get_column_letter(indice)
        atual = ws.column_dimensions[letra].width
        ideal = _largura_ideal(ws, indice, ultima)
        if atual is not None and abs(float(atual) - ideal) < 1:
            continue
        ws.column_dimensions[letra].width = ideal
        titulo = str(ws.cell(row=header_row, column=indice).value or letra)
        anterior = f"{float(atual):.1f}" if atual else "padrão"
        mudancas.append(
            PresentationChange(titulo, "largura_ajustada", f"largura {anterior} → {ideal}")
        )
    return mudancas


def _aplicar_formatos_e_alinhamento(
    ws: Worksheet, header_row: int, colunas: int, ultima: int
) -> list[PresentationChange]:
    """
    Uniformiza o formato de cada coluna e alinha por tipo.

    O formato ESCOLHIDO e o que a propria coluna ja usa mais — nao um
    padrao nosso. Assim uma planilha em `dd/mm/yyyy` nao vira `mm-dd-yy`
    porque "ficou melhor". Celulas marcadas como TEXTO (`@`) ficam como
    estao: e la que moram os identificadores com zero a esquerda.
    """
    mudancas: list[PresentationChange] = []
    for indice in range(1, colunas + 1):
        dominante = _formato_dominante(ws, indice, header_row, ultima)
        if dominante is None:
            continue
        titulo = str(ws.cell(row=header_row, column=indice).value or get_column_letter(indice))
        divergentes = 0
        for linha in range(header_row + 1, ultima + 1):
            celula = ws.cell(row=linha, column=indice)
            if celula.value is None:
                continue
            if celula.number_format not in {dominante, _FORMATO_TEXTO}:
                celula.number_format = dominante
                divergentes += 1
            alinhamento = _alinhamento_por_tipo(celula.value, celula.number_format)
            if alinhamento and celula.alignment.horizontal != alinhamento:
                celula.alignment = Alignment(horizontal=alinhamento, vertical="center")
        if divergentes:
            mudancas.append(
                PresentationChange(
                    titulo,
                    "formato_padronizado",
                    f"{divergentes} célula(s) alinhadas ao formato '{dominante}' da coluna",
                )
            )
    if colunas:
        mudancas.append(
            PresentationChange(
                "planilha",
                "alinhamento_por_tipo",
                "números à direita, datas ao centro, texto à esquerda",
            )
        )
    return mudancas


def _aplicar_filtro_e_painel(
    ws: Worksheet, header_row: int, colunas: int, ultima: int
) -> list[PresentationChange]:
    mudancas: list[PresentationChange] = []
    referencia = f"A{header_row}:{get_column_letter(colunas)}{ultima}"
    if ws.auto_filter.ref != referencia:
        ws.auto_filter.ref = referencia
        mudancas.append(
            PresentationChange("planilha", "filtro_aplicado", f"autofiltro em {referencia}")
        )
    alvo = f"A{header_row + 1}"
    if ws.freeze_panes != alvo:
        ws.freeze_panes = alvo
        mudancas.append(
            PresentationChange("planilha", "painel_congelado", f"cabeçalho fixo em {alvo}")
        )
    return mudancas


def _aplicar_correcoes(
    ws: Worksheet,
    changes: Sequence[Mapping[str, Any]],
    titulos: dict[str, int],
) -> int:
    """Reescreve so as celulas que a limpeza confirmou (valor tratado)."""
    aplicadas = 0
    for mudanca in changes:
        linha = mudanca.get("line")
        coluna = str(mudanca.get("column", ""))
        if not isinstance(linha, int) or coluna not in titulos:
            continue
        ws.cell(row=linha, column=titulos[coluna]).value = mudanca.get("after")
        aplicadas += 1
    return aplicadas


def _ordenar(  # noqa: PLR0913 - a aba e as suas dimensoes vem juntas
    ws: Worksheet,
    pedido: SortRequest,
    titulos: dict[str, int],
    header_row: int,
    colunas: int,
    ultima: int,
) -> tuple[bool, str]:
    """
    Reordena as LINHAS de dados pela coluna escolhida.

    Returns:
        (aplicou, motivo_da_recusa). Recusa nao e falha: e o sistema
        dizendo que ordenar ali quebraria outra coisa.
    """
    if pedido.column not in titulos:
        return False, f"a coluna '{pedido.column}' não existe nesta aba"
    if _tem_formula(ws, header_row):
        return False, (
            "esta aba tem fórmulas: reordenar as linhas mudaria o que cada fórmula "
            "aponta. A ordem original foi mantida."
        )

    indice = titulos[pedido.column]
    linhas: list[list[Any]] = []
    for numero in range(header_row + 1, ultima + 1):
        valores = [ws.cell(row=numero, column=c).value for c in range(1, colunas + 1)]
        if all(v is None for v in valores):
            continue
        linhas.append(valores)

    def chave(valores: list[Any]) -> tuple[int, str]:
        # Ordem estavel e previsivel entre tipos diferentes: vazio por
        # ultimo, numeros antes de texto, texto sem diferenciar caixa.
        valor = valores[indice - 1]
        if valor is None or (isinstance(valor, float) and math.isnan(valor)):
            return (2, "")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return (0, f"{float(valor):030.6f}")
        return (1, str(valor).casefold())

    linhas.sort(key=chave, reverse=not pedido.ascending)

    for deslocamento, valores in enumerate(linhas):
        for coluna, valor in enumerate(valores, start=1):
            ws.cell(row=header_row + 1 + deslocamento, column=coluna).value = valor
    return True, ""


def _adicionar_dashboard(
    workbook: Any,
    indicadores: Sequence[Indicator],
    pedido: IndicatorRequest,
) -> PresentationChange | None:
    """
    Cria a aba do painel a partir dos papeis que a pessoa confirmou.

    Fica na frente das outras de proposito: quem abre a planilha ve primeiro o
    resumo e depois os dados. A aba dos dados nao e tocada — nem grafico, nem
    total, nem coluna nova.
    """
    if not indicadores:
        return None
    if DASHBOARD_SHEET in workbook.sheetnames:
        del workbook[DASHBOARD_SHEET]
    ws = workbook.create_sheet(DASHBOARD_SHEET, 0)
    write_panel(
        ws,
        indicadores,
        heading="Dashboard",
        source_note=describe_source(
            pedido.value_column, pedido.category_column, pedido.date_column
        ),
    )
    return PresentationChange(
        scope=DASHBOARD_SHEET,
        kind="dashboard_adicionado",
        detail=f"{len(indicadores)} indicador(es) confirmado(s), em aba separada",
    )


def _elementos_nao_preservados(ws: Worksheet) -> list[str]:
    perdidos: list[str] = []
    if getattr(ws, "_charts", None):
        perdidos.append(f"{len(ws._charts)} gráfico(s) do original não sobrevivem à regravação")
    if getattr(ws, "_images", None):
        perdidos.append(f"{len(ws._images)} imagem(ns) do original não sobrevivem à regravação")
    return perdidos


def organize_workbook(  # noqa: PLR0913 - opcionais keyword-only, uma etapa cada
    original: Path,
    destination: Path,
    *,
    sheet: str | None = None,
    header_row: int = 1,
    apply_format: bool = True,
    sort: SortRequest | None = None,
    value_changes: Sequence[Mapping[str, Any]] = (),
    dashboard: Sequence[Indicator] = (),
    dashboard_request: IndicatorRequest | None = None,
) -> OrganizeResult:
    """
    Gera a versao organizada a partir de uma COPIA do original.

    Args:
        original: arquivo XLSX/XLSM de entrada (nunca alterado).
        destination: caminho da planilha organizada.
        sheet: aba a organizar. None = a ativa.
        header_row: linha fisica do cabecalho.
        apply_format: aplica as melhorias de apresentacao.
        sort: ordenacao confirmada (coluna + direcao). None = ordem original.
        value_changes: correcoes de valor ja confirmadas (line/column/after).
        dashboard: indicadores CONFIRMADOS. Vazio = nenhuma aba de painel.
        dashboard_request: os papeis que a pessoa confirmou, para declarar na
            aba de onde os numeros vieram.

    Returns:
        OrganizeResult com cada mudanca, as recusas e o que nao pode ser
        preservado.

    Raises:
        ValueError: a entrada nao e XLSX/XLSM.
    """
    if original.suffix.lower() not in PRESERVABLE_SUFFIXES:
        msg = f"a versao organizada parte de um .xlsx/.xlsm (recebido: {original.suffix})"
        raise ValueError(msg)

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, destination)

    workbook = load_workbook(destination, keep_vba=original.suffix.lower() == ".xlsm")
    ws = workbook[sheet] if sheet is not None else workbook.active
    if ws is None:  # pragma: no cover
        msg = "planilha sem aba ativa"
        raise ValueError(msg)

    nao_preservado = _elementos_nao_preservados(ws)
    titulos = _titulos(ws, header_row)
    colunas = int(ws.max_column or 0)
    ultima = int(ws.max_row or header_row)

    aplicadas = _aplicar_correcoes(ws, value_changes, titulos)

    recusas: list[str] = []
    ordenado = ""
    if sort is not None:
        ok, motivo = _ordenar(ws, sort, titulos, header_row, colunas, ultima)
        if ok:
            ordenado = sort.describe()
        else:
            recusas.append(motivo)

    mudancas: list[PresentationChange] = []
    if apply_format:
        mudancas.extend(_aplicar_cabecalho(ws, header_row))
        mudancas.extend(_aplicar_formatos_e_alinhamento(ws, header_row, colunas, ultima))
        mudancas.extend(_aplicar_larguras(ws, header_row, colunas, ultima))
        mudancas.extend(_aplicar_filtro_e_painel(ws, header_row, colunas, ultima))

    if dashboard and dashboard_request is not None:
        painel = _adicionar_dashboard(workbook, dashboard, dashboard_request)
        if painel is not None:
            mudancas.append(painel)

    workbook.save(destination)
    workbook.close()

    return OrganizeResult(
        path=destination,
        sheet=str(ws.title),
        changes=tuple(mudancas),
        value_changes_applied=aplicadas,
        sorted_by=ordenado,
        refusals=tuple(recusas),
        not_preserved=tuple(nao_preservado),
        limitations=(
            "só a apresentação muda: valores, fórmulas e nomes de coluna ficam como estão",
            "identificadores formatados como texto continuam texto (zeros à esquerda intactos)",
            "a ordem das linhas só muda com ordenação confirmada",
        ),
    )


__all__ = [
    "DASHBOARD_SHEET",
    "LARGURA_MAXIMA",
    "LARGURA_MINIMA",
    "ORGANIZED_XLSX_NAME",
    "OrganizeResult",
    "PresentationChange",
    "SortRequest",
    "organize_workbook",
]
