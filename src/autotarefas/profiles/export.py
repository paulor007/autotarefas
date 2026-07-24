"""
Exportacao de um perfil como schema pronto para o `validate`.

O perfil fala em campos conceituais. O usuario precisa de um schema com as
colunas REAIS da planilha dele. Este modulo faz a ponte e produz um YAML:

  - com as regras do perfil,
  - com os nomes das colunas ja trocados (onde ha mapeamento),
  - com os campos requeridos NAO mapeados marcados de forma inconfundivel,
  - com a procedencia (que perfil, versao, ferramenta).

FONTE UNICA DA VERDADE (o que este modulo garante):

    O mapeamento resolvido e um DADO — `ExportResult.resolutions` — e nao um
    efeito colateral escondido na geracao do YAML. O schema e o resumo
    mostrado ao usuario saem os DOIS dessa mesma estrutura.

    Isso nao e preciosismo: a versao anterior montava o resumo em separado,
    pareando campos com colunas por POSICAO, e chegou a exibir
    `telefone -> Documento` enquanto o YAML (corretamente) escrevia
    `Documento` com regra de CPF. O motor estava certo e a tela mentia — a
    pior combinacao possivel para uma ferramenta que promete explicar quais
    regras vai aplicar.

TEMPLATE INCOMPLETO vs SCHEMA PRONTO:

  Campo requerido sem mapeamento -> marcador `PREENCHA_...`, e o arquivo e um
  TEMPLATE (`is_complete = False`). Campo OPCIONAL sem mapeamento e omitido:
  uma coluna que o usuario nao tem nao deve virar regra procurando coluna
  inexistente. Assim um schema pronto nunca carrega marcador dentro.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import yaml

from autotarefas import __version__
from autotarefas.profiles.remap import remap_schema

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from autotarefas.profiles.catalog import Profile

#: Prefixo dos campos que o usuario ainda precisa preencher. Escolhido para
#: ser obvio a olho nu E para o `validate` tropecar nele se alguem esquecer.
UNMAPPED_PREFIX = "PREENCHA_o_nome_real_da_coluna__"


class MappingError(ValueError):
    """Mapeamento invalido — erro de configuracao, sempre explicito."""


@dataclass(frozen=True, slots=True)
class FieldResolution:
    """
    O destino final de UM campo conceitual do perfil.

    Esta e a unidade da fonte unica: o YAML e o resumo na tela sao ambos
    derivados de uma lista destes.
    """

    field: str
    """O campo conceitual, como o perfil o nomeia."""
    column: str | None
    """A coluna real. None = campo omitido do schema (opcional sem mapa)."""
    required: bool
    is_placeholder: bool
    """True = `column` e um marcador PREENCHA_, nao uma coluna de verdade."""

    @property
    def mapped(self) -> bool:
        """Foi mapeado para uma coluna real (nem omitido, nem marcador)."""
        return self.column is not None and not self.is_placeholder


@dataclass(frozen=True, slots=True)
class ExportResult:
    """O resultado de exportar um perfil."""

    yaml_text: str
    resolutions: tuple[FieldResolution, ...]
    """Como cada campo do perfil foi resolvido. FONTE UNICA para o resumo."""

    @property
    def is_complete(self) -> bool:
        """True = todos os requeridos mapeados; o schema esta pronto para uso."""
        return not self.unmapped_required

    @property
    def unmapped_required(self) -> tuple[str, ...]:
        return tuple(r.field for r in self.resolutions if r.required and not r.mapped)

    @property
    def unmapped_optional(self) -> tuple[str, ...]:
        return tuple(r.field for r in self.resolutions if not r.required and not r.mapped)

    @property
    def mapping_applied(self) -> dict[str, str]:
        """O mapeamento efetivamente aplicado: campo -> coluna real."""
        return {r.field: r.column for r in self.resolutions if r.mapped and r.column}


def resolve_mapping(
    perfil: Profile,
    mapping: Mapping[str, str],
    *,
    available_columns: Sequence[str] | None = None,
) -> tuple[FieldResolution, ...]:
    """
    Resolve cada campo conceitual do perfil em coluna real, marcador ou omissao.

    Percorre os campos NA ORDEM DO PERFIL e consulta o mapa POR NOME. Nunca
    por posicao — a ordem em que o usuario passou os `--map` e irrelevante, e
    um campo sem mapa nao desloca os seguintes.

    Args:
        perfil: o perfil carregado.
        mapping: campo_conceitual -> coluna_real (pode ser parcial ou vazio).
        available_columns: se informado (via `--planilha`), as colunas reais
            do arquivo; usado para recusar mapeamento para coluna inexistente.

    Raises:
        MappingError: campo inexistente no perfil, coluna vazia, coluna
            inexistente no arquivo, ou dois campos apontando para a mesma coluna.
    """
    campos = perfil.concept_fields
    conhecidos = set(campos)

    desconhecidos = sorted(set(mapping) - conhecidos)
    if desconhecidos:
        msg = (
            f"o perfil '{perfil.id}' nao tem o(s) campo(s): {', '.join(desconhecidos)}. "
            f"Campos disponiveis: {', '.join(campos)}"
        )
        raise MappingError(msg)

    for campo, coluna in mapping.items():
        if not coluna.strip():
            msg = f"o campo '{campo}' foi mapeado para um nome de coluna vazio"
            raise MappingError(msg)

    if available_columns is not None:
        reais = set(available_columns)
        ausentes = sorted({c.strip() for c in mapping.values()} - reais)
        if ausentes:
            msg = (
                f"coluna(s) nao encontrada(s) na planilha: {', '.join(ausentes)}. "
                f"Colunas do arquivo: {', '.join(available_columns)}"
            )
            raise MappingError(msg)

    destinos: dict[str, str] = {}
    for campo, coluna in mapping.items():
        limpo = coluna.strip()
        if limpo in destinos:
            msg = (
                f"os campos '{destinos[limpo]}' e '{campo}' foram mapeados para a "
                f"mesma coluna '{limpo}'. Cada campo precisa de uma coluna propria."
            )
            raise MappingError(msg)
        destinos[limpo] = campo

    requeridos = set(perfil.required_fields)
    resolucoes = []
    for campo in campos:
        destino = mapping.get(campo, "").strip()
        obrigatorio = campo in requeridos
        if destino:
            resolucoes.append(
                FieldResolution(
                    field=campo, column=destino, required=obrigatorio, is_placeholder=False
                )
            )
        elif obrigatorio:
            resolucoes.append(
                FieldResolution(
                    field=campo,
                    column=f"{UNMAPPED_PREFIX}{campo}",
                    required=True,
                    is_placeholder=True,
                )
            )
        else:
            resolucoes.append(
                FieldResolution(field=campo, column=None, required=False, is_placeholder=False)
            )
    return tuple(resolucoes)


def _provenance_header(perfil: Profile, *, complete: bool) -> list[str]:
    linhas = [
        "# Schema gerado a partir de um perfil do AutoTarefas.",
        "#",
        "# generated_from:",
        f"#   profile: {perfil.id}",
        f"#   profile_version: {perfil.version}",
        f"#   tool_version: {__version__}",
        "#",
        "# 'Gerado a partir de' — voce pode editar este arquivo livremente.",
        "#",
    ]
    if complete:
        linhas += [
            "# Todos os campos requeridos foram mapeados: este schema esta pronto.",
            "#",
        ]
    else:
        linhas += [
            "# ATENCAO: este arquivo e um TEMPLATE, ainda NAO esta pronto.",
            f"# Troque cada '{UNMAPPED_PREFIX}...' pelo nome real da coluna",
            "# na sua planilha antes de usar no validate.",
            "#",
        ]
    return linhas


def _field_reference(perfil: Profile, resolucoes: tuple[FieldResolution, ...]) -> list[str]:
    """Documentacao dos campos, ao lado do destino que cada um recebeu."""
    linhas = ["# Campos deste perfil e a coluna que cada um recebeu:"]
    for r in resolucoes:
        ficha = perfil.fields.get(r.field)
        doc = f" {ficha.doc}" if ficha and ficha.doc else ""
        if r.mapped:
            destino = f"-> {r.column}"
        elif r.is_placeholder:
            destino = "-> (PREENCHA)"
        else:
            destino = "-> (nao usado)"
        linhas.append(f"#   {r.field} {destino}.{doc}")
    return linhas


def export_schema(
    perfil: Profile,
    mapping: Mapping[str, str] | None = None,
    *,
    available_columns: Sequence[str] | None = None,
) -> ExportResult:
    """
    Gera o schema de um perfil, aplicando o mapeamento de colunas.

    Args:
        perfil: o perfil carregado.
        mapping: campo_conceitual -> coluna_real. Parcial ou vazio e valido:
            requeridos que faltarem viram marcador, opcionais sao omitidos.
        available_columns: colunas reais da planilha, quando conhecidas.

    Returns:
        ExportResult com o YAML e as resolucoes (a fonte unica do resumo).

    Raises:
        MappingError: mapeamento invalido.
    """
    mapping = dict(mapping or {})
    resolucoes = resolve_mapping(perfil, mapping, available_columns=available_columns)

    renomear = {r.field: r.column for r in resolucoes if r.column is not None}
    omitir = {r.field for r in resolucoes if r.column is None}
    remapeado = remap_schema(perfil.profile_schema, renomear, omit=omitir)

    completo = not any(r.required and not r.mapped for r in resolucoes)

    payload = remapeado.model_dump(mode="json", exclude_defaults=True, by_alias=True)
    payload["generated_from"] = {
        "profile": perfil.id,
        "profile_version": perfil.version,
        "tool_version": __version__,
    }
    corpo = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False)

    linhas = _provenance_header(perfil, complete=completo)
    linhas += _field_reference(perfil, resolucoes)
    linhas.append("")
    linhas.append(corpo.rstrip())

    return ExportResult(yaml_text="\n".join(linhas) + "\n", resolutions=resolucoes)


def render_mapping(result: ExportResult) -> list[str]:
    """
    Linhas do resumo mostrado ao usuario.

    Renderiza `result.resolutions` — a MESMA estrutura que gerou o YAML. Nao
    ha como esta tabela discordar do arquivo: ela nao tem dados proprios.
    """
    if not result.resolutions:
        return []

    largura = max(len(r.field) for r in result.resolutions)
    linhas = ["Mapeamento aplicado:"]
    for r in result.resolutions:
        if r.mapped:
            destino = str(r.column)
        elif r.is_placeholder:
            destino = "(FALTA MAPEAR)"
        else:
            destino = "(nao usado)"
        # parenteses, nao colchetes: o console usa Rich, e "[texto]" seria
        # consumido como tag de estilo e sumiria da tela.
        marca = "  (obrigatorio)" if r.required else ""
        linhas.append(f"  {r.field.ljust(largura)}  ->  {destino}{marca}")
    return linhas


def available_columns_lines(columns: Sequence[str]) -> list[str]:
    """
    Lista as colunas reais da planilha, para ajudar quem vai montar o mapa.

    Deliberadamente NAO pareia com os campos do perfil: parear seria um
    palpite, e um palpite exibido como se fosse decisao foi exatamente o bug
    que esta funcao substitui. Aqui e so uma lista do que existe no arquivo.
    """
    if not columns:
        return []
    return ["Colunas encontradas na planilha:", *[f"  - {c}" for c in columns]]


__all__ = [
    "UNMAPPED_PREFIX",
    "ExportResult",
    "FieldResolution",
    "MappingError",
    "available_columns_lines",
    "export_schema",
    "render_mapping",
    "resolve_mapping",
]
