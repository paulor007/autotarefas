# Configuração

Este guia explica como configurar o AutoTarefas para suas necessidades.

## Arquivos de Configuração

O AutoTarefas usa dois arquivos principais de configuração:

| Arquivo | Descrição | Localização |
|---------|-----------|-------------|
| `.env` | Variáveis de ambiente (senhas, API keys) | Raiz do projeto |
| `autotarefas.json` | Configurações gerais | Raiz do projeto |

## Variáveis de Ambiente (.env)

O arquivo `.env` armazena configurações sensíveis:

```bash
# ============================================
# AUTOTAREFAS - Configuração de Ambiente
# ============================================

# === GERAL ===
AUTOTAREFAS_ENV=production
AUTOTAREFAS_DEBUG=false
AUTOTAREFAS_LOG_LEVEL=INFO

# === EMAIL ===
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@gmail.com
SMTP_PASSWORD=sua-senha-de-app
SMTP_FROM=seu-email@gmail.com
SMTP_USE_TLS=true

# === NOTIFICAÇÕES ===
NOTIFY_EMAIL=destino@email.com
NOTIFY_ON_SUCCESS=false
NOTIFY_ON_FAILURE=true

# === BACKUP ===
BACKUP_DEFAULT_DESTINATION=/backup
BACKUP_COMPRESSION=zip
BACKUP_KEEP_LAST=10

# === LIMPEZA ===
CLEANER_DEFAULT_MAX_AGE_DAYS=30
CLEANER_USE_TRASH=true

# === MONITORAMENTO ===
MONITOR_CPU_THRESHOLD=80
MONITOR_MEMORY_THRESHOLD=90
MONITOR_DISK_THRESHOLD=85
MONITOR_INTERVAL_SECONDS=60
```

### Variáveis Importantes

#### Email (SMTP)

Para enviar notificações por email, configure:

=== "Gmail"

    ```bash
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=seu-email@gmail.com
    SMTP_PASSWORD=sua-senha-de-app  # Use App Password!
    SMTP_USE_TLS=true
    ```

    !!! warning "Gmail App Password"
        Use uma **Senha de App**, não sua senha normal.
        [Como criar App Password](https://support.google.com/accounts/answer/185833)

=== "Outlook"

    ```bash
    SMTP_HOST=smtp.office365.com
    SMTP_PORT=587
    SMTP_USER=seu-email@outlook.com
    SMTP_PASSWORD=sua-senha
    SMTP_USE_TLS=true
    ```

=== "Servidor Próprio"

    ```bash
    SMTP_HOST=mail.seudominio.com
    SMTP_PORT=465
    SMTP_USER=usuario
    SMTP_PASSWORD=senha
    SMTP_USE_TLS=false
    SMTP_USE_SSL=true
    ```

#### Níveis de Log

```bash
# Opções: DEBUG, INFO, WARNING, ERROR, CRITICAL
AUTOTAREFAS_LOG_LEVEL=INFO
```

| Nível | Descrição |
|-------|-----------|
| DEBUG | Tudo, incluindo detalhes de debug |
| INFO | Informações gerais (recomendado) |
| WARNING | Apenas avisos e erros |
| ERROR | Apenas erros |
| CRITICAL | Apenas erros críticos |

## Configuração JSON (autotarefas.json)

Para configurações mais complexas, use o arquivo JSON:

```json
{
  "version": "1.0.0",

  "logging": {
    "level": "INFO",
    "file": "logs/autotarefas.log",
    "max_size": "10MB",
    "backup_count": 5,
    "format": "json"
  },

  "backup": {
    "default_destination": "/backup",
    "compression": "zip",
    "compression_level": 6,
    "incremental": false,
    "verify": true,
    "exclude_patterns": [
      "*.tmp",
      "*.log",
      "__pycache__",
      ".git"
    ]
  },

  "cleaner": {
    "default_max_age_days": 30,
    "use_trash": true,
    "protected_patterns": [
      "*.important",
      "DO_NOT_DELETE*"
    ]
  },

  "monitor": {
    "cpu_threshold": 80,
    "memory_threshold": 90,
    "disk_threshold": 85,
    "interval_seconds": 60,
    "alert_cooldown_minutes": 15
  },

  "scheduler": {
    "timezone": "America/Sao_Paulo",
    "persist_jobs": true,
    "job_store": "jobs.json",
    "max_concurrent": 3
  },

  "email": {
    "templates_dir": "templates/email",
    "default_template": "notify.html"
  }
}
```

## Configuração via CLI

Você também pode configurar via linha de comando:

### Ver configuração atual

```bash
autotarefas config show
```

### Definir valor

```bash
autotarefas config set logging.level DEBUG
autotarefas config set backup.compression tar.gz
```

### Resetar para padrão

```bash
autotarefas config reset
```

## Configuração Programática

Via Python:

```python
from autotarefas.config import Config

# Carregar configuração
config = Config()

# Acessar valores
print(config.logging.level)
print(config.backup.compression)

# Modificar
config.monitor.cpu_threshold = 75
config.save()
```

## Configuração por Tarefa

Cada tarefa pode ter sua própria configuração:

### Backup

```python
from autotarefas.tasks import BackupTask

backup = BackupTask(
    source="/dados",
    destination="/backup",
    compress=True,
    compression_type="tar.gz",  # zip, tar.gz, tar.bz2
    compression_level=9,        # 1-9
    incremental=True,
    verify=True,
    exclude=["*.tmp", "*.log"],
    max_backups=10              # Manter últimos N backups
)
```

### Cleaner

```python
from autotarefas.tasks import CleanerTask

cleaner = CleanerTask(
    path="/temp",
    max_age_days=30,
    max_size_mb=100,            # Arquivos maiores que X MB
    patterns=["*.tmp", "*.log"],
    exclude=["important.log"],
    use_trash=True,             # Mover para lixeira
    recursive=True
)
```

### Monitor

```python
from autotarefas.tasks import MonitorTask

monitor = MonitorTask(
    cpu_threshold=80,
    memory_threshold=90,
    disk_threshold=85,
    disk_paths=["/", "/home"],
    network=True,
    processes=True,
    alert_callback=minha_funcao_alerta
)
```

## Variáveis de Ambiente de Sistema

O AutoTarefas também respeita variáveis de ambiente do sistema:

```bash
# Diretório de dados
export AUTOTAREFAS_DATA_DIR=/var/lib/autotarefas

# Diretório de logs
export AUTOTAREFAS_LOG_DIR=/var/log/autotarefas

# Arquivo de configuração alternativo
export AUTOTAREFAS_CONFIG=/etc/autotarefas/config.json
```

## Precedência de Configuração

A ordem de precedência (maior para menor):

1. **Argumentos CLI** - `--log-level DEBUG`
2. **Variáveis de ambiente** - `AUTOTAREFAS_LOG_LEVEL=DEBUG`
3. **Arquivo .env** - `AUTOTAREFAS_LOG_LEVEL=DEBUG`
4. **autotarefas.json** - `{"logging": {"level": "DEBUG"}}`
5. **Valores padrão** - Definidos no código

## Validação

Para validar sua configuração:

```bash
autotarefas config validate
```

Isso verifica:

- ✅ Sintaxe do JSON
- ✅ Tipos de valores
- ✅ Caminhos existentes
- ✅ Conexão SMTP (se configurado)

## Próximos Passos

- [Guia de Backup](guias/backup.md) - Configure backups avançados
- [Guia de Email](guias/email.md) - Configure notificações
- [Referência da API](api/index.md) - Todas as opções de configuração
