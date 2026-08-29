"""
A porta da demonstração pública.

Ela existe para um recrutador entrar no AutoTarefas pelo portfólio, sem conta e
sem instalar nada. O risco correspondente é óbvio: uma porta sem senha numa
instalação que não deveria ter nenhuma. Os testes aqui insistem justamente
nisso — que ela não abre sozinha, que não escolhe organização por conta
própria, e que o que sai dela não muda nada.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.app.config import settings
from apps.api.app.db import repositorio as repo
from apps.api.app.db.atual import definir_banco
from apps.api.app.db.models import Organizacao, Papel, Usuario
from apps.api.app.db.sessao import Banco
from apps.api.app.identidade import demonstracao
from apps.api.app.identidade.sessao_web import COOKIE_SESSAO, ler_sessao
from apps.api.app.main import app

HTTP_NAO_ENCONTRADO = 404
HTTP_PROIBIDO = 403
HTTP_VIU_OUTRO = 303

VITRINE = "AutoTarefas Demonstracao"


def _ajustar(**valores: object) -> dict[str, object]:
    anteriores = {nome: getattr(settings, nome) for nome in valores}
    for nome, valor in valores.items():
        object.__setattr__(settings, nome, valor)
    return anteriores


@pytest.fixture
def banco() -> object:
    instancia = Banco("sqlite:///:memory:")
    instancia.criar_esquema()
    definir_banco(instancia)
    with instancia.sessao() as sessao:
        repo.criar_organizacao(sessao, nome=VITRINE, dominio="demonstracao.local")
        # Uma SEGUNDA organizacao, de proposito: e o cenario em que escolher
        # "a primeira que aparecer" publicaria dado de cliente.
        organizacao = repo.criar_organizacao(sessao, nome="Cliente Real", dominio="cliente.com.br")
        usuario = repo.criar_usuario(
            sessao,
            email="dono@cliente.com.br",
            nome="Dono",
            emissor="bootstrap",
            assunto="Cliente Real",
        )
        repo.vincular(sessao, organizacao=organizacao, usuario=usuario, papel=Papel.DONO)
    yield instancia
    definir_banco(None)


@pytest.fixture
def ligada(banco: Banco) -> object:
    del banco
    anteriores = _ajustar(demonstracao_publica=True, demonstracao_org=VITRINE)
    yield
    _ajustar(**anteriores)


class TestNaoAbreSozinha:
    def test_desligada_por_padrao(self, banco: Banco) -> None:
        del banco
        anteriores = _ajustar(demonstracao_publica=False, demonstracao_org=VITRINE)
        try:
            assert demonstracao.ligada() is False
            resposta = TestClient(app).get("/api/auth/visitante", follow_redirects=False)
        finally:
            _ajustar(**anteriores)

        assert resposta.status_code == HTTP_NAO_ENCONTRADO

    def test_ligada_sem_organizacao_nomeada_nao_abre(self, banco: Banco) -> None:
        """
        Sem o nome, a porta fica fechada — e não "escolhe uma".

        Num servidor com mais de uma organização, adivinhar seria a receita
        para publicar o dado de um cliente por acidente.
        """
        del banco
        anteriores = _ajustar(demonstracao_publica=True, demonstracao_org="")
        try:
            assert demonstracao.ligada() is False
            resposta = TestClient(app).get("/api/auth/visitante", follow_redirects=False)
        finally:
            _ajustar(**anteriores)

        assert resposta.status_code == HTTP_NAO_ENCONTRADO

    def test_apontada_para_organizacao_que_nao_existe_recusa(self, banco: Banco) -> None:
        del banco
        anteriores = _ajustar(demonstracao_publica=True, demonstracao_org="Nao Existe")
        try:
            resposta = TestClient(app).get("/api/auth/visitante", follow_redirects=False)
        finally:
            _ajustar(**anteriores)

        assert resposta.status_code == HTTP_NAO_ENCONTRADO


class TestOVisitanteEntra:
    def test_um_pedido_e_a_pessoa_esta_dentro(self, ligada: None) -> None:
        del ligada
        resposta = TestClient(app).get("/api/auth/visitante", follow_redirects=False)

        assert resposta.status_code == HTTP_VIU_OUTRO
        assert resposta.headers["location"] == "/app"
        assert COOKIE_SESSAO in resposta.cookies

    def test_a_sessao_sai_marcada_como_somente_leitura(self, ligada: None) -> None:
        del ligada
        resposta = TestClient(app).get("/api/auth/visitante", follow_redirects=False)

        lida = ler_sessao(resposta.cookies[COOKIE_SESSAO])
        assert lida is not None
        assert lida.somente_leitura is True

    def test_cai_na_organizacao_nomeada_e_nao_na_outra(self, ligada: None, banco: Banco) -> None:
        del ligada
        resposta = TestClient(app).get("/api/auth/visitante", follow_redirects=False)

        lida = ler_sessao(resposta.cookies[COOKIE_SESSAO])
        assert lida is not None
        with banco.sessao() as sessao:
            nomes = {nome for (nome,) in sessao.execute(select(Organizacao.nome)).all()}
            entrada = demonstracao.abrir(sessao)

        assert "Cliente Real" in nomes, "o cenario precisa das duas organizacoes"
        assert entrada.organizacao == VITRINE
        assert lida.organizacao_id == entrada.organizacao_id

    def test_visitar_duas_vezes_nao_cria_dois_usuarios(self, ligada: None, banco: Banco) -> None:
        """
        Uma linha por visita encheria o banco e faria a auditoria contar mil
        pessoas onde há uma função.
        """
        del ligada
        cliente = TestClient(app)
        cliente.get("/api/auth/visitante", follow_redirects=False)
        cliente.get("/api/auth/visitante", follow_redirects=False)

        with banco.sessao() as sessao:
            entrada = demonstracao.abrir(sessao)
            usuarios = (
                sessao.execute(
                    select(Usuario).where(Usuario.email == demonstracao.EMAIL_DO_VISITANTE)
                )
                .scalars()
                .all()
            )

        assert len(usuarios) == 1
        assert entrada.usuario_id == usuarios[0].id

    def test_o_visitante_e_leitor_no_banco(self, ligada: None, banco: Banco) -> None:
        """
        Papel `leitor` ALÉM da marca de somente leitura, e não no lugar dela.

        Duas travas independentes: afrouxar o middleware ainda esbarra no
        papel; promover o papel por engano ainda esbarra no middleware.
        """
        del ligada
        with banco.sessao() as sessao:
            entrada = demonstracao.abrir(sessao)
            contexto = repo.abrir_contexto(
                sessao,
                usuario_id=entrada.usuario_id,
                organizacao_id=entrada.organizacao_id,
            )

        assert contexto.papel is Papel.LEITOR

    def test_e_nao_consegue_mudar_nada(self, ligada: None) -> None:
        """O teste que fecha o assunto: entrou, tentou, foi recusado."""
        del ligada
        cliente = TestClient(app)
        cliente.get("/api/auth/visitante")

        assert cliente.post("/api/politicas", json={}).status_code == HTTP_PROIBIDO
        assert cliente.post("/api/dispositivos/codigo").status_code == HTTP_PROIBIDO


class TestOEstadoConta:
    def test_a_tela_sabe_que_ha_demonstracao_antes_de_entrar(self, ligada: None) -> None:
        del ligada
        corpo = TestClient(app).get("/api/auth/estado").json()

        assert corpo["demonstracao_publica"] is True
        assert corpo["autenticado"] is False

    def test_depois_de_entrar_a_tela_sabe_que_nao_muda_nada(self, ligada: None) -> None:
        del ligada
        cliente = TestClient(app)
        cliente.get("/api/auth/visitante")

        corpo = cliente.get("/api/auth/estado").json()

        assert corpo["autenticado"] is True
        assert corpo["somente_leitura"] is True
        assert corpo["organizacao"]["nome"] == VITRINE
