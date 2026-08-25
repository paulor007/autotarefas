"""Backup executado pelo Agente, na maquina do cliente.

Aqui o produto deixa de ser "envie arquivos pelo navegador". O Agente le as
pastas que **alguem autorizou nesta maquina**, monta o pacote com o mesmo
nucleo da CLI e deixa o pacote **na maquina** (decisao H-4): o Live recebe a
ficha — nome, tamanho, soma, quantidade —, nunca o conteudo.

Sobre arquivo grande. O limite de 10 MB e do **envio pelo navegador**, e nao
existe aqui. O nucleo grava cada arquivo por pedacos, com um intermediario que
so vai para o disco quando passa do limite de memoria; um video de gigabytes
atravessa sem que o processo cresca junto. Isso e medido por teste, e nao
prometido: `test_arquivo_grande_nao_carrega_tudo_na_memoria` acompanha o pico
de alocacao durante um backup de arquivo maior que 10 MB.

Toda origem passa pela guarda de pastas autorizadas antes de qualquer leitura.
Um pedido do servidor com caminho que ninguem autorizou nao vira "backup
vazio": vira recusa com o motivo.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from autotarefas.tasks.backup import BackupTask

from . import raizes, vss
from .comandos import Contexto

#: Onde os pacotes ficam quando o pedido nao diz outra coisa.
PASTA_PADRAO = "backups"


class BackupRecusado(Exception):
    """O pedido nao pode ser atendido, e a mensagem diz por que."""


@dataclass(frozen=True)
class Pedido:
    """O que o Live pediu, ja validado contra o que esta autorizado."""

    origens: tuple[Path, ...]
    destino: Path
    excluir: tuple[str, ...] = ()
    manter: int = 0
    com_data: bool = True
    #: Tentar instantaneo de volume para copiar arquivo aberto.
    usar_vss: bool = False


def _destino_padrao(configuracao_raizes: tuple[str, ...]) -> Path:
    """
    Onde gravar quando o pedido nao diz.

    Ao lado da primeira pasta autorizada, e nao dentro dela: dentro, o pacote
    da execucao de hoje entraria no backup de amanha, e o tamanho dobraria a
    cada dia.
    """
    if not configuracao_raizes:
        msg = "nenhuma pasta autorizada nesta maquina"
        raise BackupRecusado(msg)
    return Path(configuracao_raizes[0]).parent / PASTA_PADRAO


def montar_pedido(parametros: dict[str, Any], contexto: Contexto) -> Pedido:
    """
    Transforma o pedido do servidor num pedido validado.

    Cada origem passa pela guarda. O servidor pode pedir qualquer caminho; o
    que ele NAO pode e obter um que ninguem autorizou aqui.
    """
    configuracao = contexto.configuracao
    brutas = parametros.get("origens") or list(configuracao.raizes)
    if not brutas:
        msg = "nenhuma pasta autorizada nesta maquina. Autorize pelo Agente, no proprio computador."
        raise BackupRecusado(msg)

    origens: list[Path] = []
    for bruta in brutas:
        caminho = Path(str(bruta))
        try:
            origens.append(raizes.exigir_autorizacao(configuracao, caminho))
        except raizes.AutorizacaoRecusada as erro:
            raise BackupRecusado(str(erro)) from erro

    destino_bruto = parametros.get("destino")
    destino = Path(str(destino_bruto)) if destino_bruto else _destino_padrao(configuracao.raizes)

    return Pedido(
        origens=tuple(origens),
        destino=destino,
        excluir=tuple(str(item) for item in parametros.get("excluir") or ()),
        manter=int(parametros.get("manter") or 0),
        com_data=bool(parametros.get("com_data", True)),
        usar_vss=bool(parametros.get("usar_vss", False)),
    )


def _nome_do_pacote(pedido: Pedido, momento: datetime | None = None) -> Path:
    """Nome final do pacote, com data quando pedido."""
    if pedido.destino.suffix.lower() == ".zip":
        return pedido.destino
    instante = momento or datetime.now(UTC)
    etiqueta = instante.strftime("%Y-%m-%d_%H%M") if pedido.com_data else "backup"
    return pedido.destino / f"backup_{etiqueta}.zip"


def executar(pedido: Pedido) -> dict[str, Any]:
    """
    Roda o backup e devolve a ficha do pacote.

    Sincrono de proposito: e trabalho de disco, nao de rede. Quem chama coloca
    isto numa thread para nao segurar o laco de eventos do canal — um backup
    de meia hora nao pode impedir o Agente de responder a uma batida.
    """
    alvo = _nome_do_pacote(pedido)
    alvo.parent.mkdir(parents=True, exist_ok=True)

    tarefa = BackupTask(
        sources=list(pedido.origens),
        destination=alvo,
        exclude_patterns=list(pedido.excluir) or None,
    )
    resultado = tarefa.run()

    if resultado.is_failure:
        msg = resultado.error_message or "o backup falhou"
        raise BackupRecusado(msg)

    dados = resultado.data
    nao_lidos = dados.get("unreadable", [])
    return {
        # O caminho fica na maquina; o Live recebe so o NOME. Caminho local do
        # cliente nao e assunto do servidor, e mandar o caminho completo
        # entregaria a estrutura de pastas da empresa.
        "pacote": alvo.name,
        "tamanho_bytes": int(dados.get("size_bytes", 0)),
        "sha256": str(dados.get("sha256", "")),
        "arquivos": int(dados.get("file_count", 0)),
        "excluidos_por_regra": int(dados.get("skipped_count", 0)),
        "nao_lidos": [{"arquivo": item["arquivo"], "motivo": item["motivo"]} for item in nao_lidos],
        "com_ressalva": bool(nao_lidos),
    }


def executar_com_instantaneo(pedido: Pedido) -> dict[str, Any]:
    """
    Roda o backup lendo de uma foto do volume, e nao do disco vivo.

    E o que faz a planilha aberta no Excel entrar no pacote. Todas as origens
    precisam estar no MESMO volume: uma foto cobre um volume, e tirar varias
    ao mesmo tempo daria fotos de instantes diferentes — o pacote pareceria
    consistente sem ser.

    O caminho gravado dentro do pacote continua sendo o do disco vivo. Quem
    for restaurar nao pode receber caminhos com o nome interno do instantaneo,
    que nao existem mais depois que ele e apagado.
    """
    volumes = {vss.volume_de(origem) for origem in pedido.origens}
    if len(volumes) > 1:
        msg = (
            "instantaneo de volume cobre um disco por vez; estas pastas estao "
            f"em {len(volumes)} discos diferentes. Crie uma politica por disco."
        )
        raise BackupRecusado(msg)

    volume = volumes.pop()
    with vss.instantaneo_de(volume) as foto:
        origens_na_foto = [foto.mapear(origem) for origem in pedido.origens]
        na_foto = replace(pedido, origens=tuple(origens_na_foto))
        ficha = executar(na_foto)

    ficha["instantaneo"] = True
    return ficha


async def executar_backup(parametros: dict[str, Any], contexto: Contexto) -> dict[str, Any]:
    """
    Executor do comando `backup`.

    O trabalho pesado sai para uma thread: sem isso, um backup grande
    bloquearia o laco de eventos e a conexao morreria por falta de batida —
    o servidor concluiria que a maquina caiu no meio do proprio backup.
    """
    pedido = montar_pedido(parametros, contexto)
    await contexto.relatar({"etapa": "iniciando", "origens": len(pedido.origens)})

    if pedido.usar_vss:
        # Recusa explicita, e nao queda silenciosa para o modo antigo: quem
        # pediu instantaneo pediu porque tem arquivo aberto, e receber um
        # pacote sem ele "com sucesso" e pior do que receber o motivo.
        motivo = vss.motivo_de_indisponibilidade()
        if motivo:
            raise BackupRecusado(motivo)
        ficha = await asyncio.to_thread(executar_com_instantaneo, pedido)
    else:
        ficha = await asyncio.to_thread(executar, pedido)
        ficha["instantaneo"] = False

    await contexto.relatar({"etapa": "concluido", "arquivos": ficha["arquivos"]})
    return ficha


__all__ = [
    "PASTA_PADRAO",
    "BackupRecusado",
    "Pedido",
    "executar",
    "executar_backup",
    "executar_com_instantaneo",
    "montar_pedido",
]
