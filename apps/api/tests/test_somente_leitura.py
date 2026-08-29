"""
A tranca da demonstração pública.

O que se protege aqui não é uma rota: é a promessa de que **qualquer** rota,
inclusive a que ainda não foi escrita, nasce fechada para uma sessão pública.
Um teste que listasse as rotas de hoje passaria para sempre e deixaria a
próxima entrar sem portão — que é exatamente o defeito que a tranca existe
para impedir.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.app.identidade.sessao_web import COOKIE_SESSAO, SessaoWeb, escrever_sessao
from apps.api.app.identidade.somente_leitura import (
    LIBERADOS,
    RECUSADOS_MESMO_LENDO,
    SEGUROS,
)
from apps.api.app.main import app

HTTP_PROIBIDO = 403


def _cookie(*, somente_leitura: bool) -> dict[str, str]:
    valor = escrever_sessao(
        SessaoWeb(
            usuario_id="u1",
            organizacao_id="o1",
            somente_leitura=somente_leitura,
        )
    )
    return {COOKIE_SESSAO: valor}


def _rotas_que_mudam() -> list[tuple[str, str]]:
    """
    Toda rota da aplicação cujo método não é seguro.

    Descoberta a partir do `app`, e não escrita à mão: uma lista fixa
    envelheceria em silêncio, e o primeiro efeito seria a rota nova ficar de
    fora justamente do teste que existe por causa dela.

    A varredura sai do esquema OpenAPI porque `app.routes` desta versão do
    FastAPI guarda os roteadores incluídos embrulhados, sem expor as rotas de
    dentro — percorrer a lista crua encontraria duas rotas de quarenta e uma.

    Fica de fora o que é `include_in_schema=False`: hoje só as páginas da
    interface, que são GET. Uma rota de escrita escondida do esquema escaparia
    daqui — e é por isso que a tranca vive no middleware, e não neste teste.
    """
    esquema = app.openapi()
    return sorted(
        (metodo.upper(), caminho)
        for caminho, verbos in esquema["paths"].items()
        for metodo in verbos
        if metodo.upper() not in SEGUROS and caminho.startswith("/api")
    )


def _concreto(caminho: str) -> str:
    """`/api/politicas/{politica_id}` vira um caminho pedível."""
    partes = ["algum-id" if pedaco.startswith("{") else pedaco for pedaco in caminho.split("/")]
    return "/".join(partes)


class TestNadaMuda:
    def test_ha_rotas_de_escrita_para_conferir(self) -> None:
        """Guarda contra o teste abaixo passar por não achar nada."""
        assert len(_rotas_que_mudam()) >= 5

    @pytest.mark.parametrize(("metodo", "caminho"), _rotas_que_mudam())
    def test_toda_rota_de_escrita_e_recusada(self, metodo: str, caminho: str) -> None:
        """
        Nenhuma exceção por rota: ou está em `LIBERADOS`, ou é 403.

        É este teste que faz a tranca valer para o futuro — ele varre o `app`,
        então uma rota criada amanhã entra na varredura sozinha.
        """
        cliente = TestClient(app)
        resposta = cliente.request(
            metodo,
            _concreto(caminho),
            cookies=_cookie(somente_leitura=True),
        )

        if caminho in LIBERADOS:
            assert resposta.status_code != HTTP_PROIBIDO, caminho
        else:
            assert resposta.status_code == HTTP_PROIBIDO, (metodo, caminho)

    def test_o_recado_explica_em_vez_de_so_negar(self) -> None:
        cliente = TestClient(app)
        resposta = cliente.post("/api/politicas", json={}, cookies=_cookie(somente_leitura=True))

        assert resposta.status_code == HTTP_PROIBIDO
        assert "demonstração pública" in resposta.json()["detail"]


class TestOQuePassa:
    def test_leitura_continua_valendo(self) -> None:
        # Uma tranca que impedisse de ver tambem nao serviria: a demonstracao
        # existe para ser olhada.
        cliente = TestClient(app)
        resposta = cliente.get("/api/health", cookies=_cookie(somente_leitura=True))

        assert resposta.status_code != HTTP_PROIBIDO

    def test_sair_e_sempre_permitido(self) -> None:
        """Quem entrou pode sair. `sair` só apaga o próprio cookie."""
        cliente = TestClient(app)
        resposta = cliente.post("/api/auth/sair", cookies=_cookie(somente_leitura=True))

        assert resposta.status_code != HTTP_PROIBIDO

    @pytest.mark.parametrize("caminho", RECUSADOS_MESMO_LENDO)
    def test_o_instalador_nao_e_leitura_inofensiva(self, caminho: str) -> None:
        """
        Um binário de 29 MB entregue a qualquer visitante, em laço.

        Não muda dado nenhum — e é justamente por isso que passaria por
        "leitura" se a regra fosse só o método HTTP.
        """
        cliente = TestClient(app)
        resposta = cliente.get(caminho, cookies=_cookie(somente_leitura=True))

        assert resposta.status_code == HTTP_PROIBIDO


class TestSessaoDeDentro:
    def test_sessao_normal_nao_e_barrada_pela_tranca(self) -> None:
        """
        A tranca vale para a sessão pública, e só para ela.

        Recusar aqui também transformaria a demonstração num recurso que
        quebra o produto — e o 403 viria do meio do caminho, sem explicar.
        """
        cliente = TestClient(app)
        resposta = cliente.post("/api/politicas", json={}, cookies=_cookie(somente_leitura=False))

        # 401/403 por papel ou 422 por corpo invalido sao respostas da ROTA.
        # O que nao pode e o recado da tranca.
        corpo: Any = resposta.json()
        assert "demonstração pública" not in str(corpo)


class TestOCookieAntigo:
    def test_sem_a_marca_o_cookie_entra_trancado(self) -> None:
        """
        Cookie de antes desta marca existir vale como somente leitura.

        O pior que acontece é alguém de dentro precisar entrar de novo. O
        contrário — cookie velho virando sessão com poder de escrita — seria o
        erro que não dá para desfazer depois de publicado.
        """
        from itsdangerous import URLSafeTimedSerializer

        from apps.api.app.identidade import sessao_web

        antigo = URLSafeTimedSerializer(sessao_web.segredo(), salt="autotarefas.sessao").dumps(
            {"usuario": "u1", "organizacao": "o1"}
        )

        lida = sessao_web.ler_sessao(antigo)

        assert lida is not None
        assert lida.somente_leitura is True
