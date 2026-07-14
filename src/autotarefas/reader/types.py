"""
Inferencia de tipos — agnostica de dominio.

Este modulo nao sabe o que e CPF, SKU, venda ou estoque. Ele so sabe
distinguir NUMERO de TEXTO de DATA de IDENTIFICADOR, olhando a forma dos
valores — nunca o nome da coluna. (A planilha de vendas que motivou este
trabalho tem uma coluna chamada "ID Loja" que contem NOMES de loja: o nome
da coluna mente, os valores nao.)

Duas decisoes estruturais:

1. No XLSX, o Excel JA AFIRMA o tipo (``data_type`` + ``number_format``).
   Nao ha o que inferir — ha o que CLASSIFICAR. A inferencia pesada so
   e necessaria para valores que chegam como TEXTO (todo CSV, e as celulas
   "numero salvo como texto" do XLSX).

2. Ambiguidade decimal ("1.234" e mil-e-duzentos ou um-virgula-dois?) NAO
   se resolve celula a celula. Resolve-se pela COLUNA inteira.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autotarefas.reader.result import CellType

# --- Constantes de reconhecimento -------------------------------------------

#: Valores de erro do Excel (chegam como texto).
EXCEL_ERRORS = frozenset(
    {
        "#DIV/0!",
        "#N/A",
        "#N/D",
        "#NAME?",
        "#NOME?",
        "#NULL!",
        "#NULO!",
        "#NUM!",
        "#NUM.!",
        "#REF!",
        "#VALUE!",
        "#VALOR!",
    }
)

_TRUE_WORDS = frozenset({"sim", "true", "verdadeiro", "v", "yes", "y", "s"})
_FALSE_WORDS = frozenset({"nao", "não", "false", "falso", "f", "no", "n"})
_BOOL_WORDS = _TRUE_WORDS | _FALSE_WORDS

_CURRENCY_SYMBOLS = ("R$", "US$", "$", "€", "£")

#: Padroes de data em texto (dd/mm/aaaa, aaaa-mm-dd, dd-mm-aaaa).
_DATE_PATTERNS = (
    (re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$"), "dmy"),
    (re.compile(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$"), "ymd"),
)
_TIME_RE = re.compile(r"\d{1,2}:\d{2}(:\d{2})?")

#: Digitos com mascara (000.000.000-00, 00000-000, 00.000.000/0000-00...).
_MASKED_DIGITS_RE = re.compile(r"^[\d][\d.\-/ ]*[\d]$")
_ONLY_DIGITS_RE = re.compile(r"^\d+$")

#: Numero "cru" (aceita separadores; a desambiguacao vem depois).
_NUMERIC_RE = re.compile(r"^[+-]?[\d.,]*\d$")

_ID_MIN_LENGTH = 4
_HIGH_CARDINALITY = 0.5
_THOUSAND_GROUP = 3
#: Faixa dos seriais de data do Excel: 01/01/2000 a 01/01/2050.
_SERIAL_DATE_MIN = 36526
_SERIAL_DATE_MAX = 54789


def _as_text(value: object) -> str:
    """Representacao textual BRUTA de uma celula (sem strip)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


@dataclass(frozen=True, slots=True)
class RawCell:
    """Uma celula como o arquivo a entregou (antes de qualquer conversao)."""

    value: object
    excel_type: str = ""
    """'n','s','d','f','e','b' no XLSX; '' no CSV (tudo e texto)."""
    number_format: str = ""

    #: Calculados uma unica vez. Eram propriedades — e o perfilador mostrou
    #: 4,7 MILHOES de recalculos numa planilha de 7 mil linhas.
    raw: str = field(init=False, default="", compare=False)
    """O texto EXATO do arquivo, com os espacos. Base do original_dataframe."""
    text: str = field(init=False, default="", compare=False)
    """O texto sem espacos nas pontas. Base da classificacao e da conversao."""
    is_empty: bool = field(init=False, default=True, compare=False)

    def __post_init__(self) -> None:
        bruto = _as_text(self.value)
        limpo = bruto.strip()
        object.__setattr__(self, "raw", bruto)
        object.__setattr__(self, "text", limpo)
        object.__setattr__(self, "is_empty", limpo == "")


# --- Classificacao de UMA celula --------------------------------------------


def _looks_like_date_text(text: str) -> CellType | None:
    """Data em texto? Retorna 'data'/'data_hora' ou None."""
    base = text
    has_time = bool(_TIME_RE.search(text))
    if has_time:
        base = _TIME_RE.sub("", text).strip()
    for pattern, order in _DATE_PATTERNS:
        match = pattern.match(base)
        if not match:
            continue
        parts = [int(p) for p in match.groups()]
        day, month = (parts[0], parts[1]) if order == "dmy" else (parts[2], parts[1])
        max_month = 12
        max_day = 31
        if 1 <= month <= max_month and 1 <= day <= max_day:
            return "data_hora" if has_time else "data"
    return None


def _strip_currency(text: str) -> tuple[str, bool]:
    """Remove simbolo de moeda. Retorna (resto, tinha_moeda)."""
    cleaned = text
    found = False
    for symbol in _CURRENCY_SYMBOLS:
        if cleaned.upper().startswith(symbol) or cleaned.upper().endswith(symbol):
            cleaned = cleaned.upper().replace(symbol, "", 1).strip()
            found = True
            break
    return cleaned, found


def _rule_error(text: str) -> CellType | None:
    return "erro" if text.upper() in EXCEL_ERRORS else None


def _rule_bool(text: str) -> CellType | None:
    return "booleano" if text.lower() in _BOOL_WORDS else None


def _rule_date(text: str) -> CellType | None:
    return _looks_like_date_text(text)


def _rule_percent(text: str) -> CellType | None:
    if text.endswith("%") and _NUMERIC_RE.match(text[:-1].strip()):
        return "percentual"
    return None


def _rule_currency(text: str) -> CellType | None:
    rest, had = _strip_currency(text)
    if had and _NUMERIC_RE.match(rest.replace(" ", "")):
        return "moeda"
    return None


def _rule_number(text: str) -> CellType | None:
    if not _NUMERIC_RE.match(text):
        return None
    # inteiro vs decimal e decidido na coluna (separadores sao ambiguos)
    return "inteiro" if _ONLY_DIGITS_RE.match(text.lstrip("+-")) else "decimal"


#: Ordem importa: o primeiro que casar vence.
_TEXT_RULES: tuple[Callable[[str], CellType | None], ...] = (
    _rule_error,
    _rule_bool,
    _rule_date,
    _rule_percent,
    _rule_currency,
    _rule_number,
)


def classify_text(text: str) -> CellType:
    """
    Classifica um valor de TEXTO (CSV, ou 'numero como texto' do XLSX).

    Nao decide identificador nem separador decimal: isso depende da coluna
    inteira e e resolvido em `infer_column_type`.
    """
    if text == "":
        return "vazio"
    for rule in _TEXT_RULES:
        tipo = rule(text)
        if tipo is not None:
            return tipo
    return "texto"


def _date_type(value: object) -> CellType:
    if isinstance(value, datetime) and (value.hour or value.minute or value.second):
        return "data_hora"
    return "data"


def _numeric_type(cell: RawCell) -> CellType:
    fmt = (cell.number_format or "").upper()
    if "%" in fmt:
        return "percentual"
    if any(sym in fmt for sym in ("R$", "$", "€", "£")):
        return "moeda"
    as_float = float(cell.value) if isinstance(cell.value, (int, float)) else 0.0
    return "inteiro" if as_float.is_integer() else "decimal"


def _from_excel_metadata(cell: RawCell) -> CellType | None:
    """O que o Excel JA AFIRMA sobre a celula (None = nao afirma nada)."""
    if cell.excel_type == "e":
        return "erro"
    if cell.excel_type == "b" or isinstance(cell.value, bool):
        return "booleano"
    if cell.excel_type == "d" or isinstance(cell.value, (datetime, date)):
        return _date_type(cell.value)
    if cell.excel_type == "n" or isinstance(cell.value, (int, float)):
        return _numeric_type(cell)
    return None


def classify_cell(cell: RawCell) -> CellType:
    """Classifica uma celula usando o que o Excel ja afirma (quando afirma)."""
    if cell.is_empty:
        return "vazio"
    tipo = _from_excel_metadata(cell)
    return tipo if tipo is not None else classify_text(cell.text)


# --- Decisoes de COLUNA ------------------------------------------------------


def looks_like_identifier(texts: list[str], *, from_numbers: bool = False) -> tuple[bool, str]:
    """
    A coluna parece um IDENTIFICADOR (e nao um numero)?

    Criterios AGNOSTICOS (nunca o nome da coluna):
      (a) algum valor tem ZERO A ESQUERDA          -> certeza alta
      (b) so-digitos, MESMO comprimento (>= 4) E alta cardinalidade
      (c) todos com mascara de digitos (000.000.000-00, 00000-000, ...)

    `from_numbers=True` (a coluna veio do Excel como NUMERO) desliga as
    heuristicas: se o Excel guardou como numero, e numero. Isso evita o
    falso positivo classico — uma coluna de ANOS (2019, 2020, 2021) tambem
    tem "digitos de comprimento fixo" e viraria identificador. Para essas
    colunas, o leitor apenas OBSERVA ("possivel identificador"), sem decidir.

    Identificador e preservado como TEXTO: "00123" nunca vira 123.
    """
    valores = [t for t in texts if t]
    if not valores or from_numbers:
        return False, ""

    if any(_ONLY_DIGITS_RE.match(v) and len(v) > 1 and v[0] == "0" for v in valores):
        return True, "zero a esquerda"

    if all(_ONLY_DIGITS_RE.match(v) for v in valores):
        tamanhos = {len(v) for v in valores}
        distintos = len(set(valores)) / len(valores)
        if (
            len(tamanhos) == 1
            and next(iter(tamanhos)) >= _ID_MIN_LENGTH
            and distintos > _HIGH_CARDINALITY
        ):
            return True, "digitos de comprimento fixo, valores quase todos distintos"

    mascarados = [
        v
        for v in valores
        if _MASKED_DIGITS_RE.match(v)
        and not _ONLY_DIGITS_RE.match(v)
        and any(c.isdigit() for c in v)
        and any(c in ".-/" for c in v)
    ]
    if len(mascarados) == len(valores):
        return True, "mascara de digitos"

    return False, ""


def detect_decimal_separator(texts: list[str]) -> str:
    """
    Descobre o separador DECIMAL da coluna: ',', '.' ou '' (indefinido).

    Regra: um separador so e decimal se, em algum valor, o grupo depois dele
    NAO tiver exatamente 3 digitos (milhar sempre tem 3).
      "10,25"    -> virgula e decimal (BR)
      "1.234"    -> ambiguo isolado; sem outro sinal, e MILHAR
      "1.234,56" -> virgula e decimal, ponto e milhar
    """
    virgula_decimal = False
    ponto_decimal = False
    for raw in texts:
        limpo, _ = _strip_currency(raw.replace("%", "").strip())
        limpo = limpo.replace(" ", "")
        if "," in limpo:
            depois = limpo.rsplit(",", 1)[1]
            if depois.isdigit() and len(depois) != _THOUSAND_GROUP:
                virgula_decimal = True
        if "." in limpo:
            depois = limpo.rsplit(".", 1)[1]
            if depois.isdigit() and len(depois) != _THOUSAND_GROUP:
                ponto_decimal = True

    if virgula_decimal and not ponto_decimal:
        return ","
    if ponto_decimal and not virgula_decimal:
        return "."
    if virgula_decimal and ponto_decimal:
        return ","  # "1.234,56" e o caso classico: virgula manda
    return ""


def _dominant(counts: dict[CellType, int], total: int) -> tuple[CellType, float]:
    """Tipo dominante e sua confianca (ignorando vazios)."""
    if not counts:
        return "vazio", 1.0
    tipo, quantos = max(counts.items(), key=lambda kv: kv[1])
    return tipo, (quantos / total if total else 0.0)


def _merge_numeric(counts: dict[CellType, int]) -> dict[CellType, int]:
    """inteiro + decimal na mesma coluna = decimal (nao e 'misto')."""
    if counts.get("inteiro") and counts.get("decimal"):
        counts = dict(counts)
        counts["decimal"] += counts.pop("inteiro")
    return counts


@dataclass(frozen=True, slots=True)
class ColumnTyping:
    """O que a inferencia descobriu sobre uma coluna."""

    inferred_type: CellType
    confidence: float
    observations: list[str]
    type_counts: dict[str, int]
    """Distribuicao dos tipos observados (ex.: {'inteiro': 95, 'texto': 5}).

    Estruturado de proposito: a perfilagem precisa CONTAR os tipos, e
    extrair numeros de uma frase seria fragil.
    """


def infer_column_type(cells: list[RawCell]) -> ColumnTyping:
    """
    Infere o tipo de uma coluna inteira.

    Returns:
        ColumnTyping. As observacoes sao OBSERVACOES, nunca conclusoes:
        ex. "possivel identificador (alta cardinalidade)" — quem decide se
        aquilo e uma chave e o perfil/usuario, nao o leitor.
    """
    observacoes: list[str] = []
    preenchidas = [c for c in cells if not c.is_empty]
    textos = [c.text for c in preenchidas]

    if not textos:
        return ColumnTyping("vazio", 1.0, ["coluna inteiramente vazia"], {})

    counts: dict[CellType, int] = {}
    for cell in preenchidas:
        tipo_celula = classify_cell(cell)
        counts[tipo_celula] = counts.get(tipo_celula, 0) + 1

    counts = _merge_numeric(counts)
    tipo, confianca = _dominant(counts, len(textos))
    distribuicao = {str(k): v for k, v in sorted(counts.items())}

    if len(counts) > 1:
        detalhe = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        return ColumnTyping(
            "misto", confianca, [f"tipos misturados na coluna ({detalhe})"], distribuicao
        )

    # (a) IDENTIFICADOR so compete com numero e texto — nunca com data,
    # booleano ou erro. Sem esta guarda, "01/12/2019" casaria com a
    # heuristica de "mascara de digitos" e uma coluna de datas viraria
    # identificador.
    if tipo in ("inteiro", "decimal", "texto"):
        # Se o Excel guardou como NUMERO, e numero: as heuristicas de
        # identificador so valem para valores que chegaram como TEXTO.
        veio_de_numeros = all(c.excel_type == "n" for c in preenchidas)
        e_id, motivo = looks_like_identifier(textos, from_numbers=veio_de_numeros)
        if e_id:
            return ColumnTyping(
                "identificador",
                1.0,
                [f"identificador ({motivo}); preservado como texto"],
                distribuicao,
            )

    # (b) numero inteiro com cardinalidade alta -> OBSERVA, nao conclui
    if tipo == "inteiro":
        distintos = len(set(textos))
        if distintos / len(textos) > _HIGH_CARDINALITY and distintos > 1:
            observacoes.append("possivel identificador (alta cardinalidade, sem casas decimais)")

        # (c) numero na faixa dos seriais de data do Excel -> OBSERVA.
        # NAO converte: sem formato de data na celula, 43800 e indistinguivel
        # de uma quantidade. Adivinhar aqui seria inventar dado.
        numeros = [float(c.value) for c in preenchidas if isinstance(c.value, (int, float))]
        if numeros and all(_SERIAL_DATE_MIN <= n <= _SERIAL_DATE_MAX for n in numeros):
            observacoes.append(
                "possivel data serial do Excel (nao convertida: o formato da celula "
                "nao declara data)"
            )

    return ColumnTyping(tipo, confianca, observacoes, distribuicao)


__all__ = [
    "EXCEL_ERRORS",
    "RawCell",
    "classify_cell",
    "classify_text",
    "detect_decimal_separator",
    "infer_column_type",
    "looks_like_identifier",
]
