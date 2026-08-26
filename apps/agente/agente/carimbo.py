"""O instalador ja sabe de onde veio: o carimbo colado no fim do executavel.

Sem isto, o cliente teria que digitar o endereco do Live e um codigo de seis
caracteres numa janela — dois campos, dois jeitos de errar, e o suporte
recebendo "diz que o codigo esta errado" pelo resto da vida.

O Live sabe quem clicou em "Parear nova maquina". Entao o download ja sai
carimbado: mesmo executavel para todo mundo, com um pedacinho de JSON colado no
fim. Ao subir, o programa le o proprio arquivo e descobre para onde ligar.

**Por que colar no fim, e nao gerar um `.exe` por download.** Construir um
executavel leva dezenas de segundos e alguns megabytes de trabalho; um download
nao pode esperar por isso. Colar bytes no fim de um arquivo pronto e uma copia —
custa o tempo de escrever o arquivo, e nada mais. E funciona porque tanto `.exe`
do Windows quanto arquivo ZIP sao formatos que ignoram sobras no fim: o carimbo
nao atrapalha a execucao.

**O que o carimbo carrega, e o que ele NAO carrega.** Endereco do servidor e
codigo de pareamento. O codigo vale poucos minutos, serve uma vez so e ja e
mostrado na tela de quem pediu — carrega-lo aqui nao cria exposicao nova. O que
nunca entra: chave, senha, token de sessao, credencial de nuvem. Um instalador
que vazasse qualquer um deles seria um vazamento por download, e nao ha como
recolher.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

#: Separador entre o programa e o carimbo. Improvavel de aparecer por acidente
#: dentro de um executavel, e facil de achar de tras para frente.
MARCA = b"\n<<<AUTOTAREFAS-CARIMBO>>>\n"

#: Teto do carimbo. Ele guarda endereco e codigo; qualquer coisa muito maior e
#: sinal de que alguem tentou enfiar outra coisa ali.
LIMITE_BYTES = 4096

#: Quanto do fim do arquivo vale a pena ler. Suficiente para o carimbo com folga,
#: e pequeno o bastante para nao carregar um executavel inteiro na memoria toda
#: vez que o programa sobe.
CAUDA_BYTES = 64 * 1024


def gravar(base: Path, destino: Path, dados: dict[str, str]) -> int:
    """
    Escreve `destino` = `base` + carimbo. Devolve o tamanho final, em bytes.

    A base nunca e alterada: e ela que serve todos os downloads seguintes, e
    carimbar por cima transformaria o segundo cliente no primeiro.
    """
    corpo = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(corpo) > LIMITE_BYTES:
        msg = f"carimbo grande demais ({len(corpo)} bytes); o limite e {LIMITE_BYTES}"
        raise ValueError(msg)

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(base.read_bytes() + MARCA + corpo)
    return destino.stat().st_size


def ler(executavel: Path) -> dict[str, str]:
    """
    Le o carimbo de um arquivo. Devolve `{}` quando nao ha nenhum.

    Nao levanta: executavel sem carimbo e o caso normal de quem compilou por
    conta propria, e o assistente simplesmente pergunta o endereco. Um
    instalador que morre por falta de carimbo seria pior do que um que pergunta.
    """
    try:
        with executavel.open("rb") as arquivo:
            arquivo.seek(0, 2)
            tamanho = arquivo.tell()
            arquivo.seek(max(0, tamanho - CAUDA_BYTES))
            cauda = arquivo.read()
    except OSError:
        return {}

    posicao = cauda.rfind(MARCA)
    if posicao < 0:
        return {}

    bruto = cauda[posicao + len(MARCA) :]
    if len(bruto) > LIMITE_BYTES:
        return {}

    try:
        dados = json.loads(bruto.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        # Carimbo truncado ou corrompido: melhor perguntar do que adivinhar o
        # endereco de um servidor.
        return {}

    if not isinstance(dados, dict):
        return {}
    return {str(chave): str(valor) for chave, valor in dados.items()}


def do_processo() -> dict[str, str]:
    """
    O carimbo deste programa, quando ele e um executavel congelado.

    Rodando do codigo-fonte nao ha o que ler — e nem faria sentido: quem roda do
    codigo tem o terminal ali do lado.
    """
    if not getattr(sys, "frozen", False):
        return {}
    return ler(Path(sys.executable))


__all__ = ["CAUDA_BYTES", "LIMITE_BYTES", "MARCA", "do_processo", "gravar", "ler"]
