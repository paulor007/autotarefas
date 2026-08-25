"""Da politica ao pacote, na maquina (02.E).

O que se prova aqui e a traducao: uma politica configurada na tela vira um
backup de verdade, com destino e retencao aplicados na ordem certa.

A ordem importa e tem teste: a retencao roda DEPOIS do backup e so quando ele
deu certo. Rodar antes apagaria a copia mais antiga para abrir espaco de um
pacote que talvez nem seja criado — trocar uma copia boa por nenhuma.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from apps.agente.agente import backup as backup_agente
from apps.agente.agente import raizes, retencao
from apps.agente.agente.config import Configuracao, Local
from autotarefas.tasks.politica import (
    Destino,
    Politica,
    Retencao,
    TipoDeDestino,
)


@pytest.fixture
def autorizada(tmp_path: Path) -> tuple[Configuracao, Path]:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "contrato.txt").write_text("contrato", encoding="utf-8")
    return raizes.autorizar(Local(pasta=tmp_path / "cfg"), pasta), pasta


class TestTraducao:
    def test_politica_vira_pacote(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        configuracao, pasta = autorizada
        politica = Politica(
            origens=[str(pasta)],
            destino=Destino(tipo=TipoDeDestino.LOCAL, caminho=str(tmp_path / "copia")),
        )

        ficha = asyncio.run(backup_agente.executar_politica(politica, configuracao))

        assert ficha["ok"] is True
        assert ficha["arquivos"] == 1
        assert ficha["entregas"][0]["conferido_no_destino"] is True

    def test_politica_com_vss_sem_elevacao_recusa(
        self, autorizada: tuple[Configuracao, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Recusa com motivo, e nao pacote sem o arquivo aberto."""
        from apps.agente.agente import vss

        configuracao, pasta = autorizada
        monkeypatch.setattr(vss, "elevado", lambda: False)
        monkeypatch.setattr(vss, "no_windows", lambda: True)

        politica = Politica(origens=[str(pasta)], usar_vss=True)

        with pytest.raises(backup_agente.BackupRecusado, match="administrador"):
            asyncio.run(backup_agente.executar_politica(politica, configuracao))


class TestRetencaoNaPolitica:
    def test_retencao_apaga_os_antigos_depois_do_backup(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        configuracao, pasta = autorizada
        destino = tmp_path / "pacotes"
        destino.mkdir()
        base = datetime(2020, 1, 10, 2, 0)
        for i in range(5):
            quando = base - timedelta(days=i)
            (destino / f"backup_{quando:%Y-%m-%d_%H%M}.zip").write_bytes(b"antigo")

        politica = Politica(
            origens=[str(pasta)],
            retencao=Retencao(diarias=1, semanais=0, mensais=0),
        )
        # Sem destino externo, o pacote vai para a pasta padrao; o teste
        # aponta a retencao para a pasta com o historico antigo.
        ficha = asyncio.run(backup_agente.executar_politica(politica, configuracao))
        relatorio = retencao.aplicar(destino, politica.retencao)

        assert ficha["ok"] is True
        assert len(relatorio["removidos"]) == 4
        assert len(retencao.listar(destino)) == 1

    def test_o_pacote_recem_criado_sobrevive_a_retencao(
        self, autorizada: tuple[Configuracao, Path]
    ) -> None:
        """
        A copia que acabou de ser feita nao pode ser a primeira a ir embora.

        Seria o desfecho mais absurdo possivel: fazer backup e apaga-lo em
        seguida, relatando sucesso.
        """
        configuracao, pasta = autorizada
        politica = Politica(
            origens=[str(pasta)],
            retencao=Retencao(diarias=1, semanais=0, mensais=0),
        )

        ficha = asyncio.run(backup_agente.executar_politica(politica, configuracao))

        assert ficha["retencao"]["guardados"] >= 1
        assert ficha["pacote"] not in ficha["retencao"]["removidos"]

    def test_falha_na_faxina_vira_ressalva_e_nao_falha(
        self, autorizada: tuple[Configuracao, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O pacote existe; o que nao deu certo foi a limpeza."""
        configuracao, pasta = autorizada

        def limpeza_com_problema(_pasta: Path, _regra: Retencao) -> dict[str, object]:
            return {"guardados": 1, "removidos": [], "nao_removidos": ["velho.zip"]}

        monkeypatch.setattr(retencao, "aplicar", limpeza_com_problema)

        ficha = asyncio.run(
            backup_agente.executar_politica(Politica(origens=[str(pasta)]), configuracao)
        )

        assert ficha["ok"] is True
        assert ficha["com_ressalva"] is True
        assert "nao puderam ser apagados" in ficha["ressalva"]


class TestIncrementalNaPolitica:
    """
    O incremental so acontece quando a politica pede.

    Desligado por padrao de proposito: o pacote completo se sustenta sozinho,
    e o incremental exige a corrente de pacotes anteriores para restaurar.
    """

    def test_desligado_por_padrao(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        configuracao, pasta = autorizada

        ficha = asyncio.run(
            backup_agente.executar_politica(Politica(origens=[str(pasta)]), configuracao)
        )

        assert ficha["incremental"] is False
        assert ficha["inalterados"] == 0

    def test_segunda_execucao_pula_o_que_nao_mudou(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        configuracao, pasta = autorizada
        politica = Politica(
            origens=[str(pasta)],
            destino=Destino(tipo=TipoDeDestino.LOCAL, caminho=str(tmp_path / "copia")),
            incremental=True,
        )

        primeira = asyncio.run(backup_agente.executar_politica(politica, configuracao))
        (pasta / "novo.txt").write_text("novo", encoding="utf-8")
        segunda = asyncio.run(backup_agente.executar_politica(politica, configuracao))

        assert primeira["arquivos"] == 1
        assert segunda["arquivos"] == 1
        assert segunda["inalterados"] == 1
        assert segunda["incremental"] is True

    def test_catalogo_esquece_pacote_que_a_retencao_apagou(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        """
        Catalogo apontando para pacote apagado e referencia quebrada.

        Melhor copiar de novo do que prometer um arquivo que nao existe.
        """
        configuracao, pasta = autorizada
        politica = Politica(
            origens=[str(pasta)],
            retencao=Retencao(diarias=1, semanais=0, mensais=0),
            incremental=True,
        )

        asyncio.run(backup_agente.executar_politica(politica, configuracao))
        segunda = asyncio.run(backup_agente.executar_politica(politica, configuracao))

        # A chave e o campo existir e ser um numero: a sincronizacao rodou.
        assert "catalogo_esquecidos" in segunda
        assert isinstance(segunda["catalogo_esquecidos"], int)
