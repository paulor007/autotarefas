"""Entrega diferida na nuvem: o pacote sobe quando há canal, não quando há vontade.

Duas decisões do produto pareciam, juntas, impedir backup **agendado** com
destino na nuvem. Vale a pena registrar as duas, porque nenhuma delas era o
problema:

- **O agendamento roda offline.** Se dependesse do canal, o backup pararia toda
  vez que a internet caísse — que é justamente a madrugada em que ninguém está
  olhando. Essa é a diferença entre "backup automático" e "backup enquanto
  tudo estiver bem".
- **O Agente não grava chave de nuvem em disco.** A credencial mora no cofre da
  organização, aqui no servidor. Guardá-la na máquina do cliente espalharia o
  segredo por tantos discos quantas forem as máquinas.

O que destrava é notar que **o que precisa de rede é o envio, e não o backup**.
Então o agendamento faz o pacote sozinho, e o envio acontece depois: o servidor
vê que há pacote pendente, manda a credencial pelo canal autenticado, o Agente
sobe o arquivo, confere o objeto lendo-o de volta, e a credencial some com a
resposta.

Isso cria uma janela real — pacote feito, ainda não subiu — e a janela aparece
como tal no painel. É o oposto do que havia antes desta correção: uma política
com destino na nuvem contava como "Protegido" desde o instante em que era
salva, para uma cópia que nunca saía do computador.

Duas garantias:

**Reenvio é seguro.** A chave do objeto é derivada do nome do pacote, então
subir de novo sobrescreve o mesmo objeto em vez de multiplicar cópias. Uma
queda de rede no meio de um envio não deixa lixo permanente no balde.

**Falha não vira sucesso.** Erro de envio fica gravado no artefato, o pacote
continua pendente, e a próxima conexão tenta de novo. O painel continua
dizendo que a cópia ainda não saiu.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.models import Artefato, Dispositivo, Execucao, Politica, agora

if TYPE_CHECKING:  # pragma: no cover — só para o verificador de tipos
    pass

#: Quantos pacotes pendentes tentar por rodada.
#:
#: Uma máquina que ficou uma semana sem internet volta com uma fila. Subir tudo
#: de uma vez seguraria o canal por minutos e atrasaria comando de quem está
#: olhando a tela agora. O que sobrar vai na próxima conexão.
POR_RODADA = 5

#: Quanto esperar por um envio. Generoso de propósito: é upload de arquivo
#: grande por rede do cliente, e não uma consulta.
PRAZO_S = 600.0


def pendentes(sessao: Session, dispositivo_id: str, limite: int = POR_RODADA) -> list[Artefato]:
    """
    Pacotes desta máquina que a política mandou para a nuvem e ainda não foram.

    Do mais novo para o mais velho: se a fila for maior do que cabe numa
    rodada, a cópia mais recente é a que mais importa ter fora do prédio.
    """
    consulta = (
        select(Artefato)
        .join(Execucao, Artefato.execucao_id == Execucao.id)
        .where(
            Execucao.dispositivo_id == dispositivo_id,
            Artefato.nuvem_pendente.is_(True),
            Artefato.nuvem_em.is_(None),
        )
        .order_by(Artefato.criado_em.desc())
        .limit(limite)
    )
    return list(sessao.execute(consulta).scalars().all())


def ha_pendencia(sessao: Session, politica_id: str) -> bool:
    """Esta política tem pacote esperando para subir?"""
    if not politica_id:
        return False
    consulta = (
        select(Artefato.id)
        .join(Execucao, Artefato.execucao_id == Execucao.id)
        .where(
            Execucao.politica_id == politica_id,
            Artefato.nuvem_pendente.is_(True),
            Artefato.nuvem_em.is_(None),
        )
        .limit(1)
    )
    return sessao.execute(consulta).first() is not None


def _organizacao_do(sessao: Session, dispositivo_id: str) -> Dispositivo | None:
    return sessao.get(Dispositivo, dispositivo_id)


async def entregar_pendentes(sessao: Session, dispositivo_id: str) -> dict[str, Any]:
    """
    Sobe o que estiver pendente nesta máquina, se houver credencial e canal.

    Silenciosa por natureza: roda quando a máquina reconecta, sem ninguém
    olhando. Por isso nunca levanta — máquina desligada, cofre trancado e
    organização sem credencial são situações normais, e a resposta certa para
    todas é "não deu para subir agora", com o pacote seguindo pendente.
    """
    from . import canal, cofre
    from .db import repositorio as repo
    from .dispositivos import credencial_de_nuvem

    dispositivo = _organizacao_do(sessao, dispositivo_id)
    if dispositivo is None:
        return {"enviados": 0, "motivo": "dispositivo desconhecido"}

    fila = pendentes(sessao, dispositivo_id)
    if not fila:
        return {"enviados": 0}

    # Contexto do DISPOSITIVO, e nao de um usuario: esta rotina nao nasce de
    # pedido de ninguem. E a mesma regra do `_receber_execucoes` — a
    # organizacao vem da maquina, e nunca do que a mensagem disser — e o
    # mesmo helper, que ja resolve o detalhe de a trilha nao ter usuario
    # (`usuario_id=None`, e nao string vazia: a coluna e chave estrangeira).
    contexto = repo.contexto_de_dispositivo(sessao, dispositivo_id=dispositivo_id)

    try:
        credencial = credencial_de_nuvem(sessao, contexto)
    except (cofre.CofreTrancado, cofre.SegredoAusente) as erro:
        # Nao e falha do envio: e configuracao que falta. Marcar como erro do
        # artefato diria "tentamos e nao deu", quando o certo e "ninguem
        # configurou o balde ainda".
        return {"enviados": 0, "motivo": str(erro)}

    enviados = 0
    for artefato in fila:
        try:
            resposta = await canal.pedir_ao_dispositivo(
                dispositivo_id,
                "enviar_para_nuvem",
                {"pacote": artefato.nome, "s3": credencial},
                prazo_s=PRAZO_S,
            )
        except (canal.DispositivoDesconectado, canal.SemResposta) as erro:
            # A maquina caiu no meio da fila. O resto fica para a proxima
            # conexao; insistir agora so encheria o log.
            artefato.nuvem_erro = str(erro)[:2000]
            break

        if not resposta.get("ok"):
            artefato.nuvem_erro = str(resposta.get("erro", "envio recusado"))[:2000]
            continue

        artefato.nuvem_em = agora()
        artefato.nuvem_chave = str(resposta.get("objeto", ""))[:2000]
        artefato.nuvem_erro = ""
        artefato.nuvem_pendente = False
        _registrar(sessao, contexto, artefato, dispositivo)
        enviados += 1

    sessao.flush()
    return {"enviados": enviados, "restantes": len(fila) - enviados}


def _registrar(
    sessao: Session, contexto: Any, artefato: Artefato, dispositivo: Dispositivo
) -> None:
    """
    Anota na trilha que a cópia saiu do prédio.

    Faz parte da evidência: "onde está o meu backup" é uma pergunta que precisa
    de resposta datada, e não de uma caixa marcada na tela.
    """
    from .db import repositorio as repo

    repo.registrar(
        sessao,
        contexto,
        acao="artefato.na_nuvem",
        alvo=artefato.nome,
        detalhe=artefato.nuvem_chave,
        dispositivo_id=dispositivo.id,
    )


def politicas_na_nuvem(sessao: Session, organizacao_id: str) -> list[str]:
    """Ids das políticas desta organização cujo destino é a nuvem."""
    from autotarefas.tasks.politica import Politica as ConfiguracaoDePolitica

    achadas: list[str] = []
    registros = sessao.execute(
        select(Politica).where(Politica.organizacao_id == organizacao_id, Politica.ativa.is_(True))
    ).scalars()
    for registro in registros:
        try:
            configuracao = ConfiguracaoDePolitica.de_json(registro.configuracao)
        except ValueError:
            continue
        if configuracao.destino.tipo.value == "nuvem":
            achadas.append(registro.id)
    return achadas


__all__ = [
    "POR_RODADA",
    "PRAZO_S",
    "entregar_pendentes",
    "ha_pendencia",
    "pendentes",
    "politicas_na_nuvem",
]
