"""Testes da assinatura do manifesto (02.B).

O teste que da sentido a esta subetapa inteira e
`test_recalcular_o_manifesto_deixa_de_funcionar`: ate aqui, quem alterava um
arquivo e refazia o manifesto passava pela conferencia sem ser notado, porque a
chave da conferencia viajava dentro do proprio pacote. Isso estava documentado
como limitacao. Agora tem que estar fechado — e o teste prova que esta.
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from autotarefas.tasks import assinatura
from autotarefas.tasks.assinatura import Autenticidade
from autotarefas.tasks.backup import MANIFEST_NAME, BackupTask, verify_backup


@pytest.fixture
def chave() -> str:
    return assinatura.gerar_chave()


@pytest.fixture
def origem(tmp_path: Path) -> Path:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "contrato.txt").write_text("contrato importante", encoding="utf-8")
    (pasta / "nota.txt").write_text("nota fiscal", encoding="utf-8")
    return pasta


def _empacotar(origem: Path, destino: Path) -> Path:
    resultado = BackupTask(sources=[origem], destination=destino).run()
    assert resultado.status.name in {"SUCCESS", "PARTIAL"}, resultado.error_message
    return destino


def _adulterar_recalculando_manifesto(pacote: Path, destino: Path, arcname: str) -> None:
    """
    O ataque que a assinatura existe para deter.

    Troca o conteudo de um arquivo e refaz a linha do manifesto para o novo
    hash. Sem assinatura, o pacote resultante passa na conferencia.
    """
    with zipfile.ZipFile(pacote) as zf:
        itens = {nome: zf.read(nome) for nome in zf.namelist()}

    novo = b"conteudo trocado pelo atacante\n"
    itens[arcname] = novo

    linhas = list(csv.reader(io.StringIO(itens[MANIFEST_NAME].decode("utf-8"))))
    for linha in linhas:
        if len(linha) > 4 and linha[1] == arcname:
            linha[3] = str(len(novo))
            linha[4] = hashlib.sha256(novo).hexdigest()
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerows(linhas)
    itens[MANIFEST_NAME] = buffer.getvalue().encode("utf-8")

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome, dados in itens.items():
            zf.writestr(nome, dados)


# ============================================================
# A chave
# ============================================================


class TestChave:
    def test_chave_gerada_e_aceita(self, chave: str) -> None:
        assert len(assinatura.decodificar(chave)) >= assinatura.TAMANHO_MINIMO

    def test_chave_curta_e_recusada(self) -> None:
        """
        Chave curta enfraquece o HMAC e ainda parece configurada.

        Recusar alto e melhor do que assinar com material fraco.
        """
        import base64

        curta = base64.urlsafe_b64encode(b"curta").decode("ascii")
        with pytest.raises(assinatura.ChaveInvalida, match="ao menos"):
            assinatura.decodificar(curta)

    def test_chave_que_nao_e_base64_e_recusada(self) -> None:
        with pytest.raises(assinatura.ChaveInvalida, match="base64"):
            assinatura.decodificar("isto nao e base64 !!!")

    def test_sem_variavel_nao_ha_chave_e_isso_nao_e_erro(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Assinar e opcional.

        Recusar backup por falta de chave trocaria um risco por outro pior: o
        de nao existir copia nenhuma.
        """
        monkeypatch.delenv(assinatura.VAR_CHAVE, raising=False)
        assert assinatura.chave_configurada() is None

    def test_impressao_nao_revela_a_chave(self, chave: str) -> None:
        bruta = assinatura.decodificar(chave)
        impressao = assinatura.impressao_da_chave(bruta)

        assert len(impressao) == 16
        assert impressao not in chave
        assert assinatura.impressao_da_chave(bruta) == impressao


# ============================================================
# Assinar e conferir, isolado
# ============================================================


class TestConferencia:
    def test_assinatura_propria_confere(self, chave: str) -> None:
        bruta = assinatura.decodificar(chave)
        manifesto = b"situacao,arquivo\nincluido,a.txt\n"
        conteudo = assinatura.assinar(manifesto, bruta)

        assert assinatura.conferir(conteudo, manifesto, bruta) is Autenticidade.AUTENTICO

    def test_manifesto_alterado_nao_confere(self, chave: str) -> None:
        bruta = assinatura.decodificar(chave)
        conteudo = assinatura.assinar(b"manifesto original", bruta)

        assert (
            assinatura.conferir(conteudo, b"manifesto trocado", bruta) is Autenticidade.ADULTERADO
        )

    def test_sem_chave_diz_sem_chave_e_nao_adulterado(self, chave: str) -> None:
        """
        Alarme falso treina a pessoa a ignorar o alarme de verdade.

        Quem so nao tem a chave em maos precisa ouvir "nao da para conferir",
        e nao "seu backup foi adulterado".
        """
        bruta = assinatura.decodificar(chave)
        conteudo = assinatura.assinar(b"manifesto", bruta)

        assert assinatura.conferir(conteudo, b"manifesto", None) is Autenticidade.SEM_CHAVE

    def test_outra_chave_e_distinguida_de_adulteracao(self, chave: str) -> None:
        """Trocar a chave e um evento administrativo, nao um ataque."""
        bruta = assinatura.decodificar(chave)
        outra = assinatura.decodificar(assinatura.gerar_chave())
        conteudo = assinatura.assinar(b"manifesto", bruta)

        assert assinatura.conferir(conteudo, b"manifesto", outra) is Autenticidade.OUTRA_CHAVE

    def test_arquivo_de_assinatura_estragado_e_adulteracao(self, chave: str) -> None:
        bruta = assinatura.decodificar(chave)
        assert assinatura.conferir("lixo qualquer", b"manifesto", bruta) is (
            Autenticidade.ADULTERADO
        )

    def test_toda_conclusao_tem_frase_para_a_pessoa(self) -> None:
        """Nenhum desfecho pode chegar a tela sem explicacao."""
        for desfecho in Autenticidade:
            assert assinatura.EXPLICACAO[desfecho]


# ============================================================
# Ponta a ponta, no pacote de verdade
# ============================================================


class TestPacoteAssinado:
    def test_com_chave_o_pacote_sai_assinado_e_confere(
        self, tmp_path: Path, origem: Path, chave: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(assinatura.VAR_CHAVE, chave)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        with zipfile.ZipFile(pacote) as zf:
            assert assinatura.NOME_ASSINATURA in zf.namelist()

        relatorio = verify_backup(pacote)
        assert relatorio.ok is True
        assert relatorio.signed is True
        assert relatorio.authenticity is Autenticidade.AUTENTICO

    def test_sem_chave_o_pacote_sai_sem_assinatura_e_ainda_serve(
        self, tmp_path: Path, origem: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(assinatura.VAR_CHAVE, raising=False)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        with zipfile.ZipFile(pacote) as zf:
            assert assinatura.NOME_ASSINATURA not in zf.namelist()

        relatorio = verify_backup(pacote)
        assert relatorio.ok is True
        assert relatorio.signed is False
        assert relatorio.authenticity is Autenticidade.NAO_ASSINADO

    def test_recalcular_o_manifesto_deixa_de_funcionar(
        self, tmp_path: Path, origem: Path, chave: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        O teste que justifica a 02.B inteira.

        Ate aqui, alterar um arquivo e refazer o manifesto produzia um pacote
        que passava na conferencia. Com a assinatura, o atacante teria que
        assinar de novo — e nao tem a chave.
        """
        monkeypatch.setenv(assinatura.VAR_CHAVE, chave)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")
        adulterado = tmp_path / "adulterado.zip"
        _adulterar_recalculando_manifesto(pacote, adulterado, "dados/contrato.txt")

        relatorio = verify_backup(adulterado)

        # Os hashes batem: o atacante recalculou tudo direitinho.
        assert relatorio.corrupted == ()
        # E ainda assim o pacote e recusado.
        assert relatorio.ok is False
        assert relatorio.authenticity is Autenticidade.ADULTERADO

    def test_sem_assinatura_o_mesmo_ataque_ainda_passa_e_isso_e_dito(
        self, tmp_path: Path, origem: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A limitacao continua real para quem nao assina — e o texto avisa.

        Prometer protecao que depende de configuracao que o cliente nao fez
        seria pior do que nao ter a protecao.
        """
        monkeypatch.delenv(assinatura.VAR_CHAVE, raising=False)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")
        adulterado = tmp_path / "adulterado.zip"
        _adulterar_recalculando_manifesto(pacote, adulterado, "dados/contrato.txt")

        relatorio = verify_backup(adulterado)

        assert relatorio.ok is True
        assert relatorio.authenticity is Autenticidade.NAO_ASSINADO
        assert "Não comprova autenticidade" in relatorio.as_dict()["limite"]

    def test_apagar_a_assinatura_nao_disfarca_a_adulteracao(
        self, tmp_path: Path, origem: Path, chave: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Remover a assinatura rebaixa o pacote a "nao assinado", e isso aparece.

        Nao ha como o atacante devolver o pacote ao estado de "autentico"; o
        melhor que ele consegue e um pacote que anuncia nao ter prova nenhuma.
        """
        monkeypatch.setenv(assinatura.VAR_CHAVE, chave)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        sem_assinatura = tmp_path / "sem_assinatura.zip"
        with (
            zipfile.ZipFile(pacote) as origem_zip,
            zipfile.ZipFile(sem_assinatura, "w", zipfile.ZIP_DEFLATED) as destino_zip,
        ):
            for nome in origem_zip.namelist():
                if nome != assinatura.NOME_ASSINATURA:
                    destino_zip.writestr(nome, origem_zip.read(nome))

        relatorio = verify_backup(sem_assinatura)
        assert relatorio.signed is False
        assert relatorio.authenticity is Autenticidade.NAO_ASSINADO

    def test_assinatura_nao_e_listada_como_arquivo_nao_declarado(
        self, tmp_path: Path, origem: Path, chave: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A assinatura e metadado do pacote, nao conteudo do cliente.

        Sem esta regra, todo pacote assinado apareceria com um "arquivo nao
        declarado" e pareceria defeituoso.
        """
        monkeypatch.setenv(assinatura.VAR_CHAVE, chave)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        relatorio = verify_backup(pacote)
        assert relatorio.unexpected == ()

    def test_chave_diferente_na_conferencia_nao_e_confundida_com_ataque(
        self, tmp_path: Path, origem: Path, chave: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(assinatura.VAR_CHAVE, chave)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        monkeypatch.setenv(assinatura.VAR_CHAVE, assinatura.gerar_chave())
        relatorio = verify_backup(pacote)

        assert relatorio.authenticity is Autenticidade.OUTRA_CHAVE
        assert relatorio.ok is False

    def test_chave_ilegivel_na_conferencia_vira_sem_chave(
        self, tmp_path: Path, origem: Path, chave: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Chave malformada na hora de conferir nao pode virar 'adulterado'."""
        monkeypatch.setenv(assinatura.VAR_CHAVE, chave)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        monkeypatch.setenv(assinatura.VAR_CHAVE, "nao e base64 !!!")
        relatorio = verify_backup(pacote)

        assert relatorio.authenticity is Autenticidade.SEM_CHAVE
        assert relatorio.ok is True
