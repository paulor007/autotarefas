"""Instantaneo de volume (02.D).

O criterio de aceite do card tem duas metades. Esta suite cobre a segunda por
inteiro e a primeira ate onde uma sessao sem elevacao alcanca:

- **sem elevacao, recusa clara e nenhum instantaneo orfao** — testado aqui,
  inclusive o caminho em que o backup FALHA no meio e a limpeza tem que
  acontecer assim mesmo;
- **com elevacao, arquivo aberto no Excel entra no backup** — precisa de um
  processo administrador. Os testes existem, marcados para rodar so quando ha
  elevacao, e ficam registrados como verificacao manual pendente enquanto nao
  houver.

A recusa e o comportamento mais importante do modulo. Quem pediu instantaneo
pediu porque tem arquivo aberto; devolver um pacote sem ele "com sucesso" seria
pior do que devolver o motivo.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest

from apps.agente.agente import backup as backup_agente
from apps.agente.agente import raizes, vss
from apps.agente.agente.comandos import Contexto
from apps.agente.agente.config import Configuracao, Local

no_windows = pytest.mark.skipif(os.name != "nt", reason="VSS e do Windows")
com_elevacao = pytest.mark.skipif(
    not vss.elevado(), reason="criar instantaneo exige processo administrador"
)


def _contexto(configuracao: Configuracao) -> Contexto:
    async def relatar(_dados: dict[str, Any]) -> None:
        return None

    return Contexto(configuracao=configuracao, relatar=relatar)


@pytest.fixture
def autorizada(tmp_path: Path) -> tuple[Configuracao, Path]:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "planilha.xlsx").write_text("conteudo importante", encoding="utf-8")
    configuracao = raizes.autorizar(Local(pasta=tmp_path / "cfg"), pasta)
    return configuracao, pasta


class TestDisponibilidade:
    def test_sem_elevacao_o_motivo_diz_o_que_fazer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        "Acesso negado" nao ajuda ninguem.

        A frase precisa dizer o que muda a situacao: instalar o Agente como
        servico do sistema.
        """
        monkeypatch.setattr(vss, "elevado", lambda: False)
        monkeypatch.setattr(vss, "no_windows", lambda: True)

        motivo = vss.motivo_de_indisponibilidade()

        assert "administrador" in motivo
        assert "servico do sistema" in motivo
        assert vss.disponivel() is False

    def test_fora_do_windows_diz_isso(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(vss, "no_windows", lambda: False)

        assert "so existe no Windows" in vss.motivo_de_indisponibilidade()

    def test_criar_sem_elevacao_nao_chega_a_chamar_o_windows(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Conferir antes evita um erro de WMI ilegivel.

        E evita, principalmente, deixar meio instantaneo criado num caminho
        de erro que ninguem previu.
        """
        monkeypatch.setattr(vss, "elevado", lambda: False)
        monkeypatch.setattr(vss, "no_windows", lambda: True)

        def nao_deveria(_script: str) -> str:
            msg = "o PowerShell nao pode ser chamado sem elevacao"
            raise AssertionError(msg)

        monkeypatch.setattr(vss, "_powershell", nao_deveria)

        with pytest.raises(vss.VSSIndisponivel, match="administrador"):
            vss.criar("C:\\")


class TestVolume:
    @no_windows
    def test_volume_vem_com_barra(self, tmp_path: Path) -> None:
        """
        Sem a barra final o WMI recusa com erro generico.

        Custa tempo de depuracao a cada vez que alguem esquece.
        """
        volume = vss.volume_de(tmp_path)

        assert volume.endswith(":\\")
        assert len(volume) == 3

    def test_volume_invalido_e_recusado(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(vss, "elevado", lambda: True)
        monkeypatch.setattr(vss, "no_windows", lambda: True)

        with pytest.raises(vss.VSSIndisponivel, match="volume invalido"):
            vss.criar("nao-e-volume")


class TestMapeamento:
    def test_mapeia_para_dentro_da_foto(self, tmp_path: Path) -> None:
        """
        `C:\\dados\\x` tem que virar `<ponto>\\dados\\x`.

        Errar aqui produz um backup vazio sem erro nenhum — o pior desfecho
        possivel, porque parece sucesso.
        """
        ponto = tmp_path / "ponto"
        foto = vss.Instantaneo(
            identificador="{1}",
            volume=str(Path(tmp_path.anchor)),
            dispositivo=r"\\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy1",
            ponto=ponto,
        )

        alvo = tmp_path / "dados" / "nota.xlsx"
        mapeado = foto.mapear(alvo)

        assert ponto in mapeado.parents
        assert mapeado.name == "nota.xlsx"

    def test_sem_ponto_de_acesso_recusa(self, tmp_path: Path) -> None:
        foto = vss.Instantaneo(
            identificador="{1}",
            volume=str(Path(tmp_path.anchor)),
            dispositivo=r"\\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy1",
        )

        with pytest.raises(vss.VSSIndisponivel, match="sem ponto de acesso"):
            foto.mapear(tmp_path / "x")


class TestLimpeza:
    def test_apagar_sem_identificador_nao_faz_nada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def nao_deveria(_script: str) -> str:
            msg = "nao ha instantaneo para apagar"
            raise AssertionError(msg)

        monkeypatch.setattr(vss, "_powershell", nao_deveria)

        vss.apagar(vss.Instantaneo(identificador="", volume="C:\\", dispositivo=""))

    def test_falha_ao_apagar_nao_esconde_o_erro_original(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Limpeza que levanta apaga a causa real do problema.

        Quem esta depurando um backup que falhou nao pode receber, no lugar,
        um erro de remocao de instantaneo.
        """

        def falhar(_script: str) -> str:
            msg = "o Windows recusou"
            raise vss.VSSIndisponivel(msg)

        monkeypatch.setattr(vss, "_powershell", falhar)

        vss.apagar(vss.Instantaneo(identificador="{1}", volume="C:\\", dispositivo="x"))

    def test_instantaneo_e_apagado_mesmo_quando_o_backup_falha(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """
        O `finally` que impede lixo caro no disco do cliente.

        Instantaneo orfao consome espaco ate alguem notar — e ninguem nota,
        porque ele nao aparece em lugar nenhum do dia a dia.
        """
        criados: list[str] = []
        apagados: list[str] = []

        def criar_falso(volume: str) -> vss.Instantaneo:
            criados.append(volume)
            return vss.Instantaneo(
                identificador="{teste}",
                volume=volume,
                dispositivo=r"\\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy9",
            )

        def apagar_falso(foto: vss.Instantaneo) -> None:
            apagados.append(foto.identificador)

        def ligar_falso(_foto: vss.Instantaneo) -> Path:
            ponto = tmp_path / "ponto"
            ponto.mkdir()
            return ponto

        monkeypatch.setattr(vss, "criar", criar_falso)
        monkeypatch.setattr(vss, "apagar", apagar_falso)
        monkeypatch.setattr(vss, "_ligar_ponto", ligar_falso)
        monkeypatch.setattr(vss, "_desligar_ponto", lambda _p: None)

        def explodir_no_meio() -> None:
            with vss.instantaneo_de("C:\\"):
                msg = "o backup explodiu"
                raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="o backup explodiu"):
            explodir_no_meio()

        assert criados == ["C:\\"]
        assert apagados == ["{teste}"]


class TestPedidoDeBackupComInstantaneo:
    def test_sem_elevacao_o_backup_recusa_em_vez_de_cair_para_o_modo_antigo(
        self, autorizada: tuple[Configuracao, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A regra que evita a mentira mais facil deste modulo.

        Cair em silencio para o modo sem instantaneo produziria um pacote SEM
        a planilha aberta, marcado como sucesso. Quem pediu instantaneo pediu
        justamente por causa dela.
        """
        configuracao, _ = autorizada
        monkeypatch.setattr(vss, "elevado", lambda: False)
        monkeypatch.setattr(vss, "no_windows", lambda: True)

        with pytest.raises(backup_agente.BackupRecusado, match="administrador"):
            asyncio.run(backup_agente.executar_backup({"usar_vss": True}, _contexto(configuracao)))

    def test_sem_instantaneo_a_ficha_diz_que_nao_usou(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        """
        O relatorio nao pode deixar duvida sobre como o pacote foi feito.

        `instantaneo: false` e o que distingue "a planilha nao estava aberta"
        de "a planilha ficou de fora".
        """
        configuracao, _ = autorizada

        ficha = asyncio.run(
            backup_agente.executar_backup(
                {"destino": str(tmp_path / "p.zip")}, _contexto(configuracao)
            )
        )

        assert ficha["instantaneo"] is False

    def test_pastas_em_discos_diferentes_sao_recusadas(
        self, autorizada: tuple[Configuracao, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Uma foto cobre um volume.

        Varias fotos ao mesmo tempo dariam instantes diferentes, e o pacote
        pareceria consistente sem ser — que e pior do que recusar.
        """
        _configuracao, pasta = autorizada
        monkeypatch.setattr(vss, "elevado", lambda: True)
        monkeypatch.setattr(vss, "no_windows", lambda: True)

        volumes = iter(["C:\\", "D:\\"])
        monkeypatch.setattr(vss, "volume_de", lambda _c: next(volumes))

        pedido = backup_agente.Pedido(
            origens=(pasta, pasta / "outra"), destino=pasta.parent / "p.zip"
        )

        with pytest.raises(backup_agente.BackupRecusado, match="discos diferentes"):
            backup_agente.executar_com_instantaneo(pedido)


@no_windows
@com_elevacao
class TestComElevacao:
    """
    A metade do criterio de aceite que exige processo administrador.

    Roda de verdade quando ha elevacao; caso contrario e pulada e fica
    registrada como verificacao manual pendente na documentacao do card.
    """

    def test_cria_e_apaga_um_instantaneo_de_verdade(self, tmp_path: Path) -> None:
        volume = vss.volume_de(tmp_path)

        with vss.instantaneo_de(volume) as foto:
            assert foto.identificador
            assert foto.ponto is not None
            assert foto.ponto.exists()
            identificador = foto.identificador

        # Depois do bloco, o instantaneo nao pode mais existir.
        listagem = vss._powershell(
            "Get-WmiObject Win32_ShadowCopy | Select-Object -ExpandProperty ID"
        )
        assert identificador not in listagem

    def test_arquivo_aberto_no_excel_entra_no_backup(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        """O problema numero um de um escritorio: a planilha esta aberta."""
        import msvcrt

        configuracao, pasta = autorizada
        travado = pasta / "planilha.xlsx"

        with travado.open("r+b") as alvo:
            msvcrt.locking(alvo.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                ficha = asyncio.run(
                    backup_agente.executar_backup(
                        {"destino": str(tmp_path / "p.zip"), "usar_vss": True},
                        _contexto(configuracao),
                    )
                )
            finally:
                alvo.seek(0)
                msvcrt.locking(alvo.fileno(), msvcrt.LK_UNLCK, 1)

        assert ficha["instantaneo"] is True
        assert ficha["com_ressalva"] is False
        assert ficha["arquivos"] >= 1
