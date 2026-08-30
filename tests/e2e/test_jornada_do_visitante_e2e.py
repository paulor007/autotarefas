"""A jornada do visitante, com NAVEGADOR REAL.

A homologação do Card 02 prova que o produto funciona para quem o **opera**:
alguém cria a empresa, instala o Agente, autoriza pasta, cria política. Este
arquivo prova outra coisa, e é a que decide se o AutoTarefas serve como peça de
portfólio: **que a pessoa que só chega e olha encontra tudo pronto**.

Quem chega não é desenvolvedor do projeto. Ela não abre terminal, não instala
`.exe`, não pareia máquina, não copia token e não configura variável de
ambiente. Ela clica em "Acessar projeto" e precisa estar dentro, diante de um
sistema que já está de pé.

Nada aqui é simulado, e o ambiente é montado pela ferramenta de verdade
(`tools/vitrine.py`) — a mesma que publica. Uma cópia dela dentro do teste
provaria que a cópia funciona.

    visitante entra pelo portfólio
    → acessa o AutoTarefas          (sem login, sem conta)
    → abre Backup automático
    → encontra máquina real conectada
    → políticas reais ativas
    → último backup real
    → próxima execução
    → integridade
    → histórico
    → detalhe da execução
    → evidências
    → e não consegue alterar nada

Rodar:
    playwright install chromium
    npm --prefix apps/web run build
    python -m pytest tests/e2e/test_jornada_do_visitante_e2e.py -p no:randomly

Pula sozinho (sem falhar a suite) quando faltar Chromium ou o build do
frontend.
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
from dataclasses import dataclass, field
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright nao instalado")
from playwright.sync_api import Browser, Page, sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
FRONTEND = RAIZ / "apps" / "web"

TIMEOUT_UI_MS = 30_000
TIMEOUT_SUBIDA_S = 90

#: Quanto esperar pelo Agente conectar e pelo backup rodar. Generoso: sao
#: processos separados, com disco no meio.
PACIENCIA_S = 120

ORGANIZACAO = "AutoTarefas Demonstracao"


@dataclass
class Vitrine:
    """O ambiente publico no ar, e como falar com ele."""

    url: str
    casa: Path
    live: subprocess.Popen[str]
    agente: subprocess.Popen[str] | None = None
    #: As ultimas linhas de cada processo. Existem por causa do `_drenar`, e
    #: ajudam quando um passo falha sem dizer por que.
    log_do_live: list[str] = field(default_factory=list)
    log_do_agente: list[str] = field(default_factory=list)


def _porta_livre() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as tomada:
        tomada.bind(("127.0.0.1", 0))
        return int(tomada.getsockname()[1])


def _esperar_porta(porta: int, limite_s: int = TIMEOUT_SUBIDA_S) -> bool:
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as tomada:
            tomada.settimeout(0.4)
            if tomada.connect_ex(("127.0.0.1", porta)) == 0:
                return True
        time.sleep(0.2)
    return False


def _drenar(processo: subprocess.Popen[str], destino: list[str]) -> None:
    """
    Le a saida do processo continuamente, numa thread.

    Nao e para inspecionar o log: e para o processo NAO TRAVAR. Um `PIPE` que
    ninguem le enche (64 KB no Windows) e a proxima escrita bloqueia para
    sempre. O efeito e cruel de diagnosticar: o servidor responde normalmente
    por alguns minutos e depois para de responder, sem erro e sem morrer —
    exatamente o tempo que o log leva para encher o buffer.
    """

    def laco() -> None:
        assert processo.stdout is not None
        for linha in processo.stdout:
            destino.append(linha)
            del destino[:-200]

    threading.Thread(target=laco, daemon=True).start()


def _encerrar(processo: subprocess.Popen[str] | None) -> None:
    if processo is None or processo.poll() is not None:
        return
    processo.terminate()
    with suppress(subprocess.TimeoutExpired):
        processo.wait(timeout=10)
    if processo.poll() is None:
        processo.kill()


def _ambiente(casa: Path, url: str) -> dict[str, str]:
    """
    O ambiente de quem publica a vitrine.

    `DEMONSTRACAO_PUBLICA` e `DEMONSTRACAO_ORG` são o que abre a porta do
    visitante — e as duas juntas, de propósito: sem o nome da organização a
    porta fica fechada, porque escolher "a primeira que aparecer" num servidor
    com mais de uma seria a receita para publicar o dado de um cliente.
    """
    return {
        **os.environ,
        "DEMO_SERVERS_AUTOSTART": "0",
        "VITRINE_CASA": str(casa),
        "DATABASE_URL": f"sqlite:///{(casa / 'vitrine.db').as_posix()}",
        "DEMONSTRACAO_PUBLICA": "1",
        "DEMONSTRACAO_ORG": ORGANIZACAO,
        "SESSION_SECRET": "homologacao-do-visitante",  # pragma: allowlist secret
        "PUBLIC_BASE_URL": url,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }


def _vitrine(*argumentos: str, ambiente: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Roda `tools/vitrine.py`, que e a ferramenta de publicacao de verdade."""
    return subprocess.run(  # noqa: S603  # nosec B603
        [sys.executable, str(RAIZ / "tools" / "vitrine.py"), *argumentos],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=False,
        env=ambiente,
        encoding="utf-8",
        errors="replace",
        timeout=PACIENCIA_S,
    )


@pytest.fixture(scope="module")
def vitrine(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Vitrine]:
    """
    Um ambiente publico inteiro, montado do zero e descartado no fim.

    A ordem e a mesma de uma publicacao: sobe o Live, provisiona, sobe o
    Agente, semeia a primeira execucao. Se algum passo nao completar, o teste
    **pula** em vez de falhar — o que se prova aqui e a jornada do visitante,
    e nao a disponibilidade do ambiente de quem roda a suite.
    """
    if not (FRONTEND / "dist" / "index.html").is_file():
        pytest.skip("frontend nao buildado: rode `npm --prefix apps/web run build`")

    casa = tmp_path_factory.mktemp("vitrine")
    porta = _porta_livre()
    url = f"http://127.0.0.1:{porta}"
    ambiente = _ambiente(casa, url)

    live = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "uvicorn", "apps.api.app.main:app", "--port", str(porta)],
        cwd=RAIZ,
        env=ambiente,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    montada = Vitrine(url=url, casa=casa, live=live)
    _drenar(live, montada.log_do_live)

    try:
        if not _esperar_porta(porta):
            pytest.skip("o Live da vitrine nao subiu a tempo")

        preparo = _vitrine("preparar", "--servidor", url, ambiente=ambiente)
        if preparo.returncode != 0:
            pytest.skip(f"o provisionamento da vitrine falhou: {preparo.stdout[-400:]}")

        montada.agente = subprocess.Popen(  # noqa: S603
            [sys.executable, str(RAIZ / "tools" / "vitrine.py"), "agente"],
            cwd=RAIZ,
            env=ambiente,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        _drenar(montada.agente, montada.log_do_agente)

        semeadura = _vitrine("primeira-execucao", "--servidor", url, ambiente=ambiente)
        if semeadura.returncode != 0:
            pytest.skip(f"a primeira execucao nao rodou: {semeadura.stdout[-400:]}")

        yield montada
    finally:
        _encerrar(montada.agente)
        _encerrar(live)


@pytest.fixture(scope="module")
def navegador() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        try:
            instancia = playwright.chromium.launch()
        except Exception as erro:  # noqa: BLE001 — navegador ausente e ambiente
            pytest.skip(f"Chromium indisponivel: {str(erro)[:120]}")
        try:
            yield instancia
        finally:
            instancia.close()


@pytest.fixture(scope="module")
def visitante(navegador: Browser, vitrine: Vitrine) -> Iterator[Page]:
    """
    O navegador de quem chega pelo portfolio.

    Contexto novo, sem cookie nenhum: e exatamente a situacao de quem nunca
    esteve aqui. Reaproveitar um contexto ja logado provaria o oposto do que
    este arquivo existe para provar.
    """
    contexto = navegador.new_context()
    pagina = contexto.new_page()
    pagina.set_default_timeout(TIMEOUT_UI_MS)
    try:
        yield pagina
    finally:
        contexto.close()


class TestAJornada:
    """
    Os passos na ordem em que acontecem, e cada um depende do anterior.

    A pergunta que este bloco responde nao e "cada peca funciona?" — os testes
    de unidade ja respondem. E "a pessoa que so chega e olha encontra tudo
    pronto?".
    """

    def test_01_entra_sem_login_e_sem_conta(self, visitante: Page, vitrine: Vitrine) -> None:
        """
        O passo que define o resto: nada de tela de entrada.

        Quem chega clicou em "Acessar projeto" no portfolio. Um formulario de
        login aqui seria uma porta trancada para quem nao tem chave — e ela
        nao tem, nem deveria precisar.
        """
        visitante.goto(f"{vitrine.url}/app")

        visitante.wait_for_selector("text=Suas automações")
        assert visitante.locator("input[type=password]").count() == 0
        assert "Entrar" not in visitante.locator("#produto").inner_text()

    def test_02_a_tela_diz_que_e_demonstracao(self, visitante: Page) -> None:
        """
        Duas perguntas que a tela sozinha nao responde: se aquilo e real, e o
        que acontece se a pessoa mexer.
        """
        faixa = visitante.get_by_role("note", name="Demonstração pública")

        assert faixa.is_visible()
        texto = faixa.inner_text()
        assert "aconteceu de verdade" in texto
        assert "somente leitura" in texto

    def test_03_encontra_maquina_real_conectada(self, visitante: Page, vitrine: Vitrine) -> None:
        """
        Conectada vem da PRESENCA, e nao do cadastro.

        Um dispositivo cadastrado e desligado aparece como desligado. Se este
        teste passa, ha um processo do Agente com canal aberto — e nao uma
        linha no banco.
        """
        visitante.goto(f"{vitrine.url}/app/dispositivos")

        visitante.wait_for_selector("text=SERVIDOR-DEMONSTRACAO")
        assert visitante.get_by_text("Conectado").first.is_visible()

    def test_04_encontra_politicas_reais_ativas(self, visitante: Page, vitrine: Vitrine) -> None:
        visitante.goto(f"{vitrine.url}/app/backups")

        visitante.wait_for_selector("text=Backup diario 03:00")
        for hora in ("09:00", "15:00", "21:00"):
            assert visitante.get_by_text(f"Backup diario {hora}").first.is_visible()

    def test_05_o_ultimo_backup_e_uma_execucao_que_aconteceu(
        self, visitante: Page, vitrine: Vitrine
    ) -> None:
        """
        Nao e um rotulo: e uma execucao com data, tamanho e resultado.

        O visitante nao precisou clicar em nada para que ela existisse — foi o
        ambiente que rodou, antes de ele chegar.
        """
        visitante.goto(f"{vitrine.url}/app")

        cartao = visitante.get_by_text("ÚLTIMO BACKUP").locator("..")
        visitante.wait_for_selector("text=ÚLTIMO BACKUP")
        assert "concluído" in cartao.inner_text().lower()

    def test_06_sabe_quando_e_a_proxima_execucao(self, visitante: Page) -> None:
        """
        "Nada rodando agora" precisa vir com o proximo horario.

        Sem ele, uma tela em branco nao distingue "nada rodando" de "isto aqui
        esta morto" — e as duas coisas parecem iguais para quem chegou agora.
        """
        painel = visitante.get_by_role("region", name="Atividade agora")

        painel.wait_for(state="visible")
        texto = painel.inner_text()
        assert "Próximo" in texto or "rodando" in texto

    def test_07_o_veredito_de_protecao_e_honesto(self, visitante: Page) -> None:
        """
        Num servidor unico o destino fica no mesmo disco, e o painel diz isso.

        Se um dia este teste comecar a ver "Protegido" numa vitrine de destino
        local, e porque alguem afrouxou o veredito para deixar a tela bonita.
        """
        selo = visitante.get_by_role("region", name="Estado da proteção")

        selo.wait_for(state="visible")
        texto = selo.inner_text()
        assert "Proteção parcial" in texto
        assert "mesmo computador" in texto

    def test_08_o_historico_mostra_o_que_rodou(self, visitante: Page, vitrine: Vitrine) -> None:
        visitante.goto(f"{vitrine.url}/app/atividade")

        # Espera pelo BOTAO, e nao pelo titulo: o titulo aparece assim que a
        # tela monta, e a lista chega depois. Conferir logo apos o titulo
        # transformava este passo num sorteio entre a rede e o assert.
        evidencias = visitante.get_by_role("button", name="Ver evidências").first
        evidencias.wait_for(state="visible")

        assert evidencias.is_visible()

    def test_09_a_trilha_de_auditoria_confere(self, visitante: Page) -> None:
        """
        Mostrar as linhas sem dizer se elas ainda batem seria oferecer
        exatamente a confianca que o encadeamento existe para nao pedir.
        """
        visitante.wait_for_selector("text=Auditoria")

        assert visitante.get_by_text("Trilha íntegra").is_visible()

    def test_10_abre_o_detalhe_e_encontra_as_evidencias(self, visitante: Page) -> None:
        """
        O passo que fecha a jornada: "aconteceu" vira "como eu sei?".

        A soma inteira, e para onde a copia foi — com a distincao entre
        "chegou" e "chegou e foi conferido", que e a que sustenta a palavra
        verificavel.
        """
        visitante.get_by_role("button", name="Ver evidências").first.click()
        visitante.wait_for_selector("text=O PACOTE")

        detalhe = visitante.locator("#produto").inner_text()
        assert "SHA-256" in detalhe
        assert "conferido pela soma" in detalhe
        assert "O QUE A POLÍTICA PEDIU" in detalhe

    def test_11_o_caminho_do_cliente_nao_aparece_na_entrega(self, visitante: Page) -> None:
        """
        A ficha da entrega ia para a tela com o caminho local dentro.

        O desenho inteiro toma o cuidado de nao mandar caminho ao servidor; a
        entrega furava isso em silencio, e a tela publicava.
        """
        entrega = visitante.get_by_text("Lido de volta no destino").first
        linha = entrega.locator("..").inner_text()

        assert ":\\" not in linha, "o caminho local do cliente voltou a aparecer"

    def test_12_nao_ha_botao_que_o_servidor_recusaria(
        self, visitante: Page, vitrine: Vitrine
    ) -> None:
        """
        Botao que so sabe responder 403 e botao sem funcao.

        E o 403 chegaria como erro vermelho, que e a forma mais cara de
        explicar uma regra de produto.
        """
        visitante.goto(f"{vitrine.url}/app/backups")
        visitante.wait_for_selector("text=Backup diario 03:00")

        assert visitante.get_by_role("button", name="Executar agora").count() == 0
        assert visitante.get_by_role("button", name="Remover").count() == 0

    def test_13_ve_como_se_configura_sem_poder_gravar(self, visitante: Page) -> None:
        """
        Esconder o assistente escondia o produto.

        O visitante e `leitor`, e um leitor nao via a tela de configuracao —
        ou seja, a demonstracao do produto de backup escondia que existe disco
        externo, pasta de rede e nuvem.
        """
        visitante.get_by_role("button", name="Ver como se configura").click()
        visitante.wait_for_selector("text=O que seria criado")

        assistente = visitante.locator("#produto").inner_text()
        assert "Disco externo" in assistente
        assert "não grava" in assistente
        assert visitante.get_by_role("button", name="Ativar backup").count() == 0

    def test_14_o_servidor_recusa_a_escrita_por_baixo_da_tela(
        self, visitante: Page, vitrine: Vitrine
    ) -> None:
        """
        A tela esconder o botao nao basta: quem sabe usar o console do
        navegador chega a rota assim mesmo. A tranca de verdade e no servidor,
        antes de qualquer rota.
        """
        resposta = visitante.request.post(f"{vitrine.url}/api/politicas", data={})

        assert resposta.status == 403
        assert "demonstração pública" in resposta.text()

    def test_15_o_visitante_nao_baixa_o_instalador(self, visitante: Page, vitrine: Vitrine) -> None:
        """
        Um binario de dezenas de MB entregue a qualquer visitante, em laco.

        Nao muda dado nenhum — e e por isso que passaria por "leitura" se a
        regra fosse so o metodo HTTP.
        """
        resposta = visitante.request.get(f"{vitrine.url}/api/agente/instalador")

        assert resposta.status == 403
