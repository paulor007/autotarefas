# type: ignore
"""
AutoTarefas - Exemplo: Plugin de Task Customizada
=================================================

Este plugin demonstra como criar tasks customizadas
e registrá-las no sistema.

A task DatabaseBackupTask faz backup de bancos de dados.
"""

from dataclasses import dataclass, field
from pathlib import Path

from autotarefas.plugins import PluginInfo, TaskPlugin, register_task

# Simular imports do autotarefas
try:
    from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
except ImportError:
    # Fallback para desenvolvimento
    from dataclasses import dataclass as task_dataclass
    from enum import Enum

    class TaskStatus(Enum):
        SUCCESS = "success"
        FAILURE = "failure"

    @task_dataclass
    class TaskResult:
        status: TaskStatus
        message: str = ""
        data: dict = field(default_factory=dict)

        @classmethod
        def success(cls, **kwargs):
            return cls(status=TaskStatus.SUCCESS, **kwargs)

        @classmethod
        def failure(cls, **kwargs):
            return cls(status=TaskStatus.FAILURE, **kwargs)

    class BaseTask:
        name: str = ""

        def run(self):
            pass

        def validate(self):
            return True, ""

        def execute(self):
            pass


@dataclass
class DatabaseBackupTask(BaseTask):
    """
    Task para backup de banco de dados.

    Suporta: PostgreSQL, MySQL, SQLite

    Exemplo:
        task = DatabaseBackupTask(
            name="backup_db",
            db_type="postgresql",
            connection_string="postgresql://user:pass@localhost/db",
            output_dir=Path("./backups"),
        )
        result = task.run()
    """

    name: str = "database_backup"
    db_type: str = "postgresql"  # postgresql, mysql, sqlite
    connection_string: str = ""
    output_dir: Path = field(default_factory=lambda: Path("./backups"))
    compress: bool = True
    tables: list[str] = field(default_factory=list)  # Vazio = todas

    def validate(self) -> tuple[bool, str]:
        if not self.connection_string:
            return False, "connection_string é obrigatório"
        if self.db_type not in ["postgresql", "mysql", "sqlite"]:
            return False, f"db_type inválido: {self.db_type}"
        return True, ""

    def execute(self) -> TaskResult:
        """Executa o backup do banco de dados."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # Simular backup (implementação real dependeria do tipo de DB)
            timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"db_backup_{self.db_type}_{timestamp}"
            if self.compress:
                filename += ".sql.gz"
            else:
                filename += ".sql"

            output_path = self.output_dir / filename

            # Em produção, usaria pg_dump, mysqldump, etc.
            output_path.write_text(f"-- Backup simulado de {self.db_type}\n")

            return TaskResult.success(
                message=f"Backup criado: {output_path}",
                data={
                    "output_path": str(output_path),
                    "db_type": self.db_type,
                    "tables": self.tables or "all",
                    "compressed": self.compress,
                },
            )

        except Exception as e:
            return TaskResult.failure(
                message=f"Erro no backup: {e}",
                data={"error": str(e)},
            )


class DatabaseBackupPlugin(TaskPlugin):
    """Plugin que fornece DatabaseBackupTask."""

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="database-backup",
            version="1.0.0",
            description="Backup de bancos de dados (PostgreSQL, MySQL, SQLite)",
            author="AutoTarefas Team",
            tags=["database", "backup", "postgresql", "mysql", "sqlite"],
            requires=["psycopg2", "mysql-connector-python"],
        )

    def activate(self) -> None:
        """Registra a task ao ativar."""
        register_task("database_backup", DatabaseBackupTask, plugin=self.name)
        print(f"[{self.name}] Task 'database_backup' registrada!")

    def deactivate(self) -> None:
        """Limpa recursos ao desativar."""
        print(f"[{self.name}] Plugin desativado!")

    def get_tasks(self) -> dict[str, type]:
        """Retorna tasks fornecidas pelo plugin."""
        return {
            "database_backup": DatabaseBackupTask,
        }


# Demonstração de uso
if __name__ == "__main__":
    # Criar e ativar plugin
    plugin = DatabaseBackupPlugin()
    plugin.activate()

    # Usar a task
    task = DatabaseBackupTask(
        name="test_backup",
        db_type="postgresql",
        connection_string="postgresql://localhost/test",
        output_dir=Path("./test_backups"),
    )

    valid, msg = task.validate()
    print(f"Validação: {valid} - {msg}")

    if valid:
        result = task.execute()
        print(f"Resultado: {result}")
