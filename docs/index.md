# AutoTarefas

<div align="center">
  <h2>🤖 Sistema de Automação de Tarefas</h2>
  <p><strong>Automatize tarefas repetitivas do seu computador com facilidade</strong></p>
</div>

---

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Coverage](https://img.shields.io/badge/Coverage-93%25-brightgreen.svg)]()

## O que é o AutoTarefas?

O **AutoTarefas** é um sistema completo para automação de tarefas repetitivas do computador, desenvolvido em Python. Com ele, você pode:

- 📦 **Fazer backups** automáticos de arquivos e pastas
- 🧹 **Limpar arquivos** antigos ou desnecessários
- 📊 **Monitorar** CPU, memória e disco
- ⏰ **Agendar** tarefas para execução automática
- 📧 **Receber notificações** por email

## Início Rápido

### Instalação

```bash
pip install autotarefas
```

### Primeiro uso

```bash
# Inicializar o projeto
autotarefas init

# Ver status do sistema
autotarefas monitor status

# Fazer um backup
autotarefas backup run ./meus-arquivos --destino ./backups
```

!!! tip "Dica"
    Execute `autotarefas --help` para ver todos os comandos disponíveis.

## Funcionalidades

<div class="grid cards" markdown>

-   :material-backup-restore:{ .lg .middle } **Backup**

    ---

    Backup automático com compressão ZIP ou TAR.GZ, modo incremental e verificação de integridade.

    [:octicons-arrow-right-24: Guia de Backup](guias/backup.md)

-   :material-broom:{ .lg .middle } **Limpeza**

    ---

    Limpeza inteligente de arquivos por idade, tamanho ou padrão, com modo preview e proteção.

    [:octicons-arrow-right-24: Guia de Limpeza](guias/cleaner.md)

-   :material-monitor-dashboard:{ .lg .middle } **Monitoramento**

    ---

    Monitoramento de CPU, memória, disco e rede com alertas configuráveis.

    [:octicons-arrow-right-24: Guia de Monitoramento](guias/monitor.md)

-   :material-clock-outline:{ .lg .middle } **Agendamento**

    ---

    Agende tarefas com expressões cron ou intervalos simples, com persistência.

    [:octicons-arrow-right-24: Guia de Agendamento](guias/scheduler.md)

</div>

## Exemplo de Uso

=== "Backup"

    ```python
    from autotarefas.tasks import BackupTask

    # Criar tarefa de backup
    backup = BackupTask(
        source="/home/user/documentos",
        destination="/backup",
        compress=True
    )

    # Executar
    result = backup.run()
    print(f"Backup concluído: {result.message}")
    ```

=== "Monitoramento"

    ```python
    from autotarefas.tasks import MonitorTask

    # Criar tarefa de monitoramento
    monitor = MonitorTask(
        cpu_threshold=80,
        memory_threshold=90
    )

    # Executar
    result = monitor.run()
    print(f"CPU: {result.data['cpu']}%")
    print(f"Memória: {result.data['memory']}%")
    ```

=== "CLI"

    ```bash
    # Backup via CLI
    autotarefas backup run ./docs --destino ./backup --comprimir

    # Monitoramento via CLI
    autotarefas monitor status

    # Agendar tarefa
    autotarefas schedule add backup --cron "0 2 * * *"
    ```

## Requisitos

- **Python**: 3.12 ou superior
- **Sistema Operacional**: Linux, macOS ou Windows
- **Dependências**: Instaladas automaticamente via pip

## Links Úteis

- [Instalação Completa](instalacao.md)
- [Início Rápido](quickstart.md)
- [Referência da API](api/index.md)
- [Contribuir](desenvolvimento/contribuindo.md)
- [Changelog](desenvolvimento/changelog.md)

## Licença

Este projeto está licenciado sob a [Licença MIT](https://opensource.org/licenses/MIT).
