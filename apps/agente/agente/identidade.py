"""Identidade do dispositivo: o par de chaves que prova quem e a maquina.

O Agente nao guarda senha nem token compartilhado. Ele gera um par Ed25519 na
primeira execucao: a **privada** nunca sai da maquina; a **publica** e enviada
ao servidor no pareamento. Depois disso, cada conexao e provada assinando um
desafio aleatorio.

Por que par de chaves, e nao um token. Token e segredo compartilhado: existe
uma copia no servidor. Se o banco do servidor vazar, todos os dispositivos
podem ser personificados. Com chave assimetrica, o servidor guarda so a parte
publica — que nao serve para se passar por ninguem.

Onde a privada mora, em ordem:

1. **Cofre do Windows** (Credential Manager, via `keyring`). O sistema protege
   o valor com a conta do usuario ou do servico.
2. **Arquivo com permissao restrita**, quando nao ha cofre disponivel. E pior,
   e o Agente **diz** que e pior no seu estado — em vez de fingir que os dois
   caminhos sao equivalentes.

A privada nunca e impressa, nunca vai para log e nunca aparece numa resposta.
O que se mostra e a impressao digital: os primeiros bytes do SHA-256 da
publica, que identifica o dispositivo sem revelar nada.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

#: Servico e conta usados no cofre do sistema operacional.
SERVICO = "autotarefas-agente"
CONTA_CHAVE = "chave-do-dispositivo"

#: Nome do arquivo de fallback, dentro da pasta de configuracao do Agente.
ARQUIVO_CHAVE = "dispositivo.chave"

#: Desliga o cofre do sistema operacional. Existe por dois motivos concretos:
#: a suite nao pode escrever no Credential Manager da maquina de quem roda os
#: testes, e um Agente para servidor Linux sem sessao grafica nao tem cofre
#: nenhum para usar. Sem esta valvula, testar o caminho de arquivo exigiria
#: sujar o cofre real — e foi o que aconteceu antes de ela existir.
VAR_SEM_COFRE = "AUTOTAREFAS_AGENTE_SEM_COFRE"


class SemIdentidade(Exception):
    """Nao ha chave privada nesta maquina."""


class Guarda:
    """
    Onde a chave privada e guardada.

    E uma classe com dois caminhos, e nao um `if` espalhado, porque a suite
    precisa exercitar os dois — inclusive o pior — e porque o estado do Agente
    tem que conseguir dizer qual deles esta em uso.
    """

    def __init__(self, pasta: Path, *, usar_cofre_do_sistema: bool = True) -> None:
        self.pasta = pasta
        self.usar_cofre_do_sistema = usar_cofre_do_sistema

    # --------------------------------------------------------
    # Cofre do sistema
    # --------------------------------------------------------

    def _keyring(self) -> object | None:
        if not self.usar_cofre_do_sistema:
            return None
        if os.environ.get(VAR_SEM_COFRE, "").strip().lower() in {"1", "true", "yes", "on"}:
            return None
        try:
            import keyring
        except ImportError:
            return None
        try:
            backend = keyring.get_keyring()
        except Exception:  # noqa: BLE001 — backend do SO falha de N jeitos
            return None
        # `fail` e o backend que o keyring instala quando nao acha nenhum de
        # verdade. Usa-lo daria a impressao de que ha cofre onde nao ha.
        if backend.__class__.__name__.lower().startswith("fail"):
            return None
        return keyring

    @property
    def caminho_do_arquivo(self) -> Path:
        return self.pasta / ARQUIVO_CHAVE

    def onde_guarda(self) -> str:
        """Descricao curta de onde a chave esta. Vai para o estado do Agente."""
        return "cofre do sistema" if self._keyring() is not None else "arquivo local"

    # --------------------------------------------------------
    # Gravar e ler
    # --------------------------------------------------------

    def gravar(self, privada_em_base64: str) -> None:
        cofre = self._keyring()
        if cofre is not None:
            cofre.set_password(SERVICO, CONTA_CHAVE, privada_em_base64)  # type: ignore[attr-defined]
            return
        self.pasta.mkdir(parents=True, exist_ok=True)
        destino = self.caminho_do_arquivo
        destino.write_text(privada_em_base64, encoding="ascii")
        _restringir(destino)

    def ler(self) -> str | None:
        cofre = self._keyring()
        if cofre is not None:
            with contextlib.suppress(Exception):
                guardada = cofre.get_password(SERVICO, CONTA_CHAVE)  # type: ignore[attr-defined]
                if guardada:
                    return str(guardada)
        destino = self.caminho_do_arquivo
        if destino.is_file():
            return destino.read_text(encoding="ascii").strip()
        return None

    def apagar(self) -> None:
        """Esquece a chave. Usado ao revogar o dispositivo nesta maquina."""
        cofre = self._keyring()
        if cofre is not None:
            with contextlib.suppress(Exception):
                cofre.delete_password(SERVICO, CONTA_CHAVE)  # type: ignore[attr-defined]
        self.caminho_do_arquivo.unlink(missing_ok=True)


def _restringir(caminho: Path) -> None:
    """
    Deixa o arquivo legivel so pelo dono.

    No Windows o modo POSIX e uma aproximacao — a ACL de verdade e o que vale,
    e ela e herdada da pasta do servico. Ainda assim vale aplicar: em Linux
    (contêiner, futuro agente para servidor) isso e a protecao real, e nao
    custa nada onde nao e.
    """
    with contextlib.suppress(OSError, NotImplementedError):
        caminho.chmod(stat.S_IRUSR | stat.S_IWUSR)


@dataclass(frozen=True)
class Identidade:
    """O par de chaves deste dispositivo."""

    privada: ed25519.Ed25519PrivateKey

    @property
    def publica(self) -> ed25519.Ed25519PublicKey:
        return self.privada.public_key()

    @property
    def publica_em_base64(self) -> str:
        """Chave publica em base64. E o que vai para o servidor no pareamento."""
        bruta = self.publica.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(bruta).decode("ascii")

    @property
    def impressao(self) -> str:
        """
        Identificador legivel do dispositivo, derivado da publica.

        Serve para a pessoa comparar o que aparece na tela do Live com o que o
        Agente mostra na maquina — e perceber se estao pareando o dispositivo
        errado.
        """
        bruta = self.publica.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        digesto = hashlib.sha256(bruta).hexdigest()[:16].upper()
        return "-".join(digesto[i : i + 4] for i in range(0, len(digesto), 4))

    def assinar(self, desafio: bytes) -> str:
        """Assina um desafio do servidor. E a prova de posse da privada."""
        return base64.b64encode(self.privada.sign(desafio)).decode("ascii")


def gerar() -> Identidade:
    """Sorteia um par novo."""
    return Identidade(privada=ed25519.Ed25519PrivateKey.generate())


def _privada_em_base64(identidade: Identidade) -> str:
    bruta = identidade.privada.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.b64encode(bruta).decode("ascii")


def carregar(guarda: Guarda) -> Identidade:
    """Le a identidade guardada. `SemIdentidade` quando nao ha nenhuma."""
    guardada = guarda.ler()
    if not guardada:
        msg = "este dispositivo ainda nao tem identidade: rode o pareamento"
        raise SemIdentidade(msg)
    bruta = base64.b64decode(guardada.encode("ascii"))
    return Identidade(privada=ed25519.Ed25519PrivateKey.from_private_bytes(bruta))


def obter_ou_criar(guarda: Guarda) -> tuple[Identidade, bool]:
    """
    Devolve `(identidade, criada_agora)`.

    Criar so quando nao existe e importante: gerar um par novo a cada partida
    do servico faria o dispositivo perder o pareamento toda vez que a maquina
    reiniciasse.
    """
    try:
        return carregar(guarda), False
    except SemIdentidade:
        identidade = gerar()
        guarda.gravar(_privada_em_base64(identidade))
        return identidade, True


def conferir_assinatura(publica_em_base64: str, desafio: bytes, assinatura: str) -> bool:
    """
    Confere, do lado do servidor, que o dispositivo tem mesmo a privada.

    Fica aqui, junto do resto, para que as duas pontas usem exatamente o mesmo
    formato de chave e de assinatura. Um formato divergindo em base64 daria um
    "assinatura invalida" que ninguem consegue depurar.
    """
    try:
        publica = ed25519.Ed25519PublicKey.from_public_bytes(
            base64.b64decode(publica_em_base64.encode("ascii"))
        )
        publica.verify(base64.b64decode(assinatura.encode("ascii")), desafio)
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def pasta_padrao() -> Path:
    """
    Onde o Agente guarda configuracao nesta maquina.

    `PROGRAMDATA` e nao a pasta do usuario: o Agente roda como servico, e um
    caminho por usuario faria a configuracao sumir quando o servico troca de
    conta.
    """
    base = os.environ.get("PROGRAMDATA") or os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "AutoTarefas"
    return Path.home() / ".autotarefas"


__all__ = [
    "ARQUIVO_CHAVE",
    "CONTA_CHAVE",
    "SERVICO",
    "VAR_SEM_COFRE",
    "Guarda",
    "Identidade",
    "SemIdentidade",
    "carregar",
    "conferir_assinatura",
    "gerar",
    "obter_ou_criar",
    "pasta_padrao",
]
