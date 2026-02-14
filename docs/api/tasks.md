# Tasks

Implementações das tarefas do AutoTarefas.

## BackupTask

Backup de arquivos e diretórios.

```python
from autotarefas.tasks import BackupTask

backup = BackupTask(
    source="/dados",
    destination="/backup",
    compress=True,
    compression_type="zip",
    incremental=False,
    verify=True,
    exclude=["*.tmp", "__pycache__"]
)

result = backup.run()
print(f"Backup: {result.data['backup_file']}")
```

### Parâmetros

| Parâmetro | Tipo | Descrição | Padrão |
|-----------|------|-----------|--------|
| `source` | `str/Path` | Origem dos arquivos | Obrigatório |
| `destination` | `str/Path` | Destino do backup | Obrigatório |
| `compress` | `bool` | Ativar compressão | `False` |
| `compression_type` | `str` | `zip` ou `tar.gz` | `zip` |
| `compression_level` | `int` | Nível 1-9 | `6` |
| `incremental` | `bool` | Modo incremental | `False` |
| `verify` | `bool` | Verificar integridade | `True` |
| `exclude` | `list` | Padrões a excluir | `[]` |

### Dados Retornados

```python
result.data = {
    "backup_file": "/backup/backup_20250212.zip",
    "files_count": 1234,
    "total_size": "456 MB",
    "compressed_size": "123 MB",
    "verified": True
}
```

---

## CleanerTask

Limpeza de arquivos.

```python
from autotarefas.tasks import CleanerTask

cleaner = CleanerTask(
    path="/downloads",
    max_age_days=30,
    max_size_mb=100,
    patterns=["*.tmp", "*.log"],
    exclude=["importante.txt"],
    use_trash=True,
    dry_run=False
)

result = cleaner.run()
print(f"Removidos: {result.data['deleted_count']}")
```

### Parâmetros

| Parâmetro | Tipo | Descrição | Padrão |
|-----------|------|-----------|--------|
| `path` | `str/Path` | Diretório a limpar | Obrigatório |
| `max_age_days` | `int` | Idade mínima em dias | `30` |
| `max_size_mb` | `float` | Tamanho mínimo MB | `None` |
| `patterns` | `list` | Padrões glob | `["*"]` |
| `exclude` | `list` | Arquivos protegidos | `[]` |
| `use_trash` | `bool` | Usar lixeira | `True` |
| `recursive` | `bool` | Incluir subpastas | `True` |
| `dry_run` | `bool` | Apenas simular | `False` |

### Dados Retornados

```python
result.data = {
    "deleted_count": 45,
    "freed_space": "1.2 GB",
    "files_to_delete": [...]  # Se dry_run=True
}
```

---

## MonitorTask

Monitoramento do sistema.

```python
from autotarefas.tasks import MonitorTask

monitor = MonitorTask(
    cpu_threshold=80,
    memory_threshold=90,
    disk_threshold=85,
    disk_paths=["/", "/home"],
    network=True
)

result = monitor.run()
print(f"CPU: {result.data['cpu']}%")
```

### Parâmetros

| Parâmetro | Tipo | Descrição | Padrão |
|-----------|------|-----------|--------|
| `cpu_threshold` | `int` | Limite CPU % | `None` |
| `memory_threshold` | `int` | Limite memória % | `None` |
| `disk_threshold` | `int` | Limite disco % | `None` |
| `disk_paths` | `list` | Discos a monitorar | `["/"]` |
| `network` | `bool` | Incluir rede | `False` |
| `processes` | `bool` | Incluir processos | `False` |

### Dados Retornados

```python
result.data = {
    "cpu": 45.2,
    "memory": 67.8,
    "disk": 55.0,
    "disks": [
        {"mountpoint": "/", "percent": 55.0, "free": "50GB"}
    ],
    "network": {"bytes_sent": "1.2GB", "bytes_recv": "5.6GB"},
    "alerts": [
        {"metric": "cpu", "value": 85, "threshold": 80}
    ]
}
```

### Monitoramento Contínuo

```python
def on_alert(metric, value, threshold):
    print(f"ALERTA: {metric} = {value}%")

monitor = MonitorTask(cpu_threshold=80, on_alert=on_alert)
monitor.watch(interval=5)  # Loop a cada 5s
```

---

## ReporterTask

Geração de relatórios.

```python
from autotarefas.tasks import ReporterTask

reporter = ReporterTask(
    report_type="backup_summary",
    output_format="xlsx",
    output_path="/reports",
    period="weekly"
)

result = reporter.run()
print(f"Relatório: {result.data['report_file']}")
```

### Parâmetros

| Parâmetro | Tipo | Descrição | Padrão |
|-----------|------|-----------|--------|
| `report_type` | `str` | Tipo do relatório | Obrigatório |
| `output_format` | `str` | `xlsx`, `csv`, `html` | `xlsx` |
| `output_path` | `str/Path` | Pasta de saída | `./reports` |
| `period` | `str` | `daily`, `weekly`, `monthly` | `daily` |
| `template` | `str` | Template customizado | `None` |

### Tipos de Relatório

- `backup_summary` - Resumo de backups
- `cleaner_summary` - Resumo de limpezas
- `monitor_history` - Histórico de monitoramento
- `scheduler_history` - Histórico de execuções

---

## Criando Tarefas Customizadas

```python
from autotarefas.core import BaseTask, TaskResult, TaskStatus

class MinhaTask(BaseTask):
    """Minha tarefa customizada."""

    def __init__(self, meu_param: str, **kwargs):
        super().__init__(**kwargs)
        self.meu_param = meu_param

    def execute(self) -> TaskResult:
        try:
            # Sua lógica aqui
            resultado = self._processar()

            return TaskResult(
                success=True,
                status=TaskStatus.SUCCESS,
                message="Processado com sucesso",
                data={"resultado": resultado}
            )
        except Exception as e:
            return TaskResult(
                success=False,
                status=TaskStatus.FAILURE,
                error=str(e)
            )

    def _processar(self):
        return f"Processado: {self.meu_param}"

# Usar
task = MinhaTask(meu_param="valor", max_retries=3)
result = task.run()
```
