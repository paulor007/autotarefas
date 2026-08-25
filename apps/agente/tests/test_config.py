"""Testes da configuracao local do Agente (G.3.1).

Duas coisas sao verificadas com mais cuidado, porque as duas ja causaram
estrago em produtos parecidos:

- **segredo na configuracao** — o arquivo tem que ser inofensivo se vazar;
- **caminho nao resolvido** — `..\\..\\Windows` gravado como veio autorizaria,
  na pratica, um lugar diferente do que a pessoa viu ao consentir.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.agente.agente.config import Configuracao, Local


@pytest.fixture
def local(tmp_path: Path) -> Local:
    return Local(pasta=tmp_path / "config")


class TestIdaEVolta:
    def test_grava_e_le(self, local: Local) -> None:
        original = Configuracao(
            servidor="https://live.exemplo.com.br",
            dispositivo_id="disp-1",
            nome="PC da loja",
            pareado_em="2026-08-25T10:00:00+00:00",
        )
        local.gravar(original)

        lida = local.carregar()

        assert lida.servidor == original.servidor
        assert lida.dispositivo_id == original.dispositivo_id
        assert lida.nome == original.nome
        assert lida.pareado is True

    def test_sem_arquivo_nasce_vazio_e_nao_pareado(self, local: Local) -> None:
        vazia = local.carregar()

        assert vazia.pareado is False
        assert vazia.raizes == ()

    def test_arquivo_corrompido_nao_derruba_o_agente(self, local: Local) -> None:
        """
        JSON quebrado nao pode impedir o servico de subir.

        Servico que nao sobe e backup que nao acontece. Vazio significa "nao
        pareado", que o Agente sabe tratar e mostrar.
        """
        local.pasta.mkdir(parents=True)
        local.arquivo.write_text("{isto nao e json", encoding="utf-8")

        assert local.carregar().pareado is False

    def test_gravacao_e_atomica(self, local: Local) -> None:
        """
        Nao pode sobrar arquivo pela metade nem `.parcial` esquecido.

        Configuracao truncada, no pior caso, significaria um dispositivo sem
        pastas autorizadas — um backup que copia nada, em silencio.
        """
        local.gravar(Configuracao(servidor="https://x", dispositivo_id="d"))

        assert local.arquivo.is_file()
        assert not local.arquivo.with_suffix(".parcial").exists()
        assert json.loads(local.arquivo.read_text(encoding="utf-8"))["dispositivo_id"] == "d"


class TestSegredo:
    def test_configuracao_nao_guarda_chave_privada(self, local: Local) -> None:
        """
        O arquivo tem que ser inofensivo se vazar.

        Endereco, id e pastas nao servem para se passar por ninguem. A chave
        privada mora no cofre do sistema, nunca aqui.
        """
        local.gravar(Configuracao(servidor="https://live", dispositivo_id="d", nome="PC"))
        bruto = local.arquivo.read_text(encoding="utf-8").lower()

        for proibido in ("privada", "private", "senha", "password", "token", "secret"):
            assert proibido not in bruto


class TestRaizesAutorizadas:
    def test_nasce_sem_nenhuma_pasta_autorizada(self) -> None:
        """
        O padrao e nao ter acesso a nada.

        Qualquer padrao diferente seria conceder acesso ao disco sem ninguem
        ter dito sim.
        """
        assert Configuracao().raizes == ()

    def test_guarda_o_caminho_resolvido(self, tmp_path: Path) -> None:
        """
        `..` gravado como veio autorizaria outro lugar.

        A pessoa consente com o que ve; o que fica gravado tem que ser o mesmo
        lugar.
        """
        alvo = tmp_path / "dados"
        alvo.mkdir()
        torto = tmp_path / "dados" / ".." / "dados"

        configuracao = Configuracao().com_raiz(torto)

        assert configuracao.raizes == (str(alvo.resolve()),)

    def test_autorizar_duas_vezes_nao_duplica(self, tmp_path: Path) -> None:
        alvo = tmp_path / "dados"
        alvo.mkdir()

        configuracao = Configuracao().com_raiz(alvo).com_raiz(alvo)

        assert len(configuracao.raizes) == 1

    def test_revogar_remove(self, tmp_path: Path) -> None:
        alvo = tmp_path / "dados"
        alvo.mkdir()

        configuracao = Configuracao().com_raiz(alvo).sem_raiz(alvo)

        assert configuracao.raizes == ()

    def test_raizes_sobrevivem_a_gravacao(self, local: Local, tmp_path: Path) -> None:
        alvo = tmp_path / "dados"
        alvo.mkdir()
        local.gravar(Configuracao(servidor="https://x", dispositivo_id="d").com_raiz(alvo))

        assert local.carregar().raizes == (str(alvo.resolve()),)

    def test_configuracao_e_imutavel(self, tmp_path: Path) -> None:
        """
        Autorizar devolve outra configuracao, nao muda a que existia.

        Mutar no lugar deixaria um caminho em que a pasta aparece autorizada
        antes de a gravacao confirmar — e, se a gravacao falhasse, o Agente
        ficaria lendo uma pasta que nunca foi salva como autorizada.
        """
        alvo = tmp_path / "dados"
        alvo.mkdir()
        original = Configuracao()

        nova = original.com_raiz(alvo)

        assert original.raizes == ()
        assert nova.raizes != ()
