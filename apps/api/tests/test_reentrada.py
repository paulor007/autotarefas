"""Reentrada pelo console, num servidor sem provedor (G.2.4).

Encontrado na primeira homologacao manual: a sessao venceu em 12 horas e, sem
OIDC configurado, nao havia como entrar de novo. O dono ficou trancado do lado
de fora dos proprios dados — que continuavam la dentro.

Isto e codigo de autenticacao, entao o que interessa e o que ele **recusa**. Os
tres testes que sustentam o resto:

- `test_com_provedor_configurado_nao_ha_chave` — a porta so existe onde nao ha
  fechadura. Mante-la aberta ao lado do OIDC seria acrescentar uma entrada que
  ninguem vigia;
- `test_a_chave_serve_uma_vez_so` — link em log, em historico de terminal, em
  print de tela: um token reutilizavel viraria credencial permanente;
- `test_link_de_outro_token_nao_entra` — a comparacao e em tempo constante, e a
  recusa e a mesma para token errado e para token vencido.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest

from apps.api.app.config import settings
from apps.api.app.db import repositorio as repo
from apps.api.app.db.models import Papel
from apps.api.app.db.sessao import Banco
from apps.api.app.identidade import reentrada

AGORA = 1_700_000_000.0


@pytest.fixture
def banco() -> Iterator[Banco]:
    instancia = Banco("sqlite:///:memory:")
    instancia.criar_esquema()
    reentrada.descartar()
    yield instancia
    reentrada.descartar()
    instancia.descartar()


def _organizacao(banco: Banco, nome: str = "Padaria", papel: Papel = Papel.DONO) -> str:
    with banco.sessao() as sessao:
        organizacao = repo.criar_organizacao(sessao, nome=nome, dominio=f"{nome.lower()}.com.br")
        usuario = repo.criar_usuario(
            sessao,
            email=f"dono@{nome.lower()}.com.br",
            nome="Dono",
            emissor="bootstrap",
            assunto=nome,
        )
        repo.vincular(sessao, organizacao=organizacao, usuario=usuario, papel=papel)
        return usuario.id


def _ajustar(**valores: object) -> dict[str, object]:
    """
    Troca campos do `settings`, que e um dataclass congelado.

    `monkeypatch.setattr` nao serve: congelado levanta na atribuicao. Varios
    modulos guardam a MESMA instancia, entao mexer nela e o unico jeito de a
    troca valer em todos — e por isso o valor antigo volta para ser restaurado.
    """
    anteriores = {nome: getattr(settings, nome) for nome in valores}
    for nome, valor in valores.items():
        object.__setattr__(settings, nome, valor)
    return anteriores


@pytest.fixture
def sem_provedor() -> Iterator[None]:
    anteriores = _ajustar(oidc_issuer="", oidc_client_id="")
    yield
    _ajustar(**anteriores)


@pytest.fixture
def com_provedor() -> Iterator[None]:
    anteriores = _ajustar(oidc_issuer="https://provedor", oidc_client_id="cliente")
    yield
    _ajustar(**anteriores)


class TestQuandoAChaveExiste:
    def test_com_provedor_configurado_nao_ha_chave(self, banco: Banco, com_provedor: None) -> None:
        """
        A porta so existe onde nao ha fechadura.

        Com OIDC no ar, o caminho e o provedor. Manter as duas abertas seria
        manter uma entrada que ninguem vigia ao lado de uma com fechadura.
        """
        del com_provedor
        _organizacao(banco)

        with banco.sessao() as sessao:
            assert reentrada.emitir(sessao, agora_s=AGORA) is None

    def test_sem_dono_cadastrado_nao_ha_para_quem_emitir(
        self, banco: Banco, sem_provedor: None
    ) -> None:
        """Banco vazio e caso do primeiro acesso, e nao desta porta."""
        del sem_provedor

        with banco.sessao() as sessao:
            assert reentrada.emitir(sessao, agora_s=AGORA) is None

    def test_emite_para_o_dono(self, banco: Banco, sem_provedor: None) -> None:
        del sem_provedor
        usuario_id = _organizacao(banco)

        with banco.sessao() as sessao:
            chave = reentrada.emitir(sessao, agora_s=AGORA)

        assert chave is not None
        assert chave.usuario_id == usuario_id
        assert chave.email == "dono@padaria.com.br"
        assert len(chave.token) > 30

    def test_operador_nao_ganha_chave(self, banco: Banco, sem_provedor: None) -> None:
        """
        A chave e do dono, e nao de quem por acaso tem conta.

        Quem opera pode executar backup; quem tem o console e dono do servico.
        Confundir os dois daria o servidor inteiro a um papel menor.
        """
        del sem_provedor
        _organizacao(banco, papel=Papel.OPERADOR)

        with banco.sessao() as sessao:
            assert reentrada.emitir(sessao, agora_s=AGORA) is None

    def test_com_dois_donos_vale_o_mais_antigo(self, banco: Banco, sem_provedor: None) -> None:
        """
        Quem criou a primeira organizacao e quem tem o console na mao.

        Sortear entre donos daria a chave a quem aparecesse primeiro numa
        consulta sem ordem — o que muda entre bancos e entre versoes.
        """
        del sem_provedor
        primeiro = _organizacao(banco, "Padaria")
        _organizacao(banco, "Farmacia")

        with banco.sessao() as sessao:
            chave = reentrada.emitir(sessao, agora_s=AGORA)

        assert chave is not None
        assert chave.usuario_id == primeiro


class TestOQueARecusa:
    @pytest.fixture(autouse=True)
    def _com_chave(self, banco: Banco, sem_provedor: None) -> None:
        del sem_provedor
        _organizacao(banco)
        with banco.sessao() as sessao:
            reentrada.emitir(sessao, agora_s=AGORA)

    def test_a_chave_serve_uma_vez_so(self) -> None:
        """
        Link em log, em historico de terminal, em print de tela.

        Um token reutilizavel viraria credencial permanente na primeira vez que
        alguem copiasse a linha do console para pedir ajuda.
        """
        chave = reentrada.chave_atual()
        assert chave is not None

        reentrada.usar(chave.token, agora_s=AGORA)

        with pytest.raises(reentrada.ReentradaIndisponivel, match="ja foi usado"):
            reentrada.usar(chave.token, agora_s=AGORA)

    def test_link_vencido_nao_entra(self) -> None:
        chave = reentrada.chave_atual()
        assert chave is not None
        depois = AGORA + settings.bootstrap_minutes * 60 + 1

        with pytest.raises(reentrada.ReentradaIndisponivel, match="venceu"):
            reentrada.usar(chave.token, agora_s=depois)

    def test_link_de_outro_token_nao_entra(self) -> None:
        with pytest.raises(reentrada.ReentradaIndisponivel, match="invalido"):
            reentrada.usar("token-inventado", agora_s=AGORA)

    def test_token_vazio_nao_entra(self) -> None:
        with pytest.raises(reentrada.ReentradaIndisponivel):
            reentrada.usar("", agora_s=AGORA)

    def test_sem_chave_em_vigor_nao_entra(self) -> None:
        reentrada.descartar()

        with pytest.raises(reentrada.ReentradaIndisponivel, match="nao ha link"):
            reentrada.usar("qualquer", agora_s=AGORA)


class TestALinhaDoConsole:
    def test_diz_por_que_o_link_existe(self, banco: Banco, sem_provedor: None) -> None:
        """
        Quem le a linha precisa entender que ela e a unica entrada.

        Um link solto no console, sem explicacao, parece coisa de depuracao — e
        alguem apagaria o terminal sem usar.
        """
        del sem_provedor
        _organizacao(banco)
        with banco.sessao() as sessao:
            chave = reentrada.emitir(sessao, agora_s=AGORA)
        assert chave is not None

        linha = reentrada.linha_do_console(chave, "http://localhost:8000")

        assert "http://localhost:8000/api/auth/reentrar?chave=" in linha
        assert "unico jeito de entrar" in linha
        assert "uma vez so" in linha
        assert chave.email in linha

    def test_a_linha_e_so_ascii(self, banco: Banco, sem_provedor: None) -> None:
        """
        O console do Windows abre em cp1252.

        Um tracinho de caixa derruba o `print` com `UnicodeEncodeError`, e o
        servico morre na partida — na maquina do cliente, por causa de uma
        moldura.
        """
        del sem_provedor
        _organizacao(banco)
        with banco.sessao() as sessao:
            chave = reentrada.emitir(sessao, agora_s=AGORA)
        assert chave is not None

        linha = reentrada.linha_do_console(chave, "http://localhost:8000")

        linha.encode("ascii")  # levanta se houver acento ou moldura


def test_o_relogio_usado_e_o_de_verdade() -> None:
    """
    Guarda contra um teste que passe por congelar o tempo.

    `time.time()` cresce; se algum dia a validade for calculada com um relogio
    parado, o link nunca venceria.
    """
    assert time.time() > AGORA - 10_000_000_000
