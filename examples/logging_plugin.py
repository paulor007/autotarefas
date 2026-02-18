# type: ignore
"""
AutoTarefas - Exemplo: Plugin de Logging Avançado
=================================================

Este plugin adiciona logging avançado para todas as tasks.

Funcionalidades:
    - Log de início/fim de tasks
    - Métricas de tempo de execução
    - Histórico de execuções
"""

from datetime import datetime
from typing import Any

from autotarefas.plugins import HookManager, PluginBase, PluginInfo, register_command


class LoggingPlugin(PluginBase):
    """Plugin de logging avançado."""

    def __init__(self):
        super().__init__()
        self._history: list[dict[str, Any]] = []
        self._start_times: dict[str, datetime] = {}

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="advanced-logging",
            version="1.0.0",
            description="Logging avançado para tasks",
            author="AutoTarefas Team",
            tags=["logging", "monitoring", "debug"],
        )

    def activate(self) -> None:
        """Registra hooks ao ativar."""
        HookManager.register(
            "task.before_run",
            self._on_task_start,
            name="logging_before_run",
            plugin=self.name,
        )
        HookManager.register(
            "task.after_run",
            self._on_task_end,
            name="logging_after_run",
            plugin=self.name,
        )

        # Registrar comando CLI
        register_command("task-history", self.show_history, plugin=self.name)

        print(f"[{self.name}] Plugin ativado!")

    def deactivate(self) -> None:
        """Remove hooks ao desativar."""
        self._history.clear()
        self._start_times.clear()
        print(f"[{self.name}] Plugin desativado!")

    def _on_task_start(self, task_name: str, **_kwargs: Any) -> None:
        """Hook chamado antes de executar task."""
        self._start_times[task_name] = datetime.now()
        print(f"[LOG] Task iniciada: {task_name} às {self._start_times[task_name]}")

    def _on_task_end(self, task_name: str, result: Any = None, **_kwargs: Any) -> None:
        """Hook chamado após executar task."""
        end_time = datetime.now()
        start_time = self._start_times.pop(task_name, end_time)
        duration = (end_time - start_time).total_seconds()

        entry = {
            "task_name": task_name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "status": getattr(result, "status", "unknown") if result else "unknown",
        }

        self._history.append(entry)
        print(f"[LOG] Task finalizada: {task_name} (duração: {duration:.2f}s)")

    def show_history(self) -> list[dict[str, Any]]:
        """Retorna histórico de execuções."""
        return self._history.copy()

    def get_stats(self) -> dict[str, Any]:
        """Retorna estatísticas de execução."""
        if not self._history:
            return {"total": 0, "avg_duration": 0}

        total = len(self._history)
        avg_duration = sum(h["duration_seconds"] for h in self._history) / total

        return {
            "total": total,
            "avg_duration": round(avg_duration, 2),
            "last_execution": self._history[-1] if self._history else None,
        }
