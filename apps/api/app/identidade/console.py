"""Prova de que quem pede tem a máquina onde o serviço roda.

O convite de primeira execução e o link de reentrada vão para o **console**
porque essa é a única parte do fluxo que exige provar acesso à máquina: quem
não subiu o serviço nunca vê o token. Funciona, e tem um custo — a chave de
reentrada só nasce na partida, então voltar a entrar depois que ela venceu
exigia **reiniciar o Live**. No meio de uma sessão de testes, isso é uma
instrução ruim.

Este módulo dá o mesmo tipo de prova a um comando de fora do processo. Na
partida, o serviço escreve um token num arquivo local; quem consegue ler esse
arquivo pede uma chave nova por HTTP, sem reiniciar nada.

## Por que isto não afrouxa nada

O token vale exatamente o que vale ler um arquivo dentro da pasta do serviço —
e quem consegue isso já podia abrir `autotarefas.db`, que tem muito mais. A
prova é a mesma do console, entregue por outro caminho.

Duas regras que sustentam essa equivalência:

- **um token por partida.** Cada início sorteia outro e sobrescreve o anterior,
  então uma cópia velha não serve;
- **nunca no repositório, nunca na tela, nunca no log.** O arquivo mora em
  `.autotarefas/`, que o `.gitignore` cobre, e o valor não aparece em nenhuma
  resposta HTTP — só é comparado.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import stat
from pathlib import Path

from ..config import settings

#: Onde o token da partida fica. Pasta de runtime, coberta pelo `.gitignore`.
ARQUIVO = "console.token"

_PASTA = ".autotarefas"


def caminho() -> Path:
    return settings.repo_root / _PASTA / ARQUIVO


def gerar() -> str:
    """
    Sorteia o token desta partida e grava, substituindo o anterior.

    Devolve o valor para quem quiser exibi-lo — o serviço **não** exibe. Um
    token impresso no console apareceria em captura de tela, em log de CI e no
    histórico do terminal, e passaria a valer mais do que o arquivo.
    """
    destino = caminho()
    destino.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    destino.write_text(token, encoding="utf-8")
    # Em POSIX, só o dono lê. No Windows a herança da pasta do projeto já
    # decide o acesso, e `chmod` não tem efeito equivalente — por isso a
    # garantia real deste modulo e a equivalencia com o banco, nao a permissao.
    with contextlib.suppress(OSError, NotImplementedError):
        os.chmod(destino, stat.S_IRUSR | stat.S_IWUSR)
    return token


def ler() -> str:
    """O token desta partida, ou vazio quando não há arquivo."""
    try:
        return caminho().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def confere(oferecido: str) -> bool:
    """
    O que veio no pedido é o token desta partida?

    `compare_digest` para não vazar, pelo tempo de resposta, quantos caracteres
    do começo estavam certos.
    """
    atual = ler()
    if not atual or not oferecido:
        return False
    return secrets.compare_digest(atual, oferecido)


def descartar() -> None:
    """Apaga o token. Usado no encerramento e entre testes."""
    with contextlib.suppress(OSError):
        caminho().unlink(missing_ok=True)


__all__ = ["ARQUIVO", "caminho", "confere", "descartar", "gerar", "ler"]
