# Arquitetura

Visão geral da arquitetura do AutoTarefas.

## Visão Geral

O AutoTarefas segue uma arquitetura modular com separação clara de responsabilidades:

```
┌─────────────────────────────────────────────────────────┐
│                         CLI                              │
│                  (Click + Rich)                          │
├─────────────────────────────────────────────────────────┤
│                        Tasks                             │
│     BackupTask │ CleanerTask │ MonitorTask │ Reporter   │
├─────────────────────────────────────────────────────────┤
│                        Core                              │
│   BaseTask │ Scheduler │ EmailSender │ Logger │ Storage │
├─────────────────────────────────────────────────────────┤
│                       Utils                              │
│        datetime │ format │ json │ helpers               │
└─────────────────────────────────────────────────────────┘
```

## Módulos

### Core

Módulos fundamentais que fornecem a base para todo o sistema.

| Módulo | Responsabilidade |
|--------|------------------|
| `base.py` | Classes base: BaseTask, TaskResult, TaskStatus |
| `logger.py` | Configuração de logging (Loguru) |
| `scheduler.py` | Agendamento de tarefas |
| `email.py` | Envio de emails (SMTP) |
| `notifier.py` | Sistema de notificações |
| `storage/` | Persistência (jobs, histórico) |

### Tasks

Implementações concretas das tarefas.

| Módulo | Responsabilidade |
|--------|------------------|
| `backup.py` | Backup de arquivos |
| `cleaner.py` | Limpeza de arquivos |
| `monitor.py` | Monitoramento do sistema |
| `reporter.py` | Geração de relatórios |

### CLI

Interface de linha de comando.

| Módulo | Responsabilidade |
|--------|------------------|
| `main.py` | Grupo principal de comandos |
| `commands/` | Subcomandos (backup, clean, etc.) |
| `utils/` | Utilitários de CLI |

### Utils

Funções utilitárias compartilhadas.

| Módulo | Responsabilidade |
|--------|------------------|
| `datetime_utils.py` | Manipulação de datas |
| `format_utils.py` | Formatação (bytes, duração) |
| `json_utils.py` | Serialização JSON |
| `helpers.py` | Decoradores e helpers |

## Padrões de Design

### Template Method (BaseTask)

Todas as tarefas herdam de `BaseTask` que implementa o padrão Template Method:

```python
class BaseTask(ABC):
    def run(self) -> TaskResult:
        """Template method - não sobrescrever."""
        self._pre_execute()
        try:
            result = self.execute()  # Hook method
        except Exception as e:
            result = self._handle_error(e)
        self._post_execute(result)
        return result

    @abstractmethod
    def execute(self) -> TaskResult:
        """Hook method - implementar nas subclasses."""
        pass
```

### Strategy (Compressão)

Diferentes estratégias de compressão:

```python
class CompressionStrategy(ABC):
    @abstractmethod
    def compress(self, source: Path, dest: Path) -> Path: ...

class ZipCompression(CompressionStrategy):
    def compress(self, source, dest): ...

class TarGzCompression(CompressionStrategy):
    def compress(self, source, dest): ...
```

### Observer (Notificações)

Sistema de callbacks para eventos:

```python
class BackupTask(BaseTask):
    def __init__(
        self,
        on_progress: Callable = None,
        on_success: Callable = None,
        on_failure: Callable = None
    ):
        self.on_progress = on_progress
        self.on_success = on_success
        self.on_failure = on_failure
```

### Repository (Storage)

Abstração para persistência:

```python
class JobStore:
    def save(self, job: Job) -> None: ...
    def load(self, job_id: str) -> Job: ...
    def list_all(self) -> List[Job]: ...
    def delete(self, job_id: str) -> None: ...
```

## Fluxo de Execução

### Execução de Tarefa

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  CLI     │───▶│  Task    │───▶│ Execute  │───▶│  Result  │
│ Command  │    │  .run()  │    │  Logic   │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                     │                              │
                     ▼                              ▼
               ┌──────────┐                  ┌──────────┐
               │  Logger  │                  │ Notifier │
               └──────────┘                  └──────────┘
```

### Agendamento

```
┌──────────┐    ┌───────────┐    ┌──────────┐
│  Add Job │───▶│ Scheduler │───▶│ JobStore │
└──────────┘    │   Loop    │    │  (JSON)  │
                └─────┬─────┘    └──────────┘
                      │
            ┌─────────┴─────────┐
            ▼                   ▼
      ┌──────────┐        ┌──────────┐
      │  Task 1  │        │  Task 2  │
      │  .run()  │        │  .run()  │
      └──────────┘        └──────────┘
```

## Configuração

### Hierarquia de Configuração

```
Argumentos CLI (maior prioridade)
        │
        ▼
Variáveis de Ambiente
        │
        ▼
Arquivo .env
        │
        ▼
autotarefas.json
        │
        ▼
Valores Padrão (menor prioridade)
```

### Classe Config

```python
@dataclass
class Config:
    backup: BackupConfig
    cleaner: CleanerConfig
    monitor: MonitorConfig
    scheduler: SchedulerConfig
    email: EmailConfig

    @classmethod
    def load(cls) -> "Config":
        """Carrega configuração de todas as fontes."""
        ...
```

## Decisões de Design

### Por que src/ layout?

- Evita conflitos de importação
- Garante que testes usem o pacote instalado
- Padrão recomendado pela PyPA

### Por que Click + Rich?

- **Click**: Framework maduro, bem documentado, extensível
- **Rich**: UI bonita no terminal, tabelas, progress bars

### Por que Loguru?

- Sintaxe mais simples que logging padrão
- Rotação automática de arquivos
- Colorização built-in
- Serialização JSON fácil

### Por que JSON para persistência?

- Simples e portátil
- Fácil de debugar (legível por humanos)
- Sem dependências externas (SQLite seria alternativa)

## Extensibilidade

### Adicionar Nova Tarefa

1. Criar classe que herda de `BaseTask`:

```python
# src/autotarefas/tasks/minha_task.py
from autotarefas.core import BaseTask, TaskResult

class MinhaTask(BaseTask):
    def execute(self) -> TaskResult:
        ...
```

2. Registrar em `__init__.py`:

```python
# src/autotarefas/tasks/__init__.py
from .minha_task import MinhaTask
```

3. Adicionar comando CLI (opcional):

```python
# src/autotarefas/cli/commands/minha_task.py
@click.group()
def minha_task():
    ...
```

### Adicionar Novo Storage Backend

Implementar a interface de storage:

```python
class RedisJobStore(JobStoreBase):
    def save(self, job): ...
    def load(self, job_id): ...
    def list_all(self): ...
    def delete(self, job_id): ...
```

## Testes

### Estratégia de Testes

```
tests/
├── test_*.py           # Testes unitários
├── integration/        # Testes de integração
└── e2e/               # Testes end-to-end (CLI)
```

### Fixtures Compartilhadas

```python
# tests/conftest.py
@pytest.fixture
def temp_dir(tmp_path):
    """Diretório temporário para testes."""
    ...

@pytest.fixture
def mock_smtp():
    """Mock do servidor SMTP."""
    ...
```

## Performance

### Considerações

- Backup usa streaming para arquivos grandes
- Monitor usa psutil com caching
- Scheduler usa threads para não bloquear
- Logs são bufferizados antes de escrever

### Limites Conhecidos

- Backup de arquivos muito grandes (>10GB) pode consumir muita RAM
- Monitor com intervalo muito baixo (<1s) pode impactar CPU
- Muitos jobs simultâneos podem sobrecarregar o sistema
