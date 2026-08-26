"""Testes de identidade: bootstrap, OIDC, sessao e guarda de organizacao.

O login e a porta da plataforma inteira. Cada protecao do fluxo — state,
nonce, PKCE, assinatura, audiencia, validade — tem um teste que tenta passar
sem ela. Um fluxo OIDC "que funciona" e facil; o que separa dele um fluxo
seguro sao exatamente as recusas.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from apps.api.app.config import settings
from apps.api.app.db import repositorio as repo
from apps.api.app.db.atual import definir_banco
from apps.api.app.db.models import Papel
from apps.api.app.db.sessao import Banco
from apps.api.app.identidade import bootstrap, oidc
from apps.api.app.identidade import rotas as rotas_identidade
from apps.api.app.identidade.entrada import EMISSOR_BOOTSTRAP, acolher
from apps.api.app.identidade.oidc import ErroDeIdentidade, Identidade
from apps.api.app.identidade.sessao_web import COOKIE_SESSAO, ler_sessao
from apps.api.app.main import app
from apps.api.tests.provedor_de_teste import ProvedorDeTeste

HTTP_OK = 200
HTTP_REDIRECT = 307
HTTP_SEE_OTHER = 303
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_CONFLICT = 409


def _ajustar(**valores: Any) -> dict[str, Any]:
    """
    Troca campos do `settings`, que e um dataclass congelado.

    `monkeypatch.setattr` nao serve: congelado levanta na atribuicao. Como
    varios modulos guardam a MESMA instancia, mexer nela e o unico jeito de
    a troca valer em todos — e por isso o valor antigo e devolvido para ser
    restaurado no fim.
    """
    anteriores = {nome: getattr(settings, nome) for nome in valores}
    for nome, valor in valores.items():
        object.__setattr__(settings, nome, valor)
    return anteriores


@pytest.fixture
def banco_limpo() -> Iterator[Banco]:
    """Banco vazio por teste, ligado ao servico e desligado no fim."""
    instancia = Banco("sqlite:///:memory:")
    instancia.criar_esquema()
    definir_banco(instancia)
    bootstrap.descartar()
    yield instancia
    definir_banco(None)
    bootstrap.descartar()


@pytest.fixture
def cliente(banco_limpo: Banco) -> Iterator[TestClient]:
    """Cliente do Live sem provedor OIDC configurado."""
    del banco_limpo
    anteriores = _ajustar(
        oidc_issuer="", oidc_client_id="", oidc_client_secret="", session_secret="segredo-de-teste"
    )
    with TestClient(app) as testador:
        yield testador
    _ajustar(**anteriores)


@pytest.fixture
def provedor() -> Iterator[ProvedorDeTeste]:
    """
    Provedor OIDC de teste ligado ao backend por transporte ASGI.

    Sem rede: o cliente HTTP do backend entrega direto ao aplicativo do
    provedor. O protocolo, porem, e o de verdade — assinatura, JWKS e PKCE
    conferidos.
    """
    falso = ProvedorDeTeste()
    anterior = rotas_identidade.cliente_http
    # `TestClient` e um `httpx.Client` com transporte sincrono sobre ASGI.
    # `httpx.ASGITransport` sozinho so atende em modo assincrono, e o cliente
    # do backend e sincrono.
    rotas_identidade.cliente_http = TestClient(falso.app, base_url=falso.emissor)
    anteriores = _ajustar(
        oidc_issuer=falso.emissor,
        oidc_client_id=falso.client_id,
        oidc_client_secret="segredo-do-cliente",  # pragma: allowlist secret
        session_secret="segredo-de-teste",  # pragma: allowlist secret
        public_base_url="http://live.teste",
    )
    yield falso
    if rotas_identidade.cliente_http is not None:
        rotas_identidade.cliente_http.close()
    rotas_identidade.cliente_http = anterior
    _ajustar(**anteriores)


def _iniciar_login(testador: TestClient) -> tuple[str, str, str]:
    """Chama /entrar e devolve (state, nonce, desafio) do endereco de ida."""
    resposta = testador.get("/api/auth/entrar", follow_redirects=False)
    assert resposta.status_code == HTTP_REDIRECT, resposta.text
    consulta = parse_qs(urlparse(resposta.headers["location"]).query)
    return consulta["state"][0], consulta["nonce"][0], consulta["code_challenge"][0]


# ============================================================
# Primeira execucao
# ============================================================


class TestBootstrap:
    def test_banco_vazio_pede_bootstrap_e_nao_oferece_provedor(self, cliente: TestClient) -> None:
        """A tela precisa saber a verdade antes de desenhar qualquer botao."""
        corpo = cliente.get("/api/auth/estado").json()

        assert corpo["precisa_bootstrap"] is True
        assert corpo["provedor_configurado"] is False
        assert corpo["autenticado"] is False

    def test_entrar_sem_provedor_configurado_e_recusado(self, cliente: TestClient) -> None:
        """Sem provedor nao ha para onde mandar a pessoa — e isso e dito."""
        assert cliente.get("/api/auth/entrar").status_code == HTTP_CONFLICT

    def test_convite_cria_organizacao_e_dono(self, cliente: TestClient) -> None:
        convite = bootstrap.convite_atual()
        assert convite is not None

        resposta = cliente.post(
            "/api/auth/bootstrap",
            json={
                "convite": convite.token,
                "organizacao": "Padaria Sol",
                "email": "ana@padariasol.com.br",
                "nome": "Ana",
            },
        )

        assert resposta.status_code == HTTP_OK
        estado = cliente.get("/api/auth/estado").json()
        assert estado["autenticado"] is True
        assert estado["organizacao"]["nome"] == "Padaria Sol"
        assert estado["organizacao"]["papel"] == Papel.DONO.value
        assert estado["precisa_bootstrap"] is False

    def test_convite_serve_uma_vez_so(self, cliente: TestClient) -> None:
        convite = bootstrap.convite_atual()
        assert convite is not None
        corpo = {
            "convite": convite.token,
            "organizacao": "Padaria Sol",
            "email": "ana@padariasol.com.br",
            "nome": "Ana",
        }
        assert cliente.post("/api/auth/bootstrap", json=corpo).status_code == HTTP_OK

        segunda = cliente.post("/api/auth/bootstrap", json={**corpo, "organizacao": "Outra"})
        assert segunda.status_code == HTTP_FORBIDDEN

    def test_convite_errado_nao_abre_a_porta(self, cliente: TestClient) -> None:
        resposta = cliente.post(
            "/api/auth/bootstrap",
            json={
                "convite": "chute-do-atacante",
                "organizacao": "Invasora",
                "email": "x@invasor.com",
                "nome": "X",
            },
        )
        assert resposta.status_code == HTTP_FORBIDDEN

    def test_convite_vencido_nao_abre_a_porta(self, banco_limpo: Banco) -> None:
        """
        Prazo curto e o que impede um convite esquecido no log virar porta.
        """
        convite = bootstrap.emitir(agora_s=time.time() - settings.bootstrap_minutes * 60 - 1)
        with banco_limpo.sessao() as sessao, pytest.raises(bootstrap.BootstrapIndisponivel):
            bootstrap.criar_primeira_organizacao(
                sessao,
                token=convite.token,
                nome_organizacao="Tarde demais",
                email="x@y.com.br",
                nome="X",
                agora_s=time.time(),
            )


# ============================================================
# Fluxo OIDC completo
# ============================================================


class TestLoginPeloProvedor:
    def test_login_completo_cria_organizacao_e_sessao(
        self, cliente: TestClient, provedor: ProvedorDeTeste
    ) -> None:
        """O caminho feliz, do zero: sem organizacao, o primeiro entra como dono."""
        _, nonce, desafio = _iniciar_login(cliente)
        codigo = provedor.autorizar(nonce=nonce, desafio=desafio)
        state = _ultimo_state(cliente)

        resposta = cliente.get(
            "/api/auth/retorno",
            params={"code": codigo, "state": state},
            follow_redirects=False,
        )

        assert resposta.status_code == HTTP_SEE_OTHER, resposta.text
        estado = cliente.get("/api/auth/estado").json()
        assert estado["autenticado"] is True
        assert estado["usuario"]["email"] == provedor.email
        assert estado["organizacao"]["papel"] == Papel.DONO.value

    def test_state_trocado_e_recusado(self, cliente: TestClient, provedor: ProvedorDeTeste) -> None:
        """
        Sem conferir o `state`, alguem completa na vitima um login que comecou.
        """
        _, nonce, desafio = _iniciar_login(cliente)
        codigo = provedor.autorizar(nonce=nonce, desafio=desafio)

        resposta = cliente.get(
            "/api/auth/retorno",
            params={"code": codigo, "state": "state-de-outro"},
            follow_redirects=False,
        )

        assert resposta.status_code == HTTP_BAD_REQUEST
        assert cliente.get("/api/auth/estado").json()["autenticado"] is False

    def test_retorno_sem_cookie_de_fluxo_e_recusado(
        self, cliente: TestClient, provedor: ProvedorDeTeste
    ) -> None:
        """Codigo apresentado do nada, sem ter passado pelo /entrar."""
        codigo = provedor.autorizar(nonce="n", desafio="d")
        resposta = cliente.get(
            "/api/auth/retorno",
            params={"code": codigo, "state": "qualquer"},
            follow_redirects=False,
        )
        assert resposta.status_code == HTTP_BAD_REQUEST

    def test_pkce_errado_derruba_a_troca(
        self, cliente: TestClient, provedor: ProvedorDeTeste
    ) -> None:
        """
        Codigo interceptado no retorno nao vale sem o verificador.

        O provedor de teste confere o PKCE de verdade: aqui o desafio
        registrado e de outra tentativa, entao a troca falha.
        """
        _iniciar_login(cliente)
        state = _ultimo_state(cliente)
        codigo = provedor.autorizar(nonce="nonce-qualquer", desafio="desafio-de-outra-tentativa")

        resposta = cliente.get(
            "/api/auth/retorno",
            params={"code": codigo, "state": state},
            follow_redirects=False,
        )
        assert resposta.status_code == HTTP_BAD_REQUEST


# ============================================================
# Conferencia do id_token
# ============================================================


class TestIdToken:
    def _provedor_descoberto(self, provedor: ProvedorDeTeste) -> oidc.Provedor:
        assert rotas_identidade.cliente_http is not None
        return oidc.descobrir(provedor.emissor, cliente=rotas_identidade.cliente_http)

    def test_token_valido_vira_identidade(self, provedor: ProvedorDeTeste) -> None:
        descoberto = self._provedor_descoberto(provedor)
        identidade = oidc.conferir_id_token(
            provedor.assinar(nonce="n1"),
            descoberto,
            client_id=provedor.client_id,
            nonce="n1",
            cliente=rotas_identidade.cliente_http,
        )
        assert identidade.email == provedor.email
        assert identidade.assunto == provedor.assunto

    def test_token_de_outro_cliente_e_recusado(self, provedor: ProvedorDeTeste) -> None:
        """
        Token legitimo, emitido para outro aplicativo, nao vale aqui.

        Sem a conferencia de `aud`, qualquer servico que use o mesmo provedor
        conseguiria trocar o token dele por sessao nossa.
        """
        descoberto = self._provedor_descoberto(provedor)
        with pytest.raises(ErroDeIdentidade, match="outro cliente"):
            oidc.conferir_id_token(
                provedor.assinar(nonce="n1", audiencia="outro-app"),
                descoberto,
                client_id=provedor.client_id,
                nonce="n1",
                cliente=rotas_identidade.cliente_http,
            )

    def test_token_vencido_e_recusado(self, provedor: ProvedorDeTeste) -> None:
        descoberto = self._provedor_descoberto(provedor)
        with pytest.raises(ErroDeIdentidade, match="vencido"):
            oidc.conferir_id_token(
                provedor.assinar(nonce="n1", expira_em=-3600),
                descoberto,
                client_id=provedor.client_id,
                nonce="n1",
                cliente=rotas_identidade.cliente_http,
            )

    def test_nonce_de_outra_tentativa_e_recusado(self, provedor: ProvedorDeTeste) -> None:
        descoberto = self._provedor_descoberto(provedor)
        with pytest.raises(ErroDeIdentidade, match="esta tentativa"):
            oidc.conferir_id_token(
                provedor.assinar(nonce="n-antigo"),
                descoberto,
                client_id=provedor.client_id,
                nonce="n-novo",
                cliente=rotas_identidade.cliente_http,
            )

    def test_token_com_emissor_diferente_e_recusado(self, provedor: ProvedorDeTeste) -> None:
        descoberto = self._provedor_descoberto(provedor)
        with pytest.raises(ErroDeIdentidade, match="outro provedor"):
            oidc.conferir_id_token(
                provedor.assinar(nonce="n1", emissor="http://provedor.falso"),
                descoberto,
                client_id=provedor.client_id,
                nonce="n1",
                cliente=rotas_identidade.cliente_http,
            )

    def test_token_com_assinatura_torta_e_recusado(self, provedor: ProvedorDeTeste) -> None:
        """
        O erro classico: ler o e-mail antes de conferir a assinatura.

        Aqui o token e mexido depois de assinado; se a conferencia sumir,
        qualquer um entra como qualquer pessoa.
        """
        descoberto = self._provedor_descoberto(provedor)
        assinado = provedor.assinar(nonce="n1")
        cabeca, corpo, assinatura = assinado.split(".")
        adulterado = f"{cabeca}.{corpo}.{assinatura[:-4]}AAAA"

        with pytest.raises(ErroDeIdentidade, match="assinatura invalida"):
            oidc.conferir_id_token(
                adulterado,
                descoberto,
                client_id=provedor.client_id,
                nonce="n1",
                cliente=rotas_identidade.cliente_http,
            )


# ============================================================
# Acolhimento: em qual organizacao a pessoa cai
# ============================================================


class TestAcolhimento:
    def _identidade(self, email: str, *, verificado: bool = True, sub: str = "s1") -> Identidade:
        return Identidade(
            emissor="http://provedor.teste",
            assunto=sub,
            email=email,
            nome="Alguem",
            email_verificado=verificado,
        )

    def test_primeiro_de_um_dominio_vira_dono(self, banco_limpo: Banco) -> None:
        with banco_limpo.sessao() as sessao:
            acolhida = acolher(sessao, self._identidade("ana@padariasol.com.br"))
        assert acolhida.papel == Papel.DONO
        assert acolhida.organizacao_nova is True

    def test_segundo_do_mesmo_dominio_entra_como_operador(self, banco_limpo: Banco) -> None:
        """
        Entrar por dominio nao pode dar poder de administrar.

        Caso contrario, bastaria um e-mail do dominio para trocar destino de
        backup e revogar dispositivo.
        """
        with banco_limpo.sessao() as sessao:
            acolher(sessao, self._identidade("ana@padariasol.com.br", sub="s1"))
        with banco_limpo.sessao() as sessao:
            segunda = acolher(sessao, self._identidade("bia@padariasol.com.br", sub="s2"))

        assert segunda.papel == Papel.OPERADOR
        assert segunda.organizacao_nova is False

    def test_dominio_publico_ganha_organizacao_propria(self, banco_limpo: Banco) -> None:
        """Duas pessoas de gmail nao caem na mesma empresa."""
        with banco_limpo.sessao() as sessao:
            uma = acolher(sessao, self._identidade("ana@gmail.com", sub="s1"))
        with banco_limpo.sessao() as sessao:
            outra = acolher(sessao, self._identidade("bia@gmail.com", sub="s2"))

        assert uma.organizacao_id != outra.organizacao_id
        assert uma.papel == Papel.DONO
        assert outra.papel == Papel.DONO

    def test_conta_do_bootstrap_e_adotada_pelo_provedor(self, banco_limpo: Banco) -> None:
        """
        O caso legitimo de casar por e-mail: o dono criou a conta na primeira
        execucao e depois ligou o provedor.
        """
        with banco_limpo.sessao() as sessao:
            organizacao = repo.criar_organizacao(
                sessao, nome="Padaria", dominio="padariasol.com.br"
            )
            usuario = repo.criar_usuario(
                sessao,
                email="ana@padariasol.com.br",
                nome="Ana",
                emissor=EMISSOR_BOOTSTRAP,
                assunto="ana@padariasol.com.br",
            )
            repo.vincular(sessao, organizacao=organizacao, usuario=usuario, papel=Papel.DONO)
            identificador = usuario.id

        with banco_limpo.sessao() as sessao:
            acolhida = acolher(sessao, self._identidade("ana@padariasol.com.br"))

        assert acolhida.usuario_id == identificador
        assert acolhida.papel == Papel.DONO

    def test_email_nao_verificado_nao_toma_conta_existente(self, banco_limpo: Banco) -> None:
        """
        A porta que nao pode existir.

        Um provedor que aceite qualquer e-mail sem verificar entregaria a
        conta do dono a quem digitasse o endereco dele.
        """
        with banco_limpo.sessao() as sessao:
            organizacao = repo.criar_organizacao(
                sessao, nome="Padaria", dominio="padariasol.com.br"
            )
            usuario = repo.criar_usuario(
                sessao,
                email="ana@padariasol.com.br",
                nome="Ana",
                emissor=EMISSOR_BOOTSTRAP,
                assunto="ana@padariasol.com.br",
            )
            repo.vincular(sessao, organizacao=organizacao, usuario=usuario, papel=Papel.DONO)

        with banco_limpo.sessao() as sessao, pytest.raises(ErroDeIdentidade, match="outra origem"):
            acolher(sessao, self._identidade("ana@padariasol.com.br", verificado=False))


# ============================================================
# Sessao
# ============================================================


class TestSessao:
    def test_cookie_adulterado_nao_vale(self, cliente: TestClient) -> None:
        convite = bootstrap.convite_atual()
        assert convite is not None
        cliente.post(
            "/api/auth/bootstrap",
            json={
                "convite": convite.token,
                "organizacao": "Padaria Sol",
                "email": "ana@padariasol.com.br",
                "nome": "Ana",
            },
        )
        original = cliente.cookies.get(COOKIE_SESSAO)
        assert original is not None

        cliente.cookies.set(COOKIE_SESSAO, original[:-3] + "xyz")
        assert cliente.get("/api/auth/estado").json()["autenticado"] is False

    def test_cookie_e_httponly_e_samesite(self, cliente: TestClient) -> None:
        """
        Atributos que fecham roubo por JavaScript e por site de terceiro.
        """
        convite = bootstrap.convite_atual()
        assert convite is not None
        resposta = cliente.post(
            "/api/auth/bootstrap",
            json={
                "convite": convite.token,
                "organizacao": "Padaria Sol",
                "email": "ana@padariasol.com.br",
                "nome": "Ana",
            },
        )
        bruto = resposta.headers["set-cookie"].lower()
        assert "httponly" in bruto
        assert "samesite=lax" in bruto

    def test_sair_apaga_a_sessao(self, cliente: TestClient) -> None:
        convite = bootstrap.convite_atual()
        assert convite is not None
        cliente.post(
            "/api/auth/bootstrap",
            json={
                "convite": convite.token,
                "organizacao": "Padaria Sol",
                "email": "ana@padariasol.com.br",
                "nome": "Ana",
            },
        )
        assert cliente.get("/api/auth/estado").json()["autenticado"] is True

        cliente.post("/api/auth/sair")
        assert cliente.get("/api/auth/estado").json()["autenticado"] is False

    def test_sessao_de_organizacao_que_a_pessoa_deixou_nao_autentica(
        self, cliente: TestClient, banco_limpo: Banco
    ) -> None:
        """
        Vinculo removido tem que derrubar a sessao ja emitida.

        O cookie continua assinado e valido; o que muda e o vinculo. Se a
        conferencia fosse so no cookie, um ex-funcionario continuaria dentro.
        """
        convite = bootstrap.convite_atual()
        assert convite is not None
        cliente.post(
            "/api/auth/bootstrap",
            json={
                "convite": convite.token,
                "organizacao": "Padaria Sol",
                "email": "ana@padariasol.com.br",
                "nome": "Ana",
            },
        )
        dados = ler_sessao(cliente.cookies.get(COOKIE_SESSAO))
        assert dados is not None

        with banco_limpo.sessao() as sessao:
            from apps.api.app.db.models import Usuario

            usuario = sessao.get(Usuario, dados.usuario_id)
            assert usuario is not None
            for vinculo in list(usuario.vinculos):
                sessao.delete(vinculo)

        assert cliente.get("/api/auth/estado").json()["autenticado"] is False


def _ultimo_state(testador: TestClient) -> str:
    """Le o `state` guardado no cookie de fluxo do proprio cliente."""
    from apps.api.app.identidade.sessao_web import COOKIE_FLUXO, ler_fluxo

    fluxo = ler_fluxo(testador.cookies.get(COOKIE_FLUXO))
    assert fluxo is not None
    return fluxo["state"]


class TestEnderecoDoConvite:
    """
    O endereco que o servidor IMPRIME precisa abrir a interface.

    Encontrado na primeira homologacao manual: o console mandava abrir
    `/primeiro-acesso?convite=...` e a resposta era 404. O `StaticFiles` so
    conhece arquivo, e para ele aquele caminho nao existia — entao o cliente
    seguia o proprio link do produto e batia numa porta fechada.

    O teste automatizado nao pegou porque ele montava o endereco por conta
    propria em vez de seguir o que foi impresso. Agora segue.
    """

    def test_o_caminho_do_convite_serve_a_interface(self) -> None:
        from fastapi.testclient import TestClient

        from apps.api.app.main import ROTAS_DA_INTERFACE, _frontend_dist, app

        if not _frontend_dist.is_dir():
            pytest.skip("frontend nao buildado: rode `npm --prefix apps/web run build`")

        # Sem `with`: o `TestClient` como gerenciador de contexto dispara o
        # ciclo de vida da aplicacao, que cria o banco padrao do repositorio e
        # emite convite. Este teste so precisa de um GET num arquivo estatico —
        # e subir a aplicacao inteira aqui contaminava o banco de outros testes.
        cliente = TestClient(app)
        for caminho in ROTAS_DA_INTERFACE:
            resposta = cliente.get(f"{caminho}?convite=qualquer")
            assert resposta.status_code == HTTP_OK, (caminho, resposta.status_code)
            assert "text/html" in resposta.headers["content-type"]

    def test_a_linha_do_console_aponta_para_uma_dessas_rotas(self) -> None:
        """
        A frase impressa e o codigo que serve a rota nao podem divergir.

        Se um mudar sem o outro, volta o 404 — e o unico jeito de descobrir
        seria alguem seguir o link na mao, que e exatamente o que aconteceu.
        """
        from apps.api.app.identidade.bootstrap import Convite, linha_do_console
        from apps.api.app.main import ROTAS_DA_INTERFACE

        linha = linha_do_console(Convite(token="abc"), "http://exemplo")

        assert any(f"http://exemplo{rota}?convite=" in linha for rota in ROTAS_DA_INTERFACE), linha
