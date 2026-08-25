"""Acesso ao banco com isolamento entre organizacoes embutido.

O isolamento nao pode depender de quem escreve a consulta lembrar de filtrar.
Aqui ele e estrutural: toda leitura de dado de cliente passa por `escopo()`,
que exige um `Contexto` e ja aplica `organizacao_id == contexto.organizacao_id`.
Uma consulta sem contexto nao compila — nao ha assinatura que aceite.

`Contexto` so nasce em `abrir_contexto()`, que confere o vinculo da pessoa com
a organizacao. Quem nao e membro nao consegue construir o objeto, entao nao
consegue consultar nada.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from .models import (
    Auditoria,
    Dispositivo,
    Organizacao,
    Papel,
    Usuario,
    Vinculo,
    agora,
    em_utc,
)

#: Dominios de e-mail publicos: nunca servem de chave para entrar numa
#: organizacao existente. Sem esta lista, qualquer pessoa com um gmail entraria
#: na "organizacao gmail.com" de todo mundo.
DOMINIOS_PUBLICOS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "hotmail.com",
        "hotmail.com.br",
        "outlook.com",
        "outlook.com.br",
        "live.com",
        "yahoo.com",
        "yahoo.com.br",
        "icloud.com",
        "bol.com.br",
        "uol.com.br",
        "terra.com.br",
        "proton.me",
        "protonmail.com",
    }
)

#: Papeis que podem mudar configuracao (parear, autorizar pasta, criar politica).
PAPEIS_ADMINISTRATIVOS = frozenset({Papel.DONO, Papel.ADMINISTRADOR})

#: Papeis que podem disparar execucao.
PAPEIS_OPERACIONAIS = frozenset({Papel.DONO, Papel.ADMINISTRADOR, Papel.OPERADOR})


class SemAcesso(Exception):
    """A pessoa nao tem vinculo com a organizacao, ou nao tem o papel exigido."""


@dataclass(frozen=True)
class Contexto:
    """
    Quem esta pedindo, e por qual organizacao.

    Congelado de proposito: um contexto que pudesse ser alterado depois de
    criado permitiria trocar a organizacao no meio de uma operacao, que e
    exatamente o furo que este modulo existe para fechar.
    """

    organizacao_id: str
    usuario_id: str | None
    papel: Papel

    @property
    def administra(self) -> bool:
        return self.papel in PAPEIS_ADMINISTRATIVOS

    @property
    def opera(self) -> bool:
        return self.papel in PAPEIS_OPERACIONAIS

    def exigir_administracao(self) -> None:
        """Barra quem so pode olhar de mexer na configuracao."""
        if not self.administra:
            msg = f"papel {self.papel.value} nao pode administrar esta organizacao"
            raise SemAcesso(msg)

    def exigir_operacao(self) -> None:
        """Barra quem so pode olhar de disparar execucao."""
        if not self.opera:
            msg = f"papel {self.papel.value} nao pode operar esta organizacao"
            raise SemAcesso(msg)


def escopo[T](modelo: type[T], contexto: Contexto) -> Select[tuple[T]]:
    """
    Consulta de um modelo, ja restrita a organizacao do contexto.

    Todo acesso a dado de cliente comeca aqui. `modelo.organizacao_id` e
    obrigatorio: se alguem criar uma tabela sem essa coluna e tentar usa-la
    com escopo, o erro aparece na hora, e nao depois de vazar.
    """
    coluna = getattr(modelo, "organizacao_id", None)
    if coluna is None:
        msg = f"{modelo.__name__} nao tem organizacao_id: nao pode ter escopo"
        raise TypeError(msg)
    return select(modelo).where(coluna == contexto.organizacao_id)


def abrir_contexto(sessao: Session, *, usuario_id: str, organizacao_id: str) -> Contexto:
    """
    Constroi o contexto conferindo o vinculo. Sem vinculo, `SemAcesso`.

    E o unico caminho para obter um `Contexto` de pessoa. O bootstrap e o
    Agente tem os seus, adiante, com origem propria e igualmente conferida.
    """
    vinculo = sessao.execute(
        select(Vinculo).where(
            Vinculo.usuario_id == usuario_id,
            Vinculo.organizacao_id == organizacao_id,
        )
    ).scalar_one_or_none()
    if vinculo is None:
        msg = "usuario sem vinculo com esta organizacao"
        raise SemAcesso(msg)
    return Contexto(organizacao_id=organizacao_id, usuario_id=usuario_id, papel=vinculo.papel)


def contexto_de_dispositivo(sessao: Session, *, dispositivo_id: str) -> Contexto:
    """
    Contexto de um dispositivo que se autenticou pela chave.

    O dispositivo age em nome da organizacao dele, com papel de operador: pode
    executar e reportar, nao pode mudar configuracao. Assim, uma chave privada
    roubada nao permite autorizar pasta nova nem trocar destino.
    """
    dispositivo = sessao.get(Dispositivo, dispositivo_id)
    if dispositivo is None:
        msg = "dispositivo desconhecido"
        raise SemAcesso(msg)
    return Contexto(
        organizacao_id=dispositivo.organizacao_id, usuario_id=None, papel=Papel.OPERADOR
    )


def dominio_de(email: str) -> str | None:
    """Dominio do e-mail, ou `None` se for publico ou malformado."""
    _, _, dominio = email.partition("@")
    dominio = dominio.strip().lower()
    if not dominio or dominio in DOMINIOS_PUBLICOS:
        return None
    return dominio


def criar_organizacao(sessao: Session, *, nome: str, dominio: str | None = None) -> Organizacao:
    """Cria a organizacao. `dominio` nulo = organizacao pessoal."""
    organizacao = Organizacao(nome=nome, dominio=dominio)
    sessao.add(organizacao)
    sessao.flush()
    return organizacao


def criar_usuario(sessao: Session, *, email: str, nome: str, emissor: str, assunto: str) -> Usuario:
    """Cria a pessoa. Sem senha: a identidade vem de fora."""
    usuario = Usuario(email=email.strip().lower(), nome=nome, emissor=emissor, assunto=assunto)
    sessao.add(usuario)
    sessao.flush()
    return usuario


def vincular(
    sessao: Session, *, organizacao: Organizacao, usuario: Usuario, papel: Papel
) -> Vinculo:
    """Liga a pessoa a organizacao com um papel."""
    vinculo = Vinculo(organizacao_id=organizacao.id, usuario_id=usuario.id, papel=papel)
    sessao.add(vinculo)
    sessao.flush()
    return vinculo


def organizacao_por_dominio(sessao: Session, dominio: str | None) -> Organizacao | None:
    """
    Acha a organizacao dona de um dominio verificado.

    Dominio publico devolve `None` sempre — e a diferenca entre "entrar na
    empresa em que trabalho" e "entrar na conta de um estranho".
    """
    if not dominio or dominio in DOMINIOS_PUBLICOS:
        return None
    return sessao.execute(
        select(Organizacao).where(Organizacao.dominio == dominio)
    ).scalar_one_or_none()


# ============================================================
# Trilha de auditoria encadeada
# ============================================================


def _instante(valor: datetime) -> str:
    """
    Instante em texto, num formato que sobrevive a ida e volta ao banco.

    `isoformat()` nao serve: o SQLite devolve a data sem fuso, entao o mesmo
    registro daria hashes diferentes ao ser gravado e ao ser conferido — a
    trilha acusaria adulteracao em toda linha, e um alarme que sempre toca e
    igual a alarme nenhum.
    """
    return em_utc(valor).strftime("%Y-%m-%dT%H:%M:%S.%f")


def _digerir(anterior: str, campos: dict[str, str]) -> str:
    """
    Hash de uma linha da trilha, amarrado ao hash da anterior.

    `sort_keys` e `ensure_ascii=False` deixam a serializacao deterministica:
    sem isso, a mesma linha daria hashes diferentes em execucoes diferentes e
    a conferencia acusaria adulteracao onde nao houve.
    """
    corpo = json.dumps(campos, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(f"{anterior}|{corpo}".encode()).hexdigest()


def _ultimo_hash(sessao: Session, organizacao_id: str) -> str:
    """Hash da ultima linha da organizacao. Corrente por organizacao."""
    linha = sessao.execute(
        select(Auditoria.hash_atual)
        .where(Auditoria.organizacao_id == organizacao_id)
        .order_by(Auditoria.quando.desc(), Auditoria.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    return linha or ""


def registrar(  # noqa: PLR0913 — cada campo e uma coluna da trilha; juntar
    # dois deles numa estrutura so tornaria a chamada mais dificil de ler
    # nos dezenas de pontos que registram acao.
    sessao: Session,
    contexto: Contexto,
    *,
    acao: str,
    alvo: str = "",
    detalhe: str = "",
    dispositivo_id: str | None = None,
) -> Auditoria:
    """
    Grava uma linha na trilha, encadeada a anterior da mesma organizacao.

    Toda acao que muda estado passa por aqui. A corrente nao impede um
    administrador do banco de reescrever a trilha inteira; impede a edicao
    silenciosa de um registro isolado, que e o caso realista.
    """
    anterior = _ultimo_hash(sessao, contexto.organizacao_id)
    quando = agora()
    linha = Auditoria(
        organizacao_id=contexto.organizacao_id,
        usuario_id=contexto.usuario_id,
        dispositivo_id=dispositivo_id,
        acao=acao,
        alvo=alvo,
        detalhe=detalhe,
        quando=quando,
        hash_anterior=anterior,
    )
    linha.hash_atual = _digerir(
        anterior,
        {
            "organizacao": contexto.organizacao_id,
            "usuario": contexto.usuario_id or "",
            "dispositivo": dispositivo_id or "",
            "acao": acao,
            "alvo": alvo,
            "detalhe": detalhe,
            "quando": _instante(quando),
        },
    )
    sessao.add(linha)
    sessao.flush()
    return linha


def conferir_trilha(sessao: Session, contexto: Contexto) -> tuple[bool, str]:
    """
    Reconfere a corrente inteira da organizacao.

    Devolve `(integra, explicacao)`. A explicacao aponta a primeira linha que
    nao bate — sem ela, saber que "algo foi mexido" nao ajudaria ninguem.
    """
    linhas = list(
        sessao.execute(
            escopo(Auditoria, contexto).order_by(Auditoria.quando.asc(), Auditoria.id.asc())
        ).scalars()
    )
    anterior = ""
    for linha in linhas:
        if linha.hash_anterior != anterior:
            return False, f"linha {linha.id} nao aponta para a anterior"
        esperado = _digerir(
            anterior,
            {
                "organizacao": linha.organizacao_id,
                "usuario": linha.usuario_id or "",
                "dispositivo": linha.dispositivo_id or "",
                "acao": linha.acao,
                "alvo": linha.alvo,
                "detalhe": linha.detalhe,
                "quando": _instante(linha.quando),
            },
        )
        if esperado != linha.hash_atual:
            return False, f"linha {linha.id} foi alterada depois de gravada"
        anterior = linha.hash_atual
    return True, f"{len(linhas)} registro(s) conferem"


__all__ = [
    "DOMINIOS_PUBLICOS",
    "Contexto",
    "SemAcesso",
    "abrir_contexto",
    "conferir_trilha",
    "contexto_de_dispositivo",
    "criar_organizacao",
    "criar_usuario",
    "dominio_de",
    "escopo",
    "organizacao_por_dominio",
    "registrar",
    "vincular",
]
