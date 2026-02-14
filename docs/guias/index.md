# Guias

Guias detalhados para cada funcionalidade do AutoTarefas.

## Disponíveis

<div class="grid cards" markdown>

-   :material-backup-restore:{ .lg .middle } **[Backup](backup.md)**

    ---

    Backup automático de arquivos e pastas com compressão, modo incremental e verificação.

-   :material-broom:{ .lg .middle } **[Limpeza](cleaner.md)**

    ---

    Limpeza inteligente de arquivos por idade, tamanho ou padrão.

-   :material-monitor-dashboard:{ .lg .middle } **[Monitoramento](monitor.md)**

    ---

    Monitoramento de CPU, memória, disco e rede com alertas.

-   :material-clock-outline:{ .lg .middle } **[Agendamento](scheduler.md)**

    ---

    Agende tarefas com expressões cron ou intervalos.

-   :material-email:{ .lg .middle } **[Email](email.md)**

    ---

    Configure notificações por email para suas tarefas.

</div>

## Guia Rápido por Caso de Uso

### Quero fazer backup dos meus documentos

→ [Guia de Backup](backup.md)

```bash
autotarefas backup run ~/Documentos --destino ~/Backups --comprimir
```

### Quero limpar arquivos antigos

→ [Guia de Limpeza](cleaner.md)

```bash
autotarefas clean run ~/Downloads --dias 30
```

### Quero monitorar meu servidor

→ [Guia de Monitoramento](monitor.md)

```bash
autotarefas monitor watch --cpu 80 --memoria 90
```

### Quero agendar tarefas automáticas

→ [Guia de Agendamento](scheduler.md)

```bash
autotarefas schedule add backup --cron "0 2 * * *"
```

### Quero receber alertas por email

→ [Guia de Email](email.md)

```bash
autotarefas email test
```
