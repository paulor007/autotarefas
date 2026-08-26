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


def listar(configuracao: Configuracao) -> list[Pacote]:
    """Pacotes desta maquina, do mais novo para o mais velho."""
    pasta = pasta_dos_pacotes(configuracao)
    if pasta is None:
        return []

    encontrados: list[Pacote] = []
    for quando, caminho in listar_datados(pasta):
        try:
            tamanho = caminho.stat().st_size
        except OSError:
            # Arquivo que sumiu entre listar e medir. Nao mostrar e melhor do
            # que mostrar um pacote que a restauracao nao vai encontrar.
            continue
        encontrados.append(
            Pacote(
                nome=caminho.name,
                tamanho_bytes=tamanho,
                criado_em=_iso(quando),
                caminho=caminho,
            )
        )
    return encontrados


def achar(configuracao: Configuracao, nome: str) -> Path:
    """
    Caminho real do pacote com esse nome. Levanta se nao houver.

    Falha fechada: nome invalido e nome inexistente dao no mesmo — recusa. A
    mensagem diz o nome pedido, e nunca a pasta onde se procurou.
    """
    if not nome_valido(nome):
        msg = f"'{nome}' nao e um nome de pacote do AutoTarefas"
        raise PacoteDesconhecido(msg)

    pasta = pasta_dos_pacotes(configuracao)
    if pasta is None:
        msg = "nenhuma pasta autorizada nesta maquina, entao nao ha pacotes"
        raise PacoteDesconhecido(msg)

    caminho = pasta / nome
    if not caminho.is_file():
        msg = f"nao ha pacote chamado '{nome}' nesta maquina"
        raise PacoteDesconhecido(msg)
    return caminho


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
