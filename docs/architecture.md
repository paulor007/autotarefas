# 🏗️ Arquitetura do AutoTarefas

Este documento descreve a arquitetura técnica do sistema AutoTarefas.

## Visão Geral

O AutoTarefas é construído seguindo princípios de **arquitetura modular** e **separação de responsabilidades**, permitindo fácil extensão e manutenção.

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI (Click + Rich)                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ backup  │ │  clean  │ │ organize│ │ monitor │ │schedule │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
└───────┼──────────┼──────────┼──────────┼──────────┼────────────┘
        │          │          │          │          │
┌───────┴──────────┴──────────┴──────────┴──────────┴────────────┐
│                         CORE LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   BaseTask   │  │  Scheduler   │  │   Notifier   │          │
│  │  TaskResult  │  │  TaskRegistry│  │   Channels   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
        │                    │                    │
┌───────┴────────────────────┴────────────────────┴──────────────┐
│                        TASKS LAYER                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ BackupTask│ │CleanerTask│ │OrganizerTask│ │MonitorTask│      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
        │                    │                    │
┌───────┴────────────────────┴────────────────────┴──────────────┐
│                       STORAGE LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   JobStore   │  │  RunHistory  │  │   Settings   │          │
│  │    (JSON)    │  │   (SQLite)   │  │    (.env)    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## Camadas do Sistema

### 1. CLI Layer (Interface)

**Responsabilidade:** Interface com o usuário via linha de comando.

**Tecnologias:**
- **Click**: Framework para CLI
- **Rich**: Formatação rica (tabelas, painéis, progress bars)

**Componentes:**
```
src/autotarefas/cli/
├── main.py              # Ponto de entrada, grupo principal
├── commands/            # Comandos específicos
│   ├── backup.py        # autotarefas backup [run|list|restore]
│   ├── cleaner.py       # autotarefas clean [run|preview|profiles]
│   ├── organizer.py     # autotarefas organize [run|preview|stats]
│   ├── monitor.py       # autotarefas monitor [status|live]
│   ├── scheduler.py     # autotarefas schedule [add|list|start]
│   ├── email.py         # autotarefas email [send|test|status]
│   └── report.py        # autotarefas report [sales|templates]
└── utils/
    └── click_utils.py   # Helpers para CLI
```

### 2. Core Layer (Núcleo)

**Responsabilidade:** Lógica central, abstrações e serviços compartilhados.

**Componentes:**

#### BaseTask (`core/base.py`)
```python
class BaseTask(ABC):
    """Classe base abstrata para todas as tarefas."""

    name: str              # Nome da tarefa
    description: str       # Descrição

    def run(self, **params) -> TaskResult:
        """Executa a tarefa com validação e cleanup."""

    @abstractmethod
    def validate(self, **params) -> tuple[bool, str]:
        """Valida parâmetros antes da execução."""

    @abstractmethod
    def execute(self, **params) -> TaskResult:
        """Implementação específica da tarefa."""

    def cleanup(self, **params) -> None:
        """Limpeza pós-execução (opcional)."""
```

#### TaskResult (`core/base.py`)
```python
@dataclass
class TaskResult:
    """Resultado padronizado de uma tarefa."""

    status: TaskStatus     # SUCCESS, FAILED, SKIPPED, CANCELLED
    message: str           # Mensagem descritiva
    data: dict            # Dados específicos
    started_at: datetime  # Início da execução
    finished_at: datetime # Fim da execução
    error: str | None     # Erro se houver
```

#### Scheduler (`core/scheduler.py`)
```python
class Scheduler:
    """Gerenciador de agendamento de tarefas."""

    def add_job(name, task, schedule, **params) -> str
    def remove_job(job_id) -> bool
    def run_job(job_id) -> TaskResult
    def start() -> None  # Inicia loop de execução
    def stop() -> None
```

#### Notifier (`core/notifier.py`)
```python
class Notifier:
    """Sistema de notificações multi-canal."""

    channels: dict[str, ChannelConfig]

    def notify(message, level, **kwargs) -> list[NotificationResult]
    def add_channel(name, channel_type, **config) -> None
```

### 3. Tasks Layer (Tarefas)

**Responsabilidade:** Implementação específica de cada tarefa.

| Task | Arquivo | Descrição |
|------|---------|-----------|
| `BackupTask` | `tasks/backup.py` | Backup com compressão |
| `RestoreTask` | `tasks/backup.py` | Restauração de backup |
| `CleanerTask` | `tasks/cleaner.py` | Limpeza de arquivos |
| `OrganizerTask` | `tasks/organizer.py` | Organização por tipo |
| `MonitorTask` | `tasks/monitor.py` | Monitoramento do sistema |
| `SalesReportTask` | `tasks/reporter.py` | Geração de relatórios |

### 4. Storage Layer (Persistência)

**Responsabilidade:** Armazenamento de dados e configurações.

| Componente | Tecnologia | Dados |
|------------|------------|-------|
| `JobStore` | JSON | Jobs agendados |
| `RunHistory` | SQLite | Histórico de execuções |
| `Settings` | .env + Pydantic | Configurações |

## Fluxo de Execução

### Execução via CLI

```
Usuario                    CLI                     Task                  Storage
   │                        │                        │                      │
   │─── comando ───────────>│                        │                      │
   │                        │─── parse args ────────>│                      │
   │                        │                        │                      │
   │                        │<── TaskResult ─────────│                      │
   │                        │                        │                      │
   │                        │─── save history ──────────────────────────────>│
   │                        │                        │                      │
   │<── output formatado ───│                        │                      │
```

### Execução Agendada

```
Scheduler                  TaskRegistry              Task                JobStore
   │                            │                      │                    │
   │─── check due jobs ─────────────────────────────────────────────────────>│
   │                            │                      │                    │
   │<── job config ─────────────────────────────────────────────────────────│
   │                            │                      │                    │
   │─── get_task(name) ────────>│                      │                    │
   │                            │                      │                    │
   │<── Task class ─────────────│                      │                    │
   │                            │                      │                    │
   │─── task.run(**params) ────────────────────────────>│                    │
   │                            │                      │                    │
   │<── TaskResult ────────────────────────────────────│                    │
   │                            │                      │                    │
   │─── update job stats ──────────────────────────────────────────────────>│
```

## Patterns Utilizados

### 1. Template Method (BaseTask)
```python
class BaseTask:
    def run(self, **params):        # Template method
        if not self.validate():     # Hook
            return failure
        result = self.execute()     # Abstract method
        self.cleanup()              # Hook
        return result
```

### 2. Factory Method (TaskResult)
```python
@classmethod
def success(cls, message, data=None):
    return cls(status=SUCCESS, message=message, data=data)

@classmethod
def failure(cls, message, error=None):
    return cls(status=FAILED, message=message, error=error)
```

### 3. Registry Pattern (TaskRegistry)
```python
class TaskRegistry:
    _tasks: dict[str, type[BaseTask]] = {}

    @classmethod
    def register(cls, name: str, task_class: type[BaseTask]):
        cls._tasks[name] = task_class

    @classmethod
    def get(cls, name: str) -> type[BaseTask]:
        return cls._tasks.get(name)
```

### 4. Strategy Pattern (Profiles)
```python
class OrganizeProfile(Enum):
    DEFAULT = "default"      # Por categoria
    BY_DATE = "by_date"      # Por data
    BY_EXTENSION = "by_extension"  # Por extensão
```

### 5. Singleton Pattern (Settings, Scheduler)
```python
_scheduler_instance: Scheduler | None = None

def get_scheduler() -> Scheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = Scheduler()
    return _scheduler_instance
```

## Extensibilidade

### Adicionando Nova Task

1. **Criar a classe:**
```python
# src/autotarefas/tasks/my_task.py
from autotarefas.core.base import BaseTask, TaskResult

class MyTask(BaseTask):
    name = "my_task"
    description = "Minha tarefa customizada"

    def validate(self, **params):
        return True, ""

    def execute(self, **params):
        # Implementação
        return TaskResult.success("Feito!")
```

2. **Registrar no TaskRegistry:**
```python
# src/autotarefas/core/scheduler.py
TaskRegistry.register("my_task", MyTask)
```

3. **Criar comando CLI (opcional):**
```python
# src/autotarefas/cli/commands/my_task.py
@click.command()
def my_task():
    task = MyTask()
    result = task.run()
```

### Adicionando Novo Canal de Notificação

```python
# No Notifier
def _send_my_channel(self, notification, config):
    # Implementação do envio
    pass

# Registrar
notifier.add_channel("my_channel", NotificationChannel.WEBHOOK, url="...")
```

## Configuração

### Hierarquia de Configuração

```
1. Variáveis de ambiente (maior prioridade)
2. Arquivo .env
3. Valores padrão (menor prioridade)
```

### Estrutura de Diretórios (Runtime)

```
~/.autotarefas/
├── config/
│   └── settings.json     # Configurações persistidas
├── data/
│   ├── jobs.json         # Jobs agendados
│   └── history.db        # Histórico SQLite
├── logs/
│   └── autotarefas.log   # Logs da aplicação
├── backups/              # Backups criados
└── reports/              # Relatórios gerados
```

## Dependências

### Produção
| Pacote | Uso |
|--------|-----|
| click | CLI framework |
| rich | Terminal UI |
| loguru | Logging |
| schedule | Agendamento |
| psutil | Monitoramento |
| python-dotenv | Configuração |

### Desenvolvimento
| Pacote | Uso |
|--------|-----|
| pytest | Testes |
| pytest-cov | Cobertura |
| ruff | Linting/Formatting |

## Considerações de Segurança

1. **Credenciais:** Armazenadas em variáveis de ambiente, nunca no código
2. **Paths:** Validação contra path traversal
3. **Permissões:** Verificação antes de operações destrutivas
4. **Logs:** Mascaramento de dados sensíveis

## Performance

1. **Lazy Loading:** Módulos carregados sob demanda
2. **Streaming:** Processamento de arquivos grandes em chunks
3. **Caching:** Configurações em memória após primeiro load
4. **Async-ready:** Estrutura preparada para async (futuro)

---

*Última atualização: Fevereiro 2026*
