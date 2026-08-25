"""Para onde o pacote vai: disco local, disco externo, pasta de rede.

Ate aqui o pacote ficava ao lado da pasta copiada — util para experimentar,
inutil como backup de verdade. Um pacote no mesmo disco da origem nao protege
contra o defeito mais comum (o disco morrer) nem contra o mais caro (o
ransomware, que cifra tudo o que alcanca).

Este modulo trata o destino como parte do backup, e nao como um detalhe do
final. Tres coisas acontecem, nesta ordem, e nenhuma e opcional:

1. **Conferir antes de copiar** — destino existe, aceita escrita, tem espaco.
   Descobrir que o disco externo esta cheio depois de meia hora de copia e
   descobrir tarde.
2. **Copiar por pedacos** — o mesmo motivo do backup: um pacote de 40 GB nao
   pode passar pela memoria.
3. **Conferir DEPOIS de copiar** — a copia no destino e verificada com o
   mesmo verificador do pacote original. Rede que cai no meio e cabo USB ruim
   produzem arquivos com o tamanho certo e o conteudo errado; sem esta
   conferencia, o cliente descobriria no dia da restauracao.

Sobre "mesmo disco": o aviso da 02.A vira **recusa** quando o destino e
declarado como externo. Avisar e o certo quando a pessoa escolheu o caminho;
recusar e o certo quando ela pediu explicitamente um destino externo e
apontou, sem perceber, para o proprio disco de origem.
"""

from __future__ import annotations

import ctypes
import enum
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from autotarefas.tasks.backup import verify_backup

#: Tamanho do pedaco na copia. 1 MB rende mais que 64 KB em rede.
PEDACO = 1024 * 1024

#: Folga exigida alem do tamanho do pacote. Disco que enche por completo
#: costuma corromper o proprio sistema de arquivos.
FOLGA_BYTES = 64 * 1024 * 1024


class TipoDeDestino(enum.StrEnum):
    """Que tipo de lugar e este."""

    LOCAL = "local"
    """Outra pasta ou outro disco fixo da mesma maquina."""

    EXTERNO = "externo"
    """Midia removivel: HD externo, pendrive."""

    REDE = "rede"
    """Pasta compartilhada (`\\\\servidor\\pasta`)."""


class DestinoRecusado(Exception):
    """O destino nao serve, e a mensagem diz por que."""


# Codigos do `GetDriveTypeW` do Windows.
_REMOVIVEL = 2
_FIXO = 3
_REMOTO = 4


def tipo_do_caminho(caminho: Path) -> TipoDeDestino:
    """
    Descobre o tipo de destino olhando o sistema, e nao o texto.

    Perguntar ao Windows evita duas confusoes comuns: uma unidade de rede
    mapeada como `Z:` parece local pelo nome, e um caminho UNC apontado para
    a propria maquina parece remoto sem ser.
    """
    texto = str(caminho)
    if texto.startswith("\\\\"):
        return TipoDeDestino.REDE

    if os.name != "nt":
        return TipoDeDestino.LOCAL

    raiz = caminho.resolve().drive
    if not raiz:
        return TipoDeDestino.LOCAL

    codigo = ctypes.windll.kernel32.GetDriveTypeW(f"{raiz}\\")
    if codigo == _REMOVIVEL:
        return TipoDeDestino.EXTERNO
    if codigo == _REMOTO:
        return TipoDeDestino.REDE
    return TipoDeDestino.LOCAL


def mesmo_volume(origem: Path, destino: Path) -> bool:
    """
    Origem e destino estao no mesmo disco fisico?

    Compara o identificador de volume do sistema, e nao a letra: `C:\\dados` e
    `D:\\backup` podem ser o mesmo disco particionado, e um pacote la nao
    protege contra o disco morrer.
    """
    try:
        return os.stat(origem).st_dev == os.stat(destino).st_dev
    except OSError:
        return False


@dataclass(frozen=True)
class Destino:
    """Um lugar validado para onde o pacote pode ir."""

    caminho: Path
    tipo: TipoDeDestino

    @property
    def descricao(self) -> str:
        """Frase curta para a tela e para o historico."""
        rotulos = {
            TipoDeDestino.LOCAL: "pasta local",
            TipoDeDestino.EXTERNO: "disco externo",
            TipoDeDestino.REDE: "pasta de rede",
        }
        return f"{rotulos[self.tipo]} ({self.caminho})"


def espaco_livre(caminho: Path) -> int:
    """Bytes livres no destino. Zero quando nao da para saber."""
    try:
        return shutil.disk_usage(caminho).free
    except OSError:
        return 0


def preparar(
    caminho: Path, *, tipo_declarado: TipoDeDestino | None = None, origens: tuple[Path, ...] = ()
) -> Destino:
    """
    Confere o destino antes de qualquer copia.

    `tipo_declarado` e o que a pessoa escolheu na tela. Quando ela diz
    "externo" e o caminho aponta para o disco de origem, isso e recusa e nao
    aviso: ela pediu protecao contra o disco morrer, e o que receberia nao
    protege contra nada.
    """
    try:
        caminho.mkdir(parents=True, exist_ok=True)
    except OSError as erro:
        msg = f"nao foi possivel usar {caminho} como destino: {erro}"
        raise DestinoRecusado(msg) from erro

    if not os.access(caminho, os.W_OK):
        msg = f"{caminho} existe mas nao aceita escrita por este usuario"
        raise DestinoRecusado(msg)

    tipo = tipo_do_caminho(caminho)
    if tipo_declarado is not None and tipo_declarado is not tipo:
        msg = (
            f"voce escolheu '{tipo_declarado.value}', mas {caminho} e "
            f"'{tipo.value}' para o sistema. Confira a letra do disco ou o "
            "endereco da pasta de rede."
        )
        raise DestinoRecusado(msg)

    if tipo is not TipoDeDestino.LOCAL:
        repetidos = [origem for origem in origens if mesmo_volume(origem, caminho)]
        if repetidos:
            msg = (
                f"{caminho} esta no MESMO disco de {repetidos[0]}. Um destino "
                "externo no mesmo disco nao protege contra o disco falhar nem "
                "contra ransomware."
            )
            raise DestinoRecusado(msg)

    return Destino(caminho=caminho.resolve(), tipo=tipo)


def entregar(pacote: Path, destino: Destino) -> dict[str, object]:
    """
    Copia o pacote para o destino e **confere a copia**.

    A conferencia no destino nao e zelo excessivo: rede que cai no meio e cabo
    USB ruim produzem arquivos com o tamanho certo e conteudo errado. Sem
    conferir, o cliente descobriria no dia da restauracao.

    A copia vai para um nome temporario e so recebe o nome final quando
    termina — pelo mesmo motivo do `.parcial` do pacote: um arquivo pela
    metade com o nome certo parece um backup completo.
    """
    if not pacote.is_file():
        msg = f"o pacote nao existe: {pacote.name}"
        raise DestinoRecusado(msg)

    tamanho = pacote.stat().st_size
    livre = espaco_livre(destino.caminho)
    if livre and livre < tamanho + FOLGA_BYTES:
        msg = (
            f"espaco insuficiente em {destino.caminho}: o pacote tem "
            f"{tamanho / 1024 / 1024:.1f} MB e ha "
            f"{livre / 1024 / 1024:.1f} MB livres."
        )
        raise DestinoRecusado(msg)

    final = destino.caminho / pacote.name
    parcial = final.with_suffix(final.suffix + ".parcial")

    try:
        with pacote.open("rb") as origem, parcial.open("wb") as copia:
            while pedaco := origem.read(PEDACO):
                copia.write(pedaco)
        os.replace(parcial, final)
    except OSError as erro:
        parcial.unlink(missing_ok=True)
        msg = f"falha ao copiar para {destino.caminho}: {erro}"
        raise DestinoRecusado(msg) from erro

    relatorio = verify_backup(final)
    if not relatorio.ok:
        msg = (
            f"o pacote chegou a {destino.caminho}, mas nao confere la: "
            f"{relatorio.problem or 'conteudo diferente do manifesto'}. "
            "A copia foi descartada."
        )
        final.unlink(missing_ok=True)
        raise DestinoRecusado(msg)

    return {
        "destino": destino.descricao,
        "tipo": destino.tipo.value,
        "arquivo": final.name,
        "tamanho_bytes": tamanho,
        "conferido_no_destino": True,
    }


__all__ = [
    "FOLGA_BYTES",
    "PEDACO",
    "Destino",
    "DestinoRecusado",
    "TipoDeDestino",
    "entregar",
    "espaco_livre",
    "mesmo_volume",
    "preparar",
    "tipo_do_caminho",
]
