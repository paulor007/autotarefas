"""
Transferencia e enriquecimento entre planilhas (RF-REC-003).

E o "PROCV com evidencia": localizar o registro correspondente na outra
base e copiar para o destino **apenas os campos autorizados** — em um
ARQUIVO NOVO, com relatorio de tudo o que foi preenchido, atualizado ou
nao encontrado.

O que separa isto de um PROCV de planilha:

- **campo nao autorizado jamais e tocado.** A lista de campos e
  declarada (``--campo``); qualquer outra coluna do destino sai igual
  como entrou;
- **cada celula alterada vira uma linha de relatorio** (valor antes,
  valor depois, chave buscada e a acao aplicada);
- **nao-encontrado nao vira vazio silencioso**: a chave buscada e
  listada, para virar trabalho;
- **chave duplicada nao e pareada**, nem no destino nem na fonte — sem
  correspondencia confiavel, nao ha transferencia.

O pareamento reusa a comparacao da REC-001 (destino = A, fonte = B), o
que da de graca chave composta, normalizacao e conflitos de chave.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from autotarefas.reconcile.errors import CompareError
from autotarefas.reconcile.result import ComparisonResult, TableSource

#: O que aconteceu com uma celula do destino.
TransferAction = Literal["preenchido", "atualizado", "mantido", "sem_valor_na_fonte"]

#: Prefixo da coluna opcional de procedencia (``_origem_email``).
ORIGIN_PREFIX = "_origem_"

#: Limites declarados desta fatia.
LIMITATIONS: tuple[str, ...] = (
    "so as colunas declaradas em --campo sao alteradas; o resto do destino sai igual",
    "o destino original nunca e sobrescrito: o resultado e sempre um arquivo novo",
    "chave duplicada (no destino ou na fonte) nao e pareada — vai para nao pareados",
    "campo ausente na fonte nao e transferido (vira aviso)",
    "consolidar duas bases em uma so e trabalho do comando `conciliar` (--manter-novos)",
)


@dataclass(frozen=True, slots=True)
class TransferPolicy:
    """As regras declaradas da transferencia."""

    fields: tuple[str, ...] = ()
    """Colunas autorizadas a receber valor da fonte."""
    only_empty: bool = False
    """True = so preenche o que estiver vazio no destino (nunca sobrescreve)."""
    mark_origin: bool = False
    """Acrescenta ``_origem_<campo>`` com o nome do arquivo de origem."""

    def describe(self) -> str:
        campos = ", ".join(self.fields) or "(nenhum)"
        modo = "apenas campos vazios" if self.only_empty else "preenche e atualiza"
        origem = "; marca a origem" if self.mark_origin else ""
        return f"campos autorizados: {campos}; modo: {modo}{origem}"


@dataclass(frozen=True, slots=True)
class CellTransfer:
    """Uma celula do destino e o que a fonte fez com ela."""

    key: tuple[str, ...]
    row: int
    """Linha FISICA no destino."""
    column: str
    before: str
    after: str
    action: TransferAction

    @property
    def changed(self) -> bool:
        return self.action in ("preenchido", "atualizado")


@dataclass(frozen=True, slots=True)
class NotFound:
    """Um registro do destino sem correspondente na fonte."""

    key: tuple[str, ...]
    row: int


@dataclass(frozen=True, slots=True)
class TransferResult:
    """Resultado completo da transferencia."""

    comparison: ComparisonResult
    policy: TransferPolicy
    columns: tuple[str, ...]
    """Colunas do destino resultante (inclui as de origem, quando pedidas)."""
    rows: tuple[dict[str, str], ...] = ()
    """O destino ja enriquecido, linha a linha (arquivo novo)."""
    transfers: tuple[CellTransfer, ...] = ()
    not_found: tuple[NotFound, ...] = ()
    unmatched_source: tuple[tuple[str, ...], ...] = ()
    """Chaves que existem so na fonte (nao ha destino para receber)."""
    limitations: tuple[str, ...] = field(default_factory=lambda: LIMITATIONS)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "registros_no_destino": len(self.rows),
            "preenchidos": sum(1 for t in self.transfers if t.action == "preenchido"),
            "atualizados": sum(1 for t in self.transfers if t.action == "atualizado"),
            "mantidos": sum(1 for t in self.transfers if t.action == "mantido"),
            "sem_valor_na_fonte": sum(
                1 for t in self.transfers if t.action == "sem_valor_na_fonte"
            ),
            "nao_encontrados": len(self.not_found),
            "so_na_fonte": len(self.unmatched_source),
        }

    @property
    def changed_count(self) -> int:
        return sum(1 for t in self.transfers if t.changed)


def _decide(before: str, source_value: str, policy: TransferPolicy) -> TransferAction:
    """
    Qual acao aplicar a uma celula — a regra fica em um lugar so.

    Ordem importa: sem valor na fonte nunca apaga o destino, e
    ``only_empty`` protege o que ja estava preenchido.
    """
    if not source_value.strip():
        return "sem_valor_na_fonte"
    if not before.strip():
        return "preenchido"
    if policy.only_empty:
        return "mantido"
    if before == source_value:
        return "mantido"
    return "atualizado"


def _row_as_dict(table: TableSource, position: int) -> dict[str, str]:
    linha = table.frame.iloc[position]
    return {str(coluna): str(linha[coluna]) for coluna in table.frame.columns}


def _missing_fields(source: TableSource, policy: TransferPolicy) -> list[str]:
    existentes = {str(c) for c in source.frame.columns}
    return [campo for campo in policy.fields if campo not in existentes]


def transfer_values(
    destination: TableSource,
    source: TableSource,
    comparison: ComparisonResult,
    policy: TransferPolicy,
) -> TransferResult:
    """
    Copia os campos autorizados da fonte para o destino, em memoria.

    Args:
        destination: base que RECEBE (foi o lado A da comparacao).
        source: base que fornece os valores (lado B).
        comparison: resultado de `compare_tables(destino, fonte, ...)`.
        policy: campos autorizados e modo de preenchimento.

    Returns:
        TransferResult com as linhas do destino ja enriquecidas, o que foi
        alterado, o que nao foi encontrado e as limitacoes declaradas.

    Raises:
        CompareError: nenhum campo autorizado, ou campo que nao existe no
            destino (transferir para coluna inexistente seria criar dado).
    """
    if not policy.fields:
        msg = "informe ao menos um campo autorizado (--campo) para transferir"
        raise CompareError(msg)

    colunas_destino = [str(c) for c in destination.frame.columns]
    ausentes_no_destino = [c for c in policy.fields if c not in colunas_destino]
    if ausentes_no_destino:
        msg = (
            f"campo(s) inexistente(s) no destino ({destination.name}): "
            f"{', '.join(ausentes_no_destino)}"
        )
        raise CompareError(msg)

    transferiveis = [c for c in policy.fields if c not in _missing_fields(source, policy)]

    linhas: list[dict[str, str]] = []
    transferencias: list[CellTransfer] = []
    nao_encontrados: list[NotFound] = []
    so_na_fonte: list[tuple[str, ...]] = []

    colunas_saida = list(colunas_destino)
    if policy.mark_origin:
        colunas_saida += [f"{ORIGIN_PREFIX}{campo}" for campo in transferiveis]

    for record in comparison.records:
        if record.category == "somente_b":
            so_na_fonte.append(record.key)
            continue
        if record.row_a is None:  # pragma: no cover - registro sem destino
            continue

        posicao_destino = record.row_a - destination.first_data_row
        linha = _row_as_dict(destination, posicao_destino)

        if record.row_b is None:
            nao_encontrados.append(NotFound(key=record.key, row=record.row_a))
            linhas.append(_with_origin(linha, {}, policy, transferiveis))
            continue

        posicao_fonte = record.row_b - source.first_data_row
        valores_fonte = _row_as_dict(source, posicao_fonte)
        origens: dict[str, str] = {}

        for campo in transferiveis:
            antes = linha.get(campo, "")
            valor_fonte = valores_fonte.get(campo, "")
            acao = _decide(antes, valor_fonte, policy)
            depois = valor_fonte if acao in ("preenchido", "atualizado") else antes
            linha[campo] = depois
            if acao in ("preenchido", "atualizado"):
                origens[campo] = source.name
            transferencias.append(
                CellTransfer(
                    key=record.key,
                    row=record.row_a,
                    column=campo,
                    before=antes,
                    after=depois,
                    action=acao,
                )
            )

        linhas.append(_with_origin(linha, origens, policy, transferiveis))

    return TransferResult(
        comparison=comparison,
        policy=policy,
        columns=tuple(colunas_saida),
        rows=tuple(linhas),
        transfers=tuple(transferencias),
        not_found=tuple(nao_encontrados),
        unmatched_source=tuple(so_na_fonte),
    )


def _with_origin(
    row: dict[str, str],
    origins: dict[str, str],
    policy: TransferPolicy,
    fields: list[str],
) -> dict[str, str]:
    """Acrescenta as colunas ``_origem_<campo>`` quando pedidas."""
    if not policy.mark_origin:
        return row
    for campo in fields:
        row[f"{ORIGIN_PREFIX}{campo}"] = origins.get(campo, "")
    return row


def source_field_warnings(source: TableSource, policy: TransferPolicy) -> list[str]:
    """Campos autorizados que nao existem na fonte (viram aviso, nao erro)."""
    return [
        f"campo '{campo}' nao existe na fonte ({source.name}): nada foi transferido para ele"
        for campo in _missing_fields(source, policy)
    ]


__all__ = [
    "LIMITATIONS",
    "ORIGIN_PREFIX",
    "CellTransfer",
    "NotFound",
    "TransferAction",
    "TransferPolicy",
    "TransferResult",
    "source_field_warnings",
    "transfer_values",
]
