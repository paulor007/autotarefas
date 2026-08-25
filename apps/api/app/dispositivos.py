"""Pareamento e administracao de dispositivos.

O pareamento resolve um problema especifico: como uma maquina que ninguem
autenticou prova que pertence a uma organizacao. A resposta e um **codigo
temporario**, gerado por quem administra a organizacao no Live e digitado no
Agente, na maquina.

Por que codigo, e nao usuario e senha no Agente. Colocar credencial de pessoa
dentro de um servico que roda sozinho significa guardar essa credencial na
maquina — e ela abriria a organizacao inteira, nao so aquele dispositivo. O
codigo vale uma vez, por poucos minutos, e o que sobra depois dele e o par de
chaves do proprio dispositivo.

Regras do codigo, e o motivo de cada uma:

- **uso unico** — codigo reaproveitado permitiria cadastrar maquinas que
  ninguem autorizou;
- **prazo curto** — codigo esquecido num bilhete deixa de servir sozinho;
- **comparacao em tempo constante** — sem isso, o tempo de resposta conta
  quantos caracteres iniciais o atacante acertou;
- **alfabeto sem ambiguidade** — quem digita `0` achando que e `O` erra o
  pareamento e culpa o produto.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import repositorio as repo
from .db.models import Base, Dispositivo, EstadoDispositivo, Papel, agora, em_utc, novo_id
from .identidade.dependencias import ContextoAdministrador, ContextoAtual, SessaoBanco

#: Alfabeto do codigo: sem 0/O, 1/I/L, que sao os pares que a pessoa troca ao
#: ler de uma tela e digitar em outra maquina.
ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # pragma: allowlist secret

#: Quantos caracteres por bloco, e quantos blocos. `ABCD-EFGH` e ditavel por
#: telefone, que e como isso costuma acontecer numa empresa pequena.
TAMANHO_BLOCO = 4
BLOCOS = 2

#: Minutos de validade. Curto: o codigo e digitado logo depois de gerado.
VALIDADE_MINUTOS = 10


class CodigoDePareamento(Base):
    """
    Codigo temporario que autoriza UMA maquina a entrar numa organizacao.

    Fica no banco, e nao em memoria, porque o servico pode rodar com mais de
    um processo: um codigo gerado num deles precisa ser aceito pelo outro.
    """

    __tablename__ = "codigo_pareamento"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    organizacao_id: Mapped[str] = mapped_column(
        ForeignKey("organizacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    codigo: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    criado_por: Mapped[str | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Dispositivo que nasceu deste codigo. Guardado para a trilha.
    dispositivo_id: Mapped[str | None] = mapped_column(String(32))


class PareamentoRecusado(Exception):
    """O codigo nao serve: inexistente, usado, vencido ou chave repetida."""


def gerar_codigo() -> str:
    """Sorteia um codigo legivel, no formato `ABCD-EFGH`."""
    blocos = [
        "".join(secrets.choice(ALFABETO) for _ in range(TAMANHO_BLOCO)) for _ in range(BLOCOS)
    ]
    return "-".join(blocos)


def normalizar(codigo: str) -> str:
    """
    Aceita o codigo como a pessoa digitou.

    Minusculas, espacos e falta de hifen sao erro de digitacao, nao tentativa
    de invasao. Recusar por causa disso so gera chamado de suporte.
    """
    limpo = "".join(c for c in codigo.upper() if c.isalnum())
    if len(limpo) != TAMANHO_BLOCO * BLOCOS:
        return limpo
    return "-".join(limpo[i : i + TAMANHO_BLOCO] for i in range(0, len(limpo), TAMANHO_BLOCO))


def emitir(sessao: Session, contexto: repo.Contexto) -> CodigoDePareamento:
    """Cria um codigo para a organizacao de quem esta pedindo."""
    contexto.exigir_administracao()
    registro = CodigoDePareamento(
        organizacao_id=contexto.organizacao_id,
        codigo=gerar_codigo(),
        criado_por=contexto.usuario_id,
        expira_em=agora() + timedelta(minutes=VALIDADE_MINUTOS),
    )
    sessao.add(registro)
    sessao.flush()
    repo.registrar(
        sessao,
        contexto,
        acao="pareamento.codigo_emitido",
        detalhe=f"valido por {VALIDADE_MINUTOS} minutos",
    )
    return registro


def _achar_codigo(sessao: Session, digitado: str) -> CodigoDePareamento:
    """
    Acha o codigo, sem deixar o tempo de resposta contar segredo.

    A busca por igualdade no banco ja e indexada; a comparacao em tempo
    constante entra depois, sobre o valor encontrado, para o caminho em que
    alguem tente adivinhar caractere a caractere.
    """
    candidato = sessao.execute(
        select(CodigoDePareamento).where(CodigoDePareamento.codigo == digitado)
    ).scalar_one_or_none()
    if candidato is None or not secrets.compare_digest(candidato.codigo, digitado):
        msg = "codigo de pareamento invalido"
        raise PareamentoRecusado(msg)
    return candidato


def parear(  # noqa: PLR0913 — cada parametro e um campo do dispositivo que o
    # servidor precisa registrar; agrupa-los num objeto so tornaria a chamada
    # menos legivel exatamente onde a leitura importa.
    sessao: Session,
    *,
    codigo: str,
    chave_publica: str,
    nome: str,
    sistema: str,
    versao_agente: str,
    momento: datetime | None = None,
) -> Dispositivo:
    """
    Consome o codigo e registra o dispositivo.

    Nao exige sessao de pessoa: quem apresenta um codigo valido esta provando
    que alguem com poder de administracao o entregou. O que o dispositivo
    ganha e um lugar na organizacao, nao poder de configurar nada — ele age
    como operador.
    """
    instante = momento or agora()
    registro = _achar_codigo(sessao, normalizar(codigo))

    if registro.usado_em is not None:
        msg = "este codigo ja foi usado"
        raise PareamentoRecusado(msg)
    if instante > em_utc(registro.expira_em):
        msg = "este codigo venceu"
        raise PareamentoRecusado(msg)

    ja_existe = sessao.execute(
        select(Dispositivo).where(Dispositivo.chave_publica == chave_publica)
    ).scalar_one_or_none()
    if ja_existe is not None:
        # A mesma maquina nao pode aparecer em duas organizacoes: seria um
        # caminho para ler o backup de uma empresa a partir de outra.
        msg = "esta maquina ja esta pareada"
        raise PareamentoRecusado(msg)

    dispositivo = Dispositivo(
        organizacao_id=registro.organizacao_id,
        nome=nome.strip() or "Dispositivo sem nome",
        chave_publica=chave_publica,
        sistema=sistema,
        versao_agente=versao_agente,
        estado=EstadoDispositivo.ATIVO,
        pareado_em=instante,
        ultimo_contato=instante,
    )
    sessao.add(dispositivo)
    sessao.flush()

    registro.usado_em = instante
    registro.dispositivo_id = dispositivo.id

    contexto = repo.Contexto(
        organizacao_id=registro.organizacao_id, usuario_id=None, papel=Papel.OPERADOR
    )
    repo.registrar(
        sessao,
        contexto,
        acao="dispositivo.pareado",
        alvo=dispositivo.nome,
        detalhe=f"{sistema} · agente {versao_agente}",
        dispositivo_id=dispositivo.id,
    )
    return dispositivo


def revogar(sessao: Session, contexto: repo.Contexto, *, dispositivo_id: str) -> Dispositivo:
    """
    Tira o dispositivo de servico.

    Revogar nao apaga: o historico de execucoes precisa continuar apontando
    para uma maquina identificavel, senao a auditoria fica com buracos.
    """
    contexto.exigir_administracao()
    dispositivo = sessao.execute(
        repo.escopo(Dispositivo, contexto).where(Dispositivo.id == dispositivo_id)
    ).scalar_one_or_none()
    if dispositivo is None:
        msg = "dispositivo nao encontrado nesta organizacao"
        raise PareamentoRecusado(msg)

    dispositivo.estado = EstadoDispositivo.REVOGADO
    sessao.flush()
    repo.registrar(
        sessao,
        contexto,
        acao="dispositivo.revogado",
        alvo=dispositivo.nome,
        dispositivo_id=dispositivo.id,
    )
    return dispositivo


def listar(sessao: Session, contexto: repo.Contexto) -> list[dict[str, Any]]:
    """Dispositivos da organizacao, com o que a tela precisa mostrar."""
    registros = sessao.execute(
        repo.escopo(Dispositivo, contexto).order_by(Dispositivo.criado_em.asc())
    ).scalars()
    return [
        {
            "id": item.id,
            "nome": item.nome,
            "sistema": item.sistema,
            "versao_agente": item.versao_agente,
            "estado": item.estado.value,
            "impressao": impressao_de(item.chave_publica),
            "pareado_em": item.pareado_em.isoformat() if item.pareado_em else "",
            "ultimo_contato": item.ultimo_contato.isoformat() if item.ultimo_contato else "",
        }
        for item in registros
    ]


def impressao_de(chave_publica: str) -> str:
    """
    Impressao legivel da chave publica, no mesmo formato que o Agente mostra.

    E o que permite a pessoa comparar a tela com a maquina e perceber que
    esta olhando para o dispositivo errado.
    """
    import base64
    import hashlib

    try:
        bruta = base64.b64decode(chave_publica.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return ""
    digesto = hashlib.sha256(bruta).hexdigest()[:16].upper()
    return "-".join(digesto[i : i + 4] for i in range(0, len(digesto), 4))


# ============================================================
# Rotas
# ============================================================

roteador = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])


class PedidoDePareamento(BaseModel):
    """O que o Agente envia ao parear."""

    codigo: str = Field(min_length=4, max_length=32)
    chave_publica: str = Field(min_length=16, max_length=120)
    nome: str = Field(default="", max_length=200)
    sistema: str = Field(default="", max_length=120)
    versao_agente: str = Field(default="", max_length=40)


@roteador.get("")
def listar_dispositivos(contexto: ContextoAtual, sessao: SessaoBanco) -> dict[str, Any]:
    """Dispositivos desta organizacao. Nunca os de outra."""
    return {"dispositivos": listar(sessao, contexto)}


@roteador.post("/codigo")
def emitir_codigo(contexto: ContextoAdministrador, sessao: SessaoBanco) -> dict[str, Any]:
    """Gera um codigo de pareamento. So quem administra a organizacao."""
    registro = emitir(sessao, contexto)
    return {
        "codigo": registro.codigo,
        "expira_em": registro.expira_em.isoformat(),
        "validade_minutos": VALIDADE_MINUTOS,
    }


@roteador.post("/parear")
def parear_dispositivo(pedido: PedidoDePareamento, sessao: SessaoBanco) -> dict[str, Any]:
    """
    Registra o dispositivo a partir de um codigo valido.

    Sem sessao de pessoa, de proposito: o codigo E a autorizacao. O Agente
    roda numa maquina onde ninguem esta logado no Live.
    """
    try:
        dispositivo = parear(
            sessao,
            codigo=pedido.codigo,
            chave_publica=pedido.chave_publica,
            nome=pedido.nome,
            sistema=pedido.sistema,
            versao_agente=pedido.versao_agente,
        )
    except PareamentoRecusado as erro:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(erro)) from erro

    return {
        "dispositivo_id": dispositivo.id,
        "organizacao_id": dispositivo.organizacao_id,
        "nome": dispositivo.nome,
        "impressao": impressao_de(dispositivo.chave_publica),
    }


@roteador.post("/{dispositivo_id}/consultar")
async def consultar_dispositivo(
    dispositivo_id: str, contexto: ContextoAtual, sessao: SessaoBanco
) -> dict[str, Any]:
    """
    Pergunta ao dispositivo o que ele sabe sobre si mesmo, agora.

    Distingue tres situacoes que a tela precisa mostrar diferente:

    - o dispositivo nao e desta organizacao -> 404;
    - o dispositivo existe mas esta **desligado** -> 409, e nao erro. Maquina
      desligada e situacao normal, nao falha;
    - o dispositivo esta no ar mas nao respondeu no prazo -> 504.
    """
    from . import canal

    existe = sessao.execute(
        repo.escopo(Dispositivo, contexto).where(Dispositivo.id == dispositivo_id)
    ).scalar_one_or_none()
    if existe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="dispositivo nao encontrado"
        )

    try:
        resposta = await canal.pedir_ao_dispositivo(dispositivo_id, "estado", prazo_s=30.0)
    except canal.DispositivoDesconectado as erro:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(erro)) from erro
    except canal.SemResposta as erro:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(erro)) from erro

    return {"dispositivo_id": dispositivo_id, "estado": resposta}


@roteador.post("/{dispositivo_id}/revogar")
def revogar_dispositivo(
    dispositivo_id: str, contexto: ContextoAdministrador, sessao: SessaoBanco
) -> dict[str, Any]:
    """Tira o dispositivo de servico, sem apagar o historico dele."""
    try:
        dispositivo = revogar(sessao, contexto, dispositivo_id=dispositivo_id)
    except PareamentoRecusado as erro:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(erro)) from erro
    return {"id": dispositivo.id, "estado": dispositivo.estado.value}


__all__ = [
    "ALFABETO",
    "VALIDADE_MINUTOS",
    "CodigoDePareamento",
    "PareamentoRecusado",
    "emitir",
    "gerar_codigo",
    "impressao_de",
    "listar",
    "normalizar",
    "parear",
    "revogar",
    "roteador",
]
