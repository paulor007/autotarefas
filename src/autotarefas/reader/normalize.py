"""
Normalizacao segura — com trilha.

Converte o texto fiel do arquivo em valores tipados, e REGISTRA cada
mudanca numa :class:`Conversion`. A regra de ouro do AutoTarefas vale
aqui como vale na limpeza: **nada e inventado, nada e apagado**.

O que este modulo NUNCA faz:
- apagar linha (vazia, duplicada ou de rodape)
- converter valor ambiguo "no chute" (fica como esta + aviso)
- alterar identificador (zeros a esquerda sao preservados)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from autotarefas.reader.result import Conversion
from autotarefas.reader.types import (
    RawCell,
    detect_decimal_separator,
)

if TYPE_CHECKING:
    from autotarefas.reader.result import CellType

_EXCEL_EPOCH = datetime(1899, 12, 30)
_SERIAL_MIN = 1
_SERIAL_MAX = 2_958_465  # 31/12/9999
_CURRENCY_SYMBOLS = ("R$", "US$", "$", "€", "£")

#: Data-hora e testada ANTES de data-so: senao "01/12/2019 14:30" casaria
#: com "%d/%m/%Y" e PERDERIA a hora.
_DATETIME_FORMATS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)
_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d")


def _parse_date_text(texto: str) -> datetime | None:
    """Data em texto: tenta data-hora primeiro, depois data-so."""
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(texto.split(" ")[0], fmt)
        except ValueError:
            continue
    return None


def _strip_symbols(text: str) -> str:
    limpo = text.strip()
    for symbol in _CURRENCY_SYMBOLS:
        if limpo.upper().startswith(symbol):
            limpo = limpo[len(symbol) :].strip()
            break
        if limpo.upper().endswith(symbol):
            limpo = limpo[: -len(symbol)].strip()
            break
    return limpo.replace("%", "").replace(" ", "").strip()


def parse_number(text: str, decimal_sep: str) -> float | None:
    """
    Converte texto em numero, respeitando o separador decimal da COLUNA.

    `decimal_sep` vem de `detect_decimal_separator` — nunca e adivinhado
    valor a valor.
    """
    limpo = _strip_symbols(text)
    if not limpo:
        return None

    negativo = limpo.startswith("-")
    limpo = limpo.lstrip("+-")

    if decimal_sep == ",":
        limpo = limpo.replace(".", "").replace(",", ".")
    elif decimal_sep == ".":
        limpo = limpo.replace(",", "")
    else:
        # sem separador decimal na coluna: qualquer '.' ou ',' e MILHAR
        limpo = limpo.replace(".", "").replace(",", "")

    try:
        valor = float(limpo)
    except ValueError:
        return None
    return -valor if negativo else valor


def parse_date(value: object) -> datetime | None:
    """Converte data nativa, serial do Excel ou texto (dd/mm/aaaa, ISO)."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and _SERIAL_MIN <= float(value) <= _SERIAL_MAX:
        return _EXCEL_EPOCH + timedelta(days=float(value))
    if isinstance(value, str) and value.strip():
        return _parse_date_text(value.strip())
    return None


def parse_bool(text: str) -> bool | None:
    """Converte 'sim'/'nao'/'true'/'false'/... em booleano."""
    baixo = text.strip().lower()
    if baixo in {"sim", "true", "verdadeiro", "v", "yes", "y", "s", "1"}:
        return True
    if baixo in {"nao", "não", "false", "falso", "f", "no", "n", "0"}:
        return False
    return None


def _normalized_text(valor: object) -> str:
    """Representacao textual estavel do valor normalizado (para a trilha)."""
    if isinstance(valor, datetime):
        if valor.hour or valor.minute or valor.second:
            return valor.isoformat(sep=" ")
        return valor.date().isoformat()
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def _convert(
    cell: RawCell,
    col_type: CellType,
    decimal_sep: str,
) -> tuple[object, str]:
    """Converte UMA celula. Retorna (valor, regra_aplicada)."""
    if col_type in ("data", "data_hora"):
        return _convert_date(cell)
    if col_type in ("moeda", "decimal", "inteiro", "percentual"):
        return _convert_number(cell, col_type, decimal_sep)
    if col_type == "booleano":
        return _convert_bool(cell)
    # identificador, texto, erro, misto, vazio: preservados como estao
    return cell.text, ""


def _convert_date(cell: RawCell) -> tuple[object, str]:
    valor = parse_date(cell.value)
    if valor is None:
        return cell.text, ""
    if isinstance(cell.value, (datetime, date)):
        return valor, ""  # ja era data nativa: nada mudou
    regra = "data_serial" if isinstance(cell.value, (int, float)) else "data_texto"
    return valor, regra


def _convert_number(cell: RawCell, col_type: CellType, decimal_sep: str) -> tuple[object, str]:
    valor = parse_number(cell.text, decimal_sep)
    if valor is None:
        return cell.text, ""
    if isinstance(cell.value, (int, float)):
        return cell.value, ""  # ja era numero: nada mudou
    regra = {
        "moeda": "moeda_br" if decimal_sep == "," else "moeda_us",
        "percentual": "percentual_texto",
    }.get(col_type, "numero_texto")
    return valor, regra


def _convert_bool(cell: RawCell) -> tuple[object, str]:
    valor = parse_bool(cell.text)
    if valor is None:
        return cell.text, ""
    regra = "" if isinstance(cell.value, bool) else "booleano_texto"
    return valor, regra


def normalize_column(
    cells: list[RawCell],
    col_type: CellType,
    col_name: str,
    first_data_row: int,
) -> tuple[list[object], list[Conversion]]:
    """
    Normaliza uma coluna inteira e devolve a trilha das mudancas.

    `first_data_row` e a linha FISICA da primeira linha de dados — as
    conversoes usam a mesma numeracao da planilha aberta no Excel.
    """
    textos = [c.text for c in cells if not c.is_empty]
    decimal_sep = (
        detect_decimal_separator(textos)
        if col_type in ("moeda", "decimal", "inteiro", "percentual")
        else ""
    )

    valores: list[object] = []
    conversoes: list[Conversion] = []

    for offset, cell in enumerate(cells):
        if cell.is_empty:
            valores.append(None)
            continue

        valor, regra = _convert(cell, col_type, decimal_sep)
        valores.append(valor)

        if regra:
            novo = _normalized_text(valor)
            if novo != cell.text:
                conversoes.append(
                    Conversion(
                        row=first_data_row + offset,
                        column=col_name,
                        original=cell.text,
                        normalized=novo,
                        rule=regra,
                    )
                )

    return valores, conversoes


__all__ = [
    "normalize_column",
    "parse_bool",
    "parse_date",
    "parse_number",
]
