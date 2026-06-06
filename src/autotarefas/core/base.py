"""
Abstrações fundamentais do AutoTarefas: BaseTask, TaskResult, TaskStatus.

TODA tarefa do projeto (Validador, Backup, RPA, etc.) herda de ``BaseTask``
e retorna um ``TaskResult``. Isso garante:

- Interface consistente
- Timing automático
- Captura padronizada de erros
- Audit trail uniforme (Parte 1.3)
- Logs estruturados

Exemplo de uso:

    from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
    from datetime import UTC, datetime


    class MinhaTask(BaseTask):
        name = "minha_task"
        description = "Faz alguma coisa útil"

        def execute(self) -> TaskResult:
            started_at = datetime.now(UTC)
            # ... lógica de negócio ...
            return self._make_result(
                status=TaskStatus.SUCCESS,
                started_at=started_at,
                rows_affected=100,
            )


    task = MinhaTask(dry_run=False)
    result = task.run()
    print(result.is_success)  # True
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar

from autotarefas.core.audit import audit
from autotarefas.core.exceptions import AutoTarefasError
from autotarefas.core.logger import logger


class TaskStatus(StrEnum):
    """
    Status possíveis de uma task após execução.

    Herda de ``StrEnum`` pra ser facilmente serializado em JSON, audit DB, etc.
    """

    SUCCESS = "success"
    """Task concluída sem erros."""

    FAILURE = "failure"
    """Task abortou por erro."""

    PARTIAL = "partial"
    """Task processou parcialmente (parte das linhas falhou)."""

    DRY_RUN = "dry_run"
    """Task executada em modo simulação (não fez mudanças reais)."""

    SKIPPED = "skipped"
    """Task nem rodou (condições não atendidas, sem trabalho a fazer)."""


@dataclass(frozen=True, slots=True)
class TaskResult:
    """
    Resultado padronizado de toda task.

    É **imutável** (``frozen=True``) — uma vez criado, não muda.
    Usa ``slots`` pra economizar memória e acelerar acessos.

    Attributes:
        task_name: Nome da task que gerou este resultado.
        status: Status final da execução.
        started_at: Timestamp de início (UTC).
        finished_at: Timestamp de fim (UTC).
        duration_ms: Duração em milissegundos.
        rows_affected: Linhas/registros processados com sucesso.
        rows_failed: Linhas/registros que falharam.
        data: Dados arbitrários da execução (ex: caminho do arquivo gerado).
        error_message: Mensagem de erro (se status=FAILURE).
        error_type: Nome da classe da exceção (se status=FAILURE).
        dry_run: True se executou em modo simulação.
    """

    task_name: str
    status: TaskStatus
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    rows_affected: int = 0
    rows_failed: int = 0
    data: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    error_type: str | None = None
    dry_run: bool = False

    @property
    def is_success(self) -> bool:
        """True se status é SUCCESS."""
        return self.status == TaskStatus.SUCCESS

    @property
    def is_failure(self) -> bool:
        """True se status é FAILURE."""
        return self.status == TaskStatus.FAILURE

    @property
    def is_partial(self) -> bool:
        """True se status é PARTIAL (executou parte mas falhou parte)."""
        return self.status == TaskStatus.PARTIAL

    @property
    def total_rows(self) -> int:
        """Soma de rows_affected + rows_failed."""
        return self.rows_affected + self.rows_failed


class BaseTask(ABC):
    """
    Classe abstrata base de todas as tasks do AutoTarefas.

    Implementa o padrão **Template Method**:

    - ``run()`` é o ponto de entrada (não sobrescrever)
    - ``execute()`` é onde fica a lógica de negócio (subclasses implementam)
    - ``pre_execute()`` e ``post_execute()`` são hooks opcionais

    Atributos obrigatórios da subclasse:

    - ``name`` (snake_case, único) — identificador da task
    - ``description`` — texto curto descrevendo o que a task faz

    Exemplo:

        class ValidateTask(BaseTask):
            name = "validate"
            description = "Valida planilha CSV/Excel"

            def execute(self) -> TaskResult:
                started_at = datetime.now(UTC)
                # ... lógica ...
                return self._make_result(
                    status=TaskStatus.SUCCESS,
                    started_at=started_at,
                    rows_affected=42,
                )
    """

    #: Nome único da task em snake_case. Subclasses DEVEM definir.
    name: ClassVar[str] = ""

    #: Descrição curta da task. Subclasses DEVEM definir.
    description: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """
        Valida que subclasses concretas definem ``name`` e ``description``.

        Subclasses abstratas (com ``@abstractmethod`` pendente) são puladas —
        permite hierarquias intermediárias sem nome.
        """
        super().__init_subclass__(**kwargs)

        # __abstractmethods__ pode não estar definido em todos os casos
        # (varia entre versões/contextos do Python). Usa getattr defensivo.
        if getattr(cls, "__abstractmethods__", None):
            return

        if not cls.name:
            raise TypeError(
                f"{cls.__name__} precisa definir atributo de classe 'name' (snake_case, único)."
            )
        if not cls.description:
            raise TypeError(
                f"{cls.__name__} precisa definir atributo de classe 'description' (texto curto)."
            )

    def __init__(self, *, dry_run: bool = False) -> None:
        """
        Inicializa a task.

        Args:
            dry_run: Se True, task simula a execução sem fazer
                mudanças reais. Cada subclasse deve respeitar essa flag.
        """
        self.dry_run = dry_run

    # ========================================================
    # Métodos a serem implementados pelas subclasses
    # ========================================================

    @abstractmethod
    def execute(self) -> TaskResult:
        """
        Executa a lógica de negócio da task.

        DEVE ser implementado pela subclasse.

        Returns:
            TaskResult com status e dados da execução.
        """

    # ========================================================
    # Hooks opcionais (subclasses podem sobrescrever)
    # ========================================================

    def pre_execute(self) -> None:  # noqa: B027
        """
        Hook executado ANTES de ``execute()``.

        Útil pra validações de entrada, setup de recursos, etc.
        Se levantar exceção, ``execute()`` não roda.

        Implementação default é no-op (subclasses podem sobrescrever).
        """

    def post_execute(self, result: TaskResult) -> None:  # noqa: B027
        """
        Hook executado DEPOIS de ``execute()`` (mesmo se falhou).

        Útil pra cleanup, notificações, etc.

        Args:
            result: Resultado retornado por ``execute()``.

        Implementação default é no-op (subclasses podem sobrescrever).
        """

    # ========================================================
    # Método principal (NÃO sobrescrever)
    # ========================================================

    def run(self) -> TaskResult:
        """
        Ponto de entrada da task.

        Fluxo:

        1. Loga início
        2. Chama ``pre_execute()``
        3. Chama ``execute()``
        4. Chama ``post_execute(result)``
        5. Grava no audit trail
        6. Loga fim
        7. Retorna resultado

        Se ocorrer ``AutoTarefasError`` em qualquer passo, captura, registra
        no audit como FAILURE, e retorna ``TaskResult`` com status=FAILURE.
        Outras exceções (bugs reais) propagam pra cima.

        Returns:
            TaskResult com o desfecho da execução.
        """
        started_at = datetime.now(UTC)
        mode = "DRY-RUN" if self.dry_run else "REAL"
        logger.info(
            "Iniciando task '{name}' (modo={mode})",
            name=self.name,
            mode=mode,
        )

        try:
            self.pre_execute()
            result = self.execute()
            self.post_execute(result)
        except AutoTarefasError as e:
            logger.error(
                "Task '{name}' falhou: {error}",
                name=self.name,
                error=str(e),
            )
            result = self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=str(e),
                error_type=type(e).__name__,
            )
            self._record_audit(result)
            return result

        self._record_audit(result)

        logger.info(
            "Task '{name}' concluida: status={status}, duracao={ms}ms, afetados={affected}",
            name=self.name,
            status=result.status.value,
            ms=result.duration_ms,
            affected=result.rows_affected,
        )
        return result

    def _record_audit(self, result: TaskResult) -> None:
        """
        Grava o resultado no audit trail.

        Erros aqui sao silenciosos (apenas warning no log) - audit
        nao deve interromper o fluxo da task. Como ``audit.record()``
        ja captura excecoes internamente, este try/except eh apenas
        defesa adicional.

        Args:
            result: TaskResult retornado por execute() ou construido
                em caso de falha.
        """
        try:
            audit.record(
                task_name=result.task_name,
                status=result.status.value,
                started_at=result.started_at,
                duration_ms=result.duration_ms,
                rows_affected=result.rows_affected,
                rows_failed=result.rows_failed,
                error_message=result.error_message,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Falha ao gravar audit para task '{name}': {err}",
                name=result.task_name,
                err=str(exc),
            )

    # ========================================================
    # Helper pra subclasses
    # ========================================================

    def _make_result(  # noqa: PLR0913
        self,
        *,
        status: TaskStatus,
        started_at: datetime,
        rows_affected: int = 0,
        rows_failed: int = 0,
        data: dict[str, Any] | None = None,
        error_message: str | None = None,
        error_type: str | None = None,
    ) -> TaskResult:
        """
        Helper pra criar ``TaskResult`` calculando ``finished_at`` e
        ``duration_ms`` automaticamente.

        Args:
            status: Status final.
            started_at: Quando a task começou (use ``datetime.now(UTC)`` no início).
            rows_affected: Linhas/registros processados com sucesso.
            rows_failed: Linhas/registros que falharam.
            data: Dados extras (caminho de arquivo, estatísticas, etc.).
            error_message: Mensagem de erro (se aplicável).
            error_type: Nome da classe da exceção.

        Returns:
            TaskResult pronto, com timing calculado.
        """
        finished_at = datetime.now(UTC)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        return TaskResult(
            task_name=self.name,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            rows_affected=rows_affected,
            rows_failed=rows_failed,
            data=data or {},
            error_message=error_message,
            error_type=error_type,
            dry_run=self.dry_run,
        )
