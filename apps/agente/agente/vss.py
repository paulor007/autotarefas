"""Instantaneo de volume (VSS): copiar arquivo que esta aberto.

O problema que isto resolve e o mais comum de todos num escritorio: a planilha
esta aberta no Excel, o Windows recusa a leitura, e o arquivo mais importante
da empresa fica **de fora** do backup. Ate aqui isso virava ressalva visivel —
melhor que silencio, mas ainda um arquivo perdido.

O Volume Shadow Copy Service tira uma foto consistente do volume inteiro. O
backup le da foto, e nao do disco vivo: o Excel continua com o arquivo aberto e
o Agente copia a versao congelada no instante do disparo.

Duas coisas que precisam ficar ditas, porque mudam o que se pode prometer:

1. **Exige elevacao.** Criar instantaneo e operacao administrativa do Windows.
   Sem elevacao, o Agente **recusa com motivo** — nao tenta, nao finge, nao
   cai em silencio para o modo antigo sem avisar.
2. **A foto e do VOLUME, nao do aplicativo.** Ela garante que o arquivo esta
   inteiro no nivel do sistema de arquivos; nao garante que o aplicativo tinha
   terminado de gravar o que estava fazendo. Para banco de dados isso importa,
   e o produto nao promete o contrario.

Instantaneo orfao e lixo caro: cada um consome espaco no volume ate alguem
apagar. Este modulo apaga o que criou, **inclusive quando o backup falha**.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import os
import re
import subprocess  # nosec B404 — chamadas fixas ao PowerShell, sem entrada do usuario
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

#: Quanto esperar o PowerShell. Criar instantaneo em volume grande demora.
TIMEOUT_S = 180.0

#: Forma do caminho de dispositivo que o VSS devolve.
_DISPOSITIVO = re.compile(r"^\\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeShadowCopy\d+$")


class VSSIndisponivel(Exception):
    """Nao da para usar VSS nesta maquina, e a mensagem diz por que."""


def no_windows() -> bool:
    """VSS e do Windows. Em outro sistema, nem se tenta."""
    return os.name == "nt"


def elevado() -> bool:
    """
    O processo esta rodando como administrador?

    Conferir ANTES de tentar evita um erro de WMI ilegivel e permite dizer a
    coisa certa: "o Agente precisa rodar como servico do sistema para copiar
    arquivo aberto".
    """
    if not no_windows():
        return False
    try:
        # `ctypes.windll` so existe no Windows; o `no_windows()` acima e o que
        # garante que esta linha nunca roda em outro sistema.
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def motivo_de_indisponibilidade() -> str:
    """Frase pronta para a tela e para o log. Vazia quando da para usar."""
    if not no_windows():
        return "instantaneo de volume so existe no Windows"
    if not elevado():
        return (
            "criar instantaneo de volume exige privilegio de administrador. "
            "Instale o Agente como servico do sistema para copiar arquivos "
            "que estao abertos."
        )
    return ""


def disponivel() -> bool:
    """Da para usar VSS agora?"""
    return not motivo_de_indisponibilidade()


def volume_de(caminho: Path) -> str:
    """
    Volume de um caminho, no formato `C:\\` que o VSS espera.

    Sem a barra final o WMI recusa o pedido com um erro generico, que custa
    tempo de depuracao a cada vez.
    """
    unidade = caminho.resolve().drive
    if not unidade:
        msg = f"nao foi possivel determinar o volume de {caminho}"
        raise VSSIndisponivel(msg)
    return f"{unidade}\\"


def _powershell(script: str) -> str:
    """
    Roda um script fixo no PowerShell e devolve a saida.

    Sem `shell=True` e sem entrada do usuario no comando: os unicos valores
    interpolados sao a letra do volume e o identificador do instantaneo, os
    dois validados antes.
    """
    try:
        # `powershell` e `cmd` vem do PATH do Windows; apontar caminho
        # absoluto amarraria o Agente a uma instalacao especifica e
        # quebraria em Windows com pastas de sistema em outro lugar.
        concluido = subprocess.run(  # noqa: S603  # nosec B603 B607
            [  # noqa: S607
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        msg = f"nao foi possivel falar com o PowerShell: {erro}"
        raise VSSIndisponivel(msg) from erro

    if concluido.returncode != 0:
        detalhe = (concluido.stderr or concluido.stdout or "").strip().splitlines()
        msg = f"o Windows recusou o instantaneo: {detalhe[0] if detalhe else 'sem detalhe'}"
        raise VSSIndisponivel(msg)
    return concluido.stdout.strip()


@dataclass
class Instantaneo:
    """Uma foto do volume, viva enquanto este objeto existir."""

    identificador: str
    volume: str
    dispositivo: str
    #: Link que da acesso ao dispositivo por um caminho comum.
    ponto: Path | None = None

    def mapear(self, caminho: Path) -> Path:
        """
        Traduz um caminho do disco vivo para o mesmo caminho dentro da foto.

        `C:\\dados\\nota.xlsx` vira `<ponto>\\dados\\nota.xlsx`. Sem o ponto de
        acesso, o caminho de dispositivo do VSS nao e utilizavel pelas
        funcoes normais de arquivo.
        """
        if self.ponto is None:
            msg = "instantaneo sem ponto de acesso"
            raise VSSIndisponivel(msg)
        absoluto = caminho.resolve()
        relativo = absoluto.relative_to(Path(self.volume))
        return self.ponto / relativo


def criar(volume: str) -> Instantaneo:
    """
    Cria o instantaneo do volume. Levanta `VSSIndisponivel` quando nao da.

    A conferencia de elevacao vem antes de qualquer chamada: assim a pessoa le
    "instale como servico do sistema" em vez de um erro de WMI.
    """
    motivo = motivo_de_indisponibilidade()
    if motivo:
        raise VSSIndisponivel(motivo)
    if not re.fullmatch(r"[A-Za-z]:\\", volume):
        msg = f"volume invalido: {volume}"
        raise VSSIndisponivel(msg)

    letra = volume[0]
    saida = _powershell(
        "$r = (Get-WmiObject -List Win32_ShadowCopy).Create('"
        + letra
        + ":\\', 'ClientAccessible'); "
        'if ($r.ReturnValue -ne 0) { Write-Error "ReturnValue=$($r.ReturnValue)"; exit 1 }; '
        "$s = Get-WmiObject Win32_ShadowCopy | Where-Object { $_.ID -eq $r.ShadowID }; "
        "[Console]::Out.Write((ConvertTo-Json @{ id = $s.ID; device = $s.DeviceObject }))"
    )

    try:
        dados = json.loads(saida)
    except json.JSONDecodeError as erro:
        msg = "o Windows respondeu de forma inesperada ao criar o instantaneo"
        raise VSSIndisponivel(msg) from erro

    dispositivo = str(dados.get("device", ""))
    if not _DISPOSITIVO.match(dispositivo):
        msg = f"caminho de instantaneo inesperado: {dispositivo!r}"
        raise VSSIndisponivel(msg)

    return Instantaneo(
        identificador=str(dados.get("id", "")), volume=volume, dispositivo=dispositivo
    )


def apagar(instantaneo: Instantaneo) -> None:
    """
    Apaga o instantaneo. Nao levanta: limpeza nao pode esconder o erro original.

    Instantaneo orfao consome espaco no volume ate alguem notar — e ninguem
    nota, porque ele nao aparece em lugar nenhum do dia a dia.
    """
    if not instantaneo.identificador:
        return
    with contextlib.suppress(VSSIndisponivel):
        _powershell(
            "Get-WmiObject Win32_ShadowCopy | Where-Object { $_.ID -eq '"
            + instantaneo.identificador.replace("'", "")
            + "' } | ForEach-Object { $_.Delete() }"
        )


def _ligar_ponto(instantaneo: Instantaneo) -> Path:
    """
    Cria o link que torna o instantaneo acessivel por caminho comum.

    A barra final no destino nao e detalhe: sem ela o `mklink` cria um link
    que existe mas nao lista nada, e o backup sai vazio sem erro nenhum.
    """
    destino = Path(tempfile.mkdtemp(prefix="autotarefas-vss-")) / "volume"
    concluido = subprocess.run(  # noqa: S603  # nosec B603 B607
        # `mklink` e interno do `cmd`, entao nao ha executavel proprio para
        # apontar por caminho absoluto.
        ["cmd", "/c", "mklink", "/D", str(destino), instantaneo.dispositivo + "\\"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        check=False,
    )
    if concluido.returncode != 0 or not destino.exists():
        msg = "nao foi possivel montar o instantaneo para leitura"
        raise VSSIndisponivel(msg)
    return destino


def _desligar_ponto(ponto: Path | None) -> None:
    if ponto is None:
        return
    with contextlib.suppress(OSError):
        ponto.unlink()
    with contextlib.suppress(OSError):
        ponto.parent.rmdir()


@contextlib.contextmanager
def instantaneo_de(volume: str) -> Iterator[Instantaneo]:
    """
    Cria a foto, entrega, e apaga no fim — inclusive quando algo falha.

    O `finally` e o ponto: um backup que morre no meio nao pode deixar o
    instantaneo ocupando espaco no volume do cliente para sempre.
    """
    foto = criar(volume)
    try:
        foto.ponto = _ligar_ponto(foto)
        yield foto
    finally:
        _desligar_ponto(foto.ponto)
        apagar(foto)


__all__ = [
    "TIMEOUT_S",
    "Instantaneo",
    "VSSIndisponivel",
    "apagar",
    "criar",
    "disponivel",
    "elevado",
    "instantaneo_de",
    "motivo_de_indisponibilidade",
    "no_windows",
    "volume_de",
]
