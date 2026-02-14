"""
Testes do módulo base (BaseTask, TaskResult, TaskStatus).

Objetivo:
    Garantir que as estruturas fundamentais do AutoTarefas se comportem como esperado,
    porque todas as tasks e a CLI dependem delas.

O que é validado na prática:
    - TaskStatus: valores, helpers (is_finished/is_success/is_error) e emoji.
    - TaskResult: defaults, duração, formatação, factory methods, serialização e repr/str.
    - BaseTask: abstração, descrição, status inicial e o ciclo de execução via run():
        * validação
        * dry-run
        * sucesso
        * falha por exceção
        * cancelamento (KeyboardInterrupt)
        * cleanup (sempre executa após a execução dentro do bloco try/finally)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

# =============================================================================
# Testes de TaskStatus
# =============================================================================


class TestTaskStatus:
    """Testes do enum TaskStatus."""

    def test_status_values_exist(self) -> None:
        """Deve ter todos os status esperados."""
        from autotarefas.core.base import TaskStatus

        for name in ("PENDING", "RUNNING", "SUCCESS", "FAILED", "SKIPPED", "CANCELLED"):
            assert hasattr(TaskStatus, name)

    def test_status_string_values(self) -> None:
        """Status deve ter os valores string corretos."""
        from autotarefas.core.base import TaskStatus

        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.SUCCESS.value == "success"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.SKIPPED.value == "skipped"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_status_str_method(self) -> None:
        """__str__ deve retornar o value (string)."""
        from autotarefas.core.base import TaskStatus

        assert str(TaskStatus.SUCCESS) == "success"
        assert str(TaskStatus.FAILED) == "failed"

    def test_is_finished_property(self) -> None:
        """is_finished deve retornar True apenas para status finais."""
        from autotarefas.core.base import TaskStatus

        assert TaskStatus.SUCCESS.is_finished is True
        assert TaskStatus.FAILED.is_finished is True
        assert TaskStatus.SKIPPED.is_finished is True
        assert TaskStatus.CANCELLED.is_finished is True

        assert TaskStatus.PENDING.is_finished is False
        assert TaskStatus.RUNNING.is_finished is False

    def test_is_success_property(self) -> None:
        """is_success deve retornar True apenas para SUCCESS."""
        from autotarefas.core.base import TaskStatus

        assert TaskStatus.SUCCESS.is_success is True
        assert TaskStatus.FAILED.is_success is False
        assert TaskStatus.PENDING.is_success is False

    def test_is_error_property(self) -> None:
        """is_error deve retornar True apenas para FAILED."""
        from autotarefas.core.base import TaskStatus

        assert TaskStatus.FAILED.is_error is True
        assert TaskStatus.SUCCESS.is_error is False
        assert TaskStatus.CANCELLED.is_error is False

    def test_emoji_property(self) -> None:
        """Cada status deve ter um emoji definido."""
        from autotarefas.core.base import TaskStatus

        assert TaskStatus.PENDING.emoji == "⏳"
        assert TaskStatus.RUNNING.emoji == "🔄"
        assert TaskStatus.SUCCESS.emoji == "✅"
        assert TaskStatus.FAILED.emoji == "❌"
        assert TaskStatus.SKIPPED.emoji == "⏭️"
        assert TaskStatus.CANCELLED.emoji == "🚫"


# =============================================================================
# Testes de TaskResult
# =============================================================================


class TestTaskResultBasics:
    """Testes básicos da classe TaskResult."""

    def test_create_basic_result(self) -> None:
        """Deve criar resultado básico com defaults."""
        from autotarefas.core.base import TaskResult, TaskStatus

        result = TaskResult(status=TaskStatus.SUCCESS, message="OK")

        assert result.status == TaskStatus.SUCCESS
        assert result.message == "OK"
        assert result.data == {}
        assert result.error is None
        assert isinstance(result.started_at, datetime)
        assert isinstance(
            result.finished_at, datetime
        )  # status final => finished_at auto

    def test_result_with_data(self) -> None:
        """Deve criar resultado com data preservado."""
        from autotarefas.core.base import TaskResult, TaskStatus

        data = {"files": 10, "size": 1024}
        result = TaskResult(status=TaskStatus.SUCCESS, message="OK", data=data)

        assert result.data == data
        assert result.data["files"] == 10

    def test_result_with_none_data_becomes_dict(self) -> None:
        """data=None deve virar dict vazio (garantia do __post_init__)."""
        from autotarefas.core.base import TaskResult, TaskStatus

        result = TaskResult(status=TaskStatus.SUCCESS, message="OK", data=None)  # type: ignore[arg-type]
        assert result.data == {}

    def test_result_with_error(self) -> None:
        """Deve criar resultado com erro e is_error True quando FAILED."""
        from autotarefas.core.base import TaskResult, TaskStatus

        error = ValueError("Test error")
        result = TaskResult(status=TaskStatus.FAILED, message="Falhou", error=error)

        assert result.error is error
        assert result.is_error is True
        assert result.is_success is False


class TestTaskResultDuration:
    """Testes de duração e formatação do TaskResult."""

    def test_duration_seconds_calculation(self) -> None:
        """Deve calcular duração em segundos quando started_at e finished_at existem."""
        from autotarefas.core.base import TaskResult, TaskStatus

        start = datetime.now(UTC)
        end = start + timedelta(seconds=5)

        result = TaskResult(
            status=TaskStatus.SUCCESS,
            message="OK",
            started_at=start,
            finished_at=end,
        )

        assert result.duration_seconds == pytest.approx(5.0, rel=0.05)

    def test_duration_zero_when_missing_timestamps(self) -> None:
        """Sem timestamps completos, duration_seconds deve ser 0.0."""
        from autotarefas.core.base import TaskResult, TaskStatus

        result = TaskResult(
            status=TaskStatus.RUNNING, message="Running", finished_at=None
        )
        assert result.duration_seconds == 0.0

    def test_duration_formatted_seconds(self) -> None:
        """Deve formatar duração em segundos (<60s)."""
        from autotarefas.core.base import TaskResult, TaskStatus

        start = datetime.now(UTC)
        end = start + timedelta(seconds=45)

        result = TaskResult(
            status=TaskStatus.SUCCESS,
            message="OK",
            started_at=start,
            finished_at=end,
        )

        assert "s" in result.duration_formatted

    def test_duration_formatted_minutes(self) -> None:
        """Deve formatar duração em minutos (>=60s e <3600s)."""
        from autotarefas.core.base import TaskResult, TaskStatus

        start = datetime.now(UTC)
        end = start + timedelta(minutes=2, seconds=30)

        result = TaskResult(
            status=TaskStatus.SUCCESS,
            message="OK",
            started_at=start,
            finished_at=end,
        )

        formatted = result.duration_formatted
        assert "m" in formatted and "s" in formatted

    def test_duration_formatted_hours(self) -> None:
        """Deve formatar duração em horas (>=3600s)."""
        from autotarefas.core.base import TaskResult, TaskStatus

        start = datetime.now(UTC)
        end = start + timedelta(hours=1, minutes=30)

        result = TaskResult(
            status=TaskStatus.SUCCESS,
            message="OK",
            started_at=start,
            finished_at=end,
        )

        formatted = result.duration_formatted
        assert "h" in formatted and "m" in formatted


class TestTaskResultFactoryMethods:
    """Testes dos factory methods de TaskResult."""

    def test_success_factory(self) -> None:
        """TaskResult.success() deve criar resultado SUCCESS."""
        from autotarefas.core.base import TaskResult, TaskStatus

        result = TaskResult.success("Operação concluída")

        assert result.status == TaskStatus.SUCCESS
        assert result.message == "Operação concluída"
        assert result.is_success is True
        assert isinstance(result.started_at, datetime)
        assert isinstance(result.finished_at, datetime)

    def test_failure_factory(self) -> None:
        """TaskResult.failure() deve criar resultado FAILED."""
        from autotarefas.core.base import TaskResult, TaskStatus

        result = TaskResult.failure("Erro na operação")

        assert result.status == TaskStatus.FAILED
        assert result.message == "Erro na operação"
        assert result.is_error is True
        assert isinstance(result.started_at, datetime)
        assert isinstance(result.finished_at, datetime)

    def test_skipped_factory(self) -> None:
        """TaskResult.skipped() deve criar resultado SKIPPED."""
        from autotarefas.core.base import TaskResult, TaskStatus

        result = TaskResult.skipped("Condição não atendida")

        assert result.status == TaskStatus.SKIPPED
        assert result.message == "Condição não atendida"

    def test_cancelled_factory(self) -> None:
        """TaskResult.cancelled() deve criar resultado CANCELLED."""
        from autotarefas.core.base import TaskResult, TaskStatus

        result = TaskResult.cancelled("Cancelado pelo usuário")

        assert result.status == TaskStatus.CANCELLED
        assert result.message == "Cancelado pelo usuário"


class TestTaskResultSerialization:
    """Testes de serialização e representações do TaskResult."""

    def test_to_dict(self) -> None:
        """to_dict() deve retornar dict completo e consistente."""
        from autotarefas.core.base import TaskResult

        result = TaskResult.success("OK", data={"files": 10}, task_name="test")
        data = result.to_dict()

        assert isinstance(data, dict)
        assert data["task_name"] == "test"
        assert data["status"] == "success"
        assert data["message"] == "OK"
        assert data["data"] == {"files": 10}
        assert "duration_seconds" in data
        assert "started_at" in data
        assert "finished_at" in data

    def test_to_dict_with_error(self) -> None:
        """to_dict() deve incluir error e error_type quando houver erro."""
        from autotarefas.core.base import TaskResult

        error = ValueError("Test error")
        result = TaskResult.failure("Falhou", error=error)
        data = result.to_dict()

        assert data["error"] == "Test error"
        assert data["error_type"] == "ValueError"

    def test_str_representation(self) -> None:
        """__str__ deve ser legível e conter status e mensagem."""
        from autotarefas.core.base import TaskResult

        result = TaskResult.success("Concluído")
        text = str(result)

        assert "Concluído" in text
        assert "success" in text.lower() or "✅" in text

    def test_repr_representation(self) -> None:
        """__repr__ deve conter a classe e dados técnicos."""
        from autotarefas.core.base import TaskResult

        result = TaskResult.success("OK")
        text = repr(result)

        assert "TaskResult" in text
        assert "success" in text


# =============================================================================
# Testes de BaseTask
# =============================================================================


class TestBaseTaskBasics:
    """Testes básicos sobre a classe abstrata BaseTask."""

    def test_cannot_instantiate_directly(self) -> None:
        """Não deve instanciar BaseTask diretamente (ABC)."""
        from autotarefas.core.base import BaseTask

        with pytest.raises(TypeError):
            BaseTask()  # type: ignore[abstract]

    def test_default_description_includes_name(self) -> None:
        """description padrão deve incluir o nome da task."""
        from autotarefas.core.base import BaseTask, TaskResult

        class MyTask(BaseTask):
            """Task mínima para teste."""

            @property
            def name(self) -> str:
                """Nome fixo para o teste."""
                return "my-task"

            def execute(self, **_kwargs) -> TaskResult:
                """Executa com sucesso."""
                return TaskResult.success("OK")

        task = MyTask()
        assert "my-task" in task.description

    def test_initial_status_is_pending(self) -> None:
        """Status inicial deve ser PENDING."""
        from autotarefas.core.base import BaseTask, TaskResult, TaskStatus

        class MyTask(BaseTask):
            """Task mínima para teste."""

            @property
            def name(self) -> str:
                """Nome fixo para o teste."""
                return "test"

            def execute(self, **_kwargs) -> TaskResult:
                """Executa com sucesso."""
                return TaskResult.success("OK")

        task = MyTask()
        assert task.status == TaskStatus.PENDING

    def test_str_and_repr(self) -> None:
        """__str__ e __repr__ devem retornar representações úteis."""
        from autotarefas.core.base import BaseTask, TaskResult

        class MyTask(BaseTask):
            """Task mínima para teste."""

            @property
            def name(self) -> str:
                """Nome fixo para o teste."""
                return "test"

            def execute(self, **_kwargs) -> TaskResult:
                """Executa com sucesso."""
                return TaskResult.success("OK")

        task = MyTask()
        assert "test" in str(task)
        assert "status" in repr(task)


class TestBaseTaskRun:
    """Testes do ciclo completo via BaseTask.run()."""

    def test_run_success_sets_task_name_and_started_at(self) -> None:
        """run() deve retornar sucesso e preencher task_name e started_at do resultado."""
        from autotarefas.core.base import BaseTask, TaskResult, TaskStatus

        class MyTask(BaseTask):
            """Task que retorna sucesso."""

            @property
            def name(self) -> str:
                """Nome fixo para o teste."""
                return "backup"

            def execute(self, **_kwargs) -> TaskResult:
                """Executa e retorna sucesso sem task_name."""
                return TaskResult.success("Done", data={"x": 1})

        task = MyTask()
        result = task.run()

        assert result.status == TaskStatus.SUCCESS
        assert result.task_name == "backup"
        assert isinstance(result.started_at, datetime)
        assert isinstance(result.finished_at, datetime)
        assert task.status == TaskStatus.SUCCESS

    def test_run_preserves_existing_task_name(self) -> None:
        """Se execute() já trouxe task_name, run() não deve sobrescrever."""
        from autotarefas.core.base import BaseTask, TaskResult

        class MyTask(BaseTask):
            """Task que já define task_name no resultado."""

            @property
            def name(self) -> str:
                """Nome fixo para o teste."""
                return "backup"

            def execute(self, **_kwargs) -> TaskResult:
                """Retorna resultado com task_name próprio."""
                return TaskResult.success("Done", task_name="custom-name")

        task = MyTask()
        result = task.run()

        assert result.task_name == "custom-name"

    def test_run_validation_failure_returns_failure(self) -> None:
        """Se validate() falhar, run() deve retornar failure e status FAILED."""
        from autotarefas.core.base import BaseTask, TaskResult, TaskStatus

        class MyTask(BaseTask):
            """Task com validação que falha."""

            @property
            def name(self) -> str:
                """Nome fixo para o teste."""
                return "clean"

            def validate(self, **kwargs) -> tuple[bool, str]:
                """Falha se não tiver 'required'."""
                if "required" not in kwargs:
                    return False, "required é obrigatório"
                return True, ""

            def execute(self, **_kwargs) -> TaskResult:
                """Não deveria ser chamado quando validação falha."""
                return TaskResult.success("OK")

        task = MyTask()
        result = task.run()

        assert result.status == TaskStatus.FAILED
        assert "Validação falhou" in result.message
        assert task.status == TaskStatus.FAILED

    def test_run_dry_run_returns_skipped(self) -> None:
        """dry_run=True deve retornar SKIPPED e incluir kwargs no data."""
        from autotarefas.core.base import BaseTask, TaskResult, TaskStatus

        class MyTask(BaseTask):
            """Task qualquer para validar o caminho de dry-run."""

            @property
            def name(self) -> str:
                """Nome fixo para o teste."""
                return "monitor"

            def execute(self, **_kwargs) -> TaskResult:
                """Não deve ser executado em dry-run."""
                return TaskResult.success("OK")

        task = MyTask()
        result = task.run(dry_run=True, a=1, b="x")

        assert result.status == TaskStatus.SKIPPED
        assert "Dry-run" in result.message
        assert result.data["kwargs"] == {"a": 1, "b": "x"}
        assert task.status == TaskStatus.SKIPPED

    def test_run_exception_returns_failure_and_calls_cleanup(self) -> None:
        """Exceção em execute() deve virar failure e cleanup deve rodar."""
        from autotarefas.core.base import BaseTask, TaskResult, TaskStatus

        cleanup_called = {"ok": False}

        class MyTask(BaseTask):
            """Task que lança exceção na execução."""

            @property
            def name(self) -> str:
                """Nome fixo para o teste."""
                return "report"

            def execute(self, **_kwargs) -> TaskResult:
                """Simula falha."""
                raise RuntimeError("Boom")

            def cleanup(self) -> None:
                """Marca que o cleanup foi chamado."""
                cleanup_called["ok"] = True

        task = MyTask()
        result = task.run()

        assert result.status == TaskStatus.FAILED
        assert result.error is not None
        assert "Boom" in result.message
        assert task.status == TaskStatus.FAILED
        assert cleanup_called["ok"] is True

    def test_run_keyboard_interrupt_returns_cancelled(self) -> None:
        """KeyboardInterrupt em execute() deve virar CANCELLED."""
        from autotarefas.core.base import BaseTask, TaskResult, TaskStatus

        class MyTask(BaseTask):
            """Task que simula cancelamento."""

            @property
            def name(self) -> str:
                """Nome fixo para o teste."""
                return "backup"

            def execute(self, **_kwargs) -> TaskResult:
                """Simula Ctrl+C."""
                raise KeyboardInterrupt()

        task = MyTask()
        result = task.run()

        assert result.status == TaskStatus.CANCELLED
        assert "Cancelada" in result.message
        assert task.status == TaskStatus.CANCELLED

    def test_cleanup_error_is_swallowed(self) -> None:
        """Erro no cleanup não deve explodir o run() (deve ser engolido)."""
        from autotarefas.core.base import BaseTask, TaskResult, TaskStatus

        class MyTask(BaseTask):
            """Task com cleanup quebrado."""

            @property
            def name(self) -> str:
                """Nome fixo para o teste."""
                return "backup"

            def execute(self, **_kwargs) -> TaskResult:
                """Executa com sucesso."""
                return TaskResult.success("OK")

            def cleanup(self) -> None:
                """Simula erro no cleanup."""
                raise RuntimeError("cleanup failed")

        task = MyTask()
        result = task.run()

        assert result.status == TaskStatus.SUCCESS
        assert task.status == TaskStatus.SUCCESS


# =============================================================================
# Edge Cases (TaskResult)
# =============================================================================


class TestEdgeCases:
    """Testes de casos extremos para TaskResult."""

    def test_result_with_empty_message(self) -> None:
        """Deve aceitar mensagem vazia."""
        from autotarefas.core.base import TaskResult, TaskStatus

        result = TaskResult(status=TaskStatus.SUCCESS, message="")
        assert result.message == ""

    def test_result_with_long_message(self) -> None:
        """Deve aceitar mensagem longa."""
        from autotarefas.core.base import TaskResult, TaskStatus

        long_msg = "x" * 10_000
        result = TaskResult(status=TaskStatus.SUCCESS, message=long_msg)
        assert len(result.message) == 10_000

    def test_result_with_complex_data(self) -> None:
        """Deve aceitar dados complexos."""
        from autotarefas.core.base import TaskResult

        complex_data = {
            "nested": {"level1": {"level2": [1, 2, 3]}},
            "list": [{"a": 1}, {"b": 2}],
            "unicode": "日本語テスト",
        }

        result = TaskResult.success("OK", data=complex_data)
        assert result.data == complex_data
