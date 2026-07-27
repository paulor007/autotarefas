"""
Pacote operacional de uma execucao: evidencias que o cliente consegue usar.

Um relatorio dizendo "23 problemas" nao encerra o trabalho de ninguem. O
cliente ainda precisa achar as linhas, separar o que segue do que volta,
corrigir, reenviar — e, meses depois, provar qual arquivo e qual
configuracao produziram aquele resultado.

Este modulo transforma o resultado de uma validacao num diretorio assim:

    <destino>/
      manifest.json                 o que rodou, sobre o que, com que hashes
      resumo.json                   o relatorio JSON que o projeto ja gerava
      problemas.csv                 uma linha por problema, para abrir no Excel
      registros_validos.csv         o que passou
      registros_para_revisao.csv    o que precisa de gente olhando
      schema_efetivo.yaml           copia exata da configuracao aplicada

NADA AQUI ALTERA O ARQUIVO DO CLIENTE. O manifesto registra o sha256 da
entrada; um teste confere que ele e o mesmo antes e depois.

POLITICA DE CLASSIFICACAO (uma so, e explicita):

    linha com ERRO            -> revisao
    linha so com AVISO        -> valida, e sinalizada no manifesto
    linha sem problema        -> valida
    problema de grupo         -> TODAS as linhas do grupo vao para revisao
    problema sem linha        -> entra em problemas.csv, nao classifica ninguem

    `--strict-warnings` muda o RESULTADO DA EXECUCAO (status e exit code),
    nunca o destino de uma linha. Se um aviso mudasse a linha de arquivo, a
    mesma planilha teria duas verdades conforme a flag — e o cliente veria
    "registro valido" na tela e o registro dentro de revisao no disco.

HONESTIDADE DO MANIFESTO: se a coleta parou no `--max-issues`, a
classificacao esta incompleta por construcao — linhas problematicas alem do
limite nao foram vistas. Nesse caso o status e `incomplete` e o manifesto
diz por que. Um pacote que se declara completo sem ser e pior que nenhum.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from autotarefas import __version__
from autotarefas.tasks.artifacts import (
    categorize_message,
    split_valid_invalid,
    write_valid_csv,
)

if TYPE_CHECKING:
    import pandas as pd

    from autotarefas.core import TaskResult

MANIFEST_NAME = "manifest.json"
SUMMARY_NAME = "resumo.json"
PROBLEMS_NAME = "problemas.csv"
VALID_NAME = "registros_validos.csv"
REVIEW_NAME = "registros_para_revisao.csv"
SCHEMA_NAME = "schema_efetivo.yaml"

#: Caracteres que um programa de planilha pode interpretar como inicio de
#: formula. Nao alteramos o dado — apenas contamos e avisamos (ver
#: `formula_like_cells`).
_FORMULA_PREFIXES = ("=", "+", "-", "@")

_CHUNK = 65536


class PackageError(RuntimeError):
    """Falha ao montar o pacote — reportada, nunca silenciada."""


@dataclass(frozen=True, slots=True)
class Classification:
    """Como cada linha do arquivo foi classificada."""

    valid_lines: tuple[int, ...]
    review_lines: tuple[int, ...]
    warned_lines: tuple[int, ...]
    """Linhas validas que carregam pelo menos um aviso."""
    unlocated_issues: int
    """Problemas sem linha propria (nao classificam ninguem)."""
    truncated: bool
    """A coleta parou no limite de issues: a classificacao esta incompleta."""


@dataclass(slots=True)
class PackageResult:
    """O que foi produzido."""

    directory: Path
    status: str
    files: list[dict[str, Any]] = field(default_factory=list)
    classification: Classification | None = None
    formula_like_cells: int = 0


def sha256_file(path: Path) -> str:
    """sha256 de um arquivo, lido em blocos (nao carrega tudo na memoria)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while bloco := handle.read(_CHUNK):
            digest.update(bloco)
    return digest.hexdigest()


def _first_data_line(result: TaskResult) -> int:
    """Linha fisica do primeiro registro (cabecalho + 1). Padrao: 2."""
    cabecalho = result.data.get("header_row")
    return (cabecalho if isinstance(cabecalho, int) and cabecalho >= 1 else 1) + 1


def classify_rows(result: TaskResult) -> Classification:
    """
    Classifica as linhas a partir dos issues ja coletados.

    Reusa `split_valid_invalid` (que desde a 1.7 honra `related_lines`), e
    acrescenta o que o pacote precisa: quais linhas validas tem aviso, quantos
    problemas nao tem linha, e se a coleta foi truncada.

    Complexidade: O(n_issues + n_linhas). Uma passada em cada.
    """
    validas, revisao, _ = split_valid_invalid(result)
    issues: list[dict[str, Any]] = result.data.get("issues", [])

    em_revisao = set(revisao)
    avisadas: set[int] = set()
    sem_linha = 0

    for issue in issues:
        linhas = issue.get("related_lines") or [issue.get("line")]
        numeros = [n for n in linhas if isinstance(n, int) and n >= 2]  # noqa: PLR2004
        if not numeros:
            sem_linha += 1
            continue
        if issue.get("severity") == "warning":
            avisadas.update(n for n in numeros if n not in em_revisao)

    return Classification(
        valid_lines=tuple(validas),
        review_lines=tuple(revisao),
        warned_lines=tuple(sorted(avisadas)),
        unlocated_issues=sem_linha,
        truncated=bool(result.data.get("issues_truncated", False)),
    )


def write_problems_csv(result: TaskResult, path: Path) -> None:
    """
    Uma linha por problema, com os metadados ESTRUTURAIS do issue.

    `rule`, `category` e `related_lines` vem do proprio issue (a 1.7 os
    adicionou ao modelo). A `message` continua sendo texto para pessoas e
    NAO e analisada para extrair nada.

    NAO ha coluna `run_id` aqui, de proposito: o run_id muda a cada execucao
    e tornaria este arquivo irreproduzivel — duas execucoes sobre a mesma
    entrada e o mesmo schema produziriam bytes diferentes. Ele vive no
    manifesto, no mesmo diretorio, que e onde a procedencia pertence.

    A unica heuristica que sobrou e o
    `categorize_message` legado, usado so quando o produtor do issue nao
    informou categoria — e ela e substituivel produtor a produtor, sem
    mexer aqui.
    """
    issues: list[dict[str, Any]] = result.data.get("issues", [])
    arquivo = str(result.data.get("file", ""))

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "issue_id",
                "severity",
                "category",
                "rule",
                "physical_line",
                "column",
                "value",
                "message",
                "related_lines",
                "source_file",
            ]
        )
        for i, issue in enumerate(issues, start=1):
            categoria = issue.get("category") or categorize_message(str(issue.get("message", "")))
            relacionadas = issue.get("related_lines") or []
            writer.writerow(
                [
                    f"{i:06d}",
                    issue.get("severity", ""),
                    categoria,
                    issue.get("rule") or "",
                    issue.get("line", ""),
                    issue.get("column") or "",
                    issue.get("value") or "",
                    issue.get("message", ""),
                    " ".join(str(n) for n in relacionadas),
                    arquivo,
                ]
            )


def write_review_csv(
    dataframe: pd.DataFrame,
    review_lines: tuple[int, ...],
    path: Path,
    first_data_line: int = 2,
) -> None:
    """
    As linhas que precisam de revisao, com os VALORES ORIGINAIS.

    Sem coluna tecnica no meio das colunas do cliente e sem correcao
    automatica: isto nao e um "arquivo corrigido", e a fila de trabalho de
    quem vai corrigir. O cruzamento com `problemas.csv` e por numero de
    linha fisica, que a coluna `physical_line` de la carrega.
    """
    indices = [n - first_data_line for n in review_lines]
    recorte = dataframe.iloc[indices] if indices else dataframe.iloc[0:0]
    recorte.to_csv(path, index=False, encoding="utf-8-sig")


def count_formula_like(dataframe: pd.DataFrame) -> int:
    """
    Conta celulas cujo texto comeca com =, +, - ou @.

    O dado NAO e alterado: um valor que comeca com '-' costuma ser um numero
    negativo legitimo, e "consertar" isso corromperia a planilha do cliente.
    O manifesto registra a contagem para que quem for abrir o arquivo num
    programa de planilha saiba que ha celulas que ele pode tentar interpretar
    como formula.
    """
    total = 0
    for coluna in dataframe.columns:
        serie = dataframe[coluna].astype(str)
        total += int(serie.str.startswith(_FORMULA_PREFIXES).sum())
    return total


def _artifact_entry(path: Path, tipo: str) -> dict[str, Any]:
    return {
        "filename": path.name,
        "type": tipo,
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
    }


def build_package(  # noqa: PLR0913 - todos nomeados; agrupar em objeto so pioraria
    destination: Path,
    *,
    result: TaskResult,
    dataframe: pd.DataFrame,
    input_path: Path,
    schema_path: Path | None,
    options: dict[str, Any] | None = None,
) -> PackageResult:
    """
    Monta o pacote de evidencias de uma execucao.

    Escreve tudo num diretorio temporario ao lado do destino e so entao o
    move para o lugar. Assim uma falha no meio nao deixa um pacote pela
    metade parecendo completo.

    Args:
        destination: diretorio do pacote (nao pode existir).
        result: resultado da validacao.
        dataframe: o DataFrame ja processado — evita reler o arquivo.
        input_path: a planilha do cliente (so leitura, para o hash).
        schema_path: o schema efetivamente usado, copiado para o pacote.
        options: opcoes relevantes da execucao, para o manifesto.

    Raises:
        PackageError: destino invalido ou falha de escrita.
    """
    if destination.exists():
        msg = (
            f"o destino ja existe: {destination}. "
            "Escolha outro diretorio — nao sobrescrevo pacotes de execucoes anteriores."
        )
        raise PackageError(msg)

    run_id = uuid.uuid4().hex[:16]
    gerado_em = datetime.now(UTC)
    classificacao = classify_rows(result)

    hash_entrada_antes = sha256_file(input_path)

    temporario = destination.parent / f".{destination.name}.parcial"
    if temporario.exists():
        shutil.rmtree(temporario, ignore_errors=True)

    try:
        temporario.mkdir(parents=True)
        arquivos: list[dict[str, Any]] = []

        # resumo: o MESMO relatorio JSON que o projeto ja produz. Nao ha
        # segundo formato de relatorio — so uma copia dele dentro do pacote.
        from autotarefas.tasks.report import write_json_report

        caminho_resumo = temporario / SUMMARY_NAME
        write_json_report(result, caminho_resumo)
        arquivos.append(_artifact_entry(caminho_resumo, "resumo"))

        caminho_problemas = temporario / PROBLEMS_NAME
        write_problems_csv(result, caminho_problemas)
        arquivos.append(_artifact_entry(caminho_problemas, "problemas"))

        caminho_validos = temporario / VALID_NAME
        primeira_linha = _first_data_line(result)
        write_valid_csv(dataframe, list(classificacao.valid_lines), caminho_validos, primeira_linha)
        arquivos.append(_artifact_entry(caminho_validos, "registros_validos"))

        caminho_revisao = temporario / REVIEW_NAME
        write_review_csv(dataframe, classificacao.review_lines, caminho_revisao, primeira_linha)
        arquivos.append(_artifact_entry(caminho_revisao, "registros_para_revisao"))

        if schema_path is not None and schema_path.is_file():
            caminho_schema = temporario / SCHEMA_NAME
            shutil.copy2(schema_path, caminho_schema)
            arquivos.append(_artifact_entry(caminho_schema, "schema_efetivo"))

        formulas = count_formula_like(dataframe)

        status = _status(result, classificacao)
        manifesto = _build_manifest(
            run_id=run_id,
            gerado_em=gerado_em,
            status=status,
            result=result,
            classificacao=classificacao,
            input_path=input_path,
            input_sha=hash_entrada_antes,
            schema_path=schema_path,
            arquivos=arquivos,
            options=options or {},
            formula_like=formulas,
        )
        caminho_manifesto = temporario / MANIFEST_NAME
        caminho_manifesto.write_text(
            json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        temporario.rename(destination)
    except OSError as exc:
        shutil.rmtree(temporario, ignore_errors=True)
        msg = f"nao foi possivel gravar o pacote em {destination}: {exc}"
        raise PackageError(msg) from exc

    # o arquivo do cliente tem que estar intacto: conferimos, nao prometemos
    if sha256_file(input_path) != hash_entrada_antes:  # pragma: no cover - defensivo
        msg = "o arquivo de entrada mudou durante a execucao"
        raise PackageError(msg)

    return PackageResult(
        directory=destination,
        status=status,
        files=arquivos,
        classification=classificacao,
        formula_like_cells=formulas,
    )


def _status(result: TaskResult, classificacao: Classification) -> str:
    """
    Estado honesto da execucao.

    `incomplete` vem primeiro de proposito: se a coleta foi truncada, nao ha
    como afirmar que a classificacao esta completa, mesmo que tudo o mais
    tenha corrido bem.
    """
    if classificacao.truncated:
        return "incomplete"
    if str(result.status) == "failure":
        return "completed_with_issues"
    return "success"


def _build_manifest(  # noqa: PLR0913 - montador do manifesto, campos nomeados
    *,
    run_id: str,
    gerado_em: datetime,
    status: str,
    result: TaskResult,
    classificacao: Classification,
    input_path: Path,
    input_sha: str,
    schema_path: Path | None,
    arquivos: list[dict[str, Any]],
    options: dict[str, Any],
    formula_like: int,
) -> dict[str, Any]:
    dados = result.data
    manifesto: dict[str, Any] = {
        "run_id": run_id,
        "generated_at": gerado_em.isoformat(),
        "status": status,
        "tool": {"name": "autotarefas", "version": __version__},
        "input": {
            "filename": input_path.name,
            "extension": input_path.suffix.lower(),
            "sha256": input_sha,
            "size": input_path.stat().st_size,
            "row_count": dados.get("rows"),
            "column_count": dados.get("columns"),
        },
        "configuration": {
            "schema_filename": schema_path.name if schema_path else None,
            "schema_sha256": (
                sha256_file(schema_path) if schema_path and schema_path.is_file() else None
            ),
            "generated_from": dados.get("generated_from"),
            "header_row": dados.get("header_row"),
            "selected_sheet": dados.get("selected_sheet"),
            "options": options,
        },
        "result": {
            "valid_rows": len(classificacao.valid_lines),
            "review_rows": len(classificacao.review_lines),
            "warned_rows": len(classificacao.warned_lines),
            "errors": dados.get("total_errors", 0),
            "warnings": dados.get("total_warnings", 0),
            "total_issues": dados.get("total_issues", 0),
            "unlocated_issues": classificacao.unlocated_issues,
            "issues_by_category": dados.get("issues_by_category", {}),
        },
        "artifacts": arquivos,
        "notes": [],
    }

    if classificacao.truncated:
        manifesto["notes"].append(
            "A coleta de problemas atingiu o limite (--max-issues): pode haver "
            "linhas problematicas nao classificadas. Rode sem o limite para um "
            "pacote completo."
        )
    if formula_like:
        manifesto["notes"].append(
            f"{formula_like} celula(s) comecam com =, +, - ou @ e podem ser "
            "interpretadas como formula por programas de planilha. Os valores "
            "foram preservados exatamente como estavam."
        )
    if str(result.status) == "failure":
        manifesto["notes"].append(
            "A validacao encontrou erros: veja problemas.csv e registros_para_revisao.csv."
        )
    return manifesto


__all__ = [
    "MANIFEST_NAME",
    "PROBLEMS_NAME",
    "REVIEW_NAME",
    "SCHEMA_NAME",
    "SUMMARY_NAME",
    "VALID_NAME",
    "Classification",
    "PackageError",
    "PackageResult",
    "build_package",
    "classify_rows",
    "count_formula_like",
    "sha256_file",
    "write_problems_csv",
    "write_review_csv",
]
