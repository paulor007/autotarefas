"""
Perfilagem generica de planilhas.

    arquivo -> read_workbook -> WorkbookReadResult -> profile_workbook -> ProfileResult

A perfilagem NAO abre arquivo, NAO detecta aba, NAO infere tipo e NAO
normaliza — tudo isso ja foi feito pelo leitor, e duplicar seria criar
duas versoes da verdade. Ela recebe o resultado pronto e OBSERVA.

E ela nao conhece dominio: nao sabe o que e CPF, SKU ou venda. Ha um teste
que percorre a AST deste pacote e falha o build se um termo de dominio
aparecer no codigo.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from autotarefas.profiling.metrics import (
    SAMPLE_SIZE,
    distinct_stats,
    duplicate_row_count,
    excel_error_stats,
    fill_stats,
    top_repeated,
    value_range,
    whitespace_issues,
)
from autotarefas.profiling.result import ColumnProfile, Finding, ProfileResult

if TYPE_CHECKING:
    import pandas as pd

    from autotarefas.reader.result import ColumnInfo, WorkbookReadResult

#: Abaixo desta taxa de preenchimento, a coluna vira aviso (nao erro:
#: obrigatoriedade e decisao do perfil/schema, nunca da perfilagem).
_LOW_FILL_RATE = 0.5
#: Acima disto, a coluna e "quase toda distinta" — apenas uma observacao.
_HIGH_UNIQUENESS = 0.9
#: Abaixo disto (e com poucos distintos), parece um campo categorico.
_LOW_CARDINALITY = 0.1
_MIN_ROWS_FOR_CARDINALITY = 20
#: A cardinalidade so e SINAL em colunas de texto. Numa planilha grande,
#: toda coluna de data/moeda tem cardinalidade baixa — isso nao diz nada.
_CARDINALITY_TYPES: frozenset[str] = frozenset({"texto"})


def _reader_findings(result: WorkbookReadResult) -> list[Finding]:
    """Traz os avisos do leitor para dentro do perfil, sem reescreve-los."""
    severidade = {
        "erro_excel": "problema",
        "coluna_mista": "aviso",
        "rodape_suspeito": "aviso",
        "linhas_duplicadas": "aviso",
        "formulas": "informacao",
        "coluna_vazia": "informacao",
        "linhas_vazias_ignoradas": "informacao",
    }
    return [
        Finding(
            code=w.code,
            severity=severidade.get(w.code, "informacao"),  # type: ignore[arg-type]
            message=w.message,
            column=w.column,
            row=w.row,
        )
        for w in result.warnings
    ]


def _column_findings(perfil: ColumnProfile, amostras_espaco: list[str]) -> list[Finding]:
    """Achados de UMA coluna. Nada aqui e 'erro' — sao observacoes e avisos."""
    achados: list[Finding] = []

    if perfil.inferred_type == "vazio":
        achados.append(
            Finding(
                code="coluna_vazia",
                severity="informacao",
                message=f"coluna '{perfil.name}' nao tem nenhum valor",
                column=perfil.name,
            )
        )
    elif perfil.fill_rate < _LOW_FILL_RATE:
        achados.append(
            Finding(
                code="preenchimento_baixo",
                severity="aviso",
                message=(
                    f"coluna '{perfil.name}' esta {perfil.fill_rate:.0%} preenchida "
                    f"({perfil.empty_count} vazios) — confira se isso e esperado"
                ),
                column=perfil.name,
                count=perfil.empty_count,
            )
        )

    if perfil.mixed_types:
        detalhe = ", ".join(f"{t}: {n}" for t, n in perfil.mixed_types.items())
        achados.append(
            Finding(
                code="tipos_misturados",
                severity="aviso",
                message=(
                    f"coluna '{perfil.name}' tem mais de um tipo ({detalhe}) — "
                    "os valores NAO foram convertidos a forca"
                ),
                column=perfil.name,
                count=perfil.filled_count,
                samples=perfil.sample_values[:SAMPLE_SIZE],
            )
        )

    if perfil.excel_error_count:
        achados.append(
            Finding(
                code="erro_excel",
                severity="problema",
                message=(
                    f"coluna '{perfil.name}' tem {perfil.excel_error_count} celula(s) "
                    "com erro do Excel"
                ),
                column=perfil.name,
                count=perfil.excel_error_count,
            )
        )

    if perfil.whitespace_issue_count:
        achados.append(
            Finding(
                code="espacos_extras",
                severity="aviso",
                message=(
                    f"coluna '{perfil.name}' tem {perfil.whitespace_issue_count} celula(s) "
                    "com espaco sobrando (nas pontas ou internos)"
                ),
                column=perfil.name,
                count=perfil.whitespace_issue_count,
                samples=amostras_espaco,
            )
        )

    return achados


def _cardinality_notes(perfil: ColumnProfile, valores: list[str]) -> list[str]:
    """
    Observacoes de cardinalidade — INFORMACAO, jamais conclusao.

    So faz sentido em colunas de TEXTO. Numa planilha de 7 mil linhas,
    QUALQUER coluna de data ou moeda tem cardinalidade baixa — dizer que
    uma coluna de moeda e "possivel campo categorico" seria ruido, e ruido
    e pior que silencio: ensina o usuario a ignorar o relatorio.

    Alta cardinalidade NAO significa "chave unica". Baixa cardinalidade NAO
    significa "deveria ser um enum". Quem decide isso e o perfil/schema.
    """
    notas: list[str] = []
    if perfil.inferred_type not in _CARDINALITY_TYPES:
        return notas
    if perfil.filled_count < _MIN_ROWS_FOR_CARDINALITY:
        return notas

    if perfil.uniqueness_rate >= _HIGH_UNIQUENESS:
        notas.append(
            f"alta cardinalidade ({perfil.uniqueness_rate:.0%} de valores distintos) — "
            "possivel identificador"
        )
    elif perfil.uniqueness_rate <= _LOW_CARDINALITY:
        repetidos = top_repeated(valores, limite=3)
        exemplo = f"; mais comuns: {', '.join(repetidos)}" if repetidos else ""
        notas.append(
            f"baixa cardinalidade ({perfil.distinct_count} valores distintos) — "
            f"possivel campo categorico{exemplo}"
        )
    return notas


def _profile_column(
    info: ColumnInfo,
    originais: list[str],
    serie_normalizada: pd.Series,
) -> tuple[ColumnProfile, list[str]]:
    """Retrato de uma coluna. Retorna (perfil, amostras de espaco em branco)."""
    total = len(originais)
    preenchidos, vazios, taxa = fill_stats(originais)
    distintos, unicidade, duplicados = distinct_stats(originais)
    n_espacos, amostras_espaco = whitespace_issues(originais)
    n_erros, _ = excel_error_stats(originais)
    minimo, maximo = value_range(serie_normalizada, info.inferred_type)

    mistos = info.type_counts if info.inferred_type == "misto" else {}

    perfil = ColumnProfile(
        name=info.name,
        inferred_type=info.inferred_type,
        type_confidence=info.type_confidence,
        total_count=total,
        filled_count=preenchidos,
        empty_count=vazios,
        fill_rate=taxa,
        distinct_count=distintos,
        uniqueness_rate=unicidade,
        duplicate_value_count=duplicados,
        mixed_types=mistos,
        excel_error_count=n_erros,
        whitespace_issue_count=n_espacos,
        minimum=minimo,
        maximum=maximo,
        sample_values=info.sample_values,
        observations=list(info.observations),
    )
    return perfil, amostras_espaco


def profile_workbook(result: WorkbookReadResult) -> ProfileResult:
    """
    Perfila uma planilha ja lida. Nao abre arquivo, nao altera nada.

    Args:
        result: O que `read_workbook` produziu.

    Returns:
        ProfileResult. Se o leitor recusou o arquivo, o perfil vem vazio
        com o mesmo `rejected_reason` — sem inventar metrica nenhuma.
    """
    if not result.ok or result.original_dataframe is None:
        return ProfileResult(
            source_file=result.source_file,
            selected_sheet=result.selected_sheet,
            header_row=result.header_row,
            row_count=0,
            column_count=0,
            total_cells=0,
            filled_cells=0,
            empty_cells=0,
            fill_rate=0.0,
            duplicate_row_count=0,
            completely_empty_row_count=0,
            completely_empty_column_count=0,
            mixed_type_column_count=0,
            excel_error_count=0,
            conversion_count=0,
            warning_count=len(result.warnings),
            reader_confidence=result.confidence,
            rejected_reason=result.rejected_reason,
            findings=_reader_findings(result),
        )

    original = result.original_dataframe
    normalizado = result.normalized_dataframe
    linhas = len(original)

    perfis: list[ColumnProfile] = []
    achados: list[Finding] = _reader_findings(result)

    for info in result.detected_columns:
        originais = [str(v) for v in original[info.name]]
        serie = normalizado[info.name] if normalizado is not None else original[info.name]

        perfil, amostras = _profile_column(info, originais, serie)
        notas = _cardinality_notes(perfil, originais)
        if notas:
            perfil = replace_observations(perfil, [*perfil.observations, *notas])

        proprios = _column_findings(perfil, amostras)
        perfis.append(replace_warnings(perfil, proprios))
        achados.extend(proprios)

    duplicadas, _, vazias_no_df = duplicate_row_count(original)

    total_celulas = linhas * len(perfis)
    preenchidas = sum(p.filled_count for p in perfis)

    return ProfileResult(
        source_file=result.source_file,
        selected_sheet=result.selected_sheet,
        header_row=result.header_row,
        row_count=linhas,
        column_count=len(perfis),
        total_cells=total_celulas,
        filled_cells=preenchidas,
        empty_cells=total_celulas - preenchidas,
        fill_rate=round(preenchidas / total_celulas, 4) if total_celulas else 0.0,
        duplicate_row_count=duplicadas,
        completely_empty_row_count=result.skipped_empty_rows + vazias_no_df,
        completely_empty_column_count=sum(1 for p in perfis if p.inferred_type == "vazio"),
        mixed_type_column_count=sum(1 for p in perfis if p.inferred_type == "misto"),
        excel_error_count=sum(p.excel_error_count for p in perfis),
        conversion_count=len(result.conversions),
        warning_count=len(result.warnings),
        reader_confidence=result.confidence,
        columns=perfis,
        findings=achados,
    )


def replace_observations(perfil: ColumnProfile, observacoes: list[str]) -> ColumnProfile:
    """ColumnProfile e frozen: trocar um campo cria uma copia."""
    return replace(perfil, observations=observacoes)


def replace_warnings(perfil: ColumnProfile, avisos: list[Finding]) -> ColumnProfile:
    return replace(perfil, warnings=avisos)


__all__ = ["profile_workbook"]
