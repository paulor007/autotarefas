"""
Indicadores CONFIRMADOS — o oposto de gráfico inventado.

Uma planilha com as colunas "Data", "Loja" e "Valor Final" *parece* pedir
um resumo por loja e por mês. Mas "Valor Final" pode ser desconto, e
"Loja" pode ser o código do vendedor. Somar sem perguntar produz um número
com cara de verdade — o pior resultado possível.

Por isso este módulo separa duas coisas que costumam ser confundidas:

    SUGERIR   olhar os tipos e os nomes e dizer "isto PODE ser uma data,
              isto PODE ser um valor" — com a confiança explícita;
    CALCULAR  só depois que a pessoa confirmar qual coluna é o quê.

Sem confirmação, nada é somado e nada é desenhado. E a ausência de
indicadores nunca bloqueia a análise: ela é opcional por natureza.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from autotarefas.reader.normalize import parse_date, parse_number
from autotarefas.reader.types import detect_decimal_separator

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import pandas as pd

#: Papéis que o card sabe usar. Deliberadamente poucos: são os que
#: sustentam um resumo honesto sem conhecer o negócio.
Role = Literal["data", "categoria", "identificador", "quantidade", "valor", "texto"]

#: Confiança mínima para OFERECER a sugestão. Abaixo disso, ficamos calados.
CONFIANCA_MINIMA = 0.6

#: Acima desta fração de valores distintos, a coluna identifica o registro
#: em vez de agrupá-lo (não serve como categoria).
LIMITE_IDENTIFICADOR = 0.6

#: Uma categoria útil tem poucos valores distintos.
MAX_CATEGORIAS = 50

#: Quantas linhas do resumo entram no relatório (as maiores).
TOP_RESUMO = 15

_PISTAS_QUANTIDADE = ("quantidade", "qtd", "qtde", "itens", "unidades", "volume")
_PISTAS_VALOR = ("valor", "preco", "preço", "total", "receita", "despesa", "saldo", "custo")
_PISTAS_DATA = ("data", "dia", "mes", "mês", "competencia", "competência", "emissao", "emissão")
_PISTAS_CATEGORIA = (
    "categoria",
    "tipo",
    "status",
    "situacao",
    "situação",
    "loja",
    "unidade",
    "orgao",
    "órgão",
    "setor",
    "departamento",
    "produto",
    "servico",
    "serviço",
)


@dataclass(frozen=True, slots=True)
class RoleSuggestion:
    """ "Esta coluna PODE ser X" — nunca "esta coluna É X"."""

    column: str
    role: Role
    confidence: float
    reason: str

    @property
    def offerable(self) -> bool:
        return self.confidence >= CONFIANCA_MINIMA


@dataclass(frozen=True, slots=True)
class IndicatorRequest:
    """Os papéis CONFIRMADOS pela pessoa."""

    value_column: str
    category_column: str = ""
    date_column: str = ""

    @property
    def is_valid(self) -> bool:
        return bool(self.value_column) and bool(self.category_column or self.date_column)


@dataclass(frozen=True, slots=True)
class Indicator:
    """Um resumo pronto para virar tabela e gráfico."""

    title: str
    dimension: str
    measure: str
    rows: tuple[tuple[str, float], ...] = ()
    total: float = 0.0
    ignored_rows: int = 0
    """Linhas em que o valor não pôde ser lido como número."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "titulo": self.title,
            "dimensao": self.dimension,
            "medida": self.measure,
            "linhas": [{"chave": k, "valor": v} for k, v in self.rows],
            "total": self.total,
            "linhas_ignoradas": self.ignored_rows,
        }


# ============================================================
# Sugestão de papéis
# ============================================================


def _pista(nome: str, pistas: tuple[str, ...]) -> bool:
    baixo = nome.casefold()
    return any(p in baixo for p in pistas)


def _cardinalidade(frame: pd.DataFrame, coluna: str) -> float:
    serie = frame[coluna]
    total = len(serie)
    if total == 0:
        return 0.0
    return float(serie.nunique()) / total


def _sugerir_numerica(nome: str, cardinalidade: float) -> RoleSuggestion:
    """Coluna numérica: quantidade, valor ou código?"""
    if _pista(nome, _PISTAS_QUANTIDADE):
        return RoleSuggestion(nome, "quantidade", 0.8, "coluna numérica com nome de quantidade")
    if _pista(nome, _PISTAS_VALOR):
        return RoleSuggestion(nome, "valor", 0.75, "coluna numérica com nome de valor")
    if cardinalidade > LIMITE_IDENTIFICADOR:
        return RoleSuggestion(
            nome, "identificador", 0.65, "números quase todos distintos: parece um código"
        )
    return RoleSuggestion(nome, "quantidade", 0.5, "coluna numérica sem nome conclusivo")


def _sugerir_textual(nome: str, cardinalidade: float, distintos: int) -> RoleSuggestion:
    """Coluna de texto: identifica o registro ou agrupa registros?"""
    if cardinalidade > LIMITE_IDENTIFICADOR:
        return RoleSuggestion(nome, "identificador", 0.6, "quase todos os valores são distintos")
    if distintos <= MAX_CATEGORIAS:
        confianca = 0.8 if _pista(nome, _PISTAS_CATEGORIA) else 0.65
        return RoleSuggestion(
            nome, "categoria", confianca, f"{distintos} valor(es) distinto(s): agrupa bem"
        )
    return RoleSuggestion(nome, "texto", 0.5, "texto livre, sem papel claro")


def _sugerir_uma(nome: str, tipo: str, cardinalidade: float, distintos: int) -> RoleSuggestion:
    """
    Tipo observado + nome da coluna + cardinalidade.

    O tipo pesa mais que o nome: uma coluna chamada "Valor" cheia de texto
    não é uma medida. O nome só desempata.
    """
    if tipo in {"data", "data_hora"}:
        return RoleSuggestion(nome, "data", 0.9, f"o leitor identificou o tipo '{tipo}'")
    if _pista(nome, _PISTAS_DATA) and tipo == "texto":
        return RoleSuggestion(nome, "data", 0.4, "o nome sugere data, mas o conteúdo é texto")
    if tipo == "moeda":
        return RoleSuggestion(nome, "valor", 0.9, "valores monetários reconhecidos")
    if tipo in {"inteiro", "decimal"}:
        return _sugerir_numerica(nome, cardinalidade)
    if tipo == "identificador":
        return RoleSuggestion(nome, "identificador", 0.85, "o leitor identificou um código")
    return _sugerir_textual(nome, cardinalidade, distintos)


def suggest_roles(
    frame: pd.DataFrame,
    columns: Sequence[Mapping[str, Any]] = (),
) -> tuple[RoleSuggestion, ...]:
    """
    Propõe um papel para cada coluna, com a confiança explícita.

    Args:
        frame: o DataFrame FIEL do leitor (texto exato).
        columns: as colunas do relatório de análise (`name`, `inferred_type`).

    Returns:
        Uma sugestão por coluna, na ordem do arquivo. NADA é aplicado.
    """
    tipos = {
        str(c.get("name")): str(c.get("inferred_type", "texto")) for c in columns if c.get("name")
    }
    sugestoes: list[RoleSuggestion] = []
    for coluna in frame.columns:
        nome = str(coluna)
        distintos = int(frame[coluna].nunique())
        sugestoes.append(
            _sugerir_uma(nome, tipos.get(nome, "texto"), _cardinalidade(frame, coluna), distintos)
        )
    return tuple(sugestoes)


def summary_is_offerable(suggestions: Sequence[RoleSuggestion]) -> bool:
    """
    Dá para oferecer um resumo com segurança?

    Exige uma MEDIDA (valor ou quantidade) e uma DIMENSÃO (categoria ou
    data), ambas com confiança suficiente. Sem isso, ficamos calados.
    """
    confiaveis = [s for s in suggestions if s.offerable]
    medida = any(s.role in {"valor", "quantidade"} for s in confiaveis)
    dimensao = any(s.role in {"categoria", "data"} for s in confiaveis)
    return medida and dimensao


def default_request(suggestions: Sequence[RoleSuggestion]) -> IndicatorRequest:
    """A proposta que a tela mostra para a pessoa confirmar ou trocar."""
    confiaveis = [s for s in suggestions if s.offerable]

    def primeira(papel: Role) -> str:
        for sugestao in confiaveis:
            if sugestao.role == papel:
                return sugestao.column
        return ""

    return IndicatorRequest(
        value_column=primeira("valor") or primeira("quantidade"),
        category_column=primeira("categoria"),
        date_column=primeira("data"),
    )


# ============================================================
# Cálculo (só com papéis confirmados)
# ============================================================


def _numeros(frame: pd.DataFrame, coluna: str) -> tuple[list[float | None], int]:
    textos = [str(v) for v in frame[coluna].tolist()]
    separador = detect_decimal_separator(textos[:200]) or ","
    valores: list[float | None] = []
    ignoradas = 0
    for texto in textos:
        numero = parse_number(texto, separador)
        if numero is None:
            ignoradas += 1
        valores.append(numero)
    return valores, ignoradas


def _agrupar(
    chaves: list[str], valores: list[float | None]
) -> tuple[tuple[tuple[str, float], ...], float]:
    somas: dict[str, float] = {}
    total = 0.0
    for chave, valor in zip(chaves, valores, strict=False):
        if valor is None or not chave:
            continue
        somas[chave] = somas.get(chave, 0.0) + valor
        total += valor
    ordenado = sorted(somas.items(), key=lambda par: par[1], reverse=True)
    return tuple(ordenado[:TOP_RESUMO]), total


def build_indicators(frame: pd.DataFrame, request: IndicatorRequest) -> tuple[Indicator, ...]:
    """
    Calcula os resumos a partir dos papéis CONFIRMADOS.

    Args:
        frame: DataFrame fiel do leitor.
        request: colunas confirmadas pela pessoa.

    Returns:
        Um indicador por dimensão confirmada (categoria e/ou mês). Vazio
        quando o pedido não é aplicável — nunca um número inventado.
    """
    if not request.is_valid or request.value_column not in frame.columns:
        return ()

    valores, ignoradas = _numeros(frame, request.value_column)
    indicadores: list[Indicator] = []

    if request.category_column and request.category_column in frame.columns:
        chaves = [str(v).strip() for v in frame[request.category_column].tolist()]
        linhas, total = _agrupar(chaves, valores)
        indicadores.append(
            Indicator(
                title=f"{request.value_column} por {request.category_column}",
                dimension=request.category_column,
                measure=request.value_column,
                rows=linhas,
                total=total,
                ignored_rows=ignoradas,
            )
        )

    if request.date_column and request.date_column in frame.columns:
        meses: list[str] = []
        for valor in frame[request.date_column].tolist():
            data = parse_date(str(valor))
            meses.append(f"{data.year:04d}-{data.month:02d}" if data else "")
        linhas, total = _agrupar(meses, valores)
        indicadores.append(
            Indicator(
                title=f"{request.value_column} por mês ({request.date_column})",
                dimension="mês",
                measure=request.value_column,
                rows=tuple(sorted(linhas)),
                total=total,
                ignored_rows=ignoradas,
            )
        )

    return tuple(indicadores)


__all__ = [
    "CONFIANCA_MINIMA",
    "LIMITE_IDENTIFICADOR",
    "MAX_CATEGORIAS",
    "TOP_RESUMO",
    "Indicator",
    "IndicatorRequest",
    "Role",
    "RoleSuggestion",
    "build_indicators",
    "default_request",
    "suggest_roles",
    "summary_is_offerable",
]
