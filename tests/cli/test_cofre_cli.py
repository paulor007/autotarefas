"""Testes do comando `autotarefas cofre`.

O comando existe para uma coisa: dar ao dono uma chave mestra sem que o
produto a guarde. Os testes garantem justamente isso — que a chave nasce
utilizavel, que o comando nao a grava em lugar nenhum, e que "conferir"
distingue chave valida de chave ausente ou torta.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from click.testing import CliRunner

from autotarefas.cli.commands.cofre import TAMANHO_CHAVE, VAR_CHAVE, cofre
from autotarefas.cli.context import CLIContext


def _rodar(argumentos: list[str]) -> tuple[int, str]:
    resultado = CliRunner().invoke(cofre, argumentos, obj=CLIContext())
    return resultado.exit_code, resultado.output


class TestNovaChave:
    def test_gera_chave_utilizavel(self) -> None:
        codigo, saida = _rodar(["nova-chave"])

        assert codigo == 0
        linha = next(texto for texto in saida.splitlines() if VAR_CHAVE in texto)
        valor = linha.split("=", 1)[1].strip()
        assert len(base64.urlsafe_b64decode(valor)) == TAMANHO_CHAVE

    def test_duas_chamadas_dao_chaves_diferentes(self) -> None:
        _, primeira = _rodar(["nova-chave"])
        _, segunda = _rodar(["nova-chave"])
        assert primeira != segunda

    def test_avisa_que_perder_a_chave_e_perder_o_cofre(self) -> None:
        """
        O aviso e a parte importante do comando.

        Sem ele, alguem trocaria a chave achando que e um detalhe e so
        descobriria o custo no dia de restaurar.
        """
        _, saida = _rodar(["nova-chave"])
        assert "NAO poderao ser abertos" in saida

    def test_nao_grava_a_chave_em_arquivo_nenhum(self, tmp_path: Path) -> None:
        """O produto entrega a chave e esquece: quem guarda e o dono."""
        with CliRunner().isolated_filesystem(temp_dir=tmp_path) as pasta:
            _rodar(["nova-chave"])
            assert list(Path(pasta).iterdir()) == []


class TestConferir:
    def test_sem_variavel_avisa_e_falha(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(VAR_CHAVE, raising=False)
        codigo, saida = _rodar(["conferir"])

        assert codigo == 1
        assert "trancado" in saida

    def test_chave_valida_passa(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            VAR_CHAVE, base64.urlsafe_b64encode(b"a" * TAMANHO_CHAVE).decode("ascii")
        )
        codigo, saida = _rodar(["conferir"])

        assert codigo == 0
        assert "valida" in saida

    def test_chave_curta_e_recusada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Chave curta e pior do que chave ausente: parece configurada.
        """
        monkeypatch.setenv(VAR_CHAVE, base64.urlsafe_b64encode(b"curta").decode("ascii"))
        codigo, saida = _rodar(["conferir"])

        assert codigo == 1
        assert "precisa de" in saida

    def test_chave_que_nao_e_base64_e_recusada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(VAR_CHAVE, "isto nao e base64 !!!")
        codigo, saida = _rodar(["conferir"])

        assert codigo == 1
        assert "base64" in saida

    def test_conferir_nunca_mostra_a_chave(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Conferir e dizer 'serve' — nao repetir o segredo no terminal."""
        segredo = base64.urlsafe_b64encode(b"b" * TAMANHO_CHAVE).decode("ascii")
        monkeypatch.setenv(VAR_CHAVE, segredo)
        _, saida = _rodar(["conferir"])

        assert segredo not in saida


class TestChaveDeBackup:
    """
    A chave de assinatura e separada da mestra, e de proposito.

    A mestra protege o cofre no servidor; esta viaja ate a maquina que gera o
    pacote. Comprometer uma nao pode entregar a outra.
    """

    def test_gera_chave_com_o_nome_da_variavel_certa(self) -> None:
        from autotarefas.tasks.assinatura import VAR_CHAVE as VAR_BACKUP

        codigo, saida = _rodar(["chave-de-backup"])

        assert codigo == 0
        assert VAR_BACKUP in saida
        linha = next(texto for texto in saida.splitlines() if VAR_BACKUP in texto)
        valor = linha.split("=", 1)[1].strip()
        assert len(base64.urlsafe_b64decode(valor)) >= 32

    def test_e_diferente_da_chave_mestra(self) -> None:
        from autotarefas.tasks.assinatura import VAR_CHAVE as VAR_BACKUP

        _, backup = _rodar(["chave-de-backup"])
        _, mestra = _rodar(["nova-chave"])

        assert VAR_BACKUP in backup
        assert VAR_BACKUP not in mestra
        assert VAR_CHAVE not in backup

    def test_explica_o_que_acontece_sem_a_chave(self) -> None:
        """Quem nao configurar precisa saber exatamente o que perde."""
        _, saida = _rodar(["chave-de-backup"])
        assert "autenticidade nao foi" in saida
