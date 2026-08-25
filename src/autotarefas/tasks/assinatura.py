"""Assinatura do manifesto: a diferenca entre integridade e autenticidade.

O manifesto com SHA-256 de cada arquivo prova que o pacote **nao se estragou**.
Nao prova que ninguem **mexeu nele de proposito**: quem altera um arquivo e
recalcula o manifesto passa pela conferencia sem ser notado, porque a chave da
conferencia viaja dentro do proprio pacote.

A assinatura fecha exatamente esse buraco. E um HMAC-SHA256 do manifesto com
uma chave que **nao esta dentro do pacote**: fica no cofre da plataforma, ou no
cofre do sistema operacional da maquina do Agente. Quem nao tem a chave nao
consegue produzir uma assinatura que confira — pode alterar o pacote, mas nao
consegue mais fingir que ele e o original.

Assinar o manifesto basta para cobrir o pacote inteiro: o manifesto ja carrega
o hash de cada arquivo, e a conferencia tambem compara a lista de arquivos
presentes com a declarada. Alterar conteudo, acrescentar arquivo ou remover
arquivo cai num dos tres.

Limite que continua valendo e precisa ficar dito: quem tiver a chave pode
assinar qualquer coisa. A assinatura prova que o pacote saiu de quem tem a
chave, nao que o conteudo esta correto.
"""

from __future__ import annotations

import base64
import enum
import hashlib
import hmac
import os
import secrets

#: Variavel de ambiente com a chave, em base64 urlsafe. Nunca um parametro de
#: linha de comando: argumento aparece na lista de processos e no historico do
#: terminal, onde qualquer usuario da maquina consegue ler.
VAR_CHAVE = "AUTOTAREFAS_BACKUP_KEY"  # nosec B105 — nome da variavel, nao valor

#: Nome do arquivo de assinatura dentro do pacote.
NOME_ASSINATURA = "ASSINATURA.txt"

#: Cabecalho do formato. Versionado desde o inicio: um pacote assinado hoje
#: precisa continuar conferivel quando o formato mudar.
FORMATO = "autotarefas-assinatura/1"

#: Rotulo fixo usado para derivar a impressao da chave.
_ROTULO_IMPRESSAO = b"impressao-da-chave-autotarefas"

#: HMAC-SHA256 pede pelo menos 32 bytes para nao enfraquecer o algoritmo.
TAMANHO_MINIMO = 32


class Autenticidade(enum.StrEnum):
    """O que a conferencia da assinatura conseguiu concluir."""

    NAO_ASSINADO = "nao_assinado"
    """O pacote nao tem assinatura. Integridade sim, autenticidade nao."""

    AUTENTICO = "autentico"
    """A assinatura confere com a chave em maos."""

    ADULTERADO = "adulterado"
    """Ha assinatura e ela NAO confere. Nao confie no pacote."""

    SEM_CHAVE = "sem_chave"
    """Ha assinatura, mas nao ha chave aqui para conferi-la."""

    OUTRA_CHAVE = "outra_chave"
    """A assinatura foi feita com outra chave: nada a concluir sobre o conteudo."""


class ChaveInvalida(Exception):
    """A chave configurada nao serve."""


def gerar_chave() -> str:
    """Sorteia uma chave de assinatura, pronta para guardar no cofre."""
    return base64.urlsafe_b64encode(secrets.token_bytes(TAMANHO_MINIMO)).decode("ascii")


def decodificar(bruta: str) -> bytes:
    """Converte a chave de base64 para bytes, recusando o que nao serve."""
    try:
        chave = base64.urlsafe_b64decode(bruta.strip().encode("ascii"))
    except (ValueError, UnicodeEncodeError) as erro:
        msg = f"{VAR_CHAVE} nao esta em base64 urlsafe"
        raise ChaveInvalida(msg) from erro
    if len(chave) < TAMANHO_MINIMO:
        msg = f"{VAR_CHAVE} precisa de ao menos {TAMANHO_MINIMO} bytes; tem {len(chave)}"
        raise ChaveInvalida(msg)
    return chave


def chave_configurada() -> bytes | None:
    """
    Chave do ambiente, ou `None` se nao houver nenhuma.

    Devolver `None` em vez de levantar e proposital: assinar e **opcional**.
    Um cliente que ainda nao configurou chave continua gerando pacotes uteis,
    e a conferencia diz claramente que a autenticidade nao foi comprovada — o
    que e diferente de recusar-se a fazer backup.
    """
    bruta = os.environ.get(VAR_CHAVE, "").strip()
    if not bruta:
        return None
    return decodificar(bruta)


def impressao_da_chave(chave: bytes) -> str:
    """
    Identificador curto da chave, que nao revela a chave.

    Serve para dizer "este pacote foi assinado com aquela chave, nao com esta"
    em vez de simplesmente "nao confere" — a diferenca entre trocar a chave e
    ser alvo de adulteracao.
    """
    return hmac.new(chave, _ROTULO_IMPRESSAO, hashlib.sha256).hexdigest()[:16]


def assinar(manifesto: bytes, chave: bytes) -> str:
    """Conteudo do arquivo de assinatura para um manifesto."""
    marca = hmac.new(chave, manifesto, hashlib.sha256).hexdigest()
    return (
        f"formato: {FORMATO}\n"
        f"algoritmo: HMAC-SHA256\n"
        f"impressao-da-chave: {impressao_da_chave(chave)}\n"
        f"manifesto: {marca}\n"
    )


def _campos(conteudo: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    for linha in conteudo.splitlines():
        nome, separador, valor = linha.partition(":")
        if separador:
            campos[nome.strip()] = valor.strip()
    return campos


def conferir(conteudo: str, manifesto: bytes, chave: bytes | None) -> Autenticidade:
    """
    Confere a assinatura contra o manifesto.

    Sem chave, devolve `SEM_CHAVE` em vez de `ADULTERADO`: dizer "adulterado"
    para quem so nao tem a chave em maos seria um alarme falso, e alarme falso
    treina a pessoa a ignorar o alarme de verdade.
    """
    campos = _campos(conteudo)
    marca = campos.get("manifesto", "")
    if not marca or campos.get("formato", "") != FORMATO:
        return Autenticidade.ADULTERADO
    if chave is None:
        return Autenticidade.SEM_CHAVE

    if hmac.compare_digest(marca, hmac.new(chave, manifesto, hashlib.sha256).hexdigest()):
        return Autenticidade.AUTENTICO

    declarada = campos.get("impressao-da-chave", "")
    if declarada and declarada != impressao_da_chave(chave):
        return Autenticidade.OUTRA_CHAVE
    return Autenticidade.ADULTERADO


#: Frase que acompanha cada desfecho. Fica junto do resultado, sempre: um
#: "integro" sem a ressalva certa e promessa exagerada.
EXPLICACAO: dict[Autenticidade, str] = {
    Autenticidade.NAO_ASSINADO: (
        "Detecta corrupção e alteração acidental. Não comprova autenticidade "
        "contra adulteração intencional: este pacote não foi assinado."
    ),
    Autenticidade.AUTENTICO: (
        "Assinatura confere: o pacote saiu de quem tem a chave e o conteúdo "
        "não foi alterado depois."
    ),
    Autenticidade.ADULTERADO: (
        "A assinatura NÃO confere. O pacote foi alterado depois de assinado, "
        "ou a assinatura foi forjada. Não confie nele para restaurar."
    ),
    Autenticidade.SEM_CHAVE: (
        "O pacote está assinado, mas a chave de conferência não está "
        "disponível aqui. Integridade conferida; autenticidade, não."
    ),
    Autenticidade.OUTRA_CHAVE: (
        "O pacote foi assinado com outra chave. Confira qual chave estava em "
        "uso quando ele foi gerado."
    ),
}


__all__ = [
    "EXPLICACAO",
    "FORMATO",
    "NOME_ASSINATURA",
    "TAMANHO_MINIMO",
    "VAR_CHAVE",
    "Autenticidade",
    "ChaveInvalida",
    "assinar",
    "chave_configurada",
    "conferir",
    "decodificar",
    "gerar_chave",
    "impressao_da_chave",
]
