"""Primeira execucao: como nasce o primeiro administrador sem provedor externo.

Mecanismo conhecido — Jupyter, Grafana e Jenkins fazem o mesmo. Enquanto nao
existe **nenhuma** organizacao, o servidor sorteia um token, imprime a URL no
**console** e aceita uma unica criacao por ela. Depois disso o token morre e a
porta fecha sozinha: com organizacao no banco, o bootstrap deixa de existir.

Tres limites que fazem disso um mecanismo e nao um atalho:

- **uso unico** — consumido na primeira criacao bem-sucedida;
- **prazo** — vence em minutos;
- **so no console** — quem nao tem acesso ao servidor nunca ve o token.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import repositorio as repo
from ..db.models import Organizacao, Papel, agora
from .entrada import EMISSOR_BOOTSTRAP


class BootstrapIndisponivel(Exception):
    """Nao ha bootstrap a fazer, ou o token nao serve."""


@dataclass
class Convite:
    """Token de primeira execucao, com prazo e uso unico."""

    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    criado_em: float = 0.0
    usado: bool = False


_convite: Convite | None = None


def esta_vazio(sessao: Session) -> bool:
    """True quando nao existe nenhuma organizacao no banco."""
    total = sessao.execute(select(func.count()).select_from(Organizacao)).scalar_one()
    return int(total) == 0


def convite_atual() -> Convite | None:
    """Convite em vigor, se houver."""
    return _convite


def emitir(*, agora_s: float) -> Convite:
    """Sorteia um convite novo. Chamado na partida do servico."""
    global _convite
    _convite = Convite(criado_em=agora_s)
    return _convite


def descartar() -> None:
    """Esquece o convite. Usado no encerramento e entre testes."""
    global _convite
    _convite = None


def _validar(token: str, *, agora_s: float) -> Convite:
    convite = _convite
    if convite is None:
        msg = "nao ha bootstrap pendente"
        raise BootstrapIndisponivel(msg)
    if convite.usado:
        msg = "este convite ja foi usado"
        raise BootstrapIndisponivel(msg)
    if agora_s - convite.criado_em > settings.bootstrap_minutes * 60:
        msg = "este convite venceu"
        raise BootstrapIndisponivel(msg)
    # Comparacao em tempo constante: comparar com `==` deixa o tempo de
    # resposta contar quantos caracteres iniciais acertaram.
    if not secrets.compare_digest(token, convite.token):
        msg = "convite invalido"
        raise BootstrapIndisponivel(msg)
    return convite


@dataclass(frozen=True)
class PrimeiroAcesso:
    """Quem e a organizacao que acabaram de nascer."""

    usuario_id: str
    organizacao_id: str


def criar_primeira_organizacao(
    sessao: Session,
    *,
    token: str,
    nome_organizacao: str,
    email: str,
    nome: str,
    agora_s: float,
) -> PrimeiroAcesso:
    """
    Cria organizacao, dono e vinculo — uma vez so.

    A conferencia de "banco vazio" e refeita aqui, e nao so na tela: entre
    mostrar o formulario e enviar, outra pessoa pode ter criado a primeira
    organizacao, e duas donas diferentes nascendo da mesma porta seria pior do
    que um erro.
    """
    if not esta_vazio(sessao):
        msg = "ja existe organizacao: o bootstrap nao se aplica"
        raise BootstrapIndisponivel(msg)

    convite = _validar(token, agora_s=agora_s)

    dominio = repo.dominio_de(email)
    organizacao = repo.criar_organizacao(
        sessao, nome=nome_organizacao.strip() or "Minha empresa", dominio=dominio
    )
    usuario = repo.criar_usuario(
        sessao,
        email=email,
        nome=nome.strip() or email.split("@")[0],
        emissor=EMISSOR_BOOTSTRAP,
        assunto=email.strip().lower(),
    )
    repo.vincular(sessao, organizacao=organizacao, usuario=usuario, papel=Papel.DONO)

    contexto = repo.Contexto(organizacao_id=organizacao.id, usuario_id=usuario.id, papel=Papel.DONO)
    repo.registrar(
        sessao,
        contexto,
        acao="organizacao.criada",
        alvo=organizacao.nome,
        detalhe=f"primeira execucao, por {usuario.email}, em {agora().isoformat()}",
    )

    convite.usado = True
    return PrimeiroAcesso(usuario_id=usuario.id, organizacao_id=organizacao.id)


def linha_do_console(convite: Convite, base: str) -> str:
    """
    Texto impresso no console para o dono abrir.

    Vai para o console de proposito: e a unica coisa do fluxo que prova
    acesso a maquina onde o servico roda.

    So ASCII, e isso nao e economia de enfeite: o console do Windows abre em
    cp1252 por padrao, e um tracinho de caixa derruba o `print` com
    `UnicodeEncodeError` — o servico morreria na partida, na maquina do
    cliente, por causa de uma moldura.
    """
    return (
        "\n"
        "  +-- AutoTarefas - primeira execucao ---------------------------\n"
        "  |  Nenhuma organizacao cadastrada ainda.\n"
        "  |  Abra este endereco para criar a primeira, uma unica vez:\n"
        f"  |  {base.rstrip('/')}/primeiro-acesso?convite={convite.token}\n"
        f"  |  Vence em {settings.bootstrap_minutes} minutos.\n"
        "  +--------------------------------------------------------------\n"
    )


__all__ = [
    "BootstrapIndisponivel",
    "Convite",
    "PrimeiroAcesso",
    "convite_atual",
    "criar_primeira_organizacao",
    "descartar",
    "emitir",
    "esta_vazio",
    "linha_do_console",
]
