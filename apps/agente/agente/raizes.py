"""Pastas autorizadas: a fronteira entre o Live e o disco do cliente.

Uma regra organiza tudo: **o consentimento acontece na propria maquina**. Uma
tela na nuvem nao concede acesso ao disco de ninguem. O Live pode listar o que
foi autorizado e pode pedir que alguem autorize algo; quem autoriza e uma
pessoa, ali, com o Agente.

Isso nao e formalidade. Se um comando remoto pudesse acrescentar pasta, bastaria
comprometer a conta do Live — ou o proprio servidor — para ler qualquer arquivo
de qualquer maquina da frota. Com o consentimento local, o pior caso vira "o
atacante manda copiar de novo o que ja estava autorizado".

Duas guardas concretas:

1. **Pastas proibidas.** Autorizar `C:\\` ou `C:\\Windows` colocaria o sistema
   operacional inteiro num ZIP — lento, inutil como backup e perigoso como
   vazamento. O Agente recusa, dizendo por que.
2. **Todo caminho e resolvido antes de comparar.** Sem isso,
   `pasta-autorizada\\..\\..\\Windows` passaria pela verificacao e leria o que
   ninguem autorizou.
"""

from __future__ import annotations

import os
from pathlib import Path

from .config import Configuracao, Local


class AutorizacaoRecusada(Exception):
    """A pasta pedida nao pode ser autorizada, e a mensagem diz por que."""


def _pastas_proibidas() -> list[Path]:
    """
    Lugares que nunca viram raiz de backup.

    Montada a partir do ambiente porque a letra do disco e o idioma das pastas
    do Windows mudam de maquina para maquina; lista fixa erraria na primeira
    instalacao em outro idioma.
    """
    proibidas: list[Path] = []
    # Em maiusculas: no Windows o `os.environ` normaliza as chaves, e o ruff
    # cobra a forma canonica.
    for variavel in ("SYSTEMROOT", "WINDIR", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA"):
        valor = os.environ.get(variavel)
        if valor:
            proibidas.append(Path(valor))
    return proibidas


def _e_raiz_de_volume(caminho: Path) -> bool:
    """`C:\\`, `D:\\` ou `/`: a pasta e o proprio disco."""
    resolvido = caminho.resolve()
    return resolvido == resolvido.parent


def conferir(caminho: Path) -> Path:
    """
    Valida a pasta e devolve o caminho resolvido. Levanta se nao servir.

    A validacao acontece antes de gravar de proposito: uma configuracao com
    pasta invalida so daria erro na primeira execucao do backup — de
    madrugada, sem ninguem por perto.
    """
    if not caminho.exists():
        msg = f"a pasta nao existe: {caminho}"
        raise AutorizacaoRecusada(msg)
    if not caminho.is_dir():
        msg = f"nao e uma pasta: {caminho}"
        raise AutorizacaoRecusada(msg)

    resolvido = caminho.resolve()

    if _e_raiz_de_volume(resolvido):
        msg = (
            f"{resolvido} e o disco inteiro. Autorizar um volume completo "
            "coloca o sistema operacional no pacote: lento, inutil como backup "
            "e perigoso se o pacote vazar. Escolha as pastas de trabalho."
        )
        raise AutorizacaoRecusada(msg)

    for proibida in _pastas_proibidas():
        alvo = proibida.resolve()
        if resolvido == alvo or alvo in resolvido.parents:
            msg = (
                f"{resolvido} esta dentro de {alvo}, que e do sistema. "
                "Backup de pasta do Windows nao restaura um computador e "
                "so aumenta o tamanho do pacote."
            )
            raise AutorizacaoRecusada(msg)

    return resolvido


def autorizar(local: Local, caminho: Path) -> Configuracao:
    """
    Registra a pasta como autorizada nesta maquina.

    So e chamada por quem esta na maquina — pela linha de comando do Agente ou
    pelo instalador. Nao ha comando remoto que chegue aqui, e isso e a
    fronteira inteira do modelo.
    """
    resolvido = conferir(caminho)
    configuracao = local.carregar().com_raiz(resolvido)
    local.gravar(configuracao)
    return configuracao


def revogar(local: Local, caminho: Path) -> Configuracao:
    """
    Tira a autorizacao de uma pasta.

    Nao exige que a pasta ainda exista: revogar uma pasta que foi apagada
    precisa funcionar, senao a configuracao acumula entradas mortas que
    ninguem consegue remover.
    """
    configuracao = local.carregar().sem_raiz(caminho)
    local.gravar(configuracao)
    return configuracao


def raiz_de(configuracao: Configuracao, caminho: Path) -> Path | None:
    """
    Sob qual pasta autorizada este caminho esta? `None` se nenhuma.

    Compara caminhos **resolvidos**. Sem isso,
    `pasta-autorizada\\..\\..\\Windows` seria aceito, porque o texto comeca com
    a pasta autorizada — e o backup leria o que ninguem autorizou.
    """
    try:
        alvo = caminho.resolve()
    except OSError:
        return None

    for bruta in configuracao.raizes:
        raiz = Path(bruta).resolve()
        if alvo == raiz or raiz in alvo.parents:
            return raiz
    return None


def autorizado(configuracao: Configuracao, caminho: Path) -> bool:
    """O Agente pode ler este caminho?"""
    return raiz_de(configuracao, caminho) is not None


def exigir_autorizacao(configuracao: Configuracao, caminho: Path) -> Path:
    """
    Portao de qualquer comando que toque o disco.

    Falha fechada: na duvida, recusa. Um caminho que nao se consegue resolver
    (link quebrado, disco removido) tambem e recusado — permitir "porque
    provavelmente esta tudo bem" e como nao ter a guarda.
    """
    raiz = raiz_de(configuracao, caminho)
    if raiz is None:
        msg = (
            f"{caminho} nao esta em nenhuma pasta autorizada nesta maquina. "
            "Autorize pelo Agente, no proprio computador."
        )
        raise AutorizacaoRecusada(msg)
    return caminho.resolve()


__all__ = [
    "AutorizacaoRecusada",
    "autorizado",
    "autorizar",
    "conferir",
    "exigir_autorizacao",
    "raiz_de",
    "revogar",
]
