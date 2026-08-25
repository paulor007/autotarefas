"""Do que o provedor afirma ate a pessoa dentro de uma organizacao.

Duas decisoes moram aqui, e as duas sao de seguranca:

1. **Quando duas identidades sao a mesma pessoa.** A chave e o par
   `(emissor, assunto)`, nao o e-mail: e-mail muda de dono, `sub` nao.
2. **Em qual organizacao a pessoa cai.** Dominio corporativo ja registrado por
   um administrador leva a organizacao dele, como operador. Dominio publico ou
   desconhecido cria organizacao propria, com a pessoa como dona.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import repositorio as repo
from ..db.models import Organizacao, Papel, Usuario
from .oidc import ErroDeIdentidade, Identidade

#: Emissor gravado para quem entrou pelo bootstrap de primeira execucao.
EMISSOR_BOOTSTRAP = "bootstrap"


@dataclass(frozen=True)
class Acolhida:
    """Resultado de acolher uma identidade."""

    usuario_id: str
    organizacao_id: str
    organizacao_nova: bool
    papel: Papel


def _por_provedor(sessao: Session, identidade: Identidade) -> Usuario | None:
    return sessao.execute(
        select(Usuario).where(
            Usuario.emissor == identidade.emissor,
            Usuario.assunto == identidade.assunto,
        )
    ).scalar_one_or_none()


def _por_email(sessao: Session, email: str) -> Usuario | None:
    return sessao.execute(select(Usuario).where(Usuario.email == email)).scalar_one_or_none()


def _resolver_usuario(sessao: Session, identidade: Identidade) -> Usuario:
    """
    Acha ou cria a pessoa, sem abrir porta para tomada de conta.

    O caminho perigoso e o segundo: casar por e-mail. So e feito quando o
    provedor afirma que o e-mail foi verificado E a conta existente ainda vem
    do bootstrap — que e o caso legitimo de "o dono criou a conta na primeira
    execucao e depois ligou o provedor". Um provedor que nao verifica e-mail
    poderia, sem essa regra, entregar a conta de qualquer pessoa a quem
    digitasse o endereco dela.
    """
    existente = _por_provedor(sessao, identidade)
    if existente is not None:
        return existente

    homonimo = _por_email(sessao, identidade.email)
    if homonimo is not None:
        if not identidade.email_verificado or homonimo.emissor != EMISSOR_BOOTSTRAP:
            msg = "ja existe conta com este e-mail vinda de outra origem"
            raise ErroDeIdentidade(msg)
        homonimo.emissor = identidade.emissor
        homonimo.assunto = identidade.assunto
        sessao.flush()
        return homonimo

    return repo.criar_usuario(
        sessao,
        email=identidade.email,
        nome=identidade.nome,
        emissor=identidade.emissor,
        assunto=identidade.assunto,
    )


def _nome_de_organizacao(email: str, dominio: str | None) -> str:
    if dominio:
        return dominio.split(".")[0].replace("-", " ").title()
    local = email.split("@")[0]
    return f"Espaço de {local}"


def acolher(sessao: Session, identidade: Identidade) -> Acolhida:
    """
    Coloca a pessoa dentro de uma organizacao e devolve onde ela caiu.

    Quem chega por dominio ja registrado entra como **operador**, nunca como
    administrador: caso contrario, bastaria um e-mail do dominio para ganhar
    poder de mudar destino e revogar dispositivo.
    """
    usuario = _resolver_usuario(sessao, identidade)

    vinculo_existente = usuario.vinculos[0] if usuario.vinculos else None
    if vinculo_existente is not None:
        return Acolhida(
            usuario_id=usuario.id,
            organizacao_id=vinculo_existente.organizacao_id,
            organizacao_nova=False,
            papel=vinculo_existente.papel,
        )

    dominio = repo.dominio_de(identidade.email)
    organizacao = repo.organizacao_por_dominio(sessao, dominio)
    if organizacao is not None:
        papel = Papel.OPERADOR
        nova = False
    else:
        organizacao = repo.criar_organizacao(
            sessao, nome=_nome_de_organizacao(identidade.email, dominio), dominio=dominio
        )
        papel = Papel.DONO
        nova = True

    repo.vincular(sessao, organizacao=organizacao, usuario=usuario, papel=papel)
    contexto = repo.Contexto(organizacao_id=organizacao.id, usuario_id=usuario.id, papel=papel)
    repo.registrar(
        sessao,
        contexto,
        acao="organizacao.criada" if nova else "usuario.entrou",
        alvo=organizacao.nome,
        detalhe=f"{identidade.email} como {papel.value}",
    )
    return Acolhida(
        usuario_id=usuario.id,
        organizacao_id=organizacao.id,
        organizacao_nova=nova,
        papel=papel,
    )


def organizacoes_do_usuario(sessao: Session, usuario_id: str) -> list[Organizacao]:
    """Organizacoes em que a pessoa tem vinculo. Contador atende varias."""
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        return []
    return [vinculo.organizacao for vinculo in usuario.vinculos]


__all__ = ["EMISSOR_BOOTSTRAP", "Acolhida", "acolher", "organizacoes_do_usuario"]
