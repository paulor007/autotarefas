"""O instalador de um clique, contra um Live de verdade (G.10).

O que se prova aqui e a promessa que a tela passa a fazer: **baixar, dois
cliques, escolher a pasta**. Sem Python instalado, sem terminal, sem digitar
codigo.

Tres perguntas, e cada uma tem um jeito proprio de falhar:

1. o executavel baixado **ja sabe para onde ligar**? Se o carimbo nao chegar, a
   janela pede endereco e codigo — e a promessa vira mentira;
2. o executavel **roda** na maquina do cliente? Um `.exe` de 29 MB que abre e
   fecha e pior do que nao ter executavel nenhum;
3. o que a janela faz por baixo **funciona contra o servidor real**? Pareamento,
   pasta autorizada e registro do servico.

A janela em si nao entra: ela e casca, e tudo que decide alguma coisa mora em
`assistente.py`, que os testes de unidade cobrem. O que este arquivo acrescenta
e o contato com o servidor de verdade.

Pula sozinho quando o executavel nao foi gerado — ele nao e versionado. Para
gerar:

    pip install -e ".[instalador]"
    python tools/construir_agente.py
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import closing, suppress
from pathlib import Path

import httpx
import pytest

RAIZ = Path(__file__).resolve().parents[2]
EXECUTAVEL = RAIZ / "dist-agente" / "AutoTarefas-Agente.exe"

TIMEOUT_SUBIDA_S = 90

# O fato que este arquivo inteiro depende, dito UMA vez.
#
# A guarda morava dentro da fixture `live`, e por isso valia so para quem
# pedia a fixture. O `test_sem_pareamento_o_modo_servico_recusa_rapido` nao
# pede — ele chama o `.exe` direto —, escapava da guarda e quebrava a CI com
# `FileNotFoundError`. A guarda estava presa ao MECANISMO (a fixture) quando o
# que ela descreve e uma condicao do AMBIENTE.
#
# No modulo, ela vale por construcao, inclusive para o proximo teste que
# alguem escrever sem lembrar da fixture.
_SEM_EXECUTAVEL = not EXECUTAVEL.is_file()
_MOTIVO_SEM_EXECUTAVEL = (
    "executavel nao gerado: rode `python tools/construir_agente.py` depois de "
    '`pip install -e ".[instalador]"`. E artefato de build, nao versionado — '
    "num checkout limpo ele nunca existe, e no Linux nao pode existir"
)

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.slow,
    pytest.mark.skipif(_SEM_EXECUTAVEL, reason=_MOTIVO_SEM_EXECUTAVEL),
]


def _porta_livre() -> int:
    with closing(socket.socket()) as tomada:
        tomada.bind(("127.0.0.1", 0))
        return int(tomada.getsockname()[1])


def _esperar_porta(porta: int) -> bool:
    fim = time.monotonic() + TIMEOUT_SUBIDA_S
    while time.monotonic() < fim:
        with closing(socket.socket()) as tomada, suppress(OSError):
            tomada.settimeout(1)
            tomada.connect(("127.0.0.1", porta))
            return True
        time.sleep(0.3)
    return False


@pytest.fixture(scope="module")
def live(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[str, str]]:
    """
    Sobe o Live e devolve (endereco, cookie de sessao do dono).

    Sem guarda do executavel aqui: ela subiu para o `pytestmark` do modulo,
    onde alcanca todo teste. Repetir a checagem daria duas afirmacoes do mesmo
    fato, livres para divergir — e foi essa divergencia que deixou um teste
    escapar.
    """
    pasta = tmp_path_factory.mktemp("exe")
    porta = _porta_livre()
    endereco = f"http://127.0.0.1:{porta}"

    processo = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "uvicorn", "apps.api.app.main:app", "--port", str(porta)],
        cwd=RAIZ,
        env={
            **os.environ,
            "DEMO_SERVERS_AUTOSTART": "0",
            "DATABASE_URL": f"sqlite:///{pasta / 'live.db'}",
            "SESSION_SECRET": "instalador-de-um-clique",  # pragma: allowlist secret
            "PUBLIC_BASE_URL": endereco,
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    linhas: list[str] = []

    def drenar() -> None:
        assert processo.stdout is not None
        linhas.extend(processo.stdout)

    threading.Thread(target=drenar, daemon=True).start()

    try:
        if not _esperar_porta(porta):
            pytest.skip("o Live nao subiu a tempo")

        import re

        convite = ""
        fim = time.monotonic() + 30
        while time.monotonic() < fim and not convite:
            achado = re.search(r"convite=([A-Za-z0-9_\-]+)", "".join(linhas))
            if achado:
                convite = achado.group(1)
            time.sleep(0.3)
        if not convite:
            pytest.skip("o convite nao apareceu no console")

        with httpx.Client(base_url=endereco, timeout=30.0) as cliente:
            resposta = cliente.post(
                "/api/auth/bootstrap",
                json={
                    "convite": convite,
                    "organizacao": "Padaria Sol",
                    "email": "dono@padariasol.com.br",
                    "nome": "Ana",
                },
            )
            assert resposta.status_code == 200, resposta.text
            cookie = resposta.cookies.get("autotarefas_sessao", "")

        assert cookie, "o bootstrap nao devolveu sessao"
        yield endereco, cookie
    finally:
        processo.terminate()
        with suppress(subprocess.TimeoutExpired):
            processo.wait(timeout=15)


@pytest.fixture
def cliente(live: tuple[str, str]) -> Iterator[httpx.Client]:
    endereco, cookie = live
    with httpx.Client(base_url=endereco, timeout=120.0) as http:
        http.cookies.set("autotarefas_sessao", cookie)
        yield http


def _codigo(cliente: httpx.Client) -> str:
    resposta = cliente.post("/api/dispositivos/codigo")
    assert resposta.status_code == 200, resposta.text
    return str(resposta.json()["codigo"])


class TestOQueATelaOferece:
    def test_a_ficha_promete_um_clique(self, cliente: httpx.Client) -> None:
        """
        Com o executavel gerado, a tela para de pedir Python.

        `precisa_de_python` vazio e o que muda o roteiro inteiro na interface.
        """
        ficha = cliente.get("/api/agente/instalador/ficha").json()

        assert ficha["formato"] == "exe"
        assert ficha["precisa_de_python"] == ""
        assert ficha["arquivos"] == 1
        assert ficha["tamanho_bytes"] > 1_000_000

    def test_o_exe_baixado_ja_sabe_para_onde_ligar(
        self, cliente: httpx.Client, live: tuple[str, str], tmp_path: Path
    ) -> None:
        """
        O carimbo e o que dispensa a pessoa de digitar endereco e codigo.

        Sem ele a janela teria dois campos — dois jeitos de errar, e o suporte
        recebendo "diz que o codigo esta errado" pelo resto da vida.
        """
        from apps.agente.agente import carimbo

        codigo = _codigo(cliente)
        resposta = cliente.get("/api/agente/instalador", params={"codigo": codigo})

        assert resposta.status_code == 200
        assert "AutoTarefas-Agente.exe" in resposta.headers["content-disposition"]

        baixado = tmp_path / "AutoTarefas-Agente.exe"
        baixado.write_bytes(resposta.content)
        dados = carimbo.ler(baixado)

        assert dados["codigo"] == codigo
        assert dados["servidor"].startswith("http://127.0.0.1")
        assert live[0].endswith(dados["servidor"].rsplit(":", 1)[-1])

    def test_codigo_de_outra_empresa_nao_e_carimbado(
        self, cliente: httpx.Client, tmp_path: Path
    ) -> None:
        """
        O servidor confere de quem e o codigo antes de colar no arquivo.

        Carimbar o que o navegador mandou permitiria um instalador apontando
        para o codigo de outra empresa — e o cliente entraria na organizacao
        errada sem nunca saber.
        """
        from apps.agente.agente import carimbo

        resposta = cliente.get("/api/agente/instalador", params={"codigo": "NAO-EXISTE"})
        baixado = tmp_path / "invalido.exe"
        baixado.write_bytes(resposta.content)

        dados = carimbo.ler(baixado)

        assert "codigo" not in dados
        assert dados["servidor"].startswith("http://127.0.0.1")


class TestOExecutavelRoda:
    def test_sem_pareamento_o_modo_servico_recusa_rapido(self, tmp_path: Path) -> None:
        """
        Um `.exe` que abre e fecha em silencio e pior do que nao existir.

        Aqui ele sai com codigo de erro — e depressa, porque o Agendador vai
        chama-lo assim a cada login enquanto a maquina nao estiver pareada.
        """
        resultado = subprocess.run(  # noqa: S603
            [
                str(EXECUTAVEL),
                "--servico",
                "--pasta-de-configuracao",
                str(tmp_path / "cfg"),
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )

        assert resultado.returncode != 0


class TestOQueAJanelaFazPorBaixo:
    def test_pareia_autoriza_e_a_maquina_aparece_no_live(
        self, cliente: httpx.Client, live: tuple[str, str], tmp_path: Path
    ) -> None:
        """
        Os passos do assistente contra o servidor de verdade.

        A janela e casca: quem decide e o `Assistente`, e e ele que precisa
        funcionar contra um Live que responde de verdade. Se este teste passa, o
        duplo clique so precisa desenhar botoes.
        """
        from apps.agente.agente import identidade as ident
        from apps.agente.agente.assistente import Assistente
        from apps.agente.agente.config import Local

        endereco, _ = live
        pasta_cfg = tmp_path / "cfg"
        protegida = tmp_path / "Financeiro"
        protegida.mkdir()

        assistente = Assistente(
            local=Local(pasta=pasta_cfg),
            guarda=ident.Guarda(pasta_cfg, usar_cofre_do_sistema=False),
            servidor=endereco,
            codigo=_codigo(cliente),
            nome_da_maquina="PC da loja",
        )

        pareou = assistente.parear()
        assert pareou.ok is True, pareou.mensagem
        assert assistente.impressao

        autorizou = assistente.autorizar(protegida)
        assert autorizou.ok is True, autorizou.mensagem

        # A maquina aparece na lista, com a MESMA impressao que o assistente
        # mostrou. E o que a pessoa compara na segunda tela.
        dispositivos = cliente.get("/api/dispositivos").json()["dispositivos"]
        assert len(dispositivos) == 1
        assert dispositivos[0]["impressao"] == assistente.impressao
        assert dispositivos[0]["nome"] == "PC da loja"

    def test_o_resumo_nao_diz_pronto_sem_pasta(
        self, cliente: httpx.Client, live: tuple[str, str], tmp_path: Path
    ) -> None:
        """
        Pareado e sem pasta: o instalador nao pode dizer que terminou.

        A pessoa fecharia a janela tranquila e descobriria na primeira madrugada
        que nao havia backup nenhum.
        """
        from apps.agente.agente import identidade as ident
        from apps.agente.agente.assistente import Assistente
        from apps.agente.agente.config import Local

        endereco, _ = live
        pasta_cfg = tmp_path / "cfg2"

        assistente = Assistente(
            local=Local(pasta=pasta_cfg),
            guarda=ident.Guarda(pasta_cfg, usar_cofre_do_sistema=False),
            servidor=endereco,
            codigo=_codigo(cliente),
            nome_da_maquina="PC do caixa",
        )
        assert assistente.parear().ok is True

        resumo = assistente.resumo()

        assert resumo.ok is False
        assert "nao copia nada" in resumo.detalhe
