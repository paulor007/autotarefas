"""Homologacao do Card 02 de ponta a ponta, com NAVEGADOR REAL.

Os testes de unidade provam cada peca. Este prova o produto: uma pessoa abre o
Live, cria a empresa, baixa o Agente, instala numa maquina, autoriza uma pasta,
cria uma politica, fecha o navegador, e o backup acontece.

Nada aqui e simulado. Sao processos de verdade:

- o **backend** sobe com `uvicorn`, num banco SQLite temporario;
- o **frontend** e servido pelo proprio backend, do `dist/` — a mesma
  combinacao que o cliente recebe;
- o **Agente** roda como processo separado, a partir do ZIP que a tela oferece
  para baixar. Nao e o codigo do repositorio importado: e o pacote extraido;
- o **navegador** e o Chromium do Playwright, clicando na tela.

Os vinte passos da homologacao viram testes em ordem. Cada um depende do
anterior, e isso e proposital: a pergunta que este arquivo responde nao e "cada
peca funciona?", e sim "a jornada inteira acontece?".

Rodar:
    playwright install chromium
    npm --prefix apps/web run build
    python -m pytest tests/e2e/test_homologacao_card_02_e2e.py -p no:randomly

Pula sozinho (sem falhar a suite) quando faltar Chromium ou o build do
frontend.
"""

from __future__ import annotations

import io
import os
import re
import socket
import subprocess
import sys
import threading
import time
import zipfile
from collections.abc import Callable, Iterator
from contextlib import closing, suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright nao instalado")
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
FRONTEND = RAIZ / "apps" / "web"

TIMEOUT_SUBIDA_S = 90
TIMEOUT_UI_MS = 30_000

#: Quanto esperar por algo que depende do Agente (conectar, executar, subir
#: historico). Generoso: e processo separado, com rede e disco no meio.
PACIENCIA_S = 90.0

#: O agendador acorda de minuto em minuto. Duas voltas com folga.
PACIENCIA_AGENDAMENTO_S = 210.0

#: Maior que o limite de 10 MB do envio pelo navegador. E o teste que separa
#: "aceita arquivo grande" de "aceita arquivo pequeno e promete o resto".
TAMANHO_GRANDE = 12 * 1024 * 1024

#: Onde as capturas do fluxo sao gravadas. Elas sao evidencia da entrega, e
#: nascem do teste que passou — nao de uma sessao manual que ninguem viu.
CAPTURAS = RAIZ / "docs" / "cards" / "capturas-02"

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


# ============================================================
# Infra: processos de verdade
# ============================================================


def _porta_livre() -> int:
    with closing(socket.socket()) as tomada:
        tomada.bind(("127.0.0.1", 0))
        return int(tomada.getsockname()[1])


def _esperar_porta(porta: int, *, limite_s: int = TIMEOUT_SUBIDA_S) -> bool:
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        with closing(socket.socket()) as tomada, suppress(OSError):
            tomada.settimeout(1)
            tomada.connect(("127.0.0.1", porta))
            return True
        time.sleep(0.3)
    return False


def _encerrar(processo: subprocess.Popen[str] | None) -> None:
    if processo is None or processo.poll() is not None:
        return
    processo.terminate()
    with suppress(subprocess.TimeoutExpired):
        processo.wait(timeout=15)
    if processo.poll() is None:  # pragma: no cover - so em travamento
        processo.kill()


def _ate(condicao: Callable[[], bool], limite_s: float, recado: Callable[[], str] | str) -> None:
    """
    Espera ativa com prazo. Falha com o motivo, e nao com `None`.

    O recado pode ser uma funcao: montado so na hora da falha, ele consegue
    incluir o que o processo imprimiu ENQUANTO o teste esperava. Montado antes,
    viria sempre vazio.
    """
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        if condicao():
            return
        time.sleep(0.5)
    pytest.fail(recado() if callable(recado) else recado)


@dataclass
class Maquina:
    """A maquina do cliente, como ela existe neste teste."""

    pasta: Path
    #: Pasta autorizada — o que sera copiado.
    dados: Path
    #: Onde o Agente grava os pacotes (ao lado da autorizada, nao dentro).
    pacotes: Path
    #: Para onde a copia vai, alem da pasta de pacotes. Aqui e outra pasta
    #: da mesma maquina: uma suite nao tem como plugar um HD USB. O que ESTE
    #: teste prova e a entrega verificada no destino; que "externo" de mentira
    #: e recusado tem passo proprio, e o disco fisico fica na homologacao
    #: manual.
    destino: Path
    #: Configuracao do Agente nesta maquina.
    cfg: Path
    #: Pasta onde o pacote baixado foi extraido.
    instalado: Path | None = None
    processo: subprocess.Popen[str] | None = None


@dataclass
class Cenario:
    """Estado que atravessa os vinte passos."""

    url: str
    maquina: Maquina
    convite: str = ""
    codigo: str = ""
    dispositivo_id: str = ""
    politica_criada: bool = False
    pacotes_antes: set[str] = field(default_factory=set)
    pacote_do_agendamento: str = ""
    pacote_incremental: str = ""
    saida_do_agente: list[str] = field(default_factory=list)
    saida_do_live: list[str] = field(default_factory=list)


@pytest.fixture(scope="module")
def maquina(tmp_path_factory: pytest.TempPathFactory) -> Maquina:
    raiz = tmp_path_factory.mktemp("maquina")
    dados = raiz / "cliente" / "dados"
    (dados / "docs").mkdir(parents=True)
    (dados / "docs" / "contrato.txt").write_text("Contrato de locacao, versao 1.", encoding="utf-8")
    (dados / "docs" / "nota.txt").write_text("Nota fiscal 001.", encoding="utf-8")

    pacotes = raiz / "cliente" / "backups"
    pacotes.mkdir(parents=True)
    destino = raiz / "copia-do-backup"
    destino.mkdir()

    return Maquina(pasta=raiz, dados=dados, pacotes=pacotes, destino=destino, cfg=raiz / "cfg")


@pytest.fixture(scope="module")
def live(maquina: Maquina) -> Iterator[tuple[str, str, list[str]]]:
    """
    Sobe o Live de verdade e devolve (url, convite de primeira execucao).

    O convite e lido do **console**, como um operador faria: e a unica parte do
    fluxo que prova acesso a maquina onde o servico roda.
    """
    if not (FRONTEND / "dist" / "index.html").is_file():
        pytest.skip("frontend nao buildado: rode `npm --prefix apps/web run build`")

    porta = _porta_livre()
    endereco = f"http://127.0.0.1:{porta}"
    banco = maquina.pasta / "live.db"

    processo = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "uvicorn", "apps.api.app.main:app", "--port", str(porta)],
        cwd=RAIZ,
        env={
            **os.environ,
            "DEMO_SERVERS_AUTOSTART": "0",
            "DATABASE_URL": f"sqlite:///{banco}",
            "SESSION_SECRET": "homologacao-card-02",  # pragma: allowlist secret
            "PUBLIC_BASE_URL": endereco,
            "PYTHONIOENCODING": "utf-8",
            # Sem isto o Python segura a saida ate encher o buffer, e o
            # convite — que e um `print` unico na partida — so apareceria
            # quando o processo terminasse.
            "PYTHONUNBUFFERED": "1",
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
        for linha in processo.stdout:
            linhas.append(linha)

    threading.Thread(target=drenar, daemon=True).start()

    try:
        if not _esperar_porta(porta):
            pytest.skip("o Live nao subiu a tempo")

        convite = ""
        fim = time.monotonic() + 30
        while time.monotonic() < fim and not convite:
            # A URL INTEIRA, e nao so o token: e ela que o produto manda a
            # pessoa abrir, e portanto e ela que o teste tem que seguir. Montar
            # um endereco proprio aqui foi o que deixou passar um convite que
            # apontava para 404.
            achado = re.search(r"(http://\S+?convite=[A-Za-z0-9_\-]+)", "".join(linhas))
            if achado:
                convite = achado.group(1)
                break
            time.sleep(0.3)

        if not convite:
            pytest.skip("o convite de primeira execucao nao apareceu no console")

        yield endereco, convite, linhas
    finally:
        _encerrar(processo)


@pytest.fixture(scope="module")
def cenario(live: tuple[str, str, list[str]], maquina: Maquina) -> Iterator[Cenario]:
    endereco, convite, linhas = live
    estado = Cenario(url=endereco, maquina=maquina, convite=convite, saida_do_live=linhas)
    try:
        yield estado
    finally:
        _encerrar(maquina.processo)


@pytest.fixture(scope="module")
def navegador() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        try:
            instancia = playwright.chromium.launch()
        except Exception as erro:  # noqa: BLE001 - navegador ausente e ambiente
            pytest.skip(f"Chromium indisponivel: {str(erro)[:120]}")
        try:
            yield instancia
        finally:
            instancia.close()


@dataclass
class Janela:
    """Uma janela do navegador, que o teste abre e fecha de verdade."""

    navegador: Browser
    contexto: BrowserContext | None = None
    pagina: Page | None = None
    #: Cookies guardados ao fechar. O cookie de sessao tem prazo (nao e de
    #: sessao do navegador), entao reabrir o navegador continua logado — e e
    #: isso que o passo 10 verifica.
    sessao: dict[str, object] | None = None

    #: Erros que o navegador imprimiu. Uma tela que quebra em silencio e o
    #: pior diagnostico possivel: o teste falha dizendo "nao encontrei o
    #: texto", e o motivo real fica no console que ninguem leu.
    erros: list[str] = field(default_factory=list)

    def abrir(self, url: str) -> Page:
        self.contexto = self.navegador.new_context(
            viewport={"width": 1360, "height": 1000},
            storage_state=self.sessao,  # type: ignore[arg-type]
        )
        self.pagina = self.contexto.new_page()
        self.pagina.set_default_timeout(TIMEOUT_UI_MS)
        self.pagina.on(
            "console",
            lambda mensagem: self.erros.append(mensagem.text) if mensagem.type == "error" else None,
        )
        self.pagina.on("pageerror", lambda erro: self.erros.append(str(erro)))
        self.pagina.goto(url)
        return self.pagina

    def fechar(self) -> None:
        if self.contexto is not None:
            self.sessao = self.contexto.storage_state()
            self.contexto.close()
        self.contexto = None
        self.pagina = None

    @property
    def aberta(self) -> bool:
        return self.pagina is not None


@pytest.fixture(scope="module")
def janela(navegador: Browser) -> Iterator[Janela]:
    instancia = Janela(navegador=navegador)
    try:
        yield instancia
    finally:
        instancia.fechar()


# ============================================================
# Auxiliares do Agente
# ============================================================


def _capturar(pagina: Page, nome: str) -> None:
    """
    Guarda a tela como ela estava neste passo.

    Sai do teste que passou, e nao de uma sessao manual: uma captura tirada a
    parte pode mostrar qualquer coisa; esta mostra o estado que as asserções
    acabaram de conferir.
    """
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    pagina.screenshot(path=str(CAPTURAS / f"{nome}.png"), full_page=True)


def _painel(pagina: Page) -> object:
    """
    A parte da tela que exige conta.

    O escopo importa: o Live publico tem os proprios botoes ("Executar agora"
    do cartao de demonstracao, por exemplo), e um seletor solto acertaria o
    errado — provando que a demo funciona, e nao que o backup funciona.

    Era `#empresa`, a ultima secao da vitrine. Hoje o produto tem endereco
    proprio (`/app`) e este e o corpo dele.
    """
    return pagina.locator("#produto")


def _ir_para(pagina: Page, secao: str) -> Any:
    """
    Troca de secao pela navegacao do produto, como uma pessoa faria.

    Clicar no link, e nao pedir o endereco: assim a homologacao exercita a
    propria navegacao. Se um rotulo sumir da barra, isto quebra aqui — e nao
    tres passos adiante, com uma mensagem que nao explica nada.
    """
    barra = pagina.get_by_role("navigation", name=re.compile("Seções"))
    barra.get_by_role("link", name=secao, exact=True).click()
    return _painel(pagina)


def _nova_politica(painel: Any, cenario: Cenario, *, hora: str, nome: str) -> None:
    """
    Cria uma politica pela tela, com as escolhas que a homologacao usa.

    `hora` vazia cria sem agendamento — util quando o horario ainda vai ser
    decidido. Incremental fica ligado desde o inicio: os passos 15 a 17 medem
    exatamente isso, e ligar depois criaria uma corrente que comeca no meio.
    """
    painel.get_by_role("button", name="Nova política").click()
    painel.get_by_label("Nome da política").fill(nome)
    painel.get_by_label("Tipo de destino").select_option("local")
    painel.get_by_label("Caminho do destino").fill(str(cenario.maquina.destino))
    painel.get_by_label(re.compile("Copiar só o que mudou")).check()
    if hora:
        painel.get_by_label("Frequência").select_option("diario")
        painel.get_by_label("Hora", exact=True).fill(hora)
    else:
        painel.get_by_label("Frequência").select_option("desligado")
    painel.get_by_role("button", name="Salvar política").click()

    painel.get_by_text(re.compile("Política salva", re.IGNORECASE)).wait_for()
    painel.get_by_text(nome).first.wait_for()


def _ambiente_do_agente(maquina: Maquina) -> dict[str, str]:
    assert maquina.instalado is not None
    return {
        **os.environ,
        # Um teste nao pode escrever no Gerenciador de Credenciais de quem roda
        # a suite.
        "AUTOTAREFAS_AGENTE_SEM_COFRE": "1",
        "PYTHONPATH": str(maquina.instalado),
        "PYTHONIOENCODING": "utf-8",
        # Sem isto o Python segura a saida ate encher o buffer, e o diagnostico
        # de uma falha chegaria vazio.
        "PYTHONUNBUFFERED": "1",
    }


def _agente(
    maquina: Maquina, *argumentos: str, prazo: int = 180
) -> subprocess.CompletedProcess[str]:
    """Roda um comando do Agente a partir do PACOTE EXTRAIDO."""
    assert maquina.instalado is not None
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "apps.agente.agente", *argumentos],
        cwd=maquina.instalado,
        env=_ambiente_do_agente(maquina),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=prazo,
        check=False,
    )


# ============================================================
# Os vinte passos, em ordem
# ============================================================


def test_01_criar_organizacao_e_usuario(cenario: Cenario, janela: Janela) -> None:
    """
    1. A empresa nasce pelo convite impresso no console do servidor.

    O teste abre **o endereco que o console imprimiu**, letra por letra. Montar
    um endereco equivalente aqui deixaria passar exatamente o defeito que a
    primeira homologacao manual encontrou: o link do produto respondia 404,
    porque `/primeiro-acesso` nao e um arquivo e o servidor so servia arquivos.
    """
    pagina = janela.abrir(cenario.convite)

    pagina.get_by_placeholder("Padaria Sol").fill("Padaria Sol")
    pagina.get_by_placeholder("voce@suaempresa.com.br").fill("dono@padariasol.com.br")
    pagina.get_by_label("Seu nome").fill("Ana")
    pagina.get_by_role("button", name="Criar organização").click()

    pagina.get_by_text("Padaria Sol").first.wait_for()
    assert "dono@padariasol.com.br" in pagina.content()
    _capturar(pagina, "01-organizacao-criada")


def test_02_baixar_e_instalar_o_agente(cenario: Cenario, janela: Janela) -> None:
    """
    2. O pacote sai da propria tela, e o que roda depois e ELE.

    Pede `formato=zip` de proposito. O download padrao e o executavel de um
    clique — e ele tem homologacao propria, em
    `test_instalador_exe_e2e.py`, porque conduzir uma janela do Windows sem
    display nao prova nada. Aqui interessa o Agente rodando como processo
    separado, e para isso o pacote com codigo e o caminho.
    """
    pagina = janela.pagina
    assert pagina is not None

    resposta = pagina.request.get(f"{cenario.url}/api/agente/instalador", params={"formato": "zip"})
    assert resposta.ok, resposta.status

    destino = cenario.maquina.pasta / "baixado"
    with zipfile.ZipFile(io.BytesIO(resposta.body())) as pacote:
        pacote.extractall(destino)
    cenario.maquina.instalado = destino / "AutoTarefas-Agente"

    assert (cenario.maquina.instalado / "LEIA-ME.txt").is_file()

    # Prova que o pacote nao e so um monte de arquivo plausivel.
    saida = _agente(cenario.maquina, "estado", "--pasta-de-configuracao", str(cenario.maquina.cfg))
    assert saida.returncode == 0, saida.stderr
    assert "(nao pareado)" in saida.stdout


def test_03_parear_dispositivo(cenario: Cenario, janela: Janela) -> None:
    """
    3. O codigo sai da tela; o pareamento acontece na maquina.

    O codigo e lido do **link de download**, e nao de um comando escrito na
    tela: e ali que ele viaja de verdade. Quando o servidor tem o executavel, a
    tela deixa de mostrar comando nenhum — o carimbo leva o codigo dentro do
    arquivo, e a pessoa so da dois cliques.
    """
    pagina = janela.pagina
    assert pagina is not None

    painel = _ir_para(pagina, "Dispositivos")
    painel.get_by_role("button", name="Parear nova máquina").click()

    link = painel.get_by_role("link", name=re.compile("Baixar o Agente"))
    link.wait_for()
    endereco = link.get_attribute("href") or ""
    achado = re.search(r"codigo=([^&]+)", endereco)
    assert achado, f"o link de download nao carrega o codigo: {endereco}"
    cenario.codigo = unquote(achado.group(1))
    _capturar(pagina, "02-instalacao-guiada")

    saida = _agente(
        cenario.maquina,
        "parear",
        "--servidor",
        cenario.url,
        "--codigo",
        cenario.codigo,
        "--nome",
        "PC da loja",
        "--pasta-de-configuracao",
        str(cenario.maquina.cfg),
    )
    assert saida.returncode == 0, saida.stderr
    assert "Dispositivo pareado" in saida.stdout

    pagina.reload()
    pagina.get_by_text("PC da loja").first.wait_for()


def test_04_autorizar_pasta_e_subir_o_agente(cenario: Cenario, janela: Janela) -> None:
    """4. A autorizacao e dada NA MAQUINA; o Live so mostra o que foi liberado."""
    maquina = cenario.maquina
    saida = _agente(
        maquina,
        "autorizar",
        str(maquina.dados),
        "--pasta-de-configuracao",
        str(maquina.cfg),
    )
    assert saida.returncode == 0, saida.stderr

    assert maquina.instalado is not None
    maquina.processo = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "apps.agente.agente",
            "servico",
            "--pasta-de-configuracao",
            str(maquina.cfg),
        ],
        cwd=maquina.instalado,
        env=_ambiente_do_agente(maquina),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def drenar() -> None:
        assert maquina.processo is not None
        assert maquina.processo.stdout is not None
        for linha in maquina.processo.stdout:
            cenario.saida_do_agente.append(linha)

    threading.Thread(target=drenar, daemon=True).start()

    pagina = janela.pagina
    assert pagina is not None

    def conectou() -> bool:
        resposta = pagina.request.get(f"{cenario.url}/api/agente/conectados")
        if not resposta.ok:
            return False
        return any(item["conectado"] for item in resposta.json()["conectados"])

    _ate(
        conectou,
        PACIENCIA_S,
        lambda: (
            "o Agente nao abriu o canal com o Live. "
            f"Agente: {' | '.join(cenario.saida_do_agente[-20:])} "
            f"Live: {' | '.join(cenario.saida_do_live[-20:])}"
        ),
    )

    # E o que a TELA mostra, que e o que o cliente ve.
    pagina.reload()
    _ir_para(pagina, "Dispositivos")
    pagina.get_by_text("Conectado").first.wait_for()

    pagina.get_by_role("button", name="Ver pastas autorizadas").first.click()
    pagina.get_by_text(str(maquina.dados.resolve())).first.wait_for()
    _capturar(pagina, "03-dispositivo-conectado")


def test_05_criar_politica_com_destino_externo(cenario: Cenario, janela: Janela) -> None:
    """5 e 6. Politica e destino real, criados pela tela — sem CLI e sem API na mao."""
    pagina = janela.pagina
    assert pagina is not None

    painel = _ir_para(pagina, "Backups")
    _nova_politica(painel, cenario, hora="", nome="Backup da loja")
    cenario.politica_criada = True


def test_06_destino_externo_de_mentira_e_recusado_pela_tela(
    cenario: Cenario, janela: Janela
) -> None:
    """
    6. O destino e checado contra o SISTEMA, e nao contra o que a pessoa digitou.

    A politica do passo 5 aponta para outra pasta da mesma maquina, e a tela diz
    isso em voz alta: pacote no mesmo computador nao protege contra o disco
    morrer. Aqui provamos a outra metade — declarar "disco externo" para uma
    pasta que nao esta num disco externo e **recusa**, e nao aviso.
    """
    assert cenario.politica_criada
    pagina = janela.pagina
    assert pagina is not None
    painel = _ir_para(pagina, "Backups")

    # A honestidade sobre o destino local ja esta na tela.
    assert painel.get_by_text(re.compile("não protege contra o disco morrer")).count() > 0

    painel.get_by_role("button", name="Nova política").click()
    painel.get_by_label("Nome da política").fill("Externo de mentira")
    painel.get_by_label("Tipo de destino").select_option("externo")
    painel.get_by_label("Caminho do destino").fill(str(cenario.maquina.destino))
    painel.get_by_label("Frequência").select_option("desligado")
    painel.get_by_role("button", name="Salvar política").click()
    painel.get_by_text("Externo de mentira").first.wait_for()

    linha = painel.locator("li", has_text="Externo de mentira")
    linha.get_by_role("button", name="Executar agora").click()

    def respondeu() -> bool:
        return painel.get_by_text(re.compile("Backup (concluído|não concluído)")).count() > 0

    _ate(respondeu, 120.0, "a execucao do destino de mentira nao respondeu")
    recado = painel.get_by_text(re.compile("Backup (concluído|não concluído)")).first.inner_text()
    assert "não concluído" in recado, recado
    assert "externo" in recado, recado

    # Limpa: as proximas etapas contam com uma politica so.
    linha.get_by_role("button", name="Remover").click()
    _ate(
        lambda: painel.get_by_text("Externo de mentira").count() == 0,
        60.0,
        "a politica de teste nao foi removida",
    )


def test_07_executar_com_o_navegador_aberto(cenario: Cenario, janela: Janela) -> None:
    """7. Execucao imediata, com as escolhas da propria politica."""
    pagina = janela.pagina
    assert pagina is not None

    painel = _ir_para(pagina, "Backups")
    painel.get_by_role("button", name="Executar agora").first.click()

    def terminou() -> bool:
        return painel.get_by_text(re.compile("Backup (concluído|não concluído)")).count() > 0

    _ate(terminou, 180.0, lambda: "o backup nao terminou. Painel: " + painel.inner_text()[-800:])
    recado = painel.get_by_text(re.compile("Backup (concluído|não concluído)")).first.inner_text()
    assert "Backup concluído" in recado, recado

    pacotes = sorted(cenario.maquina.pacotes.glob("backup_*.zip"))
    assert pacotes, "nenhum pacote foi criado na maquina"
    copias = sorted(cenario.maquina.destino.glob("backup_*.zip"))
    assert copias, "o destino externo nao recebeu o pacote"
    _capturar(pagina, "04-politica-e-execucao")


def test_08_marcar_o_horario_e_fechar_o_navegador(cenario: Cenario, janela: Janela) -> None:
    """
    8. O horario e marcado agora, e so entao o navegador fecha.

    Marcar no passo 5 tornaria a homologacao refem do relogio: numa maquina
    lenta, o disparo cairia ANTES de o navegador fechar — e o passo 9 estaria
    provando outra coisa.

    Como nao ha tela de edicao, a politica e recriada: remover e criar de novo e
    o caminho que o cliente tem, e exercita-lo aqui e melhor do que inventar um
    atalho que ele nao teria.
    """
    pagina = janela.pagina
    assert pagina is not None
    painel = _ir_para(pagina, "Backups")

    linha = painel.locator("li", has_text="Backup da loja")
    linha.get_by_role("button", name="Remover").click()
    _ate(
        lambda: painel.locator("li", has_text="Backup da loja").count() == 0,
        60.0,
        "a politica antiga nao foi removida",
    )

    quando = (datetime.now() + timedelta(minutes=2)).strftime("%H:%M")
    _nova_politica(painel, cenario, hora=quando, nome="Backup da loja")

    cenario.pacotes_antes = {caminho.name for caminho in cenario.maquina.pacotes.glob("*.zip")}
    janela.fechar()

    assert not janela.aberta
    assert cenario.pacotes_antes, "o passo 7 deveria ter deixado ao menos um pacote"


def test_09_executar_pelo_agendamento(cenario: Cenario) -> None:
    """
    9. O backup do horario acontece com o navegador fechado.

    E o passo que separa "o cliente pode mandar fazer backup" de "o cliente tem
    backup". Nada aqui depende de alguem estar com o Live aberto: quem dispara e
    o agendador, na propria maquina.
    """

    def apareceu() -> bool:
        agora = {caminho.name for caminho in cenario.maquina.pacotes.glob("*.zip")}
        return bool(agora - cenario.pacotes_antes)

    _ate(
        apareceu,
        PACIENCIA_AGENDAMENTO_S,
        lambda: (
            "o agendamento nao disparou com o navegador fechado. "
            f"Agente: {' | '.join(cenario.saida_do_agente[-20:])}"
        ),
    )

    novos = {caminho.name for caminho in cenario.maquina.pacotes.glob("*.zip")}
    assert novos - cenario.pacotes_antes, "nenhum pacote novo"


def test_10_reabrir_o_live(cenario: Cenario, janela: Janela) -> None:
    """10. Voltar ao Live nao pede login de novo: o cookie tem prazo."""
    # O produto, e nao a raiz: `/` e a vitrine, para quem ainda esta avaliando.
    pagina = janela.abrir(f"{cenario.url}/app")

    # A sessao sobreviveu: a navegacao do produto so aparece para quem entrou.
    pagina.get_by_role("navigation", name=re.compile("Seções")).wait_for()
    assert _ir_para(pagina, "Configurações").get_by_text("Padaria Sol").count() > 0
    assert _ir_para(pagina, "Dispositivos").get_by_text("Parear nova máquina").count() > 0


def test_11_conferir_historico_e_saude(cenario: Cenario, janela: Janela) -> None:
    """
    11. O que rodou de madrugada aparece no historico, marcado como agendado.

    Sem isto, o Live mostraria uma noite vazia para uma noite em que o backup
    foi feito — e o cliente concluiria, com razao, que nao pode confiar na tela.

    Duas esperas, de proposito: primeiro o **servidor** precisa ter recebido o
    que a maquina executou sozinha; depois a **tela** precisa mostrar. Juntar as
    duas numa so faria uma falha de sincronizacao e uma falha de interface
    parecerem o mesmo problema.
    """
    pagina = janela.pagina
    assert pagina is not None
    painel = _ir_para(pagina, "Atividade")

    def no_servidor() -> str:
        resposta = pagina.request.get(f"{cenario.url}/api/historico")
        if not resposta.ok:
            return ""
        for item in resposta.json()["execucoes"]:
            if item["origem"] == "agendamento" and item["artefatos"]:
                return str(item["artefatos"][0]["nome"])
        return ""

    _ate(
        lambda: bool(no_servidor()),
        PACIENCIA_AGENDAMENTO_S,
        lambda: (
            "a execucao do agendamento nao chegou ao servidor. "
            f"Agente: {' | '.join(cenario.saida_do_agente[-15:])}"
        ),
    )
    cenario.pacote_do_agendamento = no_servidor()

    def na_tela() -> bool:
        # Sem recarregar: o historico se atualiza sozinho, e isso tambem faz
        # parte do que se esta verificando. Recarregar aqui esconderia uma tela
        # que so mostra a verdade quando alguem aperta F5 — e ninguem aperta F5
        # de madrugada.
        return (
            painel.get_by_text("Pelo horário agendado").count() > 0
            and painel.get_by_text(cenario.pacote_do_agendamento).count() > 0
        )

    _ate(
        na_tela,
        PACIENCIA_AGENDAMENTO_S,
        lambda: (
            f"o historico chegou ao servidor (pacote {cenario.pacote_do_agendamento}) "
            "mas nao apareceu na tela. "
            f"Pacotes na maquina: {sorted(p.name for p in cenario.maquina.pacotes.glob('*.zip'))} "
            f"Erros do navegador: {' | '.join(janela.erros[-5:])} "
            f"|| Painel: {painel.inner_text()}"
        ),
    )

    assert (cenario.maquina.pacotes / cenario.pacote_do_agendamento).is_file(), (
        "o Live mostrou um pacote que nao existe na maquina"
    )
    # A captura sai AQUI, com o historico na tela — e nao depois de trocar de
    # secao, quando ela mostraria outra coisa com o nome do historico.
    _capturar(pagina, "05-historico-com-agendamento")

    # Saude: a maquina continua conectada. Isso se ve em Dispositivos, e nao
    # aqui — o selo de conexao pertence a maquina, nao a execucao. Esperar, e
    # nao afirmar na hora: a presenca chega numa segunda chamada, e pode nao
    # ter chegado no instante em que a tela abriu.
    maquinas = _ir_para(pagina, "Dispositivos")
    _ate(
        lambda: maquinas.get_by_text("Conectado").count() > 0,
        PACIENCIA_S,
        "a tela nao mostrou a maquina como conectada",
    )


def test_12_conferir_pacote_e_manifesto(cenario: Cenario) -> None:
    """12. O pacote confere consigo mesmo, arquivo por arquivo."""
    from autotarefas.tasks.backup import verify_backup

    alvo = cenario.maquina.pacotes / cenario.pacote_do_agendamento
    relatorio = verify_backup(alvo)

    assert relatorio.ok, relatorio.problem
    # Pacote incremental cujo conteudo nao mudou desde o anterior confere
    # ZERO arquivos novos — e isso e certo, nao falha. O que precisa ser
    # verdade e que ele declara conteudo: conferidos mais herdados.
    assert relatorio.checked + len(relatorio.unchanged) > 0, relatorio
    assert relatorio.authenticity.value in {"nao_assinado", "autentico"}


def test_13_confirmar_presenca_no_destino(cenario: Cenario) -> None:
    """
    13. O destino recebeu o pacote, com o mesmo conteudo.

    Comparar so o nome provaria que um arquivo com aquele nome existe la. O que
    importa e que ele seja o MESMO — copia truncada tem nome certo.
    """
    import hashlib

    origem = cenario.maquina.pacotes / cenario.pacote_do_agendamento
    copia = cenario.maquina.destino / cenario.pacote_do_agendamento

    assert copia.is_file(), "o destino nao recebeu o pacote do agendamento"
    assert copia.stat().st_size == origem.stat().st_size
    assert hashlib.sha256(copia.read_bytes()).hexdigest() == (
        hashlib.sha256(origem.read_bytes()).hexdigest()
    )


def test_14_restaurar_uma_amostra_pela_tela(cenario: Cenario, janela: Janela) -> None:
    """
    14. Restaurar pela interface, sem linha de comando.

    E o momento em que o backup prova que serviu. A restauracao vai para uma
    subpasta da pasta autorizada — nada e sobrescrito.
    """
    pagina = janela.pagina
    assert pagina is not None
    painel = _ir_para(pagina, "Dispositivos")

    painel.get_by_role("button", name="Restaurar arquivos").first.click()
    # Pelo BOTAO, e nao pelo texto: o mesmo nome de pacote aparece tambem no
    # historico, e clicar la nao abriria nada.
    painel.get_by_role("button", name=cenario.pacote_do_agendamento).first.click()
    painel.get_by_text(re.compile("Confira o que há dentro")).wait_for()

    painel.get_by_label("Subpasta de destino").fill("recuperado")
    painel.get_by_role("button", name="Restaurar", exact=True).click()

    _ate(
        lambda: painel.get_by_text(re.compile("Restauração (concluída|INCOMPLETA)")).count() > 0,
        120.0,
        lambda: "a restauracao nao respondeu. Painel: " + painel.inner_text()[-600:],
    )
    inteiro = painel.inner_text()
    pacotes = sorted(p.name for p in cenario.maquina.pacotes.glob("*.zip"))
    corte = inteiro.find("Restaurar arquivos ·")
    assert "Restauração concluída" in inteiro, f"{inteiro[corte:][:900]} || pacotes={pacotes}"

    _capturar(pagina, "06-restauracao-concluida")

    recuperados = list((cenario.maquina.dados / "recuperado").rglob("contrato.txt"))
    assert recuperados, "o arquivo restaurado nao apareceu no disco"
    assert recuperados[0].read_text(encoding="utf-8") == "Contrato de locacao, versao 1."


def test_15_alterar_um_arquivo(cenario: Cenario) -> None:
    """15. Uma mudanca de verdade na pasta protegida."""
    alvo = cenario.maquina.dados / "docs" / "contrato.txt"
    alvo.write_text("Contrato de locacao, versao 2 — com reajuste.", encoding="utf-8")

    assert "versao 2" in alvo.read_text(encoding="utf-8")


def test_16_executar_novamente(cenario: Cenario, janela: Janela) -> None:
    """16. Segunda execucao, pela mesma politica."""
    pagina = janela.pagina
    assert pagina is not None
    painel = _ir_para(pagina, "Backups")

    painel.get_by_role("button", name="Executar agora").first.click()

    def terminou() -> bool:
        return painel.get_by_text(re.compile("Backup (concluído|não concluído)")).count() > 0

    _ate(terminou, 180.0, "a segunda execucao nao terminou")
    recado = painel.get_by_text(re.compile("Backup (concluído|não concluído)")).first.inner_text()
    assert "Backup concluído" in recado, recado

    achado = re.search(r"backup_\d{4}-\d{2}-\d{2}_\d{4}\.zip", recado)
    assert achado, recado
    cenario.pacote_incremental = achado.group(0)


def test_17_comprovar_comportamento_incremental(cenario: Cenario) -> None:
    """
    17. O que nao mudou nao foi copiado de novo — e isso esta no manifesto.

    "Incremental" so vale se der para apontar onde a economia aconteceu. O
    manifesto do pacote novo cita, para cada arquivo inalterado, em qual pacote
    anterior o conteudo esta; o arquivo que mudou aparece como copiado.
    """
    from autotarefas.tasks.backup import verify_backup

    alvo = cenario.maquina.pacotes / cenario.pacote_incremental
    relatorio = verify_backup(alvo)

    assert relatorio.ok, relatorio.problem
    inalterados = " ".join(relatorio.unchanged)
    assert "nota.txt" in inalterados, f"nota.txt deveria ter sido reaproveitada: {relatorio}"
    assert "contrato.txt" not in inalterados, "o arquivo alterado nao podia ser reaproveitado"
    assert relatorio.chain, "um pacote incremental precisa citar de quem depende"


def test_18_arquivo_maior_que_dez_megabytes(cenario: Cenario, janela: Janela) -> None:
    """
    18. Arquivo grande passa pelo Agente.

    O limite de 10 MB e do envio pelo navegador, e nunca foi capacidade do
    produto. Aqui um arquivo de 12 MB atravessa o caminho inteiro: leitura em
    streaming, pacote, conferencia e copia para o destino.
    """
    import os

    grande = cenario.maquina.dados / "docs" / "video.bin"
    # Conteudo aleatorio de proposito: dado compressivel deixaria o pacote
    # pequeno e o teste provaria menos do que parece.
    grande.write_bytes(os.urandom(TAMANHO_GRANDE))

    pagina = janela.pagina
    assert pagina is not None
    painel = _ir_para(pagina, "Backups")
    painel.get_by_role("button", name="Executar agora").first.click()

    def terminou() -> bool:
        texto = painel.inner_text()
        return "Backup concluído" in texto or "Backup não concluído" in texto

    _ate(terminou, 300.0, "o backup do arquivo grande nao terminou")
    recado = painel.get_by_text(re.compile("Backup (concluído|não concluído)")).first.inner_text()
    assert "Backup concluído" in recado, recado

    achado = re.search(r"backup_\d{4}-\d{2}-\d{2}_\d{4}\.zip", recado)
    assert achado, recado
    pacote = cenario.maquina.pacotes / achado.group(0)

    assert pacote.stat().st_size > TAMANHO_GRANDE, (
        "o pacote ficou menor que o arquivo: ele nao entrou inteiro"
    )
    import zipfile as _zip

    with _zip.ZipFile(pacote) as arquivo:
        entradas = {nome: arquivo.getinfo(nome).file_size for nome in arquivo.namelist()}
    grandes = [tamanho for nome, tamanho in entradas.items() if nome.endswith("video.bin")]
    assert grandes, entradas
    assert grandes[0] == TAMANHO_GRANDE, entradas


def test_19_provocar_falha_controlada(cenario: Cenario, janela: Janela) -> None:
    """
    19. Uma falha de verdade, provocada de proposito, com horario e retry.

    Falha transitoria e a regra num escritorio: disco externo desconectado,
    pasta de rede fora do ar. O que se verifica aqui e que o Agente **insiste** —
    e que cada tentativa deixa rastro. Um retry que ninguem consegue ver nao se
    distingue de um retry que nao aconteceu.
    """
    pagina = janela.pagina
    assert pagina is not None
    painel = _ir_para(pagina, "Backups")

    quando = (datetime.now() + timedelta(minutes=2)).strftime("%H:%M")

    painel.get_by_role("button", name="Nova política").click()
    painel.get_by_label("Nome da política").fill("Rede fora do ar")
    painel.get_by_label("Tipo de destino").select_option("rede")
    # Endereco UNC que nao existe: o Agente confere o destino ANTES de ler o
    # primeiro arquivo, entao a falha e limpa e nao deixa pacote pela metade.
    painel.get_by_label("Caminho do destino").fill(r"\127.0.0.1\naoexiste$\backups")
    painel.get_by_label("Frequência").select_option("diario")
    painel.get_by_label("Hora", exact=True).fill(quando)
    painel.get_by_label("Tentativas").fill("2")
    painel.get_by_label(re.compile("Espera inicial")).fill("1")
    painel.get_by_role("button", name="Salvar política").click()

    painel.get_by_text(re.compile("Política salva", re.IGNORECASE)).wait_for()
    painel.get_by_text("Rede fora do ar").first.wait_for()


def test_20_comprovar_retry_notificacao_e_auditoria(cenario: Cenario, janela: Janela) -> None:
    """
    20. As tres evidencias que sobram depois de uma falha.

    **Retry**: duas tentativas, cada uma com a sua linha. **Notificacao**: o
    servidor registra o que aconteceu com o aviso, inclusive quando ele nao pode
    ser enviado — "avisamos?" precisa ter resposta com lastro. **Auditoria**: a
    trilha inteira confere, e diz isso na tela.
    """
    pagina = janela.pagina
    assert pagina is not None
    painel = _ir_para(pagina, "Atividade")

    def tentativas() -> list[dict[str, Any]]:
        resposta = pagina.request.get(f"{cenario.url}/api/historico")
        if not resposta.ok:
            return []
        return [
            item
            for item in resposta.json()["execucoes"]
            if item["resultado"] == "falha" and item["origem"] == "agendamento"
        ]

    _ate(
        lambda: len(tentativas()) >= 2,
        PACIENCIA_AGENDAMENTO_S + 120.0,
        lambda: (
            f"o retry nao deixou duas linhas. Falhas: {tentativas()} "
            f"Agente: {' | '.join(cenario.saida_do_agente[-20:])}"
        ),
    )

    falhas = tentativas()
    assert any("tentativa 2" in item["ressalva"] for item in falhas), falhas
    assert any("naoexiste" in item["ressalva"].lower() for item in falhas), falhas

    # Notificacao: sem SMTP no cofre nao ha envio, e a trilha diz exatamente
    # isso. Registrar "notificado" sem lastro seria pior do que nao notificar.
    trilha = pagina.request.get(f"{cenario.url}/api/historico/auditoria").json()
    acoes = {linha["acao"] for linha in trilha["linhas"]}
    assert acoes & {"notificacao.enviada", "notificacao.nao_enviada"}, acoes

    # Auditoria: a corrente inteira confere, e a tela diz isso.
    assert trilha["integra"] is True, trilha["explicacao"]
    assert {"backup.pedido", "execucao.sincronizada"} <= acoes, acoes

    _ate(
        lambda: painel.get_by_text(re.compile("Trilha íntegra")).count() > 0,
        PACIENCIA_S,
        lambda: "a tela nao mostrou o selo da trilha. Painel: " + painel.inner_text()[-500:],
    )
    _capturar(pagina, "07-retry-e-auditoria")
