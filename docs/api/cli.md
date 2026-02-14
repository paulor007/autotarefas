# CLI

Interface de linha de comando do AutoTarefas.

## Visão Geral

```bash
autotarefas [COMANDO] [SUBCOMANDO] [OPÇÕES]
```

## Comandos Disponíveis

| Comando | Descrição |
|---------|-----------|
| `init` | Inicializar projeto |
| `backup` | Gerenciar backups |
| `clean` | Limpar arquivos |
| `monitor` | Monitorar sistema |
| `schedule` | Agendar tarefas |
| `email` | Gerenciar emails |
| `report` | Gerar relatórios |
| `config` | Configurações |

---

## init

Inicializa o AutoTarefas no diretório atual.

```bash
autotarefas init [OPÇÕES]
```

| Opção | Descrição |
|-------|-----------|
| `--force` | Sobrescrever arquivos existentes |
| `--minimal` | Configuração mínima |

**Arquivos criados:**
- `.env` - Variáveis de ambiente
- `autotarefas.json` - Configurações
- `logs/` - Diretório de logs

---

## backup

### backup run

```bash
autotarefas backup run <ORIGEM> -d <DESTINO> [OPÇÕES]
```

| Opção | Descrição |
|-------|-----------|
| `-d, --destino` | Pasta de destino |
| `-c, --comprimir` | Ativar compressão |
| `-f, --formato` | `zip` ou `tar.gz` |
| `-i, --incremental` | Modo incremental |
| `--excluir` | Padrões a excluir |

### backup list

```bash
autotarefas backup list <DIRETÓRIO> [--detalhes]
```

### backup restore

```bash
autotarefas backup restore <ARQUIVO> -d <DESTINO>
```

### backup clean

```bash
autotarefas backup clean <DIRETÓRIO> --manter 5
```

---

## clean

### clean preview

```bash
autotarefas clean preview <DIRETÓRIO> [OPÇÕES]
```

| Opção | Descrição |
|-------|-----------|
| `-d, --dias` | Idade mínima em dias |
| `-s, --tamanho` | Tamanho mínimo (ex: `10MB`) |
| `-p, --padrao` | Padrão de arquivo |

### clean run

```bash
autotarefas clean run <DIRETÓRIO> [OPÇÕES]
```

| Opção | Descrição |
|-------|-----------|
| `--lixeira` | Usar lixeira do sistema |
| `--forcar` | Deletar permanentemente |

### clean stats

```bash
autotarefas clean stats <DIRETÓRIO> [--por-tipo]
```

---

## monitor

### monitor status

```bash
autotarefas monitor status [--json] [--detalhes]
```

### monitor watch

```bash
autotarefas monitor watch [OPÇÕES]
```

| Opção | Descrição |
|-------|-----------|
| `-i, --intervalo` | Segundos entre verificações |
| `--cpu` | Limite de CPU % |
| `--memoria` | Limite de memória % |
| `--disco` | Limite de disco % |
| `--notificar` | Enviar email em alertas |

### monitor history

```bash
autotarefas monitor history --ultimas 24h
```

### monitor processes

```bash
autotarefas monitor processes -n 10 --ordenar cpu
```

---

## schedule

### schedule add

```bash
autotarefas schedule add <TIPO> [OPÇÕES]
```

Tipos: `backup`, `clean`, `monitor`, `report`

| Opção | Descrição |
|-------|-----------|
| `--cron` | Expressão cron |
| `--intervalo` | Intervalo (ex: `5m`, `1h`) |
| `--nome` | Nome da tarefa |

**Exemplos:**

```bash
# Backup diário às 2h
autotarefas schedule add backup --cron "0 2 * * *" \
    --origem ~/Docs --destino ~/Backup --nome backup_diario

# Monitor a cada 5 minutos
autotarefas schedule add monitor --intervalo 5m --cpu 80
```

### schedule list

```bash
autotarefas schedule list [--detalhes]
```

### schedule remove

```bash
autotarefas schedule remove <NOME>
```

### schedule run

```bash
autotarefas schedule run [--daemon]
```

### schedule history

```bash
autotarefas schedule history --nome <NOME> --ultimas 7d
```

---

## email

### email test

```bash
autotarefas email test [--para email@exemplo.com]
```

### email send

```bash
autotarefas email send -t <DESTINO> -s <ASSUNTO> -m <MENSAGEM>
```

| Opção | Descrição |
|-------|-----------|
| `-t, --para` | Destinatário |
| `-s, --assunto` | Assunto |
| `-m, --mensagem` | Corpo |
| `--html` | Enviar como HTML |
| `-a, --anexo` | Arquivo anexo |

### email templates

```bash
autotarefas email templates
```

---

## report

### report generate

```bash
autotarefas report generate <TIPO> [OPÇÕES]
```

| Opção | Descrição |
|-------|-----------|
| `--formato` | `xlsx`, `csv`, `html` |
| `--periodo` | `daily`, `weekly`, `monthly` |
| `--saida` | Pasta de saída |

### report templates

```bash
autotarefas report templates
```

---

## config

### config show

```bash
autotarefas config show [CHAVE]
```

### config set

```bash
autotarefas config set <CHAVE> <VALOR>
```

### config reset

```bash
autotarefas config reset
```

### config validate

```bash
autotarefas config validate
```

---

## Opções Globais

| Opção | Descrição |
|-------|-----------|
| `--version` | Mostrar versão |
| `--help` | Mostrar ajuda |
| `--verbose, -v` | Modo verboso |
| `--quiet, -q` | Modo silencioso |
| `--config` | Arquivo de configuração |

---

## Exemplos Completos

```bash
# Fluxo completo de setup
autotarefas init
autotarefas email test
autotarefas monitor status

# Backup com agendamento
autotarefas backup run ~/Docs -d ~/Backup -c
autotarefas schedule add backup --cron "0 2 * * *" \
    --origem ~/Docs --destino ~/Backup

# Limpeza segura
autotarefas clean preview ~/Downloads --dias 30
autotarefas clean run ~/Downloads --dias 30

# Monitoramento contínuo
autotarefas monitor watch --cpu 80 --memoria 90 --notificar

# Iniciar agendador como serviço
autotarefas schedule run --daemon
```
