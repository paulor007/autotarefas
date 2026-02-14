#!/usr/bin/env python3
"""
Exemplo de uso do módulo de Limpeza (Cleaner) do AutoTarefas.

Este script demonstra como usar a API de limpeza programaticamente.

Uso:
    python cleaner_example.py
"""

from pathlib import Path

from autotarefas.tasks.cleaner import CleanerTask, CleaningProfile, CleaningProfiles


def exemplo_limpeza_por_extensao():
    """Exemplo de limpeza por extensão."""
    print("=" * 50)
    print("Exemplo 1: Limpeza por Extensão")
    print("=" * 50)

    task = CleanerTask()

    result = task.run(
        paths=["./temp"], extensions=[".tmp", ".log", ".bak"], recursive=True
    )

    if result.is_success:
        print("✅ Limpeza concluída!")
        print(f"   Arquivos removidos: {result.data['files_removed']}")
        print(f"   Espaço liberado: {result.data['bytes_freed_formatted']}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_limpeza_com_perfil():
    """Exemplo de limpeza usando perfil pré-definido."""
    print("\n" + "=" * 50)
    print("Exemplo 2: Limpeza com Perfil")
    print("=" * 50)

    # Listar perfis disponíveis
    print("Perfis disponíveis:")
    for name in CleaningProfiles.list_profiles():
        profile = CleaningProfiles.get_by_name(name)
        print(f"  - {name}: {profile.patterns if profile else 'N/A'}")
    print()

    task = CleanerTask()

    # Usar perfil de arquivos temporários
    result = task.run(paths=["./temp"], profile="temp_files", recursive=True)

    if result.is_success:
        print("✅ Limpeza com perfil 'temp_files' concluída!")
        print(f"   Arquivos removidos: {result.data['files_removed']}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_limpeza_por_idade():
    """Exemplo de limpeza por idade do arquivo."""
    print("\n" + "=" * 50)
    print("Exemplo 3: Limpeza por Idade")
    print("=" * 50)

    task = CleanerTask()

    # Remover arquivos mais velhos que 30 dias
    result = task.run(paths=["./downloads"], min_age_days=30, recursive=False)

    if result.is_success:
        print("✅ Arquivos com mais de 30 dias removidos!")
        print(f"   Arquivos removidos: {result.data['files_removed']}")
        print(f"   Espaço liberado: {result.data['bytes_freed_formatted']}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_perfil_customizado():
    """Exemplo com perfil de limpeza customizado."""
    print("\n" + "=" * 50)
    print("Exemplo 4: Perfil Customizado")
    print("=" * 50)

    # Criar perfil customizado
    meu_perfil = CleaningProfile(
        name="meu_perfil",
        patterns=["*.cache", "*.swp", "*~", "Thumbs.db", ".DS_Store"],
        extensions=[".pyc", ".pyo"],
        min_age_days=0,
        include_hidden=True,
    )

    print(f"Perfil criado: {meu_perfil.name}")
    print(f"  Patterns: {meu_perfil.patterns}")
    print(f"  Extensions: {meu_perfil.extensions}")
    print()

    task = CleanerTask()

    result = task.run(paths=["./projeto"], profile=meu_perfil, recursive=True)

    if result.is_success:
        print("✅ Limpeza customizada concluída!")
        print(f"   Arquivos removidos: {result.data['files_removed']}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_dry_run():
    """Exemplo de dry-run (simulação)."""
    print("\n" + "=" * 50)
    print("Exemplo 5: Dry-Run (Simulação)")
    print("=" * 50)

    task = CleanerTask()

    # dry_run=True mostra o que seria removido sem remover
    result = task.run(paths=["./temp"], profile="temp_files", dry_run=True)

    print(f"Status: {result.status}")
    print(f"Mensagem: {result.message}")
    print("(Nenhum arquivo foi removido)")

    return result


def exemplo_multiplos_diretorios():
    """Exemplo de limpeza em múltiplos diretórios."""
    print("\n" + "=" * 50)
    print("Exemplo 6: Múltiplos Diretórios")
    print("=" * 50)

    task = CleanerTask()

    result = task.run(
        paths=["./temp", "./cache", "./logs"],
        extensions=[".tmp", ".log"],
        recursive=True,
        remove_empty_dirs=True,  # Remove diretórios vazios após limpeza
    )

    if result.is_success:
        print("✅ Limpeza em múltiplos diretórios concluída!")
        print(f"   Arquivos removidos: {result.data['files_removed']}")
        print(f"   Diretórios removidos: {result.data.get('dirs_removed', 0)}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


if __name__ == "__main__":
    print("\n🧹 Exemplos de Cleaner do AutoTarefas\n")

    # Criar diretórios de teste
    for dir_name in ["temp", "downloads", "projeto", "cache", "logs"]:
        Path(f"./{dir_name}").mkdir(exist_ok=True)

    # Criar arquivos de teste
    (Path("./temp") / "teste.tmp").write_text("temp")
    (Path("./temp") / "debug.log").write_text("log")
    (Path("./cache") / "data.cache").write_text("cache")

    try:
        # Executar exemplos
        exemplo_limpeza_por_extensao()
        exemplo_dry_run()

        print("\n" + "=" * 50)
        print("✅ Exemplos concluídos!")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Erro: {e}")
