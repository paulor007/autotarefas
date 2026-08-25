"""Comando `autotarefas restaurar`.

A saida e o produto aqui: uma restauracao parcial que se anuncia como sucesso
e pior do que uma que falha. Os testes cobrem o codigo de saida e o texto,
porque e por eles que uma pessoa (ou um script) decide se pode confiar.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from autotarefas.cli.commands.restaurar import restaurar
from autotarefas.cli.context import CLIContext
from autotarefas.tasks.backup import BackupTask
from autotarefas.tasks.catalogo import NOME, Catalogo


def _agora_como_nome() -> str:
    """Nome de pacote com a data de agora, para a guarda aceita-lo como recente."""
    from datetime import datetime

    return f"backup_{datetime.now():%Y-%m-%d_%H%M}.zip"


def _rodar(argumentos: list[str]) -> tuple[int, str]:
    resultado = CliRunner().invoke(restaurar, argumentos, obj=CLIContext())
    return resultado.exit_code, resultado.output


def _corrido(saida: str) -> str:
    """A saida numa linha so.

    O console quebra linha na largura do terminal, e uma frase partida no
    meio faria o teste falhar por causa da largura, nao do conteudo.
    """
    return " ".join(saida.split())


@pytest.fixture
def pacote(tmp_path: Path) -> Path:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "contrato.txt").write_text("contrato", encoding="utf-8")
    (pasta / "nota.txt").write_text("nota", encoding="utf-8")
    alvo = tmp_path / "p1.zip"
    BackupTask(sources=[pasta], destination=alvo).run()
    return alvo


class TestListar:
    def test_mostra_o_conteudo_sem_escrever_nada(self, pacote: Path, tmp_path: Path) -> None:
        codigo, saida = _rodar([str(pacote), "--listar"])

        assert codigo == 0
        assert "dados/contrato.txt" in saida
        assert not (tmp_path / "recuperado").exists()


class TestRestaurar:
    def test_sem_destino_recusa_dizendo_o_que_falta(self, pacote: Path) -> None:
        codigo, saida = _rodar([str(pacote)])

        assert codigo == 2
        assert "--para" in saida

    def test_restaura_e_confere(self, pacote: Path, tmp_path: Path) -> None:
        destino = tmp_path / "recuperado"

        codigo, saida = _rodar([str(pacote), "--para", str(destino)])

        assert codigo == 0
        assert "conferem com o manifesto" in saida
        assert (destino / "dados" / "contrato.txt").read_text(encoding="utf-8") == "contrato"

    def test_preserva_e_diz_como_sobrescrever(self, pacote: Path, tmp_path: Path) -> None:
        """
        Quem le a saida precisa saber o que fazer a seguir.

        "Ja existiam" sem dizer como substituir vira chamado de suporte.
        """
        destino = tmp_path / "recuperado"
        (destino / "dados").mkdir(parents=True)
        (destino / "dados" / "contrato.txt").write_text("ATUAL", encoding="utf-8")

        _, saida = _rodar([str(pacote), "--para", str(destino)])

        assert "JA EXISTIAM" in saida
        assert "--sobrescrever" in saida

    def test_incompleta_sai_com_codigo_1(self, tmp_path: Path) -> None:
        """
        O codigo de saida distingue "faltou" de "nao deu".

        Um script de homologacao confia nisso; sair 0 numa restauracao
        incompleta faria a verificacao passar sem os arquivos.
        """
        pasta = tmp_path / "dados"
        pasta.mkdir()
        (pasta / "a.txt").write_text("a", encoding="utf-8")
        catalogo = Catalogo(tmp_path / "pacotes" / NOME)
        BackupTask(
            sources=[pasta], destination=tmp_path / "pacotes" / "p1.zip", catalogo=catalogo
        ).run()
        (pasta / "b.txt").write_text("b", encoding="utf-8")
        BackupTask(
            sources=[pasta], destination=tmp_path / "pacotes" / "p2.zip", catalogo=catalogo
        ).run()

        codigo, saida = _rodar(
            [str(tmp_path / "pacotes" / "p2.zip"), "--para", str(tmp_path / "rec")]
        )

        assert codigo == 1
        assert "INCOMPLETA" in saida
        assert "p1.zip" in saida

    def test_pacote_que_nao_confere_sai_com_codigo_2(self, pacote: Path, tmp_path: Path) -> None:
        import zipfile

        with zipfile.ZipFile(pacote) as zf:
            itens = {nome: zf.read(nome) for nome in zf.namelist()}
        itens["dados/contrato.txt"] = b"estragado"
        with zipfile.ZipFile(pacote, "w", zipfile.ZIP_DEFLATED) as zf:
            for nome, dados in itens.items():
                zf.writestr(nome, dados)

        codigo, saida = _rodar([str(pacote), "--para", str(tmp_path / "rec")])

        assert codigo == 2
        assert "nao confere" in saida


class TestProtecao:
    """A guarda de acao destrutiva, vista da linha de comando (02.J)."""

    def test_sobrescrever_sem_protecao_e_bloqueado_e_nao_toca_no_arquivo(
        self, pacote: Path, tmp_path: Path
    ) -> None:
        """
        Falha fechada tambem aqui.

        Passar `--sobrescrever` sem apresentar backup do destino nao substitui
        nada: o arquivo atual continua exatamente como estava.
        """
        destino = tmp_path / "recuperado"
        (destino / "dados").mkdir(parents=True)
        atual = destino / "dados" / "contrato.txt"
        atual.write_text("ATUAL", encoding="utf-8")

        codigo, saida = _rodar([str(pacote), "--para", str(destino), "--sobrescrever"])

        assert codigo == 2
        assert "Nada foi alterado" in _corrido(saida)
        assert "--protecao" in _corrido(saida)
        assert atual.read_text(encoding="utf-8") == "ATUAL"

    def test_com_backup_recente_do_destino_sobrescreve(self, pacote: Path, tmp_path: Path) -> None:
        destino = tmp_path / "recuperado"
        (destino / "dados").mkdir(parents=True)
        atual = destino / "dados" / "contrato.txt"
        atual.write_text("ATUAL", encoding="utf-8")

        pacotes = tmp_path / "backups-do-destino"
        pacotes.mkdir()
        BackupTask(sources=[destino], destination=pacotes / _agora_como_nome()).run()

        codigo, saida = _rodar(
            [str(pacote), "--para", str(destino), "--sobrescrever", "--protecao", str(pacotes)]
        )

        assert codigo == 0
        assert "Protecao: backup" in _corrido(saida)
        assert atual.read_text(encoding="utf-8") == "contrato"

    def test_dispensa_explicita_libera_e_aparece_na_saida(
        self, pacote: Path, tmp_path: Path
    ) -> None:
        """
        A saida existe, e fica registrada.

        Uma protecao sem saida as pessoas desligam de vez; uma saida sem
        registro ninguem sabe se estava ligada.
        """
        destino = tmp_path / "recuperado"
        (destino / "dados").mkdir(parents=True)
        (destino / "dados" / "contrato.txt").write_text("ATUAL", encoding="utf-8")

        codigo, saida = _rodar(
            [
                str(pacote),
                "--para",
                str(destino),
                "--sobrescrever",
                "--dispensar-protecao",
                "maquina nova, sem dados",
            ]
        )

        assert codigo == 0
        assert "protecao dispensada" in _corrido(saida)
        assert "maquina nova, sem dados" in _corrido(saida)

    def test_protecao_com_backup_velho_bloqueia(self, pacote: Path, tmp_path: Path) -> None:
        destino = tmp_path / "recuperado"
        (destino / "dados").mkdir(parents=True)
        atual = destino / "dados" / "contrato.txt"
        atual.write_text("ATUAL", encoding="utf-8")

        pacotes = tmp_path / "backups-do-destino"
        pacotes.mkdir()
        BackupTask(sources=[destino], destination=pacotes / "backup_2020-01-01_0300.zip").run()

        codigo, saida = _rodar(
            [str(pacote), "--para", str(destino), "--sobrescrever", "--protecao", str(pacotes)]
        )

        assert codigo == 2
        assert "e o limite e 26h" in _corrido(saida)
        assert atual.read_text(encoding="utf-8") == "ATUAL"
