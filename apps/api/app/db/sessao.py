"""Conexao com o banco: motor, sessao e criacao do esquema.

`DATABASE_URL` decide onde os dados moram. PostgreSQL em producao (decisao
H-3), SQLite em desenvolvimento e na suite. Nenhum SQL especifico de fornecedor
e escrito em lugar nenhum, entao o esquema e o mesmo nos dois.

Esquema criado por `create_all`. E suficiente enquanto o formato ainda muda a
cada subetapa; quando estabilizar, entra migracao versionada. Isso esta
registrado como limitacao, nao como decisao definitiva.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

#: Banco padrao: arquivo ao lado dos dados do servico. Nunca em memoria por
#: default — um banco que some ao reiniciar esconderia perda de dado no
#: desenvolvimento e so apareceria em producao.
_PADRAO = "sqlite:///./autotarefas.db"


def url_do_banco() -> str:
    """Endereco do banco, de `DATABASE_URL` ou o padrao local."""
    return os.environ.get("DATABASE_URL", "").strip() or _PADRAO


def _e_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def criar_motor(url: str | None = None) -> Engine:
    """
    Cria o motor com os ajustes que cada banco exige.

    No SQLite, duas coisas nao sao opcionais:

    - `check_same_thread=False`, porque o servidor atende em varias threads;
    - `PRAGMA foreign_keys=ON`, porque o SQLite ignora chave estrangeira por
      padrao. Sem isso, `ondelete="CASCADE"` seria decoracao e apagar uma
      organizacao deixaria dispositivo e execucao orfaos — dado de cliente
      sobrevivendo ao cliente.
    """
    endereco = url or url_do_banco()
    argumentos: dict[str, object] = {}
    if _e_sqlite(endereco):
        argumentos["connect_args"] = {"check_same_thread": False}

    motor = create_engine(endereco, future=True, **argumentos)

    if _e_sqlite(endereco):

        @event.listens_for(motor, "connect")
        def _liga_chaves_estrangeiras(conexao: object, _registro: object) -> None:
            cursor = conexao.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return motor


class Banco:
    """
    Motor + fabrica de sessoes, com criacao de esquema sob demanda.

    E uma classe, e nao um par de variaveis de modulo, para que a suite possa
    montar um banco proprio por teste sem tocar em estado global. Estado
    global de banco em teste e a receita para um teste enxergar o dado do
    outro — e para o isolamento entre organizacoes parecer funcionar quando
    nao funciona.
    """

    def __init__(self, url: str | None = None) -> None:
        self.url = url or url_do_banco()
        self.motor = criar_motor(self.url)
        self._fabrica = sessionmaker(bind=self.motor, expire_on_commit=False, future=True)

    def criar_esquema(self) -> None:
        """Cria as tabelas que ainda nao existem."""
        if _e_sqlite(self.url) and ":memory:" not in self.url:
            destino = self.url.removeprefix("sqlite:///")
            pai = Path(destino).resolve().parent
            pai.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(self.motor)

    def apagar_esquema(self) -> None:
        """Remove as tabelas. Existe para a suite, nao para producao."""
        Base.metadata.drop_all(self.motor)

    @contextmanager
    def sessao(self) -> Iterator[Session]:
        """
        Sessao com commit no fim e rollback em qualquer erro.

        O rollback e o ponto: sem ele, uma falha no meio de uma operacao com
        varias escritas deixaria metade gravada — um dispositivo pareado sem
        a trilha de auditoria correspondente, por exemplo.
        """
        sessao = self._fabrica()
        try:
            yield sessao
            sessao.commit()
        except Exception:
            sessao.rollback()
            raise
        finally:
            sessao.close()

    def descartar(self) -> None:
        """Fecha o pool. Usado no encerramento do servico e entre testes."""
        self.motor.dispose()


__all__ = ["Banco", "criar_motor", "url_do_banco"]
