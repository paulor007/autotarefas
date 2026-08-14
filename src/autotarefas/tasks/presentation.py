"""
Preservacao da apresentacao original (RF-PLA-009).

O cliente precisa reconhecer a planilha tratada como a DELE: as cores, as
larguras, o painel congelado, o formato de moeda, o autofiltro. Recriar
tudo isso celula a celula seria caro e infiel.

A estrategia aqui e outra, e mais honesta: **partir do arquivo original e
tocar apenas as celulas que a limpeza mudou.** Tudo o que ninguem mexeu
continua byte a byte como estava — inclusive formulas, validacoes,
formatacao condicional e a aparencia inteira.

Consequencias dessa escolha, todas declaradas no relatorio:

- o que o openpyxl nao sabe reescrever (graficos e imagens) e PERDIDO no
  round-trip; por isso e detectado ANTES de salvar e listado no relatorio
  (risco R-13 da documentacao);
- CSV nao tem apresentacao para preservar: quem chama cai na formatacao
  profissional do PLA-007;
- o arquivo original NUNCA e alterado: a versao tratada e sempre um
  arquivo novo.
"""

from __future__ import annotations

import math
import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openpyxl import load_workbook

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    import pandas as pd

#: Nome fixo do artefato.
TREATED_XLSX_NAME = "planilha_tratada.xlsx"

#: Extensoes que tem apresentacao para preservar.
PRESERVABLE_SUFFIXES = frozenset({".xlsx", ".xlsm"})


@dataclass(frozen=True, slots=True)
class PreservationReport:
    """O que foi preservado, o que foi aplicado e o que se perdeu."""

    source: str
    """Nome do arquivo de origem."""
    applied: int = 0
    """Celulas efetivamente reescritas com o valor tratado."""
    skipped: tuple[str, ...] = ()
    """Mudancas que nao puderam ser aplicadas (coluna/linha fora do arquivo)."""
    not_preserved: tuple[str, ...] = ()
    """Elementos que o openpyxl nao consegue reescrever (declarados, nao escondidos)."""
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def fully_preserved(self) -> bool:
        return not self.not_preserved

    def as_dict(self) -> dict[str, Any]:
        """Payload para o relatorio JSON."""
        return {
            "arquivo_original": self.source,
            "celulas_aplicadas": self.applied,
            "mudancas_nao_aplicadas": list(self.skipped),
            "nao_preservado": list(self.not_preserved),
            "observacoes": list(self.notes),
            "preservacao_total": self.fully_preserved,
        }


def supports_presentation(path: Path) -> bool:
    """O arquivo tem apresentacao que faca sentido preservar?"""
    return path.suffix.lower() in PRESERVABLE_SUFFIXES


def _lost_elements(worksheet: Any) -> list[str]:
    """
    Elementos que o openpyxl carrega mas nao reescreve.

    Sao lidos da aba ANTES de salvar: depois de salvo, a informacao de que
    existia um grafico ali simplesmente nao esta mais no arquivo, e o
    relatorio nao teria como avisar.
    """
    perdidos: list[str] = []
    graficos = getattr(worksheet, "_charts", []) or []
    imagens = getattr(worksheet, "_images", []) or []
    if graficos:
        perdidos.append(f"{len(graficos)} grafico(s) do original nao sobrevivem a regravacao")
    if imagens:
        perdidos.append(f"{len(imagens)} imagem(ns) do original nao sobrevivem a regravacao")
    return perdidos


def _header_index(worksheet: Any, header_row: int) -> dict[str, int]:
    """Mapa ``nome da coluna -> indice da coluna`` lido do proprio arquivo."""
    indices: dict[str, int] = {}
    for cell in worksheet[header_row]:
        if cell.value is None:
            continue
        nome = str(cell.value).strip()
        if nome and nome not in indices:
            indices[nome] = cell.column
    return indices


def _treated_value(
    dataframe: pd.DataFrame | None,
    line: int,
    first_data_line: int,
    column: str,
    fallback: str,
) -> object:
    """
    O valor tratado com o TIPO certo (numero continua numero).

    Vem do DataFrame processado quando ele existe: usar o texto do audit
    trail transformaria 1234.56 em "1234.56" e o Excel passaria a tratar
    o valor como texto.
    """
    if dataframe is None:
        return fallback
    indice = line - first_data_line
    if indice < 0 or indice >= len(dataframe) or column not in dataframe.columns:
        return fallback
    valor = dataframe.iloc[indice][column]
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    item = getattr(valor, "item", None)
    return item() if callable(item) else valor


def write_treated_xlsx(  # noqa: PLR0913 - tres opcionais keyword-only
    original: Path,
    destination: Path,
    changes: Sequence[Mapping[str, Any]],
    *,
    dataframe: pd.DataFrame | None = None,
    header_row: int = 1,
    sheet: str | None = None,
) -> PreservationReport:
    """
    Gera a versao tratada preservando a apresentacao do original.

    Args:
        original: arquivo XLSX/XLSM de entrada (nunca e alterado).
        destination: caminho da planilha tratada a criar.
        changes: alteracoes da limpeza (``line``, ``column``, ``after``).
        dataframe: DataFrame processado, para recuperar o valor TIPADO.
        header_row: linha fisica do cabecalho no arquivo original.
        sheet: aba a tratar. None = a aba ativa.

    Returns:
        PreservationReport com o que foi aplicado e o que nao pode ser
        preservado.

    Raises:
        ValueError: o arquivo nao e XLSX/XLSM (nao ha apresentacao a copiar).
    """
    if not supports_presentation(original):
        msg = f"apresentacao so pode ser preservada em .xlsx/.xlsm (recebido: {original.suffix})"
        raise ValueError(msg)

    destination.parent.mkdir(parents=True, exist_ok=True)
    # Copiar o arquivo e o coracao da estrategia: tudo o que nao for tocado
    # continua exatamente como o cliente entregou.
    shutil.copyfile(original, destination)

    manter_vba = original.suffix.lower() == ".xlsm"
    workbook = load_workbook(destination, keep_vba=manter_vba)
    worksheet = workbook[sheet] if sheet is not None else workbook.active

    nao_preservado = _lost_elements(worksheet)
    colunas = _header_index(worksheet, header_row)
    primeira_linha = header_row + 1

    aplicadas = 0
    ignoradas: list[str] = []
    for change in changes:
        linha = change.get("line")
        coluna = str(change.get("column", ""))
        if not isinstance(linha, int) or coluna not in colunas:
            ignoradas.append(f"linha {linha}, coluna '{coluna}': nao localizada no arquivo")
            continue
        valor = _treated_value(
            dataframe, linha, primeira_linha, coluna, str(change.get("after", ""))
        )
        worksheet.cell(row=linha, column=colunas[coluna]).value = valor
        aplicadas += 1

    workbook.save(destination)

    notas = [
        "a apresentacao veio do proprio arquivo original: so as celulas tratadas foram reescritas",
    ]
    if not nao_preservado:
        notas.append("nenhum elemento incompativel foi encontrado no original")

    return PreservationReport(
        source=original.name,
        applied=aplicadas,
        skipped=tuple(ignoradas),
        not_preserved=tuple(nao_preservado),
        notes=tuple(notas),
    )


__all__ = [
    "PRESERVABLE_SUFFIXES",
    "TREATED_XLSX_NAME",
    "PreservationReport",
    "supports_presentation",
    "write_treated_xlsx",
]
