"""Catálogo do backup incremental: o que já está copiado, e em qual pacote.

Backup completo todo dia é simples e caro. Numa pasta de 40 GB que muda 200 MB
por dia, ele gasta 40 GB de disco e horas de janela — e o cliente acaba
reduzindo a frequência, que é exatamente o contrário do que se quer.

O incremental **em nível de arquivo** resolve o caso real de um escritório: o
que muda são alguns arquivos inteiros, não pedaços deles. O catálogo guarda,
para cada arquivo já copiado, o tamanho, a data, o SHA-256 e **em qual pacote
ele está** — e é esse último campo que torna a restauração possível.

O que este módulo **não** faz, e não pode ser dito que faz: deduplicação, delta
em nível de bloco, ou compressão diferencial. Um arquivo que muda um byte é
copiado inteiro de novo.

Duas decisões que valem o custo:

1. **Data diferente não basta para recopiar.** Muitos programas reescrevem o
   arquivo sem mudar o conteúdo (o Excel faz isso ao abrir e fechar). Quando a
   data muda e o tamanho é o mesmo, o hash é calculado e comparado — ler o
   arquivo é mais barato do que copiá-lo e guardá-lo para sempre.
2. **SQLite, e não JSON.** Uma pasta de escritório tem centenas de milhares de
   arquivos; reler e reescrever um JSON inteiro a cada backup ficaria mais caro
   que o próprio backup.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

#: Nome do arquivo de catálogo, ao lado dos pacotes.
NOME = "catalogo.sqlite"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS arquivo (
    arcname TEXT PRIMARY KEY,
    tamanho INTEGER NOT NULL,
    modificado_em REAL NOT NULL,
    sha256 TEXT NOT NULL,
    pacote TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pacote (
    nome TEXT PRIMARY KEY,
    criado_em TEXT NOT NULL
);
"""

#: Tolerância na comparação de data. É só a margem de arredondamento de ponto
#: flutuante — não uma janela de conveniência.
#:
#: A ideia de usar dois segundos (a granularidade do FAT) foi tentada e
#: descartada por ser insegura: um arquivo alterado UM segundo depois de o
#: backup registrá-lo entraria na janela e seria considerado inalterado. A
#: alteração se perderia em silêncio, que é o pior defeito possível num
#: backup. Aqui, qualquer data diferente manda calcular o hash — ler o arquivo
#: é muito mais barato do que perder a versão dele.
FOLGA_SEGUNDOS = 1e-6


class Situacao(StrEnum):
    """O que fazer com um arquivo nesta execução."""

    NOVO = "novo"
    """Nunca foi copiado."""

    ALTERADO = "alterado"
    """Existe no catálogo, mas o conteúdo mudou."""

    INALTERADO = "inalterado"
    """Já está num pacote anterior, idêntico. Não entra neste."""


@dataclass(frozen=True)
class Anterior:
    """O que o catálogo sabe sobre um arquivo."""

    tamanho: int
    modificado_em: float
    sha256: str
    pacote: str


@dataclass(frozen=True)
class Decisao:
    """O veredito para um arquivo, e o hash quando ele foi calculado."""

    situacao: Situacao
    sha256: str = ""

    @property
    def entra_no_pacote(self) -> bool:
        return self.situacao is not Situacao.INALTERADO


class Catalogo:
    """
    O que já foi copiado, guardado ao lado dos pacotes.

    Fica junto dos pacotes de propósito: catálogo e pacotes são a mesma coisa
    do ponto de vista de quem restaura. Guardá-lo em outro lugar criaria a
    situação em que se tem os pacotes e não se sabe mais o que está em qual.
    """

    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conectar()) as conexao:
            conexao.executescript(_ESQUEMA)
            conexao.commit()

    def _conectar(self) -> sqlite3.Connection:
        return sqlite3.connect(self.caminho)

    # --------------------------------------------------------
    # Leitura
    # --------------------------------------------------------

    def anterior(self, arcname: str) -> Anterior | None:
        with closing(self._conectar()) as conexao:
            linha = conexao.execute(
                "SELECT tamanho, modificado_em, sha256, pacote FROM arquivo WHERE arcname = ?",
                (arcname,),
            ).fetchone()
        if linha is None:
            return None
        return Anterior(
            tamanho=int(linha[0]),
            modificado_em=float(linha[1]),
            sha256=str(linha[2]),
            pacote=str(linha[3]),
        )

    def quantos(self) -> int:
        with closing(self._conectar()) as conexao:
            return int(conexao.execute("SELECT COUNT(*) FROM arquivo").fetchone()[0])

    def pacotes(self) -> list[str]:
        """Pacotes que o catálogo referencia, do mais novo para o mais velho."""
        with closing(self._conectar()) as conexao:
            linhas = conexao.execute("SELECT nome FROM pacote ORDER BY criado_em DESC").fetchall()
        return [str(linha[0]) for linha in linhas]

    # --------------------------------------------------------
    # Escrita
    # --------------------------------------------------------

    def registrar(
        self,
        arcname: str,
        *,
        tamanho: int,
        modificado_em: float,
        sha256: str,
        pacote: str,
    ) -> None:
        """Anota que este arquivo, com este conteúdo, está naquele pacote."""
        with closing(self._conectar()) as conexao:
            conexao.execute(
                "INSERT INTO arquivo (arcname, tamanho, modificado_em, sha256, pacote) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(arcname) DO UPDATE SET "
                "tamanho=excluded.tamanho, modificado_em=excluded.modificado_em, "
                "sha256=excluded.sha256, pacote=excluded.pacote",
                (arcname, tamanho, modificado_em, sha256, pacote),
            )
            conexao.commit()

    def registrar_pacote(self, nome: str, criado_em: str) -> None:
        with closing(self._conectar()) as conexao:
            conexao.execute(
                "INSERT INTO pacote (nome, criado_em) VALUES (?, ?) "
                "ON CONFLICT(nome) DO UPDATE SET criado_em=excluded.criado_em",
                (nome, criado_em),
            )
            conexao.commit()

    def esquecer_pacotes(self, nomes: list[str]) -> int:
        """
        Esquece pacotes que não existem mais (a retenção os apagou).

        Todo arquivo que morava neles volta a ser **novo**: sem isso, o
        catálogo apontaria para um pacote que a retenção levou, e a
        restauração encontraria uma referência quebrada — que é pior do que
        copiar de novo.
        """
        if not nomes:
            return 0
        marcadores = ",".join("?" for _ in nomes)
        with closing(self._conectar()) as conexao:
            # A interpolação monta só a lista de `?`; os nomes vão como
            # parâmetros. É a única forma de escrever `IN` com quantidade
            # variável no sqlite3, e nenhum valor entra no texto do comando.
            cursor = conexao.execute(
                f"DELETE FROM arquivo WHERE pacote IN ({marcadores})",  # noqa: S608  # nosec B608
                nomes,
            )
            conexao.execute(
                f"DELETE FROM pacote WHERE nome IN ({marcadores})",  # noqa: S608  # nosec B608
                nomes,
            )
            conexao.commit()
            return int(cursor.rowcount)

    def sincronizar_com(self, pacotes_existentes: set[str]) -> int:
        """
        Descarta do catálogo o que aponta para pacote que sumiu.

        Chamado depois da retenção. É o que mantém catálogo e pasta contando a
        mesma história.
        """
        sumiram = [nome for nome in self.pacotes() if nome not in pacotes_existentes]
        return self.esquecer_pacotes(sumiram)


def decidir(
    anterior: Anterior | None,
    *,
    tamanho: int,
    modificado_em: float,
    calcular_sha: object,
) -> Decisao:
    """
    Este arquivo precisa entrar no pacote de hoje?

    `calcular_sha` é chamado **só quando necessário** — quando a data mudou e o
    tamanho continua igual. Nesse caso, ler o arquivo é mais barato do que
    copiá-lo e guardá-lo para sempre; nos outros, nem ler é preciso.
    """
    if anterior is None:
        return Decisao(situacao=Situacao.NOVO)

    if tamanho != anterior.tamanho:
        # Tamanho diferente é conteúdo diferente. Não há hash que mude isso, e
        # calcular um aqui seria só gastar leitura.
        return Decisao(situacao=Situacao.ALTERADO)

    if abs(modificado_em - anterior.modificado_em) <= FOLGA_SEGUNDOS:
        # Mesma data e mesmo tamanho: o caminho rápido, e o mais comum numa
        # pasta de escritório. Nem ler o arquivo é preciso.
        return Decisao(situacao=Situacao.INALTERADO, sha256=anterior.sha256)

    # Data mudou, tamanho igual: pode ser reescrita sem alteração de conteúdo,
    # que é comum (o Excel faz isso ao abrir e fechar). O hash decide.
    sha = str(calcular_sha())  # type: ignore[operator]
    if sha == anterior.sha256:
        return Decisao(situacao=Situacao.INALTERADO, sha256=sha)
    return Decisao(situacao=Situacao.ALTERADO, sha256=sha)


__all__ = [
    "FOLGA_SEGUNDOS",
    "NOME",
    "Anterior",
    "Catalogo",
    "Decisao",
    "Situacao",
    "decidir",
]
