#!/usr/bin/env python3
"""
Exemplo de uso do módulo Organizador do AutoTarefas.

Este script demonstra como usar a API de organização programaticamente.

Uso:
    python organizer_example.py
"""

from pathlib import Path

from autotarefas.tasks.organizer import (
    DEFAULT_EXTENSION_MAP,
    ConflictStrategy,
    FileCategory,
    OrganizeProfile,
    OrganizerTask,
    organize_directory,
)


def exemplo_organizacao_basica():
    """Exemplo básico de organização."""
    print("=" * 50)
    print("Exemplo 1: Organização Básica")
    print("=" * 50)

    task = OrganizerTask()

    result = task.run(
        source="./downloads",
        destination="./downloads",  # Organiza no próprio diretório
    )

    if result.is_success:
        print("✅ Organização concluída!")
        print(f"   Arquivos movidos: {result.data['files_moved']}")
        print(f"   Arquivos pulados: {result.data['files_skipped']}")

        # Mostrar categorias criadas
        if "categories" in result.data:
            print("\n   Categorias:")
            for cat, count in result.data["categories"].items():
                print(f"     {cat}: {count} arquivo(s)")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_organizacao_por_data():
    """Exemplo de organização por data de modificação."""
    print("\n" + "=" * 50)
    print("Exemplo 2: Organização por Data")
    print("=" * 50)

    task = OrganizerTask()

    # Organiza em pastas como: 2024/Janeiro, 2024/Fevereiro, etc.
    result = task.run(
        source="./fotos",
        destination="./fotos_organizadas",
        profile=OrganizeProfile.BY_DATE,
    )

    if result.is_success:
        print("✅ Organização por data concluída!")
        print(f"   Arquivos movidos: {result.data['files_moved']}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_organizacao_por_extensao():
    """Exemplo de organização por extensão."""
    print("\n" + "=" * 50)
    print("Exemplo 3: Organização por Extensão")
    print("=" * 50)

    task = OrganizerTask()

    # Organiza em pastas como: pdf/, jpg/, docx/, etc.
    result = task.run(
        source="./documentos",
        destination="./documentos_organizados",
        profile=OrganizeProfile.BY_EXTENSION,
    )

    if result.is_success:
        print("✅ Organização por extensão concluída!")
        print(f"   Arquivos movidos: {result.data['files_moved']}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_conflito_rename():
    """Exemplo de tratamento de conflitos com renomeação."""
    print("\n" + "=" * 50)
    print("Exemplo 4: Conflito - Renomear")
    print("=" * 50)

    task = OrganizerTask()

    # Se arquivo já existe, renomeia: arquivo.txt -> arquivo_1.txt
    result = task.run(
        source="./duplicados",
        destination="./organizados",
        conflict_strategy=ConflictStrategy.RENAME,
    )

    if result.is_success:
        print("✅ Organização com renomeação concluída!")
        print(f"   Arquivos movidos: {result.data['files_moved']}")
        print(f"   Conflitos resolvidos: {result.data.get('conflicts_resolved', 0)}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_dry_run():
    """Exemplo de dry-run (simulação)."""
    print("\n" + "=" * 50)
    print("Exemplo 5: Dry-Run (Preview)")
    print("=" * 50)

    task = OrganizerTask()

    # dry_run=True mostra o que seria feito sem mover
    result = task.run(source="./downloads", destination="./downloads", dry_run=True)

    print(f"Status: {result.status}")
    print(f"Mensagem: {result.message}")

    if result.data and "preview" in result.data:
        print("\nPreview das movimentações:")
        for move in result.data["preview"][:5]:  # Primeiras 5
            print(f"  {move['from']} -> {move['to']}")

    print("\n(Nenhum arquivo foi movido)")

    return result


def exemplo_recursivo():
    """Exemplo de organização recursiva."""
    print("\n" + "=" * 50)
    print("Exemplo 6: Organização Recursiva")
    print("=" * 50)

    task = OrganizerTask()

    # Processa subdiretórios também
    result = task.run(
        source="./projeto",
        destination="./projeto_organizado",
        recursive=True,
        include_hidden=False,  # Ignora arquivos ocultos
    )

    if result.is_success:
        print("✅ Organização recursiva concluída!")
        print(f"   Arquivos movidos: {result.data['files_moved']}")
        print(f"   Diretórios processados: {result.data.get('dirs_processed', 1)}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_listar_categorias():
    """Exemplo de listagem de categorias disponíveis."""
    print("\n" + "=" * 50)
    print("Exemplo 7: Categorias Disponíveis")
    print("=" * 50)

    print("\n📁 Categorias de arquivos:\n")
    for category in FileCategory:
        print(f"  {category.value}")

    print(f"\n📋 Total de extensões mapeadas: {len(DEFAULT_EXTENSION_MAP)}")

    # Mostrar algumas extensões por categoria
    print("\n📎 Exemplos de mapeamento:")
    example_extensions = [".pdf", ".jpg", ".mp4", ".py", ".zip"]
    for ext in example_extensions:
        mapped = DEFAULT_EXTENSION_MAP.get(ext, FileCategory.OTHERS)
        print(f"  {ext} -> {mapped.value}")


def exemplo_funcao_helper():
    """Exemplo usando função helper simplificada."""
    print("\n" + "=" * 50)
    print("Exemplo 8: Função Helper")
    print("=" * 50)

    # Função mais simples para uso rápido
    result = organize_directory(source="./downloads", profile="default", dry_run=True)

    print(f"Status: {result.status}")
    print(f"Arquivos: {result.data.get('files_moved', 0)}")

    return result


if __name__ == "__main__":
    print("\n🗂️  Exemplos de Organizer do AutoTarefas\n")

    # Criar diretórios de teste
    for dir_name in ["downloads", "fotos", "documentos", "projeto"]:
        Path(f"./{dir_name}").mkdir(exist_ok=True)

    # Criar arquivos de teste
    (Path("./downloads") / "relatorio.pdf").write_text("PDF")
    (Path("./downloads") / "foto.jpg").write_bytes(b"JPEG")
    (Path("./downloads") / "video.mp4").write_bytes(b"MP4")
    (Path("./downloads") / "script.py").write_text("# Python")
    (Path("./fotos") / "img001.jpg").write_bytes(b"JPEG")
    (Path("./documentos") / "doc.docx").write_bytes(b"DOCX")

    try:
        # Executar exemplos
        exemplo_listar_categorias()
        exemplo_dry_run()

        print("\n" + "=" * 50)
        print("✅ Exemplos concluídos!")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback

        traceback.print_exc()
