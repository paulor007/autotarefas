"""
Geracao de artefatos da Auditoria de planilha.

A partir do resultado da validacao (`TaskResult`) e do DataFrame ja
processado (normalizado, no modo limpeza), este modulo:

- separa registros VALIDOS de INVALIDOS. Regra: uma linha e invalida
  quando tem ao menos um problema de severidade ERROR. Avisos (ex.:
  linha duplicada) NAO invalidam a linha.
- categoriza cada problema (cpf, email, telefone, obrigatorio,
  duplicado, ...) para o resumo por categoria.
- escreve os dois CSVs de saida do pipeline:
    - ``registros_validos.csv``   — pronto para o proximo passo
    - ``registros_invalidos.csv`` — com uma coluna ``motivo`` ao final

Nao inventa dado: apenas separa e anota. Os dados que vao para o CSV
sao exatamente os do DataFrame processado (normalizado quando em modo
limpeza; originais em modo auditoria).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from autotarefas.core.base import TaskResult

#: Nome fixo do CSV de registros validos.
VALID_CSV_NAME = "registros_validos.csv"
#: Nome fixo do CSV de registros invalidos.
INVALID_CSV_NAME = "registros_invalidos.csv"
#: Nome da coluna de motivo anexada aos invalidos.
REASON_COLUMN = "motivo"


# ============================================================
# Categorizacao de problemas
# ============================================================


#: Regras de categorizacao, em ordem de prioridade. A primeira cujo
#: termo aparecer na mensagem vence. "duplicado"/"obrigatorio" vem antes
#: de cpf/email/telefone porque a mensagem de duplicidade cita o nome da
#: coluna (que pode conter "cpf", "email", etc.).
_CATEGORY_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("duplicad",), "duplicado"),
    (("obrigat",), "obrigatorio"),
    (("cpf",), "cpf"),
    (("cnpj",), "cnpj"),
    (("mail",), "email"),
    (("telefone",), "telefone"),
    (("curto",), "tamanho"),
    (("menor que", "maior que"), "intervalo"),
    (("aceitos",), "enum"),
    (("nao e um",), "tipo"),
    (("formato",), "formato"),
)


def categorize_message(message: str) -> str:
    """
    Classifica a mensagem de um problema em uma categoria legivel.

    Heuristica baseada no texto das mensagens que o proprio projeto gera
    (ver `_CATEGORY_RULES`). Categorias possiveis: duplicado, obrigatorio,
    cpf, cnpj, email, telefone, tamanho, intervalo, enum, tipo, formato,
    outro.
    """
    m = message.lower()
    for needles, category in _CATEGORY_RULES:
        if any(needle in m for needle in needles):
            return category
    return "outro"


def count_issues_by_category(issues: list[dict[str, object]]) -> dict[str, int]:
    """
    Conta quantos problemas existem por categoria (todos os issues).

    Args:
        issues: Lista de issues serializados (dicts com chave "message").

    Returns:
        Dict ``{categoria: quantidade}`` (ordem de primeira aparicao).
    """
    counts: dict[str, int] = {}
    for issue in issues:
        category = categorize_message(str(issue.get("message", "")))
        counts[category] = counts.get(category, 0) + 1
    return counts


# ============================================================
# Separacao valido / invalido
# ============================================================


def split_valid_invalid(
    result: TaskResult,
) -> tuple[list[int], list[int], dict[int, list[str]]]:
    """
    Separa numeros de linha validos de invalidos a partir dos issues.

    Uma linha e INVALIDA se aparece em ao menos um issue de severidade
    ERROR (avisos nao invalidam). Numeros de linha sao 1-based (a 1a
    linha de dados e a 2, por causa do cabecalho).

    Returns:
        Tupla ``(linhas_validas, linhas_invalidas, motivos)`` onde
        ``motivos`` mapeia cada linha invalida para a lista de mensagens
        de erro daquela linha.
    """
    total_rows = int(result.data.get("rows", 0))
    issues: list[dict[str, object]] = result.data.get("issues", [])

    reasons: dict[int, list[str]] = {}
    for issue in issues:
        if issue.get("severity") != "error":
            continue
        line = issue.get("line")
        if not isinstance(line, int) or line < 2:  # noqa: PLR2004 — 1=cabecalho
            continue
        reasons.setdefault(line, []).append(str(issue.get("message", "")))

    invalid_lines = sorted(reasons)
    valid_lines = [n for n in range(2, total_rows + 2) if n not in reasons]
    return valid_lines, invalid_lines, reasons


# ============================================================
# Escrita dos CSVs
# ============================================================


def _lines_to_indices(lines: list[int]) -> list[int]:
    """Converte numeros de linha (1-based, cabecalho=1) em indices do df."""
    return [n - 2 for n in lines]


def write_valid_csv(dataframe: pd.DataFrame, valid_lines: list[int], path: Path) -> None:
    """Escreve o CSV de registros validos (utf-8-sig, sem indice)."""
    subset = dataframe.iloc[_lines_to_indices(valid_lines)]
    path.parent.mkdir(parents=True, exist_ok=True)
    subset.to_csv(path, index=False, encoding="utf-8-sig")


def write_invalid_csv(
    dataframe: pd.DataFrame,
    invalid_lines: list[int],
    reasons: dict[int, list[str]],
    path: Path,
) -> None:
    """
    Escreve o CSV de registros invalidos com a coluna ``motivo`` ao final.

    O motivo de cada linha e a juncao das mensagens de erro daquela linha.
    """
    subset = dataframe.iloc[_lines_to_indices(invalid_lines)].copy()
    subset[REASON_COLUMN] = [" | ".join(reasons.get(n, [])) for n in invalid_lines]
    path.parent.mkdir(parents=True, exist_ok=True)
    subset.to_csv(path, index=False, encoding="utf-8-sig")


def write_separation_csvs(
    dataframe: pd.DataFrame,
    result: TaskResult,
    out_dir: Path,
) -> tuple[Path, Path]:
    """
    Gera os dois CSVs de separacao em ``out_dir`` (nomes fixos).

    Returns:
        Tupla ``(caminho_validos, caminho_invalidos)``.
    """
    valid_lines, invalid_lines, reasons = split_valid_invalid(result)
    out_dir.mkdir(parents=True, exist_ok=True)

    valid_path = out_dir / VALID_CSV_NAME
    invalid_path = out_dir / INVALID_CSV_NAME
    write_valid_csv(dataframe, valid_lines, valid_path)
    write_invalid_csv(dataframe, invalid_lines, reasons, invalid_path)
    return valid_path, invalid_path


__all__ = [
    "INVALID_CSV_NAME",
    "REASON_COLUMN",
    "VALID_CSV_NAME",
    "categorize_message",
    "count_issues_by_category",
    "split_valid_invalid",
    "write_invalid_csv",
    "write_separation_csvs",
    "write_valid_csv",
]
