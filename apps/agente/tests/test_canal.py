"""Canal do Agente contra um servidor de verdade (G.4.1).

Estes testes sobem o backend num servidor HTTP real, numa porta livre, e
conectam com o cliente WebSocket que o Agente usa em producao. Nao ha
transporte de mentira aqui: e socket de verdade, aperto de mao de verdade e
assinatura conferida de verdade.

Vale o custo porque o canal e a fundacao do modo agente. Um teste que
substituisse o transporte provaria que o codigo chama as funcoes certas — e
nao que uma maquina consegue mesmo se conectar.
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from apps.agente.agente import canal as canal_agente
from apps.agente.agente import identidade as ident
from apps.agente.agente.config import Configuracao
from apps.api.app import canal as canal_servidor
from apps.api.app import dispositivos
from apps.api.app.db import repositorio as repo
from apps.api.app.db.atual import definir_banco
from apps.api.app.db.models import Papel
from apps.api.app.db.sessao import Banco

#: Quanto esperar o servidor de teste subir antes de desistir.
_ESPERA_SUBIDA_S = 10.0


def _porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tomada:
        tomada.bind(("127.0.0.1", 0))
        return int(tomada.getsockname()[1])


@pytest.fixture
def banco() -> Iterator[Banco]:
    instancia = Banco("sqlite:///:memory:")
    instancia.criar_esquema()
    definir_banco(instancia)
    canal_servidor.presenca.limpar()
    yield instancia
    canal_servidor.presenca.limpar()
    definir_banco(None)


@pytest.fixture
def servidor(banco: Banco) -> Iterator[str]:
    """
    Backend de verdade, numa porta livre, na mesma memoria do teste.

    Mesmo processo de proposito: o banco em memoria e a presenca sao estado
    deste processo, e o teste precisa enxergar os dois.
    """
    del banco
    from apps.api.app.main import app

    porta = _porta_livre()
    configuracao = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=porta,
        log_level="error",
        # Implementacao nova de WebSocket do uvicorn. A antiga usa a API
        # legada da biblioteca `websockets` e enche a suite de avisos de
        # descontinuacao que nao sao nossos.
        ws="websockets-sansio",
    )
    servidor_uvicorn = uvicorn.Server(configuracao)
    thread = threading.Thread(target=servidor_uvicorn.run, daemon=True)
    thread.start()

    limite = time.monotonic() + _ESPERA_SUBIDA_S
    while not servidor_uvicorn.started and time.monotonic() < limite:
        time.sleep(0.05)
    if not servidor_uvicorn.started:
        pytest.skip("o servidor de teste nao subiu a tempo")

    yield f"http://127.0.0.1:{porta}"

    servidor_uvicorn.should_exit = True
    thread.join(timeout=_ESPERA_SUBIDA_S)


def _organizacao(banco: Banco) -> repo.Contexto:
    with banco.sessao() as sessao:
        organizacao = repo.criar_organizacao(sessao, nome="Padaria", dominio="padaria.com.br")
        usuario = repo.criar_usuario(
            sessao,
            email="dono@padaria.com.br",
            nome="Dono",
            emissor="bootstrap",
            assunto="dono",
        )
        repo.vincular(sessao, organizacao=organizacao, usuario=usuario, papel=Papel.DONO)
        return repo.Contexto(organizacao_id=organizacao.id, usuario_id=usuario.id, papel=Papel.DONO)


def _parear(banco: Banco, contexto: repo.Contexto, identidade: ident.Identidade) -> str:
    with banco.sessao() as sessao:
        codigo = dispositivos.emitir(sessao, contexto).codigo
    with banco.sessao() as sessao:
        return dispositivos.parear(
            sessao,
            codigo=codigo,
            chave_publica=identidade.publica_em_base64,
            nome="PC da loja",
            sistema="Windows 11",
            versao_agente="0.1.0",
        ).id


@pytest.fixture
def identidade(tmp_path: Path) -> ident.Identidade:
    guarda = ident.Guarda(tmp_path / "cfg", usar_cofre_do_sistema=False)
    criada, _ = ident.obter_ou_criar(guarda)
    return criada


class TestEnderecoDoCanal:
    def test_https_vira_wss(self) -> None:
        """
        Um Agente configurado com HTTPS nao pode cair para texto claro.

        Se `https` virasse `ws`, o desafio e a assinatura viajariam abertos e
        ninguem perceberia.
        """
        assert canal_agente.url_do_canal("https://live.exemplo.com.br") == (
            "wss://live.exemplo.com.br/api/agente/canal"
        )

    def test_http_vira_ws(self) -> None:
        assert canal_agente.url_do_canal("http://127.0.0.1:8000") == (
            "ws://127.0.0.1:8000/api/agente/canal"
        )

    def test_barra_no_fim_nao_duplica(self) -> None:
        assert "//api" not in canal_agente.url_do_canal("https://live.exemplo.com.br/")


class TestEsperaEntreTentativas:
    def test_cresce_e_respeita_o_teto(self) -> None:
        """
        Tentar a cada segundo transformaria uma queda de dez minutos em dez mil
        tentativas; esperar sempre o maximo faria uma queda de dois segundos
        custar um minuto de ausencia.
        """
        primeira = canal_agente._espera(1)
        decima = canal_agente._espera(10)

        assert primeira < decima
        assert decima <= canal_agente.ESPERA_MAXIMA_S * (1 + canal_agente.JITTER)

    def test_tem_aleatoriedade(self) -> None:
        """
        Cem Agentes que caem juntos nao podem voltar juntos.

        Queda de energia num predio derrubaria o servidor de novo na volta.
        """
        amostras = {canal_agente._espera(5) for _ in range(20)}
        assert len(amostras) > 1


@pytest.mark.slow
class TestConexaoReal:
    def test_agente_conecta_e_o_servidor_ve_presenca(
        self, banco: Banco, servidor: str, identidade: ident.Identidade
    ) -> None:
        """Socket de verdade, aperto de mao de verdade, presenca de verdade."""
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)
        configuracao = Configuracao(servidor=servidor, dispositivo_id=dispositivo_id)
        visto: dict[str, object] = {}

        async def ao_conectar(pronto: dict[str, object]) -> None:
            visto.update(pronto)
            # Confirma a presenca do lado do servidor enquanto o canal esta
            # aberto: depois de fechar, ela deixa de existir de proposito.
            visto["presente"] = canal_servidor.presenca.de(dispositivo_id) is not None
            msg = "parar depois de conferir"
            raise RuntimeError(msg)

        estado = canal_agente.Estado()
        with pytest.raises(RuntimeError, match="parar depois"):
            asyncio.run(
                canal_agente.manter_conectado(
                    configuracao, identidade, estado=estado, ao_conectar=ao_conectar
                )
            )

        assert visto.get("tipo") == "pronto"
        assert visto.get("presente") is True

    def test_dispositivo_revogado_faz_o_agente_parar_de_tentar(
        self, banco: Banco, servidor: str, identidade: ident.Identidade
    ) -> None:
        """
        Insistir nao resolve, e ficar tentando esconderia o problema.

        Quem precisa agir e uma pessoa: o Agente para e diz o motivo.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)
        with banco.sessao() as sessao:
            dispositivos.revogar(sessao, contexto, dispositivo_id=dispositivo_id)

        configuracao = Configuracao(servidor=servidor, dispositivo_id=dispositivo_id)
        estado = asyncio.run(
            canal_agente.manter_conectado(configuracao, identidade, tentativas_maximas=3)
        )

        assert estado.conectado is False
        assert estado.tentativas == 1
        assert "pareie novamente" in estado.ultimo_erro

    def test_servidor_fora_do_ar_nao_derruba_o_agente(self, identidade: ident.Identidade) -> None:
        """
        Rede caida e situacao normal, nao excecao que mata o servico.

        O Agente registra o erro e continua tentando — desistir significaria
        parar de fazer backup em silencio.
        """
        configuracao = Configuracao(servidor="http://127.0.0.1:9", dispositivo_id="qualquer")

        estado = asyncio.run(
            canal_agente.manter_conectado(configuracao, identidade, tentativas_maximas=1)
        )

        assert estado.conectado is False
        assert estado.ultimo_erro
