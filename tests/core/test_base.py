"""Testes para autotarefas.core.base."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any

import pytest

from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.core.exceptions import ValidationError

# ============================================================
# Tasks "fixtures" pra usar nos testes
# ============================================================


class _DummyTaskSuccess(BaseTask):
    """Task de teste que sempre retorna SUCCESS."""

    name = "dummy_success"
    description = "Task dummy pra testar caso de sucesso"

    def execute(self) -> TaskResult:
        started_at = datetime.now(UTC)
        return self._make_result(
            status=TaskStatus.SUCCESS,
            started_at=started_at,
            rows_affected=42,
            data={"foo": "bar"},
        )


class _DummyTaskFailure(BaseTask):
    """Task que levanta AutoTarefasError."""

    name = "dummy_failure"
    description = "Task dummy pra testar caso de erro tratado"

    def execute(self) -> TaskResult:
        raise ValidationError("erro de teste", field="campo_teste")


class _DummyTaskUnexpectedError(BaseTask):
    """Task que levanta exceção NÃO-tratada (deve propagar)."""

    name = "dummy_unexpected"
    description = "Task dummy pra testar erro não capturado"

    def execute(self) -> TaskResult:
        raise RuntimeError("bug inesperado")


class _DummyTaskHooks(BaseTask):
    """Task que registra ordem de chamadas dos hooks."""

    name = "dummy_hooks"
    description = "Task dummy pra testar hooks"

    def __init__(self, *, dry_run: bool = False) -> None:
        super().__init__(dry_run=dry_run)
        self.calls: list[str] = []

    def pre_execute(self) -> None:
        self.calls.append("pre_execute")

    def execute(self) -> TaskResult:
        self.calls.append("execute")
        started_at = datetime.now(UTC)
        return self._make_result(
            status=TaskStatus.SUCCESS,
            started_at=started_at,
        )

    def post_execute(self, result: TaskResult) -> None:
        self.calls.append("post_execute")


# ============================================================
# Tests
# ============================================================


class TestTaskStatus:
    """Testes do enum TaskStatus."""

    def test_e_string_enum(self) -> None:
        """TaskStatus herda de str (pra serializar fácil)."""
        assert isinstance(TaskStatus.SUCCESS, str)

    def test_valores_esperados(self) -> None:
        assert TaskStatus.SUCCESS.value == "success"
        assert TaskStatus.FAILURE.value == "failure"
        assert TaskStatus.PARTIAL.value == "partial"
        assert TaskStatus.DRY_RUN.value == "dry_run"
        assert TaskStatus.SKIPPED.value == "skipped"

    def test_value_e_string(self) -> None:
        """TaskStatus.SUCCESS.value é uma string."""
        assert TaskStatus.SUCCESS.value == "success"


class TestTaskResult:
    """Testes do TaskResult."""

    def _make_basic(self) -> TaskResult:
        """Helper pra criar TaskResult básico."""
        now = datetime.now(UTC)
        return TaskResult(
            task_name="test",
            status=TaskStatus.SUCCESS,
            started_at=now,
            finished_at=now,
            duration_ms=0,
        )

    def test_criacao_basica(self) -> None:
        r = self._make_basic()
        assert r.task_name == "test"
        assert r.status == TaskStatus.SUCCESS
        assert r.rows_affected == 0
        assert r.rows_failed == 0
        assert r.error_message is None

    def test_imutavel_frozen(self) -> None:
        """TaskResult é frozen — não pode alterar campos."""
        r = self._make_basic()
        with pytest.raises(FrozenInstanceError):
            r.task_name = "outro"  # type: ignore[misc]

    def test_is_success(self) -> None:
        r = self._make_basic()
        assert r.is_success is True

    def test_is_success_false_quando_failure(self) -> None:
        now = datetime.now(UTC)
        r = TaskResult(
            task_name="x",
            status=TaskStatus.FAILURE,
            started_at=now,
            finished_at=now,
            duration_ms=0,
        )
        assert r.is_success is False
        assert r.is_failure is True

    def test_is_partial(self) -> None:
        now = datetime.now(UTC)
        r = TaskResult(
            task_name="x",
            status=TaskStatus.PARTIAL,
            started_at=now,
            finished_at=now,
            duration_ms=0,
        )
        assert r.is_partial is True
        assert r.is_success is False

    def test_total_rows(self) -> None:
        now = datetime.now(UTC)
        r = TaskResult(
            task_name="x",
            status=TaskStatus.PARTIAL,
            started_at=now,
            finished_at=now,
            duration_ms=0,
            rows_affected=10,
            rows_failed=3,
        )
        assert r.total_rows == 13

    def test_data_default_vazio(self) -> None:
        r = self._make_basic()
        assert r.data == {}

    def test_dry_run_default_false(self) -> None:
        r = self._make_basic()
        assert r.dry_run is False


class TestBaseTaskValidation:
    """Testes da validação de subclasses (name/description)."""

    def test_subclasse_sem_name_levanta(self) -> None:
        """Subclasse concreta sem 'name' levanta TypeError."""
        with pytest.raises(TypeError, match="name"):

            class _SemNome(BaseTask):
                description = "tem descricao mas falta name"

                def execute(self) -> TaskResult:
                    return _DummyTaskSuccess().execute()

    def test_subclasse_sem_description_levanta(self) -> None:
        """Subclasse concreta sem 'description' levanta TypeError."""
        with pytest.raises(TypeError, match="description"):

            class _SemDesc(BaseTask):
                name = "sem_desc"

                def execute(self) -> TaskResult:
                    return _DummyTaskSuccess().execute()


class TestBaseTaskAbstract:
    """Testes que BaseTask é abstrata."""

    def test_nao_pode_instanciar_diretamente(self) -> None:
        """BaseTask é ABC — não pode instanciar."""
        with pytest.raises(TypeError):
            BaseTask()  # type: ignore[abstract]


class TestBaseTaskRun:
    """Testes do método run()."""

    def test_run_sucesso(self) -> None:
        task = _DummyTaskSuccess()
        result = task.run()
        assert result.is_success
        assert result.task_name == "dummy_success"
        assert result.rows_affected == 42
        assert result.data == {"foo": "bar"}

    def test_run_captura_autotarefas_error(self) -> None:
        """Erros do projeto viram FAILURE, não propagam."""
        task = _DummyTaskFailure()
        result = task.run()

        assert result.is_failure
        assert result.status == TaskStatus.FAILURE
        assert result.error_message == "erro de teste"
        assert result.error_type == "ValidationError"

    def test_run_propaga_excecao_inesperada(self) -> None:
        """Exceções fora do AutoTarefasError propagam (bugs reais)."""
        task = _DummyTaskUnexpectedError()
        with pytest.raises(RuntimeError, match="bug inesperado"):
            task.run()

    def test_run_calcula_duration(self) -> None:
        """duration_ms é calculado automaticamente."""
        task = _DummyTaskSuccess()
        result = task.run()
        assert result.duration_ms >= 0

    def test_run_propaga_dry_run(self) -> None:
        """dry_run da task aparece no result."""
        task = _DummyTaskSuccess(dry_run=True)
        result = task.run()
        assert result.dry_run is True

    def test_run_dry_run_default_false(self) -> None:
        task = _DummyTaskSuccess()
        result = task.run()
        assert result.dry_run is False


class TestBaseTaskHooks:
    """Testes dos hooks pre_execute e post_execute."""

    def test_hooks_chamados_na_ordem_correta(self) -> None:
        task = _DummyTaskHooks()
        task.run()

        assert task.calls == ["pre_execute", "execute", "post_execute"]

    def test_pre_execute_default_no_op(self) -> None:
        """BaseTask.pre_execute() default não faz nada."""
        task = _DummyTaskSuccess()
        # Não deve levantar exceção
        task.pre_execute()

    def test_post_execute_default_no_op(self) -> None:
        """BaseTask.post_execute() default não faz nada."""
        task = _DummyTaskSuccess()
        now = datetime.now(UTC)
        result = TaskResult(
            task_name="x",
            status=TaskStatus.SUCCESS,
            started_at=now,
            finished_at=now,
            duration_ms=0,
        )
        # Não deve levantar exceção
        task.post_execute(result)


class TestBaseTaskMakeResult:
    """Testes do helper _make_result."""

    def test_make_result_calcula_duration(self) -> None:
        task = _DummyTaskSuccess()
        started_at = datetime.now(UTC)
        result = task._make_result(
            status=TaskStatus.SUCCESS,
            started_at=started_at,
        )
        assert result.duration_ms >= 0
        assert result.finished_at >= started_at

    def test_make_result_passa_data_padrao_vazio(self) -> None:
        task = _DummyTaskSuccess()
        result = task._make_result(
            status=TaskStatus.SUCCESS,
            started_at=datetime.now(UTC),
        )
        assert result.data == {}

    def test_make_result_aceita_data_customizada(self) -> None:
        task = _DummyTaskSuccess()
        custom_data: dict[str, Any] = {"key": "value", "n": 42}
        result = task._make_result(
            status=TaskStatus.SUCCESS,
            started_at=datetime.now(UTC),
            data=custom_data,
        )
        assert result.data == custom_data

    def test_make_result_propaga_dry_run(self) -> None:
        task = _DummyTaskSuccess(dry_run=True)
        result = task._make_result(
            status=TaskStatus.DRY_RUN,
            started_at=datetime.now(UTC),
        )
        assert result.dry_run is True
