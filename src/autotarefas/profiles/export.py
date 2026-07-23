"""
Exportacao de um perfil como schema pronto para o `validate`.

O perfil fala em campos conceituais. O usuario precisa de um schema com as
colunas REAIS da planilha dele. Este modulo faz a ponte e produz um YAML:

  - com as regras do perfil,
  - com os nomes das colunas ja trocados (onde ha mapeamento),
  - com os campos NAO mapeados marcados de forma inconfundivel,
  - com um cabecalho de procedencia (que perfil, versao, ferramenta),
  - com a documentacao de cada campo ao lado, como comentario.

TEMPLATE INCOMPLETO vs SCHEMA PRONTO — a distincao que evita erro:

  Se algum campo ficou sem mapeamento, o arquivo e um TEMPLATE: ele contem
  marcadores `PREENCHA_...` que o `validate` recusaria (e deve recusar). O
  cabecalho diz isso em letras claras, e o `ExportResult` sinaliza
  `is_complete = False`. Um template nunca se disfarca de schema pronto.

  So quando todos os campos requeridos estao mapeados o arquivo e um schema
  utilizavel de imediato.

Procedencia (linhagem): o cabecalho `generated_from` registra a origem.
Isso e a semente da rastreabilidade que o roadmap pede — de onde este
schema veio — sem antecipar nada: e so um comentario hoje.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import yaml

from autotarefas import __version__
from autotarefas.profiles.remap import remap_schema

if TYPE_CHECKING:
    from collections.abc import Mapping

    from autotarefas.profiles.catalog import Profile

#: Prefixo dos campos que o usuario ainda precisa preencher. Escolhido para
#: ser obvio a olho nu E para o `validate` tropecar nele se alguem esquecer.
UNMAPPED_PREFIX = "PREENCHA_o_nome_real_da_coluna__"


@dataclass(frozen=True, slots=True)
class ExportResult:
    """O resultado de exportar um perfil."""

    yaml_text: str
    is_complete: bool
    """True = todos os campos requeridos mapeados; o schema esta pronto.
    False = e um TEMPLATE com marcadores a preencher."""
    unmapped_required: tuple[str, ...] = ()
    """Campos requeridos que ficaram sem mapeamento (vazio se completo)."""
    unmapped_optional: tuple[str, ...] = field(default_factory=tuple)


def _resolve_mapping(
    perfil: Profile, mapping: Mapping[str, str]
) -> tuple[dict[str, str], set[str]]:
    """
    Resolve cada campo conceitual em: coluna real, marcador, ou OMITIDO.

    A regra que evita o schema-pronto-com-marcador:
      - campo mapeado            -> a coluna real
      - REQUERIDO nao mapeado    -> marcador PREENCHA_ (e o arquivo vira template)
      - OPCIONAL nao mapeado     -> OMITIDO do schema (a coluna nem aparece)

    Um opcional que o usuario nao tem (uma base so de PF nao tem CNPJ) nao
    deve virar uma regra procurando uma coluna inexistente. Ele simplesmente
    sai. Retorna (mapa_de_renomeacao, campos_a_omitir).
    """
    renomear: dict[str, str] = {}
    omitir: set[str] = set()
    for campo in perfil.concept_fields:
        destino = mapping.get(campo, "").strip()
        if destino:
            renomear[campo] = destino
        elif campo in perfil.required_fields:
            renomear[campo] = f"{UNMAPPED_PREFIX}{campo}"
        else:
            omitir.add(campo)
    return renomear, omitir


def _provenance_header(perfil: Profile, *, complete: bool) -> list[str]:
    linhas = [
        "# Schema gerado a partir de um perfil do AutoTarefas.",
        "#",
        "# generated_from:",
        f"#   profile: {perfil.id}",
        f"#   profile_version: {perfil.version}",
        f"#   tool_version: {__version__}",
        "#",
    ]
    if complete:
        linhas += [
            "# Todos os campos foram mapeados. Este schema esta pronto para uso:",
            f"#   autotarefas validate SUA_PLANILHA --schema {perfil.id}_schema.yaml",
        ]
    else:
        linhas += [
            "# ATENCAO: este arquivo e um TEMPLATE, ainda NAO esta pronto.",
            f"# Troque cada '{UNMAPPED_PREFIX}...' pelo nome real da coluna na",
            "# sua planilha e remova as linhas que nao se aplicam. O validate vai",
            "# recusar o arquivo enquanto houver marcadores PREENCHA_ nele.",
        ]
    linhas.append("#")
    return linhas


def _field_comment(perfil: Profile, campo: str) -> str | None:
    ficha = perfil.fields.get(campo)
    if ficha is None or not ficha.doc:
        return None
    marca = "obrigatorio" if ficha.required else "opcional"
    return f"# {campo} ({marca}): {ficha.doc}"


def export_schema(perfil: Profile, mapping: Mapping[str, str] | None = None) -> ExportResult:
    """
    Gera o schema de um perfil, aplicando o mapeamento de colunas.

    Args:
        perfil: o perfil carregado.
        mapping: campo_conceitual -> coluna_real. Pode ser parcial ou vazio;
            o que faltar vira marcador `PREENCHA_...`.

    Returns:
        ExportResult com o YAML e o estado (pronto ou template).
    """
    mapping = dict(mapping or {})

    # resolve cada campo: coluna real, marcador (requerido) ou omitido (opcional)
    renomear, omitir = _resolve_mapping(perfil, mapping)
    remapeado = remap_schema(perfil.profile_schema, renomear, omit=omitir)

    requeridos_sem = tuple(
        campo for campo in perfil.required_fields if not mapping.get(campo, "").strip()
    )
    opcionais_sem = tuple(sorted(omitir))
    completo_ok = not requeridos_sem

    # a procedencia vira um campo REAL do schema (o validate a le e ecoa para
    # o relatorio), nao so um comentario. O dump so inclui o que difere do
    # default, entao o schema fica enxuto.
    payload = remapeado.model_dump(mode="json", exclude_defaults=True, by_alias=True)
    payload["generated_from"] = {
        "profile": perfil.id,
        "profile_version": perfil.version,
        "tool_version": __version__,
    }
    corpo = yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )

    linhas = _provenance_header(perfil, complete=completo_ok)
    linhas.append("")

    # anexa as docs dos campos como bloco de referencia (o corpo YAML ja saiu
    # do model_dump; comentar linha a linha dentro dele seria fragil, entao a
    # documentacao vai num bloco logo acima, referenciando o nome conceitual)
    linhas.append("# Referencia dos campos deste perfil:")
    for campo in perfil.concept_fields:
        comentario = _field_comment(perfil, campo)
        if comentario:
            linhas.append(comentario)
    linhas.append("")
    linhas.append(corpo.rstrip())

    return ExportResult(
        yaml_text="\n".join(linhas) + "\n",
        is_complete=completo_ok,
        unmapped_required=requeridos_sem,
        unmapped_optional=opcionais_sem,
    )


def columns_hint(perfil: Profile, real_columns: list[str]) -> list[str]:
    """
    Sugere um esqueleto de mapeamento: lista os campos do perfil e as colunas
    reais lado a lado, para o usuario preencher. NAO adivinha correspondencia.

    Isto e ajuda sem palpite (a regra do §8 da 1.6): mostra o que existe dos
    dois lados; a decisao de qual e qual e do usuario.
    """
    linhas = ["Campos deste perfil (esquerda) e colunas da sua planilha (direita):", ""]
    campos = list(perfil.concept_fields)
    largura = max((len(c) for c in campos), default=0)
    for i, campo in enumerate(campos):
        real = real_columns[i] if i < len(real_columns) else ""
        marca = " (obrigatorio)" if campo in perfil.required_fields else ""
        linhas.append(f"  {campo.ljust(largura)}  ->  {real}{marca}")
    if len(real_columns) > len(campos):
        restantes = ", ".join(real_columns[len(campos) :])
        linhas.append(f"  (colunas sem par: {restantes})")
    return linhas


__all__ = ["UNMAPPED_PREFIX", "ExportResult", "columns_hint", "export_schema"]
