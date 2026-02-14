# Limpeza de Arquivos

O módulo Cleaner permite limpar arquivos antigos, temporários ou desnecessários de forma segura e automatizada.

## Início Rápido

```bash
# Ver o que seria deletado (preview)
autotarefas clean preview ./Downloads --dias 30

# Executar limpeza
autotarefas clean run ./Downloads --dias 30

# Ver estatísticas de uso
autotarefas clean stats ./Downloads
```

## Comandos CLI

### `clean preview`

Mostra o que seria deletado **sem remover nada**. Sempre use antes de `run`.

```bash
autotarefas clean preview <DIRETÓRIO> [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--dias`, `-d` | Idade mínima em dias | `30` |
| `--tamanho`, `-s` | Tamanho mínimo (ex: `10MB`) | `None` |
| `--padrao`, `-p` | Padrão de arquivo (pode repetir) | `["*"]` |
| `--recursivo`, `-r` | Incluir subpastas | `True` |

**Exemplos:**

```bash
# Arquivos com mais de 30 dias
autotarefas clean preview ~/Downloads --dias 30

# Arquivos maiores que 100MB
autotarefas clean preview ~/Videos --tamanho 100MB

# Apenas arquivos .tmp e .log
autotarefas clean preview ~/Temp --padrao "*.tmp" --padrao "*.log"

# Combinar filtros
autotarefas clean preview ~/Downloads --dias 7 --tamanho 50MB
```

### `clean run`

Executa a limpeza de arquivos.

```bash
autotarefas clean run <DIRETÓRIO> [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--dias`, `-d` | Idade mínima em dias | `30` |
| `--tamanho`, `-s` | Tamanho mínimo | `None` |
| `--padrao`, `-p` | Padrão de arquivo | `["*"]` |
| `--lixeira` | Mover para lixeira ao invés de deletar | `True` |
| `--forcar`, `-f` | Deletar permanentemente | `False` |
| `--recursivo`, `-r` | Incluir subpastas | `True` |

**Exemplos:**

```bash
# Limpeza padrão (move para lixeira)
autotarefas clean run ~/Downloads --dias 30

# Deletar permanentemente
autotarefas clean run ~/Temp --dias 7 --forcar

# Limpar apenas logs antigos
autotarefas clean run ~/logs --padrao "*.log" --dias 14
```

!!! warning "Atenção"
    Sempre execute `preview` antes de `run` para verificar o que será removido!

### `clean stats`

Mostra estatísticas de uso de disco de um diretório.

```bash
autotarefas clean stats <DIRETÓRIO> [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--por-tipo` | Agrupar por extensão | `False` |
| `--por-idade` | Agrupar por idade | `False` |

**Exemplo:**

```bash
autotarefas clean stats ~/Downloads --por-tipo
```

Saída:
```
╭─────────────────────────────────────────────────────────╮
│              Estatísticas: ~/Downloads                   │
├──────────────────────────────────────────────────────────┤
│ Total de arquivos: 1,234                                 │
│ Tamanho total: 15.7 GB                                   │
├──────────────────────────────────────────────────────────┤
│ Por tipo:                                                │
│   .zip    → 5.2 GB  (324 arquivos)                      │
│   .pdf    → 3.1 GB  (456 arquivos)                      │
│   .exe    → 2.8 GB  (89 arquivos)                       │
│   .tmp    → 1.5 GB  (234 arquivos)                      │
│   outros  → 3.1 GB  (131 arquivos)                      │
╰──────────────────────────────────────────────────────────╯
```

## Uso via Python

### Limpeza Básica

```python
from autotarefas.tasks import CleanerTask

cleaner = CleanerTask(
    path="/home/user/Downloads",
    max_age_days=30
)

result = cleaner.run()

if result.success:
    print(f"✓ Limpeza concluída")
    print(f"  Arquivos removidos: {result.data['deleted_count']}")
    print(f"  Espaço liberado: {result.data['freed_space']}")
```

### Filtros Avançados

```python
from autotarefas.tasks import CleanerTask

cleaner = CleanerTask(
    path="/home/user/temp",
    max_age_days=7,
    max_size_mb=100,        # Arquivos maiores que 100MB
    patterns=["*.tmp", "*.log", "*.bak"],
    recursive=True
)

result = cleaner.run()
```

### Proteção de Arquivos

Use `exclude` para proteger arquivos importantes de serem deletados:

```python
from autotarefas.tasks import CleanerTask

cleaner = CleanerTask(
    path="/home/user/Downloads",
    max_age_days=30,
    exclude=[
        "importante.pdf",      # Arquivo específico
        "*.docx",              # Todos os .docx
        "projetos/*",          # Pasta inteira
        "DO_NOT_DELETE*"       # Padrão de nome
    ]
)

result = cleaner.run()
```

### Modo Preview (Dry Run)

```python
from autotarefas.tasks import CleanerTask

cleaner = CleanerTask(
    path="/home/user/Downloads",
    max_age_days=30,
    dry_run=True  # Não deleta nada
)

result = cleaner.run()

print("Arquivos que SERIAM deletados:")
for file in result.data['files_to_delete']:
    print(f"  - {file['path']} ({file['size']})")

print(f"\nTotal: {result.data['total_count']} arquivos")
print(f"Espaço que seria liberado: {result.data['total_size']}")
```

### Usar Lixeira do Sistema

```python
from autotarefas.tasks import CleanerTask

cleaner = CleanerTask(
    path="/home/user/Downloads",
    max_age_days=30,
    use_trash=True  # Move para lixeira ao invés de deletar
)

result = cleaner.run()
print(f"Arquivos movidos para lixeira: {result.data['deleted_count']}")
```

### Callbacks de Progresso

```python
from autotarefas.tasks import CleanerTask

def on_file_deleted(filepath, size):
    print(f"Removido: {filepath} ({size})")

def on_complete(result):
    print(f"\n✓ Limpeza finalizada!")
    print(f"  {result.data['deleted_count']} arquivos removidos")

cleaner = CleanerTask(
    path="/temp",
    max_age_days=7,
    on_file_deleted=on_file_deleted,
    on_success=on_complete
)

cleaner.run()
```

## Agendamento

### Limpeza Semanal de Downloads

```bash
autotarefas schedule add clean \
    --cron "0 4 * * 0" \
    --caminho ~/Downloads \
    --dias 30
```

### Limpeza Diária de Temporários

```bash
autotarefas schedule add clean \
    --cron "0 5 * * *" \
    --caminho ~/Temp \
    --dias 7 \
    --forcar
```

### Via Python

```python
from autotarefas.core import TaskScheduler
from autotarefas.tasks import CleanerTask

scheduler = TaskScheduler()

# Limpar Downloads semanalmente
cleaner_downloads = CleanerTask(
    path="/home/user/Downloads",
    max_age_days=30,
    use_trash=True
)
scheduler.add_cron(cleaner_downloads, "0 4 * * 0", name="limpar_downloads")

# Limpar Temp diariamente
cleaner_temp = CleanerTask(
    path="/home/user/temp",
    max_age_days=1,
    use_trash=False
)
scheduler.add_cron(cleaner_temp, "0 5 * * *", name="limpar_temp")

scheduler.run()
```

## Configuração

### Variáveis de Ambiente

```bash
# .env
CLEANER_DEFAULT_MAX_AGE_DAYS=30
CLEANER_USE_TRASH=true
CLEANER_DEFAULT_PATTERNS=*.tmp,*.log,*.bak
```

### Arquivo de Configuração

```json
{
  "cleaner": {
    "default_max_age_days": 30,
    "use_trash": true,
    "protected_patterns": [
      "*.important",
      "DO_NOT_DELETE*",
      ".gitkeep"
    ],
    "default_exclude_dirs": [
      ".git",
      "node_modules",
      "__pycache__"
    ]
  }
}
```

## Casos de Uso Comuns

### 1. Limpar Downloads Antigos

```bash
# Preview primeiro
autotarefas clean preview ~/Downloads --dias 30

# Se ok, executar
autotarefas clean run ~/Downloads --dias 30
```

### 2. Limpar Cache de Navegador

```bash
# Chrome
autotarefas clean run ~/.cache/google-chrome --dias 7

# Firefox
autotarefas clean run ~/.cache/mozilla --dias 7
```

### 3. Limpar Logs de Sistema

```bash
autotarefas clean run /var/log --padrao "*.log" --dias 14 --forcar
```

### 4. Limpar Arquivos Grandes

```bash
# Encontrar e remover arquivos > 500MB com mais de 7 dias
autotarefas clean run ~/Videos --tamanho 500MB --dias 7
```

### 5. Limpar Projetos de Desenvolvimento

```python
from autotarefas.tasks import CleanerTask

# Limpar artefatos de build
cleaner = CleanerTask(
    path="/projetos",
    patterns=[
        "__pycache__",
        "*.pyc",
        ".pytest_cache",
        "node_modules",
        "dist",
        "build",
        "*.egg-info"
    ],
    max_age_days=0,  # Qualquer idade
    recursive=True
)

result = cleaner.run()
print(f"Espaço liberado: {result.data['freed_space']}")
```

## Filtros Disponíveis

### Por Idade

| Opção | Descrição |
|-------|-----------|
| `--dias 0` | Todos os arquivos |
| `--dias 7` | Mais de 1 semana |
| `--dias 30` | Mais de 1 mês |
| `--dias 365` | Mais de 1 ano |

### Por Tamanho

| Opção | Descrição |
|-------|-----------|
| `--tamanho 1KB` | Maior que 1 KB |
| `--tamanho 1MB` | Maior que 1 MB |
| `--tamanho 100MB` | Maior que 100 MB |
| `--tamanho 1GB` | Maior que 1 GB |

### Por Padrão (Glob)

| Padrão | Descrição |
|--------|-----------|
| `*.tmp` | Arquivos .tmp |
| `*.log` | Arquivos de log |
| `temp_*` | Começa com "temp_" |
| `*backup*` | Contém "backup" |
| `**/*.pyc` | Recursivo .pyc |

## Boas Práticas

!!! tip "Dicas de Segurança"
    1. **Sempre use preview** antes de executar
    2. **Use a lixeira** para arquivos pessoais
    3. **Proteja arquivos importantes** com `exclude`
    4. **Teste com `dry_run=True`** em scripts
    5. **Configure notificações** para limpezas automáticas

!!! danger "Cuidado"
    - `--forcar` deleta permanentemente
    - Limpeza de `/` ou `~` pode causar problemas
    - Sempre verifique o caminho antes de executar

## Troubleshooting

### Erro: "Arquivo em uso"

Alguns arquivos podem estar sendo usados por outros programas:

```bash
# Ver quem está usando o arquivo
lsof /caminho/do/arquivo

# Tentar novamente após fechar o programa
```

### Erro: "Permissão negada"

```bash
# Verificar permissões
ls -la /caminho/do/diretorio

# Executar com sudo (cuidado!)
sudo autotarefas clean run /var/log --dias 30
```

### Lixeira cheia

```bash
# Ver tamanho da lixeira
du -sh ~/.local/share/Trash

# Esvaziar lixeira
rm -rf ~/.local/share/Trash/*
```

## Próximos Passos

- [Monitorar espaço em disco](monitor.md)
- [Agendar limpezas automáticas](scheduler.md)
- [Receber alertas por email](email.md)
