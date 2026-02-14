#!/usr/bin/env python3
"""
Exemplo de uso do módulo de Backup do AutoTarefas.

Este script demonstra como usar a API de backup programaticamente.

Uso:
    python backup_example.py
"""

from pathlib import Path

from autotarefas.tasks.backup import BackupManager, BackupTask, RestoreTask


def exemplo_backup_simples():
    """Exemplo básico de backup."""
    print("=" * 50)
    print("Exemplo 1: Backup Simples")
    print("=" * 50)

    task = BackupTask()

    # Criar backup
    result = task.run(
        source="./meus_documentos", destination="./backups", compression="zip"
    )

    if result.is_success:
        print(f"✅ Backup criado: {result.data['archive_path']}")
        print(f"   Arquivos: {result.data['files_count']}")
        print(f"   Tamanho: {result.data['size_formatted']}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_backup_com_exclusoes():
    """Exemplo de backup excluindo arquivos."""
    print("\n" + "=" * 50)
    print("Exemplo 2: Backup com Exclusões")
    print("=" * 50)

    task = BackupTask()

    result = task.run(
        source="./projeto",
        destination="./backups",
        compression="tar.gz",
        exclude_patterns=[
            "*.pyc",
            "__pycache__/*",
            ".git/*",
            "node_modules/*",
            "*.tmp",
        ],
    )

    if result.is_success:
        print(f"✅ Backup criado: {result.data['archive_path']}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_listar_backups():
    """Exemplo de listagem de backups."""
    print("\n" + "=" * 50)
    print("Exemplo 3: Listar Backups")
    print("=" * 50)

    manager = BackupManager(Path("./backups"))
    backups = manager.list_backups()

    if backups:
        print(f"Encontrados {len(backups)} backup(s):\n")
        for b in backups:
            print(f"  📦 {b.path.name}")
            print(f"     Tamanho: {b.size_formatted}")
            print(f"     Data: {b.created_at.strftime('%d/%m/%Y %H:%M')}")
            print(f"     Idade: {b.age_days} dias")
            print()
    else:
        print("Nenhum backup encontrado.")

    return backups


def exemplo_restaurar_backup():
    """Exemplo de restauração de backup."""
    print("\n" + "=" * 50)
    print("Exemplo 4: Restaurar Backup")
    print("=" * 50)

    # Encontrar backup mais recente
    manager = BackupManager(Path("./backups"))
    latest = manager.get_latest_backup("meus_documentos")

    if not latest:
        print("❌ Nenhum backup encontrado para restaurar.")
        return None

    print(f"Restaurando: {latest.path.name}")

    task = RestoreTask()
    result = task.run(
        backup_path=str(latest.path), destination="./restaurado", overwrite=False
    )

    if result.is_success:
        print(f"✅ Backup restaurado em: {result.data['destination']}")
        print(f"   Arquivos: {result.data['files_count']}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_dry_run():
    """Exemplo de dry-run (simulação)."""
    print("\n" + "=" * 50)
    print("Exemplo 5: Dry-Run (Simulação)")
    print("=" * 50)

    task = BackupTask()

    # dry_run=True simula sem criar o backup
    result = task.run(source="./documentos", destination="./backups", dry_run=True)

    print(f"Status: {result.status}")
    print(f"Mensagem: {result.message}")
    print("(Nenhum arquivo foi criado)")

    return result


def exemplo_cleanup_backups():
    """Exemplo de limpeza de backups antigos."""
    print("\n" + "=" * 50)
    print("Exemplo 6: Limpar Backups Antigos")
    print("=" * 50)

    # max_versions define quantos backups manter
    manager = BackupManager(Path("./backups"), max_versions=5)

    # Remove backups além do limite (mantém os 5 mais recentes)
    removed = manager.cleanup_old_backups()

    if removed > 0:
        print(f"✅ Removidos {removed} backup(s) antigo(s)")
    else:
        print("Nenhum backup removido (menos de 5 existentes)")

    return removed


if __name__ == "__main__":
    print("\n🔧 Exemplos de Backup do AutoTarefas\n")

    # Criar diretórios de teste
    Path("./meus_documentos").mkdir(exist_ok=True)
    Path("./backups").mkdir(exist_ok=True)

    # Criar arquivo de teste
    test_file = Path("./meus_documentos/teste.txt")
    test_file.write_text("Conteúdo de teste para backup")

    try:
        # Executar exemplos
        exemplo_backup_simples()
        exemplo_listar_backups()
        exemplo_dry_run()

        print("\n" + "=" * 50)
        print("✅ Exemplos concluídos!")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Erro: {e}")
