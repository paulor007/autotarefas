"""Testes do canal do Agente (G.4.1).

O canal e o que transforma um dispositivo cadastrado num dispositivo que
responde. Tres coisas sao verificadas com mais cuidado:

- **quem entra** — so quem assina o desafio com a privada correspondente a
  publica guardada no pareamento;
- **quem NAO entra** — dispositivo revogado continua com a chave na maquina;
  se o estado nao fosse conferido no aperto de mao, revogar seria enfeite;
- **o que a tela pode dizer** — `agent_connected` so aparece com canal aberto.
  Um dispositivo cadastrado e desligado nao habilita nada.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.agente.agente import identidade as ident
from apps.api.app import canal, dispositivos
from apps.api.app.db import repositorio as repo
from apps.api.app.db.atual import definir_banco
from apps.api.app.db.models import Dispositivo, EstadoDispositivo, Papel
from apps.api.app.db.sessao import Banco
from apps.api.app.main import app

HTTP_OK = 200


@pytest.fixture
def banco() -> Iterator[Banco]:
    instancia = Banco("sqlite:///:memory:")
    instancia.criar_esquema()
    definir_banco(instancia)
    canal.presenca.limpar()
    yield instancia
    canal.presenca.limpar()
    definir_banco(None)


@pytest.fixture
def cliente(banco: Banco) -> Iterator[TestClient]:
    del banco
    with TestClient(app, base_url="http://live.teste") as testador:
        yield testador


@pytest.fixture
def identidade(tmp_path: Path) -> ident.Identidade:
    guarda = ident.Guarda(tmp_path / "cfg", usar_cofre_do_sistema=False)
    criada, _ = ident.obter_ou_criar(guarda)
    return criada


def _organizacao(banco: Banco, nome: str = "Padaria") -> repo.Contexto:
    with banco.sessao() as sessao:
        organizacao = repo.criar_organizacao(sessao, nome=nome, dominio=f"{nome.lower()}.com.br")
        usuario = repo.criar_usuario(
            sessao,
            email=f"dono@{nome.lower()}.com.br",
            nome="Dono",
            emissor="bootstrap",
            assunto=nome,
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


def _entrar(socket: object, dispositivo_id: str, identidade: ident.Identidade) -> dict:
    """Responde ao desafio como o Agente faria e devolve o `pronto`."""
    desafio = socket.receive_json()  # type: ignore[attr-defined]
    assert desafio["tipo"] == "desafio"
    socket.send_json(  # type: ignore[attr-defined]
        {
            "tipo": "identificacao",
            "dispositivo_id": dispositivo_id,
            "assinatura": identidade.assinar(desafio["nonce"].encode("ascii")),
        }
    )
    return dict(socket.receive_json())  # type: ignore[attr-defined]


class TestApertoDeMaos:
    def test_dispositivo_pareado_entra(
        self, banco: Banco, cliente: TestClient, identidade: ident.Identidade
    ) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)

        with cliente.websocket_connect("/api/agente/canal") as socket:
            pronto = _entrar(socket, dispositivo_id, identidade)

            assert pronto["tipo"] == "pronto"
            assert pronto["dispositivo_id"] == dispositivo_id
            assert canal.presenca.de(dispositivo_id) is not None

    def test_assinatura_de_outra_chave_e_recusada(
        self, banco: Banco, cliente: TestClient, identidade: ident.Identidade, tmp_path: Path
    ) -> None:
        """
        Saber o `dispositivo_id` nao basta: ele nao e segredo.

        O que autentica e a posse da privada, e ela nunca esteve no servidor.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)
        impostor, _ = ident.obter_ou_criar(
            ident.Guarda(tmp_path / "impostor", usar_cofre_do_sistema=False)
        )

        with cliente.websocket_connect("/api/agente/canal") as socket:
            desafio = socket.receive_json()
            socket.send_json(
                {
                    "tipo": "identificacao",
                    "dispositivo_id": dispositivo_id,
                    "assinatura": impostor.assinar(desafio["nonce"].encode("ascii")),
                }
            )
            with pytest.raises(Exception):  # noqa: B017, PT011 — o socket fecha
                socket.receive_json()

        assert canal.presenca.de(dispositivo_id) is None

    def test_assinatura_de_outro_desafio_nao_serve(
        self, banco: Banco, cliente: TestClient, identidade: ident.Identidade
    ) -> None:
        """
        Trafego capturado uma vez nao da acesso depois.

        O desafio e sorteado por conexao; assinar um antigo nao abre nada.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)

        with cliente.websocket_connect("/api/agente/canal") as socket:
            socket.receive_json()
            socket.send_json(
                {
                    "tipo": "identificacao",
                    "dispositivo_id": dispositivo_id,
                    "assinatura": identidade.assinar(b"desafio-de-outra-conexao"),
                }
            )
            with pytest.raises(Exception):  # noqa: B017, PT011
                socket.receive_json()

    def test_dispositivo_revogado_nao_entra(
        self, banco: Banco, cliente: TestClient, identidade: ident.Identidade
    ) -> None:
        """
        Revogar tem que valer de verdade.

        A chave privada continua na maquina depois da revogacao. Sem esta
        conferencia, o botao "revogar" seria enfeite na tela.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)
        with banco.sessao() as sessao:
            dispositivos.revogar(sessao, contexto, dispositivo_id=dispositivo_id)

        with cliente.websocket_connect("/api/agente/canal") as socket:
            desafio = socket.receive_json()
            socket.send_json(
                {
                    "tipo": "identificacao",
                    "dispositivo_id": dispositivo_id,
                    "assinatura": identidade.assinar(desafio["nonce"].encode("ascii")),
                }
            )
            with pytest.raises(Exception):  # noqa: B017, PT011
                socket.receive_json()

        assert canal.presenca.de(dispositivo_id) is None

    def test_dispositivo_inexistente_nao_entra(
        self, banco: Banco, cliente: TestClient, identidade: ident.Identidade
    ) -> None:
        _organizacao(banco)
        with cliente.websocket_connect("/api/agente/canal") as socket:
            desafio = socket.receive_json()
            socket.send_json(
                {
                    "tipo": "identificacao",
                    "dispositivo_id": "nao-existe",
                    "assinatura": identidade.assinar(desafio["nonce"].encode("ascii")),
                }
            )
            with pytest.raises(Exception):  # noqa: B017, PT011
                socket.receive_json()

    def test_primeira_mensagem_fora_do_protocolo_derruba(
        self, banco: Banco, cliente: TestClient
    ) -> None:
        """Conexao que abre e fala outra coisa e varredura, nao cliente."""
        _organizacao(banco)
        with cliente.websocket_connect("/api/agente/canal") as socket:
            socket.receive_json()
            socket.send_json({"tipo": "qualquer-outra-coisa"})
            with pytest.raises(Exception):  # noqa: B017, PT011
                socket.receive_json()


class TestPresenca:
    def test_batida_mantem_a_conexao_viva(
        self, banco: Banco, cliente: TestClient, identidade: ident.Identidade
    ) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)

        with cliente.websocket_connect("/api/agente/canal") as socket:
            _entrar(socket, dispositivo_id, identidade)
            socket.send_json({"tipo": "batida"})

            assert socket.receive_json() == {"tipo": "batida", "eco": True}

    def test_desconectar_tira_da_presenca(
        self, banco: Banco, cliente: TestClient, identidade: ident.Identidade
    ) -> None:
        """
        Presenca e um fato do agora.

        Se ela sobrevivesse a queda da conexao, a tela mostraria "conectado"
        para uma maquina desligada — e alguem confiaria num backup que nao vai
        acontecer.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)

        with cliente.websocket_connect("/api/agente/canal") as socket:
            _entrar(socket, dispositivo_id, identidade)
            assert canal.presenca.de(dispositivo_id) is not None

        assert canal.presenca.de(dispositivo_id) is None

    def test_uma_organizacao_nao_ve_a_presenca_da_outra(
        self, banco: Banco, cliente: TestClient, identidade: ident.Identidade
    ) -> None:
        primeira = _organizacao(banco, nome="Padaria")
        segunda = _organizacao(banco, nome="Oficina")
        dispositivo_id = _parear(banco, primeira, identidade)

        with cliente.websocket_connect("/api/agente/canal") as socket:
            _entrar(socket, dispositivo_id, identidade)

            assert len(canal.presenca.da_organizacao(primeira.organizacao_id)) == 1
            assert canal.presenca.da_organizacao(segunda.organizacao_id) == []

    def test_ultimo_contato_e_atualizado(
        self, banco: Banco, cliente: TestClient, identidade: ident.Identidade
    ) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)

        with cliente.websocket_connect("/api/agente/canal") as socket:
            _entrar(socket, dispositivo_id, identidade)

        with banco.sessao() as sessao:
            dispositivo = sessao.get(Dispositivo, dispositivo_id)
            assert dispositivo is not None
            assert dispositivo.ultimo_contato is not None
            assert dispositivo.estado is EstadoDispositivo.ATIVO


class TestCapacidadeHonesta:
    def test_sem_agente_conectado_a_capacidade_nao_aparece(
        self, banco: Banco, cliente: TestClient, identidade: ident.Identidade
    ) -> None:
        """
        Dispositivo cadastrado e desligado nao habilita nada.

        Anunciar `agent_connected` sem canal aberto seria o "status simulado"
        que o produto recusa.
        """
        contexto = _organizacao(banco)
        _parear(banco, contexto, identidade)

        capacidades = cliente.get("/api/health").json()["capabilities"]

        assert "web_upload" in capacidades
        assert "agent_connected" not in capacidades

    def test_com_agente_conectado_a_capacidade_aparece(
        self, banco: Banco, cliente: TestClient, identidade: ident.Identidade
    ) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)

        with cliente.websocket_connect("/api/agente/canal") as socket:
            _entrar(socket, dispositivo_id, identidade)

            assert "agent_connected" in cliente.get("/api/health").json()["capabilities"]

    def test_capacidade_some_quando_o_agente_cai(
        self, banco: Banco, cliente: TestClient, identidade: ident.Identidade
    ) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)

        with cliente.websocket_connect("/api/agente/canal") as socket:
            _entrar(socket, dispositivo_id, identidade)

        assert "agent_connected" not in cliente.get("/api/health").json()["capabilities"]
