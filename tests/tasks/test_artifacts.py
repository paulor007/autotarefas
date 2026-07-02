"""Testes para autotarefas.tasks.artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from autotarefas.core.base import TaskResult, TaskStatus
from autotarefas.tasks.artifacts import (
    categorize_message,
    count_issues_by_category,
    split_valid_invalid,
    write_invalid_csv,
    write_separation_csvs,
    write_valid_csv,
)


def _result(rows: int, issues: list[dict[str, object]]) -> TaskResult:
    return TaskResult(
        task_name="validate",
        status=TaskStatus.SUCCESS,
        started_at=datetime(2026, 5, 15, tzinfo=UTC),
        finished_at=datetime(2026, 5, 15, tzinfo=UTC),
        duration_ms=1,
        data={"rows": rows, "issues": issues},
    )


class TestCategorizeMessage:
    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ("CPF invalido: '111'", "cpf"),
            ("CNPJ invalido: 'x'", "cnpj"),
            ("E-mail invalido: 'x'", "email"),
            ("Telefone invalido: '9999'", "telefone"),
            ("Valor obrigatorio nao informado", "obrigatorio"),
            ("Valor duplicado na coluna 'email' (linhas 2, 3)", "duplicado"),
            ("Linha duplicada (identica a linha 2)", "duplicado"),
            ("Valor muito curto: 'B' tem 1 caractere(s), minimo 3", "tamanho"),
            ("Valor 200 maior que o maximo 150", "intervalo"),
            ("Valor 'X' nao esta entre os aceitos: ['A']", "enum"),
            ("Valor 'abc' nao e um int valido", "tipo"),
            ("Formato invalido", "formato"),
            ("Mensagem estranha qualquer", "outro"),
        ],
    )
    def test_categorias(self, message: str, expected: str) -> None:
        assert categorize_message(message) == expected

    def test_duplicado_de_cpf_nao_vira_cpf(self) -> None:
        # a mensagem cita a coluna 'cpf', mas o problema e duplicidade
        assert categorize_message("Valor duplicado na coluna 'cpf' (linhas 2, 3)") == "duplicado"


class TestCountByCategory:
    def test_conta_por_categoria(self) -> None:
        issues: list[dict[str, object]] = [
            {"message": "CPF invalido: 'x'"},
            {"message": "E-mail invalido: 'y'"},
            {"message": "E-mail invalido: 'z'"},
        ]
        assert count_issues_by_category(issues) == {"cpf": 1, "email": 2}


class TestSplitValidInvalid:
    def test_sem_erros_todas_validas(self) -> None:
        valid, invalid, reasons = split_valid_invalid(_result(rows=3, issues=[]))
        assert valid == [2, 3, 4]
        assert invalid == []
        assert reasons == {}

    def test_separa_por_erro(self) -> None:
        issues: list[dict[str, object]] = [
            {"line": 3, "column": "email", "message": "E-mail invalido", "severity": "error"},
            {"line": 3, "column": "cpf", "message": "CPF invalido", "severity": "error"},
            {"line": 4, "column": None, "message": "Linha duplicada", "severity": "warning"},
        ]
        valid, invalid, reasons = split_valid_invalid(_result(rows=3, issues=issues))
        # linha 3 tem erros -> invalida; linha 4 so tem aviso -> valida
        assert valid == [2, 4]
        assert invalid == [3]
        assert reasons[3] == ["E-mail invalido", "CPF invalido"]


class TestWriteCsvs:
    def _df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "nome": ["Ana", "Bruno", "Carla"],
                "email": ["ana@x.com", "bruno-invalido", "carla@x.com"],
            }
        )

    def test_write_valid_csv(self, tmp_path: Path) -> None:
        path = tmp_path / "validos.csv"
        write_valid_csv(self._df(), [2, 4], path)  # linhas 2 e 4 -> indices 0 e 2
        out = pd.read_csv(path)
        assert list(out["nome"]) == ["Ana", "Carla"]
        assert "motivo" not in out.columns

    def test_write_invalid_csv_com_motivo(self, tmp_path: Path) -> None:
        path = tmp_path / "invalidos.csv"
        write_invalid_csv(self._df(), [3], {3: ["E-mail invalido"]}, path)  # linha 3 -> idx 1
        out = pd.read_csv(path)
        assert list(out["nome"]) == ["Bruno"]
        assert list(out["motivo"]) == ["E-mail invalido"]

    def test_write_separation_csvs(self, tmp_path: Path) -> None:
        issues: list[dict[str, object]] = [
            {"line": 3, "column": "email", "message": "E-mail invalido", "severity": "error"},
        ]
        valid_path, invalid_path = write_separation_csvs(
            self._df(), _result(rows=3, issues=issues), tmp_path
        )
        assert valid_path.exists()
        assert invalid_path.exists()
        validos = pd.read_csv(valid_path)
        invalidos = pd.read_csv(invalid_path)
        assert list(validos["nome"]) == ["Ana", "Carla"]
        assert list(invalidos["nome"]) == ["Bruno"]
        assert "motivo" in invalidos.columns
