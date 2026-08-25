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
from autotarefas.tasks.politica import Politica as PoliticaDoNucleo
from autotarefas.tasks.politica import TipoDeDestino as TipoDeDestinoDaPolitica

from . import destinos as mod_destinos
from . import raizes, vss
from . import s3 as mod_s3
from .comandos import Contexto
from .config import Configuracao

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
    #: Para onde COPIAR o pacote depois de pronto. Vazio = fica so na maquina.
    destino_externo: Path | None = None
    tipo_do_destino: mod_destinos.TipoDeDestino | None = None
    #: Destino em nuvem compativel com S3. A credencial chega pelo canal
    #: autenticado, e usada, e some com o processo — nunca e gravada aqui.
    destino_s3: mod_s3.Credencial | None = None


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
        destino_externo=(
            Path(str(parametros["destino_externo"])) if parametros.get("destino_externo") else None
        ),
        tipo_do_destino=(
            mod_destinos.TipoDeDestino(str(parametros["tipo_do_destino"]))
            if parametros.get("tipo_do_destino")
            else None
        ),
        destino_s3=_credencial_s3(parametros.get("s3")),
    )


def _credencial_s3(bruta: Any) -> mod_s3.Credencial | None:
    """
    Le a credencial de nuvem do pedido, sem inventar valor nenhum.

    Campo obrigatorio faltando vira recusa com o nome do campo. Preencher com
    padrao silencioso levaria o pacote a um balde que ninguem escolheu.
    """
    if not bruta:
        return None
    if not isinstance(bruta, dict):
        msg = "credencial de nuvem em formato invalido"
        raise BackupRecusado(msg)

    faltando = [campo for campo in ("balde", "chave", "segredo") if not bruta.get(campo)]
    if faltando:
        msg = f"credencial de nuvem incompleta: falta {', '.join(faltando)}"
        raise BackupRecusado(msg)

    return mod_s3.Credencial(
        endpoint=str(bruta.get("endpoint", "")),
        regiao=str(bruta.get("regiao", "")),
        balde=str(bruta["balde"]),
        chave=str(bruta["chave"]),
        segredo=str(bruta["segredo"]),
        prefixo=str(bruta.get("prefixo", "")),
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
        # Interno: some antes de a ficha subir. O servidor nunca ve caminho
        # local do cliente.
        "_caminho_local": alvo,
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

    destino = _preparar_destino(pedido)

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

    caminho_local = ficha.pop("_caminho_local")
    entregas: list[dict[str, Any]] = []

    if destino is not None:
        await contexto.relatar({"etapa": "entregando", "destino": destino.descricao})
        entregas.append(await asyncio.to_thread(mod_destinos.entregar, caminho_local, destino))

    if pedido.destino_s3 is not None:
        await contexto.relatar({"etapa": "enviando", "destino": pedido.destino_s3.descricao})
        try:
            entregas.append(
                await asyncio.to_thread(mod_s3.enviar, caminho_local, pedido.destino_s3)
            )
        except mod_s3.EnvioRecusado as erro:
            raise BackupRecusado(str(erro)) from erro

    # `entrega` continua sendo a primeira, para nao quebrar quem ja le esse
    # campo; `entregas` traz todas. `null` ali segue sendo informacao: e o que
    # distingue "o pacote esta so nesta maquina" de "o pacote saiu daqui".
    ficha["entrega"] = entregas[0] if entregas else None
    ficha["entregas"] = entregas

    await contexto.relatar({"etapa": "concluido", "arquivos": ficha["arquivos"]})
    return ficha


def _preparar_destino(pedido: Pedido) -> mod_destinos.Destino | None:
    """
    Confere o destino ANTES de copiar qualquer arquivo.

    Descobrir que o disco externo esta cheio, ou que a pasta de rede nao
    aceita escrita, depois de meia hora de copia e descobrir tarde.
    """
    if pedido.destino_externo is None:
        return None
    try:
        return mod_destinos.preparar(
            pedido.destino_externo,
            tipo_declarado=pedido.tipo_do_destino,
            origens=pedido.origens,
        )
    except mod_destinos.DestinoRecusado as erro:
        raise BackupRecusado(str(erro)) from erro


async def executar_politica(
    politica: PoliticaDoNucleo,
    configuracao: Configuracao,
    relatar: Any = None,
) -> dict[str, Any]:
    """
    Traduz uma politica em um backup, executa e aplica a retencao.

    A retencao roda DEPOIS do backup e so quando ele deu certo. Rodar antes
    apagaria a copia mais antiga para abrir espaco de um pacote que talvez nem
    seja criado — trocar uma copia boa por nenhuma.

    Falha na retencao vira ressalva, e nao falha: o pacote existe; o que nao
    deu certo foi a faxina.
    """
    from . import retencao as mod_retencao

    parametros: dict[str, Any] = {
        "origens": list(politica.origens),
        "usar_vss": politica.usar_vss,
    }
    if politica.destino.tipo in {
        TipoDeDestinoDaPolitica.LOCAL,
        TipoDeDestinoDaPolitica.EXTERNO,
        TipoDeDestinoDaPolitica.REDE,
    }:
        parametros["destino_externo"] = politica.destino.caminho
        parametros["tipo_do_destino"] = politica.destino.tipo.value

    async def sem_relato(_dados: dict[str, Any]) -> None:
        return None

    contexto = Contexto(configuracao=configuracao, relatar=relatar or sem_relato)
    ficha = await executar_backup(parametros, contexto)

    pedido = montar_pedido(parametros, contexto)
    limpeza = await asyncio.to_thread(
        mod_retencao.aplicar, _pasta_dos_pacotes(pedido), politica.retencao
    )
    ficha["retencao"] = limpeza

    ressalvas: list[str] = []
    if ficha.get("com_ressalva"):
        ressalvas.append(f"{len(ficha.get('nao_lidos', []))} arquivo(s) nao entraram")
    if limpeza["nao_removidos"]:
        ressalvas.append(
            f"{len(limpeza['nao_removidos'])} pacote(s) antigo(s) nao puderam ser apagados"
        )
    ficha["ok"] = True
    ficha["com_ressalva"] = bool(ressalvas)
    ficha["ressalva"] = "; ".join(ressalvas)
    return ficha


def _pasta_dos_pacotes(pedido: Pedido) -> Path:
    """Onde os pacotes desta politica ficam, para a retencao varrer."""
    return pedido.destino if pedido.destino.suffix.lower() != ".zip" else pedido.destino.parent


__all__ = [
    "PASTA_PADRAO",
    "BackupRecusado",
    "Pedido",
    "executar",
    "executar_backup",
    "executar_com_instantaneo",
    "montar_pedido",
]
