"""Retenção avô-pai-filho (02.E).

Esta é a única rotina do produto que **apaga arquivo**. Os testes cobrem menos
o caminho feliz e mais as formas de estragar:

- apagar o que não é nosso;
- esvaziar a pasta com uma configuração errada;
- confiar na data de modificação do arquivo em vez da data do nome.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from apps.agente.agente import retencao
from autotarefas.tasks.politica import Retencao


def _criar(pasta: Path, quando: datetime) -> Path:
    alvo = pasta / f"backup_{quando:%Y-%m-%d_%H%M}.zip"
    alvo.write_bytes(b"pacote")
    return alvo


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    alvo = tmp_path / "backups"
    alvo.mkdir()
    return alvo


class TestListagem:
    def test_reconhece_o_nome_que_o_produto_gera(self, pasta: Path) -> None:
        _criar(pasta, datetime(2026, 8, 25, 2, 30))

        encontrados = retencao.listar(pasta)

        assert len(encontrados) == 1
        assert encontrados[0].quando == datetime(2026, 8, 25, 2, 30)

    def test_ignora_arquivo_que_nao_e_nosso(self, pasta: Path) -> None:
        """
        Um arquivo que a pessoa guardou na mesma pasta não é problema da
        retenção — e apagá-lo seria destruir dado alheio.
        """
        _criar(pasta, datetime(2026, 8, 25, 2, 30))
        (pasta / "contrato-importante.zip").write_bytes(b"nao e nosso")
        (pasta / "backup-antigo.zip").write_bytes(b"outro formato")
        (pasta / "notas.txt").write_text("x", encoding="utf-8")

        assert len(retencao.listar(pasta)) == 1

    def test_data_vem_do_nome_e_nao_do_arquivo(self, pasta: Path) -> None:
        """
        Copiar a pasta para outro disco atualiza a data de modificação de tudo.

        Se a retenção olhasse a data do arquivo, passaria a achar que todos os
        pacotes são de hoje — e apagaria o histórico inteiro na primeira
        limpeza depois de uma migração.
        """
        antigo = _criar(pasta, datetime(2024, 1, 15, 3, 0))
        # Toca o arquivo, como uma cópia faria.
        antigo.write_bytes(b"tocado agora")

        encontrado = retencao.listar(pasta)[0]

        assert encontrado.quando.year == 2024

    def test_pasta_inexistente_devolve_vazio(self, tmp_path: Path) -> None:
        assert retencao.listar(tmp_path / "nao-existe") == []

    def test_nome_com_data_impossivel_e_ignorado(self, pasta: Path) -> None:
        (pasta / "backup_2026-02-31_0300.zip").write_bytes(b"x")

        assert retencao.listar(pasta) == []


class TestDecisao:
    def _serie_diaria(self, pasta: Path, dias: int) -> None:
        base = datetime(2026, 8, 25, 2, 0)
        for i in range(dias):
            _criar(pasta, base - timedelta(days=i))

    def test_guarda_as_diarias_pedidas(self, pasta: Path) -> None:
        self._serie_diaria(pasta, 10)

        guardar, apagar = retencao.decidir(
            retencao.listar(pasta), Retencao(diarias=3, semanais=0, mensais=0)
        )

        assert len(guardar) == 3
        assert len(apagar) == 7

    def test_cobre_um_intervalo_maior_que_so_diarias(self, pasta: Path) -> None:
        """
        O motivo de existir GFS.

        Com 90 dias de histórico, "7 diárias" alcança uma semana; 7 diárias +
        4 semanais + 3 mensais alcançam três meses, ocupando pouco mais.
        """
        base = datetime(2026, 8, 25, 2, 0)
        for i in range(90):
            _criar(pasta, base - timedelta(days=i))

        guardar, _ = retencao.decidir(
            retencao.listar(pasta), Retencao(diarias=7, semanais=4, mensais=3)
        )

        mais_antigo = min(item.quando for item in guardar)
        assert (base - mais_antigo).days > 30

    def test_um_pacote_ocupa_mais_de_uma_vaga(self, pasta: Path) -> None:
        """O de segunda costuma ser a diária do dia e a semanal da semana."""
        base = datetime(2026, 8, 25, 2, 0)
        for i in range(3):
            _criar(pasta, base - timedelta(days=i))

        guardar, apagar = retencao.decidir(
            retencao.listar(pasta), Retencao(diarias=1, semanais=1, mensais=1)
        )

        # Os tres pacotes sao do mesmo mes e da mesma semana: so o primeiro
        # ocupa as tres vagas.
        assert len(guardar) == 1
        assert len(apagar) == 2

    def test_o_mais_recente_nunca_e_apagado(self, pasta: Path) -> None:
        """
        A guarda contra a configuração errada.

        Uma rotina de limpeza que esvazia a pasta é pior do que não ter
        limpeza nenhuma.
        """
        antigo = datetime(2020, 1, 1, 2, 0)
        _criar(pasta, antigo)

        guardar, apagar = retencao.decidir(
            retencao.listar(pasta), Retencao(diarias=1, semanais=0, mensais=0)
        )

        assert len(guardar) == 1
        assert apagar == []

    def test_pasta_vazia_nao_quebra(self, pasta: Path) -> None:
        assert retencao.decidir([], Retencao()) == ([], [])


class TestAplicacao:
    def test_apaga_de_verdade_e_relata(self, pasta: Path) -> None:
        base = datetime(2026, 8, 25, 2, 0)
        for i in range(5):
            _criar(pasta, base - timedelta(days=i))

        relatorio = retencao.aplicar(pasta, Retencao(diarias=2, semanais=0, mensais=0))

        assert relatorio["guardados"] == 2
        assert len(relatorio["removidos"]) == 3
        assert len(retencao.listar(pasta)) == 2

    def test_relata_o_que_apagou_pelo_nome(self, pasta: Path) -> None:
        """
        Apagar em silêncio seria a operação mais perigosa do produto sem
        nenhum rastro.

        No dia em que faltar um pacote, ninguém saberia se ele nunca existiu
        ou se a retenção o levou.
        """
        base = datetime(2026, 8, 25, 2, 0)
        _criar(pasta, base)
        alvo = _criar(pasta, base - timedelta(days=1))

        relatorio = retencao.aplicar(pasta, Retencao(diarias=1, semanais=0, mensais=0))

        assert alvo.name in relatorio["removidos"]

    def test_arquivo_em_uso_vira_ressalva_e_nao_derruba(
        self, pasta: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Não é motivo para derrubar o backup que acabou de dar certo.

        O pacote existe; o que falhou foi a faxina.
        """
        base = datetime(2026, 8, 25, 2, 0)
        _criar(pasta, base)
        _criar(pasta, base - timedelta(days=1))

        def recusar(self: Path) -> None:
            del self
            msg = "arquivo em uso"
            raise OSError(msg)

        monkeypatch.setattr(Path, "unlink", recusar)

        relatorio = retencao.aplicar(pasta, Retencao(diarias=1, semanais=0, mensais=0))

        assert relatorio["removidos"] == []
        assert len(relatorio["nao_removidos"]) == 1

    def test_arquivo_alheio_continua_la(self, pasta: Path) -> None:
        base = datetime(2026, 8, 25, 2, 0)
        for i in range(4):
            _criar(pasta, base - timedelta(days=i))
        alheio = pasta / "planilha-da-empresa.zip"
        alheio.write_bytes(b"nao e nosso")

        retencao.aplicar(pasta, Retencao(diarias=1, semanais=0, mensais=0))

        assert alheio.is_file()


def test_semana_iso_atravessa_a_virada_do_ano() -> None:
    """
    Usar (ano, número da semana) do calendário comum quebraria no fim do ano.

    Os últimos dias de dezembro pertencem à primeira semana ISO do ano
    seguinte; com o ano civil, eles disputariam vaga com janeiro inteiro.
    """
    fim = retencao.Pacote(caminho=Path("x"), quando=datetime(2025, 12, 30, 2, 0))
    inicio = retencao.Pacote(caminho=Path("y"), quando=datetime(2026, 1, 2, 2, 0))

    assert fim.semana == inicio.semana
    assert fim.dia != inicio.dia
    assert isinstance(fim.dia, date)


class TestCorrenteIncremental:
    """
    A retencao nao apaga a base de uma corrente que ela mesma guardou (G.7.2).

    Sem isto, duas execucoes no mesmo dia terminariam assim: a regra diaria
    guarda so a mais nova, apaga a anterior — e a mais nova e incremental,
    dependendo justamente da que acabou de sumir. O pacote continuaria la,
    parecendo inteiro, e so nao restauraria o que promete.
    """

    @staticmethod
    def _duas_no_mesmo_dia(tmp_path: Path) -> tuple[Path, Path]:
        from autotarefas.tasks.backup import BackupTask
        from autotarefas.tasks.catalogo import NOME, Catalogo

        origem = tmp_path / "dados"
        origem.mkdir()
        (origem / "contrato.txt").write_text("contrato", encoding="utf-8")

        pacotes = tmp_path / "backups"
        pacotes.mkdir()
        catalogo = Catalogo(pacotes / NOME)

        base = pacotes / "backup_2026-08-25_0200.zip"
        BackupTask(sources=[origem], destination=base, catalogo=catalogo).run()

        (origem / "novo.txt").write_text("novo", encoding="utf-8")
        depois = pacotes / "backup_2026-08-25_1400.zip"
        BackupTask(sources=[origem], destination=depois, catalogo=catalogo).run()
        return base, depois

    def test_a_base_do_incremental_nao_e_apagada(self, tmp_path: Path) -> None:
        base, depois = self._duas_no_mesmo_dia(tmp_path)

        relatorio = retencao.aplicar(depois.parent, Retencao(diarias=1, semanais=0, mensais=0))

        assert base.name not in relatorio["removidos"]
        assert base.is_file(), "a retencao apagou a base da corrente incremental"
        assert depois.is_file()

    def test_pacote_completo_antigo_continua_sendo_apagado(self, tmp_path: Path) -> None:
        """
        A protecao e so para quem sustenta uma corrente.

        Sem esse limite, a retencao viraria enfeite: nada seria apagado nunca, e
        o disco encheria em silencio.
        """
        from autotarefas.tasks.backup import BackupTask

        origem = tmp_path / "dados"
        origem.mkdir()
        (origem / "contrato.txt").write_text("contrato", encoding="utf-8")

        pacotes = tmp_path / "backups"
        pacotes.mkdir()
        velho = pacotes / "backup_2026-08-24_0200.zip"
        novo = pacotes / "backup_2026-08-25_0200.zip"
        BackupTask(sources=[origem], destination=velho).run()
        BackupTask(sources=[origem], destination=novo).run()

        relatorio = retencao.aplicar(pacotes, Retencao(diarias=1, semanais=0, mensais=0))

        assert velho.name in relatorio["removidos"]
        assert not velho.is_file()
        assert novo.is_file()
