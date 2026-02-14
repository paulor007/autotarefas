"""
Comandos CLI do AutoTarefas.

Este pacote contém todos os comandos disponíveis:
    - init: Inicialização e configuração
    - backup: Backup e restauração
    - cleaner: Limpeza de arquivos
    - monitor: Monitoramento do sistema
    - reporter: Geração de relatórios
    - scheduler: Agendamento de tarefas (Fase 5.2)

Comandos futuros (outras fases):
    - email: Notificações por email (Fase 6)
    - organizer: Organização de arquivos (Fase 8)
"""

from autotarefas.cli.commands import backup, cleaner, init, monitor, reporter, scheduler

__all__ = [
    "init",
    "backup",
    "cleaner",
    "monitor",
    "reporter",
    "scheduler",
    "email",
]
