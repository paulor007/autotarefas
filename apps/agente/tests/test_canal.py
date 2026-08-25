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
import contextlib
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn

from apps.agente.agente import canal as canal_agente
from apps.agente.agente import identidade as ident
from apps.agente.agente.config import Configuracao
from apps.agente.agente.diario import Diario
from apps.agente.agente.diario import Execucao as ExecucaoDoDiario
from apps.api.app import canal as canal_servidor
from apps.api.app import dispositivos
from apps.api.app.db import repositorio as repo
from apps.api.app.db.atual import definir_banco
from apps.api.app.db.models import Artefato, Execucao, Papel, ResultadoExecucao
from apps.api.app.db.sessao import Banco
from apps.api.app.identidade.sessao_web import COOKIE_SESSAO, SessaoWeb, escrever_sessao

#: Quanto esperar o servidor de teste subir antes de desistir.
_ESPERA_SUBIDA_S = 10.0

HTTP_OK = 200
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409


def _sessao_de(banco: Banco, contexto: repo.Contexto) -> str:
    """
    Cookie de sessao valido para aquele contexto.

    Emitido diretamente, e nao pelo fluxo de login: o que este teste mede e o
    canal do Agente, e passar pelo OIDC aqui so acrescentaria formas de o
    teste falhar por motivo que nao e o dele.
    """
    del banco
    assert contexto.usuario_id is not None
    return escrever_sessao(
        SessaoWeb(usuario_id=contexto.usuario_id, organizacao_id=contexto.organizacao_id)
    )


def _organizacao_extra(banco: Banco, nome: str) -> repo.Contexto:
    """Outra organizacao, para provar que uma nao alcanca a outra."""
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


def _cliente_http(servidor: str) -> httpx.Client:
    return httpx.Client(base_url=servidor, timeout=30.0)


def _com_agente_no_ar(
    banco: Banco,
    servidor: str,
    identidade: ident.Identidade,
    pasta_autorizada: Path | None = None,
    diario: Diario | None = None,
) -> tuple[str, repo.Contexto, threading.Thread]:
    """Sobe o Agente numa thread e espera ele aparecer na presenca."""
    contexto = _organizacao(banco)
    dispositivo_id = _parear(banco, contexto, identidade)
    configuracao = Configuracao(servidor=servidor, dispositivo_id=dispositivo_id)
    if pasta_autorizada is not None:
        configuracao = configuracao.com_raiz(pasta_autorizada)

    def rodar() -> None:
        with contextlib.suppress(Exception):
            asyncio.run(
                canal_agente.manter_conectado(
                    configuracao, identidade, tentativas_maximas=1, diario=diario
                )
            )

    thread = threading.Thread(target=rodar, daemon=True)
    thread.start()

    limite = time.monotonic() + _ESPERA_SUBIDA_S
    while canal_servidor.presenca.de(dispositivo_id) is None and time.monotonic() < limite:
        time.sleep(0.05)
    if canal_servidor.presenca.de(dispositivo_id) is None:
        pytest.skip("o Agente nao conectou a tempo")
    return dispositivo_id, contexto, thread


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


@pytest.mark.slow
class TestComandosPeloCanal:
    """
    Comando de ponta a ponta: sai do Live, atravessa o socket, executa na
    maquina e a resposta volta.

    O pedido sai por uma rota HTTP de proposito. E o caminho que a interface
    vai usar, e ele garante que a espera pelo resultado acontece no mesmo laco
    de eventos do canal — detalhe que, feito errado, produz um travamento que
    so aparece em producao.
    """

    def test_live_pergunta_e_o_agente_responde(
        self, banco: Banco, servidor: str, identidade: ident.Identidade, tmp_path: Path
    ) -> None:
        pasta = tmp_path / "dados"
        pasta.mkdir()
        dispositivo_id, contexto, _ = _com_agente_no_ar(
            banco, servidor, identidade, pasta_autorizada=pasta
        )
        cookie = _sessao_de(banco, contexto)

        with _cliente_http(servidor) as http:
            http.cookies.set(COOKIE_SESSAO, cookie)
            resposta = http.post(f"/api/dispositivos/{dispositivo_id}/consultar")

        assert resposta.status_code == HTTP_OK, resposta.text
        estado = resposta.json()["estado"]
        assert estado["ok"] is True
        assert estado["pode_copiar"] is True
        assert str(pasta.resolve()) in estado["raizes"]

    def test_dispositivo_desligado_e_409_e_nao_erro(
        self, banco: Banco, servidor: str, identidade: ident.Identidade
    ) -> None:
        """
        Maquina desligada e situacao normal, nao falha do produto.

        Confundir as duas faria a tela acusar erro toda noite, quando o
        computador da loja esta simplesmente fechado.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)
        cookie = _sessao_de(banco, contexto)

        with _cliente_http(servidor) as http:
            http.cookies.set(COOKIE_SESSAO, cookie)
            resposta = http.post(f"/api/dispositivos/{dispositivo_id}/consultar")

        assert resposta.status_code == HTTP_CONFLICT
        assert "canal aberto" in resposta.json()["detail"]

    def test_uma_organizacao_nao_consulta_o_dispositivo_da_outra(
        self, banco: Banco, servidor: str, identidade: ident.Identidade
    ) -> None:
        dispositivo_id, _, _ = _com_agente_no_ar(banco, servidor, identidade)
        outra = _organizacao_extra(banco, "Oficina")
        cookie = _sessao_de(banco, outra)

        with _cliente_http(servidor) as http:
            http.cookies.set(COOKIE_SESSAO, cookie)
            resposta = http.post(f"/api/dispositivos/{dispositivo_id}/consultar")

        assert resposta.status_code == HTTP_NOT_FOUND

    def test_backup_de_ponta_a_ponta_pelo_live(
        self, banco: Banco, servidor: str, identidade: ident.Identidade, tmp_path: Path
    ) -> None:
        """
        O fluxo que o Card 02 existe para entregar.

        Uma pessoa clica no Live; o comando atravessa o canal; o Agente copia
        pastas autorizadas NA MAQUINA; o pacote fica la; o servidor guarda a
        ficha e a execucao. Nenhum arquivo sobe.
        """
        pasta = tmp_path / "dados"
        pasta.mkdir()
        (pasta / "contrato.txt").write_text("contrato importante", encoding="utf-8")
        (pasta / "nota.txt").write_text("nota fiscal", encoding="utf-8")

        dispositivo_id, contexto, _ = _com_agente_no_ar(
            banco, servidor, identidade, pasta_autorizada=pasta
        )
        destino = tmp_path / "saida" / "pacote.zip"
        cookie = _sessao_de(banco, contexto)

        with _cliente_http(servidor) as http:
            http.cookies.set(COOKIE_SESSAO, cookie)
            resposta = http.post(
                f"/api/dispositivos/{dispositivo_id}/backup",
                json={"destino": str(destino)},
            )

        assert resposta.status_code == HTTP_OK, resposta.text
        corpo = resposta.json()
        assert corpo["ok"] is True
        assert corpo["pacote"] == "pacote.zip"

        # O pacote existe NA MAQUINA e confere.
        assert destino.is_file()
        from autotarefas.tasks.backup import verify_backup

        assert verify_backup(destino).ok is True

        # E o servidor guardou a ficha, sem o conteudo e sem o caminho local.
        with banco.sessao() as sessao:
            execucao = sessao.get(Execucao, corpo["execucao_id"])
            assert execucao is not None
            assert execucao.resultado is ResultadoExecucao.SUCESSO
            assert execucao.arquivos_incluidos == 2
            artefatos = list(sessao.execute(repo.escopo(Artefato, contexto)).scalars())

        assert len(artefatos) == 1
        assert artefatos[0].nome == "pacote.zip"
        assert artefatos[0].sha256
        assert str(tmp_path) not in artefatos[0].localizacao

    def test_backup_com_dispositivo_desligado_registra_a_falha(
        self, banco: Banco, servidor: str, identidade: ident.Identidade
    ) -> None:
        """
        A execucao e gravada antes de o comando sair.

        Sem registro, "mandei fazer backup e nada aconteceu" viraria uma
        conversa sem evidencia nenhuma.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _parear(banco, contexto, identidade)
        cookie = _sessao_de(banco, contexto)

        with _cliente_http(servidor) as http:
            http.cookies.set(COOKIE_SESSAO, cookie)
            resposta = http.post(f"/api/dispositivos/{dispositivo_id}/backup", json={})

        assert resposta.status_code == HTTP_CONFLICT
        with banco.sessao() as sessao:
            execucoes = list(sessao.execute(repo.escopo(Execucao, contexto)).scalars())

        assert len(execucoes) == 1
        assert execucoes[0].resultado is ResultadoExecucao.FALHA
        assert "canal aberto" in execucoes[0].ressalva


class TestHistoricoDoAgendamento:
    """
    O backup que rodou com o navegador fechado aparece no Live (G.7.1).

    Este e o teste que separa "o cliente pode mandar fazer backup" de "o cliente
    tem backup". O agendamento roda de madrugada, muitas vezes com a internet
    caida; se o registro dependesse do envio, o Live mostraria uma noite vazia
    para uma noite em que o backup foi feito.
    """

    @staticmethod
    def _diario_com_execucoes(pasta: Path, quantas: int = 2) -> Diario:
        """Simula noites de agendamento que aconteceram sem o servidor por perto."""
        diario = Diario(pasta=pasta)
        for numero in range(quantas):
            diario.registrar(
                ExecucaoDoDiario(
                    politica_id="",
                    politica_nome="Diaria da loja",
                    iniciada_em=f"2026-08-2{numero}T02:00:00",
                    terminada_em=f"2026-08-2{numero}T02:04:00",
                    resultado="sucesso",
                    arquivos=12,
                    bytes_copiados=4096,
                    artefato={
                        "nome": f"backup_2026-08-2{numero}_0200.zip",
                        "tamanho_bytes": 4096,
                        "sha256": "a" * 64,
                        "localizacao": "dispositivo",
                    },
                )
            )
        return diario

    def _esperar_execucoes(
        self, banco: Banco, contexto: repo.Contexto, quantas: int
    ) -> list[Execucao]:
        limite = time.monotonic() + _ESPERA_SUBIDA_S
        while time.monotonic() < limite:
            with banco.sessao() as sessao:
                achadas = list(sessao.execute(repo.escopo(Execucao, contexto)).scalars())
            if len(achadas) >= quantas:
                return achadas
            time.sleep(0.05)
        return []

    def test_execucoes_feitas_offline_aparecem_ao_reconectar(
        self, banco: Banco, servidor: str, identidade: ident.Identidade, tmp_path: Path
    ) -> None:
        diario = self._diario_com_execucoes(tmp_path / "cfg")

        _, contexto, _ = _com_agente_no_ar(banco, servidor, identidade, diario=diario)
        execucoes = self._esperar_execucoes(banco, contexto, 2)

        assert len(execucoes) == 2, "o historico do agendamento nao chegou ao servidor"
        assert {item.resultado for item in execucoes} == {ResultadoExecucao.SUCESSO}
        assert {item.origem for item in execucoes} == {"agendamento"}

    def test_o_pacote_aparece_como_artefato_sem_caminho_local(
        self, banco: Banco, servidor: str, identidade: ident.Identidade, tmp_path: Path
    ) -> None:
        """
        A ficha do pacote sobe; o pacote e o caminho dele, nao.

        O ZIP fica na maquina do cliente, e a estrutura de pastas da empresa
        nao e assunto do servidor.
        """
        diario = self._diario_com_execucoes(tmp_path / "cfg", quantas=1)

        _, contexto, _ = _com_agente_no_ar(banco, servidor, identidade, diario=diario)
        self._esperar_execucoes(banco, contexto, 1)

        with banco.sessao() as sessao:
            artefatos = list(sessao.execute(repo.escopo(Artefato, contexto)).scalars())

        assert len(artefatos) == 1
        assert artefatos[0].nome.startswith("backup_2026-08-2")
        assert artefatos[0].localizacao == "dispositivo"
        assert str(tmp_path) not in artefatos[0].localizacao

    def test_o_diario_para_de_reenviar_o_que_foi_confirmado(
        self, banco: Banco, servidor: str, identidade: ident.Identidade, tmp_path: Path
    ) -> None:
        """
        A confirmacao do servidor e o que esvazia a fila.

        Sem ela, o mesmo backup voltaria a cada reconexao, para sempre.
        """
        diario = self._diario_com_execucoes(tmp_path / "cfg")

        _, contexto, _ = _com_agente_no_ar(banco, servidor, identidade, diario=diario)
        self._esperar_execucoes(banco, contexto, 2)

        limite = time.monotonic() + _ESPERA_SUBIDA_S
        while diario.pendentes() and time.monotonic() < limite:
            time.sleep(0.05)

        assert diario.pendentes() == []
        assert len(diario.todas()) == 2

    def test_o_historico_chega_a_tela_pela_rota(
        self, banco: Banco, servidor: str, identidade: ident.Identidade, tmp_path: Path
    ) -> None:
        """O que o Live mostra vem da rota, e nao de uma consulta de teste."""
        diario = self._diario_com_execucoes(tmp_path / "cfg")

        dispositivo_id, contexto, _ = _com_agente_no_ar(banco, servidor, identidade, diario=diario)
        self._esperar_execucoes(banco, contexto, 2)
        cookie = _sessao_de(banco, contexto)

        with _cliente_http(servidor) as http:
            http.cookies.set(COOKIE_SESSAO, cookie)
            resposta = http.get("/api/historico", params={"dispositivo_id": dispositivo_id})

        assert resposta.status_code == HTTP_OK, resposta.text
        execucoes = resposta.json()["execucoes"]
        assert len(execucoes) == 2
        assert execucoes[0]["origem"] == "agendamento"
        assert execucoes[0]["artefatos"][0]["nome"].startswith("backup_")

    def test_a_organizacao_vizinha_nao_ve_este_historico(
        self, banco: Banco, servidor: str, identidade: ident.Identidade, tmp_path: Path
    ) -> None:
        """Isolamento vale para o historico como vale para o resto."""
        diario = self._diario_com_execucoes(tmp_path / "cfg", quantas=1)

        _, contexto, _ = _com_agente_no_ar(banco, servidor, identidade, diario=diario)
        self._esperar_execucoes(banco, contexto, 1)

        vizinha = _organizacao_extra(banco, "Farmacia")
        cookie = _sessao_de(banco, vizinha)

        with _cliente_http(servidor) as http:
            http.cookies.set(COOKIE_SESSAO, cookie)
            resposta = http.get("/api/historico")

        assert resposta.status_code == HTTP_OK, resposta.text
        assert resposta.json()["execucoes"] == []
