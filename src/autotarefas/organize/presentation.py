"""
Avaliacao OBJETIVA da apresentacao de uma planilha.

"Bonita" e "feia" nao sao criterios: duas pessoas discordam e ninguem
consegue conferir. Este modulo troca o julgamento por uma lista de
criterios verificaveis — cada um responde sim ou nao, com o detalhe que
justifica a resposta — e so entao emite um veredito.

Tres vereditos, e o que cada um significa para o produto:

    organizada   nao ha o que melhorar com seguranca; NAO oferecemos
                 reformatacao (mexer na identidade visual de quem ja
                 cuidou da planilha e desrespeito, nao ajuda)
    melhoravel   ha ganhos claros e seguros; oferecemos a organizacao
    ambigua      a estrutura nao esta clara o bastante para decidir
                 sozinho (celulas mescladas na area de dados, cabecalho
                 irreconhecivel) — quem decide e a pessoa

O modulo NAO altera nada: ele lê e conclui. Quem aplica e o `organizer`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from openpyxl import load_workbook

if TYPE_CHECKING:
    from pathlib import Path

    from openpyxl.worksheet.worksheet import Worksheet

#: Veredito da avaliacao.
Verdict = Literal["organizada", "melhoravel", "ambigua"]

#: A partir de quantas linhas um filtro e um painel congelado passam a
#: fazer diferenca real para quem abre o arquivo.
LINHAS_PARA_FILTRO = 15
LINHAS_PARA_PAINEL = 15

#: Largura minima e maxima consideradas legiveis (unidades do Excel).
LARGURA_MINIMA = 6.0
LARGURA_MAXIMA = 80.0

#: Quantas cores de preenchimento distintas na area de dados ja indicam
#: excesso (o cabecalho nao entra na conta).
MAX_CORES_NOS_DADOS = 3

#: Amostra de linhas lidas para avaliar formato e alinhamento. Uma planilha
#: de 100 mil linhas nao precisa ser varrida inteira para se saber se a
#: coluna de datas tem formato consistente.
AMOSTRA = 200

#: Criterios ESTRUTURAIS: falhar num deles significa que nao entendemos a
#: tabela, e organizar seria chutar. Falta de destaque no cabecalho NAO
#: entra aqui — isso e questao de apresentacao, e tem conserto seguro.
_ESTRUTURAIS = frozenset({"estrutura_tabular", "cabecalho_presente"})


@dataclass(frozen=True, slots=True)
class Criterion:
    """Um criterio verificavel — com a evidencia que sustenta o resultado."""

    key: str
    title: str
    passed: bool
    detail: str
    applicable: bool = True


@dataclass(frozen=True, slots=True)
class PresentationAudit:
    """O que a planilha ja tem, o que falta, e o veredito."""

    sheet: str
    verdict: Verdict
    criteria: tuple[Criterion, ...] = ()
    rows: int = 0
    columns: int = 0

    @property
    def applicable(self) -> tuple[Criterion, ...]:
        return tuple(c for c in self.criteria if c.applicable)

    @property
    def failures(self) -> tuple[Criterion, ...]:
        return tuple(c for c in self.applicable if not c.passed)

    @property
    def score(self) -> float:
        """Fracao dos criterios aplicaveis atendidos (0..1)."""
        aplicaveis = self.applicable
        if not aplicaveis:
            return 1.0
        return sum(1 for c in aplicaveis if c.passed) / len(aplicaveis)

    @property
    def can_improve(self) -> bool:
        """Vale oferecer a organizacao?"""
        return self.verdict == "melhoravel"

    def as_dict(self) -> dict[str, Any]:
        return {
            "aba": self.sheet,
            "veredito": self.verdict,
            "pontuacao": round(self.score, 3),
            "linhas": self.rows,
            "colunas": self.columns,
            "criterios": [
                {
                    "chave": c.key,
                    "titulo": c.title,
                    "atendido": c.passed,
                    "detalhe": c.detail,
                    "aplicavel": c.applicable,
                }
                for c in self.criteria
            ],
            "pendencias": [c.title for c in self.failures],
        }


# ============================================================
# Leitura de fatos (nada de julgamento aqui)
# ============================================================


def _largura(ws: Worksheet, indice: int) -> float | None:
    from openpyxl.utils import get_column_letter

    dimensao = ws.column_dimensions.get(get_column_letter(indice))
    return None if dimensao is None or dimensao.width is None else float(dimensao.width)


def _celulas_de_dados(ws: Worksheet, header_row: int) -> list[list[Any]]:
    """Amostra das celulas da area de dados (objetos, nao valores)."""
    linhas: list[list[Any]] = []
    for linha in ws.iter_rows(min_row=header_row + 1, max_row=header_row + AMOSTRA):
        if all(c.value is None for c in linha):
            continue
        linhas.append(list(linha))
    return linhas


def _mescladas_na_area(ws: Worksheet, header_row: int) -> int:
    """Celulas mescladas DENTRO da area de dados (as piores para ler)."""
    return sum(
        1
        for intervalo in ws.merged_cells.ranges
        if intervalo.max_row >= header_row  # inclui o proprio cabecalho
    )


def _cores_dos_dados(amostra: list[list[Any]]) -> int:
    cores: set[str] = set()
    for linha in amostra:
        for celula in linha:
            preenchimento = celula.fill
            if preenchimento is not None and preenchimento.fill_type == "solid":
                cores.add(str(preenchimento.fgColor.rgb))
    # Branco/sem cor nao conta como "cor".
    return len({c for c in cores if c not in {"00000000", "FFFFFFFF", "None"}})


# ============================================================
# Criterios
# ============================================================


def _criterios_cabecalho(ws: Worksheet, header_row: int) -> tuple[Criterion, Criterion]:
    """
    Duas perguntas diferentes sobre a mesma linha.

    "Existe cabecalho?" e ESTRUTURAL: sem titulos nao ha tabela para
    organizar. "Ele se destaca?" e APRESENTACAO: tem conserto seguro, e
    por isso nao pode empurrar a planilha para o veredito 'ambigua'.
    """
    celulas = [c for c in ws[header_row] if c.value is not None]
    presente = Criterion(
        "cabecalho_presente",
        "Cabeçalho preenchido",
        passed=bool(celulas),
        detail=(
            f"{len(celulas)} título(s) na linha {header_row}"
            if celulas
            else "a linha de cabeçalho não tem nenhum título preenchido"
        ),
    )

    def destacada(celula: Any) -> bool:
        preenchimento = celula.fill
        colorida = (
            preenchimento is not None
            and preenchimento.fill_type == "solid"
            and str(preenchimento.fgColor.rgb) not in {"00000000", "FFFFFFFF"}
        )
        return bool(celula.font.bold) or colorida

    destaque = Criterion(
        "cabecalho_destacado",
        "Cabeçalho legível e destacado",
        passed=any(destacada(c) for c in celulas),
        detail=(
            "títulos com negrito ou preenchimento"
            if any(destacada(c) for c in celulas)
            else "títulos sem destaque visual (nem negrito, nem preenchimento)"
        ),
        applicable=bool(celulas),
    )
    return presente, destaque


def _criterio_larguras(ws: Worksheet, header_row: int, colunas: int) -> Criterion:
    estreitas: list[str] = []
    largas: list[str] = []
    for indice in range(1, colunas + 1):
        largura = _largura(ws, indice)
        if largura is None:
            continue
        titulo = str(ws.cell(row=header_row, column=indice).value or f"coluna {indice}")
        if largura < LARGURA_MINIMA:
            estreitas.append(titulo)
        elif largura > LARGURA_MAXIMA:
            largas.append(titulo)

    problemas = estreitas + largas
    return Criterion(
        "larguras_adequadas",
        "Larguras legíveis",
        passed=not problemas,
        detail=(
            "todas as larguras definidas estão em faixa legível"
            if not problemas
            else f"fora da faixa: {', '.join(problemas[:4])}"
        ),
    )


def _criterio_texto_cortado(ws: Worksheet, header_row: int, colunas: int) -> Criterion:
    cortados: list[str] = []
    for indice in range(1, colunas + 1):
        largura = _largura(ws, indice)
        titulo = str(ws.cell(row=header_row, column=indice).value or "")
        if largura is not None and titulo and len(titulo) > largura:
            cortados.append(titulo)
    return Criterion(
        "texto_nao_cortado",
        "Títulos visíveis por inteiro",
        passed=not cortados,
        detail=(
            "nenhum título maior que a largura da coluna"
            if not cortados
            else f"provavelmente cortado(s): {', '.join(cortados[:4])}"
        ),
    )


def _criterio_formatos(amostra: list[list[Any]], colunas: int) -> Criterion:
    inconsistentes: list[int] = []
    for indice in range(colunas):
        formatos = {
            linha[indice].number_format
            for linha in amostra
            if indice < len(linha) and linha[indice].value is not None
        }
        if len(formatos) > 1:
            inconsistentes.append(indice + 1)
    return Criterion(
        "formatos_consistentes",
        "Formatos consistentes por coluna",
        passed=not inconsistentes,
        detail=(
            "cada coluna usa um formato só"
            if not inconsistentes
            else f"{len(inconsistentes)} coluna(s) com formatos misturados"
        ),
        applicable=bool(amostra),
    )


def _criterio_alinhamento(amostra: list[list[Any]], colunas: int) -> Criterion:
    misturadas = 0
    for indice in range(colunas):
        alinhamentos = {
            linha[indice].alignment.horizontal
            for linha in amostra
            if indice < len(linha) and linha[indice].value is not None
        }
        if len({a for a in alinhamentos if a}) > 1:
            misturadas += 1
    return Criterion(
        "alinhamento_coerente",
        "Alinhamento coerente",
        passed=misturadas == 0,
        detail=(
            "alinhamento uniforme dentro de cada coluna"
            if misturadas == 0
            else f"{misturadas} coluna(s) com alinhamentos diferentes"
        ),
        applicable=bool(amostra),
    )


def _criterio_filtro(ws: Worksheet, linhas: int) -> Criterion:
    tem = ws.auto_filter.ref is not None or bool(getattr(ws, "tables", {}))
    aplicavel = linhas >= LINHAS_PARA_FILTRO
    return Criterion(
        "filtro",
        "Filtro na área tabular",
        passed=tem,
        detail="filtro presente" if tem else f"sem filtro (a planilha tem {linhas} linhas)",
        applicable=aplicavel,
    )


def _criterio_painel(ws: Worksheet, linhas: int) -> Criterion:
    tem = bool(ws.freeze_panes)
    aplicavel = linhas >= LINHAS_PARA_PAINEL
    return Criterion(
        "painel_congelado",
        "Cabeçalho congelado",
        passed=tem,
        detail=(
            f"painel congelado em {ws.freeze_panes}"
            if tem
            else f"sem congelamento (a planilha tem {linhas} linhas)"
        ),
        applicable=aplicavel,
    )


def _criterio_cores(amostra: list[list[Any]]) -> Criterion:
    cores = _cores_dos_dados(amostra)
    return Criterion(
        "cores_moderadas",
        "Uso moderado de cores",
        passed=cores <= MAX_CORES_NOS_DADOS,
        detail=f"{cores} cor(es) de preenchimento na área de dados",
        applicable=bool(amostra),
    )


def _criterio_estrutura(ws: Worksheet, header_row: int, colunas: int) -> Criterion:
    mescladas = _mescladas_na_area(ws, header_row)
    titulos = [str(c.value).strip() for c in ws[header_row] if c.value is not None]
    duplicados = len(titulos) != len(set(titulos))
    vazios = colunas - len(titulos)

    problemas: list[str] = []
    if mescladas:
        problemas.append(f"{mescladas} célula(s) mesclada(s) na área de dados")
    if duplicados:
        problemas.append("títulos de coluna repetidos")
    if vazios > 0:
        problemas.append(f"{vazios} coluna(s) sem título")

    return Criterion(
        "estrutura_tabular",
        "Estrutura tabular clara",
        passed=not problemas,
        detail="; ".join(problemas) if problemas else "uma tabela simples, sem mesclagens",
    )


def _criterio_tabela(ws: Worksheet) -> Criterion:
    tabelas = getattr(ws, "tables", {}) or {}
    return Criterion(
        "tabela_estruturada",
        "Tabela estruturada do Excel",
        passed=bool(tabelas),
        detail=f"{len(tabelas)} tabela(s) declarada(s)" if tabelas else "sem tabela declarada",
        # Nao e obrigatorio: uma planilha pode estar impecavel sem isso.
        applicable=False,
    )


# ============================================================
# Veredito
# ============================================================


def _veredito(criterios: tuple[Criterion, ...]) -> Verdict:
    """
    Do conjunto de criterios para uma decisao de produto.

    Falha ESTRUTURAL (mesclagem na area de dados, cabecalho irreconhecivel)
    nao e questao de gosto: sem entender a tabela, organizar seria chutar.
    Nesse caso o veredito e `ambigua` e quem decide e a pessoa.
    """
    aplicaveis = [c for c in criterios if c.applicable]
    falhas = [c for c in aplicaveis if not c.passed]
    if any(c.key in _ESTRUTURAIS for c in falhas):
        return "ambigua"
    return "organizada" if not falhas else "melhoravel"


def audit_presentation(
    path: Path,
    *,
    sheet: str | None = None,
    header_row: int = 1,
) -> PresentationAudit:
    """
    Avalia a apresentacao de uma aba, criterio a criterio.

    Args:
        path: arquivo XLSX/XLSM (nunca e alterado).
        sheet: aba a avaliar. None = a ativa.
        header_row: linha fisica do cabecalho.

    Returns:
        PresentationAudit com o veredito e a evidencia de cada criterio.
    """
    workbook = load_workbook(path, read_only=False, data_only=False)
    ws = workbook[sheet] if sheet is not None else workbook.active
    if ws is None:  # pragma: no cover - openpyxl sempre devolve uma aba
        msg = "planilha sem aba ativa"
        raise ValueError(msg)

    colunas = int(ws.max_column or 0)
    linhas_dados = max(int(ws.max_row or 0) - header_row, 0)
    amostra = _celulas_de_dados(ws, header_row)

    cabecalho_presente, cabecalho_destacado = _criterios_cabecalho(ws, header_row)
    criterios = (
        cabecalho_presente,
        cabecalho_destacado,
        _criterio_estrutura(ws, header_row, colunas),
        _criterio_larguras(ws, header_row, colunas),
        _criterio_texto_cortado(ws, header_row, colunas),
        _criterio_formatos(amostra, colunas),
        _criterio_alinhamento(amostra, colunas),
        _criterio_filtro(ws, linhas_dados),
        _criterio_painel(ws, linhas_dados),
        _criterio_cores(amostra),
        _criterio_tabela(ws),
    )

    workbook.close()
    return PresentationAudit(
        sheet=str(ws.title),
        verdict=_veredito(criterios),
        criteria=criterios,
        rows=linhas_dados,
        columns=colunas,
    )


__all__ = [
    "AMOSTRA",
    "LARGURA_MAXIMA",
    "LARGURA_MINIMA",
    "LINHAS_PARA_FILTRO",
    "LINHAS_PARA_PAINEL",
    "MAX_CORES_NOS_DADOS",
    "Criterion",
    "PresentationAudit",
    "Verdict",
    "audit_presentation",
]
