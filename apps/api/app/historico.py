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

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import repositorio as repo
from .db.models import (
    Artefato,
    Dispositivo,
    Execucao,
    Politica,
    ResultadoExecucao,
    agora,
    em_utc,
    momento,
)
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


def _entregas_como_json(brutas: Any) -> str:
    """As entregas relatadas pelo Agente, prontas para guardar. Ver `dispositivos`."""
    from .dispositivos import _entregas_como_json as converter

    return converter(brutas)


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
                    entregas=_entregas_como_json(ficha.get("entregas")),
                )
            )
        sessao.flush()

        # Uma linha por execucao, nomeando o PACOTE.
        #
        # A linha do lote, mais abaixo, diz que houve sincronizacao — util para
        # quem audita o canal, e inutil para quem pergunta "o que prova que
        # este backup de terca aconteceu?". Sem uma linha que nomeie o pacote,
        # o detalhe da execucao so conseguia recortar a trilha por janela de
        # tempo — e o horario da linha e o da SINCRONIZACAO, que pode ser dias
        # depois da execucao numa maquina que ficou sem internet.
        pacote = str(ficha.get("nome", "")) if isinstance(ficha, dict) else ""
        contexto_do_dispositivo = repo.contexto_de_dispositivo(
            sessao, dispositivo_id=dispositivo.id
        )
        repo.registrar(
            sessao,
            contexto_do_dispositivo,
            acao="execucao.registrada",
            alvo=pacote or str(item.get("politica_nome", ""))[:400],
            detalhe=execucao.resultado.value,
            dispositivo_id=dispositivo.id,
        )

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
        "iniciada_em": momento(execucao.iniciada_em),
        "terminada_em": momento(execucao.terminada_em),
        "arquivos": execucao.arquivos_incluidos,
        "bytes_copiados": execucao.bytes_copiados,
        "ressalva": execucao.ressalva,
        "artefatos": [_artefato_como_dicionario(item) for item in artefatos],
    }


def _artefato_como_dicionario(artefato: Artefato) -> dict[str, Any]:
    """
    A ficha do pacote, com o que prova onde ele está.

    O nome e o tamanho dizem que algo foi produzido. O `sha256` e as entregas
    conferidas dizem que o que foi produzido é o que está lá — que é a
    diferença entre um backup e um arquivo com nome de backup.
    """
    import json

    try:
        entregas = json.loads(artefato.entregas) if artefato.entregas else []
    except ValueError:
        entregas = []

    return {
        "id": artefato.id,
        "nome": artefato.nome,
        "tamanho_bytes": artefato.tamanho_bytes,
        "sha256": artefato.sha256,
        "localizacao": artefato.localizacao,
        # Para onde a cópia foi, e se foi conferida lá.
        "entregas": entregas,
        "nuvem_pendente": artefato.nuvem_pendente,
        "nuvem_em": momento(artefato.nuvem_em),
        "nuvem_chave": artefato.nuvem_chave,
        "nuvem_erro": artefato.nuvem_erro,
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


def detalhar(sessao: Session, contexto: repo.Contexto, execucao_id: str) -> dict[str, Any]:
    """
    Uma execução inteira, com o que a sustenta.

    A lista do histórico responde "aconteceu". Esta rota responde a pergunta
    seguinte, que é a que decide se alguém confia: **como eu sei?**

    Por isso ela junta coisas que moram em lugares diferentes — a linha da
    execução, a ficha do pacote com o SHA-256, para onde a cópia foi e se foi
    conferida lá, a política que pediu, e as linhas da trilha encadeada
    daquele momento. Cada uma sozinha é uma afirmação; juntas são um caso.
    """

    execucao = sessao.execute(
        repo.escopo(Execucao, contexto).where(Execucao.id == execucao_id)
    ).scalar_one_or_none()
    if execucao is None:
        msg = "execucao nao encontrada nesta organizacao"
        raise LookupError(msg)

    artefatos = list(
        sessao.execute(select(Artefato).where(Artefato.execucao_id == execucao.id)).scalars()
    )
    corpo = _como_dicionario(execucao, artefatos)

    dispositivo = (
        sessao.get(Dispositivo, execucao.dispositivo_id) if execucao.dispositivo_id else None
    )
    corpo["maquina"] = dispositivo.nome if dispositivo is not None else ""

    politica = sessao.get(Politica, execucao.politica_id) if execucao.politica_id else None
    if politica is not None:
        from autotarefas.tasks.politica import Politica as ConfiguracaoDePolitica

        configuracao = ConfiguracaoDePolitica.de_json(politica.configuracao)
        corpo["politica"] = {
            "id": politica.id,
            "nome": politica.nome,
            # O que a política mandou copiar, para onde, e por quanto tempo
            # guardar. É contra isto que a execução se compara.
            "origens": configuracao.origens,
            "destino": configuracao.destino.model_dump(mode="json"),
            "agendamento": configuracao.agendamento.model_dump(mode="json"),
            "retencao": configuracao.retencao.model_dump(mode="json"),
            "protege_de_verdade": configuracao.protege_de_verdade,
        }
    else:
        corpo["politica"] = None

    corpo["trilha"] = _trilha_da_execucao(sessao, contexto, execucao, artefatos)
    return corpo


#: Folga em torno da execução ao recortar a trilha.
#:
#: A execução tem começo e fim; a trilha registra coisas em volta dela — o
#: pedido que a disparou, a sincronização que a trouxe da máquina, a entrega na
#: nuvem que só aconteceu quando a internet voltou. Um recorte exato pelos
#: instantes de início e fim deixaria de fora justamente o que explica.
FOLGA_DA_TRILHA = timedelta(hours=1)


def _trilha_da_execucao(
    sessao: Session,
    contexto: repo.Contexto,
    execucao: Execucao,
    artefatos: list[Artefato],
) -> list[dict[str, Any]]:
    """
    As linhas da trilha que dizem respeito a esta execução.

    A trilha é encadeada por hash na organização inteira, e é assim que ela
    vale: cada linha carrega o hash da anterior, e alterar uma no meio quebra a
    corrente. Aqui só se **recorta** o que diz respeito a esta execução — nada
    é recalculado, e a corrente continua sendo a da organização.

    O recorte tem dois critérios, e cada um cobre o que o outro não alcança:

    **Pelo nome do pacote.** É o critério forte, e o único que funciona para o
    backup do agendamento: a linha do registro e a da entrega na nuvem nomeiam
    o pacote. A entrega na nuvem pode ter acontecido horas depois, quando a
    internet voltou — e é exatamente uma das coisas que alguém quer ver ao
    perguntar "onde está esta cópia".

    **Pela janela de tempo.** Cobre o `backup.pedido` de uma execução pedida
    pela tela, que acontece ANTES de existir pacote para nomear. Não serve
    sozinho: numa máquina que ficou dias sem internet, a linha do registro tem
    a hora da SINCRONIZAÇÃO, e não a da execução.
    """
    from .db.models import Auditoria

    inicio = em_utc(execucao.iniciada_em) - FOLGA_DA_TRILHA
    fim = em_utc(execucao.terminada_em or execucao.iniciada_em) + FOLGA_DA_TRILHA
    alvos = {item.nome for item in artefatos}

    linhas = sessao.execute(
        repo.escopo(Auditoria, contexto)
        .where(Auditoria.dispositivo_id == execucao.dispositivo_id)
        .order_by(Auditoria.quando.desc())
        .limit(PAGINA)
    ).scalars()

    return [
        {
            "acao": linha.acao,
            "alvo": linha.alvo,
            "detalhe": linha.detalhe,
            "quando": momento(linha.quando),
            "hash_atual": linha.hash_atual,
        }
        for linha in linhas
        if linha.alvo in alvos or inicio <= em_utc(linha.quando) <= fim
    ]


@roteador.get("/execucao/{execucao_id}")
def detalhe_da_execucao(
    execucao_id: str,
    contexto: ContextoAtual,
    sessao: SessaoBanco,
) -> dict[str, Any]:
    """O que aconteceu numa execução, e o que prova que aconteceu."""
    try:
        return detalhar(sessao, contexto, execucao_id)
    except LookupError as erro:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(erro)) from erro


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
                "quando": momento(linha.quando),
                "dispositivo_id": linha.dispositivo_id or "",
            }
            for linha in linhas
        ],
    }


__all__ = ["LOTE_MAXIMO", "PAGINA", "listar", "registrar_do_agente", "roteador"]
