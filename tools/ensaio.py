"""Ensaio: percorrer o AutoTarefas do jeito que uma empresa percorreria.

Nada aqui e simulado. E o Live de verdade, o Agente de verdade, o banco de
verdade - so que num arquivo separado, para o ensaio poder recomecar do zero
sem levar junto os dados de ninguem.

Este arquivo escreve no console do Windows, que abre em cp1252. Por isso as
mensagens sao ASCII: um acento no lugar errado vira lixo na tela de quem esta
tentando seguir um roteiro.

O que este comando resolve, e que atrapalhava repetir o teste:

- **banco sujo.** Depois do primeiro ensaio sobram organizacao, maquina pareada
  e execucoes antigas. A jornada de um cliente novo comeca com o banco vazio, e
  `--limpo` garante isso sem tocar no `autotarefas.db` do dia a dia;
- **a porta e o endereco impresso.** O `--port` do uvicorn nao chega ate a
  aplicacao: quem sobe em outra porta recebe no console um link com a porta
  errada. Aqui as duas coisas saem do mesmo lugar, sempre iguais;
- **voltar a entrar.** A chave de reentrada so nascia na partida do servico, e
  reiniciar o Live no meio de um teste e instrucao ruim. `entrar` pede uma
  chave nova com o servico no ar.

    python tools/ensaio.py comecar --limpo   # do zero, como um cliente novo
    python tools/ensaio.py entrar            # link de entrada, sem reiniciar
    python tools/ensaio.py limpar            # apaga o ensaio
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

RAIZ = Path(__file__).resolve().parents[1]

#: O banco do ensaio. Separado de propósito: `autotarefas.db` é o do dia a dia,
#: e apagá-lo para recomeçar um teste seria apagar dado de verdade.
BANCO = RAIZ / ".autotarefas" / "ensaio.db"

#: A porta do ensaio. Não é 8000: essa é a do `mkdocs serve`, e com a
#: documentação aberta o Live não sobe.
PORTA = 7860

CABECALHO = "X-AutoTarefas-Console"


def _endereco(porta: int) -> str:
    return f"http://localhost:{porta}"


def _preparar_ambiente(porta: int, *, banco: Path) -> None:
    """
    Deixa `PORT`, `PUBLIC_BASE_URL` e `DATABASE_URL` combinando entre si.

    É a parte que ninguém acerta na mão duas vezes seguidas — e errar aqui
    produz um link impresso que não abre, que foi como este comando nasceu.
    """
    banco.parent.mkdir(parents=True, exist_ok=True)
    os.environ["PORT"] = str(porta)
    os.environ["PUBLIC_BASE_URL"] = _endereco(porta)
    os.environ["DATABASE_URL"] = f"sqlite:///{banco.as_posix()}"


@click.group(help=__doc__)
def ensaio() -> None:
    """Ensaio da jornada do cliente."""


@ensaio.command(help="Sobe o Live num banco de ensaio e imprime o que fazer.")
@click.option("--porta", default=PORTA, show_default=True, help="Porta do Live.")
@click.option(
    "--limpo/--continuar",
    default=False,
    help="Comecar do zero, apagando o ensaio anterior.",
)
def comecar(porta: int, limpo: bool) -> None:
    if limpo and BANCO.exists():
        BANCO.unlink()
        click.echo(f"Ensaio anterior apagado: {BANCO}")

    _preparar_ambiente(porta, banco=BANCO)

    frente = RAIZ / "apps" / "web" / "dist" / "index.html"
    if not frente.is_file():
        click.echo(
            "A interface nao esta compilada. Rode antes:\n  npm --prefix apps/web run build",
            err=True,
        )
        raise SystemExit(1)

    executavel = RAIZ / "dist-agente" / "AutoTarefas-Agente.exe"
    if not executavel.is_file():
        # Aviso, e nao recusa: da para percorrer o Live inteiro sem chegar a
        # instalar o Agente — so nao da para provar backup nenhum.
        click.echo(
            "[aviso] O executavel do Agente nao existe. A tela vai oferecer o\n"
            "        pacote .zip, que precisa de Python na maquina. Para o\n"
            "        caminho de dois cliques, rode antes:\n"
            "          python tools/construir_agente.py\n"
        )

    click.echo(_roteiro(porta, primeira_vez=not BANCO.exists()))

    import uvicorn

    uvicorn.run("apps.api.app.main:app", host="127.0.0.1", port=porta)


def _roteiro(porta: int, *, primeira_vez: bool) -> str:
    """O que fazer depois que o serviço subir, em ordem."""
    abertura = (
        "Banco de ensaio novo: o console vai imprimir o CONVITE de primeira\n"
        "  execucao. Siga o link e crie a organizacao."
        if primeira_vez
        else "Ensaio ja iniciado antes: o console vai imprimir um link de\n"
        "  ENTRADA para o dono que voce criou."
    )
    return (
        "\n"
        "  +-- Ensaio do AutoTarefas -------------------------------------\n"
        f"  |  Live em {_endereco(porta)}\n"
        f"  |  Banco de ensaio: {BANCO}\n"
        "  |\n"
        f"  |  {abertura}\n"
        "  |\n"
        "  |  Depois, em /app:\n"
        "  |    Dispositivos  -> Parear nova maquina -> baixe e execute\n"
        "  |    (na maquina)  -> escolha as pastas -> Concluir\n"
        "  |    Backups       -> o assistente abre sozinho -> Ativar backup\n"
        "  |    Inicio        -> o selo diz se voce esta protegido\n"
        "  |\n"
        "  |  Precisa entrar de novo, sem derrubar isto aqui? Noutro terminal:\n"
        "  |    python tools/ensaio.py entrar\n"
        "  +--------------------------------------------------------------\n"
    )


@ensaio.command(help="Pede uma chave de entrada nova, com o Live no ar.")
@click.option("--porta", default=PORTA, show_default=True, help="Porta do Live.")
def entrar(porta: int) -> None:
    import httpx

    from apps.api.app.identidade import console

    token = console.ler()
    if not token:
        click.echo(
            "Nao encontrei a prova do console. Ela e escrita quando o Live\n"
            f"sobe, em {console.caminho()}.\n"
            "O Live esta rodando?",
            err=True,
        )
        raise SystemExit(1)

    try:
        resposta = httpx.post(
            f"{_endereco(porta)}/api/auth/reentrar/emitir",
            headers={CABECALHO: token},
            timeout=10.0,
        )
    except httpx.HTTPError as erro:
        click.echo(f"Nao consegui falar com o Live em {_endereco(porta)}: {erro}", err=True)
        raise SystemExit(1) from erro

    if resposta.status_code != 200:  # noqa: PLR2004 — o unico caso de sucesso
        click.echo(f"O Live recusou: {resposta.json().get('detail', resposta.text)}", err=True)
        raise SystemExit(1)

    corpo = resposta.json()
    click.echo(
        "\n"
        "  +-- Entrar no ensaio ------------------------------------------\n"
        f"  |  {corpo['url']}\n"
        f"  |  Dono: {corpo['email']}\n"
        f"  |  Vale uma vez, por {corpo['vence_em_minutos']} minutos.\n"
        "  +--------------------------------------------------------------\n"
    )


@ensaio.command(help="Apaga o banco de ensaio para recomecar do zero.")
def limpar() -> None:
    if BANCO.exists():
        BANCO.unlink()
        click.echo(f"Apagado: {BANCO}")
    else:
        click.echo("Nao havia ensaio para apagar.")

    from apps.agente.agente import identidade as ident

    # Dito em voz alta porque a proxima pessoa vai tropecar nisto: apagar o
    # banco do servidor NAO desinstala o Agente da maquina. Ele continua
    # subindo com o Windows e tentando falar com uma organizacao que nao
    # existe mais — e o sintoma (maquina que nunca aparece) parece defeito.
    click.echo(
        "\nO Agente na maquina NAO foi tocado. Para tira-lo tambem:\n"
        f"  1. apague {ident.pasta_padrao()}\n"
        "  2. remova a partida automatica:\n"
        "     AutoTarefas-Agente.exe desinstalar-servico\n"
    )


if __name__ == "__main__":
    sys.path.insert(0, str(RAIZ))
    ensaio()
