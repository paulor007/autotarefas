"""
Testes da Auditoria de planilha: schema estendido (format/min_length/unique)
e deteccao de duplicatas cross-row na ValidateTask.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from autotarefas.core.base import TaskResult
from autotarefas.tasks.validate import ColumnSchema, Schema, ValidateTask


def _make_csv(tmp_path: Path, content: str, name: str = "dados.csv") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _issues(result: TaskResult) -> list[dict[str, Any]]:
    return cast("list[dict[str, Any]]", result.data["issues"])


def _messages(result: TaskResult) -> list[str]:
    return [str(i["message"]) for i in _issues(result)]


class TestFormatEmail:
    def test_email_invalido_vira_erro(self, tmp_path: Path) -> None:
        csv = _make_csv(tmp_path, "email\nana@example.com\nbruno-invalido\n")
        schema = Schema(columns=[ColumnSchema(name="email", format="email")])
        result = ValidateTask(file_path=csv, schema=schema).run()
        assert not result.is_success
        assert any("mail" in m.lower() for m in _messages(result))

    def test_emails_validos_passam(self, tmp_path: Path) -> None:
        csv = _make_csv(tmp_path, "email\nana@example.com\nbruno@empresa.io\n")
        schema = Schema(columns=[ColumnSchema(name="email", format="email")])
        result = ValidateTask(file_path=csv, schema=schema).run()
        assert result.is_success


class TestFormatPhone:
    def test_telefone_invalido(self, tmp_path: Path) -> None:
        csv = _make_csv(tmp_path, "telefone\n(11) 98765-4321\n9999\n")
        schema = Schema(columns=[ColumnSchema(name="telefone", format="phone")])
        result = ValidateTask(file_path=csv, schema=schema).run()
        assert not result.is_success
        assert any("elefone" in m for m in _messages(result))


class TestMinLength:
    def test_nome_curto(self, tmp_path: Path) -> None:
        csv = _make_csv(tmp_path, "nome\nAna\nA\n")
        schema = Schema(columns=[ColumnSchema(name="nome", min_length=3)])
        result = ValidateTask(file_path=csv, schema=schema).run()
        assert not result.is_success
        assert any("curto" in m for m in _messages(result))


class TestUniqueColumn:
    def test_cpf_duplicado_com_mascara_diferente(self, tmp_path: Path) -> None:
        # mesmo CPF, um com mascara e outro sem -> duplicata detectada
        csv = _make_csv(tmp_path, "cpf\n111.444.777-35\n11144477735\n")
        schema = Schema(
            columns=[ColumnSchema(name="cpf", validator_br="cpf", unique=True)],
        )
        result = ValidateTask(file_path=csv, schema=schema).run()
        assert not result.is_success
        assert any("duplicado" in m for m in _messages(result))
        # ambas as linhas (2 e 3) sao apontadas
        lines = {i["line"] for i in _issues(result) if "duplicado" in str(i["message"])}
        assert lines == {2, 3}

    def test_email_unico_sem_duplicata(self, tmp_path: Path) -> None:
        csv = _make_csv(tmp_path, "email\na@x.com\nb@x.com\n")
        schema = Schema(
            columns=[ColumnSchema(name="email", format="email", unique=True)],
        )
        result = ValidateTask(file_path=csv, schema=schema).run()
        assert result.is_success


class TestDuplicateRows:
    def test_linha_identica_vira_warning(self, tmp_path: Path) -> None:
        csv = _make_csv(tmp_path, "nome,cidade\nAna,SP\nBruno,RJ\nana,sp\n")
        schema = Schema(
            columns=[ColumnSchema(name="nome"), ColumnSchema(name="cidade")],
            detect_duplicate_rows=True,
        )
        result = ValidateTask(file_path=csv, schema=schema).run()
        # warning nao invalida a planilha
        assert result.is_success
        warnings = [i for i in _issues(result) if i["severity"] == "warning"]
        assert any("duplicada" in str(w["message"]) for w in warnings)
        # a 2a ocorrencia (linha 4) e marcada
        assert any(w["line"] == 4 for w in warnings)
