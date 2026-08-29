"""A porta da demonstração pública.

O AutoTarefas nasceu como produto de empresa: quem entra prova quem é, por um
provedor de identidade ou pelo link do console. Isso continua valendo para uma
instalação de cliente.

Publicado num portfólio, o público é outro. Quem chega é alguém avaliando o
trabalho — um recrutador, uma empresa, um curioso. Essa pessoa não tem conta,
não vai abrir terminal e não deveria instalar nada no computador dela só para
entender o que o sistema faz. Ela clica em "Acessar projeto" e precisa estar
dentro.

Então existe um segundo jeito de entrar, e três regras o mantêm honesto:

**1. Só quando alguém liga.** `DEMONSTRACAO_PUBLICA` não tem valor padrão
verdadeiro. Uma instalação de cliente nunca ganha esta porta por descuido de
quem implanta.

**2. Só numa organização, e ela é escolhida a dedo.** `DEMONSTRACAO_ORG` nomeia
qual. Sem esse nome, a porta não abre — cair na "primeira organização que
aparecer" seria a receita para publicar o dado de um cliente por acidente.

**3. Sempre somente leitura.** A sessão emitida aqui carrega a marca que o
middleware confere antes de qualquer rota. Ver tudo, mudar nada.

O que o visitante encontra do outro lado não é simulação: é o mesmo banco, o
mesmo agendador e o mesmo Agente, num ambiente que pertence ao projeto e roda
de verdade.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import repositorio as repo
from ..db.models import Organizacao, Papel, Usuario, Vinculo

#: E-mail do visitante. Não é uma pessoa: é o papel "quem está olhando".
EMAIL_DO_VISITANTE = "visitante@demonstracao.autotarefas"

NOME_DO_VISITANTE = "Visitante"


class DemonstracaoIndisponivel(Exception):
    """Não há demonstração pública a servir, e a mensagem diz por quê."""


@dataclass(frozen=True)
class Entrada:
    """Para quem emitir a sessão de visitante."""

    usuario_id: str
    organizacao_id: str
    organizacao: str


def ligada() -> bool:
    """A demonstração pública está ligada e apontada para uma organização?"""
    return bool(settings.demonstracao_publica and settings.demonstracao_org.strip())


def _organizacao(sessao: Session) -> Organizacao:
    nome = settings.demonstracao_org.strip()
    achada = sessao.execute(
        select(Organizacao).where(Organizacao.nome == nome)
    ).scalar_one_or_none()
    if achada is None:
        msg = f"a organizacao de demonstracao '{nome}' nao existe neste servidor"
        raise DemonstracaoIndisponivel(msg)
    return achada


def _visitante(sessao: Session, organizacao: Organizacao) -> Usuario:
    """
    O usuário do visitante, criado uma vez e reaproveitado sempre.

    Um usuário por visita encheria o banco de linhas que ninguém vai ler, e
    faria a trilha de auditoria contar mil pessoas onde há uma função.
    """
    achado = sessao.execute(
        select(Usuario).where(Usuario.email == EMAIL_DO_VISITANTE)
    ).scalar_one_or_none()
    if achado is None:
        achado = repo.criar_usuario(
            sessao,
            email=EMAIL_DO_VISITANTE,
            nome=NOME_DO_VISITANTE,
            emissor="demonstracao",
            assunto=EMAIL_DO_VISITANTE,
        )

    tem_vinculo = sessao.execute(
        select(Vinculo).where(
            Vinculo.usuario_id == achado.id,
            Vinculo.organizacao_id == organizacao.id,
        )
    ).scalar_one_or_none()
    if tem_vinculo is None:
        # `LEITOR` alem da marca de somente leitura, e nao no lugar dela. Duas
        # travas independentes: se um dia alguem afrouxar o middleware, o papel
        # ainda recusa; se alguem promover o papel por engano, o middleware
        # ainda recusa.
        repo.vincular(sessao, organizacao=organizacao, usuario=achado, papel=Papel.LEITOR)
    return achado


def abrir(sessao: Session) -> Entrada:
    """
    Prepara a entrada do visitante, criando o que faltar.

    Idempotente de propósito: é chamada a cada visita, e uma instalação
    publicada recebe visitas em paralelo.
    """
    if not ligada():
        msg = "este servidor nao publica demonstracao"
        raise DemonstracaoIndisponivel(msg)

    organizacao = _organizacao(sessao)
    usuario = _visitante(sessao, organizacao)
    return Entrada(
        usuario_id=usuario.id,
        organizacao_id=organizacao.id,
        organizacao=organizacao.nome,
    )


__all__ = [
    "EMAIL_DO_VISITANTE",
    "NOME_DO_VISITANTE",
    "DemonstracaoIndisponivel",
    "Entrada",
    "abrir",
    "ligada",
]
