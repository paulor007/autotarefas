"""Políticas de backup: criar, alterar e mandar para a máquina.

O servidor guarda e valida; quem **executa** é o Agente, com a política gravada
no disco dele. Essa divisão é o que faz o backup acontecer com o navegador
fechado e com o servidor fora do ar.

Por isso toda alteração termina com uma sincronização: gravar aqui e não avisar
a máquina produziria a pior discordância possível — a tela mostrando "todo dia
às 2h" enquanto o Agente segue com o horário antigo, ou com nenhum.

Quando a máquina está desligada na hora de sincronizar, isso **não** é erro: a
política fica pendente e sobe na próxima conexão. O que não pode é a tela
afirmar que está valendo.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from autotarefas.tasks.politica import Politica as ConfiguracaoDePolitica
from autotarefas.tasks.politica import TipoDeDestino

from .db import repositorio as repo
from .db.models import Dispositivo, EstadoDispositivo, Politica, agora
from .identidade.dependencias import (
    ContextoAdministrador,
    ContextoAtual,
    SessaoBanco,
)

roteador = APIRouter(prefix="/api/politicas", tags=["politicas"])


class PoliticaRecusada(Exception):
    """A política não pode ser gravada, e a mensagem diz por quê."""


class PedidoDePolitica(BaseModel):
    """O que a tela envia ao criar ou alterar uma política."""

    nome: str = Field(min_length=1, max_length=200)
    dispositivo_id: str = Field(min_length=1)
    ativa: bool = True
    #: A configuração é validada pelo schema do núcleo antes de ser gravada.
    #: Validar aqui, e não na execução, é o ponto: de madrugada não há quem
    #: corrija um campo errado.
    configuracao: dict[str, Any] = Field(default_factory=dict)


#: O que o Agente sabe fazer sozinho, no horario, sem falar com o servidor.
#:
#: `nuvem` fica de fora, e a ausencia e deliberada. O envio para S3 existe e
#: funciona — o Agente verifica o objeto depois de subir — mas a credencial
#: mora no cofre da organizacao, no servidor, e o agendamento roda **offline**
#: por decisao de projeto: se dependesse do canal, o backup pararia sempre que
#: a internet caisse, que e justamente a madrugada em que ninguem esta olhando.
#:
#: Enquanto a credencial nao for entregue a maquina, uma politica com destino
#: `nuvem` produziria um pacote que nunca sai do computador — e o painel a
#: contaria como "Protegido", porque `protege_de_verdade` considera nuvem um
#: destino de verdade. Backup que se declara protegido e nao saiu do lugar e a
#: falha mais cara que este produto pode ter.
DESTINOS_QUE_O_AGENDAMENTO_ENTREGA = frozenset(
    {
        TipoDeDestino.NENHUM,
        TipoDeDestino.LOCAL,
        TipoDeDestino.EXTERNO,
        TipoDeDestino.REDE,
    }
)

RECUSA_DA_NUVEM = (
    "destino 'nuvem': o backup agendado ainda nao leva a credencial de nuvem "
    "ate a maquina, entao o pacote ficaria no proprio computador enquanto o "
    "painel diria 'Protegido'. Use disco externo ou pasta de rede."
)


def _validar(bruta: dict[str, Any]) -> ConfiguracaoDePolitica:
    try:
        configuracao = ConfiguracaoDePolitica.model_validate(bruta)
    except ValidationError as erro:
        primeira = erro.errors()[0]
        campo = ".".join(str(parte) for parte in primeira.get("loc", ()))
        msg = f"{campo or 'configuracao'}: {primeira.get('msg', 'valor invalido')}"
        raise PoliticaRecusada(msg) from erro

    if configuracao.destino.tipo not in DESTINOS_QUE_O_AGENDAMENTO_ENTREGA:
        raise PoliticaRecusada(RECUSA_DA_NUVEM)
    return configuracao


def _dispositivo_da_organizacao(
    sessao: Session, contexto: repo.Contexto, dispositivo_id: str
) -> Dispositivo:
    dispositivo = sessao.execute(
        repo.escopo(Dispositivo, contexto).where(Dispositivo.id == dispositivo_id)
    ).scalar_one_or_none()
    if dispositivo is None:
        msg = "dispositivo nao encontrado nesta organizacao"
        raise PoliticaRecusada(msg)
    if dispositivo.estado is EstadoDispositivo.REVOGADO:
        # Deixar criar política para máquina revogada geraria uma linha que
        # nunca vai executar, e a tela mostraria backup agendado que não
        # acontece.
        msg = "este dispositivo foi revogado: pareie novamente antes de criar politica"
        raise PoliticaRecusada(msg)
    return dispositivo


def como_dicionario(registro: Politica) -> dict[str, Any]:
    """Forma que a tela consome."""
    configuracao = ConfiguracaoDePolitica.de_json(registro.configuracao)
    return {
        "id": registro.id,
        "nome": registro.nome,
        "dispositivo_id": registro.dispositivo_id,
        "ativa": registro.ativa,
        "configuracao": configuracao.model_dump(mode="json"),
        # Dito em voz alta: pacote no mesmo computador não protege contra o
        # disco morrer nem contra ransomware. "Configurado" sem isto seria
        # uma palavra que não significa nada.
        "protege_de_verdade": configuracao.protege_de_verdade,
        "criada_em": registro.criada_em.isoformat(),
        "atualizada_em": registro.atualizada_em.isoformat(),
    }


def listar(sessao: Session, contexto: repo.Contexto) -> list[dict[str, Any]]:
    registros = sessao.execute(
        repo.escopo(Politica, contexto).order_by(Politica.criada_em.asc())
    ).scalars()
    return [como_dicionario(item) for item in registros]


def criar(sessao: Session, contexto: repo.Contexto, pedido: PedidoDePolitica) -> Politica:
    contexto.exigir_administracao()
    configuracao = _validar(pedido.configuracao)
    _dispositivo_da_organizacao(sessao, contexto, pedido.dispositivo_id)

    registro = Politica(
        organizacao_id=contexto.organizacao_id,
        dispositivo_id=pedido.dispositivo_id,
        nome=pedido.nome,
        ativa=pedido.ativa,
        configuracao=configuracao.como_json(),
    )
    sessao.add(registro)
    sessao.flush()
    repo.registrar(
        sessao,
        contexto,
        acao="politica.criada",
        alvo=registro.nome,
        detalhe=configuracao.agendamento.tipo.value,
        dispositivo_id=pedido.dispositivo_id,
    )
    return registro


def alterar(
    sessao: Session, contexto: repo.Contexto, politica_id: str, pedido: PedidoDePolitica
) -> Politica:
    contexto.exigir_administracao()
    configuracao = _validar(pedido.configuracao)
    _dispositivo_da_organizacao(sessao, contexto, pedido.dispositivo_id)

    registro = sessao.execute(
        repo.escopo(Politica, contexto).where(Politica.id == politica_id)
    ).scalar_one_or_none()
    if registro is None:
        msg = "politica nao encontrada nesta organizacao"
        raise PoliticaRecusada(msg)

    registro.nome = pedido.nome
    registro.dispositivo_id = pedido.dispositivo_id
    registro.ativa = pedido.ativa
    registro.configuracao = configuracao.como_json()
    registro.atualizada_em = agora()
    sessao.flush()
    repo.registrar(
        sessao,
        contexto,
        acao="politica.alterada",
        alvo=registro.nome,
        detalhe=configuracao.agendamento.tipo.value,
        dispositivo_id=registro.dispositivo_id,
    )
    return registro


def remover(sessao: Session, contexto: repo.Contexto, politica_id: str) -> str:
    contexto.exigir_administracao()
    registro = sessao.execute(
        repo.escopo(Politica, contexto).where(Politica.id == politica_id)
    ).scalar_one_or_none()
    if registro is None:
        msg = "politica nao encontrada nesta organizacao"
        raise PoliticaRecusada(msg)

    nome, dispositivo_id = registro.nome, registro.dispositivo_id
    sessao.delete(registro)
    sessao.flush()
    repo.registrar(
        sessao,
        contexto,
        acao="politica.removida",
        alvo=nome,
        dispositivo_id=dispositivo_id,
    )
    return dispositivo_id


def para_o_agente(
    sessao: Session, contexto: repo.Contexto, dispositivo_id: str
) -> list[dict[str, Any]]:
    """
    Políticas **ativas** deste dispositivo, no formato que o Agente entende.

    Política desativada não é enviada: desativar tem que parar o backup de
    verdade, e não só sumir da lista da tela.
    """
    registros = sessao.execute(
        repo.escopo(Politica, contexto)
        .where(Politica.dispositivo_id == dispositivo_id)
        .where(Politica.ativa.is_(True))
    ).scalars()
    return [
        {
            "id": item.id,
            "nome": item.nome,
            "configuracao": ConfiguracaoDePolitica.de_json(item.configuracao).model_dump(
                mode="json"
            ),
        }
        for item in registros
    ]


# ============================================================
# Rotas
# ============================================================


@roteador.get("")
def listar_politicas(contexto: ContextoAtual, sessao: SessaoBanco) -> dict[str, Any]:
    return {"politicas": listar(sessao, contexto)}


@roteador.post("")
async def criar_politica(
    pedido: PedidoDePolitica, contexto: ContextoAdministrador, sessao: SessaoBanco
) -> dict[str, Any]:
    """Cria a política e tenta mandá-la à máquina na mesma operação."""
    try:
        registro = criar(sessao, contexto, pedido)
    except PoliticaRecusada as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro)) from erro
    return {
        **como_dicionario(registro),
        "sincronizacao": await sincronizar(sessao, contexto, registro.dispositivo_id),
    }


@roteador.put("/{politica_id}")
async def alterar_politica(
    politica_id: str,
    pedido: PedidoDePolitica,
    contexto: ContextoAdministrador,
    sessao: SessaoBanco,
) -> dict[str, Any]:
    try:
        registro = alterar(sessao, contexto, politica_id, pedido)
    except PoliticaRecusada as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro)) from erro
    return {
        **como_dicionario(registro),
        "sincronizacao": await sincronizar(sessao, contexto, registro.dispositivo_id),
    }


@roteador.delete("/{politica_id}")
async def remover_politica(
    politica_id: str, contexto: ContextoAdministrador, sessao: SessaoBanco
) -> dict[str, Any]:
    try:
        dispositivo_id = remover(sessao, contexto, politica_id)
    except PoliticaRecusada as erro:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(erro)) from erro
    return {
        "removida": politica_id,
        "sincronizacao": await sincronizar(sessao, contexto, dispositivo_id),
    }


async def sincronizar(
    sessao: Session, contexto: repo.Contexto, dispositivo_id: str
) -> dict[str, Any]:
    """
    Manda as políticas ativas para a máquina.

    Máquina desligada devolve `pendente`, e não erro: a política sobe na
    próxima conexão. O que não pode é a tela afirmar que já está valendo — a
    diferença entre "vai valer" e "está valendo" é a diferença entre ter
    backup hoje à noite e descobrir amanhã que não teve.
    """
    from . import canal

    politicas = para_o_agente(sessao, contexto, dispositivo_id)
    try:
        resposta = await canal.pedir_ao_dispositivo(
            dispositivo_id, "politicas", {"politicas": politicas}, prazo_s=30.0
        )
    except canal.DispositivoDesconectado:
        return {
            "aplicada": False,
            "motivo": "a maquina esta desligada; a politica vale a partir da proxima conexao",
        }
    except canal.SemResposta:
        return {
            "aplicada": False,
            "motivo": "a maquina nao respondeu a tempo; sera tentado de novo na proxima conexao",
        }

    if not resposta.get("ok"):
        return {"aplicada": False, "motivo": str(resposta.get("erro", "recusada"))}
    return {
        "aplicada": True,
        "politicas": resposta.get("politicas", 0),
        "proximas": resposta.get("proximas", []),
    }


@roteador.post("/sincronizar/{dispositivo_id}")
async def sincronizar_dispositivo(
    dispositivo_id: str, contexto: ContextoAdministrador, sessao: SessaoBanco
) -> dict[str, Any]:
    """Reenvia as políticas para uma máquina, sob pedido."""
    try:
        _dispositivo_da_organizacao(sessao, contexto, dispositivo_id)
    except PoliticaRecusada as erro:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(erro)) from erro
    return await sincronizar(sessao, contexto, dispositivo_id)


__all__ = [
    "PedidoDePolitica",
    "PoliticaRecusada",
    "alterar",
    "como_dicionario",
    "criar",
    "listar",
    "para_o_agente",
    "remover",
    "roteador",
    "sincronizar",
]
