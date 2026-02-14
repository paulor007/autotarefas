# Backup

O módulo de backup permite criar cópias de segurança automáticas dos seus arquivos com compressão, verificação de integridade e modo incremental.

## Início Rápido

```bash
# Backup simples
autotarefas backup run ./meus-arquivos --destino ./backups

# Backup com compressão
autotarefas backup run ./meus-arquivos --destino ./backups --comprimir

# Listar backups existentes
autotarefas backup list ./backups
```

## Comandos CLI

### `backup run`

Executa um backup manual.

```bash
autotarefas backup run <ORIGEM> --destino <DESTINO> [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--destino`, `-d` | Pasta de destino do backup | Obrigatório |
| `--comprimir`, `-c` | Ativar compressão | `False` |
| `--formato`, `-f` | Formato: `zip` ou `tar.gz` | `zip` |
| `--incremental`, `-i` | Backup incremental | `False` |
| `--verificar` | Verificar integridade após backup | `True` |
| `--excluir` | Padrões para excluir (pode repetir) | `[]` |

**Exemplos:**

```bash
# Backup completo com compressão ZIP
autotarefas backup run ~/Documentos -d ~/Backups -c

# Backup incremental (só arquivos alterados)
autotarefas backup run ~/Projetos -d ~/Backups -i

# Backup excluindo arquivos temporários
autotarefas backup run ~/Codigo -d ~/Backups --excluir "*.pyc" --excluir "__pycache__"

# Backup em TAR.GZ
autotarefas backup run ~/Dados -d ~/Backups -c -f tar.gz
```

### `backup list`

Lista backups existentes em um diretório.

```bash
autotarefas backup list <DIRETÓRIO> [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--detalhes`, `-v` | Mostrar detalhes (tamanho, data) | `False` |
| `--limite`, `-n` | Número máximo de resultados | `10` |

**Exemplo:**

```bash
autotarefas backup list ~/Backups --detalhes
```

Saída:
```
╭─────────────────────────────────────────────────────────╮
│                    Backups Encontrados                   │
├──────────────────────┬──────────┬───────────────────────┤
│ Arquivo              │ Tamanho  │ Data                  │
├──────────────────────┼──────────┼───────────────────────┤
│ backup_20250212.zip  │ 45.2 MB  │ 2025-02-12 14:30:00   │
│ backup_20250211.zip  │ 44.8 MB  │ 2025-02-11 14:30:00   │
│ backup_20250210.zip  │ 43.1 MB  │ 2025-02-10 14:30:00   │
╰──────────────────────┴──────────┴───────────────────────╯
```

### `backup restore`

Restaura um backup.

```bash
autotarefas backup restore <ARQUIVO> --destino <DESTINO> [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--destino`, `-d` | Pasta de destino da restauração | Obrigatório |
| `--sobrescrever` | Sobrescrever arquivos existentes | `False` |

**Exemplo:**

```bash
autotarefas backup restore ~/Backups/backup_20250212.zip -d ~/Restaurado
```

### `backup clean`

Remove backups antigos mantendo apenas os N mais recentes.

```bash
autotarefas backup clean <DIRETÓRIO> [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--manter`, `-k` | Quantidade de backups a manter | `5` |
| `--preview` | Apenas mostrar o que seria removido | `False` |

**Exemplo:**

```bash
# Ver o que seria removido
autotarefas backup clean ~/Backups --manter 3 --preview

# Executar limpeza
autotarefas backup clean ~/Backups --manter 3
```

## Uso via Python

### Backup Básico

```python
from autotarefas.tasks import BackupTask

# Criar tarefa
backup = BackupTask(
    source="/home/user/documentos",
    destination="/backup"
)

# Executar
result = backup.run()

if result.success:
    print(f"✓ Backup concluído: {result.data['backup_file']}")
    print(f"  Arquivos: {result.data['files_count']}")
    print(f"  Tamanho: {result.data['total_size']}")
else:
    print(f"✗ Erro: {result.message}")
```

### Backup com Compressão

```python
from autotarefas.tasks import BackupTask

backup = BackupTask(
    source="/home/user/projetos",
    destination="/backup",
    compress=True,
    compression_type="zip",  # ou "tar.gz"
    compression_level=6      # 1-9 (9 = máxima compressão)
)

result = backup.run()
```

### Backup Incremental

O backup incremental só copia arquivos que foram modificados desde o último backup.

```python
from autotarefas.tasks import BackupTask

backup = BackupTask(
    source="/home/user/codigo",
    destination="/backup",
    incremental=True,
    compress=True
)

result = backup.run()
print(f"Arquivos novos/modificados: {result.data['incremental_count']}")
```

### Excluindo Arquivos

```python
from autotarefas.tasks import BackupTask

backup = BackupTask(
    source="/home/user/projeto",
    destination="/backup",
    exclude=[
        "*.pyc",
        "__pycache__",
        ".git",
        "node_modules",
        "*.log",
        ".env"
    ]
)

result = backup.run()
```

### Verificação de Integridade

```python
from autotarefas.tasks import BackupTask

backup = BackupTask(
    source="/dados/importantes",
    destination="/backup",
    compress=True,
    verify=True  # Verifica após criar
)

result = backup.run()

if result.data.get('verified'):
    print("✓ Integridade verificada com sucesso")
```

### Callbacks de Progresso

```python
from autotarefas.tasks import BackupTask

def on_progress(current, total, filename):
    percent = (current / total) * 100
    print(f"[{percent:.1f}%] {filename}")

def on_complete(result):
    print(f"Backup finalizado: {result.data['backup_file']}")

backup = BackupTask(
    source="/dados",
    destination="/backup",
    on_progress=on_progress,
    on_success=on_complete
)

backup.run()
```

## Agendamento

### Backup Diário às 2h da manhã

```bash
autotarefas schedule add backup \
    --cron "0 2 * * *" \
    --origem ~/Documentos \
    --destino ~/Backups \
    --comprimir
```

### Backup Semanal aos Domingos

```bash
autotarefas schedule add backup \
    --cron "0 3 * * 0" \
    --origem ~/Projetos \
    --destino ~/Backups \
    --incremental
```

### Via Python

```python
from autotarefas.core import TaskScheduler
from autotarefas.tasks import BackupTask

scheduler = TaskScheduler()

backup = BackupTask(
    source="/dados",
    destination="/backup",
    compress=True
)

# Agendar para 2h da manhã todos os dias
scheduler.add_cron(backup, "0 2 * * *", name="backup_diario")

# Iniciar agendador
scheduler.run()
```

## Configuração

### Variáveis de Ambiente

```bash
# .env
BACKUP_DEFAULT_DESTINATION=/backup
BACKUP_COMPRESSION=zip
BACKUP_COMPRESSION_LEVEL=6
BACKUP_KEEP_LAST=10
BACKUP_VERIFY=true
```

### Arquivo de Configuração

```json
{
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
    ],
    "keep_last": 10
  }
}
```

## Boas Práticas

!!! tip "Dicas"
    1. **Sempre verifique** - Use `--verificar` para garantir integridade
    2. **Use incremental** para backups frequentes - Economiza espaço e tempo
    3. **Exclua arquivos desnecessários** - `.git`, `node_modules`, `__pycache__`
    4. **Mantenha múltiplas cópias** - Use `backup clean --manter 5`
    5. **Teste a restauração** periodicamente

!!! warning "Atenção"
    - Backups incrementais dependem do backup base
    - Não armazene backups no mesmo disco dos dados originais
    - Configure notificações por email para falhas

## Formatos Suportados

| Formato | Extensão | Vantagens | Desvantagens |
|---------|----------|-----------|--------------|
| ZIP | `.zip` | Universal, suporte nativo | Compressão moderada |
| TAR.GZ | `.tar.gz` | Melhor compressão, preserva permissões | Menos universal |
| TAR.BZ2 | `.tar.bz2` | Máxima compressão | Mais lento |

## Troubleshooting

### Erro: "Permissão negada"

```bash
# Verificar permissões da pasta de destino
ls -la /backup

# Ajustar permissões se necessário
chmod 755 /backup
```

### Erro: "Disco cheio"

```bash
# Verificar espaço disponível
df -h /backup

# Limpar backups antigos
autotarefas backup clean /backup --manter 3
```

### Backup muito lento

- Use compressão nível 1-3 para mais velocidade
- Exclua arquivos grandes desnecessários
- Considere backup incremental

## Próximos Passos

- [Agendar backups automáticos](scheduler.md)
- [Configurar notificações](email.md)
- [Monitorar espaço em disco](monitor.md)
