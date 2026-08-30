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
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import cofre
from .db import repositorio as repo
from .db.models import (
    Artefato,
    Base,
    Dispositivo,
    EstadoDispositivo,
    Execucao,
    Papel,
    ResultadoExecucao,
    agora,
    em_utc,
    momento,
    novo_id,
)
from .identidade.dependencias import (
    ContextoAdministrador,
    ContextoAtual,
    ContextoOperador,
    SessaoBanco,
)

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
            "pareado_em": momento(item.pareado_em),
            "ultimo_contato": momento(item.ultimo_contato),
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
        "expira_em": momento(registro.expira_em),
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


class PedidoDeBackup(BaseModel):
    """O que a tela manda ao pedir um backup agora."""

    #: Vazio = usa as pastas autorizadas na maquina. O Agente recusa qualquer
    #: caminho que nao esteja autorizado la, venha ele daqui ou nao.
    origens: list[str] = Field(default_factory=list)
    destino: str = ""
    #: Ler de um instantaneo de volume, para copiar arquivo aberto. O Agente
    #: RECUSA quando nao tem privilegio, em vez de cair para o modo antigo em
    #: silencio — o pacote sairia sem a planilha aberta, marcado como sucesso.
    usar_vss: bool = False
    #: Para onde COPIAR o pacote depois de pronto: disco externo, pasta de
    #: rede, ou outra pasta local. O Agente confere o destino ANTES de ler o
    #: primeiro arquivo, e confere a copia DEPOIS de gravar.
    destino_externo: str = ""
    tipo_do_destino: str = ""
    #: Enviar tambem para a nuvem configurada no cofre desta organizacao. A
    #: credencial NAO vem no pedido: ela sai do cofre no servidor e viaja pelo
    #: canal autenticado. Se viesse daqui, o navegador teria que guardar a
    #: chave de nuvem do cliente.
    enviar_para_nuvem: bool = False
    #: Copiar so o que mudou. Existe aqui para o "executar agora" de uma
    #: politica se comportar como a execucao agendada dela: um botao que roda
    #: diferente do horario faria o cliente testar outra coisa.
    incremental: bool = False
    #: De qual politica veio o pedido, quando veio de uma.
    #:
    #: Sem isto, "Executar agora" numa politica produzia uma execucao ORFA: o
    #: historico mostrava a linha, mas ela nao pertencia a politica nenhuma. E
    #: o veredito de protecao agrupa por politica — entao um backup que
    #: acabara de rodar com sucesso deixava a politica dele em "nunca concluiu
    #: uma execucao", que e o oposto do que tinha acabado de acontecer.
    #:
    #: Vazio continua valido: o botao da tela de maquinas roda um backup avulso,
    #: que nao pertence a politica alguma.
    politica_id: str = ""


def _politica_citada(sessao: Session, contexto: repo.Contexto, politica_id: str) -> Any:
    """
    O registro da politica citada, se ela for desta organizacao.

    Existe separado de `_politica_da_organizacao` porque o pedido precisa de
    duas coisas dela: o id, que vira a pasta dos pacotes na maquina, e o nome,
    que vira o marcador dentro dessa pasta.
    """
    if not politica_id:
        return None
    from .politicas import Politica as RegistroDePolitica

    return sessao.execute(
        repo.escopo(RegistroDePolitica, contexto).where(RegistroDePolitica.id == politica_id)
    ).scalar_one_or_none()


def _politica_da_organizacao(
    sessao: Session, contexto: repo.Contexto, politica_id: str
) -> str | None:
    """
    Confirma que a politica citada e desta organizacao. `None` se nao for.

    Conferir, e nao confiar: aceitar o id como veio deixaria uma execucao de
    uma empresa carimbada com a politica de outra — e o veredito de protecao,
    que agrupa por politica, passaria a somar coisas de organizacoes
    diferentes.

    `None`, e nao string vazia. A coluna e chave estrangeira: `""` nao e nulo,
    e o SQLite com `PRAGMA foreign_keys=ON` recusa a insercao inteira porque
    nao existe politica de id "". O backup avulso — sem politica — morria
    assim, e o erro nao falava de politica nenhuma.
    """
    achada = _politica_citada(sessao, contexto, politica_id)
    return str(achada.id) if achada is not None else None


def _parametros_do_backup(pedido: PedidoDeBackup, politica: Any = None) -> dict[str, Any]:
    """
    So o que foi realmente pedido.

    Campo vazio nao entra: o Agente tem padroes proprios — as pastas
    autorizadas, a pasta de pacotes ao lado delas — e mandar `""` os
    sobrescreveria com nada.
    """
    escolhas: dict[str, Any] = {
        "origens": pedido.origens,
        "destino": pedido.destino,
        "usar_vss": pedido.usar_vss,
        "incremental": pedido.incremental,
        "destino_externo": pedido.destino_externo,
        "tipo_do_destino": pedido.tipo_do_destino,
        # Vai para a maquina, e nao so para o banco: e o `politica_id` que
        # decide em qual pasta o pacote cai. Sem ele, o "executar agora" de
        # uma politica gravaria na raiz, fora do alcance da retencao dessa
        # mesma politica — e o pacote ficaria la para sempre, sem dono.
        "politica_id": str(politica.id) if politica is not None else "",
        "politica_nome": str(politica.nome) if politica is not None else "",
    }
    return {chave: valor for chave, valor in escolhas.items() if valor}


@roteador.post("/{dispositivo_id}/backup")
async def executar_backup_agora(
    dispositivo_id: str,
    pedido: PedidoDeBackup,
    contexto: ContextoOperador,
    sessao: SessaoBanco,
) -> JSONResponse:
    """
    Pede ao dispositivo um backup agora, e registra a execucao.

    A execucao e gravada ANTES de o comando sair, e fechada quando a resposta
    chega. Se o servidor cair no meio, sobra uma execucao "em andamento" — o
    que e verdade — em vez de nenhum registro de que alguem mandou copiar.
    """
    from . import canal

    dispositivo = sessao.execute(
        repo.escopo(Dispositivo, contexto).where(Dispositivo.id == dispositivo_id)
    ).scalar_one_or_none()
    if dispositivo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="dispositivo nao encontrado"
        )
    if dispositivo.estado is EstadoDispositivo.REVOGADO:
        # Antes de abrir a execucao: uma maquina revogada nao vai copiar nada, e
        # registrar a tentativa como execucao encheria o historico de linhas que
        # nunca tiveram chance. A recusa tambem precisa dizer o motivo CERTO —
        # "nao ha canal aberto" mandaria a pessoa conferir o cabo de rede de uma
        # maquina que ela mesma tirou de servico.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="este dispositivo foi revogado; pareie novamente para voltar a usar",
        )

    # Conferida uma vez, usada nos dois lugares: na linha da execucao e no
    # pedido que vai para a maquina. Mandar o id como veio deixaria o cliente
    # escolher em que pasta do disco alheio o Agente escreve.
    politica = _politica_citada(sessao, contexto, pedido.politica_id)

    execucao = Execucao(
        organizacao_id=contexto.organizacao_id,
        dispositivo_id=dispositivo_id,
        politica_id=str(politica.id) if politica is not None else None,
        origem="manual",
        resultado=ResultadoExecucao.EM_ANDAMENTO,
    )
    sessao.add(execucao)
    sessao.flush()
    repo.registrar(
        sessao,
        contexto,
        acao="backup.pedido",
        alvo=dispositivo.nome,
        dispositivo_id=dispositivo_id,
    )

    parametros = _parametros_do_backup(pedido, politica)
    if pedido.enviar_para_nuvem:
        try:
            parametros["s3"] = credencial_de_nuvem(sessao, contexto)
        except cofre.CofreTrancado as erro:
            return _falhou(sessao, execucao, erro, status.HTTP_409_CONFLICT)
        except cofre.SegredoAusente as erro:
            return _falhou(sessao, execucao, erro, status.HTTP_409_CONFLICT)

    try:
        resposta = await canal.pedir_ao_dispositivo(dispositivo_id, "backup", parametros)
    except canal.DispositivoDesconectado as erro:
        return _falhou(sessao, execucao, erro, status.HTTP_409_CONFLICT)
    except canal.SemResposta as erro:
        return _falhou(sessao, execucao, erro, status.HTTP_504_GATEWAY_TIMEOUT)

    if not resposta.get("ok"):
        _fechar(sessao, execucao, ResultadoExecucao.FALHA, str(resposta.get("erro", "")))
        return JSONResponse(
            {"execucao_id": execucao.id, "ok": False, "erro": resposta.get("erro", "")}
        )

    _registrar_pacote(sessao, contexto, execucao, resposta)
    aviso = _avisar(sessao, contexto, execucao, dispositivo.nome)
    return JSONResponse(
        {
            "execucao_id": execucao.id,
            "ok": True,
            "pacote": resposta.get("pacote", ""),
            "aviso": aviso,
        }
    )


def _avisar(
    sessao: Session, contexto: repo.Contexto, execucao: Execucao, dispositivo: str
) -> dict[str, Any]:
    """
    Avisa quem a politica pediu.

    A regra mora em `notificacoes` porque a execucao do agendamento — a que
    ninguem viu acontecer — precisa exatamente da mesma coisa.
    """
    from . import notificacoes

    return notificacoes.avisar_execucao(
        sessao, contexto, execucao=execucao, dispositivo=dispositivo
    )


def _falhou(sessao: Session, execucao: Execucao, erro: Exception, codigo: int) -> JSONResponse:
    """
    Fecha a execucao como falha e responde — sem levantar.

    Levantar `HTTPException` aqui desfaria a gravacao: a sessao da requisicao
    reverte tudo quando a excecao sobe, e o registro da tentativa sumiria
    junto. "Mandei fazer backup e nada aconteceu" viraria uma conversa sem
    evidencia nenhuma.
    """
    _fechar(sessao, execucao, ResultadoExecucao.FALHA, str(erro))
    return JSONResponse(
        {"execucao_id": execucao.id, "ok": False, "erro": str(erro), "detail": str(erro)},
        status_code=codigo,
    )


#: Nomes dos segredos de nuvem no cofre da organizacao. Fixos de proposito:
#: a tela grava com estes nomes e o backup le com estes nomes, sem inventar
#: convencao no meio do caminho.
SEGREDOS_DE_NUVEM = (
    "s3.endpoint",
    "s3.regiao",
    "s3.balde",
    "s3.chave",
    "s3.segredo",
    "s3.prefixo",
)

#: Os que nao podem faltar. Endpoint vazio significa Amazon S3; prefixo vazio
#: significa raiz do balde. Balde, chave e segredo nao tem substituto.
OBRIGATORIOS_DE_NUVEM = ("s3.balde", "s3.chave", "s3.segredo")


def credencial_de_nuvem(sessao: Session, contexto: repo.Contexto) -> dict[str, str]:
    """
    Le a credencial de nuvem do cofre desta organizacao.

    Ela sai daqui e vai para o Agente pelo canal autenticado — nunca passa
    pelo navegador. Se passasse, a chave de nuvem do cliente ficaria na tela
    dele a cada configuracao, e no histórico do navegador junto.
    """
    faltando = [
        nome for nome in OBRIGATORIOS_DE_NUVEM if not cofre.existe(sessao, contexto, nome=nome)
    ]
    if faltando:
        msg = "destino em nuvem nao configurado nesta organizacao: falta " + ", ".join(
            nome.removeprefix("s3.") for nome in faltando
        )
        raise cofre.SegredoAusente(msg)

    valores: dict[str, str] = {}
    for nome in SEGREDOS_DE_NUVEM:
        if cofre.existe(sessao, contexto, nome=nome):
            valores[nome.removeprefix("s3.")] = cofre.revelar(sessao, contexto, nome=nome)
    return valores


def _fechar(
    sessao: Session, execucao: Execucao, resultado: ResultadoExecucao, ressalva: str
) -> None:
    """Encerra a execucao com o desfecho e o motivo."""
    execucao.resultado = resultado
    execucao.terminada_em = agora()
    execucao.ressalva = ressalva
    sessao.flush()


def _entregas_como_json(brutas: Any) -> str:
    """
    As entregas que o Agente relatou, prontas para guardar.

    Guardar isto e o que faz a conferencia no destino virar EVIDENCIA em vez de
    um acontecimento que ninguem consegue mais consultar. Formato invalido vira
    vazio: um campo de evidencia com lixo dentro e pior do que um campo vazio,
    porque parece resposta.
    """
    import json

    if not isinstance(brutas, list):
        return ""
    limpas = [item for item in brutas if isinstance(item, dict)]
    return json.dumps(limpas, ensure_ascii=False) if limpas else ""


def _registrar_pacote(
    sessao: Session,
    contexto: repo.Contexto,
    execucao: Execucao,
    resposta: dict[str, Any],
) -> None:
    """
    Guarda a ficha do pacote. O conteudo fica na maquina do cliente (H-4).

    `COM_RESSALVA` e um desfecho proprio: backup que copiou quase tudo nao e
    sucesso nem falha, e chamar de sucesso esconderia o que ficou de fora.
    """
    nao_lidos = resposta.get("nao_lidos") or []
    _fechar(
        sessao,
        execucao,
        ResultadoExecucao.COM_RESSALVA if nao_lidos else ResultadoExecucao.SUCESSO,
        f"{len(nao_lidos)} arquivo(s) nao entraram no pacote" if nao_lidos else "",
    )
    execucao.arquivos_incluidos = int(resposta.get("arquivos", 0))
    execucao.bytes_copiados = int(resposta.get("tamanho_bytes", 0))

    sessao.add(
        Artefato(
            organizacao_id=contexto.organizacao_id,
            execucao_id=execucao.id,
            nome=str(resposta.get("pacote", "")),
            tamanho_bytes=int(resposta.get("tamanho_bytes", 0)),
            sha256=str(resposta.get("sha256", "")),
            # Onde o pacote esta, do ponto de vista do DISPOSITIVO. Nunca um
            # caminho do servidor, e nunca o caminho completo da maquina.
            localizacao="dispositivo",
            entregas=_entregas_como_json(resposta.get("entregas")),
        )
    )
    sessao.flush()


class PedidoDeRestauracao(BaseModel):
    """O que a tela envia ao restaurar."""

    pacote: str = Field(min_length=1)
    destino: str = Field(min_length=1)
    #: Pacotes anteriores da corrente, quando o backup e incremental.
    anteriores: list[str] = Field(default_factory=list)
    #: Restaurar so estes arquivos. Vazio = tudo. E como se testa um backup
    #: sem tocar no que esta em producao.
    apenas: list[str] = Field(default_factory=list)
    #: Substituir o que ja existir no destino. Padrao: preservar. Restaurar
    #: por cima e decisao de quem esta ali, e por isso e explicita.
    sobrescrever: bool = False
    #: Pasta de pacotes do DESTINO, na maquina. Com `sobrescrever`, e ela que
    #: prova que existe backup recente e conferido daquilo que sera
    #: substituido. Sem prova, o Agente bloqueia.
    protecao: str = ""
    #: O caminho da TELA: ela nao conhece pasta nenhuma da maquina, entao pede
    #: "confira nos meus pacotes" e o Agente resolve qual pasta e essa.
    conferir_backup: bool = False
    #: Saida explicita da guarda, com o motivo. Fica na trilha de auditoria:
    #: uma protecao sem saida as pessoas desligam de vez, e uma saida sem
    #: registro ninguem sabe se estava ligada.
    dispensar_protecao: str = ""


@roteador.post("/{dispositivo_id}/pacotes")
async def listar_pacotes_do_dispositivo(
    dispositivo_id: str,
    contexto: ContextoAtual,
    sessao: SessaoBanco,
) -> JSONResponse:
    """
    Quais pacotes existem NAQUELA maquina, agora.

    Vem do dispositivo, e nao do banco: o servidor guarda a ficha do artefato,
    mas quem sabe se o arquivo ainda esta la e a maquina. Listar do banco
    ofereceria para restaurar um pacote que alguem ja apagou.
    """
    return await _pedir_ao_dispositivo(sessao, contexto, dispositivo_id, "pacotes", {})


class PedidoDePacote(BaseModel):
    """O que a tela envia para so OLHAR dentro de um pacote."""

    #: Nome do pacote, e nunca um caminho: quem sabe onde o arquivo esta e a
    #: maquina. Ver `2.13` no roadmap.
    pacote: str = Field(min_length=1, max_length=400)


@roteador.post("/{dispositivo_id}/pacote")
async def listar_pacote(
    dispositivo_id: str,
    pedido: PedidoDePacote,
    contexto: ContextoAtual,
    sessao: SessaoBanco,
) -> JSONResponse:
    """
    Mostra o que ha dentro de um pacote, antes de restaurar.

    Modelo proprio, e nao o da restauracao: exigir um `destino` para uma
    operacao que so le seria pedir uma informacao que nao vai ser usada — e a
    tela teria que inventar um valor para preencher o campo.
    """
    return await _pedir_ao_dispositivo(
        sessao,
        contexto,
        dispositivo_id,
        "listar_pacote",
        {"pacote": pedido.pacote},
    )


@roteador.post("/{dispositivo_id}/restaurar")
async def restaurar_no_dispositivo(
    dispositivo_id: str,
    pedido: PedidoDeRestauracao,
    contexto: ContextoOperador,
    sessao: SessaoBanco,
) -> JSONResponse:
    """
    Restaura arquivos de um pacote para uma pasta da maquina.

    Exige papel de operador — e o Agente ainda confere, na maquina, se pacote
    e destino estao em pastas autorizadas. Escrever no disco do cliente e a
    operacao mais perigosa do produto, e ela nao pode ter porta mais larga que
    a de ler.
    """
    return await _pedir_ao_dispositivo(
        sessao,
        contexto,
        dispositivo_id,
        "restaurar",
        {
            "pacote": pedido.pacote,
            "destino": pedido.destino,
            "anteriores": pedido.anteriores,
            "apenas": pedido.apenas,
            "sobrescrever": pedido.sobrescrever,
            "protecao": pedido.protecao,
            "conferir_backup": pedido.conferir_backup,
            "dispensar_protecao": pedido.dispensar_protecao,
        },
        prazo_s=1800.0,
    )


async def _pedir_ao_dispositivo(  # noqa: PLR0913 — sessao, contexto,
    # dispositivo, acao, parametros e prazo sao seis coisas distintas;
    # agrupa-las esconderia o que esta sendo pedido a quem.
    sessao: Session,
    contexto: repo.Contexto,
    dispositivo_id: str,
    acao: str,
    parametros: dict[str, Any],
    *,
    prazo_s: float = 60.0,
) -> JSONResponse:
    """
    Encaminha um pedido ao Agente, com as tres respostas que a tela distingue.

    404 nao e desta organizacao; 409 a maquina esta desligada (situacao
    normal); 504 esta no ar e nao respondeu. Colapsar os tres num "erro"
    faria a tela acusar problema quando o computador esta so fechado.
    """
    from . import canal

    existe = sessao.execute(
        repo.escopo(Dispositivo, contexto).where(Dispositivo.id == dispositivo_id)
    ).scalar_one_or_none()
    if existe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="dispositivo nao encontrado"
        )
    if existe.estado is EstadoDispositivo.REVOGADO:
        # Sem esta linha, revogar seria enfeite: a maquina com o canal ja
        # aberto continuaria executando backup e restauracao normalmente.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="este dispositivo foi revogado; pareie novamente para voltar a usar",
        )

    try:
        resposta = await canal.pedir_ao_dispositivo(
            dispositivo_id, acao, parametros, prazo_s=prazo_s
        )
    except canal.DispositivoDesconectado as erro:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(erro)) from erro
    except canal.SemResposta as erro:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(erro)) from erro

    repo.registrar(
        sessao,
        contexto,
        acao=f"dispositivo.{acao}",
        alvo=existe.nome,
        detalhe="ok" if resposta.get("ok") else str(resposta.get("erro", "")),
        dispositivo_id=dispositivo_id,
    )
    return JSONResponse(resposta)


@roteador.post("/{dispositivo_id}/revogar")
async def revogar_dispositivo(
    dispositivo_id: str, contexto: ContextoAdministrador, sessao: SessaoBanco
) -> dict[str, Any]:
    """
    Tira o dispositivo de servico, e corta o que ja estava aberto.

    Marcar no banco so valeria na PROXIMA conexao, e uma maquina conectada pode
    ficar assim por dias. A chave privada esta na maquina do cliente: se o corte
    nao acontecer aqui, ele nao acontece.
    """
    from . import canal

    try:
        dispositivo = revogar(sessao, contexto, dispositivo_id=dispositivo_id)
    except PareamentoRecusado as erro:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(erro)) from erro

    desconectado = await canal.presenca.expulsar(dispositivo_id, canal.FECHAR_DISPOSITIVO_INATIVO)
    return {
        "id": dispositivo.id,
        "estado": dispositivo.estado.value,
        # Dito em voz alta: e a diferenca entre "cortei agora" e "vai cortar
        # quando a maquina tentar voltar".
        "desconectado": desconectado,
    }


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
