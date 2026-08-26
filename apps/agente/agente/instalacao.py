"""O Agente como servico da maquina: sobe sozinho, sem ninguem logar no Live.

Um Agente que so roda quando alguem abre um terminal nao e backup automatico —
e um backup manual com passos a mais.

**Dois mecanismos, e a ordem importa.** O primeiro e o Agendador de Tarefas do
Windows; o segundo, a lista de programas que sobem quando o usuario entra. A
diferenca entre eles nao e detalhe de implementacao: e o que o cliente pode
esperar do produto.

| Mecanismo | Precisa de administrador? | Roda quando |
| --- | --- | --- |
| Agendador, `ONSTART` | **sim** | a maquina liga, mesmo sem ninguem logado |
| Agendador, `ONLOGON` | **em geral sim** | alguem entra no Windows |
| Logon do usuario (registro) | nao | **este** usuario entra no Windows |

A terceira linha existe porque a segunda mentiu. A documentacao deste modulo
afirmava que `ONLOGON` dispensava elevacao — e numa maquina Windows 11 comum ele
responde **"Acesso negado"**. O instalador registrava o Agente, dizia que estava
tudo certo, e o backup agendado simplesmente nao aconteceria. Foi encontrado
rodando o produto de verdade, e nao pela suite: o teste conferia os argumentos
enviados ao `schtasks`, e eles estavam certos.

Entao a instalacao tenta o Agendador e, ao ser recusada por falta de privilegio,
**cai para o logon do usuario** — dizendo qual dos dois conseguiu. Um instalador
que so tenta o melhor caminho e desiste deixa o cliente sem backup automatico
por causa de uma politica de seguranca que ele nem sabe que tem.

O que este modulo NAO faz, e diz que nao faz: nao instala Python, nao baixa nada
e nao pede elevacao sozinho. Um instalador que se eleva sozinho ensina o cliente
a clicar "sim" em janelas que ele nao leu.

Fora do Windows, cada funcao recusa dizendo o motivo. Fingir que registrou um
servico que nao existe seria a pior mentira possivel aqui: o cliente iria embora
achando que o backup roda sozinho.
"""

from __future__ import annotations

import enum
import shutil
import subprocess  # nosec B404 — chamada de programa do sistema, com argumentos fixos
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Nome da tarefa no Agendador, e do valor no registro. Estavel: e por ele que
#: instalar de novo substitui em vez de duplicar.
NOME_DA_TAREFA = "AutoTarefas Agente"

#: Onde o Windows guarda o que sobe quando o usuario entra. Chave do USUARIO:
#: gravavel sem elevacao, e some junto com o perfil dele.
CHAVE_DE_LOGON = r"Software\Microsoft\Windows\CurrentVersion\Run"

#: Quanto esperar pelo `schtasks`. Ele responde em milissegundos; um minuto e
#: folga para maquina carregada, e evita travar a instalacao para sempre.
PRAZO_S = 60.0


class Modo(enum.StrEnum):
    """Como o Agente foi registrado para subir sozinho."""

    AGENDADOR = "agendador"
    """Tarefa no Agendador. Melhor: aceita `ONSTART` e reinicio."""

    LOGON = "logon"
    """Lista de logon do usuario. Sem elevacao, mas so para este usuario."""

    NENHUM = "nenhum"
    """Nao esta registrado em lugar nenhum."""


class InstalacaoRecusada(Exception):
    """Nao deu para registrar, e a mensagem diz o que resolver."""


@dataclass(frozen=True)
class Situacao:
    """O que o sistema diz sobre a partida automatica do Agente."""

    registrada: bool
    detalhe: str = ""
    modo: Modo = Modo.NENHUM

    def como_dicionario(self) -> dict[str, object]:
        return {"registrada": self.registrada, "detalhe": self.detalhe, "modo": self.modo.value}


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


# ============================================================
# Logon do usuario — o caminho que nao pede elevacao
# ============================================================


def _registro() -> Any:
    """
    O modulo `winreg`, importado so quando ha Windows para consultar.

    Import tardio de proposito: `winreg` nao existe em Linux nem em macOS, e um
    import no topo quebraria ate a suite que roda em outro sistema.
    """
    import winreg

    return winreg


def gravar_no_logon(comando: str) -> None:
    """
    Poe o Agente na lista de programas que sobem quando este usuario entra.

    Chave do usuario, e nao da maquina: nao precisa de elevacao, e some junto
    com o perfil — o que e a coisa certa para um programa que so faz sentido
    enquanto aquela pessoa usa aquele computador.
    """
    winreg = _registro()
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, CHAVE_DE_LOGON, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, NOME_DA_TAREFA, 0, winreg.REG_SZ, comando)


def ler_do_logon() -> str:
    """O comando registrado, ou vazio quando nao ha nenhum."""
    if not e_windows():
        return ""
    winreg = _registro()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_DE_LOGON) as k:
            valor, _ = winreg.QueryValueEx(k, NOME_DA_TAREFA)
    except OSError:
        return ""
    return str(valor)


def apagar_do_logon() -> bool:
    """Tira o Agente da lista de logon. Devolve se havia algo para tirar."""
    if not e_windows():
        return False
    winreg = _registro()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_DE_LOGON, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, NOME_DA_TAREFA)
    except OSError:
        return False
    return True


# ============================================================
# Instalar e desinstalar
# ============================================================


def instalar(
    *,
    comando: str = "",
    ao_ligar: bool = False,
    pasta_de_configuracao: Path | None = None,
) -> Situacao:
    """
    Registra o Agente para subir sozinho, pelo melhor caminho disponivel.

    `ao_ligar=True` exige terminal como administrador e registra a tarefa que
    dispara **com a maquina ligada, sem ninguem logado**. E o unico modo que faz
    backup de madrugada num computador onde ninguem deixou a sessao aberta.

    O padrao tenta o Agendador e, se o Windows recusar por falta de privilegio,
    cai para a lista de logon deste usuario — dizendo qual dos dois conseguiu.
    Desistir no primeiro "acesso negado" deixaria o cliente sem backup
    automatico por causa de uma politica que ele nem sabe que tem.
    """
    _exigir_windows("registrar o Agente para subir sozinho")
    linha = comando or comando_padrao(pasta_de_configuracao)

    if ao_ligar:
        resultado = _criar_tarefa(linha, ao_ligar=True)
        if resultado.returncode != 0:
            detalhe = (resultado.stderr or resultado.stdout or "").strip()
            raise InstalacaoRecusada(_explicar(detalhe, ao_ligar=True))
        return Situacao(
            registrada=True,
            detalhe="dispara quando a maquina liga, mesmo sem ninguem logado",
            modo=Modo.AGENDADOR,
        )

    resultado = _criar_tarefa(linha, ao_ligar=False)
    if resultado.returncode == 0:
        return Situacao(
            registrada=True,
            detalhe="dispara quando alguem entra no Windows",
            modo=Modo.AGENDADOR,
        )

    recusa = (resultado.stderr or resultado.stdout or "").strip()
    try:
        gravar_no_logon(linha)
    except OSError as erro:
        raise InstalacaoRecusada(_explicar(recusa or str(erro), ao_ligar=False)) from erro

    return Situacao(
        registrada=True,
        detalhe=(
            "dispara quando VOCE entra no Windows. O Agendador de Tarefas pediu "
            "administrador, entao usei a lista de logon do seu usuario. Para o "
            "backup rodar com a maquina ligada e ninguem logado, rode o "
            "instalador como administrador."
        ),
        modo=Modo.LOGON,
    )


def _criar_tarefa(linha: str, *, ao_ligar: bool) -> subprocess.CompletedProcess[str]:
    """Monta e dispara o `schtasks /Create`."""
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
        ["/SC", "ONSTART", "/RU", "SYSTEM", "/RL", "HIGHEST"] if ao_ligar else ["/SC", "ONLOGON"]
    )
    return _rodar(argumentos)


def desinstalar() -> Situacao:
    """
    Tira o Agente dos dois lugares onde ele pode ter sido registrado.

    Nao apaga configuracao, nem chave, nem pacote. Parar de rodar sozinho e uma
    decisao; apagar o backup do cliente e outra, e ninguem pediu a segunda.
    """
    _exigir_windows("remover a partida automatica do Agente")

    tirou_tarefa = _rodar(["/Delete", "/TN", NOME_DA_TAREFA, "/F"]).returncode == 0
    tirou_logon = apagar_do_logon()

    if not (tirou_tarefa or tirou_logon):
        return Situacao(registrada=False, detalhe="o Agente nao estava registrado")

    onde = " e ".join(
        parte
        for parte, houve in (("do Agendador", tirou_tarefa), ("da lista de logon", tirou_logon))
        if houve
    )
    return Situacao(registrada=False, detalhe=f"removido {onde}")


def situacao() -> Situacao:
    """
    O Agente esta registrado para subir sozinho — e por qual caminho?

    Pergunta ao sistema toda vez, nos dois lugares. Guardar a resposta num
    arquivo faria a tela dizer "instalado" para uma tarefa que alguem removeu
    pelo Agendador.
    """
    if not e_windows():
        return Situacao(registrada=False, detalhe="fora do Windows nao ha registro a fazer")

    try:
        no_agendador = _rodar(["/Query", "/TN", NOME_DA_TAREFA]).returncode == 0
    except InstalacaoRecusada as erro:
        return Situacao(registrada=False, detalhe=str(erro))

    if no_agendador:
        return Situacao(registrada=True, detalhe="tarefa no Agendador", modo=Modo.AGENDADOR)
    if ler_do_logon():
        return Situacao(
            registrada=True,
            detalhe="na lista de logon do seu usuario",
            modo=Modo.LOGON,
        )
    return Situacao(registrada=False, detalhe="o Agente nao esta registrado para subir sozinho")


def _explicar(detalhe: str, *, ao_ligar: bool) -> str:
    """
    Traduz a recusa do sistema para algo acionavel.

    "Acesso negado" sozinho nao diz a ninguem o que fazer; "abra o terminal
    como administrador" diz.
    """
    baixo = detalhe.lower()
    if "denied" in baixo or "negado" in baixo or "access" in baixo:
        alvo = "AO LIGAR" if ao_ligar else "no Agendador de Tarefas"
        return f"registrar {alvo} exige terminal como administrador. Detalhe do sistema: " + detalhe
    return detalhe or "o Agendador de Tarefas recusou sem dizer o motivo"


__all__ = [
    "CHAVE_DE_LOGON",
    "NOME_DA_TAREFA",
    "InstalacaoRecusada",
    "Modo",
    "Situacao",
    "apagar_do_logon",
    "comando_padrao",
    "desinstalar",
    "e_windows",
    "gravar_no_logon",
    "instalar",
    "ler_do_logon",
    "situacao",
]
