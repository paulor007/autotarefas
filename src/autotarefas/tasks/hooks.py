"""Proteção antes de ação destrutiva, com falha fechada.

Há operações que apagam ou substituem o trabalho de alguém: restaurar por cima
de arquivos existentes, mover em massa, limpar uma pasta. Elas são legítimas —
e são exatamente as que dão errado do jeito que não se desfaz.

A regra aqui é simples: **antes de destruir, prove que existe backup recente e
conferido daquilo**. Sem prova, a ação não acontece.

O que "falha fechada" significa na prática, e por que importa:

- backup recente e conferido → **libera**;
- backup antigo, corrompido ou incompleto → **bloqueia**, dizendo qual;
- **não foi possível saber** (pasta ilegível, pacote inacessível, relógio
  incoerente) → **bloqueia também**.

O terceiro caso é o que separa uma proteção de um enfeite. Liberar "porque
provavelmente está tudo bem" transforma a guarda numa formalidade que só
funciona quando não era necessária.

Existe uma saída explícita — e ela é registrada. Quem precisa passar por cima
consegue, mas fica escrito que passou, quando e por quê. Uma proteção sem saída
vira algo que as pessoas desligam de vez; uma saída sem registro vira uma
proteção que ninguém sabe se estava ligada.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from autotarefas.tasks.backup import verify_backup
from autotarefas.tasks.retencao_nomes import listar_datados


class AcaoDestrutiva(enum.StrEnum):
    """O que está prestes a acontecer."""

    SOBRESCREVER_NA_RESTAURACAO = "sobrescrever_na_restauracao"
    """Restaurar por cima de arquivos que já existem."""

    MOVER_EM_MASSA = "mover_em_massa"
    """Reorganizar uma pasta inteira, mudando arquivos de lugar."""

    APAGAR = "apagar"
    """Remover arquivos."""


#: Quanto tempo um backup continua valendo como proteção. Um dia é o intervalo
#: em que a maioria das políticas roda; mais que isso e a "proteção" cobriria
#: uma versão que já não é a atual.
VALIDADE_PADRAO = timedelta(hours=26)


class ProtecaoBloqueou(Exception):
    """A ação destrutiva foi impedida, e a mensagem diz o que resolver."""


@dataclass(frozen=True)
class Veredito:
    """O que a guarda decidiu, e por quê."""

    liberado: bool
    motivo: str
    pacote: str = ""
    """Qual pacote sustentou a liberação, quando houve uma."""

    def exigir(self) -> None:
        """Levanta quando bloqueado. É o jeito de usar num caminho de código."""
        if not self.liberado:
            raise ProtecaoBloqueou(self.motivo)


def _mais_recente(pasta: Path) -> tuple[datetime, Path] | None:
    """
    Pacote mais recente da pasta, pela data no NOME.

    Pela data do nome, e não do arquivo: copiar a pasta para outro disco
    atualiza a data de modificação de tudo, e a guarda passaria a achar que há
    backup de hoje quando o mais novo é de janeiro.
    """
    encontrados = listar_datados(pasta)
    return encontrados[0] if encontrados else None


def conferir(
    acao: AcaoDestrutiva,
    pasta_dos_pacotes: Path,
    *,
    agora: datetime | None = None,
    validade: timedelta = VALIDADE_PADRAO,
) -> Veredito:
    """
    Há backup recente e conferido que justifique deixar a ação acontecer?

    Falha fechada em toda dúvida: pasta que não existe, pacote que não abre,
    data que não faz sentido. Liberar na dúvida seria o mesmo que não ter a
    guarda.
    """
    return _decidir(acao, pasta_dos_pacotes, agora or datetime.now(UTC), validade)


def _decidir(  # noqa: PLR0911 — cada saida e um motivo diferente, e cada um
    # pede uma acao diferente de quem le: "faca um backup", "traga os pacotes
    # anteriores", "o disco esta ilegivel". Um "bloqueado" generico nao
    # resolveria nenhum deles.
    acao: AcaoDestrutiva,
    pasta: Path,
    instante: datetime,
    validade: timedelta,
) -> Veredito:
    """O veredito, com a frase que diz o que resolver."""
    limite_h = int(validade.total_seconds() // 3600)

    if not pasta.is_dir():
        return _bloqueio(acao, f"a pasta de pacotes ({pasta.name}) nao existe", "")

    try:
        encontrado = _mais_recente(pasta)
    except OSError as erro:
        return _bloqueio(acao, f"nao foi possivel ler a pasta de pacotes ({erro})", "")

    if encontrado is None:
        return _bloqueio(
            acao,
            f"nenhum backup encontrado em {pasta.name}. Faca um backup antes",
            "",
        )

    quando, mais_recente = encontrado

    # O nome carrega hora LOCAL; `agora` pode vir com fuso. Comparar sem
    # normalizar daria uma idade errada por horas — e a guarda liberaria ou
    # bloquearia pelo motivo errado.
    idade = instante.replace(tzinfo=None) - quando
    if idade > validade:
        horas = int(idade.total_seconds() // 3600)
        return _bloqueio(
            acao,
            f"o backup mais recente ({mais_recente.name}) tem {horas}h, e o limite e {limite_h}h",
            mais_recente.name,
        )

    relatorio = verify_backup(mais_recente)
    if not relatorio.ok:
        detalhe = relatorio.problem or "o conteudo nao confere com o manifesto"
        return _bloqueio(
            acao,
            f"o backup mais recente ({mais_recente.name}) nao confere: {detalhe}",
            mais_recente.name,
        )

    # Pacote incremental cuja corrente pode não estar completa. A guarda não
    # tem como saber daqui se os anteriores existem — e "não sei" é bloqueio,
    # não liberação.
    faltando = [nome for nome in relatorio.chain if not (pasta / nome).is_file()]
    if faltando:
        return _bloqueio(
            acao,
            f"{mais_recente.name} e incremental e depende de "
            f"{', '.join(faltando)}, que nao esta(o) na pasta",
            mais_recente.name,
        )

    return Veredito(
        liberado=True,
        motivo=f"backup {mais_recente.name} confere e tem menos de {limite_h}h",
        pacote=mais_recente.name,
    )


def _bloqueio(acao: AcaoDestrutiva, motivo: str, pacote: str) -> Veredito:
    """Monta a recusa com a frase de ação no fim, sempre no mesmo lugar."""
    return Veredito(
        liberado=False,
        motivo=f"{motivo}. A acao '{acao.value}' foi bloqueada.",
        pacote=pacote,
    )


def liberar_com_registro(acao: AcaoDestrutiva, motivo: str) -> Veredito:
    """
    A saída explícita.

    Quem precisa passar por cima da guarda consegue — e fica escrito que
    passou, com o motivo. Uma proteção sem saída vira algo que as pessoas
    desligam de vez; uma saída sem registro vira uma proteção que ninguém sabe
    se estava ligada.
    """
    return Veredito(
        liberado=True,
        motivo=(
            f"protecao dispensada para '{acao.value}': {motivo.strip() or 'sem motivo informado'}"
        ),
    )


__all__ = [
    "VALIDADE_PADRAO",
    "AcaoDestrutiva",
    "ProtecaoBloqueou",
    "Veredito",
    "conferir",
    "liberar_com_registro",
]
