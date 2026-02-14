"""
Classes base do AutoTarefas.

Define as interfaces e tipos fundamentais usados por todas as tasks.

Classes:
    - TaskStatus: Enum com estados possíveis de uma task
    - TaskResult: Resultado da execução de uma task
    - BaseTask: Classe abstrata base para todas as tasks

Uso:
    from autotarefas.core.base import BaseTask, TaskResult, TaskStatus

    class MinhaTask(BaseTask):
        @property
        def name(self) -> str:
            return "minha-task"

        def execute(self, **kwargs) -> TaskResult:
            # implementação
            return TaskResult.success("Concluído!")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def _now_utc() -> datetime:
    return datetime.now(UTC)


class TaskStatus(Enum):
    """
    Status possíveis de uma task.

    Valores:
        PENDING: Aguardando execução
        RUNNING: Em execução
        SUCCESS: Executada com sucesso
        FAILED: Falhou durante execução
        SKIPPED: Pulada (ex: dry-run, condição não atendida)
        CANCELLED: Cancelada pelo usuário
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        return self.value

    @property
    def is_finished(self) -> bool:
        """Retorna True se é um status final."""
        return self in (
            TaskStatus.SUCCESS,
            TaskStatus.FAILED,
            TaskStatus.SKIPPED,
            TaskStatus.CANCELLED,
        )

    @property
    def is_success(self) -> bool:
        """Retorna True se foi sucesso."""
        return self == TaskStatus.SUCCESS

    @property
    def is_error(self) -> bool:
        """Retorna True se foi erro."""
        return self == TaskStatus.FAILED

    @property
    def emoji(self) -> str:
        """Retorna emoji representativo do status."""
        emojis = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.RUNNING: "🔄",
            TaskStatus.SUCCESS: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.SKIPPED: "⏭️",
            TaskStatus.CANCELLED: "🚫",
        }
        return emojis.get(self, "❓")


@dataclass
class TaskResult:
    """
    Resultado da execução de uma task.

    Attributes:
        status: Status final da execução
        message: Mensagem descritiva do resultado
        data: Dados adicionais do resultado (opcional)
        error: Exceção que causou falha (se houver)
        started_at: Momento de início da execução
        finished_at: Momento de término da execução
        duration_seconds: Duração em segundos

    Exemplo:
        >>> result = TaskResult.success("Backup concluído!", data={"files": 42})
        >>> print(result.status)
        TaskStatus.SUCCESS
        >>> print(result.data)
        {'files': 42}
    """

    status: TaskStatus
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: BaseException | None = None

    task_name: str | None = None

    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        """Garante que finished_at seja definido para status finais."""
        if self.started_at is None:
            self.started_at = _now_utc()

        # Se já terminou e não tem finished_at, define (UTC).
        if self.status.is_finished and self.finished_at is None:
            self.finished_at = _now_utc()

        # Garantia de dict
        if self.data is None:
            self.data = {}

    @property
    def duration_seconds(self) -> float:
        """Calcula duração em segundos."""
        if self.started_at is None or self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()

    @property
    def duration_formatted(self) -> str:
        """Retorna duração formatada (ex: '2m 30s')."""
        seconds = self.duration_seconds
        if seconds <= 0:
            return "0.0s"
        if seconds < 60:
            return f"{seconds:.1f}s"
        if seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

    @property
    def is_success(self) -> bool:
        """Atalho para verificar sucesso."""
        return self.status.is_success

    @property
    def is_error(self) -> bool:
        """Atalho para verificar erro."""
        return self.status.is_error

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_name": self.task_name,
            "status": self.status.value,
            "message": self.message,
            "data": self.data,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error": str(self.error) if self.error else None,
            "error_type": type(self.error).__name__ if self.error else None,
        }

    # === Factory Methods ===

    @classmethod
    def success(
        cls,
        message: str = "Tarefa concluída com sucesso",
        data: dict[str, Any] | None = None,
        *,
        task_name: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> TaskResult:
        """
        Cria um resultado de sucesso.

        Args:
            message: Mensagem de sucesso
            data: Dados adicionais
            task_name: Nome/identificador da task associada ao resultado (opcional).
            started_at: Momento de início (para calcular duração)
            finished_at: Momento de término da execução da task (opcional).
        """
        return cls(
            status=TaskStatus.SUCCESS,
            message=message,
            data=data or {},
            task_name=task_name,
            started_at=started_at,
            finished_at=finished_at or _now_utc(),
        )

    @classmethod
    def failure(
        cls,
        message: str = "Tarefa falhou",
        error: BaseException | None = None,
        data: dict[str, Any] | None = None,
        *,
        task_name: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> TaskResult:
        """
        Cria um resultado de falha.

        Args:
            message: Mensagem de erro
            error: Exceção que causou a falha
            data: Dados adicionais (contexto do erro)
            task_name: Nome/identificador da task associada ao resultado (opcional).
            started_at: Momento de início
            finished_at: Momento de término da execução da task (opcional).
        """
        return cls(
            status=TaskStatus.FAILED,
            message=message,
            error=error,
            data=data or {},
            task_name=task_name,
            started_at=started_at,
            finished_at=finished_at or _now_utc(),
        )

    @classmethod
    def skipped(
        cls,
        message: str = "Tarefa ignorada",
        data: dict[str, Any] | None = None,
        *,
        task_name: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> TaskResult:
        """
        Cria um resultado de tarefa ignorada.

        Args:
            message: Motivo de ter sido ignorada
            data: Dados adicionais
            task_name: Nome/identificador da task associada ao resultado (opcional).
            started_at: Momento de início
            finished_at: Momento de término da execução da task (opcional).
        """
        return cls(
            status=TaskStatus.SKIPPED,
            message=message,
            data=data or {},
            task_name=task_name,
            started_at=started_at,
            finished_at=finished_at or _now_utc(),
        )

    @classmethod
    def cancelled(
        cls,
        message: str = "Tarefa cancelada",
        error: BaseException | None = None,
        data: dict[str, Any] | None = None,
        *,
        task_name: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> TaskResult:
        """
        Cria um resultado de tarefa cancelada.

        Args:
            message: Motivo do cancelamento
            error: Exceção associada ao cancelamento (ex: KeyboardInterrupt)
            data: Dados adicionais
            task_name: Nome/identificador da task associada ao resultado (opcional).
            started_at: Momento de início
            finished_at: Momento de término da execução da task (opcional).
        """
        return cls(
            status=TaskStatus.CANCELLED,
            message=message,
            error=error,
            data=data or {},
            task_name=task_name,
            started_at=started_at,
            finished_at=finished_at or _now_utc(),
        )

    def __str__(self) -> str:
        return f"{self.status.emoji} [{self.status.value}] {self.message}"

    def __repr__(self) -> str:
        return f"TaskResult(status={self.status.value!r}, message={self.message!r}, duration={self.duration_formatted})"


class BaseTask(ABC):
    """
    Classe abstrata base para todas as tasks.

    Todas as tasks do sistema devem herdar desta classe e implementar:
        - name: Nome único da task
        - execute: Lógica de execução

    Opcionalmente podem sobrescrever:
        - description: Descrição da task
        - validate: Validação de parâmetros
        - cleanup: Limpeza pós-execução

    Exemplo:
        >>> class BackupTask(BaseTask):
        ...     @property
        ...     def name(self) -> str:
        ...         return "backup"
        ...
        ...     @property
        ...     def description(self) -> str:
        ...         return "Cria backup de arquivos e diretórios"
        ...
        ...     def execute(self, source: str, dest: str) -> TaskResult:
        ...         # implementação do backup
        ...         return TaskResult.success(f"Backup de {source} criado")
    """

    def __init__(self) -> None:
        """Inicializa a task."""
        self._started_at: datetime | None = None
        self._status: TaskStatus = TaskStatus.PENDING

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Nome único da task.

        Deve ser um identificador curto, em minúsculas, sem espaços.
        Exemplo: "backup", "cleaner", "monitor"
        """
        ...

    @property
    def description(self) -> str:
        """Descrição da task. Pode ser sobrescrito."""
        return f"Task: {self.name}"

    @property
    def status(self) -> TaskStatus:
        """Status atual da task."""
        return self._status

    @abstractmethod
    def execute(self, **kwargs: Any) -> TaskResult:
        """
        Executa a task.

        Este método deve ser implementado por cada task específica.

        Args:
            **kwargs: Argumentos específicos da task

        Returns:
            TaskResult com o resultado da execução
        """
        ...

    def validate(self, **kwargs: Any) -> tuple[bool, str]:
        """
        Valida os parâmetros antes da execução.

        Pode ser sobrescrito para adicionar validações específicas.

        Args:
            **kwargs: Argumentos a serem validados

        Returns:
            Tupla (is_valid, error_message)
        """
        del kwargs
        return True, ""

    def cleanup(self) -> None:
        """
        Limpeza pós-execução.

        Chamado após execute(), independente do resultado.
        Pode ser sobrescrito para liberar recursos.
        """
        return None

    def run(self, dry_run: bool = False, **kwargs: Any) -> TaskResult:
        """
        Executa a task com tratamento de erros.

        Este é o método principal que deve ser chamado para executar uma task.
        Ele cuida de:
            - Validação de parâmetros
            - Tratamento de erros
            - Logging
            - Cleanup

        Args:
            dry_run: Se True, simula a execução sem fazer alterações
            **kwargs: Argumentos para a task

        Returns:
            TaskResult com o resultado
        """
        # Usar LoggerContext do logger.py para incluir contexto automaticamente.
        from autotarefas.core.logger import LoggerContext

        self._started_at = _now_utc()
        self._status = TaskStatus.RUNNING

        with LoggerContext(self.name, task=self.name, dry_run=dry_run) as log:
            # Validação
            is_valid, error_msg = self.validate(**kwargs)
            if not is_valid:
                self._status = TaskStatus.FAILED
                log.error("Validação falhou: {}", error_msg)
                return TaskResult.failure(
                    message=f"Validação falhou: {error_msg}",
                    task_name=self.name,
                    started_at=self._started_at,
                    finished_at=_now_utc(),
                )

        # Dry run
        if dry_run:
            self._status = TaskStatus.SKIPPED
            log.info("Modo dry-run: simulando execução (nenhuma alteração será feita)")
            return TaskResult.skipped(
                message="Dry-run: nenhuma alteração foi feita",
                data={"kwargs": kwargs},
                task_name=self.name,
                started_at=self._started_at,
                finished_at=_now_utc(),
            )

        # Execução
        try:
            result = self.execute(**kwargs)

            result.task_name = result.task_name or self.name
            result.started_at = self._started_at
            if result.status.is_finished and result.finished_at is None:
                result.finished_at = _now_utc()

            self._status = result.status

            if result.is_success:
                log.info("{}", result.message)
            else:
                log.warning("{}", result.message)

            return result

        except KeyboardInterrupt as e:
            self._status = TaskStatus.CANCELLED
            log.warning("Execução cancelada pelo usuário (Ctrl+C)")
            return TaskResult.cancelled(
                message="Cancelada pelo usuário",
                error=e,
                task_name=self.name,
                started_at=self._started_at,
                finished_at=_now_utc(),
            )

        except Exception as e:
            self._status = TaskStatus.FAILED
            log.exception("Erro durante execução: {}", e)
            return TaskResult.failure(
                message=str(e),
                error=e,
                task_name=self.name,
                started_at=self._started_at,
                finished_at=_now_utc(),
            )

        finally:
            try:
                self.cleanup()
            except Exception as cleanup_error:
                log.warning("Erro no cleanup: {}", cleanup_error)

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, status={self.status.value!r})"


# Exports
__all__ = [
    "TaskStatus",
    "TaskResult",
    "BaseTask",
]
