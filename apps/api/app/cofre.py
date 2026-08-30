"""Cofre de segredos da plataforma: chave de HMAC, senha de criptografia, credencial de destino.

Tres regras, e nenhuma delas e negociavel:

1. **A chave mestra nunca esta no repositorio.** Ela vem do ambiente
   (`AUTOTAREFAS_MASTER_KEY`) ou do cofre do sistema operacional. Sem ela o
   cofre fica **trancado** e quem depende dele falha com mensagem clara — nao
   ha queda silenciosa para uma chave embutida, porque chave embutida em codigo
   publicado nao protege nada.
2. **O segredo nunca sai para o frontend.** As rotas devolvem nome, data e uma
   impressao; o valor so e revelado dentro do servidor, para quem vai usa-lo.
3. **Cada organizacao tem a propria chave**, derivada da mestra. Um texto
   cifrado copiado de uma empresa para outra nao abre — e nem trocando o nome
   do segredo dentro da mesma empresa, porque nome e organizacao entram como
   dado autenticado da cifra.

Cifra: AES-256-GCM, nonce aleatorio por gravacao, dado autenticado
`organizacao|nome`. GCM detecta adulteracao do texto cifrado; sem isso, alterar
bytes do banco produziria um "segredo" diferente sem ninguem perceber.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import Session as Sessao

from .db.models import Base, agora, momento, novo_id
from .db.repositorio import Contexto, escopo

#: Variavel de ambiente que carrega a chave mestra, em base64 urlsafe.
VAR_CHAVE = "AUTOTAREFAS_MASTER_KEY"  # nosec B105 — nome da variavel, nao valor

#: Nome do servico no cofre do sistema operacional, quando `keyring` existe.
SERVICO_KEYRING = "autotarefas"

#: AES-256 pede 32 bytes.
TAMANHO_CHAVE = 32

#: GCM: 12 bytes e o tamanho recomendado; outro tamanho custa desempenho e
#: nao ganha seguranca.
TAMANHO_NONCE = 12


class CofreTrancado(Exception):
    """Nao ha chave mestra. Quem depende do cofre para de funcionar, e diz por que."""


class SegredoAusente(Exception):
    """O segredo pedido nao existe nesta organizacao."""


class Segredo(Base):
    """Segredo guardado cifrado. O valor em claro nunca toca esta tabela."""

    __tablename__ = "segredo"
    __table_args__ = (UniqueConstraint("organizacao_id", "nome", name="uq_segredo_org_nome"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    organizacao_id: Mapped[str] = mapped_column(
        ForeignKey("organizacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    #: `nonce || texto cifrado || etiqueta`, em base64.
    cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    #: Impressao para conferir "e a mesma chave?" sem revelar nada. E um HMAC
    #: com a chave mestra, e nao um hash do valor: hash puro de uma senha curta
    #: seria quebravel por forca bruta a partir do banco.
    impressao: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=agora, onupdate=agora
    )


# ============================================================
# Chave mestra
# ============================================================


def gerar_chave_mestra() -> str:
    """Sorteia uma chave mestra nova, pronta para colar no ambiente."""
    return base64.urlsafe_b64encode(secrets.token_bytes(TAMANHO_CHAVE)).decode("ascii")


def _do_keyring() -> str | None:
    """Le a chave do cofre do sistema, se `keyring` estiver instalado."""
    try:
        import keyring
    except ImportError:
        return None
    try:
        guardada = keyring.get_password(SERVICO_KEYRING, VAR_CHAVE)
    except Exception:  # noqa: BLE001 — backend do cofre do SO pode falhar de N jeitos
        return None
    return str(guardada) if guardada else None


def chave_mestra() -> bytes:
    """
    Chave mestra em bytes. `CofreTrancado` quando nao ha nenhuma.

    A ordem e ambiente primeiro, cofre do sistema depois: em servidor a
    variavel e o caminho normal; na maquina de quem desenvolve, o cofre do SO
    evita deixar a chave num arquivo `.env` esquecido.
    """
    bruta = os.environ.get(VAR_CHAVE, "").strip() or _do_keyring()
    if not bruta:
        msg = (
            f"cofre trancado: defina {VAR_CHAVE} com uma chave de 32 bytes em "
            "base64 (gere uma com `autotarefas cofre nova-chave`)"
        )
        raise CofreTrancado(msg)
    try:
        chave = base64.urlsafe_b64decode(bruta.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as erro:
        msg = f"{VAR_CHAVE} nao esta em base64 urlsafe"
        raise CofreTrancado(msg) from erro
    if len(chave) != TAMANHO_CHAVE:
        msg = f"{VAR_CHAVE} precisa ter {TAMANHO_CHAVE} bytes; tem {len(chave)}"
        raise CofreTrancado(msg)
    return chave


def destrancado() -> bool:
    """True quando ha chave mestra utilizavel. A tela usa isto para nao mentir."""
    try:
        chave_mestra()
    except CofreTrancado:
        return False
    return True


def _chave_da_organizacao(organizacao_id: str) -> bytes:
    """
    Chave derivada por organizacao.

    Deriva com HMAC-SHA256 da mestra. Assim, um texto cifrado que vaze de uma
    empresa nao abre com a chave de outra, e a mestra nunca e usada
    diretamente para cifrar nada.
    """
    return hmac.new(
        chave_mestra(), f"organizacao:{organizacao_id}".encode(), hashlib.sha256
    ).digest()


def _dado_autenticado(organizacao_id: str, nome: str) -> bytes:
    """Amarra o texto cifrado a organizacao e ao nome do segredo."""
    return f"{organizacao_id}|{nome}".encode()


def _impressao(valor: str) -> str:
    """Impressao curta do valor, inutil sem a chave mestra."""
    return hmac.new(chave_mestra(), valor.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


# ============================================================
# Operacoes
# ============================================================


def guardar(sessao: Sessao, contexto: Contexto, *, nome: str, valor: str) -> Segredo:
    """
    Cifra e grava o segredo. Regravar sobre o mesmo nome substitui o valor.

    Exige papel administrativo: mudar a chave de assinatura ou a senha de
    criptografia e configuracao, nao operacao.
    """
    contexto.exigir_administracao()
    if not valor:
        msg = "segredo vazio nao e segredo"
        raise ValueError(msg)

    nonce = secrets.token_bytes(TAMANHO_NONCE)
    cifra = AESGCM(_chave_da_organizacao(contexto.organizacao_id))
    corpo = cifra.encrypt(
        nonce,
        valor.encode("utf-8"),
        _dado_autenticado(contexto.organizacao_id, nome),
    )
    empacotado = base64.b64encode(nonce + corpo).decode("ascii")

    existente = sessao.execute(
        escopo(Segredo, contexto).where(Segredo.nome == nome)
    ).scalar_one_or_none()
    if existente is not None:
        existente.cifrado = empacotado
        existente.impressao = _impressao(valor)
        sessao.flush()
        return existente

    novo = Segredo(
        organizacao_id=contexto.organizacao_id,
        nome=nome,
        cifrado=empacotado,
        impressao=_impressao(valor),
    )
    sessao.add(novo)
    sessao.flush()
    return novo


def revelar(sessao: Sessao, contexto: Contexto, *, nome: str) -> str:
    """
    Decifra o segredo. So dentro do servidor — nunca numa resposta HTTP.

    Papel de operador basta: quem executa backup precisa do valor para
    assinar o manifesto, mas nao pode troca-lo.
    """
    contexto.exigir_operacao()
    registro = sessao.execute(
        escopo(Segredo, contexto).where(Segredo.nome == nome)
    ).scalar_one_or_none()
    if registro is None:
        msg = f"segredo '{nome}' nao existe nesta organizacao"
        raise SegredoAusente(msg)

    empacotado = base64.b64decode(registro.cifrado.encode("ascii"))
    nonce, corpo = empacotado[:TAMANHO_NONCE], empacotado[TAMANHO_NONCE:]
    cifra = AESGCM(_chave_da_organizacao(contexto.organizacao_id))
    aberto = cifra.decrypt(nonce, corpo, _dado_autenticado(contexto.organizacao_id, nome))
    return aberto.decode("utf-8")


def existe(sessao: Sessao, contexto: Contexto, *, nome: str) -> bool:
    """Diz se o segredo existe, sem abrir nada."""
    return (
        sessao.execute(escopo(Segredo, contexto).where(Segredo.nome == nome)).scalar_one_or_none()
        is not None
    )


def esquecer(sessao: Sessao, contexto: Contexto, *, nome: str) -> bool:
    """Apaga o segredo. Devolve se havia algo para apagar."""
    contexto.exigir_administracao()
    registro = sessao.execute(
        escopo(Segredo, contexto).where(Segredo.nome == nome)
    ).scalar_one_or_none()
    if registro is None:
        return False
    sessao.delete(registro)
    sessao.flush()
    return True


def listar(sessao: Sessao, contexto: Contexto) -> list[dict[str, str]]:
    """
    O que a tela pode ver: nome, impressao e datas. Nunca o valor.

    A impressao serve para a pessoa conferir que a chave guardada e a mesma
    que ela tem em maos, sem que o servidor precise mostra-la.
    """
    registros = sessao.execute(escopo(Segredo, contexto).order_by(Segredo.nome.asc())).scalars()
    return [
        {
            "nome": registro.nome,
            "impressao": registro.impressao,
            "criado_em": momento(registro.criado_em),
            "atualizado_em": momento(registro.atualizado_em),
        }
        for registro in registros
    ]


def conferir_impressao(sessao: Sessao, contexto: Contexto, *, nome: str, valor: str) -> bool:
    """Confere se o valor em maos e o mesmo guardado, sem revelar o guardado."""
    registro = sessao.execute(
        escopo(Segredo, contexto).where(Segredo.nome == nome)
    ).scalar_one_or_none()
    if registro is None:
        return False
    return hmac.compare_digest(registro.impressao, _impressao(valor))


__all__ = [
    "SERVICO_KEYRING",
    "VAR_CHAVE",
    "CofreTrancado",
    "Segredo",
    "SegredoAusente",
    "chave_mestra",
    "conferir_impressao",
    "destrancado",
    "esquecer",
    "existe",
    "gerar_chave_mestra",
    "guardar",
    "listar",
    "revelar",
]
