"""O Agente como servico da maquina: sobe sozinho, sem ninguem logar no Live.

Um Agente que so roda quando alguem abre um terminal nao e backup automatico —
e um backup manual com passos a mais. Esta etapa registra o Agente no
**Agendador de Tarefas do Windows**, que e o mecanismo do sistema para "rode
isso quando a maquina ligar" e "reinicie se cair".

Por que o Agendador, e nao um servico do Windows de verdade:

- servico exige elevacao **sempre**, inclusive para instalar. Numa micro
  empresa isso trava a instalacao na primeira tela;
- servico roda como SYSTEM, e o Agente precisa alcancar as pastas do usuario —
  incluindo mapeamentos de rede, que SYSTEM nao enxerga;
- o Agendador cobre os dois casos que importam: **ao entrar** (sem elevacao) e
  **ao ligar** (com elevacao, para quem quiser backup antes de alguem logar).

O que este modulo NAO faz, e diz que nao faz: nao instala Python, nao baixa
nada e nao pede elevacao sozinho. Um instalador que se eleva sozinho ensina o
cliente a clicar "sim" em janelas que ele nao leu.

Fora do Windows, cada funcao recusa dizendo o motivo. Fingir que registrou um
servico que nao existe seria a pior mentira possivel aqui: o cliente iria
embora achando que o backup roda sozinho.
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 — chamada de programa do sistema, com argumentos fixos
import sys
from dataclasses import dataclass
from pathlib import Path

#: Nome da tarefa no Agendador. Estavel: e por ele que instalar de novo
#: substitui em vez de duplicar.
NOME_DA_TAREFA = "AutoTarefas Agente"

#: Quanto esperar pelo `schtasks`. Ele responde em milissegundos; um minuto e
#: folga para maquina carregada, e evita travar a instalacao para sempre.
PRAZO_S = 60.0


class InstalacaoRecusada(Exception):
    """Nao deu para registrar, e a mensagem diz o que resolver."""


@dataclass(frozen=True)
class Situacao:
    """O que o sistema diz sobre a tarefa do Agente."""

    registrada: bool
    detalhe: str = ""

    def como_dicionario(self) -> dict[str, object]:
        return {"registrada": self.registrada, "detalhe": self.detalhe}


def e_windows() -> bool:
    return sys.platform == "win32"


def comando_padrao(pasta_de_configuracao: Path | None = None) -> str:
    """
    O que a tarefa executa: este mesmo Python, rodando o servico do Agente.

    Usa `sys.executable` de proposito. A maquina do cliente pode ter varios
    Pythons instalados, e apontar para "python" deixaria o sistema escolher —
    provavelmente o errado, e so na primeira madrugada alguem descobriria.
    """
    partes = [f'"{Path(sys.executable).resolve()}"', "-m", "apps.agente.agente", "servico"]
    if pasta_de_configuracao is not None:
        partes.append(f'--pasta-de-configuracao "{pasta_de_configuracao.resolve()}"')
    return " ".join(partes)


def _schtasks() -> str:
    caminho = shutil.which("schtasks")
    if caminho is None:
        msg = "nao encontrei o Agendador de Tarefas (schtasks) nesta maquina"
        raise InstalacaoRecusada(msg)
    return caminho


def _exigir_windows(acao: str) -> None:
    if not e_windows():
        msg = (
            f"{acao} so existe no Windows. Neste sistema, coloque "
            "'autotarefas-agente servico' para subir junto com a maquina do jeito "
            "que ele faz isso (systemd, launchd)."
        )
        raise InstalacaoRecusada(msg)


def _rodar(argumentos: list[str]) -> subprocess.CompletedProcess[str]:
    """Chama o `schtasks` com argumentos fixos, sem passar pelo shell."""
    # nosec B603 — sem shell, e a lista vem so daqui: o caminho do `schtasks`
    # resolvido pelo sistema, mais argumentos que este modulo monta. Nada do
    # que chega do Live entra nesta linha.
    return subprocess.run(  # noqa: S603
        [_schtasks(), *argumentos],  # nosec B603
        capture_output=True,
        text=True,
        timeout=PRAZO_S,
        check=False,
    )


def instalar(
    *,
    comando: str = "",
    ao_ligar: bool = False,
    pasta_de_configuracao: Path | None = None,
) -> Situacao:
    """
    Registra o Agente para subir sozinho.

    `ao_ligar=False` (padrao) registra **ao entrar** no Windows: nao precisa de
    elevacao, e cobre o caso normal de um computador de escritorio, que alguem
    liga de manha.

    `ao_ligar=True` registra **ao ligar a maquina**, rodando como SYSTEM. Exige
    terminal como administrador — e a recusa do sistema chega inteira para quem
    pediu, em vez de virar um "instalado" que nao instalou nada.
    """
    _exigir_windows("registrar o Agente como servico")

    linha = comando or comando_padrao(pasta_de_configuracao)
    argumentos = [
        "/Create",
        "/TN",
        NOME_DA_TAREFA,
        "/TR",
        linha,
        # `/F` substitui a tarefa se ela ja existir. Sem isso, instalar de novo
        # depois de uma atualizacao falharia com "ja existe" — e o cliente
        # ficaria com a versao velha rodando.
        "/F",
    ]
    argumentos += (
        ["/SC", "ONSTART", "/RU", "SYSTEM", "/RL", "HIGHEST"]
        if ao_ligar
        else [
            "/SC",
            "ONLOGON",
        ]
    )

    resultado = _rodar(argumentos)
    if resultado.returncode != 0:
        detalhe = (resultado.stderr or resultado.stdout or "").strip()
        raise InstalacaoRecusada(_explicar(detalhe, ao_ligar=ao_ligar))

    quando = "ao ligar a maquina" if ao_ligar else "ao entrar no Windows"
    return Situacao(registrada=True, detalhe=f"tarefa '{NOME_DA_TAREFA}' criada, dispara {quando}")


def desinstalar() -> Situacao:
    """
    Tira a tarefa do Agendador.

    Nao apaga configuracao, nem chave, nem pacote. Parar de rodar sozinho e uma
    decisao; apagar o backup do cliente e outra, e ninguem pediu a segunda.
    """
    _exigir_windows("remover o servico do Agente")

    resultado = _rodar(["/Delete", "/TN", NOME_DA_TAREFA, "/F"])
    if resultado.returncode != 0:
        detalhe = (resultado.stderr or resultado.stdout or "").strip()
        return Situacao(registrada=False, detalhe=detalhe or "a tarefa nao estava registrada")
    return Situacao(registrada=False, detalhe=f"tarefa '{NOME_DA_TAREFA}' removida")


def situacao() -> Situacao:
    """
    O Agente esta registrado para subir sozinho?

    Pergunta ao sistema toda vez. Guardar a resposta num arquivo faria a tela
    dizer "instalado" para uma tarefa que alguem removeu pelo Agendador.
    """
    if not e_windows():
        return Situacao(registrada=False, detalhe="fora do Windows nao ha tarefa registrada")

    try:
        resultado = _rodar(["/Query", "/TN", NOME_DA_TAREFA])
    except InstalacaoRecusada as erro:
        return Situacao(registrada=False, detalhe=str(erro))

    if resultado.returncode != 0:
        return Situacao(registrada=False, detalhe="o Agente nao esta registrado para subir sozinho")
    return Situacao(registrada=True, detalhe=(resultado.stdout or "").strip())


def _explicar(detalhe: str, *, ao_ligar: bool) -> str:
    """
    Traduz a recusa do sistema para algo acionavel.

    "Acesso negado" sozinho nao diz a ninguem o que fazer; "abra o terminal
    como administrador" diz.
    """
    baixo = detalhe.lower()
    if ao_ligar and ("denied" in baixo or "negado" in baixo or "access" in baixo):
        return (
            "registrar para rodar AO LIGAR exige terminal como administrador. "
            "Sem elevacao, use o modo padrao (ao entrar no Windows), que cobre "
            "computador de escritorio. Detalhe do sistema: " + detalhe
        )
    return detalhe or "o Agendador de Tarefas recusou sem dizer o motivo"


__all__ = [
    "NOME_DA_TAREFA",
    "InstalacaoRecusada",
    "Situacao",
    "comando_padrao",
    "desinstalar",
    "e_windows",
    "instalar",
    "situacao",
]
