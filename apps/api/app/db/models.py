"""Modelo de dados multiempresa da plataforma AutoTarefas.

Uma unica regra organiza tudo aqui: **nada existe fora de uma organizacao**.
Toda tabela que guarda dado de cliente carrega `organizacao_id`, e o acesso
passa por `repositorio.py`, que exige o contexto da organizacao para montar
qualquer consulta. Deixar o filtro a cargo de quem chama seria a mesma coisa
que nao ter isolamento: basta esquecer uma vez.

Portabilidade: SQLAlchemy 2.0 com tipos genericos. PostgreSQL em producao
(decisao H-3), SQLite em desenvolvimento e na suite. Nenhum SQL especifico de
fornecedor, para que o esquema seja o mesmo nos dois.

Identificadores sao `str` com UUID hexadecimal, nao inteiros sequenciais: um id
sequencial vaza quantos clientes existem e convida a tentar o vizinho.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def novo_id() -> str:
    """Identificador opaco de 32 hexadecimais."""
    return uuid.uuid4().hex


def agora() -> datetime:
    """Instante atual em UTC, sempre com fuso.

    Sem fuso, uma comparacao entre datas gravadas em maquinas diferentes vira
    aposta — e retencao e agendamento sao exatamente comparacao de datas.
    """
    return datetime.now(UTC)


def em_utc(valor: datetime) -> datetime:
    """
    Devolve o instante em UTC, com fuso, venha ele de onde vier.

    O SQLite nao guarda fuso: grava-se `12:00+00:00` e le-se `12:00` pelado.
    O PostgreSQL guarda. Sem esta normalizacao, a mesma data teria duas
    representacoes conforme o banco — e comparacao de data e o coracao de
    retencao, agendamento e trilha de auditoria.
    """
    if valor.tzinfo is None:
        return valor.replace(tzinfo=UTC)
    return valor.astimezone(UTC)


class Base(DeclarativeBase):
    """Base declarativa de todo o esquema."""


class Papel(enum.StrEnum):
    """O que a pessoa pode fazer dentro da organizacao."""

    DONO = "dono"
    ADMINISTRADOR = "administrador"
    OPERADOR = "operador"
    LEITOR = "leitor"


class EstadoDispositivo(enum.StrEnum):
    """Ciclo de vida de um dispositivo pareado."""

    AGUARDANDO_PAREAMENTO = "aguardando_pareamento"
    ATIVO = "ativo"
    SUSPENSO = "suspenso"
    REVOGADO = "revogado"


class ResultadoExecucao(enum.StrEnum):
    """Como uma execucao terminou.

    `COM_RESSALVA` existe porque backup que copiou quase tudo nao e sucesso
    nem falha: e um pacote util com ausencias que precisam ficar visiveis.
    """

    EM_ANDAMENTO = "em_andamento"
    SUCESSO = "sucesso"
    COM_RESSALVA = "com_ressalva"
    FALHA = "falha"
    CANCELADA = "cancelada"


class Organizacao(Base):
    """A empresa cliente. Raiz de todo isolamento."""

    __tablename__ = "organizacao"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    #: Dominio de e-mail verificado. Nulo em organizacao pessoal, criada a
    #: partir de dominio publico (gmail, hotmail): dominio publico nunca
    #: pode servir de chave para entrar na organizacao de outra pessoa.
    dominio: Mapped[str | None] = mapped_column(String(200), unique=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    # `passive_deletes` deixa o CASCADE com o banco. Sem ele o ORM tenta
    # zerar a chave estrangeira dos filhos antes de apagar o pai, o que
    # esbarra no NOT NULL — e um cliente encerrado ficaria meio apagado.
    membros: Mapped[list[Vinculo]] = relationship(
        back_populates="organizacao", cascade="all, delete-orphan", passive_deletes=True
    )
    dispositivos: Mapped[list[Dispositivo]] = relationship(
        back_populates="organizacao", cascade="all, delete-orphan", passive_deletes=True
    )


class Usuario(Base):
    """Pessoa que entra pelo Live.

    Sem coluna de senha, e de proposito: a identidade vem de um provedor OIDC
    ou do bootstrap de primeira execucao. Guardar senha de cliente e assumir
    um passivo que o produto nao precisa ter.
    """

    __tablename__ = "usuario"
    __table_args__ = (UniqueConstraint("emissor", "assunto", name="uq_usuario_oidc"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    #: `iss` do provedor OIDC. `bootstrap` quando veio da primeira execucao.
    emissor: Mapped[str] = mapped_column(String(320), nullable=False)
    #: `sub` do provedor: estavel mesmo se a pessoa mudar de e-mail.
    assunto: Mapped[str] = mapped_column(String(320), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    vinculos: Mapped[list[Vinculo]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", passive_deletes=True
    )


class Vinculo(Base):
    """Liga uma pessoa a uma organizacao, com um papel.

    Tabela propria em vez de coluna no usuario porque a mesma pessoa pode
    atender mais de uma empresa — contador, suporte de TI, socio de duas
    lojas. Sem isso, ela precisaria de um e-mail por cliente.
    """

    __tablename__ = "vinculo"
    __table_args__ = (
        UniqueConstraint("organizacao_id", "usuario_id", name="uq_vinculo_org_usuario"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    organizacao_id: Mapped[str] = mapped_column(
        ForeignKey("organizacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id: Mapped[str] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    papel: Mapped[Papel] = mapped_column(Enum(Papel), nullable=False, default=Papel.OPERADOR)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    organizacao: Mapped[Organizacao] = relationship(back_populates="membros")
    usuario: Mapped[Usuario] = relationship(back_populates="vinculos")


class Dispositivo(Base):
    """Maquina com o Agente instalado.

    A chave publica e o que identifica o dispositivo depois do pareamento:
    quem prova possuir a privada e o dispositivo. Nao ha segredo compartilhado
    que possa vazar do servidor e permitir personificacao.
    """

    __tablename__ = "dispositivo"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    organizacao_id: Mapped[str] = mapped_column(
        ForeignKey("organizacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    #: Ed25519 em base64. Unica no sistema inteiro: a mesma maquina nao pode
    #: aparecer em duas organizacoes.
    chave_publica: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    sistema: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    versao_agente: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    estado: Mapped[EstadoDispositivo] = mapped_column(
        Enum(EstadoDispositivo),
        nullable=False,
        default=EstadoDispositivo.AGUARDANDO_PAREAMENTO,
    )
    pareado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_contato: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    organizacao: Mapped[Organizacao] = relationship(back_populates="dispositivos")
    raizes: Mapped[list[RaizAutorizada]] = relationship(
        back_populates="dispositivo", cascade="all, delete-orphan", passive_deletes=True
    )


class RaizAutorizada(Base):
    """Pasta que o Agente pode ler, autorizada NA PROPRIA MAQUINA.

    O registro no servidor e o espelho de um consentimento dado localmente,
    nunca a origem dele: uma tela na nuvem nao pode conceder acesso ao disco
    de ninguem. Se a linha existir aqui sem o consentimento local, o Agente
    recusa.
    """

    __tablename__ = "raiz_autorizada"
    __table_args__ = (
        UniqueConstraint("dispositivo_id", "caminho", name="uq_raiz_dispositivo_caminho"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    organizacao_id: Mapped[str] = mapped_column(
        ForeignKey("organizacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dispositivo_id: Mapped[str] = mapped_column(
        ForeignKey("dispositivo.id", ondelete="CASCADE"), nullable=False, index=True
    )
    caminho: Mapped[str] = mapped_column(Text, nullable=False)
    rotulo: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    autorizada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    dispositivo: Mapped[Dispositivo] = relationship(back_populates="raizes")


class Politica(Base):
    """O que copiar, de onde, para onde, quando e por quanto tempo guardar."""

    __tablename__ = "politica"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    organizacao_id: Mapped[str] = mapped_column(
        ForeignKey("organizacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dispositivo_id: Mapped[str] = mapped_column(
        ForeignKey("dispositivo.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: JSON com origens, destino, agendamento, retencao, criptografia. Fica em
    #: texto porque a forma ainda vai crescer (GFS, retry, notificacao) e uma
    #: coluna por opcao viraria migracao a cada ajuste. A validacao e feita
    #: por schema Pydantic antes de gravar, entao nao e "campo livre".
    configuracao: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=agora, onupdate=agora
    )

    execucoes: Mapped[list[Execucao]] = relationship(
        back_populates="politica", passive_deletes=True
    )


class Execucao(Base):
    """Uma rodada de backup: quando comecou, como terminou, o que produziu."""

    __tablename__ = "execucao"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    organizacao_id: Mapped[str] = mapped_column(
        ForeignKey("organizacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dispositivo_id: Mapped[str | None] = mapped_column(
        ForeignKey("dispositivo.id", ondelete="SET NULL"), index=True
    )
    politica_id: Mapped[str | None] = mapped_column(
        ForeignKey("politica.id", ondelete="SET NULL"), index=True
    )
    origem: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    resultado: Mapped[ResultadoExecucao] = mapped_column(
        Enum(ResultadoExecucao), nullable=False, default=ResultadoExecucao.EM_ANDAMENTO
    )
    iniciada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    terminada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arquivos_incluidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_copiados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Texto curto do que ficou de fora ou do que falhou. Vai para a tela.
    ressalva: Mapped[str] = mapped_column(Text, nullable=False, default="")

    politica: Mapped[Politica | None] = relationship(back_populates="execucoes")
    artefatos: Mapped[list[Artefato]] = relationship(
        back_populates="execucao", cascade="all, delete-orphan", passive_deletes=True
    )


class Artefato(Base):
    """Pacote produzido por uma execucao.

    O ZIP fica **na maquina do cliente** (decisao H-4). O que o servidor
    guarda e a ficha: nome, tamanho, soma e onde esta. Sem o conteudo, um
    vazamento do servidor nao entrega dado de cliente nenhum.
    """

    __tablename__ = "artefato"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    organizacao_id: Mapped[str] = mapped_column(
        ForeignKey("organizacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    execucao_id: Mapped[str] = mapped_column(
        ForeignKey("execucao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(400), nullable=False)
    tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    #: Onde o pacote ficou, do ponto de vista do dispositivo ou do destino.
    #: Nunca um caminho do servidor do Live.
    localizacao: Mapped[str] = mapped_column(Text, nullable=False, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    execucao: Mapped[Execucao] = relationship(back_populates="artefatos")


class Auditoria(Base):
    """Trilha do que foi feito, encadeada por hash.

    Cada linha carrega o hash da anterior. Apagar ou alterar uma linha no meio
    quebra a corrente e fica detectavel — o que uma tabela comum de log nao
    oferece. Nao impede um administrador do banco de reescrever tudo do zero;
    impede a edicao silenciosa de um registro isolado.
    """

    __tablename__ = "auditoria"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=novo_id)
    organizacao_id: Mapped[str] = mapped_column(
        ForeignKey("organizacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id: Mapped[str | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    dispositivo_id: Mapped[str | None] = mapped_column(
        ForeignKey("dispositivo.id", ondelete="SET NULL")
    )
    acao: Mapped[str] = mapped_column(String(80), nullable=False)
    alvo: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    detalhe: Mapped[str] = mapped_column(Text, nullable=False, default="")
    quando: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)
    hash_anterior: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    hash_atual: Mapped[str] = mapped_column(String(64), nullable=False, default="")


__all__ = [
    "Artefato",
    "Auditoria",
    "Base",
    "Dispositivo",
    "EstadoDispositivo",
    "Execucao",
    "Organizacao",
    "Papel",
    "Politica",
    "RaizAutorizada",
    "ResultadoExecucao",
    "Usuario",
    "Vinculo",
    "agora",
    "em_utc",
    "novo_id",
]
