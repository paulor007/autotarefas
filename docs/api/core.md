# Core

Módulos fundamentais do AutoTarefas.

## BaseTask

Classe base abstrata para todas as tarefas.

```python
from autotarefas.core import BaseTask, TaskResult, TaskStatus
```

### Uso Básico

```python
from autotarefas.core import BaseTask, TaskResult, TaskStatus

class MyTask(BaseTask):
    def __init__(self, param1: str, **kwargs):
        super().__init__(**kwargs)
        self.param1 = param1

    def execute(self) -> TaskResult:
        # Sua lógica aqui
        return TaskResult(
            success=True,
            status=TaskStatus.SUCCESS,
            message="Concluído",
            data={"resultado": self.param1}
        )

# Executar
task = MyTask(param1="valor", max_retries=3, timeout=60)
result = task.run()
```

### Parâmetros do Construtor

| Parâmetro | Tipo | Descrição | Padrão |
|-----------|------|-----------|--------|
| `name` | `str` | Nome da tarefa | Nome da classe |
| `max_retries` | `int` | Tentativas em caso de falha | `0` |
| `retry_delay` | `float` | Segundos entre tentativas | `1.0` |
| `timeout` | `float` | Timeout em segundos | `None` |
| `on_success` | `Callable` | Callback de sucesso | `None` |
| `on_failure` | `Callable` | Callback de falha | `None` |

---

## TaskResult

Resultado padronizado de execução.

```python
from autotarefas.core import TaskResult, TaskStatus

result = TaskResult(
    success=True,
    status=TaskStatus.SUCCESS,
    message="Tarefa concluída",
    data={"files": 100, "size": "50MB"}
)

print(result.success)    # True
print(result.duration)   # 2.34
print(result.data)       # {"files": 100, "size": "50MB"}
```

### Atributos

| Atributo | Tipo | Descrição |
|----------|------|-----------|
| `success` | `bool` | Se foi bem-sucedida |
| `status` | `TaskStatus` | Status detalhado |
| `message` | `str` | Mensagem descritiva |
| `data` | `dict` | Dados retornados |
| `error` | `str` | Erro (se houver) |
| `duration` | `float` | Duração em segundos |

### TaskStatus

```python
class TaskStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
```

---

## TaskScheduler

Agendador de tarefas.

```python
from autotarefas.core import TaskScheduler

scheduler = TaskScheduler()
```

### Adicionar Tarefas

```python
# Com expressão cron (diário às 2h)
scheduler.add_cron(task, "0 2 * * *", name="backup_diario")

# Com intervalo (a cada 5 minutos)
scheduler.add_interval(task, minutes=5, name="monitor")

# Data específica
from datetime import datetime
scheduler.add_date(task, datetime(2025, 3, 1, 14, 0), name="especial")
```

### Gerenciar Tarefas

```python
scheduler.list_jobs()           # Listar
scheduler.remove_job("nome")    # Remover
scheduler.pause_job("nome")     # Pausar
scheduler.resume_job("nome")    # Retomar
scheduler.trigger_job("nome")   # Executar agora
```

### Executar

```python
# Em primeiro plano (bloqueia)
scheduler.run()

# Em segundo plano
scheduler.start_background()
# ... fazer outras coisas ...
scheduler.stop()
```

---

## EmailSender

Cliente SMTP para emails.

```python
from autotarefas.core import EmailSender

email = EmailSender()  # Usa configurações do .env
```

### Enviar Email

```python
# Email simples
email.send(
    to="destino@email.com",
    subject="Assunto",
    body="Mensagem"
)

# Email HTML com anexo
email.send(
    to=["user1@email.com", "user2@email.com"],
    subject="Relatório",
    body="<h1>Relatório</h1><p>Em anexo.</p>",
    html=True,
    attachments=["/path/to/file.pdf"]
)

# Com template
email.send_template(
    to="destino@email.com",
    template="notify",
    context={"task": "Backup", "status": "success"}
)
```

---

## Logger

Sistema de logging com Loguru.

```python
from autotarefas.core import get_logger

logger = get_logger(__name__)

logger.debug("Debug")
logger.info("Info")
logger.warning("Aviso")
logger.error("Erro")
```

### Configuração

```python
from autotarefas.core import setup_logging

setup_logging(
    level="INFO",
    log_file="logs/app.log",
    rotation="10 MB",
    retention="30 days"
)
```
