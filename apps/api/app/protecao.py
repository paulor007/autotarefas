"""Uma pergunta só: os dados desta empresa estão protegidos?

É a única pergunta que um cliente de backup faz, e até aqui a tela não a
respondia. Ela mostrava máquinas numa seção, políticas noutra e execuções numa
terceira, e deixava a conclusão por conta de quem olhava — que precisava saber,
sozinho, que uma política ativa com o último backup de três dias atrás e
destino no mesmo disco não é proteção nenhuma.

## A regra é conservadora de propósito

Um veredito de backup que erra para o lado otimista é pior do que nenhum
veredito: ele substitui a desconfiança saudável por uma confiança falsa, e a
pessoa só descobre no dia em que precisa restaurar. Então:

- o nível da organização é o **pior** entre os backups configurados;
- qualquer dúvida vira ressalva, nunca "protegido";
- nada aqui é estimado: cada motivo aponta um fato registrado.

## O que NÃO entra no veredito, e por quê

**Máquina desligada.** O computador da loja fecha à noite; o do escritório passa
o fim de semana desligado. Isso é normal e não é falha. Se o desligamento
atrapalhou o backup, a consequência aparece sozinha: a execução esperada não
aconteceu, e o atraso é detectado pelo item de janela. Marcar "em risco" por
desconexão faria a tela acusar problema toda noite e treinaria o cliente a
ignorá-la.

**Destino alcançável agora.** Só a máquina sabe se o disco externo está plugado
ou se a pasta de rede responde, e perguntar a cada carregamento de tela custaria
uma consulta por máquina — que falharia justamente quando a máquina estivesse
desligada, produzindo alarme falso. Um destino que sumiu faz a execução falhar,
e a falha é fato registrado. É esse fato que conta aqui.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter

from autotarefas.tasks.politica import Politica as ConfiguracaoDePolitica
from autotarefas.tasks.politica import proxima_execucao

from . import dispositivos, historico, politicas
from .db.models import agora as agora_do_banco
from .identidade.dependencias import ContextoAtual, SessaoBanco

roteador = APIRouter(prefix="/api/protecao", tags=["protecao"])

#: Quanto um backup pode atrasar antes de contar como não feito.
#:
#: É o mesmo valor que o agendador da máquina usa para decidir se ainda vale a
#: pena executar uma janela perdida (`TOLERANCIA_ATRASO`, em
#: `apps/agente/agente/agendador.py`). Divergir criaria a pior combinação
#: possível: o Agente desistindo de executar enquanto a tela ainda considera a
#: execução em dia. Um teste guarda a igualdade dos dois.
TOLERANCIA = timedelta(hours=12)

#: Resultados que contam como "o backup aconteceu".
CONCLUIDOS = frozenset({"sucesso", "com_ressalva"})


class Nivel(enum.StrEnum):
    """Do pior para o melhor. A ordem importa: o veredito é o mínimo."""

    EM_RISCO = "em_risco"
    PARCIAL = "parcial"
    PROTEGIDO = "protegido"
    SEM_CONFIGURACAO = "sem_configuracao"


#: Ordem de gravidade. `SEM_CONFIGURACAO` fica fora: não é um grau de proteção,
#: é a ausência dela, e comparar os dois no mesmo eixo produziria bobagem do
#: tipo "sem configuração é melhor que em risco".
GRAVIDADE: dict[Nivel, int] = {
    Nivel.EM_RISCO: 0,
    Nivel.PARCIAL: 1,
    Nivel.PROTEGIDO: 2,
}

TITULOS: dict[Nivel, str] = {
    Nivel.SEM_CONFIGURACAO: "Nenhum backup configurado",
    Nivel.EM_RISCO: "Proteção em risco",
    Nivel.PARCIAL: "Proteção parcial",
    Nivel.PROTEGIDO: "Protegido",
}


@dataclass
class Veredito:
    """O que se conclui sobre um backup, e os fatos que sustentam."""

    nivel: Nivel = Nivel.PROTEGIDO
    motivos: list[str] = field(default_factory=list)

    def rebaixar(self, nivel: Nivel, motivo: str) -> None:
        """Registra o motivo e piora o nível — nunca melhora."""
        self.motivos.append(motivo)
        if GRAVIDADE[nivel] < GRAVIDADE[self.nivel]:
            self.nivel = nivel


def _quando(bruto: str) -> datetime | None:
    if not bruto:
        return None
    try:
        return datetime.fromisoformat(bruto)
    except ValueError:
        return None


def _comparavel(instante: datetime, referencia: datetime) -> datetime:
    """
    Deixa os dois instantes no mesmo mundo de fuso.

    O banco grava datas ingênuas e o `agora` do servidor pode vir com fuso.
    Comparar os dois direto levanta `TypeError` — e o veredito de proteção não
    pode cair porque uma data veio sem `+00:00`.
    """
    if (instante.tzinfo is None) == (referencia.tzinfo is None):
        return instante
    if referencia.tzinfo is None:
        return instante.replace(tzinfo=None)
    return instante.replace(tzinfo=referencia.tzinfo)


def _por_data(execucao: dict[str, Any]) -> str:
    return str(execucao.get("terminada_em") or execucao.get("iniciada_em") or "")


def _avaliar_politica(
    politica: dict[str, Any],
    dispositivo: dict[str, Any] | None,
    execucoes: list[dict[str, Any]],
    agora: datetime,
) -> Veredito:
    veredito = Veredito()
    configuracao = ConfiguracaoDePolitica.model_validate(politica["configuracao"])

    if dispositivo is None:
        veredito.rebaixar(
            Nivel.EM_RISCO,
            "A máquina desta política não existe mais nesta organização.",
        )
        return veredito

    if dispositivo.get("estado") == "revogado":
        veredito.rebaixar(
            Nivel.EM_RISCO,
            f"A máquina {dispositivo['nome']} foi revogada: nada será copiado.",
        )
        return veredito

    if not configuracao.origens:
        veredito.rebaixar(
            Nivel.EM_RISCO,
            "Nenhuma pasta escolhida: esta política não copiaria nada.",
        )

    minhas = sorted(
        (item for item in execucoes if item.get("politica_id") == politica["id"]),
        key=_por_data,
        reverse=True,
    )
    concluidas = [item for item in minhas if item.get("resultado") in CONCLUIDOS]
    ultima_boa = _quando(_por_data(concluidas[0])) if concluidas else None

    if ultima_boa is None:
        veredito.rebaixar(
            Nivel.EM_RISCO,
            "Este backup nunca concluiu uma execução.",
        )
    else:
        esperada = proxima_execucao(configuracao.agendamento, ultima_boa)
        if esperada is not None and agora > _comparavel(esperada, agora) + TOLERANCIA:
            veredito.rebaixar(
                Nivel.EM_RISCO,
                "O último backup concluído é mais antigo que o horário combinado: "
                "havia execução prevista que não aconteceu.",
            )

    if minhas and minhas[0].get("resultado") == "falha":
        veredito.rebaixar(
            Nivel.EM_RISCO,
            "A tentativa mais recente falhou"
            + (f": {minhas[0]['ressalva']}" if minhas[0].get("ressalva") else "."),
        )
    elif minhas and minhas[0].get("resultado") == "com_ressalva":
        veredito.rebaixar(
            Nivel.PARCIAL,
            "O último backup terminou com ressalva"
            + (f": {minhas[0]['ressalva']}" if minhas[0].get("ressalva") else "."),
        )

    if not configuracao.protege_de_verdade:
        veredito.rebaixar(
            Nivel.PARCIAL,
            "A cópia fica no mesmo computador dos arquivos originais. Isso não "
            "protege contra o disco morrer nem contra ransomware.",
        )

    if configuracao.agendamento.tipo == "desligado":
        veredito.rebaixar(
            Nivel.PARCIAL,
            "Sem horário marcado: este backup só acontece quando alguém clica.",
        )

    return veredito


def avaliar(
    politicas_ativas: list[dict[str, Any]],
    dispositivos: list[dict[str, Any]],
    execucoes: list[dict[str, Any]],
    agora: datetime,
) -> dict[str, Any]:
    """
    O veredito da organização, e o de cada backup que o compõe.

    Função pura: recebe o que já foi lido do banco e devolve a conclusão. Assim
    a regra — que é a decisão de produto mais delicada desta tela — pode ser
    exercitada com dezenas de combinações sem subir servidor nem popular banco.
    """
    por_id = {item["id"]: item for item in dispositivos}
    ativas = [item for item in politicas_ativas if item.get("ativa")]

    if not ativas:
        return {
            "nivel": Nivel.SEM_CONFIGURACAO.value,
            "titulo": TITULOS[Nivel.SEM_CONFIGURACAO],
            "resumo": ("Nenhum backup ativo. Enquanto não houver política, nada é copiado."),
            "backups": [],
        }

    backups: list[dict[str, Any]] = []
    for politica in ativas:
        dispositivo = por_id.get(politica["dispositivo_id"])
        veredito = _avaliar_politica(politica, dispositivo, execucoes, agora)
        backups.append(
            {
                "politica_id": politica["id"],
                "nome": politica["nome"],
                "maquina": dispositivo["nome"] if dispositivo else "",
                "nivel": veredito.nivel.value,
                "titulo": TITULOS[veredito.nivel],
                "motivos": veredito.motivos,
            }
        )

    pior = min(
        (Nivel(item["nivel"]) for item in backups),
        key=lambda nivel: GRAVIDADE[nivel],
    )
    return {
        "nivel": pior.value,
        "titulo": TITULOS[pior],
        "resumo": _resumo(pior, backups),
        "backups": backups,
    }


def _resumo(pior: Nivel, backups: list[dict[str, Any]]) -> str:
    quantos = len(backups)
    plural = "backup ativo" if quantos == 1 else "backups ativos"
    if pior is Nivel.PROTEGIDO:
        return f"{quantos} {plural}, todos em dia."
    com_ressalva = sum(1 for item in backups if item["nivel"] != Nivel.PROTEGIDO.value)
    quais = "1 precisa" if com_ressalva == 1 else f"{com_ressalva} precisam"
    return f"{quantos} {plural}. {quais} de atenção."


@roteador.get("")
def estado_da_protecao(
    sessao: SessaoBanco,
    contexto: ContextoAtual,
) -> dict[str, Any]:
    """O veredito desta organização, com os fatos que o sustentam."""
    return avaliar(
        politicas.listar(sessao, contexto),
        dispositivos.listar(sessao, contexto),
        historico.listar(sessao, contexto),
        agora_do_banco(),
    )
