"""
Mapeamento de colunas para campos do destino (RF-INT-005).

A planilha do cliente chama a coluna de "E-mail do Cliente"; a API chama o
campo de "email". Sem um de/para explicito, so restam duas saidas ruins:
pedir que o cliente renomeie as colunas, ou adivinhar. Este modulo e a
terceira: o de/para vira **configuracao declarada**, conferida antes de
qualquer envio.

O que ele garante, antes de a primeira requisicao sair:

- **coluna inexistente** na planilha e erro (nao vira campo vazio);
- **dois mapeamentos para o mesmo campo** e erro (o segundo apagaria o
  primeiro em silencio);
- **campo obrigatorio do destino sem origem** e erro;
- **linha com campo obrigatorio vazio** e REJEITADA antes do envio, com o
  motivo — nunca enviada pela metade.

O que ele deliberadamente NAO faz: adivinhar mapeamento por semelhanca de
nome, converter tipos ou virar um framework de conectores (DP-08). Ele
renomeia e confere; nada mais.

Nenhuma credencial passa por aqui: o arquivo de mapeamento so tem nomes
de coluna e de campo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import yaml

from autotarefas.core.exceptions import ConfigError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

#: Separador aceito na forma curta da CLI (``"Coluna=campo"``).
SPEC_SEPARATOR = "="


@dataclass(frozen=True, slots=True)
class FieldMapping:
    """O de/para declarado: coluna da planilha -> campo do destino."""

    pairs: tuple[tuple[str, str], ...] = ()
    required: tuple[str, ...] = ()
    """Campos que o destino exige (checados no mapeamento e por linha)."""
    keep_unmapped: bool = False
    """True = colunas sem mapeamento tambem vao no payload, com o nome original."""

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(coluna for coluna, _ in self.pairs)

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(campo for _, campo in self.pairs)

    @property
    def is_empty(self) -> bool:
        return not self.pairs

    def describe(self) -> str:
        if self.is_empty:
            return "(sem mapeamento: as colunas vao com o nome original)"
        pares = ", ".join(f"{coluna} -> {campo}" for coluna, campo in self.pairs)
        obrigatorios = f"; obrigatorios: {', '.join(self.required)}" if self.required else ""
        return f"{pares}{obrigatorios}"

    def as_dict(self) -> dict[str, Any]:
        """Payload do mapeamento para o relatorio e o audit."""
        return {
            "mapa": dict(self.pairs),
            "obrigatorios": list(self.required),
            "colunas_nao_mapeadas": "enviadas" if self.keep_unmapped else "ignoradas",
        }


# ============================================================
# Leitura
# ============================================================


def parse_mapping_specs(specs: Sequence[str]) -> tuple[tuple[str, str], ...]:
    """
    Le pares ``"Coluna=campo"`` da linha de comando.

    Raises:
        ConfigError: par sem ``=``, com lado vazio ou repetido.
    """
    pares: list[tuple[str, str]] = []
    for spec in specs:
        if SPEC_SEPARATOR not in spec:
            msg = f"mapeamento invalido: {spec!r}. Use a forma 'Coluna da planilha=campo'."
            raise ConfigError(msg)
        coluna, campo = spec.split(SPEC_SEPARATOR, 1)
        coluna, campo = coluna.strip(), campo.strip()
        if not coluna or not campo:
            msg = f"mapeamento invalido: {spec!r}. Os dois lados precisam ter nome."
            raise ConfigError(msg)
        pares.append((coluna, campo))
    return tuple(pares)


def load_mapping_file(path: Path) -> FieldMapping:
    """
    Le o mapeamento de um arquivo simples (YAML ou JSON).

    Formato::

        mapa:
          "E-mail do Cliente": email
          "Nome Completo": nome
        obrigatorios: [nome, email]
        colunas_nao_mapeadas: ignorar   # ou 'enviar'

    Raises:
        ConfigError: arquivo ilegivel ou estrutura invalida.
    """
    try:
        texto = path.read_text(encoding="utf-8")
        conteudo = json.loads(texto) if path.suffix.lower() == ".json" else yaml.safe_load(texto)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        msg = f"nao foi possivel ler o mapeamento {path.name}: {exc}"
        raise ConfigError(msg) from exc

    if not isinstance(conteudo, dict) or "mapa" not in conteudo:
        msg = f"{path.name}: o arquivo precisa ter a chave 'mapa' com o de/para das colunas."
        raise ConfigError(msg)

    mapa = conteudo["mapa"]
    if not isinstance(mapa, dict) or not mapa:
        msg = f"{path.name}: 'mapa' precisa ser um dicionario 'Coluna: campo' nao vazio."
        raise ConfigError(msg)

    obrigatorios = conteudo.get("obrigatorios") or []
    if not isinstance(obrigatorios, list):
        msg = f"{path.name}: 'obrigatorios' precisa ser uma lista de campos."
        raise ConfigError(msg)

    nao_mapeadas = str(conteudo.get("colunas_nao_mapeadas", "ignorar")).strip().lower()
    if nao_mapeadas not in ("ignorar", "enviar"):
        msg = f"{path.name}: 'colunas_nao_mapeadas' aceita 'ignorar' ou 'enviar'."
        raise ConfigError(msg)

    return FieldMapping(
        pairs=tuple((str(coluna), str(campo)) for coluna, campo in mapa.items()),
        required=tuple(str(campo) for campo in obrigatorios),
        keep_unmapped=nao_mapeadas == "enviar",
    )


def build_mapping(
    specs: Sequence[str] = (),
    mapping_file: Path | None = None,
    required: Sequence[str] = (),
    *,
    keep_unmapped: bool = False,
) -> FieldMapping:
    """
    Junta o mapeamento do arquivo com o da linha de comando.

    Precedencia: **a CLI vence o arquivo** — quem digitou agora sabe mais
    do que quem escreveu o arquivo semana passada. Um par declarado nos
    dois lugares para a MESMA coluna nao e conflito: e sobrescrita
    intencional.
    """
    base = load_mapping_file(mapping_file) if mapping_file is not None else FieldMapping()
    do_cli = parse_mapping_specs(specs)

    pares: dict[str, str] = dict(base.pairs)
    pares.update(dict(do_cli))

    obrigatorios = tuple(dict.fromkeys([*base.required, *required]))
    return FieldMapping(
        pairs=tuple(pares.items()),
        required=obrigatorios,
        keep_unmapped=keep_unmapped or base.keep_unmapped,
    )


# ============================================================
# Validacao
# ============================================================


@dataclass(frozen=True, slots=True)
class MappingIssue:
    """Um problema no mapeamento — sempre antes de qualquer envio."""

    code: str
    message: str


def validate_mapping(mapping: FieldMapping, columns: Sequence[str]) -> list[MappingIssue]:
    """
    Confere o mapeamento contra as colunas reais da planilha.

    Returns:
        Lista de problemas (vazia = mapeamento aplicavel). Nao levanta:
        quem chama decide se mostra tudo de uma vez ou aborta no primeiro.
    """
    problemas: list[MappingIssue] = []
    existentes = set(columns)

    for coluna, campo in mapping.pairs:
        if coluna not in existentes:
            problemas.append(
                MappingIssue(
                    code="coluna_inexistente",
                    message=(
                        f"a planilha nao tem a coluna '{coluna}' (mapeada para '{campo}'). "
                        f"Colunas disponiveis: {', '.join(sorted(existentes)) or '(nenhuma)'}"
                    ),
                )
            )

    vistos: dict[str, str] = {}
    for coluna, campo in mapping.pairs:
        if campo in vistos:
            problemas.append(
                MappingIssue(
                    code="campo_repetido",
                    message=(
                        f"o campo '{campo}' recebe duas colunas ('{vistos[campo]}' e "
                        f"'{coluna}'): uma apagaria a outra no envio"
                    ),
                )
            )
        else:
            vistos[campo] = coluna

    for obrigatorio in mapping.required:
        if obrigatorio in vistos:
            continue
        if mapping.keep_unmapped and obrigatorio in existentes:
            continue
        problemas.append(
            MappingIssue(
                code="obrigatorio_sem_origem",
                message=f"o campo obrigatorio '{obrigatorio}' nao tem coluna de origem",
            )
        )

    return problemas


# ============================================================
# Aplicacao
# ============================================================


@dataclass(frozen=True, slots=True)
class MappedRow:
    """Uma linha ja traduzida para o vocabulario do destino."""

    line: int
    """Linha FISICA na planilha (cabecalho = 1; 1a de dados = 2)."""
    payload: dict[str, Any] = field(default_factory=dict)
    rejected_reason: str = ""

    @property
    def accepted(self) -> bool:
        return not self.rejected_reason


def apply_mapping(
    rows: Sequence[Mapping[Any, Any]],
    mapping: FieldMapping,
    *,
    first_data_line: int = 2,
) -> list[MappedRow]:
    """
    Traduz as linhas para os campos do destino.

    Linha com campo obrigatorio vazio e REJEITADA aqui, antes do envio,
    com o motivo — e nao enviada pela metade para o sistema do cliente.

    Colunas de metadado do proprio AutoTarefas (prefixo ``_``) nunca entram
    no payload: elas existem nos artefatos, nao no registro.
    """
    resultado: list[MappedRow] = []
    de_para = dict(mapping.pairs)

    for indice, row in enumerate(rows):
        linha = first_data_line + indice
        payload: dict[str, Any] = {}

        for coluna, valor in row.items():
            nome = str(coluna)
            if nome.startswith("_"):
                continue
            campo = de_para.get(nome)
            if campo is not None:
                payload[campo] = valor
            elif mapping.keep_unmapped or mapping.is_empty:
                payload[nome] = valor

        faltando = [campo for campo in mapping.required if not str(payload.get(campo, "")).strip()]
        motivo = f"campo(s) obrigatorio(s) vazio(s): {', '.join(faltando)}" if faltando else ""
        resultado.append(MappedRow(line=linha, payload=payload, rejected_reason=motivo))

    return resultado


def preview_payloads(mapped: Sequence[MappedRow], limit: int = 3) -> list[dict[str, Any]]:
    """As primeiras linhas ja traduzidas, para conferencia antes do envio."""
    return [row.payload for row in mapped[:limit] if row.accepted]


__all__ = [
    "SPEC_SEPARATOR",
    "FieldMapping",
    "MappedRow",
    "MappingIssue",
    "apply_mapping",
    "build_mapping",
    "load_mapping_file",
    "parse_mapping_specs",
    "preview_payloads",
    "validate_mapping",
]
