"""De quem é cada pacote: uma pasta por política, dentro da pasta de pacotes.

Antes disto, todas as políticas de uma máquina gravavam no mesmo lugar. O
efeito não aparecia com uma política só, e era destrutivo com duas:

    backups/
        backup_2026-08-01_0300.zip   <- do "diário / 7 dias"
        backup_2026-08-01_2100.zip   <- do "mensal / 12 meses"

A retenção varre a pasta e decide o que sobra. Rodando pelo "diário / 7 dias",
ela olhava os dois pacotes, e apagava o mensal de julho por ele ter mais de
sete dias — cumprindo à risca uma regra que não era dele. O cliente
configurou doze meses de histórico e recebeu sete dias, sem erro, sem aviso e
sem nada no log que explicasse a falta.

O incremental sofria do mesmo mal por outro caminho: o catálogo mora ao lado
dos pacotes, então duas políticas incrementais compartilhavam a corrente. A
segunda "copiava só o que mudou" em relação ao pacote da primeira — que cobre
outras pastas. A restauração encontraria uma corrente que nunca esteve
completa.

A correção é dar dono ao artefato, e o dono precisa sobreviver a tudo o que
acontece com um arquivo: ser copiado para outro disco, ser levado para outra
máquina, ser encontrado meses depois por alguém que não sabe o que é. Por
isso o vínculo é a **pasta**, e não um registro em banco: o banco fica no
servidor, e o pacote precisa dizer de quem é sem servidor nenhum por perto.

    backups/
        backup_2026-08-30_1015.zip       <- avulso: não é de política alguma
        politica-a1b2.../
            politica.json                <- {"id": ..., "nome": "Diário 03:00"}
            backup_2026-08-01_0300.zip
        politica-c3d4.../
            politica.json
            backup_2026-08-01_2100.zip

O identificador vira nome de pasta, e ele chega do servidor — então é
conferido antes de virar caminho, pela mesma razão que o nome do pacote é
conferido em `artefatos`: sem isso, quem controla o servidor escolheria em que
pasta do disco o Agente escreve.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

#: Prefixo da pasta de cada política.
#:
#: Existe para que a varredura saiba, olhando só o nome, o que é pasta de
#: política e o que é uma pasta qualquer que a pessoa criou ali.
PREFIXO = "politica-"

#: Arquivo que diz, dentro da pasta, de qual política ela é.
#:
#: A pasta já carrega o identificador. O marcador existe para o **nome**:
#: quem abre o disco meses depois encontra "Backup diário 03:00" em vez de um
#: identificador de trinta e dois caracteres.
MARCADOR = "politica.json"

#: O que é aceito como identificador de política.
#:
#: Fechado de propósito. O identificador vem do servidor e vira nome de pasta;
#: um padrão frouxo aceitaria `..\\..\\Windows` e deixaria o servidor escolher
#: onde o Agente escreve.
ACEITO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def identificador_valido(politica_id: str) -> bool:
    """É identificador de política, e não um caminho disfarçado?"""
    return bool(ACEITO.match(politica_id))


def pasta_da_politica(raiz: Path, politica_id: str) -> Path:
    """
    A pasta desta política dentro da pasta de pacotes.

    Identificador vazio devolve a própria raiz: é o backup avulso, que não
    pertence a política alguma e mora onde sempre morou.
    """
    if not politica_id:
        return raiz
    if not identificador_valido(politica_id):
        msg = f"identificador de politica invalido: {politica_id!r}"
        raise ValueError(msg)
    return raiz / f"{PREFIXO}{politica_id}"


def marcar(pasta: Path, *, politica_id: str, nome: str) -> None:
    """
    Escreve (ou atualiza) o marcador da política nesta pasta.

    Idempotente: roda a cada execução, porque o nome da política muda e o
    marcador desatualizado é pior do que marcador nenhum — ele afirma.

    Falha ao escrever não interrompe backup nenhum. O marcador é conveniência
    para quem lê o disco; a pasta, que é o vínculo de verdade, já existe.
    """
    if not politica_id:
        return
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / MARCADOR).write_text(
            json.dumps({"id": politica_id, "nome": nome}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        return


def nome_marcado(pasta: Path) -> str:
    """O nome da política gravado no marcador, ou vazio se não der para ler."""
    try:
        dados = json.loads((pasta / MARCADOR).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(dados.get("nome", "")) if isinstance(dados, dict) else ""


def identificador_da_pasta(pasta: Path) -> str:
    """O identificador que o nome da pasta declara. Vazio quando não é uma."""
    nome = pasta.name
    if not nome.startswith(PREFIXO):
        return ""
    return nome[len(PREFIXO) :]


def pastas_de_politica(raiz: Path) -> list[Path]:
    """As pastas de política existentes na raiz, em ordem estável."""
    if not raiz.is_dir():
        return []
    return sorted(
        caminho
        for caminho in raiz.iterdir()
        if caminho.is_dir() and identificador_da_pasta(caminho)
    )


__all__ = [
    "ACEITO",
    "MARCADOR",
    "PREFIXO",
    "identificador_da_pasta",
    "identificador_valido",
    "marcar",
    "nome_marcado",
    "pasta_da_politica",
    "pastas_de_politica",
]
