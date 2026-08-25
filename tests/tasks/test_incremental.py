"""Backup incremental por arquivo, com catálogo (02.I).

Os dois critérios de aceite do card viram teste direto:

- **arquivo idêntico não é reenviado** — `test_arquivo_identico_nao_entra_no_segundo_pacote`;
- **data alterada sem conteúdo alterado não infla o pacote** —
  `test_data_mudada_sem_conteudo_mudado_nao_recopia`. É o caso do Excel, que
  reescreve o arquivo só de abrir e fechar.

E um terceiro, que é o que separa incremental usável de incremental perigoso:
o pacote precisa dizer **em qual pacote anterior** cada arquivo pulado está.
Sem essa referência, o incremental produz pacotes que ninguém consegue juntar
de volta.

O que NÃO é prometido, e é testado que não se promete: deduplicação e delta em
nível de bloco. Um arquivo que muda um byte é copiado inteiro.
"""

from __future__ import annotations

import os
import time
import zipfile
from pathlib import Path

import pytest

from autotarefas.tasks.backup import BackupTask, verify_backup
from autotarefas.tasks.catalogo import NOME, Catalogo, Situacao, decidir


@pytest.fixture
def origem(tmp_path: Path) -> Path:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "contrato.txt").write_text("contrato importante", encoding="utf-8")
    (pasta / "nota.txt").write_text("nota fiscal", encoding="utf-8")
    return pasta


@pytest.fixture
def catalogo(tmp_path: Path) -> Catalogo:
    return Catalogo(tmp_path / "pacotes" / NOME)


def _rodar(origem: Path, destino: Path, catalogo: Catalogo | None = None) -> dict:
    resultado = BackupTask(sources=[origem], destination=destino, catalogo=catalogo).run()
    assert resultado.status.name in {"SUCCESS", "PARTIAL"}, resultado.error_message
    return resultado.data


def _conteudo(pacote: Path) -> set[str]:
    with zipfile.ZipFile(pacote) as zf:
        return {
            nome
            for nome in zf.namelist()
            if not nome.endswith("/") and nome not in {"MANIFESTO.csv", "ASSINATURA.txt"}
        }


class TestDecisao:
    def test_arquivo_novo(self) -> None:
        assert (
            decidir(None, tamanho=10, modificado_em=1.0, calcular_sha=lambda: "x").situacao
            is Situacao.NOVO
        )

    def test_tamanho_diferente_nao_calcula_hash(self) -> None:
        """
        Tamanho diferente é conteúdo diferente.

        Calcular o hash aqui seria ler o arquivo inteiro para confirmar o
        óbvio — e num backup de 40 GB isso custa a janela toda.
        """
        from autotarefas.tasks.catalogo import Anterior

        def nao_deveria() -> str:
            msg = "hash desnecessario"
            raise AssertionError(msg)

        anterior = Anterior(tamanho=10, modificado_em=1.0, sha256="abc", pacote="p1")

        assert (
            decidir(anterior, tamanho=20, modificado_em=1.0, calcular_sha=nao_deveria).situacao
            is Situacao.ALTERADO
        )

    def test_data_identica_nao_calcula_hash(self) -> None:
        """O caminho rápido, e o mais comum numa pasta de escritório."""
        from autotarefas.tasks.catalogo import Anterior

        def nao_deveria() -> str:
            msg = "hash desnecessario"
            raise AssertionError(msg)

        anterior = Anterior(tamanho=10, modificado_em=1000.0, sha256="abc", pacote="p1")

        assert (
            decidir(anterior, tamanho=10, modificado_em=1000.0, calcular_sha=nao_deveria).situacao
            is Situacao.INALTERADO
        )

    def test_alteracao_logo_apos_o_backup_nao_se_perde(self) -> None:
        """
        A guarda contra a perda silenciosa.

        Uma tolerância de dois segundos na data — comum em ferramentas de
        backup por causa do FAT — faria um arquivo alterado UM segundo depois
        de ser registrado passar como inalterado. A alteração sumiria sem
        ninguém saber, que é o pior defeito possível aqui.
        """
        from autotarefas.tasks.catalogo import Anterior

        anterior = Anterior(tamanho=10, modificado_em=1000.0, sha256="abc", pacote="p1")

        decisao = decidir(
            anterior, tamanho=10, modificado_em=1001.0, calcular_sha=lambda: "conteudo-novo"
        )

        assert decisao.situacao is Situacao.ALTERADO

    def test_data_diferente_com_mesmo_conteudo_e_inalterado(self) -> None:
        """
        O caso do Excel: abrir e fechar reescreve o arquivo sem mudá-lo.

        Sem esta regra, o backup de amanhã recopiaria toda planilha que
        alguém abriu hoje.
        """
        from autotarefas.tasks.catalogo import Anterior

        anterior = Anterior(tamanho=10, modificado_em=1000.0, sha256="abc", pacote="p1")

        assert (
            decidir(anterior, tamanho=10, modificado_em=9999.0, calcular_sha=lambda: "abc").situacao
            is Situacao.INALTERADO
        )


class TestCatalogo:
    def test_registra_e_le(self, catalogo: Catalogo) -> None:
        catalogo.registrar("dados/a.txt", tamanho=10, modificado_em=1.0, sha256="abc", pacote="p1")

        anterior = catalogo.anterior("dados/a.txt")

        assert anterior is not None
        assert anterior.pacote == "p1"
        assert catalogo.quantos() == 1

    def test_regravar_substitui(self, catalogo: Catalogo) -> None:
        catalogo.registrar("a", tamanho=1, modificado_em=1.0, sha256="x", pacote="p1")
        catalogo.registrar("a", tamanho=2, modificado_em=2.0, sha256="y", pacote="p2")

        anterior = catalogo.anterior("a")
        assert anterior is not None
        assert anterior.pacote == "p2"
        assert catalogo.quantos() == 1

    def test_pacote_removido_pela_retencao_e_esquecido(self, catalogo: Catalogo) -> None:
        """
        O teste que evita a referência quebrada.

        Se o catálogo apontasse para um pacote que a retenção levou, a
        restauração encontraria uma referência morta — pior do que copiar de
        novo.
        """
        catalogo.registrar_pacote("p1", "2026-08-20T02:00:00")
        catalogo.registrar_pacote("p2", "2026-08-21T02:00:00")
        catalogo.registrar("a", tamanho=1, modificado_em=1.0, sha256="x", pacote="p1")
        catalogo.registrar("b", tamanho=1, modificado_em=1.0, sha256="y", pacote="p2")

        removidos = catalogo.sincronizar_com({"p2"})

        assert removidos == 1
        assert catalogo.anterior("a") is None
        assert catalogo.anterior("b") is not None


class TestIncrementalNoPacote:
    def test_sem_catalogo_o_pacote_e_completo(self, origem: Path, tmp_path: Path) -> None:
        """
        O padrão continua sendo o backup completo.

        É ele que vale quando ninguém configurou nada — e um padrão que
        depende de configuração não é padrão.
        """
        dados = _rodar(origem, tmp_path / "p1.zip")

        assert dados["incremental"] is False
        assert dados["file_count"] == 2

    def test_arquivo_identico_nao_entra_no_segundo_pacote(
        self, origem: Path, tmp_path: Path, catalogo: Catalogo
    ) -> None:
        """Critério de aceite: arquivo idêntico não é reenviado."""
        _rodar(origem, tmp_path / "pacotes" / "p1.zip", catalogo)
        (origem / "novo.txt").write_text("arquivo novo", encoding="utf-8")

        segundo = _rodar(origem, tmp_path / "pacotes" / "p2.zip", catalogo)

        assert segundo["file_count"] == 1
        assert segundo["inalterados_count"] == 2
        assert _conteudo(tmp_path / "pacotes" / "p2.zip") == {"dados/novo.txt"}

    def test_data_mudada_sem_conteudo_mudado_nao_recopia(
        self, origem: Path, tmp_path: Path, catalogo: Catalogo
    ) -> None:
        """
        Critério de aceite: data alterada sem conteúdo alterado não infla o
        pacote.
        """
        _rodar(origem, tmp_path / "pacotes" / "p1.zip", catalogo)

        alvo = origem / "contrato.txt"
        conteudo = alvo.read_bytes()
        time.sleep(0.05)
        alvo.write_bytes(conteudo)
        futuro = time.time() + 3600
        os.utime(alvo, (futuro, futuro))

        segundo = _rodar(origem, tmp_path / "pacotes" / "p2.zip", catalogo)

        assert segundo["file_count"] == 0
        assert segundo["inalterados_count"] == 2

    def test_conteudo_alterado_entra_de_novo(
        self, origem: Path, tmp_path: Path, catalogo: Catalogo
    ) -> None:
        _rodar(origem, tmp_path / "pacotes" / "p1.zip", catalogo)
        (origem / "contrato.txt").write_text("contrato REVISADO", encoding="utf-8")

        segundo = _rodar(origem, tmp_path / "pacotes" / "p2.zip", catalogo)

        assert _conteudo(tmp_path / "pacotes" / "p2.zip") == {"dados/contrato.txt"}
        assert segundo["inalterados_count"] == 1

    def test_um_byte_alterado_copia_o_arquivo_INTEIRO(
        self, tmp_path: Path, catalogo: Catalogo
    ) -> None:
        """
        O limite que o produto NÃO pode esconder.

        Não há deduplicação nem delta em nível de bloco: um arquivo que muda
        um byte é copiado inteiro. Prometer o contrário faria alguém planejar
        a banda de upload com números que não existem.
        """
        pasta = tmp_path / "dados"
        pasta.mkdir()
        grande = pasta / "grande.bin"
        grande.write_bytes(b"A" * 200_000)

        _rodar(pasta, tmp_path / "pacotes" / "p1.zip", catalogo)
        bruto = bytearray(grande.read_bytes())
        bruto[0] = ord("B")
        grande.write_bytes(bytes(bruto))
        _rodar(pasta, tmp_path / "pacotes" / "p2.zip", catalogo)

        with zipfile.ZipFile(tmp_path / "pacotes" / "p2.zip") as zf:
            info = zf.getinfo("dados/grande.bin")

        assert info.file_size == 200_000  # o arquivo inteiro, não o byte


class TestManifestoEConferencia:
    def test_o_manifesto_diz_em_qual_pacote_o_arquivo_esta(
        self, origem: Path, tmp_path: Path, catalogo: Catalogo
    ) -> None:
        """
        A referência que torna a restauração possível.

        Sem ela, o incremental produziria pacotes que ninguém consegue juntar
        de volta.
        """
        _rodar(origem, tmp_path / "pacotes" / "p1.zip", catalogo)
        (origem / "novo.txt").write_text("novo", encoding="utf-8")
        _rodar(origem, tmp_path / "pacotes" / "p2.zip", catalogo)

        with zipfile.ZipFile(tmp_path / "pacotes" / "p2.zip") as zf:
            manifesto = zf.read("MANIFESTO.csv").decode("utf-8")

        assert "INALTERADO" in manifesto
        assert "esta em p1.zip" in manifesto

    def test_pacote_incremental_confere_sem_parecer_defeituoso(
        self, origem: Path, tmp_path: Path, catalogo: Catalogo
    ) -> None:
        """
        Tratar `INALTERADO` como "declarado e ausente" faria todo pacote
        incremental parecer quebrado.
        """
        _rodar(origem, tmp_path / "pacotes" / "p1.zip", catalogo)
        (origem / "novo.txt").write_text("novo", encoding="utf-8")
        _rodar(origem, tmp_path / "pacotes" / "p2.zip", catalogo)

        relatorio = verify_backup(tmp_path / "pacotes" / "p2.zip")

        assert relatorio.ok is True
        assert relatorio.missing == ()

    def test_a_conferencia_diz_de_quais_pacotes_este_depende(
        self, origem: Path, tmp_path: Path, catalogo: Catalogo
    ) -> None:
        """
        Quem restaura precisa saber EXATAMENTE o que ter em mãos.

        Descobrir isso na hora da restauração é descobrir tarde.
        """
        _rodar(origem, tmp_path / "pacotes" / "p1.zip", catalogo)
        (origem / "novo.txt").write_text("novo", encoding="utf-8")
        _rodar(origem, tmp_path / "pacotes" / "p2.zip", catalogo)

        relatorio = verify_backup(tmp_path / "pacotes" / "p2.zip")

        assert relatorio.chain == ("p1.zip",)
        assert len(relatorio.unchanged) == 2
        assert relatorio.as_dict()["incremental"] is True

    def test_pacote_completo_nao_declara_dependencia(self, origem: Path, tmp_path: Path) -> None:
        relatorio = verify_backup(_caminho_do_completo(origem, tmp_path))

        assert relatorio.chain == ()
        assert relatorio.as_dict()["incremental"] is False


def _caminho_do_completo(origem: Path, tmp_path: Path) -> Path:
    destino = tmp_path / "completo.zip"
    _rodar(origem, destino)
    return destino
