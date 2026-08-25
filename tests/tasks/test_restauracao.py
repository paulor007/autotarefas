"""Restauração (02.H).

Os quatro critérios de aceite do card viram testes diretos:

- reproduz os arquivos **byte a byte**;
- **recusa caminho malicioso** no pacote;
- **não sobrescreve** sem permissão explícita;
- **recusa pacote corrompido** — inteiro, e não "até onde deu".

O quinto teste que importa é o do incremental: um pacote que depende da
corrente e não a tem precisa **dizer o que falta**, e não restaurar pela metade
chamando de sucesso.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from autotarefas.tasks import assinatura
from autotarefas.tasks.backup import BackupTask
from autotarefas.tasks.catalogo import NOME, Catalogo
from autotarefas.tasks.restauracao import (
    RestauracaoRecusada,
    caminho_seguro,
    listar_conteudo,
    restaurar,
)


@pytest.fixture
def origem(tmp_path: Path) -> Path:
    pasta = tmp_path / "dados"
    (pasta / "contratos").mkdir(parents=True)
    (pasta / "contrato.txt").write_text("contrato importante", encoding="utf-8")
    (pasta / "contratos" / "aditivo.txt").write_text("aditivo", encoding="utf-8")
    (pasta / "planilha.bin").write_bytes(os.urandom(50_000))
    return pasta


def _empacotar(origem: Path, destino: Path, catalogo: Catalogo | None = None) -> Path:
    resultado = BackupTask(sources=[origem], destination=destino, catalogo=catalogo).run()
    assert resultado.status.name in {"SUCCESS", "PARTIAL"}, resultado.error_message
    return destino


class TestCaminhoSeguro:
    @pytest.mark.parametrize(
        "malicioso",
        [
            "../fora.txt",
            "../../Windows/System32/cmd.exe",
            "dados/../../fora.txt",
            "/etc/passwd",
            "C:/Windows/System32/drivers/etc/hosts",
            "..\\..\\Windows\\notepad.exe",
        ],
    )
    def test_caminho_que_sai_da_pasta_e_recusado(self, tmp_path: Path, malicioso: str) -> None:
        """
        O ZIP é um formato de arquivo, não um contrato de confiança.

        Um pacote pode ter vindo de qualquer lugar, e restaurar um caminho
        absoluto ou com `..` escreveria fora da pasta que a pessoa escolheu.
        """
        assert caminho_seguro(tmp_path, malicioso) is None

    def test_caminho_comum_e_aceito(self, tmp_path: Path) -> None:
        alvo = caminho_seguro(tmp_path, "dados/contratos/aditivo.txt")

        assert alvo is not None
        assert tmp_path.resolve() in alvo.parents


class TestRestauracaoBasica:
    def test_reproduz_byte_a_byte(self, origem: Path, tmp_path: Path) -> None:
        """
        O critério que dá sentido ao produto inteiro.

        Tudo o que veio antes existe para que este passo funcione no pior dia
        possível, quando o original já não existe.
        """
        original = (origem / "planilha.bin").read_bytes()
        pacote = _empacotar(origem, tmp_path / "p1.zip")
        destino = tmp_path / "restaurado"

        relatorio = restaurar(pacote, destino)

        assert relatorio.completa is True
        assert len(relatorio.restaurados) == 3
        assert (destino / "dados" / "planilha.bin").read_bytes() == original
        assert (destino / "dados" / "contrato.txt").read_text(
            encoding="utf-8"
        ) == "contrato importante"

    def test_preserva_a_estrutura_de_pastas(self, origem: Path, tmp_path: Path) -> None:
        pacote = _empacotar(origem, tmp_path / "p1.zip")
        destino = tmp_path / "restaurado"

        restaurar(pacote, destino)

        assert (destino / "dados" / "contratos" / "aditivo.txt").is_file()

    def test_restauracao_de_amostra(self, origem: Path, tmp_path: Path) -> None:
        """
        É como se testa um backup sem mexer no que está em produção.

        Restaurar tudo por cima para "conferir" é o tipo de teste que causa o
        incidente que deveria prevenir.
        """
        pacote = _empacotar(origem, tmp_path / "p1.zip")
        destino = tmp_path / "amostra"

        relatorio = restaurar(pacote, destino, apenas=["dados/contrato.txt"])

        assert relatorio.restaurados == ["dados/contrato.txt"]
        assert not (destino / "dados" / "planilha.bin").exists()

    def test_o_manifesto_nao_e_restaurado_como_arquivo(self, origem: Path, tmp_path: Path) -> None:
        """Manifesto e assinatura são metadados do pacote, não conteúdo."""
        pacote = _empacotar(origem, tmp_path / "p1.zip")
        destino = tmp_path / "restaurado"

        restaurar(pacote, destino)

        assert not (destino / "MANIFESTO.csv").exists()


class TestNaoSobrescrever:
    def test_por_padrao_preserva_o_que_existe(self, origem: Path, tmp_path: Path) -> None:
        """
        Restaurar por cima é decisão de quem está ali, não do programa.

        O padrão preserva — e diz o que preservou.
        """
        pacote = _empacotar(origem, tmp_path / "p1.zip")
        destino = tmp_path / "restaurado"
        (destino / "dados").mkdir(parents=True)
        (destino / "dados" / "contrato.txt").write_text("VERSAO ATUAL", encoding="utf-8")

        relatorio = restaurar(pacote, destino)

        assert "dados/contrato.txt" in relatorio.ja_existiam
        assert (destino / "dados" / "contrato.txt").read_text(encoding="utf-8") == "VERSAO ATUAL"

    def test_preservar_nao_conta_como_restauracao_incompleta(
        self, origem: Path, tmp_path: Path
    ) -> None:
        """Preservar foi a escolha de quem pediu; não é falha."""
        pacote = _empacotar(origem, tmp_path / "p1.zip")
        destino = tmp_path / "restaurado"
        (destino / "dados").mkdir(parents=True)
        (destino / "dados" / "contrato.txt").write_text("ATUAL", encoding="utf-8")

        assert restaurar(pacote, destino).completa is True

    def test_com_permissao_explicita_sobrescreve(self, origem: Path, tmp_path: Path) -> None:
        pacote = _empacotar(origem, tmp_path / "p1.zip")
        destino = tmp_path / "restaurado"
        (destino / "dados").mkdir(parents=True)
        (destino / "dados" / "contrato.txt").write_text("ATUAL", encoding="utf-8")

        relatorio = restaurar(pacote, destino, sobrescrever=True)

        assert "dados/contrato.txt" in relatorio.restaurados
        assert (destino / "dados" / "contrato.txt").read_text(
            encoding="utf-8"
        ) == "contrato importante"


class TestPacoteRuim:
    def test_pacote_corrompido_e_recusado_inteiro(self, origem: Path, tmp_path: Path) -> None:
        """
        Restauração parcial silenciosa é pior do que nenhuma: a pessoa acha
        que recuperou tudo.
        """
        pacote = _empacotar(origem, tmp_path / "p1.zip")

        # O conteudo esta comprimido: para simular a corrupcao de verdade, o
        # pacote e reescrito com um arquivo diferente e o manifesto ORIGINAL.
        # E assim que um disco com defeito se manifesta — o hash deixa de
        # bater com o que o manifesto declarou.
        with zipfile.ZipFile(pacote) as zf:
            itens = {nome: zf.read(nome) for nome in zf.namelist()}
        itens["dados/contrato.txt"] = b"conteudo estragado"
        with zipfile.ZipFile(pacote, "w", zipfile.ZIP_DEFLATED) as zf:
            for nome, dados in itens.items():
                zf.writestr(nome, dados)

        with pytest.raises(RestauracaoRecusada, match="nao confere"):
            restaurar(pacote, tmp_path / "restaurado")

    def test_pacote_adulterado_e_recusado(
        self, origem: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Assinatura que não confere impede a restauração.

        Recuperar de um pacote que alguém alterou seria recuperar o que o
        atacante quis, com a confiança de um backup.
        """
        monkeypatch.setenv(assinatura.VAR_CHAVE, assinatura.gerar_chave())
        pacote = _empacotar(origem, tmp_path / "p1.zip")

        monkeypatch.setenv(assinatura.VAR_CHAVE, assinatura.gerar_chave())

        with pytest.raises(RestauracaoRecusada, match="nao confere"):
            restaurar(pacote, tmp_path / "restaurado")

    def test_pacote_inexistente_diz_isso(self, tmp_path: Path) -> None:
        with pytest.raises(RestauracaoRecusada, match="nao encontrado"):
            restaurar(tmp_path / "nunca-existiu.zip", tmp_path / "destino")

    def test_caminho_malicioso_no_pacote_e_recusado_e_registrado(self, tmp_path: Path) -> None:
        """
        Um pacote com caminho malicioso é informação sobre a origem dele.

        Engolir em silêncio esconderia justamente o que precisa ser visto.
        """
        # Monta um pacote a mão, com manifesto declarando um caminho que
        # tenta escapar: um pacote gerado por outra ferramenta poderia.
        pacote = tmp_path / "suspeito.zip"
        manifesto = (
            "# backup,autotarefas\n"
            "\n"
            "situacao,arquivo,bytes,modificado_em,sha256,motivo\n"
            "incluido,../fora.txt,5,,{sha},\n"
        ).format(sha=__import__("hashlib").sha256(b"dados").hexdigest())
        with zipfile.ZipFile(pacote, "w") as zf:
            zf.writestr("../fora.txt", b"dados")
            zf.writestr("MANIFESTO.csv", manifesto)

        relatorio = restaurar(pacote, tmp_path / "restaurado")

        assert relatorio.recusados == ["../fora.txt"]
        assert relatorio.completa is False
        assert not (tmp_path / "fora.txt").exists()


class TestIncremental:
    def test_restaura_seguindo_a_corrente(self, origem: Path, tmp_path: Path) -> None:
        catalogo = Catalogo(tmp_path / "pacotes" / NOME)
        primeiro = _empacotar(origem, tmp_path / "pacotes" / "p1.zip", catalogo)
        (origem / "novo.txt").write_text("arquivo novo", encoding="utf-8")
        segundo = _empacotar(origem, tmp_path / "pacotes" / "p2.zip", catalogo)
        destino = tmp_path / "restaurado"

        relatorio = restaurar(segundo, destino, anteriores=[primeiro])

        assert relatorio.completa is True
        assert (destino / "dados" / "contrato.txt").read_text(
            encoding="utf-8"
        ) == "contrato importante"
        assert (destino / "dados" / "novo.txt").read_text(encoding="utf-8") == "arquivo novo"

    def test_sem_a_corrente_diz_o_que_falta(self, origem: Path, tmp_path: Path) -> None:
        """
        Restaurar pela metade e chamar de sucesso é a pior forma de falhar
        aqui.

        A mensagem nomeia o pacote que a pessoa precisa procurar.
        """
        catalogo = Catalogo(tmp_path / "pacotes" / NOME)
        _empacotar(origem, tmp_path / "pacotes" / "p1.zip", catalogo)
        (origem / "novo.txt").write_text("arquivo novo", encoding="utf-8")
        segundo = _empacotar(origem, tmp_path / "pacotes" / "p2.zip", catalogo)

        relatorio = restaurar(segundo, tmp_path / "restaurado")

        assert relatorio.completa is False
        assert len(relatorio.faltando) == 3
        assert any("p1.zip" in item for item in relatorio.faltando)


class TestListagem:
    def test_lista_o_que_ha_no_pacote(self, origem: Path, tmp_path: Path) -> None:
        """
        Escolher o que restaurar sem ver a lista seria escolher às cegas.

        E restauração às cegas costuma sobrescrever o que não devia.
        """
        pacote = _empacotar(origem, tmp_path / "p1.zip")

        conteudo = listar_conteudo(pacote)

        nomes = {item["arquivo"] for item in conteudo}
        assert "dados/contrato.txt" in nomes
        assert "MANIFESTO.csv" not in nomes

    def test_a_listagem_diz_em_qual_pacote_cada_arquivo_esta(
        self, origem: Path, tmp_path: Path
    ) -> None:
        catalogo = Catalogo(tmp_path / "pacotes" / NOME)
        _empacotar(origem, tmp_path / "pacotes" / "p1.zip", catalogo)
        (origem / "novo.txt").write_text("novo", encoding="utf-8")
        segundo = _empacotar(origem, tmp_path / "pacotes" / "p2.zip", catalogo)

        conteudo = {item["arquivo"]: item for item in listar_conteudo(segundo)}

        assert conteudo["dados/novo.txt"]["neste_pacote"] == "sim"
        assert conteudo["dados/contrato.txt"]["onde"] == "p1.zip"


class TestPacoteCifrado:
    def test_restaura_pacote_cifrado_com_a_senha(
        self, origem: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from autotarefas.tasks import cifra

        monkeypatch.setenv(cifra.VAR_SENHA, "senha-de-teste-bem-longa")
        pacote = _empacotar(origem, tmp_path / "p1.zip")
        destino = tmp_path / "restaurado"

        relatorio = restaurar(pacote, destino)

        assert relatorio.completa is True
        assert (destino / "dados" / "contrato.txt").is_file()

    def test_sem_a_senha_recusa_com_instrucao(
        self, origem: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from autotarefas.tasks import cifra

        monkeypatch.setenv(cifra.VAR_SENHA, "senha-de-teste-bem-longa")
        pacote = _empacotar(origem, tmp_path / "p1.zip")

        monkeypatch.delenv(cifra.VAR_SENHA, raising=False)

        with pytest.raises(RestauracaoRecusada, match="cifrado"):
            restaurar(pacote, tmp_path / "restaurado")
