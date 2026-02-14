# Início Rápido

Aprenda a usar o AutoTarefas em 5 minutos! 🚀

## Pré-requisitos

Certifique-se de ter o AutoTarefas instalado:

```bash
pip install autotarefas
```

## 1. Inicialização

O primeiro passo é inicializar o AutoTarefas no seu diretório de trabalho:

```bash
autotarefas init
```

Isso cria:

- `.env` - Arquivo de configuração com variáveis de ambiente
- `autotarefas.json` - Configurações do projeto
- `logs/` - Pasta para arquivos de log

!!! success "Pronto!"
    O AutoTarefas está configurado e pronto para uso.

## 2. Verificar Status do Sistema

Veja o estado atual do seu sistema:

```bash
autotarefas monitor status
```

Saída esperada:

```
╭─────────────────────────────────────╮
│       Status do Sistema             │
├─────────────────────────────────────┤
│ CPU:      23.5%  ████░░░░░░         │
│ Memória:  67.2%  ███████░░░         │
│ Disco:    45.0%  █████░░░░░         │
╰─────────────────────────────────────╯
```

## 3. Fazer um Backup

### Backup simples

```bash
autotarefas backup run ./meus-documentos --destino ./backups
```

### Backup com compressão

```bash
autotarefas backup run ./meus-documentos --destino ./backups --comprimir
```

### Listar backups existentes

```bash
autotarefas backup list ./backups
```

## 4. Limpar Arquivos Antigos

### Preview (ver o que seria deletado)

```bash
autotarefas clean preview ./temp --dias 30
```

### Executar limpeza

```bash
autotarefas clean run ./temp --dias 30
```

!!! warning "Atenção"
    Sempre use `preview` primeiro para verificar o que será deletado!

## 5. Agendar Tarefas

### Agendar backup diário às 2h

```bash
autotarefas schedule add backup \
    --cron "0 2 * * *" \
    --origem ./documentos \
    --destino ./backups
```

### Listar tarefas agendadas

```bash
autotarefas schedule list
```

### Executar o agendador

```bash
autotarefas schedule run
```

!!! tip "Dica"
    Use `--daemon` para executar em segundo plano:
    ```bash
    autotarefas schedule run --daemon
    ```

## 6. Monitoramento Contínuo

### Monitorar com alertas

```bash
autotarefas monitor watch --cpu 80 --memoria 90
```

Isso monitora continuamente e alerta quando:

- CPU ultrapassar 80%
- Memória ultrapassar 90%

### Ver histórico

```bash
autotarefas monitor history --ultimas 24h
```

## Exemplo Completo

Aqui está um fluxo de trabalho típico:

```bash
# 1. Inicializar
autotarefas init

# 2. Configurar backup automático diário
autotarefas schedule add backup \
    --cron "0 2 * * *" \
    --origem ~/documentos \
    --destino ~/backups \
    --comprimir

# 3. Configurar limpeza semanal de temporários
autotarefas schedule add clean \
    --cron "0 3 * * 0" \
    --caminho ~/Downloads \
    --dias 30

# 4. Configurar monitoramento
autotarefas schedule add monitor \
    --intervalo 5m \
    --cpu 80 \
    --memoria 90

# 5. Iniciar agendador
autotarefas schedule run --daemon
```

## Usando via Python

Você também pode usar o AutoTarefas como biblioteca:

```python
from autotarefas.tasks import BackupTask, CleanerTask, MonitorTask

# Backup
backup = BackupTask(
    source="./documentos",
    destination="./backups",
    compress=True
)
result = backup.run()
print(f"✓ {result.message}")

# Limpeza
cleaner = CleanerTask(
    path="./temp",
    max_age_days=30
)
result = cleaner.run()
print(f"✓ Removidos: {result.data['deleted_count']} arquivos")

# Monitoramento
monitor = MonitorTask()
result = monitor.run()
print(f"CPU: {result.data['cpu']}%")
print(f"Memória: {result.data['memory']}%")
```

## Próximos Passos

Agora que você conhece o básico:

<div class="grid cards" markdown>

-   :material-cog:{ .lg .middle } **Configuração**

    ---

    Personalize o AutoTarefas para suas necessidades.

    [:octicons-arrow-right-24: Configuração](configuracao.md)

-   :material-book-open-variant:{ .lg .middle } **Guias**

    ---

    Guias detalhados de cada funcionalidade.

    [:octicons-arrow-right-24: Guias](guias/index.md)

-   :material-api:{ .lg .middle } **API**

    ---

    Referência completa da API Python.

    [:octicons-arrow-right-24: API](api/index.md)

</div>

## Precisa de Ajuda?

- 📖 [Documentação completa](index.md)
- 🐛 [Reportar bug](https://github.com/paulor007/autotarefas/issues)
- 💬 [Discussões](https://github.com/paulor007/autotarefas/discussions)
