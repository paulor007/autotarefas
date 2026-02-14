"""
Módulo de Tasks do AutoTarefas.

Contém todas as tasks de automação disponíveis:
    - BackupTask: Backup de arquivos e diretórios
    - RestoreTask: Restauração de backups
    - CleanerTask: Limpeza de arquivos temporários
    - OrganizerTask: Organização de arquivos por tipo
    - MonitorTask: Monitoramento do sistema
    - ReporterTask: Geração de relatórios
    - SalesReportTask: Relatório de vendas

Uso:
    from autotarefas.tasks import BackupTask, CleanerTask, OrganizerTask

    backup = BackupTask()
    result = backup.run(source="/home/user/docs", dest="/backups")
"""

# Backup
from autotarefas.tasks.backup import (
    BackupManager,
    BackupTask,
    CompressionType,
    RestoreTask,
)

# Cleaner
from autotarefas.tasks.cleaner import CleanerTask, CleaningProfile, CleaningProfiles

# Monitor
from autotarefas.tasks.monitor import MonitorTask

# Organizer
from autotarefas.tasks.organizer import (
    ConflictStrategy,
    FileCategory,
    OrganizeProfile,
    OrganizerTask,
)

# Reporter
from autotarefas.tasks.reporter import ReporterTask, ReportFormat

# Sales Report
from autotarefas.tasks.sales_report import SalesData, SalesReportTask

__all__ = [
    # Backup
    "BackupTask",
    "RestoreTask",
    "BackupManager",
    "CompressionType",
    # Cleaner
    "CleanerTask",
    "CleaningProfile",
    "CleaningProfiles",
    # Organizer
    "OrganizerTask",
    "OrganizeProfile",
    "ConflictStrategy",
    "FileCategory",
    # Monitor
    "MonitorTask",
    # Reporter
    "ReporterTask",
    "ReportFormat",
    # Sales Report
    "SalesReportTask",
    "SalesData",
]
