"""
Analise estrutural de uma planilha, em um passo, com resultado estruturado.

Encadeia o que a 1.1-1.4 ja fazem:

    read_workbook  ->  profile_workbook  ->  build_report
                                          ->  build_schema_suggestion
                                          ->  generate_preview

E acrescenta UMA coisa que nenhuma das etapas anteriores tinha: um veredito
explicito de AMBIGUIDADE. O leitor devolve confianca como numero (0..1) e a
lista de candidatas; quem consome precisa decidir se aquilo e bom o bastante
para seguir sozinho ou se deve perguntar ao usuario. Essa decisao estava
implicita em cada chamador — aqui ela fica em um lugar so, com limiar
documentado.

O QUE ESTE MODULO NAO FAZ:

  - nao valida nada (isso e o ValidateTask);
  - nao adivinha regra de negocio;
  - nao escolhe aba nem cabecalho quando a confianca e baixa: devolve as
    opcoes e deixa a decisao para quem sabe (o usuario);
  - nao conhece dominio nenhum;
  - nao devolve caminho fisico de arquivo (o payload do relatorio ja guarda
    somente o NOME, porque o caminho no disco do cliente pode ser sensivel).
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from autotarefas.profiling import profile_workbook
from autotarefas.profiling.report import (
    build_report,
    generate_preview,
    generate_rejection,
)
from autotarefas.profiling.schema_suggestion import build_schema_suggestion
from autotarefas.reader import read_workbook

if TYPE_CHECKING:
    from pathlib import Path

#: Abaixo deste limiar a selecao de ABA nao e confiavel o suficiente para
#: seguir sem perguntar. Vale so quando ha mais de uma aba candidata: com uma
#: aba unica nao existe escolha a fazer, qualquer que seja a confianca.
SHEET_CONFIDENCE_THRESHOLD = 0.70

#: Idem para a linha de CABECALHO. Só vira pergunta quando o leitor tambem
#: apontou alternativas — sem alternativas nao ha o que oferecer.
HEADER_CONFIDENCE_THRESHOLD = 0.70

#: Falhas que significam "o arquivo esta ruim", nao "o programa esta errado".
#: `BadZipFile` vem de um .xlsx que nao e zip; `KeyError`/`OSError` de zip sem
#: as partes esperadas; `UnicodeDecodeError` de texto ilegivel; `ValueError` do
#: proprio leitor. Erros fora desta lista sobem, como devem.
_CORRUPT_FILE_ERRORS = (
    zipfile.BadZipFile,
    UnicodeDecodeError,
    ValueError,
    KeyError,
    OSError,
)

#: Linhas da previa. Limitado de proposito: a previa serve para o usuario
#: reconhecer o arquivo, nao para transportar a planilha para a tela.
DEFAULT_PREVIEW_ROWS = 10


@dataclass(frozen=True, slots=True)
class SheetOption:
    """Uma aba candidata, com o que o usuario precisa para escolher."""

    name: str
    score: float
    rows: int
    cols: int


@dataclass(frozen=True, slots=True)
class Ambiguity:
    """
    Uma escolha que o AutoTarefas NAO vai fazer sozinho.

    Existir uma ambiguidade nao e erro: e o sistema sendo honesto sobre nao
    ter certeza. Quem consome deve apresentar as opcoes e reanalisar com a
    escolha explicita.
    """

    kind: Literal["sheet", "header"]
    confidence: float
    sheet_options: tuple[SheetOption, ...] = ()
    header_options: tuple[int, ...] = ()
    """Linhas FISICAS (1-based) candidatas a cabecalho."""


@dataclass(frozen=True, slots=True)
class AnalysisOutcome:
    """Resultado completo de uma analise."""

    ok: bool
    """False = o arquivo foi recusado pelo leitor; veja `rejection`."""
    rejection: str | None = None
    report: dict[str, Any] = field(default_factory=dict)
    """Payload estruturado (o mesmo do `analisar --json`)."""
    schema_suggestion: str = ""
    """Texto YAML do schema sugerido (conservador: so nomes e tipos)."""
    preview: str = ""
    ambiguities: tuple[Ambiguity, ...] = ()
    selected_sheet: str | None = None
    header_row: int | None = None

    @property
    def needs_choice(self) -> bool:
        """
        True se ha escolha pendente do usuario.

        Pode ser True mesmo com `ok=False`: a recusa por "varias abas parecem
        tabela" e recuperavel escolhendo a aba. Quem consome deve checar
        `needs_choice` ANTES de tratar `ok=False` como caminho sem volta.
        """
        return bool(self.ambiguities)


def _sheet_options(leitura: Any) -> tuple[SheetOption, ...]:
    return tuple(
        SheetOption(name=s.name, score=s.score, rows=s.rows, cols=s.cols)
        for s in (getattr(leitura, "available_sheets", None) or ())
    )


def _recoverable_sheet_ambiguity(
    leitura: Any,
    *,
    sheet_was_chosen: bool,
) -> tuple[Ambiguity, ...]:
    """
    Uma recusa do leitor que o USUARIO consegue resolver escolhendo a aba.

    Este e o caminho real da ambiguidade de aba, e ele nao passa por
    "confianca baixa": quando mais de uma aba parece uma tabela, o leitor
    RECUSA o arquivo e explica que e preciso escolher — mas preenche
    `available_sheets` com as candidatas. Sem tratar isso, uma pasta de tres
    abas terminaria a jornada em "arquivo recusado", quando na verdade falta
    apenas uma pergunta.

    Se o usuario JA escolheu uma aba e ainda houve recusa, o problema e
    outro (aba inexistente, por exemplo) e nao ha escolha a oferecer.
    """
    if sheet_was_chosen:
        return ()
    opcoes = _sheet_options(leitura)
    if len(opcoes) < 2:  # noqa: PLR2004 - com uma aba nao existe escolha
        return ()
    return (
        Ambiguity(
            kind="sheet",
            confidence=leitura.sheet_confidence,
            sheet_options=opcoes,
        ),
    )


def _detect_ambiguities(
    leitura: Any,
    *,
    sheet_was_chosen: bool,
    header_was_chosen: bool,
) -> tuple[Ambiguity, ...]:
    """
    Decide o que ainda precisa da palavra do usuario.

    Uma escolha JA FEITA nunca volta como ambiguidade — senao a interface
    ficaria perguntando de novo o que a pessoa acabou de responder.
    """
    achados: list[Ambiguity] = []

    opcoes = _sheet_options(leitura)
    if (
        not sheet_was_chosen
        and len(opcoes) > 1
        and leitura.sheet_confidence < SHEET_CONFIDENCE_THRESHOLD
    ):
        # Caminho secundario: o leitor conseguiu ler, mas sem convicao.
        # (A ambiguidade FORTE vem como recusa — ver _recoverable_sheet_ambiguity.)
        achados.append(
            Ambiguity(kind="sheet", confidence=leitura.sheet_confidence, sheet_options=opcoes)
        )

    alternativas = tuple(getattr(leitura, "header_alternatives", ()) or ())
    if (
        not header_was_chosen
        and alternativas
        and leitura.header_confidence < HEADER_CONFIDENCE_THRESHOLD
    ):
        achados.append(
            Ambiguity(
                kind="header",
                confidence=leitura.header_confidence,
                header_options=alternativas,
            )
        )

    return tuple(achados)


def analyze_spreadsheet(
    path: Path,
    *,
    sheet: str | None = None,
    header_row: int | None = None,
    preview_rows: int = DEFAULT_PREVIEW_ROWS,
) -> AnalysisOutcome:
    """
    Analisa uma planilha e devolve diagnostico, previa e schema sugerido.

    Args:
        path: arquivo a analisar (nao e modificado em momento algum).
        sheet: aba escolhida pelo usuario. None = deixar o leitor detectar.
        header_row: linha fisica (1-based) do cabecalho escolhida pelo
            usuario. None = deixar o leitor detectar.
        preview_rows: quantas linhas da previa.

    Returns:
        AnalysisOutcome. Quando `ok` e False, so `rejection` e util. Quando
        `needs_choice` e True, ha ambiguidade a resolver e vale reanalisar
        passando `sheet`/`header_row`.

    Nao levanta excecao para arquivo invalido: um arquivo que o leitor recusa
    e um FATO sobre o arquivo, nao um erro do programa — quem chama decide
    como mostrar isso. Isso vale tambem para arquivo CORROMPIDO: um .xlsx que
    nao e um zip valido faz o openpyxl estourar la no fundo, e deixar essa
    excecao subir transformaria "arquivo ruim" em erro 500 de quem chama.
    """
    try:
        leitura = read_workbook(path, sheet=sheet, header_row=header_row)
    except _CORRUPT_FILE_ERRORS as exc:
        # Arquivo corrompido e um FATO sobre o arquivo. A lista de excecoes e
        # fechada de proposito: um `except Exception` aqui esconderia defeito
        # nosso (AttributeError, TypeError) sob a fachada de "arquivo ruim", e
        # o bug so apareceria como recusa inexplicavel para o cliente.
        return AnalysisOutcome(
            ok=False,
            rejection=(
                "nao foi possivel ler este arquivo. Ele pode estar corrompido, "
                f"protegido ou nao ser uma planilha valida ({type(exc).__name__})."
            ),
        )

    if not leitura.ok:
        # Recusa pode ser recuperavel (varias abas candidatas): devolvemos as
        # opcoes para que a interface pergunte em vez de encerrar a jornada.
        return AnalysisOutcome(
            ok=False,
            rejection=generate_rejection(leitura),
            ambiguities=_recoverable_sheet_ambiguity(leitura, sheet_was_chosen=sheet is not None),
            selected_sheet=leitura.selected_sheet,
        )

    perfil = profile_workbook(leitura)

    return AnalysisOutcome(
        ok=True,
        report=build_report(leitura, perfil),
        schema_suggestion=build_schema_suggestion(perfil),
        preview=generate_preview(leitura, preview_rows),
        ambiguities=_detect_ambiguities(
            leitura,
            sheet_was_chosen=sheet is not None,
            header_was_chosen=header_row is not None,
        ),
        selected_sheet=leitura.selected_sheet,
        header_row=leitura.header_row,
    )


__all__ = [
    "DEFAULT_PREVIEW_ROWS",
    "HEADER_CONFIDENCE_THRESHOLD",
    "SHEET_CONFIDENCE_THRESHOLD",
    "Ambiguity",
    "AnalysisOutcome",
    "SheetOption",
    "analyze_spreadsheet",
]
