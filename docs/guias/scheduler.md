# Agendamento de Tarefas

O módulo Scheduler permite agendar tarefas para execução automática usando expressões cron ou intervalos simples.

## Início Rápido

```bash
# Adicionar tarefa agendada
autotarefas schedule add backup --cron "0 2 * * *" --origem ~/Docs --destino ~/Backup

# Listar tarefas
autotarefas schedule list

# Executar agendador
autotarefas schedule run
```

## Comandos CLI

### `schedule add`

Adiciona uma nova tarefa agendada.

```bash
autotarefas schedule add <TIPO> [OPÇÕES]
```

**Tipos disponíveis:** `backup`, `clean`, `monitor`, `report`

#### Opções de Agendamento

| Opção | Descrição | Exemplo |
|-------|-----------|---------|
| `--cron` | Expressão cron | `"0 2 * * *"` |
| `--intervalo` | Intervalo simples | `5m`, `1h`, `1d` |
| `--data` | Data/hora específica | `"2025-03-01 14:00"` |
| `--nome` | Nome da tarefa | `"backup_diario"` |

**Exemplos:**

```bash
# Backup diário às 2h
autotarefas schedule add backup \
    --cron "0 2 * * *" \
    --origem ~/Documentos \
    --destino ~/Backups \
    --nome "backup_docs"

# Limpeza semanal aos domingos
autotarefas schedule add clean \
    --cron "0 3 * * 0" \
    --caminho ~/Downloads \
    --dias 30 \
    --nome "limpar_downloads"

# Monitoramento a cada 5 minutos
autotarefas schedule add monitor \
    --intervalo 5m \
    --cpu 80 \
    --memoria 90 \
    --nome "monitor_sistema"

# Relatório mensal no dia 1
autotarefas schedule add report \
    --cron "0 8 1 * *" \
    --tipo vendas \
    --nome "relatorio_mensal"
```

### `schedule list`

Lista todas as tarefas agendadas.

```bash
autotarefas schedule list [OPÇÕES]
```

| Opção | Descrição |
|-------|-----------|
| `--ativas` | Mostrar apenas ativas |
| `--detalhes` | Mostrar configurações |

**Exemplo:**

```bash
autotarefas schedule list --detalhes
```

Saída:
```
╭─────────────────────────────────────────────────────────────────────╮
│                        Tarefas Agendadas                             │
├─────────────────┬──────────┬─────────────────┬───────────────────────┤
│ Nome            │ Tipo     │ Agendamento     │ Próxima Execução      │
├─────────────────┼──────────┼─────────────────┼───────────────────────┤
│ backup_docs     │ backup   │ 0 2 * * *       │ 2025-02-13 02:00:00   │
│ limpar_downloads│ clean    │ 0 3 * * 0       │ 2025-02-16 03:00:00   │
│ monitor_sistema │ monitor  │ cada 5 min      │ 2025-02-12 14:35:00   │
╰─────────────────┴──────────┴─────────────────┴───────────────────────╯
```

### `schedule remove`

Remove uma tarefa agendada.

```bash
autotarefas schedule remove <NOME>
```

**Exemplo:**

```bash
autotarefas schedule remove backup_docs
```

### `schedule run`

Inicia o agendador para executar as tarefas.

```bash
autotarefas schedule run [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--daemon`, `-d` | Executar em segundo plano | `False` |
| `--log` | Arquivo de log | `scheduler.log` |

**Exemplos:**

```bash
# Executar em primeiro plano
autotarefas schedule run

# Executar como daemon
autotarefas schedule run --daemon

# Com log específico
autotarefas schedule run --log /var/log/autotarefas.log
```

### `schedule history`

Mostra histórico de execuções.

```bash
autotarefas schedule history [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--nome` | Filtrar por tarefa | `None` |
| `--ultimas` | Período | `7d` |
| `--status` | Filtrar por status | `all` |

**Exemplo:**

```bash
autotarefas schedule history --nome backup_docs --ultimas 7d
```

Saída:
```
╭─────────────────────────────────────────────────────────────────────╮
│              Histórico: backup_docs (últimos 7 dias)                 │
├─────────────────────┬──────────┬──────────┬─────────────────────────┤
│ Data/Hora           │ Status   │ Duração  │ Detalhes                │
├─────────────────────┼──────────┼──────────┼─────────────────────────┤
│ 2025-02-12 02:00:00 │ ✓ Sucesso│ 2m 34s   │ 1.234 arquivos, 456 MB  │
│ 2025-02-11 02:00:00 │ ✓ Sucesso│ 2m 12s   │ 1.230 arquivos, 452 MB  │
│ 2025-02-10 02:00:00 │ ✗ Falha  │ 0m 05s   │ Disco cheio             │
│ 2025-02-09 02:00:00 │ ✓ Sucesso│ 2m 45s   │ 1.225 arquivos, 448 MB  │
╰─────────────────────┴──────────┴──────────┴─────────────────────────╯
```

### `schedule pause` / `schedule resume`

Pausa ou retoma uma tarefa.

```bash
autotarefas schedule pause <NOME>
autotarefas schedule resume <NOME>
```

### `schedule trigger`

Executa uma tarefa imediatamente (fora do agendamento).

```bash
autotarefas schedule trigger <NOME>
```

## Expressões Cron

### Formato

```
┌───────────── minuto (0 - 59)
│ ┌───────────── hora (0 - 23)
│ │ ┌───────────── dia do mês (1 - 31)
│ │ │ ┌───────────── mês (1 - 12)
│ │ │ │ ┌───────────── dia da semana (0 - 6) (Domingo = 0)
│ │ │ │ │
* * * * *
```

### Exemplos Comuns

| Expressão | Descrição |
|-----------|-----------|
| `0 * * * *` | A cada hora |
| `0 2 * * *` | Todo dia às 2h |
| `0 2 * * 0` | Todo domingo às 2h |
| `0 2 1 * *` | Todo dia 1 às 2h |
| `*/5 * * * *` | A cada 5 minutos |
| `0 9-17 * * 1-5` | Das 9h às 17h, seg-sex |
| `0 0 1,15 * *` | Dia 1 e 15 à meia-noite |

### Caracteres Especiais

| Caractere | Significado | Exemplo |
|-----------|-------------|---------|
| `*` | Qualquer valor | `* * * * *` |
| `,` | Lista | `1,15 * * * *` |
| `-` | Intervalo | `9-17 * * * *` |
| `/` | Passo | `*/5 * * * *` |

## Intervalos Simples

Para casos mais simples, use intervalos:

| Formato | Descrição |
|---------|-----------|
| `30s` | 30 segundos |
| `5m` | 5 minutos |
| `1h` | 1 hora |
| `12h` | 12 horas |
| `1d` | 1 dia |
| `1w` | 1 semana |

```bash
# A cada 30 segundos
autotarefas schedule add monitor --intervalo 30s

# A cada 6 horas
autotarefas schedule add backup --intervalo 6h

# Uma vez por dia
autotarefas schedule add clean --intervalo 1d
```

## Uso via Python

### Criar Agendador

```python
from autotarefas.core import TaskScheduler
from autotarefas.tasks import BackupTask, CleanerTask, MonitorTask

scheduler = TaskScheduler()
```

### Agendar com Cron

```python
# Backup diário às 2h
backup = BackupTask(
    source="/home/user/docs",
    destination="/backup"
)
scheduler.add_cron(backup, "0 2 * * *", name="backup_diario")

# Limpeza semanal aos domingos
cleaner = CleanerTask(
    path="/home/user/downloads",
    max_age_days=30
)
scheduler.add_cron(cleaner, "0 3 * * 0", name="limpeza_semanal")
```

### Agendar com Intervalo

```python
# Monitoramento a cada 5 minutos
monitor = MonitorTask(
    cpu_threshold=80,
    memory_threshold=90
)
scheduler.add_interval(monitor, minutes=5, name="monitor_sistema")

# Backup a cada 6 horas
scheduler.add_interval(backup, hours=6, name="backup_frequente")
```

### Agendar para Data Específica

```python
from datetime import datetime

# Executar em data específica
scheduler.add_date(
    backup,
    run_date=datetime(2025, 3, 1, 14, 0),
    name="backup_migracao"
)
```

### Executar Agendador

```python
# Executar em loop (bloqueia)
scheduler.run()

# Executar em thread separada
scheduler.start_background()

# ... fazer outras coisas ...

# Parar quando necessário
scheduler.stop()
```

### Callbacks

```python
def on_job_success(job_name, result):
    print(f"✓ {job_name} concluído com sucesso")
    print(f"  Duração: {result.duration}")

def on_job_failure(job_name, error):
    print(f"✗ {job_name} falhou: {error}")
    # Enviar alerta

scheduler = TaskScheduler(
    on_success=on_job_success,
    on_failure=on_job_failure
)
```

### Persistência

```python
# Salvar jobs em arquivo (persistir entre reinícios)
scheduler = TaskScheduler(
    persist=True,
    job_store="jobs.json"
)

# Adicionar jobs
scheduler.add_cron(backup, "0 2 * * *", name="backup")

# Jobs são salvos automaticamente
# Na próxima execução, serão carregados do arquivo
```

### Histórico de Execuções

```python
# Habilitar histórico
scheduler = TaskScheduler(
    save_history=True,
    history_file="history.json"
)

# Consultar histórico
history = scheduler.get_history("backup_diario", days=7)

for execution in history:
    print(f"{execution['timestamp']}: {execution['status']}")
```

### Controle de Jobs

```python
# Listar jobs
for job in scheduler.list_jobs():
    print(f"{job.name}: {job.next_run}")

# Pausar job
scheduler.pause_job("backup_diario")

# Retomar job
scheduler.resume_job("backup_diario")

# Remover job
scheduler.remove_job("backup_diario")

# Executar imediatamente
scheduler.trigger_job("backup_diario")
```

## Configuração

### Variáveis de Ambiente

```bash
# .env
SCHEDULER_TIMEZONE=America/Sao_Paulo
SCHEDULER_PERSIST=true
SCHEDULER_JOB_STORE=jobs.json
SCHEDULER_MAX_CONCURRENT=3
SCHEDULER_MISFIRE_GRACE_TIME=60
```

### Arquivo de Configuração

```json
{
  "scheduler": {
    "timezone": "America/Sao_Paulo",
    "persist": true,
    "job_store": "jobs.json",
    "history_file": "history.json",
    "max_concurrent": 3,
    "misfire_grace_time": 60,
    "coalesce": true
  }
}
```

## Execução como Serviço

### Linux (systemd)

Crie `/etc/systemd/system/autotarefas.service`:

```ini
[Unit]
Description=AutoTarefas Scheduler
After=network.target

[Service]
Type=simple
User=seu_usuario
WorkingDirectory=/home/seu_usuario
ExecStart=/usr/local/bin/autotarefas schedule run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Comandos:

```bash
# Habilitar serviço
sudo systemctl enable autotarefas

# Iniciar
sudo systemctl start autotarefas

# Ver status
sudo systemctl status autotarefas

# Ver logs
journalctl -u autotarefas -f
```

### Windows (Task Scheduler)

1. Abra o "Agendador de Tarefas"
2. Crie uma nova tarefa
3. Configure para iniciar com o sistema
4. Ação: `python -m autotarefas schedule run`

### Docker

```dockerfile
FROM python:3.12-slim
RUN pip install autotarefas
COPY config/ /app/config/
WORKDIR /app
CMD ["autotarefas", "schedule", "run"]
```

```bash
docker run -d --name autotarefas-scheduler \
    -v $(pwd)/data:/app/data \
    autotarefas-scheduler
```

## Tratamento de Erros

### Retry Automático

```python
from autotarefas.tasks import BackupTask

# Tarefa com retry
backup = BackupTask(
    source="/dados",
    destination="/backup",
    max_retries=3,
    retry_delay=60  # segundos entre tentativas
)

scheduler.add_cron(backup, "0 2 * * *")
```

### Timeout

```python
backup = BackupTask(
    source="/dados",
    destination="/backup",
    timeout=3600  # 1 hora máximo
)
```

### Notificação de Falha

```python
from autotarefas.core import EmailSender

email = EmailSender()

def notify_failure(job_name, error):
    email.send(
        to="admin@empresa.com",
        subject=f"[FALHA] {job_name}",
        body=f"A tarefa {job_name} falhou:\n\n{error}"
    )

scheduler = TaskScheduler(on_failure=notify_failure)
```

## Boas Práticas

!!! tip "Dicas"
    1. **Use nomes descritivos** para as tarefas
    2. **Evite horários cheios** (meia-noite, hora cheia)
    3. **Configure retry** para tarefas críticas
    4. **Monitore o histórico** regularmente
    5. **Use persistência** para não perder jobs após reinício
    6. **Configure notificações** para falhas

!!! warning "Atenção"
    - Cuidado com tarefas que demoram muito
    - Evite agendar muitas tarefas no mesmo horário
    - Verifique o timezone configurado
    - Monitore o uso de recursos do agendador

## Troubleshooting

### Tarefa não executa

```bash
# Verificar se o agendador está rodando
autotarefas schedule status

# Verificar próxima execução
autotarefas schedule list --detalhes

# Verificar logs
tail -f scheduler.log
```

### Tarefa executa no horário errado

```bash
# Verificar timezone
autotarefas config show scheduler.timezone

# Corrigir timezone
autotarefas config set scheduler.timezone America/Sao_Paulo
```

### Jobs perdidos após reinício

```bash
# Verificar se persistência está habilitada
autotarefas config show scheduler.persist

# Habilitar persistência
autotarefas config set scheduler.persist true
```

## Próximos Passos

- [Configurar notificações por email](email.md)
- [Agendar backups](backup.md)
- [Agendar limpezas](cleaner.md)
- [Agendar monitoramento](monitor.md)
