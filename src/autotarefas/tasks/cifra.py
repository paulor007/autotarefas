"""Criptografia do pacote de backup: AES-256 no padrao WinZip.

Por que cifrar. O pacote e uma copia inteira dos arquivos da empresa. Ele viaja
para disco externo, pasta de rede e, adiante, para nuvem — lugares onde quem
encontrar o arquivo abre tudo. Cifrar transforma "quem achar o ZIP tem os dados"
em "quem achar o ZIP tem um arquivo inutil sem a senha".

Escolha do formato: **AES-256 no padrao WinZip**, e nao um formato proprio. O
7-Zip, o WinRAR e o proprio Windows (com ferramenta) abrem esse ZIP com a
senha. Um formato caseiro obrigaria o cliente a ter o AutoTarefas instalado
para recuperar os proprios arquivos, justamente no dia em que a maquina dele
nao existe mais. Vale o mesmo principio do manifesto: o pacote precisa se
sustentar sozinho.

O que a cifra **nao** esconde, e precisa estar escrito: os **nomes** dos
arquivos e as pastas continuam legiveis, junto com os tamanhos. O padrao ZIP
cifra o conteudo de cada entrada, nao a lista. Quem achar o pacote nao le o
contrato, mas ve que existe um arquivo chamado `contrato-rescisao-joao.pdf`.
Esconder tambem a lista exigiria um formato proprio — e o custo seria o
paragrafo anterior.

A senha nunca e argumento de linha de comando: argumento aparece na lista de
processos e no historico do terminal, legivel por qualquer usuario da maquina.
"""

from __future__ import annotations

import os
import secrets
import zipfile
from pathlib import Path
from typing import Protocol

import pyzipper

#: Variavel de ambiente com a senha do pacote.
VAR_SENHA = "AUTOTAREFAS_BACKUP_PASSWORD"  # nosec B105 — nome da variavel, nao valor

#: Comprimento da senha sorteada, em caracteres. 24 caracteres do alfabeto
#: urlsafe dao mais de 140 bits: forca bruta deixa de ser uma opcao, e a senha
#: ainda cabe num gerenciador sem virar duas linhas.
TAMANHO_SENHA = 24

#: Abaixo disto a senha enfraquece o AES-256 a ponto de a cifra virar enfeite.
MINIMO_SENHA = 12


class SenhaFraca(Exception):
    """A senha configurada e curta demais para valer alguma coisa."""


class PacoteCifrado(Exception):
    """O pacote esta cifrado e a senha nao foi fornecida, ou nao serve."""


class Empacotador(Protocol):
    """O minimo que o resto do codigo usa de um ZIP, cifrado ou nao."""

    def writestr(self, zinfo_or_arcname: object, data: object) -> None: ...
    def open(self, name: object, mode: str = "r") -> object: ...
    def namelist(self) -> list[str]: ...


#: O `pyzipper` tem a PROPRIA `BadZipFile`, que nao herda da biblioteca
#: padrao. Capturar so a da stdlib deixaria um arquivo que nem e ZIP explodir
#: em vez de virar "nao foi possivel abrir".
#: `OSError` entra junto porque, para quem chama, "o arquivo nao abre" e um
#: caso so — disco, permissao ou formato.
ERROS_DE_PACOTE: tuple[type[Exception], ...] = (
    zipfile.BadZipFile,
    pyzipper.BadZipFile,
    OSError,
)


def gerar_senha() -> str:
    """Sorteia uma senha forte para o pacote."""
    return secrets.token_urlsafe(TAMANHO_SENHA)


def senha_configurada() -> bytes | None:
    """
    Senha do ambiente, em bytes, ou `None` se nao houver.

    Cifrar e opcional, pelo mesmo motivo de assinar: um cliente que ainda nao
    configurou senha precisa continuar tendo backup. O que nao pode e o
    produto dizer que cifrou quando nao cifrou.
    """
    bruta = os.environ.get(VAR_SENHA, "")
    if not bruta:
        return None
    if len(bruta) < MINIMO_SENHA:
        msg = (
            f"{VAR_SENHA} tem {len(bruta)} caracteres; o minimo e {MINIMO_SENHA}. "
            "Senha curta transforma AES-256 em enfeite."
        )
        raise SenhaFraca(msg)
    return bruta.encode("utf-8")


def abrir_para_escrita(caminho: Path | str, senha: bytes | None) -> zipfile.ZipFile:
    """
    Abre o pacote para escrita, cifrado ou nao.

    Com senha, usa `AESZipFile` com AES-256 no padrao WinZip. Sem senha,
    continua o `zipfile` da biblioteca padrao: nao ha razao para pagar o custo
    de outra dependencia no caminho em que ela nao faz nada.
    """
    if senha is None:
        return zipfile.ZipFile(
            caminho,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        )
    pacote = pyzipper.AESZipFile(
        caminho,
        mode="w",
        compression=pyzipper.ZIP_DEFLATED,
        compresslevel=6,
        encryption=pyzipper.WZ_AES,
    )
    pacote.setencryption(pyzipper.WZ_AES, nbits=256)
    pacote.setpassword(senha)
    # `AESZipFile` herda de `ZipFile`: quem chama nao precisa saber qual
    # dos dois recebeu.
    return pacote  # type: ignore[no-any-return]


def abrir_para_leitura(caminho: Path | str, senha: bytes | None) -> zipfile.ZipFile:
    """
    Abre o pacote para leitura, com senha quando houver.

    `AESZipFile` le tambem pacote sem cifra, entao ele serve para os dois
    casos e evita adivinhar o formato pelo nome do arquivo.
    """
    pacote = pyzipper.AESZipFile(caminho)
    if senha is not None:
        pacote.setpassword(senha)
    return pacote  # type: ignore[no-any-return]


def nova_entrada(
    pacote: zipfile.ZipFile, arcname: str, data: tuple[int, int, int, int, int, int]
) -> zipfile.ZipInfo:
    """
    Cria a entrada do jeito que ESTE pacote espera.

    O `pyzipper` tem a propria classe de entrada (ela carrega os campos do
    AES) e recusa uma `ZipInfo` da biblioteca padrao — com um erro obscuro,
    dizendo que um `ZipInfo` nao tem `.find`. Perguntar ao pacote qual classe
    usar mantem o resto do codigo igual nos dois caminhos.
    """
    classe = getattr(pacote, "zipinfo_cls", zipfile.ZipInfo)
    entrada: zipfile.ZipInfo = classe(arcname, date_time=data)
    entrada.compress_type = zipfile.ZIP_DEFLATED
    return entrada


def esta_cifrado(pacote: zipfile.ZipFile) -> bool:
    """
    Diz se alguma entrada do pacote esta cifrada.

    Le a flag do proprio ZIP em vez de tentar abrir e ver se falha: assim a
    mensagem para a pessoa e "este pacote esta cifrado, informe a senha", e
    nao um erro de biblioteca.
    """
    return any(info.flag_bits & 0x1 for info in pacote.infolist())


#: Frase que acompanha um pacote cifrado. A ressalva sobre os nomes vai junto,
#: sempre: quem acha que o nome tambem esta escondido toma decisao errada
#: sobre onde guardar o pacote.
EXPLICACAO_CIFRADO = (
    "Pacote cifrado com AES-256 (padrão WinZip): abre no 7-Zip ou no WinRAR "
    "com a senha. Os nomes dos arquivos e das pastas continuam visíveis — o "
    "padrão ZIP cifra o conteúdo, não a lista."
)

EXPLICACAO_SEM_CIFRA = "Pacote não cifrado: quem tiver acesso ao arquivo lê todo o conteúdo."


__all__ = [
    "ERROS_DE_PACOTE",
    "EXPLICACAO_CIFRADO",
    "EXPLICACAO_SEM_CIFRA",
    "MINIMO_SENHA",
    "TAMANHO_SENHA",
    "VAR_SENHA",
    "PacoteCifrado",
    "SenhaFraca",
    "abrir_para_escrita",
    "abrir_para_leitura",
    "esta_cifrado",
    "gerar_senha",
    "nova_entrada",
    "senha_configurada",
]
