"""
Teste E2E do RPA de cadastro, com navegador de verdade.

O QUE ESTE ARQUIVO PROVA
========================
Os testes de unidade do `RPACadastroTask` rodam com o browser mockado: eles
provam que a task **decide** certo. Não provam que ela **cadastra**. Um mock
que responde "sucesso" produz exatamente a mesma saída de uma task que digitou
no campo errado e nunca submeteu nada.

Aqui a diferença é essa: o Chromium abre o formulário do servidor demo,
preenche, submete — e a asserção que importa não é o retorno da task, é o
`GET /cadastros` do destino. **Verificar o retorno provaria que a task acha que
deu certo; ler o destino prova que deu.**

Os casos cobrem os dois critérios de aceite da ficha do RF-WEB-003:

1. caminho feliz — os registros chegam ao destino, com os valores certos;
2. linha ruim não interrompe — a válida que vem **depois** da ruim entra;
3. duplicado vira `skipped`, e o destino continua com um registro só;
4. o agregado vira `PARTIAL` quando há erro de verdade junto com sucesso;
5. erro inesperado gera **screenshot mascarada** — o segundo critério.

Mais o dry-run, que não precisa de navegador, e é bom que não precise: mostra
que a validação é independente do browser.

SOBRE A VERIFICAÇÃO DA SCREENSHOT
=================================
Ver "o CPF não aparece na imagem" exigiria OCR. O que este teste faz é mais
direto e não depende de biblioteca nenhuma: decodifica o PNG com `zlib` da
stdlib e procura a **cor da máscara** (`#FF00FF`), que o Playwright pinta por
cima dos elementos passados em `mask=`. Encontrar um bloco sólido dessa cor,
do tamanho de um campo de formulário, prova que a máscara foi pintada **na
captura** — e não apenas configurada. O elo entre "uma máscara foi pintada" e
"é o CPF que ela cobre" é asserido à parte, conferindo que os seletores padrão
do `BrowserSession` casam com o `input[name="cpf"]` do formulário.

ISOLAMENTO E CI
===============
- `@pytest.mark.integration` (sobe servidor HTTP real).
- Os casos com navegador têm `skipif` ligado a `verify_playwright_installed()`,
  então o CI não precisa instalar Chromium: ele pula.
- O servidor guarda cadastros **em memória**, então cada teste começa com um
  `POST /limpar`. Sem isso o caso do duplicado passaria por acidente, vendo o
  que o caso anterior cadastrou.

Para rodar a prova real:
    playwright install chromium
    pytest tests/e2e/test_rpa_cadastro_e2e.py -v --no-cov
"""

from __future__ import annotations

import zlib
from pathlib import Path
from typing import Any

import httpx
import pytest

from autotarefas.core.base import TaskStatus
from autotarefas.core.browser import BrowserSession, verify_playwright_installed
from autotarefas.tasks.rpa_cadastro import RPACadastroTask

# O modulo inteiro toca mais de um componente (servidor + Task): integracao.
pytestmark = pytest.mark.integration

# Avaliado uma vez: os casos COM navegador so rodam se o Chromium existir.
_SEM_NAVEGADOR = not verify_playwright_installed()["ok"]
_MOTIVO_SKIP = "navegador do Playwright nao instalado (rode: playwright install chromium)"

# CPFs validos no modulo 11 e no formato que o servidor exige. Numeros de
# teste, sem dono: nao pertencem a pessoa nenhuma.
CPF_ANA = "052.482.396-05"
CPF_BRUNO = "111.444.777-35"
CPF_CARLA = "168.995.350-09"
# Reprovado no modulo 11 — e o que faz a linha ser recusada antes do browser.
CPF_INVALIDO = "111.222.333-44"

# A cor que o Playwright pinta sobre os elementos mascarados.
MASCARA_RGB = (0xFF, 0x00, 0xFF)
# Um campo de formulario ocupa MUITO mais que isso; o piso so descarta ruido
# de antialiasing em alguma borda.
AREA_MINIMA_DA_MASCARA = 500


def _planilha(destino: Path, linhas: list[dict[str, str]]) -> Path:
    """Escreve um CSV de cadastros no formato que a task espera."""
    colunas = ["nome", "email", "cpf", "telefone"]
    conteudo = [",".join(colunas)]
    conteudo.extend(",".join(linha.get(coluna, "") for coluna in colunas) for linha in linhas)
    destino.write_text("\n".join(conteudo) + "\n", encoding="utf-8")
    return destino


def _cadastros(base_url: str) -> list[dict[str, Any]]:
    """O que chegou ao destino, lido do proprio destino."""
    resposta = httpx.get(f"{base_url}/cadastros", timeout=5.0)
    resposta.raise_for_status()
    dados: list[dict[str, Any]] = resposta.json()
    return dados


def _operacoes(resultado: Any) -> list[dict[str, Any]]:
    """As operacoes linha a linha do resultado da task."""
    operacoes: list[dict[str, Any]] = resultado.data["operations"]
    return operacoes


def _por_cpf(operacoes: list[dict[str, Any]], cpf: str) -> dict[str, Any]:
    """A operacao de uma linha especifica, pelo CPF."""
    achadas = [op for op in operacoes if op.get("cpf") == cpf]
    assert len(achadas) == 1, f"esperava 1 operacao para {cpf}, achei {len(achadas)}"
    return achadas[0]


# ------------------------------------------------------------------
# Leitura de PNG sem dependencia externa
# ------------------------------------------------------------------


def _paeth(a: int, b: int, c: int) -> int:
    """O preditor Paeth do PNG (filtro 4)."""
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _desfiltra(linha: bytearray, anterior: bytearray, filtro: int, canais: int) -> None:
    """Desfaz, no lugar, o filtro de uma scanline do PNG (tipos 1 a 4)."""
    for x in range(len(linha)):
        esquerda = linha[x - canais] if x >= canais else 0
        acima = anterior[x]
        diagonal = anterior[x - canais] if x >= canais else 0
        if filtro == 1:
            somar = esquerda
        elif filtro == 2:
            somar = acima
        elif filtro == 3:
            somar = (esquerda + acima) // 2
        else:
            somar = _paeth(esquerda, acima, diagonal)
        linha[x] = (linha[x] + somar) & 0xFF


def _conta_pixels_da_mascara(caminho: Path) -> int:
    """
    Conta os pixels da cor da máscara num PNG, sem Pillow.

    O Pillow não é dependência deste projeto, e acrescentar uma biblioteca
    inteira para contar pixel de uma cor seria caro pelo que entrega. PNG de
    8 bits sem entrelace é simples o bastante: descomprime o IDAT com `zlib` e
    desfaz o filtro de cada linha.
    """
    dados = caminho.read_bytes()
    assert dados[:8] == b"\x89PNG\r\n\x1a\n", "nao e um PNG"

    largura = altura = canais = 0
    idat = bytearray()
    posicao = 8
    while posicao < len(dados):
        tamanho = int.from_bytes(dados[posicao : posicao + 4], "big")
        tipo = dados[posicao + 4 : posicao + 8]
        corpo = dados[posicao + 8 : posicao + 8 + tamanho]
        posicao += 12 + tamanho  # 4 tamanho + 4 tipo + corpo + 4 CRC

        if tipo == b"IHDR":
            largura = int.from_bytes(corpo[0:4], "big")
            altura = int.from_bytes(corpo[4:8], "big")
            profundidade, tipo_de_cor, entrelace = corpo[8], corpo[9], corpo[12]
            assert profundidade == 8, f"esperava 8 bits por canal, veio {profundidade}"
            assert entrelace == 0, "PNG entrelacado nao e lido aqui"
            canais = {2: 3, 6: 4}[tipo_de_cor]  # RGB ou RGBA
        elif tipo == b"IDAT":
            idat += corpo
        elif tipo == b"IEND":
            break

    bruto = zlib.decompress(bytes(idat))
    bytes_por_linha = largura * canais
    anterior = bytearray(bytes_por_linha)
    encontrados = 0
    indice = 0

    for _ in range(altura):
        filtro = bruto[indice]
        indice += 1
        linha = bytearray(bruto[indice : indice + bytes_por_linha])
        indice += bytes_por_linha

        if filtro:  # 0 = sem filtro, e o caso barato
            _desfiltra(linha, anterior, filtro, canais)

        for x in range(0, bytes_por_linha, canais):
            if (linha[x], linha[x + 1], linha[x + 2]) == MASCARA_RGB:
                encontrados += 1

        anterior = linha

    return encontrados


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def destino_limpo(servidor_demo: str) -> str:
    """
    Zera os cadastros antes de cada teste.

    O servidor guarda tudo em memória e a fixture do servidor é de módulo. Sem
    esta limpeza, o caso do duplicado veria o registro que o caminho feliz
    criou e passaria **por acidente** — o pior tipo de teste verde, porque ele
    continuaria verde depois de o código quebrar.
    """
    httpx.post(f"{servidor_demo}/limpar", timeout=5.0).raise_for_status()
    return servidor_demo


@pytest.fixture
def screenshots_no_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Manda as screenshots para o tmp do teste, e não para a pasta do usuário.

    O `BrowserSession` grava em `settings.autotarefas_home / "screenshots"`
    quando ninguém diz o contrário, e a task o constrói internamente — não há
    parâmetro para interceptar. Teste que suja `~/.autotarefas` é teste que
    deixa rastro na máquina de quem rodou.
    """
    from autotarefas.core.settings import settings

    casa = tmp_path / "casa"
    monkeypatch.setattr(settings, "autotarefas_home", casa)
    return casa / "screenshots"


class TestRPACadastroE2E:
    """
    Os cinco casos da ficha, mais o dry-run.

    A ordem é a da leitura, não a da dependência: cada teste limpa o destino e
    monta a própria planilha, então qualquer um roda sozinho.
    """

    @pytest.mark.skipif(_SEM_NAVEGADOR, reason=_MOTIVO_SKIP)
    def test_cadastra_de_verdade_e_o_destino_confirma(
        self, destino_limpo: str, tmp_path: Path
    ) -> None:
        """
        Caminho feliz: três linhas válidas viram três registros no destino.

        A asserção que importa é a última. As de status provam que a task não
        reclamou; a leitura do `/cadastros` prova que os dados chegaram, com
        nome e e-mail certos — o que um mock nunca poderia falsificar.
        """
        planilha = _planilha(
            tmp_path / "validos.csv",
            [
                {"nome": "Ana Souza", "email": "ana@exemplo.com.br", "cpf": CPF_ANA},
                {"nome": "Bruno Lima", "email": "bruno@exemplo.com.br", "cpf": CPF_BRUNO},
                {
                    "nome": "Carla Dias",
                    "email": "carla@exemplo.com.br",
                    "cpf": CPF_CARLA,
                    "telefone": "(11) 98765-4321",
                },
            ],
        )

        resultado = RPACadastroTask(planilha, base_url=destino_limpo, headless=True).run()

        assert resultado.status == TaskStatus.SUCCESS
        assert resultado.data["success_count"] == 3
        assert resultado.data["error_count"] == 0

        # O destino, e não o retorno da task.
        cadastrados = _cadastros(destino_limpo)
        assert len(cadastrados) == 3

        por_cpf = {registro["cpf"]: registro for registro in cadastrados}
        assert por_cpf[CPF_ANA]["nome"] == "Ana Souza"
        assert por_cpf[CPF_ANA]["email"] == "ana@exemplo.com.br"
        assert por_cpf[CPF_BRUNO]["nome"] == "Bruno Lima"
        assert por_cpf[CPF_CARLA]["telefone"] == "(11) 98765-4321"

    @pytest.mark.skipif(_SEM_NAVEGADOR, reason=_MOTIVO_SKIP)
    def test_linha_ruim_nao_interrompe_o_restante(self, destino_limpo: str, tmp_path: Path) -> None:
        """
        Primeiro critério de aceite: linha ruim não para o processamento.

        A ordem da planilha é o teste. A linha válida vem **depois** da ruim —
        se o RPA abortasse no primeiro CPF inválido, ela não existiria no
        destino, e é exatamente isso que a última asserção cobra.
        """
        planilha = _planilha(
            tmp_path / "mistura.csv",
            [
                {"nome": "Ana Souza", "email": "ana@exemplo.com.br", "cpf": CPF_ANA},
                {"nome": "Nao Existe", "email": "ruim@exemplo.com.br", "cpf": CPF_INVALIDO},
                {"nome": "Carla Dias", "email": "carla@exemplo.com.br", "cpf": CPF_CARLA},
            ],
        )

        resultado = RPACadastroTask(planilha, base_url=destino_limpo, headless=True).run()

        # O agregado e SUCCESS, e nao PARTIAL: `_determine_status` so devolve
        # PARTIAL quando ha ERRO junto com sucesso, e CPF invalido e `skipped`,
        # nao erro. A distincao e deliberada — uma linha que a planilha trouxe
        # torta nao e falha do RPA. O PARTIAL tem teste proprio, logo abaixo.
        assert resultado.status == TaskStatus.SUCCESS
        assert resultado.data["success_count"] == 2
        assert resultado.data["skipped_count"] == 1
        assert resultado.data["error_count"] == 0

        ruim = _por_cpf(_operacoes(resultado), CPF_INVALIDO)
        assert ruim["status"] == "skipped"
        assert "CPF invalido" in ruim["error"]

        cadastrados = _cadastros(destino_limpo)
        cpfs = {registro["cpf"] for registro in cadastrados}
        assert cpfs == {CPF_ANA, CPF_CARLA}
        assert CPF_INVALIDO not in cpfs

    @pytest.mark.skipif(_SEM_NAVEGADOR, reason=_MOTIVO_SKIP)
    def test_duplicado_e_recusado_pelo_destino_e_vira_skipped(
        self, destino_limpo: str, tmp_path: Path
    ) -> None:
        """
        Duplicidade é `skipped`, não erro — e o destino não ganha uma segunda
        linha.

        Quem detecta a duplicidade aqui é o **destino**, não a task: ela
        submete, o servidor responde "CPF ja cadastrado", e a task traduz isso
        para `skipped`. Rodar duas vezes é o jeito de exercitar esse caminho
        sem simular a resposta.
        """
        planilha = _planilha(
            tmp_path / "uma.csv",
            [{"nome": "Ana Souza", "email": "ana@exemplo.com.br", "cpf": CPF_ANA}],
        )

        primeira = RPACadastroTask(planilha, base_url=destino_limpo, headless=True).run()
        assert primeira.status == TaskStatus.SUCCESS
        assert len(_cadastros(destino_limpo)) == 1

        segunda = RPACadastroTask(planilha, base_url=destino_limpo, headless=True).run()

        repetida = _por_cpf(_operacoes(segunda), CPF_ANA)
        assert repetida["status"] == "skipped"
        assert "ja cadastrado" in repetida["error"].lower()
        assert segunda.data["skipped_count"] == 1
        assert segunda.data["error_count"] == 0

        # O que importa: continua um só.
        assert len(_cadastros(destino_limpo)) == 1

    @pytest.mark.skipif(_SEM_NAVEGADOR, reason=_MOTIVO_SKIP)
    def test_status_agregado_vira_partial_quando_uma_linha_da_erro(
        self, destino_limpo: str, tmp_path: Path
    ) -> None:
        """
        `PARTIAL` é o agregado de "entregou parte" — sucesso **e** erro juntos.

        Vale distinguir dos outros dois casos, porque a diferença é de
        vocabulário e importa para quem lê o relatório: linha torta na planilha
        é `skipped` e mantém o agregado em `SUCCESS`; linha que o RPA não
        conseguiu processar é `error` e derruba o agregado para `PARTIAL`. Um
        relatório que chamasse as duas de "parcial" ensinaria o operador a
        ignorar o aviso.

        Aqui a segunda linha tem telefone fora do `pattern` do formulário, e o
        navegador recusa o submit — o mesmo gatilho do caso da screenshot.
        """
        planilha = _planilha(
            tmp_path / "parcial.csv",
            [
                {"nome": "Ana Souza", "email": "ana@exemplo.com.br", "cpf": CPF_ANA},
                {
                    "nome": "Bruno Lima",
                    "email": "bruno@exemplo.com.br",
                    "cpf": CPF_BRUNO,
                    "telefone": "11987654321",  # sem parenteses nem traco
                },
            ],
        )

        resultado = RPACadastroTask(
            planilha,
            base_url=destino_limpo,
            headless=True,
            screenshot_on_error=False,  # o teste da screenshot e o proximo
        ).run()

        assert resultado.status == TaskStatus.PARTIAL
        assert resultado.data["success_count"] == 1
        assert resultado.data["error_count"] == 1
        assert _por_cpf(_operacoes(resultado), CPF_BRUNO)["status"] == "error"

        # A que deu certo chegou ao destino; a que falhou, nao.
        cpfs = {registro["cpf"] for registro in _cadastros(destino_limpo)}
        assert cpfs == {CPF_ANA}

    @pytest.mark.skipif(_SEM_NAVEGADOR, reason=_MOTIVO_SKIP)
    def test_erro_gera_screenshot_com_o_campo_sensivel_mascarado(
        self, destino_limpo: str, tmp_path: Path, screenshots_no_tmp: Path
    ) -> None:
        """
        Segundo critério de aceite: a screenshot de erro não expõe dado
        sensível.

        O erro é forçado por um telefone fora do formato, e o caminho que ele
        toma é instrutivo: o campo tem `pattern` no HTML, então **o próprio
        navegador recusa o submit**. Nenhum POST sai. Do lado da task isso é
        um estado inesperado — ela clicou, esperou, e não veio nem
        `#record-id` nem `.errors` — e é exatamente o gatilho que a ficha
        descreve por "erro inesperado".

        É um caso realista, e mais interessante do que uma recusa do servidor:
        o alvo pode ter regra de tela que o nosso validador não conhece, e o
        RPA precisa registrar isso em vez de travar em silêncio. A página
        continua no formulário, com o CPF preenchido — é aí que a captura
        acontece, com dado sensível na tela.

        O que a asserção prova, com o que dá para provar sem OCR: o arquivo
        existe, e dentro dele há um bloco sólido da cor de máscara, do tamanho
        de um campo. Isso só é possível se o `mask=` do Playwright tiver
        pintado na hora da captura. O elo com "é o CPF que está coberto" é a
        última asserção: os seletores padrão do `BrowserSession` incluem o
        `input[name*='cpf']`, que é o nome do campo neste formulário.
        """
        planilha = _planilha(
            tmp_path / "telefone_ruim.csv",
            [
                {
                    "nome": "Ana Souza",
                    "email": "ana@exemplo.com.br",
                    "cpf": CPF_ANA,
                    "telefone": "11987654321",  # sem parenteses nem traco
                }
            ],
        )

        resultado = RPACadastroTask(
            planilha,
            base_url=destino_limpo,
            headless=True,
            screenshot_on_error=True,
        ).run()

        operacao = _por_cpf(_operacoes(resultado), CPF_ANA)
        assert operacao["status"] == "error"
        assert "inesperada" in operacao["error"].lower()
        assert resultado.data["error_count"] == 1

        # 1. A screenshot foi gerada, onde a task disse que gerou.
        assert "screenshot" in operacao, "erro nao produziu screenshot"
        imagem = Path(operacao["screenshot"])
        assert imagem.exists()
        assert imagem.parent == screenshots_no_tmp
        assert imagem.stat().st_size > 0

        # 2. A mascara foi pintada NA CAPTURA, e nao apenas configurada.
        pintados = _conta_pixels_da_mascara(imagem)
        assert pintados >= AREA_MINIMA_DA_MASCARA, (
            f"so {pintados} pixels da cor de mascara — o campo sensivel "
            f"provavelmente saiu legivel na imagem"
        )

        # 3. O elo: o campo coberto e o do CPF.
        seletores = BrowserSession.DEFAULT_SENSITIVE_SELECTORS
        assert any("cpf" in seletor.lower() for seletor in seletores)

        # E o dado nao vazou para o registro da operacao em texto puro:
        # o destino nao guardou nada, porque a linha foi recusada.
        assert _cadastros(destino_limpo) == []

    def test_dry_run_valida_sem_abrir_navegador(self, destino_limpo: str, tmp_path: Path) -> None:
        """
        O dry-run valida e não cadastra — sem Chromium.

        Este é o único caso sem `skipif`, e de propósito: ele roda no CI mesmo
        sem navegador instalado. Que a validação funcione sem browser não é
        detalhe de implementação; é o que permite conferir uma planilha de mil
        linhas antes de abrir a primeira janela.
        """
        planilha = _planilha(
            tmp_path / "previa.csv",
            [
                {"nome": "Ana Souza", "email": "ana@exemplo.com.br", "cpf": CPF_ANA},
                {"nome": "Nao Existe", "email": "ruim@exemplo.com.br", "cpf": CPF_INVALIDO},
            ],
        )

        resultado = RPACadastroTask(
            planilha, base_url=destino_limpo, headless=True, dry_run=True
        ).run()

        operacoes = _operacoes(resultado)
        assert _por_cpf(operacoes, CPF_ANA)["status"] == "would_create"
        assert _por_cpf(operacoes, CPF_INVALIDO)["status"] == "would_skip"
        assert resultado.data["success_count"] == 1
        assert resultado.data["skipped_count"] == 1

        # Nada foi criado: previa que cria e previa.
        assert _cadastros(destino_limpo) == []
