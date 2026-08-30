"""Destinos reais do pacote (G.5.3).

O teste que carrega o peso e `test_copia_estragada_no_destino_e_descartada`.
Rede que cai no meio e cabo USB ruim produzem arquivos com o tamanho certo e o
conteudo errado — e um backup assim so mostra o problema no dia da
restauracao. A conferencia acontece **no destino**, depois da copia.

O segundo em importancia e a recusa de destino "externo" que aponta para o
disco de origem: a pessoa pediu protecao contra o disco morrer, e o que
receberia nao protege contra nada.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from apps.agente.agente import backup as backup_agente
from apps.agente.agente import destinos, raizes
from apps.agente.agente.comandos import Contexto
from apps.agente.agente.config import Configuracao, Local


def _contexto(configuracao: Configuracao) -> Contexto:
    async def relatar(_dados: dict[str, Any]) -> None:
        return None

    return Contexto(configuracao=configuracao, relatar=relatar)


@pytest.fixture
def autorizada(tmp_path: Path) -> tuple[Configuracao, Path]:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "contrato.txt").write_text("contrato importante", encoding="utf-8")
    configuracao = raizes.autorizar(Local(pasta=tmp_path / "cfg"), pasta)
    return configuracao, pasta


@pytest.fixture
def pacote(tmp_path: Path, autorizada: tuple[Configuracao, Path]) -> Path:
    """Um pacote de verdade, gerado pelo Agente."""
    configuracao, _ = autorizada
    alvo = tmp_path / "origem" / "pacote.zip"
    asyncio.run(backup_agente.executar_backup({"destino": str(alvo)}, _contexto(configuracao)))
    return alvo


class TestPreparacao:
    def test_cria_a_pasta_de_destino(self, tmp_path: Path) -> None:
        alvo = tmp_path / "backups" / "2026"

        destino = destinos.preparar(alvo)

        assert alvo.is_dir()
        assert destino.caminho == alvo.resolve()

    def test_destino_impossivel_e_recusado_com_motivo(self, tmp_path: Path) -> None:
        """
        Falhar aqui e barato; falhar depois de meia hora de copia nao e.
        """
        arquivo = tmp_path / "isto-e-um-arquivo"
        arquivo.write_text("x", encoding="utf-8")

        with pytest.raises(destinos.DestinoRecusado, match="nao foi possivel usar"):
            destinos.preparar(arquivo / "dentro-de-um-arquivo")

    def test_tipo_declarado_diferente_do_real_e_recusado(self, tmp_path: Path) -> None:
        """
        A pessoa escolheu "disco externo" e apontou para uma pasta local.

        Aceitar em silencio entregaria a sensacao de protecao externa sem a
        protecao.
        """
        with pytest.raises(destinos.DestinoRecusado, match=r"mas .+ e "):
            destinos.preparar(tmp_path / "backups", tipo_declarado=destinos.TipoDeDestino.EXTERNO)

    def test_externo_no_mesmo_disco_da_origem_e_recusado(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Pediu protecao contra o disco morrer; receberia nada.

        Aqui e recusa, e nao aviso: o aviso serve quando a pessoa escolheu o
        caminho sabendo; a recusa serve quando ela pediu explicitamente um
        destino externo.
        """
        origem = tmp_path / "dados"
        origem.mkdir()
        alvo = tmp_path / "backups"
        monkeypatch.setattr(destinos, "tipo_do_caminho", lambda _c: destinos.TipoDeDestino.EXTERNO)

        with pytest.raises(destinos.DestinoRecusado, match="MESMO disco"):
            destinos.preparar(
                alvo, tipo_declarado=destinos.TipoDeDestino.EXTERNO, origens=(origem,)
            )

    def test_local_no_mesmo_disco_e_permitido(self, tmp_path: Path) -> None:
        """
        Quem escolheu "pasta local" sabe que e o mesmo disco.

        Recusar seria impedir o caso legitimo de guardar uma copia a mao
        enquanto o disco externo nao chega.
        """
        origem = tmp_path / "dados"
        origem.mkdir()

        destino = destinos.preparar(
            tmp_path / "backups",
            tipo_declarado=destinos.TipoDeDestino.LOCAL,
            origens=(origem,),
        )

        assert destino.tipo is destinos.TipoDeDestino.LOCAL

    def test_caminho_de_rede_e_reconhecido_pelo_formato(self) -> None:
        assert destinos.tipo_do_caminho(Path(r"\\servidor\backups")) is destinos.TipoDeDestino.REDE


class TestEntrega:
    def test_copia_e_confere_no_destino(self, pacote: Path, tmp_path: Path) -> None:
        destino = destinos.preparar(tmp_path / "externo")

        recibo = destinos.entregar(pacote, destino)

        assert recibo["conferido_no_destino"] is True
        assert (destino.caminho / pacote.name).is_file()
        assert recibo["arquivo"] == pacote.name

    def test_copia_estragada_no_destino_e_descartada(self, pacote: Path, tmp_path: Path) -> None:
        """
        O teste que justifica conferir DEPOIS de copiar.

        Rede que cai e cabo USB ruim produzem arquivo com tamanho certo e
        conteudo errado. Sem esta conferencia, o cliente descobriria no dia da
        restauracao — que e o unico dia em que descobrir nao adianta.
        """
        destino = destinos.preparar(tmp_path / "externo")

        # Corrompe um byte do conteudo. E o que um cabo com defeito faz: o
        # arquivo tem o tamanho certo, e o conteudo nao bate com o manifesto.
        bruto = bytearray(pacote.read_bytes())
        alvo_byte = bruto.rfind(b"contrato")
        assert alvo_byte > 0
        bruto[alvo_byte] ^= 0xFF
        pacote.write_bytes(bytes(bruto))

        with pytest.raises(destinos.DestinoRecusado, match="nao confere la"):
            destinos.entregar(pacote, destino)

        assert not (destino.caminho / pacote.name).exists()

    def test_sem_espaco_recusa_antes_de_copiar(
        self, pacote: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Disco que enche por completo costuma corromper o sistema de arquivos.

        Melhor recusar com numeros do que preencher o ultimo byte livre.
        """
        destino = destinos.preparar(tmp_path / "externo")
        monkeypatch.setattr(destinos, "espaco_livre", lambda _c: 1024)

        with pytest.raises(destinos.DestinoRecusado, match="espaco insuficiente"):
            destinos.entregar(pacote, destino)

        assert not (destino.caminho / pacote.name).exists()

    def test_nao_deixa_arquivo_parcial_com_o_nome_final(self, pacote: Path, tmp_path: Path) -> None:
        """
        Um arquivo pela metade com o nome certo parece um backup completo.

        Mesmo motivo do `.parcial` do pacote original.
        """
        destino = destinos.preparar(tmp_path / "externo")
        destinos.entregar(pacote, destino)

        parciais = list(destino.caminho.glob("*.parcial"))
        assert parciais == []

    def test_pacote_inexistente_e_recusado(self, tmp_path: Path) -> None:
        destino = destinos.preparar(tmp_path / "externo")

        with pytest.raises(destinos.DestinoRecusado, match="nao existe"):
            destinos.entregar(tmp_path / "nunca-existiu.zip", destino)


class TestBackupComDestino:
    def test_pacote_chega_ao_destino_e_a_ficha_registra(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        configuracao, _ = autorizada
        externo = tmp_path / "externo"

        ficha = asyncio.run(
            backup_agente.executar_backup(
                {
                    "destino": str(tmp_path / "origem" / "p.zip"),
                    "destino_externo": str(externo),
                },
                _contexto(configuracao),
            )
        )

        assert ficha["entrega"] is not None
        assert ficha["entrega"]["conferido_no_destino"] is True
        assert (externo / "p.zip").is_file()

    def test_sem_destino_externo_a_ficha_diz_que_nao_houve_entrega(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        """
        `entrega: null` e informacao, nao ausencia de informacao.

        E o que distingue "o pacote esta so nesta maquina" de "o pacote foi
        para o disco externo".
        """
        configuracao, _ = autorizada

        ficha = asyncio.run(
            backup_agente.executar_backup(
                {"destino": str(tmp_path / "p.zip")}, _contexto(configuracao)
            )
        )

        assert ficha["entrega"] is None

    def test_a_ficha_nunca_carrega_o_caminho_local(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        """O caminho interno some antes de a ficha subir ao servidor."""
        configuracao, _ = autorizada

        ficha = asyncio.run(
            backup_agente.executar_backup(
                {
                    "destino": str(tmp_path / "origem" / "p.zip"),
                    "destino_externo": str(tmp_path / "externo"),
                },
                _contexto(configuracao),
            )
        )

        assert "_caminho_local" not in ficha
        assert str(tmp_path / "origem") not in str(ficha)

    def test_destino_invalido_recusa_antes_de_copiar_arquivo(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        """
        A conferencia do destino vem antes de ler o primeiro arquivo.

        Ler gigabytes para descobrir no fim que o destino nao serve seria
        gastar o tempo do cliente para nada.
        """
        configuracao, _ = autorizada
        arquivo = tmp_path / "nao-e-pasta"
        arquivo.write_text("x", encoding="utf-8")
        alvo = tmp_path / "origem" / "p.zip"

        with pytest.raises(backup_agente.BackupRecusado):
            asyncio.run(
                backup_agente.executar_backup(
                    {
                        "destino": str(alvo),
                        "destino_externo": str(arquivo / "dentro"),
                    },
                    _contexto(configuracao),
                )
            )

        assert not alvo.exists()


class TestOCaminhoLocalNaoSobe:
    """
    O desenho inteiro toma o cuidado de nao mandar caminho local ao servidor —
    o pacote sobe como NOME, nunca como caminho, e ate a mensagem de erro do
    `artefatos` evita dizer onde procurou.

    A ficha da entrega furava isso em silencio: ela ia para o historico com
    o caminho completo dentro, e a tela do Live exibia. Um mapa da
    estrutura de pastas da empresa, entregue de graca a quem olhasse a tela.
    """

    def test_a_ficha_da_entrega_nao_carrega_o_caminho(self, pacote: Path, tmp_path: Path) -> None:
        alvo = tmp_path / "clientes-contratos-2019"
        destino = destinos.preparar(alvo)

        ficha = destinos.entregar(pacote, destino)

        assert "clientes-contratos-2019" not in str(ficha)
        assert str(alvo) not in str(ficha)
        # Continua dizendo QUE TIPO de lugar e: essa parte e informacao util e
        # nao entrega nada.
        assert ficha["destino"] == "pasta local"

    def test_a_descricao_longa_continua_existindo_para_a_maquina(self, tmp_path: Path) -> None:
        """
        Quem le o log do Agente esta NO computador em que a pasta existe.

        Tirar o caminho de la tambem seria pior: a pessoa perderia a unica
        forma de saber para onde a copia foi.
        """
        destino = destinos.preparar(tmp_path / "backups")

        assert str(tmp_path) in destino.descricao
        assert destino.rotulo in destino.descricao
