"""Como o dono volta a entrar num servidor sem provedor de identidade.

O primeiro acesso resolve o comeco: banco vazio, convite no console, organizacao
criada. Depois disso a porta fecha — e, num servidor **sem OIDC configurado**,
ela fecha para sempre. A sessao vence em algumas horas, e a pessoa fica trancada
do lado de fora do proprio servidor, com os dados dela dentro.

Isso nao e caso raro: e o estado normal de quem acabou de subir o Live para
experimentar. Foi exatamente o que aconteceu na primeira homologacao manual.

O mecanismo aqui e o mesmo do primeiro acesso, e a razao e a mesma: **quem tem
acesso ao console da maquina onde o servico roda ja controla o servico**. Um
link impresso ali nao concede nada que essa pessoa nao pudesse tomar de outro
jeito. O que ele evita e o unico desfecho pior que todos: um produto que perde o
dono dos dados.

Tres limites, iguais aos do bootstrap:

- **uso unico** — consumido na primeira entrada;
- **prazo** — vence em minutos;
- **so no console** — quem nao tem acesso a maquina nunca ve o token.

E um limite a mais, que o bootstrap nao precisa ter:

- **so quando NAO ha provedor configurado**. Com OIDC no ar, o caminho e o
  provedor, e nada e impresso. Manter os dois abertos seria manter uma porta que
  ninguem vigia ao lado de uma porta com fechadura.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db.models import Papel, Usuario, Vinculo


class ReentradaIndisponivel(Exception):
    """Nao ha reentrada a fazer, ou o token nao serve."""


@dataclass
class Chave:
    """Token de reentrada, com prazo e uso unico."""

    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    usuario_id: str = ""
    organizacao_id: str = ""
    email: str = ""
    criado_em: float = 0.0
    usada: bool = False


_chave: Chave | None = None


def ha_provedor() -> bool:
    """Este servidor tem um provedor de identidade configurado?"""
    return bool(settings.oidc_issuer and settings.oidc_client_id)


def chave_atual() -> Chave | None:
    return _chave


def descartar() -> None:
    """Esquece a chave. Usado no encerramento e entre testes."""
    global _chave
    _chave = None


def _dono(sessao: Session) -> Vinculo | None:
    """
    O vinculo de dono mais antigo do servidor.

    O mais antigo, e nao "algum": num servidor com varias organizacoes, quem
    criou a primeira e quem tem o console na mao. Sortear entre donos daria a
    chave a quem por acaso aparecesse primeiro numa consulta sem ordem.
    """
    return (
        sessao.execute(
            select(Vinculo)
            .where(Vinculo.papel == Papel.DONO)
            .order_by(Vinculo.criado_em.asc(), Vinculo.id.asc())
        )
        .scalars()
        .first()
    )


def emitir(sessao: Session, *, agora_s: float) -> Chave | None:
    """
    Sorteia uma chave de reentrada para o dono, se ela fizer falta.

    Devolve `None` quando **nao** deve existir: com provedor configurado (o
    caminho e ele) ou sem nenhum dono cadastrado (nao ha para quem emitir — e o
    caso do banco vazio, que e do bootstrap).
    """
    global _chave

    if ha_provedor():
        return None

    vinculo = _dono(sessao)
    if vinculo is None:
        return None

    usuario = sessao.get(Usuario, vinculo.usuario_id)
    if usuario is None:  # pragma: no cover - vinculo sem usuario e inconsistencia
        return None

    _chave = Chave(
        usuario_id=usuario.id,
        organizacao_id=vinculo.organizacao_id,
        email=usuario.email,
        criado_em=agora_s,
    )
    return _chave


def usar(token: str, *, agora_s: float) -> Chave:
    """
    Consome a chave e devolve para quem ela vale.

    Comparacao em tempo constante: comparar com `==` deixa o tempo de resposta
    contar quantos caracteres bateram, e um token de 32 bytes vira adivinhavel
    caractere a caractere.
    """
    chave = _chave
    if chave is None:
        msg = "nao ha link de acesso em vigor"
        raise ReentradaIndisponivel(msg)
    if chave.usada:
        msg = "este link ja foi usado"
        raise ReentradaIndisponivel(msg)
    if agora_s - chave.criado_em > settings.bootstrap_minutes * 60:
        msg = "este link venceu"
        raise ReentradaIndisponivel(msg)
    if not secrets.compare_digest(token, chave.token):
        msg = "link invalido"
        raise ReentradaIndisponivel(msg)

    chave.usada = True
    return chave


def _nota_do_endereco() -> str:
    """
    Diz que o host do link foi suposto, quando foi.

    O `--port` do uvicorn nao chega ate a aplicacao: quem sobe em outra porta
    recebe um link com a porta errada, e o unico jeito de descobrir e seguir o
    link e bater numa porta fechada. Entao o console admite o palpite em vez de
    apresenta-lo como endereco.

    Com `PUBLIC_BASE_URL` definido nao ha palpite, e a nota some.
    """
    if not settings.base_url_suposta:
        return ""
    return (
        "  |\n"
        "  |  O endereco acima foi SUPOSTO a partir de PORT. Se o seu Live\n"
        "  |  esta em outra porta, troque a porta no link (a chave vale do\n"
        "  |  mesmo jeito), ou defina PUBLIC_BASE_URL antes de subir.\n"
    )


def linha_do_console(chave: Chave, base: str) -> str:
    """
    Texto impresso no console para o dono voltar a entrar.

    So ASCII: o console do Windows abre em cp1252, e um tracinho de caixa
    derruba o `print` com `UnicodeEncodeError` — o servico morreria na partida,
    na maquina do cliente, por causa de uma moldura.
    """
    return (
        "\n"
        "  +-- AutoTarefas - entrar sem provedor de identidade ------------\n"
        "  |  Este servidor nao tem OIDC configurado, entao este link e o\n"
        "  |  unico jeito de entrar. Ele vale uma vez so.\n"
        f"  |  {base.rstrip('/')}/api/auth/reentrar?chave={chave.token}\n"
        f"  |  Dono: {chave.email}\n"
        f"  |  Vence em {settings.bootstrap_minutes} minutos.\n"
        + _nota_do_endereco()
        + "  +--------------------------------------------------------------\n"
    )


__all__ = [
    "Chave",
    "ReentradaIndisponivel",
    "chave_atual",
    "descartar",
    "emitir",
    "ha_provedor",
    "linha_do_console",
    "usar",
]
