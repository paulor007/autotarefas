# Referência da API

Documentação completa da API Python do AutoTarefas.

## Módulos

<div class="grid cards" markdown>

-   :material-cube-outline:{ .lg .middle } **[Core](core.md)**

    ---

    Módulos fundamentais: BaseTask, TaskResult, Logger, Scheduler, EmailSender.

-   :material-cog:{ .lg .middle } **[Tasks](tasks.md)**

    ---

    Implementações das tarefas: BackupTask, CleanerTask, MonitorTask, ReporterTask.

-   :material-console:{ .lg .middle } **[CLI](cli.md)**

    ---

    Interface de linha de comando e utilitários.

</div>

## Instalação

```bash
pip install autotarefas
```

## Uso Básico

```python
from autotarefas.tasks import BackupTask, CleanerTask, MonitorTask
from autotarefas.core import TaskScheduler, EmailSender

# Criar e executar tarefa
backup = BackupTask(source="/dados", destination="/backup")
result = backup.run()

# Verificar resultado
if result.success:
    print(f"✓ {result.message}")
else:
    print(f"✗ {result.error}")
```

## Estrutura do Pacote

```
autotarefas/
├── core/
│   ├── base.py        # BaseTask, TaskResult, TaskStatus
│   ├── logger.py      # Configuração de logging
│   ├── scheduler.py   # TaskScheduler
│   ├── email.py       # EmailSender
│   ├── notifier.py    # Notifier
│   └── storage/       # Persistência
├── tasks/
│   ├── backup.py      # BackupTask
│   ├── cleaner.py     # CleanerTask
│   ├── monitor.py     # MonitorTask
│   └── reporter.py    # ReporterTask
├── cli/
│   └── commands/      # Comandos CLI
└── utils/             # Utilitários
```

## Convenções

### Nomenclatura

| Tipo | Convenção | Exemplo |
|------|-----------|---------|
| Classes | PascalCase | `BackupTask` |
| Funções | snake_case | `run_backup()` |
| Constantes | UPPER_SNAKE | `MAX_RETRIES` |
| Módulos | snake_case | `task_scheduler.py` |

### Retornos

Todas as tarefas retornam um objeto `TaskResult`:

```python
@dataclass
class TaskResult:
    success: bool           # Se a tarefa foi bem-sucedida
    status: TaskStatus      # SUCCESS, FAILURE, SKIPPED, TIMEOUT
    message: str            # Mensagem descritiva
    data: dict             # Dados adicionais
    error: Optional[str]   # Mensagem de erro (se houver)
    duration: float        # Tempo de execução em segundos
    timestamp: datetime    # Data/hora da execução
```

### Exceções

| Exceção | Descrição |
|---------|-----------|
| `TaskError` | Erro genérico de tarefa |
| `ConfigError` | Erro de configuração |
| `ValidationError` | Erro de validação de parâmetros |
| `TimeoutError` | Tarefa excedeu o tempo limite |

## Type Hints

O AutoTarefas usa type hints em todo o código:

```python
from typing import Optional, List, Dict, Callable
from pathlib import Path

def backup_files(
    source: Path,
    destination: Path,
    exclude: Optional[List[str]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None
) -> TaskResult:
    ...
```

## Logging

```python
from autotarefas.core import get_logger

logger = get_logger(__name__)

logger.debug("Mensagem de debug")
logger.info("Informação")
logger.warning("Aviso")
logger.error("Erro")
```

## Configuração

```python
from autotarefas.config import Config

config = Config()

# Acessar configurações
print(config.backup.compression)
print(config.monitor.cpu_threshold)

# Modificar
config.backup.compression = "tar.gz"
config.save()
```

## Próximos Passos

- [Core - Módulos Fundamentais](core.md)
- [Tasks - Tarefas Disponíveis](tasks.md)
- [CLI - Linha de Comando](cli.md)
