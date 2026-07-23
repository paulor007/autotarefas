"""
Perfis embutidos do AutoTarefas.

Um perfil e uma configuracao reutilizavel de regras — um `Schema` com nomes
conceituais e uma ficha em volta — que o cliente aplica a planilha dele
escolhendo o mapeamento das colunas. O perfil traz as REGRAS; o cliente
traz os NOMES.

    from autotarefas.profiles import list_profiles, load_profile, export_schema

    for pid in list_profiles():
        print(pid)

    perfil = load_profile("cadastro_contatos")
    yaml_text = export_schema(perfil, mapping={"email": "Contato principal"})

O fluxo do produto e EXPORT-ONLY: o perfil gera um schema que o usuario
revisa e usa no `validate`. O `validate` nao muda — nao existe modo
"--perfil" em tempo de execucao, entao nunca ha dois contratos concorrentes.
So existe o schema, e ele e inspecionavel antes de rodar.
"""

from autotarefas.profiles.catalog import (
    FieldDoc,
    Profile,
    ProfileError,
    list_profiles,
    load_all_profiles,
    load_profile,
)
from autotarefas.profiles.export import (
    UNMAPPED_PREFIX,
    ExportResult,
    export_schema,
)
from autotarefas.profiles.remap import RemapError, referenced_fields, remap_schema

__all__ = [
    "UNMAPPED_PREFIX",
    "ExportResult",
    "FieldDoc",
    "Profile",
    "ProfileError",
    "RemapError",
    "export_schema",
    "list_profiles",
    "load_all_profiles",
    "load_profile",
    "referenced_fields",
    "remap_schema",
]
