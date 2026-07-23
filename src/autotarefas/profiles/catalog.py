"""
Catalogo de perfis embutidos.

Os perfis sao recursos YAML DENTRO do pacote, carregados por
`importlib.resources` — funcionam no repositorio, no wheel instalado e em
qualquer lugar, sem depender do diretorio atual e sem caminho absoluto.

O nucleo generico NAO conhece nenhum perfil: este modulo carrega o que
estiver na pasta de recursos, seja qual for. Adicionar um perfil e soltar
um `.yaml` la — nenhuma linha de codigo muda. E por isso que nao ha nome de
dominio nenhum aqui: o dominio mora no YAML, que o cliente pode ler.

SEGURANCA: o id de um perfil e validado contra um formato restrito antes de
virar nome de recurso. `../`, barras e nomes vazios sao recusados — um id
nunca vira um caminho para fora do pacote.
"""

from __future__ import annotations

import re
from importlib.resources import files
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from autotarefas.tasks.validate import Schema

if TYPE_CHECKING:
    from collections.abc import Mapping

#: Pacote onde os recursos de perfil vivem.
_RESOURCES = "autotarefas.profiles.resources"

#: Um id de perfil e uma palavra segura: minusculas, digitos e underscore.
#: Isto e o que impede um id de virar travessia de caminho.
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

_STRICT = ConfigDict(extra="forbid")


class ProfileError(ValueError):
    """Perfil inexistente, id invalido ou recurso mal formado."""


class FieldDoc(BaseModel):
    """Documentacao de um campo conceitual do perfil."""

    model_config = _STRICT

    required: bool = False
    doc: str = ""


class Profile(BaseModel):
    """
    Um perfil embutido: metadados + um Schema reutilizavel.

    O `schema` usa o MESMO modelo do `validate` — um perfil e, no fundo, um
    Schema com nomes conceituais e uma ficha de identificacao em volta.
    """

    model_config = _STRICT

    id: str = Field(..., min_length=1)
    version: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    summary: str = ""
    fields: dict[str, FieldDoc] = Field(default_factory=dict)
    profile_schema: Schema = Field(..., alias="schema")

    @field_validator("id")
    @classmethod
    def _id_seguro(cls, valor: str) -> str:
        if not _ID_PATTERN.match(valor):
            msg = (
                f"id de perfil invalido: {valor!r}. Use apenas letras minusculas, "
                "digitos e underscore (comecando por letra)."
            )
            raise ValueError(msg)
        return valor

    @property
    def required_fields(self) -> tuple[str, ...]:
        """Campos que o perfil considera obrigatorios (precisam ser mapeados)."""
        return tuple(nome for nome, ficha in self.fields.items() if ficha.required)

    @property
    def concept_fields(self) -> tuple[str, ...]:
        """Todos os campos conceituais (nomes das colunas do schema do perfil)."""
        return tuple(col.name for col in self.profile_schema.columns)


def _valid_id(profile_id: str) -> bool:
    return bool(_ID_PATTERN.match(profile_id))


def list_profiles() -> list[str]:
    """
    Ids de todos os perfis disponiveis, em ordem estavel.

    Le a pasta de recursos do PACOTE — nao um caminho do disco de
    desenvolvimento. No wheel instalado, e daqui que a lista sai.
    """
    raiz = files(_RESOURCES)
    ids = [
        recurso.name[:-5]  # remove ".yaml"
        for recurso in raiz.iterdir()
        if recurso.name.endswith(".yaml") and _valid_id(recurso.name[:-5])
    ]
    return sorted(ids)


def load_profile(profile_id: str) -> Profile:
    """
    Carrega e valida um perfil pelo id.

    Args:
        profile_id: o identificador (ex.: "cadastro_contatos").

    Returns:
        O `Profile` validado.

    Raises:
        ProfileError: id invalido, perfil inexistente ou recurso mal formado.
    """
    if not _valid_id(profile_id):
        msg = (
            f"id de perfil invalido: {profile_id!r}. Ids nao podem conter caminhos, barras ou '..'."
        )
        raise ProfileError(msg)

    recurso = files(_RESOURCES) / f"{profile_id}.yaml"
    if not recurso.is_file():
        disponiveis = ", ".join(list_profiles()) or "(nenhum)"
        msg = f"perfil '{profile_id}' nao existe. Disponiveis: {disponiveis}"
        raise ProfileError(msg)

    try:
        dados = yaml.safe_load(recurso.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        msg = f"perfil '{profile_id}' tem YAML invalido: {exc}"
        raise ProfileError(msg) from exc

    try:
        perfil = Profile.model_validate(dados)
    except ValueError as exc:
        msg = f"perfil '{profile_id}' e estruturalmente invalido: {exc}"
        raise ProfileError(msg) from exc

    # o id declarado dentro do arquivo tem que bater com o nome do recurso,
    # senao `listar` mostra um id e `ver` carrega outro.
    if perfil.id != profile_id:
        msg = (
            f"o perfil no arquivo '{profile_id}.yaml' se declara como "
            f"'{perfil.id}' — o id interno e o nome do arquivo devem coincidir"
        )
        raise ProfileError(msg)

    return perfil


def load_all_profiles() -> Mapping[str, Profile]:
    """Carrega todos os perfis (usado nos testes de catalogo e integridade)."""
    return {pid: load_profile(pid) for pid in list_profiles()}


__all__ = [
    "FieldDoc",
    "Profile",
    "ProfileError",
    "list_profiles",
    "load_all_profiles",
    "load_profile",
]
