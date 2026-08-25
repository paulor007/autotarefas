"""O nome do pacote, e o que dá para saber por ele.

`backup_2026-08-25_0230.zip` carrega a data em que o pacote foi criado. Isso
não é enfeite: é a única fonte de data confiável que sobrevive a uma cópia.
Copiar a pasta para outro disco atualiza a data de modificação de todos os
arquivos, e qualquer decisão baseada nela — retenção, proteção antes de ação
destrutiva — passaria a achar que tudo foi feito hoje.

Mora no núcleo porque três partes dependem da mesma convenção: quem cria o
pacote, quem aplica a retenção e quem confere se existe backup recente. Três
leitores do mesmo formato precisam de uma definição só.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

#: Nome que o produto gera. Fechado de propósito: é ele que autoriza a
#: retenção a apagar um arquivo, e um padrão frouxo apagaria dado alheio.
PADRAO = re.compile(r"^backup_(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})\.zip$")


def data_do_nome(nome: str) -> datetime | None:
    """
    Data que o nome declara, ou `None` se o nome não é do nosso formato.

    Data impossível (31 de fevereiro) também devolve `None`: um nome que não
    se consegue interpretar não pode virar uma data qualquer.
    """
    casou = PADRAO.match(nome)
    if casou is None:
        return None
    ano, mes, dia, hora, minuto = (int(parte) for parte in casou.groups())
    try:
        return datetime(ano, mes, dia, hora, minuto)
    except ValueError:
        return None


def listar_datados(pasta: Path) -> list[tuple[datetime, Path]]:
    """
    Pacotes reconhecidos na pasta com a data que cada nome declara, do mais
    novo para o mais velho.

    Devolve a data junto do caminho porque quem chama quase sempre precisa das
    duas coisas. Reinterpretar o nome depois obrigaria a tratar de novo o caso
    "não deu para ler a data" que aqui já foi resolvido — um caminho de código
    que nunca acontece e que ninguém consegue testar.

    Só entra o que casa com o padrão. Um arquivo que a pessoa guardou na mesma
    pasta não é problema nosso — e tratá-lo como pacote seria o primeiro passo
    para apagá-lo.
    """
    if not pasta.is_dir():
        return []

    encontrados: list[tuple[datetime, Path]] = []
    for arquivo in pasta.iterdir():
        if not arquivo.is_file():
            continue
        quando = data_do_nome(arquivo.name)
        if quando is not None:
            encontrados.append((quando, arquivo))

    return sorted(encontrados, key=lambda par: par[0], reverse=True)


def listar_pacotes(pasta: Path) -> list[Path]:
    """Só os caminhos, do mais novo para o mais velho."""
    return [caminho for _, caminho in listar_datados(pasta)]


__all__ = ["PADRAO", "data_do_nome", "listar_datados", "listar_pacotes"]
