"""Historico: o que cada dispositivo executou, e o que produziu.

Duas fontes alimentam a mesma tabela, e a diferenca entre elas e o ponto desta
etapa:

- **execucao pedida pela tela** — o servidor abre a linha antes de o comando
  sair e a fecha quando a resposta chega;
- **execucao do agendamento** — acontece na maquina, muitas vezes de madrugada
  e com a internet caida. O Agente grava no diario dele e envia quando
  reconecta.

Sem a segunda, o Live mostraria uma noite vazia para uma noite em que o backup
foi feito. O cliente concluiria, com razao, que nao pode confiar na tela — e um
historico em que nao se confia nao serve para nada.

O identificador da execucao e gerado **na maquina**, junto com o registro. E ele
que torna o reenvio inofensivo: o Agente que manda de novo depois de uma queda
no meio do envio nao vira duas linhas no historico.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import repositorio as repo
from .db.models import Artefato, Dispositivo, Execucao, Politica, ResultadoExecucao, agora
from .identidade.dependencias import ContextoAtual, SessaoBanco

#: Quantas execucoes a tela pede por vez. O suficiente para caber uma semana de
#: agendamento diario sem paginar, e pouco o bastante para nao pesar.
PAGINA = 50

#: Teto do que o Agente pode mandar num lote. Uma mensagem maior que isso nao
#: e um Agente sincronizando: e alguem tentando encher o banco.
LOTE_MAXIMO = 100


def _resultado_de(nome: str) -> ResultadoExecucao:
    """
    Traduz o nome vindo do Agente. Desconhecido vira `FALHA`, nunca sucesso.

    Um Agente mais novo pode mandar um resultado que este servidor ainda nao
    conhece. Tratar o desconhecido como sucesso mostraria "backup ok" para algo
    que ninguem sabe o que foi.
    """
    try:
        return ResultadoExecucao(nome)
    except ValueError:
        return ResultadoExecucao.FALHA


def _instante(bruto: str) -> datetime | None:
    """Data que o Agente mandou. Ilegivel vira `None`, e nao a hora de agora."""
    if not bruto:
        return None
    try:
        return datetime.fromisoformat(bruto)
    except ValueError:
        return None


def _politica_valida(sessao: Session, organizacao_id: str, politica_id: str) -> str | None:
    """
    So aceita politica desta organizacao.

    O `politica_id` chega do Agente, e um dispositivo nao pode pendurar a
    execucao dele na politica de outra empresa — nem por engano, nem de
    proposito.
    """
    if not politica_id:
        return None
    politica = sessao.get(Politica, politica_id)
    if politica is None or politica.organizacao_id != organizacao_id:
        return None
    return politica.id


def registrar_do_agente(
    sessao: Session,
    dispositivo: Dispositivo,
    itens: list[dict[str, Any]],
) -> list[str]:
    """
    Grava execucoes que o Agente fez sozinho. Devolve os ids aceitos.

    Um id que **ja existe** tambem volta na lista: para o Agente, "ja esta
    gravado" e "acabou de ser gravado" significam a mesma coisa — pode parar de
    reenviar. Deixa-lo de fora faria o mesmo registro voltar a cada reconexao,
    para sempre.
    """
    aceitos: list[str] = []

    for item in itens[:LOTE_MAXIMO]:
        identificador = str(item.get("id", ""))
        if not identificador or len(identificador) > 32:  # noqa: PLR2004 — tamanho da coluna
            continue

        if sessao.get(Execucao, identificador) is not None:
            aceitos.append(identificador)
            continue

        execucao = Execucao(
            id=identificador,
            organizacao_id=dispositivo.organizacao_id,
            dispositivo_id=dispositivo.id,
            politica_id=_politica_valida(
                sessao, dispositivo.organizacao_id, str(item.get("politica_id", ""))
            ),
            origem=str(item.get("origem", "agendamento"))[:40],
            resultado=_resultado_de(str(item.get("resultado", ""))),
            iniciada_em=_instante(str(item.get("iniciada_em", ""))) or agora(),
            terminada_em=_instante(str(item.get("terminada_em", ""))),
            arquivos_incluidos=int(item.get("arquivos", 0) or 0),
            bytes_copiados=int(item.get("bytes_copiados", 0) or 0),
            ressalva=str(item.get("ressalva", ""))[:2000],
        )
        sessao.add(execucao)
        sessao.flush()

        ficha = item.get("artefato")
        if isinstance(ficha, dict) and ficha.get("nome"):
            sessao.add(
                Artefato(
                    organizacao_id=dispositivo.organizacao_id,
                    execucao_id=execucao.id,
                    nome=str(ficha.get("nome", ""))[:400],
                    tamanho_bytes=int(ficha.get("tamanho_bytes", 0) or 0),
                    sha256=str(ficha.get("sha256", ""))[:64],
                    # O ZIP fica na maquina do cliente. O servidor guarda a
                    # ficha, nunca o conteudo nem o caminho local.
                    localizacao=str(ficha.get("localizacao", "dispositivo"))[:200],
                    # A politica pede nuvem e o pacote ainda esta so na
                    # maquina. Quem sobe e o servidor, pedindo ao Agente assim
                    # que houver canal — ver `nuvem.py`.
                    nuvem_pendente=bool(item.get("nuvem_pendente", False)),
                )
            )
        sessao.flush()
        _avisar_se_precisa(sessao, dispositivo, execucao)
        aceitos.append(identificador)

    if aceitos:
        contexto = repo.contexto_de_dispositivo(sessao, dispositivo_id=dispositivo.id)
        repo.registrar(
            sessao,
            contexto,
            acao="execucao.sincronizada",
            alvo=dispositivo.nome,
            detalhe=f"{len(aceitos)} execucao(oes) do agendamento",
            dispositivo_id=dispositivo.id,
        )

    return aceitos


def _avisar_se_precisa(sessao: Session, dispositivo: Dispositivo, execucao: Execucao) -> None:
    """
    Manda o aviso da politica para o que a maquina executou sozinha.

    E o caso que mais precisa de aviso: a falha de madrugada, que ninguem viu
    acontecer. Avisar so na execucao pedida pela tela faria a notificacao
    funcionar exatamente quando ela nao era necessaria.

    Falha no envio nao derruba a gravacao: o historico e o fato; o e-mail e a
    consequencia. Perder a linha do historico por causa de um SMTP fora do ar
    seria trocar o registro pela cortesia.
    """
    from . import notificacoes

    contexto = repo.contexto_de_dispositivo(sessao, dispositivo_id=dispositivo.id)
    try:
        notificacoes.avisar_execucao(
            sessao, contexto, execucao=execucao, dispositivo=dispositivo.nome
        )
    except Exception:  # noqa: BLE001 — envio de e-mail nao pode derrubar historico
        logger.exception("nao foi possivel avisar sobre a execucao %s", execucao.id)


def listar(
    sessao: Session,
    contexto: repo.Contexto,
    *,
    dispositivo_id: str = "",
    limite: int = PAGINA,
) -> list[dict[str, Any]]:
    """Execucoes desta organizacao, das mais recentes para as antigas."""
    consulta = repo.escopo(Execucao, contexto)
    if dispositivo_id:
        consulta = consulta.where(Execucao.dispositivo_id == dispositivo_id)
    consulta = consulta.order_by(Execucao.iniciada_em.desc(), Execucao.id.desc()).limit(
        max(1, min(limite, PAGINA))
    )

    execucoes = list(sessao.execute(consulta).scalars())
    if not execucoes:
        return []

    por_execucao: dict[str, list[Artefato]] = {}
    encontrados = sessao.execute(
        select(Artefato).where(Artefato.execucao_id.in_([item.id for item in execucoes]))
    ).scalars()
    for artefato in encontrados:
        por_execucao.setdefault(artefato.execucao_id, []).append(artefato)

    return [_como_dicionario(item, por_execucao.get(item.id, [])) for item in execucoes]


def _como_dicionario(execucao: Execucao, artefatos: list[Artefato]) -> dict[str, Any]:
    return {
        "id": execucao.id,
        "dispositivo_id": execucao.dispositivo_id or "",
        "politica_id": execucao.politica_id or "",
        "origem": execucao.origem,
        "resultado": execucao.resultado.value,
        "iniciada_em": execucao.iniciada_em.isoformat() if execucao.iniciada_em else "",
        "terminada_em": execucao.terminada_em.isoformat() if execucao.terminada_em else "",
        "arquivos": execucao.arquivos_incluidos,
        "bytes_copiados": execucao.bytes_copiados,
        "ressalva": execucao.ressalva,
        "artefatos": [
            {
                "id": artefato.id,
                "nome": artefato.nome,
                "tamanho_bytes": artefato.tamanho_bytes,
                "sha256": artefato.sha256,
                "localizacao": artefato.localizacao,
            }
            for artefato in artefatos
        ],
    }


# ============================================================
# Rotas
# ============================================================

roteador = APIRouter(prefix="/api/historico", tags=["historico"])


@roteador.get("")
def historico_da_organizacao(
    contexto: ContextoAtual,
    sessao: SessaoBanco,
    dispositivo_id: str = Query(default="", max_length=32),
    limite: int = Query(default=PAGINA, ge=1, le=PAGINA),
) -> dict[str, Any]:
    """
    Execucoes desta organizacao. Nunca as de outra.

    Inclui as que o Agente fez sozinho, no horario agendado, com o navegador
    fechado — sao elas que provam que o backup nao depende de alguem estar
    olhando.
    """
    if dispositivo_id:
        existe = sessao.execute(
            repo.escopo(Dispositivo, contexto).where(Dispositivo.id == dispositivo_id)
        ).scalar_one_or_none()
        if existe is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="dispositivo nao encontrado"
            )

    return {"execucoes": listar(sessao, contexto, dispositivo_id=dispositivo_id, limite=limite)}


@roteador.get("/auditoria")
def trilha_da_organizacao(
    contexto: ContextoAtual,
    sessao: SessaoBanco,
    limite: int = Query(default=PAGINA, ge=1, le=PAGINA),
) -> dict[str, Any]:
    """
    A trilha do que foi feito, e se ela continua integra.

    A trilha ja era gravada e encadeada por hash desde a G.2.1, mas nao aparecia
    em lugar nenhum — uma evidencia que ninguem consegue olhar nao serve de
    evidencia. `integra` vem junto porque a corrente so vale enquanto se pode
    conferir: mostrar as linhas sem dizer se elas ainda batem seria oferecer
    exatamente a confianca que o encadeamento existe para nao pedir.
    """
    from .db.models import Auditoria

    integra, explicacao = repo.conferir_trilha(sessao, contexto)
    linhas = sessao.execute(
        repo.escopo(Auditoria, contexto)
        .order_by(Auditoria.quando.desc(), Auditoria.id.desc())
        .limit(limite)
    ).scalars()

    return {
        "integra": integra,
        "explicacao": explicacao,
        "linhas": [
            {
                "id": linha.id,
                "acao": linha.acao,
                "alvo": linha.alvo,
                "detalhe": linha.detalhe,
                "quando": linha.quando.isoformat(),
                "dispositivo_id": linha.dispositivo_id or "",
            }
            for linha in linhas
        ],
    }


__all__ = ["LOTE_MAXIMO", "PAGINA", "listar", "registrar_do_agente", "roteador"]
