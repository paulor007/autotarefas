"""Testes da criptografia do pacote (02.C).

Dois testes carregam o peso desta subetapa:

- `test_conteudo_nao_aparece_em_claro_no_arquivo` — a cifra tem que valer no
  arquivo mesmo, e nao so na promessa;
- `test_e_o_padrao_winzip_aes_256` — o pacote precisa abrir no 7-Zip com a
  senha. Um formato caseiro obrigaria o cliente a ter o AutoTarefas instalado
  para recuperar os proprios arquivos, no dia em que a maquina dele nao existe
  mais.

O terceiro que importa e o do limite: os NOMES continuam visiveis. Se isso
deixar de ser dito, alguem vai guardar o pacote num lugar errado achando que a
lista tambem esta protegida.
"""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path

import pytest

from autotarefas.tasks import assinatura, cifra
from autotarefas.tasks.backup import BackupTask, verify_backup

SENHA = "senha-de-teste-bem-longa"  # pragma: allowlist secret

#: Cabecalho do campo extra que identifica AES no padrao WinZip.
_CAMPO_AES = 0x9901

#: Codigo de forca 3 = AES-256.
_FORCA_256 = 3


@pytest.fixture
def origem(tmp_path: Path) -> Path:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "contrato.txt").write_text("contrato secreto da empresa", encoding="utf-8")
    (pasta / "nota.txt").write_text("nota fiscal reservada", encoding="utf-8")
    return pasta


def _empacotar(origem: Path, destino: Path) -> Path:
    resultado = BackupTask(sources=[origem], destination=destino).run()
    assert resultado.status.name in {"SUCCESS", "PARTIAL"}, resultado.error_message
    return destino


def _campo_aes(pacote: Path, arcname: str) -> tuple[int, str] | None:
    """(bits do AES, fornecedor) da entrada, ou `None` se nao houver cifra."""
    with zipfile.ZipFile(pacote) as zf:
        info = zf.getinfo(arcname)
    extra, posicao = info.extra, 0
    while posicao + 4 <= len(extra):
        cabecalho, tamanho = struct.unpack_from("<HH", extra, posicao)
        if cabecalho == _CAMPO_AES:
            _versao, fornecedor, forca, _metodo = struct.unpack_from("<HHBH", extra, posicao + 4)
            bits = {1: 128, 2: 192, 3: 256}[forca]
            return bits, fornecedor.to_bytes(2, "little").decode("ascii")
        posicao += 4 + tamanho
    return None


# ============================================================
# A senha
# ============================================================


class TestSenha:
    def test_sem_variavel_nao_ha_senha_e_isso_nao_e_erro(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cifrar e opcional: sem senha o cliente ainda precisa ter backup."""
        monkeypatch.delenv(cifra.VAR_SENHA, raising=False)
        assert cifra.senha_configurada() is None

    def test_senha_curta_e_recusada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Senha curta transforma AES-256 em enfeite.

        Recusar alto e melhor do que cifrar com algo que se quebra numa tarde
        e ainda deixar a pessoa achando que esta protegida.
        """
        monkeypatch.setenv(cifra.VAR_SENHA, "1234")
        with pytest.raises(cifra.SenhaFraca, match="minimo"):
            cifra.senha_configurada()

    def test_senha_sorteada_passa_no_minimo(self) -> None:
        assert len(cifra.gerar_senha()) >= cifra.MINIMO_SENHA

    def test_duas_senhas_sorteadas_sao_diferentes(self) -> None:
        assert cifra.gerar_senha() != cifra.gerar_senha()


# ============================================================
# O pacote cifrado
# ============================================================


class TestPacoteCifrado:
    def test_conteudo_nao_aparece_em_claro_no_arquivo(
        self, tmp_path: Path, origem: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cifra vale no arquivo, nao so na promessa."""
        monkeypatch.setenv(cifra.VAR_SENHA, SENHA)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        bruto = pacote.read_bytes()
        assert b"contrato secreto da empresa" not in bruto
        assert b"nota fiscal reservada" not in bruto

    def test_e_o_padrao_winzip_aes_256(
        self, tmp_path: Path, origem: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Tem que ser o padrao que 7-Zip e WinRAR abrem.

        `AE` e o identificador de fornecedor do WinZip AES; forca 3 e 256 bits.
        Se isto mudar para um formato proprio, o cliente perde a capacidade de
        abrir o proprio backup sem o AutoTarefas.
        """
        monkeypatch.setenv(cifra.VAR_SENHA, SENHA)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        assert _campo_aes(pacote, "dados/contrato.txt") == (256, "AE")

    def test_biblioteca_padrao_le_os_nomes_mas_nao_o_conteudo(
        self, tmp_path: Path, origem: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        O limite que precisa estar dito: a lista de arquivos NAO e cifrada.

        Quem achar o pacote nao le o contrato, mas ve que existe um arquivo
        chamado `contrato.txt`. Guardar o pacote onde alguem possa achar
        continua sendo uma decisao com consequencia.
        """
        monkeypatch.setenv(cifra.VAR_SENHA, SENHA)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        with zipfile.ZipFile(pacote) as zf:
            assert "dados/contrato.txt" in zf.namelist()
            with pytest.raises((NotImplementedError, RuntimeError)):
                zf.read("dados/contrato.txt", pwd=SENHA.encode("utf-8"))

    def test_manifesto_tambem_e_cifrado(
        self, tmp_path: Path, origem: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        O manifesto lista hashes e caminhos: e informacao sobre a empresa.

        Deixa-lo em claro entregaria a estrutura inteira de pastas a quem
        achasse o pacote.
        """
        monkeypatch.setenv(cifra.VAR_SENHA, SENHA)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        assert _campo_aes(pacote, "MANIFESTO.csv") == (256, "AE")

    def test_sem_senha_o_pacote_sai_em_claro_e_isso_e_dito(
        self, tmp_path: Path, origem: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(cifra.VAR_SENHA, raising=False)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        assert _campo_aes(pacote, "dados/contrato.txt") is None
        relatorio = verify_backup(pacote)
        assert relatorio.encrypted is False
        assert "não cifrado" in relatorio.as_dict()["limite_cifra"]


# ============================================================
# Conferencia de pacote cifrado
# ============================================================


class TestConferenciaComCifra:
    def test_com_a_senha_a_conferencia_funciona_normalmente(
        self, tmp_path: Path, origem: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(cifra.VAR_SENHA, SENHA)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        relatorio = verify_backup(pacote)

        assert relatorio.ok is True
        assert relatorio.encrypted is True
        assert relatorio.checked == 2
        assert "AES-256" in relatorio.as_dict()["limite_cifra"]

    def test_sem_a_senha_diz_o_que_fazer(
        self, tmp_path: Path, origem: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        "Bad password for file" nao ajuda ninguem.

        A mensagem tem que dizer que o pacote esta cifrado e onde informar a
        senha.
        """
        monkeypatch.setenv(cifra.VAR_SENHA, SENHA)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        monkeypatch.delenv(cifra.VAR_SENHA, raising=False)
        relatorio = verify_backup(pacote)

        assert relatorio.ok is False
        assert "cifrado" in relatorio.problem
        assert cifra.VAR_SENHA in relatorio.problem

    def test_senha_errada_nao_vira_pacote_corrompido(
        self, tmp_path: Path, origem: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Senha errada e senha errada — nao "seu backup esta corrompido".

        Confundir os dois faria alguem descartar um backup perfeitamente bom.
        """
        monkeypatch.setenv(cifra.VAR_SENHA, SENHA)
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        monkeypatch.setenv(cifra.VAR_SENHA, "outra-senha-bem-longa")
        relatorio = verify_backup(pacote)

        assert relatorio.ok is False
        assert "senha" in relatorio.problem.lower()

    def test_cifra_e_assinatura_convivem(
        self, tmp_path: Path, origem: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Sao protecoes diferentes e independentes.

        A cifra impede que estranhos leiam; a assinatura impede que alterem
        sem ser notados. Um pacote de verdade quer as duas.
        """
        monkeypatch.setenv(cifra.VAR_SENHA, SENHA)
        monkeypatch.setenv(assinatura.VAR_CHAVE, assinatura.gerar_chave())
        pacote = _empacotar(origem, tmp_path / "pacote.zip")

        relatorio = verify_backup(pacote)

        assert relatorio.ok is True
        assert relatorio.encrypted is True
        assert relatorio.authenticity is assinatura.Autenticidade.AUTENTICO
