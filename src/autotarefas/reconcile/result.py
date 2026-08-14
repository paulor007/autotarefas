"""
Contratos da comparacao entre duas planilhas (RF-REC-001).

A comparacao e LEITURA PURA: nada aqui escreve nas fontes. O resultado
diz, para cada registro, em qual das quatro categorias ele caiu —
``identico``, ``divergente``, ``somente_a``, ``somente_b`` — e, quando
divergente, QUAIS colunas diferem e com quais valores de cada lado.

Duas decisoes estruturais ficam registradas nestes contratos:

1. Chave duplicada NAO vira pareamento. Ela vai para :class:`KeyConflict`
   com todas as linhas envolvidas — parear "o primeiro com o primeiro"
   seria inventar uma correspondencia que o arquivo nao afirma.

2. Os valores reportados sao os ORIGINAIS (o texto que esta no arquivo).
   A normalizacao opcional vale para a COMPARACAO, nunca para o relatorio:
   quem le precisa ver o que esta na planilha, nao o que o comparador
   fez com aquilo por dentro.

Este pacote e agnostico de dominio: ele nao sabe o que e CPF, nota fiscal
ou matricula. Chave e coluna sao o que o usuario declarar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pandas as pd

#: Categorias de classificacao de um registro pareado por chave.
Category = Literal["identico", "divergente", "somente_a", "somente_b"]

#: Por que uma chave nao pode ser pareada com seguranca.
ConflictReason = Literal["chave_duplicada", "chave_vazia"]


@dataclass(frozen=True, slots=True)
class CellDifference:
    """Uma coluna que difere entre A e B, com os dois valores originais."""

    column: str
    value_a: str
    value_b: str


@dataclass(frozen=True, slots=True)
class RecordComparison:
    """Um registro (uma chave) e o que aconteceu com ele."""

    key: tuple[str, ...]
    """Valores da chave, na ordem canonica de :data:`ComparisonResult.key_columns`."""
    category: Category
    row_a: int | None = None
    """Linha FISICA em A (como no Excel). None quando so existe em B."""
    row_b: int | None = None
    differences: tuple[CellDifference, ...] = ()
    """Preenchido apenas na categoria ``divergente``."""


@dataclass(frozen=True, slots=True)
class KeyConflict:
    """
    Uma chave que o comparador se RECUSA a parear.

    Acontece quando a chave se repete em uma das fontes (nao da para saber
    qual linha corresponde a qual) ou quando ela esta vazia (nao ha chave
    para parear). Em ambos os casos as linhas envolvidas sao listadas —
    nenhum registro desaparece do relatorio.
    """

    key: tuple[str, ...]
    reason: ConflictReason
    rows_a: tuple[int, ...] = ()
    rows_b: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class CompareWarning:
    """Algo que o usuario precisa saber — e que o comparador NAO resolveu."""

    code: str
    """Codigo estavel (ex.: 'coluna_ausente', 'linhas_vazias_ignoradas')."""
    message: str
    column: str | None = None


@dataclass(frozen=True, slots=True)
class SourceInfo:
    """Identificacao de uma das fontes no relatorio (sem caminho fisico).

    So o NOME do arquivo entra no relatorio: o caminho completo no disco do
    cliente pode revelar estrutura de pastas e nomes de pessoas.
    """

    name: str
    rows: int
    first_data_row: int
    columns: tuple[str, ...] = ()
    sheet: str | None = None


@dataclass(frozen=True, slots=True)
class TableSource:
    """Uma tabela ja lida, pronta para comparar.

    O ``frame`` deve ser o DataFrame FIEL do leitor (texto exato do
    arquivo). Comparar sobre o texto — e nao sobre o dataframe tipado —
    evita que uma coluna tipada de formas diferentes em A e em B produza
    divergencia que nao existe no arquivo.
    """

    name: str
    frame: pd.DataFrame
    first_data_row: int = 2
    """Linha FISICA do primeiro registro (2 com o cabecalho na linha 1)."""
    sheet: str | None = None
    skipped_empty_rows: int = 0
    """Linhas totalmente vazias que o leitor descartou (deslocam a numeracao)."""

    def info(self) -> SourceInfo:
        """Resume a fonte para o relatorio (sem os dados e sem o caminho)."""
        return SourceInfo(
            name=self.name,
            rows=len(self.frame),
            first_data_row=self.first_data_row,
            columns=tuple(str(c) for c in self.frame.columns),
            sheet=self.sheet,
        )

    def physical_row(self, position: int) -> int:
        """Converte a posicao 0-based no DataFrame em linha fisica."""
        return self.first_data_row + position


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """Resultado completo de uma comparacao."""

    source_a: SourceInfo
    source_b: SourceInfo
    key_columns: tuple[str, ...]
    compared_columns: tuple[str, ...]
    records: tuple[RecordComparison, ...] = ()
    conflicts: tuple[KeyConflict, ...] = ()
    warnings: tuple[CompareWarning, ...] = ()
    normalizations: tuple[str, ...] = ()
    limitations: tuple[str, ...] = field(default_factory=tuple)
    """Limites declarados desta fatia (ex.: sem tolerancias numericas)."""

    def by_category(self, category: Category) -> tuple[RecordComparison, ...]:
        """Todos os registros de uma categoria, na ordem em que foram vistos."""
        return tuple(r for r in self.records if r.category == category)

    @property
    def counts(self) -> dict[str, int]:
        """Contadores por categoria (+ conflitos), para o resumo."""
        totais = dict.fromkeys(("identico", "divergente", "somente_a", "somente_b"), 0)
        for record in self.records:
            totais[record.category] += 1
        totais["conflitos"] = len(self.conflicts)
        return totais

    @property
    def has_differences(self) -> bool:
        """True se as bases nao sao equivalentes sob a chave declarada."""
        contagem = self.counts
        return any(
            contagem[chave] for chave in ("divergente", "somente_a", "somente_b", "conflitos")
        )


__all__ = [
    "Category",
    "CellDifference",
    "CompareWarning",
    "ComparisonResult",
    "ConflictReason",
    "KeyConflict",
    "RecordComparison",
    "SourceInfo",
    "TableSource",
]
