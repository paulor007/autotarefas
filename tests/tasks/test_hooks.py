"""Proteção antes de ação destrutiva, com falha fechada (02.J).

O critério de aceite do card é curto e exigente: *backup que não atinge o nível
exigido bloqueia a ação destrutiva, explicando o que não foi feito*.

O teste que dá sentido a todos os outros é o de **falha fechada**: quando não
foi possível saber se existe backup, a guarda bloqueia. Liberar "porque
provavelmente está tudo bem" transformaria a proteção numa formalidade que só
funciona quando não era necessária.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from autotarefas.tasks.backup import BackupTask
from autotarefas.tasks.catalogo import NOME, Catalogo
from autotarefas.tasks.hooks import (
    VALIDADE_PADRAO,
    AcaoDestrutiva,
    ProtecaoBloqueou,
    conferir,
    liberar_com_registro,
)

ACAO = AcaoDestrutiva.SOBRESCREVER_NA_RESTAURACAO


@pytest.fixture
def origem(tmp_path: Path) -> Path:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "contrato.txt").write_text("contrato", encoding="utf-8")
    return pasta


def _pacote(origem: Path, pasta: Path, quando: datetime, catalogo: Catalogo | None = None) -> Path:
    alvo = pasta / f"backup_{quando:%Y-%m-%d_%H%M}.zip"
    BackupTask(sources=[origem], destination=alvo, catalogo=catalogo).run()
    return alvo


class TestFalhaFechada:
    def test_pasta_inexistente_bloqueia(self, tmp_path: Path) -> None:
        """
        Não saber é bloqueio.

        É o caso em que a proteção mais importa: ninguém confirmou que existe
        backup, e a ação apagaria o trabalho de alguém.
        """
        veredito = conferir(ACAO, tmp_path / "nao-existe")

        assert veredito.liberado is False
        assert "nao existe" in veredito.motivo
        assert ACAO.value in veredito.motivo

    def test_pasta_vazia_bloqueia_e_diz_o_que_fazer(self, tmp_path: Path) -> None:
        pasta = tmp_path / "pacotes"
        pasta.mkdir()

        veredito = conferir(ACAO, pasta)

        assert veredito.liberado is False
        assert "nenhum backup encontrado" in veredito.motivo
        assert "Faca um backup antes" in veredito.motivo

    def test_arquivo_que_nao_e_pacote_nosso_nao_conta_como_protecao(self, tmp_path: Path) -> None:
        """
        Um ZIP qualquer na pasta não prova que existe backup.

        Aceitar qualquer arquivo faria a guarda liberar por causa de um
        arquivo que alguém deixou lá.
        """
        pasta = tmp_path / "pacotes"
        pasta.mkdir()
        (pasta / "copia-manual.zip").write_bytes(b"nao e nosso")

        assert conferir(ACAO, pasta).liberado is False

    def test_pasta_ilegivel_bloqueia(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Disco com defeito ou permissão negada: não deu para saber, então bloqueia.

        Simulado porque criar uma pasta ilegível de verdade depende de ACL do
        sistema — mas o caminho de código é o mesmo, e é o mais perigoso de
        liberar por engano.
        """
        pasta = tmp_path / "pacotes"
        pasta.mkdir()

        def explode(_: Path) -> list[tuple[datetime, Path]]:
            raise PermissionError("acesso negado")

        monkeypatch.setattr("autotarefas.tasks.hooks.listar_datados", explode)

        veredito = conferir(ACAO, pasta)

        assert veredito.liberado is False
        assert "nao foi possivel ler" in veredito.motivo

    def test_bloqueio_levanta_quando_exigido(self, tmp_path: Path) -> None:
        with pytest.raises(ProtecaoBloqueou, match="bloqueada"):
            conferir(ACAO, tmp_path / "nao-existe").exigir()


class TestIdade:
    def test_backup_recente_libera(self, origem: Path, tmp_path: Path) -> None:
        pasta = tmp_path / "pacotes"
        pasta.mkdir()
        agora = datetime(2026, 8, 25, 2, 0)
        _pacote(origem, pasta, agora)

        veredito = conferir(ACAO, pasta, agora=agora + timedelta(hours=3))

        assert veredito.liberado is True
        assert veredito.pacote.startswith("backup_2026-08-25")

    def test_backup_velho_bloqueia_com_os_numeros(self, origem: Path, tmp_path: Path) -> None:
        """
        A mensagem diz a idade e o limite.

        "Bloqueado" sem número não deixa ninguém decidir o que fazer.
        """
        pasta = tmp_path / "pacotes"
        pasta.mkdir()
        antigo = datetime(2026, 8, 1, 2, 0)
        _pacote(origem, pasta, antigo)

        veredito = conferir(ACAO, pasta, agora=antigo + timedelta(days=10))

        assert veredito.liberado is False
        assert "240h" in veredito.motivo
        assert f"{int(VALIDADE_PADRAO.total_seconds() // 3600)}h" in veredito.motivo

    def test_o_mais_recente_e_que_vale(self, origem: Path, tmp_path: Path) -> None:
        pasta = tmp_path / "pacotes"
        pasta.mkdir()
        agora = datetime(2026, 8, 25, 2, 0)
        _pacote(origem, pasta, agora - timedelta(days=30))
        _pacote(origem, pasta, agora)

        assert conferir(ACAO, pasta, agora=agora + timedelta(hours=1)).liberado is True


class TestConteudo:
    def test_pacote_corrompido_bloqueia(self, origem: Path, tmp_path: Path) -> None:
        """
        Backup que não confere não é proteção.

        Deixar passar seria autorizar a destruição confiando num arquivo que
        já se sabe quebrado.
        """
        import zipfile

        pasta = tmp_path / "pacotes"
        pasta.mkdir()
        agora = datetime(2026, 8, 25, 2, 0)
        alvo = _pacote(origem, pasta, agora)

        with zipfile.ZipFile(alvo) as zf:
            itens = {nome: zf.read(nome) for nome in zf.namelist()}
        itens["dados/contrato.txt"] = b"estragado"
        with zipfile.ZipFile(alvo, "w", zipfile.ZIP_DEFLATED) as zf:
            for nome, dados in itens.items():
                zf.writestr(nome, dados)

        veredito = conferir(ACAO, pasta, agora=agora + timedelta(hours=1))

        assert veredito.liberado is False
        assert "nao confere" in veredito.motivo

    def test_incremental_sem_a_corrente_bloqueia(self, origem: Path, tmp_path: Path) -> None:
        """
        Um pacote incremental sem os anteriores não restaura tudo.

        Autorizar a destruição com ele seria autorizar com uma proteção que
        não cobre o que promete.
        """
        pasta = tmp_path / "pacotes"
        pasta.mkdir()
        catalogo = Catalogo(pasta / NOME)
        agora = datetime(2026, 8, 25, 2, 0)

        primeiro = _pacote(origem, pasta, agora - timedelta(days=1), catalogo)
        (origem / "novo.txt").write_text("novo", encoding="utf-8")
        _pacote(origem, pasta, agora, catalogo)
        primeiro.unlink()

        veredito = conferir(ACAO, pasta, agora=agora + timedelta(hours=1))

        assert veredito.liberado is False
        assert "incremental" in veredito.motivo
        assert primeiro.name in veredito.motivo

    def test_incremental_com_a_corrente_completa_libera(self, origem: Path, tmp_path: Path) -> None:
        pasta = tmp_path / "pacotes"
        pasta.mkdir()
        catalogo = Catalogo(pasta / NOME)
        agora = datetime(2026, 8, 25, 2, 0)

        _pacote(origem, pasta, agora - timedelta(days=1), catalogo)
        (origem / "novo.txt").write_text("novo", encoding="utf-8")
        _pacote(origem, pasta, agora, catalogo)

        assert conferir(ACAO, pasta, agora=agora + timedelta(hours=1)).liberado is True


class TestDispensa:
    def test_dispensa_registra_o_motivo(self) -> None:
        veredito = liberar_com_registro(ACAO, "maquina nova, sem dados")

        assert veredito.liberado is True
        assert "maquina nova" in veredito.motivo
        assert "dispensada" in veredito.motivo

    def test_dispensa_sem_motivo_ainda_registra_que_houve(self) -> None:
        """
        Passar por cima sem justificar continua sendo passar por cima.

        O registro precisa existir mesmo quando ninguém escreveu o porquê.
        """
        veredito = liberar_com_registro(ACAO, "   ")

        assert veredito.liberado is True
        assert "sem motivo informado" in veredito.motivo
