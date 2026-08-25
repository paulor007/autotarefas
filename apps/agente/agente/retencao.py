"""Retenção avô-pai-filho: o que guardar e o que pode ir embora.

Guardar "os 30 últimos" protege contra o erro de ontem. Não protege contra o
erro que ninguém viu há três meses — a planilha corrompida em maio, descoberta
em agosto, quando as 30 cópias já são todas de junho em diante.

O esquema GFS resolve isso guardando três séries ao mesmo tempo: as diárias
recentes, uma por semana e uma por mês. Ocupa pouco mais e cobre um intervalo
muito maior.

Duas regras que evitam estrago:

1. **Nunca apagar o que não se reconhece.** Só entram na conta os pacotes com o
   nome que este produto gera. Um arquivo qualquer que a pessoa guardou na
   mesma pasta não é problema da retenção.
2. **Nunca apagar o mais recente.** Mesmo com a retenção zerada por engano —
   e mesmo que a data dele esteja fora de qualquer janela —, a última cópia
   fica. Uma rotina de limpeza que esvazia a pasta é pior do que não ter
   limpeza.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TypedDict

from autotarefas.tasks.politica import Retencao

#: Nome que o produto gera: `backup_2026-08-25_0230.zip`. O padrão é fechado
#: de propósito — é ele que decide o que pode ser apagado.
PADRAO = re.compile(r"^backup_(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})\.zip$")


@dataclass(frozen=True)
class Pacote:
    """Um pacote reconhecido, com a data que o nome declara."""

    caminho: Path
    quando: datetime

    @property
    def dia(self) -> date:
        return self.quando.date()

    @property
    def semana(self) -> tuple[int, int]:
        """(ano ISO, semana ISO). Semana atravessa a virada do ano sem quebrar."""
        ano, semana, _ = self.quando.isocalendar()
        return ano, semana

    @property
    def mes(self) -> tuple[int, int]:
        return self.quando.year, self.quando.month


def listar(pasta: Path) -> list[Pacote]:
    """
    Pacotes reconhecidos na pasta, do mais novo para o mais velho.

    A data vem do NOME, e não da data de modificação do arquivo: copiar a
    pasta para outro disco atualiza a data de modificação de tudo, e a
    retenção passaria a achar que todos os pacotes são de hoje.
    """
    if not pasta.is_dir():
        return []

    encontrados: list[Pacote] = []
    for arquivo in pasta.iterdir():
        casou = PADRAO.match(arquivo.name)
        if casou is None or not arquivo.is_file():
            continue
        ano, mes, dia, hora, minuto = (int(parte) for parte in casou.groups())
        try:
            quando = datetime(ano, mes, dia, hora, minuto)
        except ValueError:
            continue
        encontrados.append(Pacote(caminho=arquivo, quando=quando))

    return sorted(encontrados, key=lambda item: item.quando, reverse=True)


def decidir(pacotes: list[Pacote], regra: Retencao) -> tuple[list[Pacote], list[Pacote]]:
    """
    Separa em (guardar, apagar), sem tocar em disco.

    Do mais novo para o mais velho: o primeiro pacote de cada dia, semana e mês
    "ocupa a vaga" daquele período. Um pacote pode ocupar mais de uma vaga —
    o de segunda-feira costuma ser a diária do dia e a semanal da semana.
    """
    if not pacotes:
        return [], []

    guardar: list[Pacote] = []
    dias: set[date] = set()
    semanas: set[tuple[int, int]] = set()
    meses: set[tuple[int, int]] = set()

    for pacote in pacotes:
        ocupou = False
        if len(dias) < regra.diarias and pacote.dia not in dias:
            dias.add(pacote.dia)
            ocupou = True
        if len(semanas) < regra.semanais and pacote.semana not in semanas:
            semanas.add(pacote.semana)
            ocupou = True
        if len(meses) < regra.mensais and pacote.mes not in meses:
            meses.add(pacote.mes)
            ocupou = True
        if ocupou:
            guardar.append(pacote)

    # O mais recente fica sempre. Sem esta linha, retenção zerada por engano
    # esvaziaria a pasta — e uma rotina de limpeza que apaga tudo e pior do
    # que nao ter limpeza nenhuma.
    if pacotes[0] not in guardar:
        guardar.insert(0, pacotes[0])

    manter = set(guardar)
    apagar = [pacote for pacote in pacotes if pacote not in manter]
    return guardar, apagar


class RelatorioDeRetencao(TypedDict):
    """O que a faxina fez. Vai para o historico e para a tela."""

    guardados: int
    removidos: list[str]
    nao_removidos: list[str]


def aplicar(pasta: Path, regra: Retencao) -> RelatorioDeRetencao:
    """
    Aplica a retenção de verdade, apagando o que sobra.

    Devolve o que fez, para o histórico. Apagar em silêncio seria a operação
    mais perigosa do produto sem nenhum rastro: no dia em que faltar um pacote,
    ninguém saberia se ele nunca existiu ou se a retenção o levou.
    """
    pacotes = listar(pasta)
    guardar, apagar = decidir(pacotes, regra)

    removidos: list[str] = []
    falharam: list[str] = []
    for pacote in apagar:
        try:
            pacote.caminho.unlink()
        except OSError:
            # Arquivo em uso ou sem permissão. Não é motivo para derrubar o
            # backup que acabou de dar certo: vira ressalva.
            falharam.append(pacote.caminho.name)
        else:
            removidos.append(pacote.caminho.name)

    return RelatorioDeRetencao(guardados=len(guardar), removidos=removidos, nao_removidos=falharam)


__all__ = ["PADRAO", "Pacote", "RelatorioDeRetencao", "aplicar", "decidir", "listar"]
