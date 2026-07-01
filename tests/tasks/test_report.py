"""Testes para autotarefas.tasks.report."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from autotarefas.core.base import TaskResult, TaskStatus
from autotarefas.tasks.report import (
    CSV_FIELDNAMES,
    generate_cleaning_summary,
    generate_summary,
    write_csv_report,
    write_json_report,
)

# ============================================================
# Fixtures — TaskResult sinteticos
# ============================================================


@pytest.fixture
def result_sem_issues() -> TaskResult:
    """Result de validacao bem-sucedida (sem problemas)."""
    return TaskResult(
        task_name="validate",
        status=TaskStatus.SUCCESS,
        started_at=datetime(2026, 5, 15, 10, 30, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 15, 10, 30, 0, tzinfo=UTC),
        duration_ms=100,
        rows_affected=10,
        rows_failed=0,
        data={
            "file": "/path/to/dados.csv",
            "rows": 10,
            "columns": ["nome", "idade"],
            "total_issues": 0,
            "total_errors": 0,
            "total_warnings": 0,
            "issues": [],
        },
    )


@pytest.fixture
def result_com_issues() -> TaskResult:
    """Result com 2 errors + 1 warning."""
    return TaskResult(
        task_name="validate",
        status=TaskStatus.FAILURE,
        started_at=datetime(2026, 5, 15, 10, 30, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 15, 10, 30, 1, tzinfo=UTC),
        duration_ms=1000,
        rows_affected=0,
        rows_failed=3,
        error_message="3 erro(s) de validacao",
        error_type="ValidationIssuesError",
        data={
            "file": "/path/to/dados.csv",
            "rows": 5,
            "columns": ["nome", "idade", "cpf"],
            "total_issues": 3,
            "total_errors": 2,
            "total_warnings": 1,
            "issues": [
                {
                    "line": 3,
                    "column": "idade",
                    "message": "Valor 200 maior que o maximo 150",
                    "severity": "error",
                    "value": "200",
                },
                {
                    "line": 5,
                    "column": "cpf",
                    "message": "CPF invalido: '111.111.111-11'",
                    "severity": "error",
                    "value": "111.111.111-11",
                },
                {
                    "line": 7,
                    "column": "nome",
                    "message": "Nome suspeito",
                    "severity": "warning",
                    "value": "x",
                },
            ],
        },
    )


@pytest.fixture
def result_falha_estrutural() -> TaskResult:
    """Result de falha estrutural — data NAO tem 'issues' (caso da Parte 3.1)."""
    return TaskResult(
        task_name="validate",
        status=TaskStatus.FAILURE,
        started_at=datetime(2026, 5, 15, 10, 30, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 15, 10, 30, 0, tzinfo=UTC),
        duration_ms=50,
        error_message="Colunas obrigatorias faltando",
        error_type="MissingColumnsError",
        data={
            "file": "/path/to/dados.csv",
            "expected_columns": ["nome", "idade"],
            "actual_columns": ["nome"],
            "missing": ["idade"],
            # SEM "issues" — falha antes de chegar na validacao de conteudo
        },
    )


@pytest.fixture
def result_com_caracteres_pt() -> TaskResult:
    """Result com acentos pra testar UTF-8."""
    return TaskResult(
        task_name="validate",
        status=TaskStatus.FAILURE,
        started_at=datetime(2026, 5, 15, 10, 30, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 15, 10, 30, 0, tzinfo=UTC),
        duration_ms=100,
        data={
            "file": "/path/açaí.csv",
            "rows": 1,
            "columns": ["nome"],
            "total_issues": 1,
            "total_errors": 1,
            "total_warnings": 0,
            "issues": [
                {
                    "line": 2,
                    "column": "nome",
                    "message": "Nome inválido: João da Silva",
                    "severity": "error",
                    "value": "João",
                }
            ],
        },
    )


# ============================================================
# Tests: write_json_report
# ============================================================


class TestWriteJsonReport:
    """Testes do write_json_report."""

    def test_cria_arquivo(self, tmp_path: Path, result_sem_issues: TaskResult) -> None:
        out = tmp_path / "rel.json"
        write_json_report(result_sem_issues, out)
        assert out.exists()

    def test_json_valido_parseavel(self, tmp_path: Path, result_sem_issues: TaskResult) -> None:
        """Arquivo gerado e JSON valido (parseavel de volta)."""
        out = tmp_path / "rel.json"
        write_json_report(result_sem_issues, out)

        with open(out, encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, dict)

    def test_inclui_metadados(self, tmp_path: Path, result_com_issues: TaskResult) -> None:
        """Tem task_name, status, timestamps, etc."""
        out = tmp_path / "rel.json"
        write_json_report(result_com_issues, out)

        with open(out, encoding="utf-8") as f:
            data = json.load(f)

        assert data["task_name"] == "validate"
        assert data["status"] == "failure"
        assert data["duration_ms"] == 1000
        assert data["error_type"] == "ValidationIssuesError"

    def test_status_e_string_nao_enum(self, tmp_path: Path, result_sem_issues: TaskResult) -> None:
        """status no JSON e string, nao objeto enum."""
        out = tmp_path / "rel.json"
        write_json_report(result_sem_issues, out)

        with open(out, encoding="utf-8") as f:
            data = json.load(f)

        assert data["status"] == "success"
        assert isinstance(data["status"], str)

    def test_datetimes_em_iso_format(self, tmp_path: Path, result_com_issues: TaskResult) -> None:
        """Timestamps no formato ISO 8601 (parseavel de volta)."""
        out = tmp_path / "rel.json"
        write_json_report(result_com_issues, out)

        with open(out, encoding="utf-8") as f:
            data = json.load(f)

        # Parseavel de volta?
        parsed = datetime.fromisoformat(data["started_at"])
        assert parsed.year == 2026

    def test_inclui_data_spread(self, tmp_path: Path, result_com_issues: TaskResult) -> None:
        """Campos do result.data viram top-level (sem aninhar em 'data')."""
        out = tmp_path / "rel.json"
        write_json_report(result_com_issues, out)

        with open(out, encoding="utf-8") as f:
            data = json.load(f)

        # file, rows, etc. estao na raiz
        assert "file" in data
        assert "issues" in data
        assert data["total_issues"] == 3

    def test_caracteres_pt_preservados(
        self, tmp_path: Path, result_com_caracteres_pt: TaskResult
    ) -> None:
        """Acentos sao mantidos (ensure_ascii=False)."""
        out = tmp_path / "rel.json"
        write_json_report(result_com_caracteres_pt, out)

        # Le como texto puro pra confirmar que NAO foi escapado pra \u00e9 etc.
        content = out.read_text(encoding="utf-8")
        assert "João" in content
        assert "inválido" in content
        # NAO deve ter escape unicode
        assert "\\u" not in content

    def test_cria_pasta_pai_se_nao_existir(
        self, tmp_path: Path, result_sem_issues: TaskResult
    ) -> None:
        """Cria diretorios faltantes (mkdir parents=True)."""
        out = tmp_path / "subpasta" / "outra" / "rel.json"
        write_json_report(result_sem_issues, out)
        assert out.exists()


# ============================================================
# Tests: write_csv_report
# ============================================================


class TestWriteCsvReport:
    """Testes do write_csv_report."""

    def test_cria_arquivo(self, tmp_path: Path, result_com_issues: TaskResult) -> None:
        out = tmp_path / "rel.csv"
        write_csv_report(result_com_issues, out)
        assert out.exists()

    def test_header_correto(self, tmp_path: Path, result_com_issues: TaskResult) -> None:
        """Primeira linha e o header com CSV_FIELDNAMES."""
        out = tmp_path / "rel.csv"
        write_csv_report(result_com_issues, out)

        with open(out, encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)

        assert header == list(CSV_FIELDNAMES)

    def test_registros_corretos(self, tmp_path: Path, result_com_issues: TaskResult) -> None:
        """Registros do issues aparecem como linhas."""
        out = tmp_path / "rel.csv"
        write_csv_report(result_com_issues, out)

        with open(out, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 3
        assert rows[0]["line"] == "3"
        assert rows[0]["column"] == "idade"
        assert "200" in rows[0]["message"]
        assert rows[0]["severity"] == "error"

    def test_csv_vazio_so_header(self, tmp_path: Path, result_sem_issues: TaskResult) -> None:
        """Sem issues: arquivo so com header (CSV valido)."""
        out = tmp_path / "rel.csv"
        write_csv_report(result_sem_issues, out)

        with open(out, encoding="utf-8-sig", newline="") as f:
            lines = f.readlines()

        assert len(lines) == 1  # so o header

    def test_encoding_utf8_com_bom(
        self, tmp_path: Path, result_com_caracteres_pt: TaskResult
    ) -> None:
        """Arquivo CSV comeca com BOM UTF-8 (compatibilidade Excel)."""
        out = tmp_path / "rel.csv"
        write_csv_report(result_com_caracteres_pt, out)

        # Le como bytes pra confirmar o BOM
        raw_bytes = out.read_bytes()
        # BOM UTF-8 = b'\xef\xbb\xbf' (3 bytes no inicio)
        assert raw_bytes.startswith(b"\xef\xbb\xbf")

    def test_caracteres_pt_preservados(
        self, tmp_path: Path, result_com_caracteres_pt: TaskResult
    ) -> None:
        """Acentos sao escritos corretamente em UTF-8."""
        out = tmp_path / "rel.csv"
        write_csv_report(result_com_caracteres_pt, out)

        with open(out, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert "João" in rows[0]["message"]

    def test_falha_estrutural_csv_so_header(
        self, tmp_path: Path, result_falha_estrutural: TaskResult
    ) -> None:
        """Result sem 'issues' no data: CSV tem so o header."""
        out = tmp_path / "rel.csv"
        write_csv_report(result_falha_estrutural, out)

        with open(out, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows == []

    def test_cria_pasta_pai_se_nao_existir(
        self, tmp_path: Path, result_sem_issues: TaskResult
    ) -> None:
        out = tmp_path / "subpasta" / "rel.csv"
        write_csv_report(result_sem_issues, out)
        assert out.exists()


# ============================================================
# Tests: generate_summary
# ============================================================


class TestGenerateSummary:
    """Testes do generate_summary."""

    def test_sem_issues_mostra_ok(self, result_sem_issues: TaskResult) -> None:
        summary = generate_summary(result_sem_issues)
        assert "[OK]" in summary
        assert "Sem problemas" in summary

    def test_com_issues_mostra_totais(self, result_com_issues: TaskResult) -> None:
        summary = generate_summary(result_com_issues)
        assert "3 problema" in summary
        assert "2 erro" in summary
        assert "1 aviso" in summary

    def test_inclui_arquivo_linhas_colunas(self, result_com_issues: TaskResult) -> None:
        summary = generate_summary(result_com_issues)
        assert "dados.csv" in summary
        assert "Linhas:" in summary
        assert "Colunas:" in summary

    def test_lista_issues_com_severity_error(self, result_com_issues: TaskResult) -> None:
        """Errors marcados com [ERROR]."""
        summary = generate_summary(result_com_issues)
        assert "[ERROR]" in summary

    def test_lista_issues_com_severity_warning(self, result_com_issues: TaskResult) -> None:
        """Warnings marcados com [WARN]."""
        summary = generate_summary(result_com_issues)
        assert "[WARN]" in summary

    def test_mostra_localizacao_dos_issues(self, result_com_issues: TaskResult) -> None:
        """Linha e coluna aparecem na lista de issues."""
        summary = generate_summary(result_com_issues)
        assert "Linha 3" in summary
        assert "idade" in summary

    def test_trunca_quando_excede_max(self) -> None:
        """Mostra so os primeiros N issues."""
        # Cria result com 15 issues
        issues = [
            {
                "line": i,
                "column": "x",
                "message": f"erro {i}",
                "severity": "error",
                "value": None,
            }
            for i in range(2, 17)
        ]
        result = TaskResult(
            task_name="validate",
            status=TaskStatus.FAILURE,
            started_at=datetime(2026, 5, 15, tzinfo=UTC),
            finished_at=datetime(2026, 5, 15, tzinfo=UTC),
            duration_ms=10,
            data={
                "file": "x.csv",
                "rows": 15,
                "columns": ["x"],
                "total_issues": 15,
                "total_errors": 15,
                "total_warnings": 0,
                "issues": issues,
            },
        )
        summary = generate_summary(result, max_issues_shown=10)
        assert "e mais 5 problema" in summary

    def test_max_issues_shown_customizavel(self, result_com_issues: TaskResult) -> None:
        """Default 10 — mas pode mudar pra qualquer N."""
        # result_com_issues tem 3 issues. max=2 deve truncar.
        summary = generate_summary(result_com_issues, max_issues_shown=2)
        assert "e mais 1 problema" in summary

    def test_max_issues_zero_nao_lista_nenhum(self, result_com_issues: TaskResult) -> None:
        """max=0: nao lista issue individual, so estatistica."""
        summary = generate_summary(result_com_issues, max_issues_shown=0)
        # Estatisticas presentes
        assert "3 problema" in summary
        # Mas nenhum issue listado (sem [ERROR] tag)
        assert "[ERROR]" not in summary

    def test_retorna_string(self, result_com_issues: TaskResult) -> None:
        """Retorna str (nao list, nao stream)."""
        summary = generate_summary(result_com_issues)
        assert isinstance(summary, str)


# ============================================================
# Tests: Edge cases
# ============================================================


class TestEdgeCases:
    """Casos extremos / defensive."""

    def test_json_de_falha_estrutural_funciona(
        self, tmp_path: Path, result_falha_estrutural: TaskResult
    ) -> None:
        """JSON e gerado mesmo sem campo 'issues' no data."""
        out = tmp_path / "rel.json"
        write_json_report(result_falha_estrutural, out)
        assert out.exists()

        with open(out, encoding="utf-8") as f:
            data = json.load(f)
        assert data["error_type"] == "MissingColumnsError"

    def test_summary_de_result_sem_metadados(self) -> None:
        """generate_summary tolera result.data com poucos campos."""
        result = TaskResult(
            task_name="x",
            status=TaskStatus.SUCCESS,
            started_at=datetime(2026, 5, 15, tzinfo=UTC),
            finished_at=datetime(2026, 5, 15, tzinfo=UTC),
            duration_ms=10,
            data={},  # totalmente vazio!
        )
        # Nao deve levantar excecao
        summary = generate_summary(result)
        assert summary  # nao vazio

    def test_csv_de_falha_estrutural_so_header(
        self, tmp_path: Path, result_falha_estrutural: TaskResult
    ) -> None:
        """CSV funciona mesmo se data nao tem 'issues'."""
        out = tmp_path / "rel.csv"
        write_csv_report(result_falha_estrutural, out)
        assert out.exists()

    def test_csv_fieldnames_e_tupla(self) -> None:
        """CSV_FIELDNAMES e tupla (constante imutavel)."""
        assert isinstance(CSV_FIELDNAMES, tuple)
        assert "line" in CSV_FIELDNAMES
        assert "column" in CSV_FIELDNAMES
        assert "message" in CSV_FIELDNAMES


# ============================================================
# generate_summary: issue sem coluna (linha duplicada)
# ============================================================


class TestGenerateSummaryColumnNone:
    def test_linha_inteira_em_vez_de_coluna_none(self) -> None:
        result = TaskResult(
            task_name="validate",
            status=TaskStatus.SUCCESS,
            started_at=datetime(2026, 5, 15, tzinfo=UTC),
            finished_at=datetime(2026, 5, 15, tzinfo=UTC),
            duration_ms=10,
            data={
                "file": "x.csv",
                "rows": 4,
                "columns": ["a", "b"],
                "total_issues": 1,
                "total_errors": 0,
                "total_warnings": 1,
                "issues": [
                    {
                        "line": 4,
                        "column": None,
                        "message": "Linha duplicada (identica a linha 2)",
                        "severity": "warning",
                        "value": None,
                    }
                ],
            },
        )
        summary = generate_summary(result)
        assert "linha inteira" in summary
        assert "coluna 'None'" not in summary
        assert "identica a linha 2" in summary


# ============================================================
# generate_cleaning_summary (audit trail)
# ============================================================


class TestGenerateCleaningSummary:
    def _result(self, changes: list[dict[str, object]]) -> TaskResult:
        return TaskResult(
            task_name="validate",
            status=TaskStatus.SUCCESS,
            started_at=datetime(2026, 5, 15, tzinfo=UTC),
            finished_at=datetime(2026, 5, 15, tzinfo=UTC),
            duration_ms=10,
            data={
                "mode": "limpeza",
                "cleaning_changes": changes,
                "total_cleaned": len(changes),
            },
        )

    def test_sem_normalizacoes(self) -> None:
        summary = generate_cleaning_summary(self._result([]))
        assert "Nenhuma normalizacao" in summary

    def test_com_normalizacoes(self) -> None:
        changes: list[dict[str, object]] = [
            {
                "line": 2,
                "column": "email",
                "before": "A@X.COM",
                "after": "a@x.com",
                "rules": ["minusculo"],
            }
        ]
        summary = generate_cleaning_summary(self._result(changes))
        assert "1 valor(es) normalizado" in summary
        assert "A@X.COM" in summary
        assert "a@x.com" in summary
        assert "minusculo" in summary
