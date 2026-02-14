# 📦 Core: Base

Módulo central com classes base para todas as tarefas.

**Localização:** `src/autotarefas/core/base.py`

---

## TaskStatus

Enum que representa o status de uma tarefa.

```python
from autotarefas.core.base import TaskStatus
```

### Valores

| Valor | Descrição |
|-------|-----------|
| `PENDING` | Aguardando execução |
| `RUNNING` | Em execução |
| `SUCCESS` | Concluída com sucesso |
| `FAILED` | Falhou |
| `SKIPPED` | Pulada (ex: dry-run) |
| `CANCELLED` | Cancelada (ex: Ctrl+C) |

### Propriedades

```python
status = TaskStatus.SUCCESS

status.is_finished  # True se SUCCESS, FAILED, SKIPPED ou CANCELLED
status.is_success   # True se SUCCESS
status.is_error     # True se FAILED
status.emoji        # "✅" para SUCCESS, "❌" para FAILED, etc.
```

---

## TaskResult

Dataclass que representa o resultado de uma tarefa.

```python
from autotarefas.core.base import TaskResult
```

### Atributos

| Atributo | Tipo | Descrição |
|----------|------|-----------|
| `status` | `TaskStatus` | Status da execução |
| `message` | `str` | Mensagem descritiva |
| `data` | `dict` | Dados específicos da tarefa |
| `task_name` | `str` | Nome da tarefa |
| `started_at` | `datetime` | Início da execução |
| `finished_at` | `datetime` | Fim da execução |
| `error` | `str \| None` | Mensagem de erro |

### Propriedades

```python
result.is_success      # bool - True se status == SUCCESS
result.duration        # float - Duração em segundos
result.duration_formatted  # str - Ex: "1.5s", "2m 30s"
```

### Factory Methods

```python
# Sucesso
result = TaskResult.success(
    message="Operação concluída",
    data={"count": 42}
)

# Falha
result = TaskResult.failure(
    message="Operação falhou",
    error="Arquivo não encontrado"
)

# Pulada
result = TaskResult.skipped(
    message="Modo dry-run"
)

# Cancelada
result = TaskResult.cancelled(
    message="Interrompida pelo usuário"
)
```

### Serialização

```python
# Para dicionário
d = result.to_dict()

# Para string
print(result)  # "[SUCCESS] Operação concluída (1.5s)"
```

---

## BaseTask

Classe abstrata base para todas as tarefas.

```python
from autotarefas.core.base import BaseTask
```

### Atributos de Classe

| Atributo | Tipo | Descrição |
|----------|------|-----------|
| `name` | `str` | Nome único da tarefa |
| `description` | `str` | Descrição da tarefa |

### Métodos Abstratos

#### validate

```python
def validate(self, **params) -> tuple[bool, str]:
    """
    Valida parâmetros antes da execução.

    Args:
        **params: Parâmetros da tarefa

    Returns:
        Tupla (válido, mensagem_erro)
    """
```

#### execute

```python
def execute(self, **params) -> TaskResult:
    """
    Executa a lógica principal da tarefa.

    Args:
        **params: Parâmetros da tarefa

    Returns:
        TaskResult com o resultado
    """
```

### Métodos Opcionais

#### cleanup

```python
def cleanup(self, **params) -> None:
    """
    Limpeza pós-execução (opcional).
    Chamado sempre, mesmo em caso de erro.
    """
```

### Método Principal

#### run

```python
def run(self, **params) -> TaskResult:
    """
    Executa a tarefa completa.

    Fluxo:
    1. Valida parâmetros
    2. Executa tarefa
    3. Chama cleanup

    Args:
        **params: Parâmetros da tarefa
        dry_run: Se True, simula sem executar

    Returns:
        TaskResult com o resultado
    """
```

---

## Exemplo Completo

```python
from autotarefas.core.base import BaseTask, TaskResult
from pathlib import Path

class FileCountTask(BaseTask):
    """Conta arquivos em um diretório."""

    name = "file_count"
    description = "Conta arquivos em um diretório"

    def validate(self, **params) -> tuple[bool, str]:
        path = params.get("path")

        if not path:
            return False, "Parâmetro 'path' é obrigatório"

        if not Path(path).exists():
            return False, f"Diretório não existe: {path}"

        if not Path(path).is_dir():
            return False, f"Não é um diretório: {path}"

        return True, ""

    def execute(self, **params) -> TaskResult:
        path = Path(params["path"])
        recursive = params.get("recursive", False)

        if recursive:
            files = list(path.rglob("*"))
        else:
            files = list(path.iterdir())

        file_count = sum(1 for f in files if f.is_file())
        dir_count = sum(1 for f in files if f.is_dir())

        return TaskResult.success(
            message=f"Encontrados {file_count} arquivos",
            data={
                "path": str(path),
                "files": file_count,
                "directories": dir_count,
                "total": len(files)
            }
        )

    def cleanup(self, **params) -> None:
        # Nada a limpar nesta tarefa
        pass


# Uso
task = FileCountTask()

# Normal
result = task.run(path="/home/user/documents", recursive=True)
print(result.data["files"])  # 42

# Dry-run
result = task.run(path="/home/user/documents", dry_run=True)
print(result.status)  # TaskStatus.SKIPPED
```

---

## Tratamento de Erros

O método `run` captura exceções automaticamente:

```python
class FailingTask(BaseTask):
    name = "failing"

    def validate(self, **params):
        return True, ""

    def execute(self, **params):
        raise ValueError("Algo deu errado!")

task = FailingTask()
result = task.run()

print(result.status)  # TaskStatus.FAILED
print(result.error)   # "Algo deu errado!"
```

Para `KeyboardInterrupt` (Ctrl+C):

```python
result = task.run()  # Usuário pressiona Ctrl+C
print(result.status)  # TaskStatus.CANCELLED
```

---

*Documentação para AutoTarefas v0.1.0*
