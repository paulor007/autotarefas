"""Backup executado pelo Agente (G.5.2).

Dois testes carregam o peso desta subetapa:

- `test_arquivo_grande_nao_carrega_tudo_na_memoria` — o limite de 10 MB e do
  envio pelo navegador e nao pode virar limite do produto. Aqui um arquivo de
  mais de 10 MB e copiado enquanto o pico de alocacao e MEDIDO, e nao
  prometido;
- `test_origem_fora_das_pastas_autorizadas_e_recusada` — o servidor pode pedir
  qualquer caminho; o que ele nao pode e obter um que ninguem autorizou nesta
  maquina.
"""

from __future__ import annotations

import asyncio
import os
import tracemalloc
import zipfile
from pathlib import Path
from typing import Any

import pytest

from apps.agente.agente import backup as backup_agente
from apps.agente.agente import raizes
from apps.agente.agente.comandos import Contexto
from apps.agente.agente.config import Configuracao, Local

#: Tamanho do arquivo grande do teste: acima do limite de 10 MB do navegador.
TAMANHO_GRANDE = 12 * 1024 * 1024

#: Teto de alocacao aceitavel durante o backup do arquivo grande. Com
#: streaming, o pico fica na casa dos poucos MB (buffers de leitura e de
#: compressao). Sem streaming, passaria dos 12 MB do proprio arquivo.
TETO_MEMORIA = 6 * 1024 * 1024


def _contexto(configuracao: Configuracao) -> Contexto:
    relatados: list[dict[str, Any]] = []

    async def relatar(dados: dict[str, Any]) -> None:
        relatados.append(dados)

    contexto = Contexto(configuracao=configuracao, relatar=relatar)
    contexto.relatados = relatados  # type: ignore[attr-defined]
    return contexto


@pytest.fixture
def autorizada(tmp_path: Path) -> tuple[Configuracao, Path]:
    """Uma pasta com conteudo, ja autorizada nesta maquina."""
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "contrato.txt").write_text("contrato importante", encoding="utf-8")
    (pasta / "nota.txt").write_text("nota fiscal", encoding="utf-8")

    local = Local(pasta=tmp_path / "cfg")
    configuracao = raizes.autorizar(local, pasta)
    return configuracao, pasta


class TestGuardaDeAutorizacao:
    def test_origem_fora_das_pastas_autorizadas_e_recusada(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        """
        O servidor pode PEDIR qualquer caminho.

        O que ele nao pode e obter um que ninguem autorizou aqui — e a recusa
        diz onde resolver, em vez de devolver um backup vazio.
        """
        configuracao, _ = autorizada
        alheia = tmp_path / "de-outra-pessoa"
        alheia.mkdir()

        with pytest.raises(backup_agente.BackupRecusado, match="no proprio computador"):
            backup_agente.montar_pedido({"origens": [str(alheia)]}, _contexto(configuracao))

    def test_caminho_com_dois_pontos_nao_escapa(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        configuracao, pasta = autorizada
        fora = tmp_path / "fora"
        fora.mkdir()

        with pytest.raises(backup_agente.BackupRecusado):
            backup_agente.montar_pedido(
                {"origens": [str(pasta / ".." / "fora")]}, _contexto(configuracao)
            )

    def test_sem_pasta_autorizada_recusa_com_instrucao(self) -> None:
        """
        Dispositivo pareado e sem autorizacao nao produz backup vazio.

        Backup vazio pareceria sucesso — e alguem descobriria a verdade no dia
        em que precisasse restaurar.
        """
        with pytest.raises(backup_agente.BackupRecusado, match="Autorize pelo Agente"):
            backup_agente.montar_pedido({}, _contexto(Configuracao()))

    def test_sem_origens_usa_as_pastas_autorizadas(
        self, autorizada: tuple[Configuracao, Path]
    ) -> None:
        configuracao, pasta = autorizada

        pedido = backup_agente.montar_pedido({}, _contexto(configuracao))

        assert pedido.origens == (pasta.resolve(),)


class TestExecucao:
    def test_gera_pacote_conferivel(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        configuracao, _ = autorizada
        destino = tmp_path / "saida" / "pacote.zip"

        ficha = asyncio.run(
            backup_agente.executar_backup({"destino": str(destino)}, _contexto(configuracao))
        )

        assert ficha["arquivos"] == 2
        assert ficha["com_ressalva"] is False
        assert destino.is_file()

        from autotarefas.tasks.backup import verify_backup

        assert verify_backup(destino).ok is True

    def test_o_pacote_fica_na_maquina_e_o_live_recebe_so_a_ficha(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        """
        Decisao H-4: o ZIP nao sobe.

        E o caminho local tambem nao: ele entregaria a estrutura de pastas da
        empresa ao servidor, que nao precisa dela para nada.
        """
        configuracao, _ = autorizada
        destino = tmp_path / "saida" / "pacote.zip"

        ficha = asyncio.run(
            backup_agente.executar_backup({"destino": str(destino)}, _contexto(configuracao))
        )

        assert ficha["pacote"] == "pacote.zip"
        assert str(tmp_path) not in str(ficha)
        assert "conteudo" not in ficha

    def test_destino_padrao_fica_fora_da_pasta_copiada(
        self, autorizada: tuple[Configuracao, Path]
    ) -> None:
        """
        Dentro da pasta copiada, o pacote de hoje entraria no de amanha.

        O tamanho dobraria a cada dia, em silencio, ate o disco encher.
        """
        configuracao, pasta = autorizada

        pedido = backup_agente.montar_pedido({}, _contexto(configuracao))

        assert pasta.resolve() not in pedido.destino.resolve().parents
        assert pedido.destino.resolve() != pasta.resolve()

    def test_relata_progresso(self, autorizada: tuple[Configuracao, Path], tmp_path: Path) -> None:
        configuracao, _ = autorizada
        contexto = _contexto(configuracao)

        asyncio.run(backup_agente.executar_backup({"destino": str(tmp_path / "p.zip")}, contexto))

        etapas = [item["etapa"] for item in contexto.relatados]  # type: ignore[attr-defined]
        assert etapas == ["iniciando", "concluido"]

    def test_arquivo_travado_vira_ressalva_e_nao_falha(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        """
        Backup que copiou quase tudo nao e falha: e pacote util com ausencias.

        O que nao pode e a ausencia ficar invisivel.
        """
        configuracao, pasta = autorizada
        travado = pasta / "planilha.xlsx"
        travado.write_text("conteudo", encoding="utf-8")

        if os.name != "nt":
            pytest.skip("travar arquivo e especifico do Windows")

        with travado.open("r+b"):
            import msvcrt

            with travado.open("r+b") as alvo:
                msvcrt.locking(alvo.fileno(), msvcrt.LK_NBLCK, 1)
                try:
                    ficha = asyncio.run(
                        backup_agente.executar_backup(
                            {"destino": str(tmp_path / "p.zip")}, _contexto(configuracao)
                        )
                    )
                finally:
                    alvo.seek(0)
                    msvcrt.locking(alvo.fileno(), msvcrt.LK_UNLCK, 1)

        assert ficha["com_ressalva"] is True
        assert any("planilha.xlsx" in item["arquivo"] for item in ficha["nao_lidos"])


@pytest.mark.slow
class TestArquivoGrande:
    def test_arquivo_grande_nao_carrega_tudo_na_memoria(self, tmp_path: Path) -> None:
        """
        O limite de 10 MB e do NAVEGADOR, nao do produto.

        Aqui um arquivo de 12 MB e copiado com o pico de alocacao medido. Sem
        streaming, o pico passaria do tamanho do proprio arquivo — e um video
        de gigabytes derrubaria o Agente na maquina do cliente.
        """
        pasta = tmp_path / "midia"
        pasta.mkdir()
        grande = pasta / "video.mp4"
        # Conteudo pseudo-aleatorio: texto repetido comprimiria a quase nada e
        # o teste mediria o compressor, nao o streaming.
        grande.write_bytes(os.urandom(TAMANHO_GRANDE))

        local = Local(pasta=tmp_path / "cfg")
        configuracao = raizes.autorizar(local, pasta)
        destino = tmp_path / "saida" / "grande.zip"

        tracemalloc.start()
        try:
            ficha = asyncio.run(
                backup_agente.executar_backup({"destino": str(destino)}, _contexto(configuracao))
            )
            _atual, pico = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        assert ficha["arquivos"] == 1
        assert destino.stat().st_size > TAMANHO_GRANDE * 0.9
        assert pico < TETO_MEMORIA, (
            f"pico de {pico / 1024 / 1024:.1f} MB para um arquivo de "
            f"{TAMANHO_GRANDE / 1024 / 1024:.0f} MB: o streaming quebrou"
        )

    def test_arquivo_grande_volta_identico(self, tmp_path: Path) -> None:
        """
        Streaming so vale se o conteudo chegar inteiro do outro lado.

        Copiar por pedacos e facil de fazer quase certo: um pedaco perdido no
        fim so apareceria no dia da restauracao.
        """
        pasta = tmp_path / "midia"
        pasta.mkdir()
        original = os.urandom(TAMANHO_GRANDE)
        (pasta / "video.mp4").write_bytes(original)

        local = Local(pasta=tmp_path / "cfg")
        configuracao = raizes.autorizar(local, pasta)
        destino = tmp_path / "saida" / "grande.zip"

        asyncio.run(
            backup_agente.executar_backup({"destino": str(destino)}, _contexto(configuracao))
        )

        with zipfile.ZipFile(destino) as pacote:
            nome = next(n for n in pacote.namelist() if n.endswith("video.mp4"))
            assert pacote.read(nome) == original
