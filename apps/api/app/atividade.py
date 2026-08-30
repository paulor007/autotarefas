"""O que está acontecendo agora, e o que vem em seguida.

Esta rota existe por causa de uma pergunta que a tela não sabia responder:
**"isto funciona mesmo?"**

O histórico responde "funcionou" — com data, tamanho e hash. É evidência forte,
e ainda assim quem chega de fora olha uma lista de linhas prontas e não vê
nenhuma delas acontecer. A diferença entre ler que um backup ocorreu e ver um
ocorrendo é a mesma que há entre um extrato e uma máquina funcionando.

Duas metades, e as duas são necessárias:

**O que está rodando.** Vem do canal, em tempo real, e só existe enquanto
existe: nenhum backup é disparado para encher a tela, e nada é simulado quando
não há nada acontecendo. Fora da janela de uma execução, esta lista é vazia — e
vazia é a resposta certa.

**O que vem depois.** Calculado do agendamento de cada política, pelo mesmo
código que o Agente usa para decidir quando disparar. É o que transforma uma
lista vazia em informação: "nada rodando agora; o próximo é às 15:00" diz que o
sistema está vivo, enquanto uma tela em branco não diz nada.

O que NÃO existe aqui: previsão de duração, barra de progresso em porcentagem,
e qualquer número que o Agente não tenha mandado. Uma barra que avança sozinha
é a forma mais fácil de mentir sobre trabalho que não está acontecendo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter

from autotarefas.tasks.politica import Politica as ConfiguracaoDePolitica
from autotarefas.tasks.politica import proxima_execucao

from .db import repositorio as repo
from .db.models import Dispositivo, Politica, agora
from .identidade.dependencias import ContextoAtual, SessaoBanco

roteador = APIRouter(prefix="/api/atividade", tags=["atividade"])

#: Como cada etapa do Agente se chama para quem não é da equipe.
#:
#: O Agente relata `iniciando`, `entregando`, `enviando`, `concluido` — nomes
#: escolhidos para o log. Quem está olhando a tela quer saber o que está
#: acontecendo com os arquivos dele.
ETAPAS: dict[str, str] = {
    "iniciando": "Lendo as pastas",
    "compactando": "Compactando os arquivos",
    "conferindo": "Conferindo o pacote",
    "entregando": "Copiando para o destino",
    "enviando": "Enviando para a nuvem",
    "concluido": "Concluído",
}


def _em_portugues(etapa: str) -> str:
    return ETAPAS.get(etapa, etapa.replace("_", " ").capitalize() if etapa else "Em andamento")


def acontecendo(organizacao_id: str) -> list[dict[str, Any]]:
    """Backups rodando agora nas máquinas conectadas desta organização."""
    from . import canal

    correndo: list[dict[str, Any]] = []
    for conexao in canal.presenca.da_organizacao(organizacao_id):
        for item in conexao.acontecendo_agora():
            correndo.append(
                {
                    "politica_id": str(item.get("politica_id", "")),
                    "politica_nome": str(item.get("politica_nome", "")),
                    "maquina": str(item.get("maquina", "")),
                    "dispositivo_id": str(item.get("dispositivo_id", "")),
                    "etapa": str(item.get("etapa", "")),
                    "etapa_em_portugues": _em_portugues(str(item.get("etapa", ""))),
                    # Só o que o Agente mandou. Campo ausente fica ausente: um
                    # zero inventado aqui apareceria na tela como fato.
                    "arquivos": item.get("arquivos"),
                    "destino": item.get("destino"),
                    "desde": str(item.get("recebido_em", "")),
                }
            )
    return correndo


def _proxima_de(configuracao: ConfiguracaoDePolitica, momento: datetime) -> str:
    """
    A próxima execução, **no relógio da máquina**, e não num fuso qualquer.

    O horário de uma política é "03:00 no relógio de quem executa" — está
    escrito no núcleo, e é a única definição que faz sentido para quem
    configura ("quero que rode de madrugada, quando a loja está fechada").

    O servidor não sabe em que fuso a máquina está: ele pode estar num
    datacenter e a máquina numa loja a três fusos dali. Devolver um instante
    absoluto aqui seria inventar essa informação — e a tela mostraria 03:00 do
    fuso errado com toda a confiança de um dado exato.

    Por isso o cálculo é feito com hora de parede, sem fuso, e o campo que sai
    daqui diz isso no próprio nome. O que a tela mostra ao lado é a **regra**
    ("todo dia às 03:00"), que não depende de fuso nenhum para ser verdadeira.
    """
    quando = proxima_execucao(configuracao.agendamento, momento)
    return quando.isoformat() if quando is not None else ""


def agenda(sessao: Any, contexto: repo.Contexto) -> list[dict[str, Any]]:
    """
    Quando cada política ativa dispara pela próxima vez.

    Calculado pelo mesmo `proxima_execucao` que o agendador da máquina usa. Uma
    segunda implementação aqui produziria, mais cedo ou mais tarde, uma tela
    prometendo 03:00 para um Agente que dispara às 04:00 — e a discordância
    apareceria como "backup atrasado" sem nada estar atrasado.
    """
    # Hora de parede, sem fuso: ver `_proxima_de`. O horário da política é o
    # relógio da máquina, e o servidor não sabe qual é.
    momento = datetime.now().replace(microsecond=0)
    maquinas = {
        item.id: item.nome for item in sessao.execute(repo.escopo(Dispositivo, contexto)).scalars()
    }
    proximas: list[dict[str, Any]] = []
    for registro in sessao.execute(repo.escopo(Politica, contexto)).scalars():
        if not registro.ativa:
            continue
        try:
            configuracao = ConfiguracaoDePolitica.de_json(registro.configuracao)
        except ValueError:
            continue
        agendamento = configuracao.agendamento
        proximas.append(
            {
                "politica_id": registro.id,
                "nome": registro.nome,
                "maquina": maquinas.get(registro.dispositivo_id or "", ""),
                "proxima_no_relogio_da_maquina": _proxima_de(configuracao, momento),
                # A REGRA, que não depende de fuso nenhum para ser verdadeira.
                # É o que a tela mostra ao lado do horário calculado.
                "quando": agendamento.tipo.value,
                "hora": agendamento.hora,
            }
        )
    # Sem horário vai para o fim: uma política manual não compete com as
    # agendadas pela atenção de quem olha "o que vem agora".
    return sorted(
        proximas,
        key=lambda item: (
            item["proxima_no_relogio_da_maquina"] == "",
            item["proxima_no_relogio_da_maquina"],
        ),
    )


@roteador.get("/ao-vivo")
def ao_vivo(contexto: ContextoAtual, sessao: SessaoBanco) -> dict[str, Any]:
    """
    O agora desta organização: o que roda, e o que vem depois.

    Feita para ser consultada de poucos em poucos segundos. Por isso não toca
    em máquina nenhuma: lê a presença, que já está em memória, e o agendamento,
    que é cálculo. Perguntar ao Agente a cada consulta transformaria uma tela
    aberta num comando por segundo na máquina do cliente.
    """
    return {
        "agora": agora().isoformat(),
        "executando": acontecendo(contexto.organizacao_id),
        "proximas": agenda(sessao, contexto),
    }


__all__ = ["ETAPAS", "acontecendo", "agenda", "ao_vivo", "roteador"]
