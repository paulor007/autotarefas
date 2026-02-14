# 📚 Documentação da API

Esta seção documenta as classes e funções principais do AutoTarefas para desenvolvedores.

## Índice

### Core

| Módulo | Descrição |
|--------|-----------|
| [base](base.md) | BaseTask, TaskResult, TaskStatus |
| [scheduler](scheduler.md) | Scheduler, TaskRegistry, ScheduledExecution |
| [notifier](notifier.md) | Notifier, Notification, Channels |
| [storage](storage.md) | JobStore, RunHistory |

### Tasks

| Módulo | Descrição |
|--------|-----------|
| [backup](tasks/backup.md) | BackupTask, RestoreTask, BackupManager |
| [cleaner](tasks/cleaner.md) | CleanerTask, CleaningProfile |
| [organizer](tasks/organizer.md) | OrganizerTask, FileCategory |
| [monitor](tasks/monitor.md) | MonitorTask, SystemMetrics |
| [reporter](tasks/reporter.md) | SalesReportTask, ReportFormat |

### Utils

| Módulo | Descrição |
|--------|-----------|
| [helpers](utils/helpers.md) | Funções utilitárias |

---

## Uso Rápido

### Importando módulos

```python
# Core
from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.core.scheduler import Scheduler, get_scheduler
from autotarefas.core.notifier import Notifier, notify

# Tasks
from autotarefas.tasks.backup import BackupTask, RestoreTask
from autotarefas.tasks.cleaner import CleanerTask
from autotarefas.tasks.organizer import OrganizerTask
from autotarefas.tasks.monitor import MonitorTask

# Utils
from autotarefas.utils.helpers import format_size, safe_path
```

### Executando uma tarefa

```python
from autotarefas.tasks.backup import BackupTask

# Criar instância
task = BackupTask()

# Executar
result = task.run(
    source="/home/user/documents",
    destination="/backups",
    compression="zip"
)

# Verificar resultado
if result.is_success:
    print(f"Backup criado: {result.data['archive_path']}")
    print(f"Arquivos: {result.data['files_count']}")
else:
    print(f"Erro: {result.error}")
```

### Criando uma tarefa customizada

```python
from autotarefas.core.base import BaseTask, TaskResult

class MyCustomTask(BaseTask):
    name = "my_task"
    description = "Minha tarefa customizada"

    def validate(self, **params) -> tuple[bool, str]:
        if "required_param" not in params:
            return False, "Parâmetro 'required_param' é obrigatório"
        return True, ""

    def execute(self, **params) -> TaskResult:
        # Sua lógica aqui
        result_data = {"processed": 42}
        return TaskResult.success(
            message="Tarefa executada com sucesso!",
            data=result_data
        )

# Usar
task = MyCustomTask()
result = task.run(required_param="valor")
```

### Usando o Scheduler

```python
from autotarefas.core.scheduler import get_scheduler

scheduler = get_scheduler()

# Adicionar job
job_id = scheduler.add_job(
    name="backup-diario",
    task="backup",
    schedule="02:00",
    schedule_type="daily",
    params={"source": "/documents", "destination": "/backups"}
)

# Listar jobs
for job in scheduler.list_jobs():
    print(f"{job.name}: {job.schedule}")

# Executar manualmente
result = scheduler.run_job(job_id)

# Iniciar scheduler
scheduler.start()
```

### Enviando notificações

```python
from autotarefas.core.notifier import notify, NotificationLevel

# Notificação simples
notify("Backup concluído!", level=NotificationLevel.SUCCESS)

# Com mais detalhes
notify(
    message="Limpeza realizada",
    title="AutoTarefas",
    level=NotificationLevel.INFO,
    data={"files_removed": 42, "space_freed": "1.5 GB"}
)
```

---

## Convenções

### Parâmetros de Tasks

Todas as tasks aceitam parâmetros via `**kwargs`:

```python
task.run(
    param1="valor1",
    param2="valor2",
    dry_run=True  # Parâmetro especial: simula sem executar
)
```

### TaskResult

Sempre retorna um `TaskResult` com:

```python
result.status      # TaskStatus enum
result.is_success  # bool
result.message     # str
result.data        # dict com dados específicos
result.error       # str ou None
result.duration    # float (segundos)
```

### Tratamento de Erros

```python
try:
    result = task.run(**params)
    if not result.is_success:
        logger.error(f"Falha: {result.error}")
except Exception as e:
    logger.exception("Erro inesperado")
```

---

## Referência Completa

Para documentação detalhada de cada módulo, consulte os arquivos específicos nesta pasta.

---

*Documentação gerada para AutoTarefas v0.1.0*
