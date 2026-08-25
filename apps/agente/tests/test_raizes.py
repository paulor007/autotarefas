"""Testes das pastas autorizadas (G.5.1).

Esta e a fronteira entre o Live e o disco do cliente, e os testes que importam
sao os de recusa:

- `test_caminho_com_dois_pontos_nao_escapa` — sem resolver o caminho antes de
  comparar, `pasta-autorizada\\..\\..\\Windows` passaria pela verificacao;
- `test_disco_inteiro_e_recusado` e `test_pasta_do_sistema_e_recusada` —
  autorizar um volume inteiro coloca o sistema operacional no pacote;
- `test_nada_e_autorizado_por_padrao` — o estado inicial e nao ter acesso a
  nada.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from apps.agente.agente import raizes
from apps.agente.agente.config import Configuracao, Local


@pytest.fixture
def local(tmp_path: Path) -> Local:
    return Local(pasta=tmp_path / "config")


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    alvo = tmp_path / "dados"
    alvo.mkdir()
    (alvo / "contrato.txt").write_text("conteudo", encoding="utf-8")
    return alvo


class TestConferencia:
    def test_pasta_comum_e_aceita(self, pasta: Path) -> None:
        assert raizes.conferir(pasta) == pasta.resolve()

    def test_pasta_inexistente_e_recusada(self, tmp_path: Path) -> None:
        """
        Validar na hora de autorizar, e nao na hora de executar.

        Uma pasta invalida guardada na configuracao so daria erro na primeira
        execucao do backup — de madrugada, sem ninguem por perto.
        """
        with pytest.raises(raizes.AutorizacaoRecusada, match="nao existe"):
            raizes.conferir(tmp_path / "nunca-existiu")

    def test_arquivo_nao_e_pasta(self, pasta: Path) -> None:
        with pytest.raises(raizes.AutorizacaoRecusada, match="nao e uma pasta"):
            raizes.conferir(pasta / "contrato.txt")

    def test_disco_inteiro_e_recusado(self) -> None:
        """
        Autorizar o volume inteiro coloca o sistema operacional no pacote.

        Lento, inutil como backup e perigoso se o pacote vazar.
        """
        raiz = Path(Path.cwd().anchor)
        with pytest.raises(raizes.AutorizacaoRecusada, match="disco inteiro"):
            raizes.conferir(raiz)

    @pytest.mark.skipif(os.name != "nt", reason="pastas do Windows")
    def test_pasta_do_sistema_e_recusada(self) -> None:
        """
        A lista vem do ambiente, e nao fixa no codigo.

        A letra do disco e o idioma das pastas do Windows mudam de maquina
        para maquina; uma lista fixa erraria na primeira instalacao em outro
        idioma.
        """
        sistema = os.environ.get("SYSTEMROOT") or r"C:\Windows"
        with pytest.raises(raizes.AutorizacaoRecusada, match="do sistema"):
            raizes.conferir(Path(sistema))

    @pytest.mark.skipif(os.name != "nt", reason="pastas do Windows")
    def test_subpasta_do_sistema_tambem_e_recusada(self) -> None:
        sistema = Path(os.environ.get("SYSTEMROOT") or r"C:\Windows")
        alvo = sistema / "System32"
        if not alvo.is_dir():
            pytest.skip("System32 nao encontrada")
        with pytest.raises(raizes.AutorizacaoRecusada, match="do sistema"):
            raizes.conferir(alvo)


class TestAutorizar:
    def test_autorizar_grava_o_caminho_resolvido(self, local: Local, pasta: Path) -> None:
        configuracao = raizes.autorizar(local, pasta / ".." / "dados")

        assert configuracao.raizes == (str(pasta.resolve()),)
        assert local.carregar().raizes == (str(pasta.resolve()),)

    def test_autorizar_duas_vezes_nao_duplica(self, local: Local, pasta: Path) -> None:
        raizes.autorizar(local, pasta)
        configuracao = raizes.autorizar(local, pasta)

        assert len(configuracao.raizes) == 1

    def test_revogar_funciona_mesmo_com_a_pasta_apagada(self, local: Local, pasta: Path) -> None:
        """
        Senao a configuracao acumula entradas mortas que ninguem remove.
        """
        raizes.autorizar(local, pasta)
        alvo = pasta.resolve()
        (pasta / "contrato.txt").unlink()
        pasta.rmdir()

        configuracao = raizes.revogar(local, alvo)

        assert configuracao.raizes == ()


class TestGuarda:
    def test_nada_e_autorizado_por_padrao(self, tmp_path: Path) -> None:
        """
        O estado inicial e nao ter acesso a nada.

        Qualquer padrao diferente seria conceder acesso ao disco sem ninguem
        ter dito sim.
        """
        assert raizes.autorizado(Configuracao(), tmp_path) is False

    def test_arquivo_dentro_da_pasta_autorizada_passa(self, local: Local, pasta: Path) -> None:
        configuracao = raizes.autorizar(local, pasta)

        assert raizes.autorizado(configuracao, pasta / "contrato.txt") is True
        assert raizes.exigir_autorizacao(configuracao, pasta / "contrato.txt")

    def test_subpasta_tambem_passa(self, local: Local, pasta: Path) -> None:
        (pasta / "notas").mkdir()
        configuracao = raizes.autorizar(local, pasta)

        assert raizes.autorizado(configuracao, pasta / "notas" / "nf.pdf") is True

    def test_irma_da_pasta_autorizada_nao_passa(
        self, local: Local, pasta: Path, tmp_path: Path
    ) -> None:
        """
        Autorizar `dados` nao autoriza `dados-secretos`.

        Comparar por texto, sem olhar a fronteira de pasta, cometeria esse
        erro — e ele e silencioso.
        """
        irma = tmp_path / "dados-secretos"
        irma.mkdir()
        configuracao = raizes.autorizar(local, pasta)

        assert raizes.autorizado(configuracao, irma / "segredo.txt") is False

    def test_caminho_com_dois_pontos_nao_escapa(
        self, local: Local, pasta: Path, tmp_path: Path
    ) -> None:
        """
        O teste que justifica resolver o caminho antes de comparar.

        `pasta-autorizada\\..\\outro` comeca com a pasta autorizada em texto,
        mas aponta para fora dela.
        """
        fora = tmp_path / "fora"
        fora.mkdir()
        (fora / "alheio.txt").write_text("de outra pessoa", encoding="utf-8")
        configuracao = raizes.autorizar(local, pasta)

        escapando = pasta / ".." / "fora" / "alheio.txt"

        assert raizes.autorizado(configuracao, escapando) is False
        with pytest.raises(raizes.AutorizacaoRecusada, match="nao esta em nenhuma"):
            raizes.exigir_autorizacao(configuracao, escapando)

    def test_a_mensagem_diz_onde_autorizar(self, local: Local, pasta: Path) -> None:
        """
        Quem le o erro precisa saber o que fazer — e onde.

        "Autorize pelo Agente, no proprio computador" e a diferenca entre um
        erro util e um chamado de suporte.
        """
        configuracao = raizes.autorizar(local, pasta)
        with pytest.raises(raizes.AutorizacaoRecusada, match="no proprio computador"):
            raizes.exigir_autorizacao(configuracao, Path.home())

    def test_falha_fechada_em_caminho_impossivel(self, local: Local, pasta: Path) -> None:
        """Na duvida, recusa. Permitir "porque provavelmente esta ok" e nao ter guarda."""
        configuracao = raizes.autorizar(local, pasta)

        assert raizes.autorizado(configuracao, Path("Z:\\") / "nao-existe") is False


class TestConsentimentoEhLocal:
    def test_nao_ha_funcao_que_autorize_sem_a_maquina(self) -> None:
        """
        Guarda de arquitetura, nao de comportamento.

        `autorizar` recebe o `Local` — o disco desta maquina. Nao existe
        variante que aceite um pedido do servidor, e essa ausencia e o modelo
        de seguranca inteiro. Se alguem acrescentar uma, este teste cai e
        obriga a conversa.
        """
        import inspect

        assinatura = inspect.signature(raizes.autorizar)

        # A anotacao chega como texto por causa de `from __future__ import
        # annotations`; o que importa e que o primeiro parametro seja o disco
        # desta maquina.
        assert list(assinatura.parameters) == ["local", "caminho"]
        assert assinatura.parameters["local"].annotation == "Local"

    def test_o_executor_de_comandos_nao_conhece_autorizar(self) -> None:
        """
        Nenhuma acao remota registrada pode autorizar pasta.

        Se um dia alguem registrar, este teste cai antes de o produto sair.
        """
        from apps.agente.agente import comandos

        registro = comandos.registro_padrao()

        assert "autorizar" not in registro.conhecidas()
        assert "autorizar_pasta" not in registro.conhecidas()
