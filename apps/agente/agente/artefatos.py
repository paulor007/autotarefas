"""Os pacotes que existem NESTA maquina, resolvidos pelo nome.

O Live sabe o **nome** de cada pacote — ele veio na ficha do artefato. O que ele
nao sabe, e nao deve saber, e onde o arquivo esta: o caminho local revela a
estrutura de pastas da empresa, e mandar isso para o servidor entregaria de
graca um mapa que ninguem pediu.

Entao a conversa acontece por nome. O Live diz `backup_2026-08-25_0200.zip`; o
Agente procura nas pastas de pacotes que ele mesmo conhece e resolve para um
caminho real. Uma consequencia util cai de brinde: o servidor nao consegue
apontar para um arquivo arbitrario do disco, porque nao e ele quem escolhe a
pasta.

O nome e conferido antes de virar caminho. `..\\..\\Windows\\System32\\x.zip`
nao e nome de pacote — e uma tentativa de sair da pasta. Nome com separador,
com `..` ou fora do formato do produto e recusado sem ser usado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from autotarefas.tasks.retencao_nomes import data_do_nome, listar_datados

from . import pastas as mod_pastas
from .backup import PASTA_PADRAO
from .config import Configuracao


class PacoteDesconhecido(Exception):
    """Nao ha pacote com esse nome nas pastas que este Agente conhece."""


@dataclass(frozen=True)
class Pacote:
    """Um pacote encontrado, do jeito que a tela precisa ve-lo."""

    nome: str
    tamanho_bytes: int
    criado_em: str
    caminho: Path
    #: De qual politica este pacote e. Vazio = avulso, sem politica.
    politica_id: str = ""
    #: Nome da politica, lido do marcador que fica ao lado dos pacotes.
    politica_nome: str = ""

    def como_dicionario(self) -> dict[str, object]:
        """
        O que sobe para o servidor. O caminho **nao** vai junto.

        E a mesma regra da ficha do artefato: o Live trabalha com nomes; onde o
        arquivo esta e assunto desta maquina.
        """
        return {
            "nome": self.nome,
            "tamanho_bytes": self.tamanho_bytes,
            "criado_em": self.criado_em,
            # De quem e o pacote. Sem isto, a tela de restauracao mostra um
            # monte de pacotes de politicas diferentes com a mesma cara, e
            # quem restaura escolhe pela data — que e a informacao que menos
            # distingue um "diario da contabilidade" de um "mensal do
            # juridico".
            "politica_id": self.politica_id,
            "politica_nome": self.politica_nome,
        }


def pasta_dos_pacotes(configuracao: Configuracao) -> Path | None:
    """
    Onde os pacotes ficam quando ninguem disse outra coisa.

    Ao lado da primeira pasta autorizada, e nao dentro dela — a mesma escolha
    da execucao: dentro, o pacote de hoje entraria no backup de amanha.
    """
    if not configuracao.raizes:
        return None
    return Path(configuracao.raizes[0]).parent / PASTA_PADRAO


def nome_valido(nome: str) -> bool:
    """
    E nome de pacote, e nao um caminho disfarcado?

    Recusa separador, `..` e qualquer coisa fora do formato do produto. Sem
    isto, o `nome` viraria o caminho — e o servidor escolheria qual arquivo do
    disco o Agente abre.
    """
    if not nome or "/" in nome or "\\" in nome or ".." in nome:
        return False
    return data_do_nome(nome) is not None


def _pastas_a_varrer(raiz: Path) -> list[Path]:
    """
    A raiz e a pasta de cada politica.

    A raiz continua entrando porque o backup avulso mora la, e porque os
    pacotes gerados antes de existir pasta por politica tambem estao la — eles
    nao tem como ser atribuidos a ninguem agora (essa era exatamente a
    informacao que faltava), e some-los da lista seria fazer sumir backup que
    existe.
    """
    return [raiz, *mod_pastas.pastas_de_politica(raiz)]


def listar(configuracao: Configuracao) -> list[Pacote]:
    """Pacotes desta maquina, do mais novo para o mais velho."""
    raiz = pasta_dos_pacotes(configuracao)
    if raiz is None:
        return []

    encontrados: list[Pacote] = []
    for pasta in _pastas_a_varrer(raiz):
        politica_id = mod_pastas.identificador_da_pasta(pasta)
        politica_nome = mod_pastas.nome_marcado(pasta) if politica_id else ""
        for quando, caminho in listar_datados(pasta):
            try:
                tamanho = caminho.stat().st_size
            except OSError:
                # Arquivo que sumiu entre listar e medir. Nao mostrar e melhor
                # do que mostrar um pacote que a restauracao nao vai encontrar.
                continue
            encontrados.append(
                Pacote(
                    nome=caminho.name,
                    tamanho_bytes=tamanho,
                    criado_em=_iso(quando),
                    caminho=caminho,
                    politica_id=politica_id,
                    politica_nome=politica_nome,
                )
            )
    # Ordenado no fim, e nao por pasta: a tela mostra uma linha do tempo da
    # maquina, e nao um agrupamento por pasta que ninguem pediu.
    return sorted(encontrados, key=lambda item: item.criado_em, reverse=True)


def achar(configuracao: Configuracao, nome: str) -> Path:
    """
    Caminho real do pacote com esse nome. Levanta se nao houver.

    Falha fechada: nome invalido e nome inexistente dao no mesmo — recusa. A
    mensagem diz o nome pedido, e nunca a pasta onde se procurou.
    """
    if not nome_valido(nome):
        msg = f"'{nome}' nao e um nome de pacote do AutoTarefas"
        raise PacoteDesconhecido(msg)

    raiz = pasta_dos_pacotes(configuracao)
    if raiz is None:
        msg = "nenhuma pasta autorizada nesta maquina, entao nao ha pacotes"
        raise PacoteDesconhecido(msg)

    # Procura na raiz e nas pastas de politica. O nome ja foi conferido acima,
    # entao ele nao sai daqui: `nome_valido` recusa separador e `..`, e as
    # pastas varridas sao as que este Agente mesmo montou.
    for pasta in _pastas_a_varrer(raiz):
        caminho = pasta / nome
        if caminho.is_file():
            return caminho

    msg = f"nao ha pacote chamado '{nome}' nesta maquina"
    raise PacoteDesconhecido(msg)


def corrente(pacote: Path) -> list[Path]:
    """
    Os pacotes anteriores de que este depende, do mais novo para o mais velho.

    Quem monta a corrente e a **maquina**, e nao a tela: o Live conhece nomes, e
    so aqui se sabe quais deles ainda existem no disco. Sem isto, restaurar o
    pacote de hoje devolveria uma pasta pela metade — com cara de restauracao
    concluida.
    """
    from autotarefas.tasks.backup import corrente_de

    return corrente_de(pacote)


def _iso(quando: datetime) -> str:
    return quando.isoformat(timespec="minutes")


__all__ = [
    "Pacote",
    "PacoteDesconhecido",
    "achar",
    "corrente",
    "listar",
    "nome_valido",
    "pasta_dos_pacotes",
]
