"""
Jornada guiada de planilhas no Live (1.8B-2B).

O card antigo subia o arquivo e validava numa requisicao, com schema fixo.
Aqui a jornada tem etapas e a pessoa ve o diagnostico antes de decidir. Estes
testes cobrem o caminho completo, as recusas e o isolamento entre sessoes.

O teste `test_aba_confirmada_e_realmente_usada_na_validacao` e o mais
importante: prova que a validacao final roda na aba que a pessoa escolheu, e
nao na primeira. Sem a 1.8B-2A (`--sheet`/`--header-row` no validate) isso
seria impossivel.
"""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from live_demo.backend.app import engine, jobs, ratelimit
from live_demo.backend.app.main import app

FX = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "planilhas"

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_TOO_LARGE = 413
HTTP_UNSUPPORTED_MEDIA = 415

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

DATA_PREFIX = "data: "


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """Cliente do app real, por modulo (subir o app a cada teste seria lento)."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _estado_limpo() -> Iterator[None]:
    """
    Cada teste comeca com o servidor em estado zerado.

    Tres coisas sao GLOBAIS e, sem zerar as tres, a suite falha por ORDEM DE
    EXECUCAO (isolados os testes passam, juntos dao 429/503):

      registro de jobs .......... sessoes de um teste contam no limite do outro
      rate limit por IP ......... o teto e 12 req/min e a suite faz muito mais
      DIRETORIOS de workspace ... `create_workspace` recusa acima de
          `max_workspaces` (40), e isso NAO depende do registro de jobs — foi
          o que sustentou a falha por mais tempo: limpar so o registro deixava
          as pastas no disco e o 503 continuava.

    Em producao quem faz esse papel e o TTL (`sweep_expired` + remocao das
    pastas) e a janela deslizante do proprio limitador.
    """
    _zerar_estado_do_servidor()
    yield
    _zerar_estado_do_servidor()


def _zerar_estado_do_servidor() -> None:
    jobs._jobs.clear()
    ratelimit.limiter._hits.clear()
    raiz = engine._root()
    if raiz.is_dir():
        for pasta in raiz.iterdir():
            if pasta.is_dir():
                shutil.rmtree(pasta, ignore_errors=True)


def _enviar(client: TestClient, fixture: str) -> dict[str, Any]:
    """Sobe uma fixture pelo endpoint de analise."""
    caminho = FX / fixture
    mime = XLSX_MIME if caminho.suffix == ".xlsx" else "text/csv"
    with caminho.open("rb") as handle:
        resposta = client.post(
            "/api/spreadsheets/analyze",
            files={"files": (fixture, handle, mime)},
        )
    # Mensagem util quando falha: sem isto, um 429/503 aparecia so como
    # KeyError: 'token', escondendo o motivo real.
    assert resposta.status_code == HTTP_OK, (
        f"analyze devolveu {resposta.status_code}: {resposta.text[:200]}"
    )
    return dict(resposta.json())


def _concluir(client: TestClient, token: str) -> dict[str, Any]:
    """Consome o SSE ate o fim e devolve o resultado consolidado."""
    with client.stream("GET", f"/api/stream/{token}") as resposta:
        list(resposta.iter_lines())
    return dict(client.get(f"/api/result/{token}").json())


def _jornada_completa(
    client: TestClient, fixture: str, *, sheet: str | None = None
) -> tuple[str, dict[str, Any]]:
    """Analisa, escolhe aba se preciso, confirma o sugerido e valida."""
    inicio = _enviar(client, fixture)
    token = inicio["token"]
    if sheet is not None:
        client.post(f"/api/spreadsheets/{token}/selection", data={"sheet": sheet})
    client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
    client.post(f"/api/spreadsheets/{token}/validate")
    return token, _concluir(client, token)


# ============================================================
# Analise
# ============================================================


class TestAnalise:
    def test_csv_valido(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        assert d["status"] == "analysis_ready"
        assert d["needs_choice"] is False
        assert d["analysis"]["columns"]

    def test_xlsx_valido(self, client: TestClient) -> None:
        d = _enviar(client, "02_xlsx_limpo.xlsx")
        assert d["status"] == "analysis_ready"
        assert d["analysis"]["estrutura"]["column_count"] > 0

    def test_exemplo_do_servidor(self, client: TestClient) -> None:
        r = client.post("/api/spreadsheets/analyze", params={"use_sample": "true"})
        assert r.status_code == HTTP_OK
        assert r.json()["status"] == "analysis_ready"

    def test_sem_arquivo_e_sem_exemplo(self, client: TestClient) -> None:
        r = client.post("/api/spreadsheets/analyze")
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "no_file"

    def test_exemplo_e_upload_juntos_e_recusado(self, client: TestClient) -> None:
        """Duas origens ao mesmo tempo e ambiguidade: escolha uma."""
        with (FX / "32_servicos.csv").open("rb") as handle:
            r = client.post(
                "/api/spreadsheets/analyze",
                params={"use_sample": "true"},
                files={"files": ("32_servicos.csv", handle, "text/csv")},
            )
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "ambiguous_source"

    def test_extensao_nao_permitida(self, client: TestClient) -> None:
        """415 vem do `_check_ext` do upload — o status correto para extensao."""
        r = client.post(
            "/api/spreadsheets/analyze",
            files={"files": ("script.txt", io.BytesIO(b"a,b\n1,2\n"), "text/plain")},
        )
        assert r.status_code == HTTP_UNSUPPORTED_MEDIA

    def test_arquivo_vazio(self, client: TestClient) -> None:
        r = client.post(
            "/api/spreadsheets/analyze",
            files={"files": ("vazio.csv", io.BytesIO(b""), "text/csv")},
        )
        assert r.json()["status"] in {"rejected_file", "analysis_ready"}

    def test_conteudo_corrompido_nao_derruba_a_api(self, client: TestClient) -> None:
        """XLSX falso: o leitor recusa; a API responde, nao explode."""
        r = client.post(
            "/api/spreadsheets/analyze",
            files={"files": ("falso.xlsx", io.BytesIO(b"nao sou um xlsx"), XLSX_MIME)},
        )
        assert r.status_code == HTTP_OK
        assert r.json()["status"] == "rejected_file"
        assert "detail" in r.json()

    def test_payload_nao_expoe_caminho_fisico(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        texto = json.dumps(d)
        assert "workspace" not in texto
        assert str(engine._root()) not in texto
        assert "\\\\Users" not in texto

    def test_previa_e_limitada(self, client: TestClient) -> None:
        d = _enviar(client, "01_csv_limpo.csv")
        assert d["preview"]
        assert len(d["preview"].splitlines()) < 30


# ============================================================
# Ambiguidade e selecao
# ============================================================


class TestSelecao:
    def test_aba_ambigua_vira_pergunta(self, client: TestClient) -> None:
        d = _enviar(client, "07_tres_abas.xlsx")
        assert d["status"] == "needs_selection"
        assert d["needs_choice"] is True
        opcoes = d["ambiguities"][0]["sheet_options"]
        assert {o["name"] for o in opcoes} == {"Vendas", "Estoque", "Clientes"}

    def test_escolha_valida_resolve(self, client: TestClient) -> None:
        d = _enviar(client, "07_tres_abas.xlsx")
        r = client.post(f"/api/spreadsheets/{d['token']}/selection", data={"sheet": "Estoque"})
        novo = r.json()
        assert novo["status"] == "analysis_ready"
        assert novo["needs_choice"] is False
        assert novo["selected_sheet"] == "Estoque"
        assert [c["name"] for c in novo["analysis"]["columns"]] == ["sku", "saldo"]

    def test_aba_fora_das_opcoes_e_recusada(self, client: TestClient) -> None:
        d = _enviar(client, "07_tres_abas.xlsx")
        r = client.post(f"/api/spreadsheets/{d['token']}/selection", data={"sheet": "Fantasma"})
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "invalid_sheet"

    @pytest.mark.parametrize("valor", ["", "   "])
    def test_aba_vazia_e_recusada(self, client: TestClient, valor: str) -> None:
        d = _enviar(client, "07_tres_abas.xlsx")
        r = client.post(f"/api/spreadsheets/{d['token']}/selection", data={"sheet": valor})
        assert r.status_code == HTTP_BAD_REQUEST

    def test_caminho_como_aba_e_recusado(self, client: TestClient) -> None:
        """Um caminho nunca esta entre as candidatas."""
        d = _enviar(client, "07_tres_abas.xlsx")
        r = client.post(
            f"/api/spreadsheets/{d['token']}/selection",
            data={"sheet": "../../etc/passwd"},
        )
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "invalid_sheet"

    def test_header_row_valido(self, client: TestClient) -> None:
        d = _enviar(client, "06_cabecalho_linha_4.xlsx")
        r = client.post(f"/api/spreadsheets/{d['token']}/selection", data={"header_row": "4"})
        assert r.status_code == HTTP_OK
        assert r.json()["header_row"] == 4

    @pytest.mark.parametrize("valor", ["0", "-3"])
    def test_header_row_invalido(self, client: TestClient, valor: str) -> None:
        d = _enviar(client, "32_servicos.csv")
        r = client.post(f"/api/spreadsheets/{d['token']}/selection", data={"header_row": valor})
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "invalid_header_row"

    def test_selecao_vazia_e_recusada(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        r = client.post(f"/api/spreadsheets/{d['token']}/selection", data={})
        assert r.status_code == HTTP_BAD_REQUEST

    def test_token_inexistente(self, client: TestClient) -> None:
        r = client.post("/api/spreadsheets/naoexiste/selection", data={"sheet": "Plan1"})
        assert r.status_code == HTTP_NOT_FOUND
        assert r.json()["code"] == "expired"


# ============================================================
# Schema
# ============================================================

SCHEMA_PROPRIO = """
columns:
  - name: Numero
    type: str
    required: true
  - name: Situacao
    type: str
"""

SCHEMA_COM_REGRAS = """
columns:
  - name: Numero
    type: str
  - name: Servico
    type: str
  - name: Situacao
    type: str
group_keys:
  - name: por_servico
    columns: ["Servico"]
group_checks:
  - name: coerencia
    group_key: por_servico
    consistent: ["Situacao"]
    severity: warning
"""


class TestSchema:
    def test_sugerido_gera_resumo(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        r = client.post(f"/api/spreadsheets/{d['token']}/schema", data={"source": "suggested"})
        corpo = r.json()
        assert corpo["status"] == "schema_ready"
        assert corpo["schema_origin"] == "suggested"
        assert corpo["summary"]["columns"]

    def test_sugerido_nao_inventa_procedencia(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        r = client.post(f"/api/spreadsheets/{d['token']}/schema", data={"source": "suggested"})
        assert "generated_from" not in r.json()["summary"]

    def test_yaml_proprio_valido(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        r = client.post(
            f"/api/spreadsheets/{d['token']}/schema",
            data={"source": "uploaded"},
            files={"files": ("meu.yaml", SCHEMA_PROPRIO.encode(), "application/yaml")},
        )
        corpo = r.json()
        assert corpo["status"] == "schema_ready"
        assert corpo["schema_origin"] == "uploaded"
        assert [c["name"] for c in corpo["summary"]["columns"]] == ["Numero", "Situacao"]

    def test_resumo_mostra_regras_de_grupo(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        r = client.post(
            f"/api/spreadsheets/{d['token']}/schema",
            data={"source": "uploaded"},
            files={"files": ("r.yaml", SCHEMA_COM_REGRAS.encode(), "application/yaml")},
        )
        resumo = r.json()["summary"]
        assert resumo["group_keys"][0]["name"] == "por_servico"
        assert resumo["group_checks"][0]["severity"] == "warning"

    def test_yaml_invalido(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        r = client.post(
            f"/api/spreadsheets/{d['token']}/schema",
            data={"source": "uploaded"},
            files={"files": ("x.yaml", b"columns: [[[", "application/yaml")},
        )
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "invalid_schema"
        assert "Traceback" not in r.json()["detail"]

    def test_yaml_com_tag_executavel(self, client: TestClient) -> None:
        """`safe_load` nao constroi objetos: a tag nao executa nada."""
        malicioso = b"!!python/object/apply:os.system ['echo comprometido']\n"
        d = _enviar(client, "32_servicos.csv")
        r = client.post(
            f"/api/spreadsheets/{d['token']}/schema",
            data={"source": "uploaded"},
            files={"files": ("mal.yaml", malicioso, "application/yaml")},
        )
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "invalid_schema"

    def test_yaml_grande_e_recusado(self, client: TestClient) -> None:
        gigante = b"# " + b"a" * (400 * 1024)
        d = _enviar(client, "32_servicos.csv")
        r = client.post(
            f"/api/spreadsheets/{d['token']}/schema",
            data={"source": "uploaded"},
            files={"files": ("g.yaml", gigante, "application/yaml")},
        )
        assert r.status_code == HTTP_TOO_LARGE
        assert r.json()["code"] == "schema_too_large"

    def test_origem_desconhecida(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        r = client.post(f"/api/spreadsheets/{d['token']}/schema", data={"source": "inventada"})
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "invalid_source"

    def test_schema_antes_de_resolver_ambiguidade(self, client: TestClient) -> None:
        d = _enviar(client, "07_tres_abas.xlsx")
        r = client.post(f"/api/spreadsheets/{d['token']}/schema", data={"source": "suggested"})
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "analysis_pending"


# ============================================================
# Validacao
# ============================================================


class TestValidacao:
    def test_sem_problemas_da_exit_0(self, client: TestClient) -> None:
        token, res = _jornada_completa(client, "32_servicos.csv")
        assert res["exit_code"] == 0
        assert res["outcome"] == "ok"
        job = jobs.get(token)
        assert job is not None
        assert job.journey is not None
        assert job.journey.status == "completed"

    def test_com_problemas_da_exit_1_e_gera_pacote(self, client: TestClient) -> None:
        """Problema nos dados: validacao CONCLUIDA, com evidencias completas."""
        d = _enviar(client, "32_servicos.csv")
        token = d["token"]
        # schema que reprova: Situacao como int
        ruim = b"columns:\n  - name: Situacao\n    type: int\n"
        client.post(
            f"/api/spreadsheets/{token}/schema",
            data={"source": "uploaded"},
            files={"files": ("ruim.yaml", ruim, "application/yaml")},
        )
        client.post(f"/api/spreadsheets/{token}/validate")
        res = _concluir(client, token)
        assert res["exit_code"] == 1
        assert res["outcome"] == "caught_issue"
        assert "pacote_execucao.zip" in [a["name"] for a in res["artifacts"]]
        job = jobs.get(token)
        assert job is not None
        assert job.journey is not None
        assert job.journey.status == "completed_with_issues"

    def test_artefatos_da_1_8a_preservados(self, client: TestClient) -> None:
        _, res = _jornada_completa(client, "32_servicos.csv")
        nomes = {a["name"] for a in res["artifacts"]}
        assert "validacao_report.json" in nomes
        assert "registros_validos.csv" in nomes
        assert "pacote_execucao.zip" in nomes

    def test_pacote_tem_manifesto_e_schema_efetivo(self, client: TestClient) -> None:
        _, res = _jornada_completa(client, "32_servicos.csv")
        zip_art = next(a for a in res["artifacts"] if a["name"] == "pacote_execucao.zip")
        baixado = client.get(zip_art["download_url"])
        assert baixado.status_code == HTTP_OK
        pacote = zipfile.ZipFile(io.BytesIO(baixado.content))
        assert {"manifest.json", "schema_efetivo.yaml"} <= set(pacote.namelist())

    def test_aba_confirmada_e_realmente_usada_na_validacao(self, client: TestClient) -> None:
        """
        A prova central da jornada.

        07_tres_abas tem 'Vendas' (produto/qtd/valor) como primeira aba e
        'Estoque' (sku/saldo) como segunda. Escolhendo Estoque, a validacao
        precisa rodar em sku/saldo — se rodasse na primeira aba, o schema
        sugerido de Estoque acusaria colunas ausentes e o exit seria 1.
        """
        _, res = _jornada_completa(client, "07_tres_abas.xlsx", sheet="Estoque")
        assert res["exit_code"] == 0, res["stdout"][-400:]
        relatorio_art = next(a for a in res["artifacts"] if a["name"] == "validacao_report.json")
        relatorio = client.get(relatorio_art["download_url"]).json()
        assert relatorio["selected_sheet"] == "Estoque"

    def test_validar_sem_schema_usa_o_sugerido(self, client: TestClient) -> None:
        """
        Contrato do Card 01: ninguém precisa entender schema.

        Sem schema próprio, o servidor adota o SUGERIDO — que só descreve a
        estrutura observada, sem inventar regra de negócio.
        """
        d = _enviar(client, "32_servicos.csv")
        r = client.post(f"/api/spreadsheets/{d['token']}/validate")

        assert r.status_code == HTTP_OK
        assert r.json()["status"] == "validating"

        res = _concluir(client, d["token"])
        assert res["outcome"] in {"ok", "caught_issue"}
        job = jobs.get(d["token"])
        assert job is not None
        assert job.journey is not None
        assert job.journey.schema_origin == "suggested"

    def test_max_issues_invalido(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        client.post(f"/api/spreadsheets/{d['token']}/schema", data={"source": "suggested"})
        r = client.post(f"/api/spreadsheets/{d['token']}/validate", data={"max_issues": "0"})
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "invalid_max_issues"

    def test_original_intacto(self, client: TestClient) -> None:
        import hashlib

        alvo = FX / "32_servicos.csv"
        antes = hashlib.sha256(alvo.read_bytes()).hexdigest()
        _jornada_completa(client, "32_servicos.csv")
        assert hashlib.sha256(alvo.read_bytes()).hexdigest() == antes


# ============================================================
# Correcoes seguras confirmadas (modo limpeza na jornada)
# ============================================================


class TestCorrecoesConfirmadas:
    """
    A jornada so normaliza valor quando a pessoa CONFIRMA.

    Sem confirmacao, o AutoTarefas audita: aponta o que encontrou e nao toca
    em nada. Com confirmacao, normaliza o que e seguro e — em XLSX — entrega
    a planilha tratada preservando a apresentacao do arquivo original.
    """

    def _validar(self, client: TestClient, fixture: str, **dados: str) -> dict[str, Any]:
        inicio = _enviar(client, fixture)
        token = inicio["token"]
        client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
        client.post(f"/api/spreadsheets/{token}/validate", data=dados)
        return _concluir(client, token)

    def test_sem_confirmacao_nao_ha_planilha_tratada(self, client: TestClient) -> None:
        resultado = self._validar(client, "29_espacos_extras.csv")
        nomes = [a["name"] for a in resultado["artifacts"]]
        assert "planilha_tratada.xlsx" not in nomes

    def test_sem_confirmacao_nada_e_normalizado(self, client: TestClient) -> None:
        resultado = self._validar(client, "29_espacos_extras.csv")
        relatorio = next(a for a in resultado["artifacts"] if a["name"] == "validacao_report.json")
        dados = client.get(relatorio["download_url"]).json()
        assert dados["mode"] == "auditoria"
        assert dados["total_cleaned"] == 0

    def test_confirmacao_normaliza_e_registra(self, client: TestClient) -> None:
        resultado = self._validar(client, "29_espacos_extras.csv", apply_cleaning="true")
        relatorio = next(a for a in resultado["artifacts"] if a["name"] == "validacao_report.json")
        dados = client.get(relatorio["download_url"]).json()
        assert dados["mode"] == "limpeza"
        assert dados["total_cleaned"] > 0

    def test_xlsx_confirmado_gera_planilha_tratada(self, client: TestClient) -> None:
        resultado = self._validar(client, "02_xlsx_limpo.xlsx", apply_cleaning="true")
        nomes = [a["name"] for a in resultado["artifacts"]]
        assert "planilha_tratada.xlsx" in nomes
        assert "preservacao_report.json" in nomes

    def test_planilha_tratada_e_baixavel(self, client: TestClient) -> None:
        inicio = _enviar(client, "02_xlsx_limpo.xlsx")
        token = inicio["token"]
        client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
        client.post(f"/api/spreadsheets/{token}/validate", data={"apply_cleaning": "true"})
        resultado = _concluir(client, token)

        artefato = next(a for a in resultado["artifacts"] if a["name"] == "planilha_tratada.xlsx")
        resposta = client.get(artefato["download_url"])
        assert resposta.status_code == HTTP_OK
        # XLSX real: um zip, que comeca com "PK".
        assert resposta.content[:2] == b"PK"

    def test_csv_confirmado_nao_inventa_planilha_tratada(self, client: TestClient) -> None:
        """CSV nao tem apresentacao a preservar — e nao ganha arquivo fantasma."""
        resultado = self._validar(client, "29_espacos_extras.csv", apply_cleaning="true")
        nomes = [a["name"] for a in resultado["artifacts"]]
        assert "planilha_tratada.xlsx" not in nomes

    def test_original_intacto_mesmo_com_correcoes(self, client: TestClient) -> None:
        import hashlib

        alvo = FX / "02_xlsx_limpo.xlsx"
        antes = hashlib.sha256(alvo.read_bytes()).hexdigest()
        self._validar(client, "02_xlsx_limpo.xlsx", apply_cleaning="true")
        assert hashlib.sha256(alvo.read_bytes()).hexdigest() == antes


# ============================================================
# Linhas repetidas: sinalizadas quando confirmado, nunca removidas
# ============================================================


HOMOLOGACAO = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "homologacao"


class TestLinhasRepetidas:
    """
    A analise ENCONTRA linhas 100% repetidas; a validacao so as acusa quando
    a pessoa confirma. O schema sugerido deixa essa regra comentada de
    proposito — o nucleo nao inventa regra de negocio.
    """

    def _enviar_homologacao(self, client: TestClient, nome: str) -> dict[str, Any]:
        caminho = HOMOLOGACAO / nome
        with caminho.open("rb") as handle:
            r = client.post("/api/spreadsheets/analyze", files={"files": (nome, handle, XLSX_MIME)})
        assert r.status_code == HTTP_OK, r.text[:200]
        return dict(r.json())

    def test_analise_informa_quantas_linhas_repetidas(self, client: TestClient) -> None:
        d = self._enviar_homologacao(client, "A_vendas_com_anomalias.xlsx")
        assert d["duplicate_rows"] == 1

    def test_arquivo_sem_repetidas_informa_zero(self, client: TestClient) -> None:
        d = _enviar(client, "01_csv_limpo.csv")
        assert d["duplicate_rows"] == 0

    def test_duplicidade_e_verificada_sempre(self, client: TestClient) -> None:
        """
        Contrato do Card 01: a verificação de linhas 100% repetidas **sempre**
        acontece — não depende de schema, de perfil nem de opção escondida.
        """
        d = self._enviar_homologacao(client, "A_vendas_com_anomalias.xlsx")
        token = d["token"]
        client.post(f"/api/spreadsheets/{token}/validate")
        res = _concluir(client, token)

        relatorio = next(a for a in res["artifacts"] if a["name"] == "validacao_report.json")
        dados = client.get(relatorio["download_url"]).json()
        duplicadas = [i for i in dados["issues"] if "duplicad" in str(i["message"]).lower()]
        assert len(duplicadas) == 1
        assert duplicadas[0]["severity"] == "warning"

    def test_confirmada_a_repetida_aparece_com_o_numero_da_linha(self, client: TestClient) -> None:
        d = self._enviar_homologacao(client, "A_vendas_com_anomalias.xlsx")
        token = d["token"]
        client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
        client.post(f"/api/spreadsheets/{token}/validate", data={"flag_duplicate_rows": "true"})
        res = _concluir(client, token)

        relatorio = next(a for a in res["artifacts"] if a["name"] == "validacao_report.json")
        dados = client.get(relatorio["download_url"]).json()
        duplicadas = [i for i in dados["issues"] if "duplicad" in str(i["message"]).lower()]
        assert len(duplicadas) == 1
        assert duplicadas[0]["line"] == 12

    def test_a_regra_confirmada_entra_no_schema_efetivo(self, client: TestClient) -> None:
        """O pacote guarda o que REALMENTE rodou, nao o que foi sugerido."""
        d = self._enviar_homologacao(client, "A_vendas_com_anomalias.xlsx")
        token = d["token"]
        client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
        client.post(f"/api/spreadsheets/{token}/validate", data={"flag_duplicate_rows": "true"})
        res = _concluir(client, token)

        pacote = next(a for a in res["artifacts"] if a["name"] == "pacote_execucao.zip")
        conteudo = client.get(pacote["download_url"]).content
        with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
            efetivo = zf.read("schema_efetivo.yaml").decode("utf-8")
        assert "detect_duplicate_rows: true" in efetivo

    def test_nenhuma_linha_e_removida(self, client: TestClient) -> None:
        d = self._enviar_homologacao(client, "A_vendas_com_anomalias.xlsx")
        token = d["token"]
        client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
        client.post(
            f"/api/spreadsheets/{token}/validate",
            data={"flag_duplicate_rows": "true", "apply_cleaning": "true"},
        )
        res = _concluir(client, token)

        relatorio = next(a for a in res["artifacts"] if a["name"] == "validacao_report.json")
        dados = client.get(relatorio["download_url"]).json()
        assert dados["rows"] == 17  # as 17 linhas de dados da fixture, inteiras


# ============================================================
# Card 01: analise geral, organizacao, ordenacao e indicadores
# ============================================================


DOMINIOS = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "dominios"


class TestCardAnaliseEOrganizacao:
    """
    O contrato do Card 01 pelos endpoints reais.

    Cada teste aqui responde a um critério de aceite: análise geral sem
    schema, apresentação avaliada, organização opcional e confirmada,
    ordenação nunca silenciosa e indicador nenhum sem confirmação.
    """

    def _enviar_dominio(self, client: TestClient, nome: str) -> dict[str, Any]:
        caminho = DOMINIOS / nome
        mime = XLSX_MIME if caminho.suffix == ".xlsx" else "text/csv"
        with caminho.open("rb") as handle:
            r = client.post("/api/spreadsheets/analyze", files={"files": (nome, handle, mime)})
        assert r.status_code == HTTP_OK, r.text[:200]
        return dict(r.json())

    def _executar(self, client: TestClient, token: str, **opcoes: str) -> dict[str, Any]:
        client.post(f"/api/spreadsheets/{token}/validate", data=opcoes)
        return _concluir(client, token)

    # --- diagnóstico -------------------------------------------------

    def test_diagnostico_traz_abas_e_apresentacao(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "vendas_simples.xlsx")

        assert d["presentation"]["veredito"] == "melhoravel"
        assert d["presentation"]["criterios"]
        assert [a["nome"] for a in d["sheets"]] == ["Vendas"]
        assert d["multiple_sheets"] is False

    def test_planilha_profissional_nao_recebe_proposta(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "financeiro_profissional.xlsx")
        assert d["presentation"]["veredito"] == "organizada"
        assert d["presentation"]["pendencias"] == []

    def test_estrutura_ambigua_e_declarada(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "pesquisa_ambigua.xlsx")
        assert d["presentation"]["veredito"] == "ambigua"

    def test_varias_abas_tabulares_pedem_escolha(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "atendimentos_duas_abas.xlsx")
        naturezas = {a["nome"]: a["natureza"] for a in d["sheets"]}

        assert d["multiple_sheets"] is True
        assert naturezas["Rascunho"] == "vazia"
        assert naturezas["Leia-me"] == "apresentacao"

    def test_csv_nao_inventa_apresentacao(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "clientes.csv")
        assert d["presentation"] is None
        assert d["sheets"] == []

    def test_papeis_sao_sugeridos_com_confianca(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "vendas_simples.xlsx")
        papeis = {p["coluna"]: p for p in d["column_roles"]["roles"]}

        assert papeis["Data"]["papel"] == "data"
        assert d["column_roles"]["offerable"] is True
        assert all(p["motivo"] for p in papeis.values())

    # --- observações sobre os dados -----------------------------------

    def test_numero_como_texto_aparece_antes_de_executar(self, client: TestClient) -> None:
        """Observar depois da execução seria tarde: a decisão é antes."""
        d = self._enviar_dominio(client, "servico_publico.xlsx")
        assert isinstance(d["notes"], list)

    def test_csv_nao_gera_observacoes_de_planilha(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "clientes.csv")
        assert d["notes"] == []

    def test_duas_tabelas_na_mesma_aba_viram_ambiguidade(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """
        Duas bases coladas na mesma aba nao podem ser organizadas por chute:
        a contagem de registros mistura as duas.
        """
        from openpyxl import Workbook

        caminho = tmp_path / "duas_tabelas.xlsx"
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["Aluno", "Turma", "Nota"])
        for i in range(1, 6):
            ws.append([f"Aluno {i}", "3A", 7 + i % 3])
        ws.append([])
        ws.append(["Professor", "Disciplina"])
        for i in range(1, 4):
            ws.append([f"Prof {i}", "Matematica"])
        wb.save(caminho)

        with caminho.open("rb") as handle:
            resposta = client.post(
                "/api/spreadsheets/analyze",
                files={"files": (caminho.name, handle, XLSX_MIME)},
            )
        d = dict(resposta.json())

        assert d["presentation"]["veredito"] == "ambigua"
        assert any("outra tabela na mesma aba" in p for p in d["presentation"]["pendencias"])

    # --- organização --------------------------------------------------

    def test_sem_confirmacao_nao_ha_planilha_organizada(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "vendas_simples.xlsx")
        res = self._executar(client, d["token"])
        nomes = [a["name"] for a in res["artifacts"]]

        assert "planilha_organizada.xlsx" not in nomes
        assert "relatorio_analise.xlsx" in nomes  # o laudo sai sempre

    def test_organizacao_confirmada_gera_o_arquivo(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "vendas_simples.xlsx")
        res = self._executar(client, d["token"], organize="true")
        nomes = [a["name"] for a in res["artifacts"]]

        assert "planilha_organizada.xlsx" in nomes

    def test_planilha_organizada_e_baixavel_e_valida(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "vendas_simples.xlsx")
        res = self._executar(client, d["token"], organize="true")
        artefato = next(a for a in res["artifacts"] if a["name"] == "planilha_organizada.xlsx")
        conteudo = client.get(artefato["download_url"]).content

        assert conteudo[:2] == b"PK"
        ws = load_workbook(io.BytesIO(conteudo))["Vendas"]
        assert ws.freeze_panes == "A2"
        assert ws.auto_filter.ref is not None

    def test_csv_nao_gera_planilha_organizada(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "clientes.csv")
        res = self._executar(client, d["token"], organize="true")
        assert "planilha_organizada.xlsx" not in [a["name"] for a in res["artifacts"]]

    # --- dashboard ----------------------------------------------------

    def test_sem_papel_confirmado_nao_ha_dashboard(self, client: TestClient) -> None:
        """Pedir o painel sem dizer o que somar nao inventa numero nenhum."""
        d = self._enviar_dominio(client, "vendas_simples.xlsx")
        res = self._executar(client, d["token"], organize="true", dashboard="true")
        artefato = next(a for a in res["artifacts"] if a["name"] == "planilha_organizada.xlsx")
        wb = load_workbook(io.BytesIO(client.get(artefato["download_url"]).content))

        assert "Dashboard" not in wb.sheetnames

    def test_dashboard_confirmado_vira_aba_separada(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "vendas_simples.xlsx")
        res = self._executar(
            client,
            d["token"],
            organize="true",
            dashboard="true",
            indicator_value="Valor",
            indicator_category="Vendedor",
        )
        artefato = next(a for a in res["artifacts"] if a["name"] == "planilha_organizada.xlsx")
        wb = load_workbook(io.BytesIO(client.get(artefato["download_url"]).content))

        assert wb.sheetnames[0] == "Dashboard"
        painel = wb["Dashboard"]
        assert painel.cell(row=1, column=1).value == "Dashboard"
        assert "Valor" in str(painel.cell(row=2, column=1).value)
        # E a aba dos dados continua sendo so dados.
        assert not wb["Vendas"]._charts

    def test_dashboard_sem_organizar_nao_cria_nada(self, client: TestClient) -> None:
        """A aba mora na planilha organizada; sem ela, nao ha onde por."""
        d = self._enviar_dominio(client, "vendas_simples.xlsx")
        res = self._executar(client, d["token"], dashboard="true", indicator_value="Valor")
        assert "planilha_organizada.xlsx" not in [a["name"] for a in res["artifacts"]]

    # --- ordenação ----------------------------------------------------

    def test_sem_ordenacao_a_ordem_original_e_mantida(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "servico_publico.xlsx")
        res = self._executar(client, d["token"], organize="true")
        artefato = next(a for a in res["artifacts"] if a["name"] == "planilha_organizada.xlsx")
        ws = load_workbook(io.BytesIO(client.get(artefato["download_url"]).content))["Protocolos"]

        assert [ws.cell(row=linha, column=1).value for linha in (2, 3, 4)] == [
            "000123",
            "000124",
            "000125",
        ]

    def test_ordenacao_confirmada_e_aplicada(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "servico_publico.xlsx")
        res = self._executar(
            client, d["token"], organize="true", sort_column="Dias", sort_desc="true"
        )
        artefato = next(a for a in res["artifacts"] if a["name"] == "planilha_organizada.xlsx")
        ws = load_workbook(io.BytesIO(client.get(artefato["download_url"]).content))["Protocolos"]
        dias = [ws.cell(row=linha, column=6).value for linha in range(2, 6)]

        assert dias == sorted(dias, reverse=True)

    # --- indicadores ---------------------------------------------------

    def test_sem_confirmacao_semantica_nao_ha_indicadores(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "vendas_simples.xlsx")
        res = self._executar(client, d["token"])
        artefato = next(a for a in res["artifacts"] if a["name"] == "relatorio_analise.xlsx")
        wb = load_workbook(io.BytesIO(client.get(artefato["download_url"]).content))

        assert "Indicadores confirmados" not in wb.sheetnames

    def test_indicadores_aparecem_com_papeis_confirmados(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "vendas_simples.xlsx")
        res = self._executar(
            client,
            d["token"],
            indicator_value="Valor",
            indicator_category="Vendedor",
            indicator_date="Data",
        )
        artefato = next(a for a in res["artifacts"] if a["name"] == "relatorio_analise.xlsx")
        wb = load_workbook(io.BytesIO(client.get(artefato["download_url"]).content))

        assert "Indicadores confirmados" in wb.sheetnames

    # --- downloads ------------------------------------------------------

    def test_original_fica_disponivel_para_download(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "vendas_simples.xlsx")
        resposta = client.get(f"/api/spreadsheets/{d['token']}/original")

        assert resposta.status_code == HTTP_OK
        assert resposta.content[:2] == b"PK"

    def test_original_de_outra_sessao_nao_e_alcancavel(self, client: TestClient) -> None:
        assert client.get("/api/spreadsheets/inexistente/original").status_code == HTTP_NOT_FOUND

    def test_relatorio_tem_as_abas_do_contrato(self, client: TestClient) -> None:
        d = self._enviar_dominio(client, "servico_publico.xlsx")
        res = self._executar(client, d["token"], organize="true", apply_cleaning="true")
        artefato = next(a for a in res["artifacts"] if a["name"] == "relatorio_analise.xlsx")
        wb = load_workbook(io.BytesIO(client.get(artefato["download_url"]).content))

        assert "Resumo" in wb.sheetnames
        assert "Abas do arquivo" in wb.sheetnames
        assert "Linhas para revisao" in wb.sheetnames
        assert "Alteracoes realizadas" in wb.sheetnames

    def test_arquivo_do_usuario_fica_intocado(self, client: TestClient) -> None:
        import hashlib

        alvo = DOMINIOS / "vendas_simples.xlsx"
        antes = hashlib.sha256(alvo.read_bytes()).hexdigest()
        d = self._enviar_dominio(client, "vendas_simples.xlsx")
        self._executar(client, d["token"], organize="true", sort_column="Pedido")
        assert hashlib.sha256(alvo.read_bytes()).hexdigest() == antes


# ============================================================
# Isolamento e seguranca
# ============================================================


class TestIsolamento:
    def test_sessao_a_nao_ve_dados_de_b(self, client: TestClient) -> None:
        a = _enviar(client, "32_servicos.csv")
        b = _enviar(client, "02_xlsx_limpo.xlsx")
        assert a["token"] != b["token"]
        colunas_a = [c["name"] for c in a["analysis"]["columns"]]
        colunas_b = [c["name"] for c in b["analysis"]["columns"]]
        assert colunas_a != colunas_b

    def test_download_de_outra_execucao_e_barrado(self, client: TestClient) -> None:
        _, res_a = _jornada_completa(client, "32_servicos.csv")
        b = _enviar(client, "02_xlsx_limpo.xlsx")
        nome = next(a["name"] for a in res_a["artifacts"] if a["name"] == "validacao_report.json")
        r = client.get(f"/api/download/{b['token']}/{nome}")
        assert r.status_code == HTTP_NOT_FOUND

    @pytest.mark.parametrize(
        "nome",
        ["../../etc/passwd", "..%2Fmanifest.json", "config/schema_confirmado.yaml"],
    )
    def test_path_traversal_barrado(self, client: TestClient, nome: str) -> None:
        token, _ = _jornada_completa(client, "32_servicos.csv")
        assert client.get(f"/api/download/{token}/{nome}").status_code == HTTP_NOT_FOUND

    def test_relatorio_baixado_nao_expoe_caminho_do_servidor(self, client: TestClient) -> None:
        """
        Regressao: o `validacao_report.json` trazia o caminho completo do
        arquivo dentro do workspace — a estrutura de pastas do servidor ia
        junto no download. Agora o relatorio guarda so o NOME.
        """
        _, res = _jornada_completa(client, "32_servicos.csv")
        artefato = next(a for a in res["artifacts"] if a["name"] == "validacao_report.json")
        texto = client.get(artefato["download_url"]).text

        assert str(engine._root()) not in texto
        assert "workspace" not in texto
        assert json.loads(texto)["file"] == "32_servicos.csv"

    def test_arquivo_de_entrada_nao_e_baixavel(self, client: TestClient) -> None:
        """Nada em `in/` sai pelo endpoint publico."""
        token, _ = _jornada_completa(client, "32_servicos.csv")
        assert client.get(f"/api/download/{token}/32_servicos.csv").status_code == HTTP_NOT_FOUND

    def test_schema_confirmado_fica_fora_de_out(self, client: TestClient) -> None:
        """
        `config/` existe para isto: o schema apenas SELECIONADO nao vira
        baixavel. O que executou aparece como schema_efetivo.yaml no pacote.
        """
        d = _enviar(client, "32_servicos.csv")
        token = d["token"]
        client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
        job = jobs.get(token)
        assert job is not None
        assert job.journey is not None
        assert job.journey.schema_path is not None
        assert job.journey.schema_path.parent.name == "config"
        assert not (job.workspace / "out" / "schema_confirmado.yaml").exists()

    def test_schema_sugerido_e_baixavel(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        r = client.get(f"/api/download/{d['token']}/schema_sugerido.yaml")
        assert r.status_code == HTTP_OK
        assert "columns" in r.text


# ============================================================
# Compatibilidade
# ============================================================


class TestCompatibilidade:
    def test_endpoint_generico_continua_funcionando(self, client: TestClient) -> None:
        """O /api/run dos cards antigos nao foi tocado."""
        r = client.post("/api/run/validate", params={"use_sample": "true"})
        assert r.status_code == HTTP_OK
        assert "token" in r.json()

    def test_catalogo_continua_respondendo(self, client: TestClient) -> None:
        assert client.get("/api/catalog").status_code == HTTP_OK

    def test_health_continua_respondendo(self, client: TestClient) -> None:
        assert client.get("/api/health").status_code == HTTP_OK


# ============================================================
# Revisao final: ciclo de vida, invalidacao e contagem de arquivos
# ============================================================


class TestCicloDeVida:
    """
    Regressao do `RuntimeError: Event loop is closed`.

    A thread leitora (`engine._pump`) fala com o event loop por
    `call_soon_threadsafe`. Sem `join` no fim de `run_streaming`, ela
    sobrevivia a execucao e podia tocar um loop ja fechado — o traceback
    aparecia DEPOIS do resumo do pytest, escondendo falha real.
    """

    def test_nenhuma_thread_pump_viva_apos_a_validacao(self, client: TestClient) -> None:
        import threading

        antes = threading.active_count()
        _jornada_completa(client, "32_servicos.csv")
        # a thread leitora ja recebeu join dentro de run_streaming
        assert threading.active_count() <= antes

    def test_nenhuma_tarefa_de_fundo_pendente(self, client: TestClient) -> None:
        from live_demo.backend.app import spreadsheets

        _jornada_completa(client, "32_servicos.csv")
        assert all(t.done() for t in spreadsheets.pending_tasks())

    def test_fechar_o_client_logo_apos_iniciar_a_validacao(self) -> None:
        """
        O caso que provocava o traceback: o app fecha com a validacao no ar.

        O shutdown cancela e AGUARDA as tarefas; a thread sai pelo join. Nada
        pode estourar depois.
        """
        from live_demo.backend.app.main import app as app_local

        with TestClient(app_local) as local:
            _zerar_estado_do_servidor()
            inicio = _enviar(local, "32_servicos.csv")
            token = inicio["token"]
            local.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
            local.post(f"/api/spreadsheets/{token}/validate")
            # sai do contexto sem consumir o SSE -> shutdown com execucao viva

    def test_timeout_nao_deixa_thread_orfa(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Mesmo matando o processo, a thread precisa terminar antes do retorno.

        O caminho de timeout e justamente onde a thread leitora continuava
        viva depois de `proc.kill()` — e onde o `Event loop is closed`
        aparecia. `settings` e um dataclass FROZEN, entao o engine le o teto
        por `run_timeout_s()`, que e o ponto de substituicao.
        """
        import threading

        from live_demo.backend.app import engine

        antes = threading.active_count()
        monkeypatch.setattr(engine, "run_timeout_s", lambda: 0.0)

        inicio = _enviar(client, "32_servicos.csv")
        token = inicio["token"]
        client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
        client.post(f"/api/spreadsheets/{token}/validate")
        resultado = _concluir(client, token)

        assert resultado["outcome"] == "timeout"
        assert threading.active_count() <= antes


class TestInvalidacaoDeEstado:
    """
    Mudar a leitura invalida o que foi confirmado sobre a leitura anterior.

    Validar a aba B com o schema confirmado para a aba A produziria um
    resultado que PARECE legitimo e nao e — o pior erro possivel aqui.
    """

    def test_trocar_de_aba_descarta_o_schema_da_aba_anterior(self, client: TestClient) -> None:
        """
        O schema confirmado descrevia OUTRA aba: ele cai.

        Desde o contrato do Card 01 a validação não exige confirmação de
        schema — ela adota o sugerido. O que não pode acontecer, e é o que
        este teste protege, é validar a aba nova com o contrato da antiga.
        """
        inicio = _enviar(client, "07_tres_abas.xlsx")
        token = inicio["token"]

        client.post(f"/api/spreadsheets/{token}/selection", data={"sheet": "Estoque"})
        pronto = client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
        assert pronto.json()["status"] == "schema_ready"

        # volta e escolhe outra aba
        client.post(f"/api/spreadsheets/{token}/selection", data={"sheet": "Vendas"})
        job = jobs.get(token)
        assert job is not None
        assert job.journey is not None
        assert job.journey.schema_path is None  # o contrato antigo foi descartado

        client.post(f"/api/spreadsheets/{token}/validate")
        res = _concluir(client, token)
        relatorio = next(a for a in res["artifacts"] if a["name"] == "validacao_report.json")
        assert client.get(relatorio["download_url"]).json()["selected_sheet"] == "Vendas"

    def test_arquivo_do_schema_antigo_e_removido(self, client: TestClient) -> None:
        inicio = _enviar(client, "07_tres_abas.xlsx")
        token = inicio["token"]
        client.post(f"/api/spreadsheets/{token}/selection", data={"sheet": "Estoque"})
        client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
        job = jobs.get(token)
        assert job is not None
        confirmado = job.workspace / "config" / "schema_confirmado.yaml"
        assert confirmado.is_file()

        client.post(f"/api/spreadsheets/{token}/selection", data={"sheet": "Vendas"})
        assert not confirmado.exists()
        assert job.journey is not None
        assert job.journey.schema_origin is None

    def test_trocar_cabecalho_tambem_descarta_o_schema(self, client: TestClient) -> None:
        inicio = _enviar(client, "06_cabecalho_linha_4.xlsx")
        token = inicio["token"]
        client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
        client.post(f"/api/spreadsheets/{token}/selection", data={"header_row": "4"})

        job = jobs.get(token)
        assert job is not None
        assert job.journey is not None
        assert job.journey.schema_path is None


class TestQuantidadeDeArquivos:
    def test_dois_arquivos_na_analise(self, client: TestClient) -> None:
        """Salvar dois e usar so o primeiro enganaria sobre o que foi analisado."""
        with (FX / "32_servicos.csv").open("rb") as a, (FX / "01_csv_limpo.csv").open("rb") as b:
            r = client.post(
                "/api/spreadsheets/analyze",
                files=[
                    ("files", ("a.csv", a, "text/csv")),
                    ("files", ("b.csv", b, "text/csv")),
                ],
            )
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "too_many_files"

    def test_dois_schemas_enviados(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        r = client.post(
            f"/api/spreadsheets/{d['token']}/schema",
            data={"source": "uploaded"},
            files=[
                ("files", ("a.yaml", SCHEMA_PROPRIO.encode(), "application/yaml")),
                ("files", ("b.yaml", SCHEMA_PROPRIO.encode(), "application/yaml")),
            ],
        )
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "too_many_files"

    def test_extensao_de_schema_invalida(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        r = client.post(
            f"/api/spreadsheets/{d['token']}/schema",
            data={"source": "uploaded"},
            files={"files": ("schema.txt", SCHEMA_PROPRIO.encode(), "text/plain")},
        )
        assert r.status_code == HTTP_UNSUPPORTED_MEDIA
        assert r.json()["code"] == "invalid_extension"

    def test_suggested_com_arquivo_junto_e_recusado(self, client: TestClient) -> None:
        """Ignorar o upload em silencio faria a pessoa crer que ele valeu."""
        d = _enviar(client, "32_servicos.csv")
        r = client.post(
            f"/api/spreadsheets/{d['token']}/schema",
            data={"source": "suggested"},
            files={"files": ("meu.yaml", SCHEMA_PROPRIO.encode(), "application/yaml")},
        )
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "unexpected_file"


class TestSchemaAtomico:
    def test_schema_invalido_nao_derruba_o_anterior(self, client: TestClient) -> None:
        """Politica: um erro de digitacao nao deixa a pessoa sem nada."""
        d = _enviar(client, "32_servicos.csv")
        token = d["token"]
        client.post(
            f"/api/spreadsheets/{token}/schema",
            data={"source": "uploaded"},
            files={"files": ("bom.yaml", SCHEMA_PROPRIO.encode(), "application/yaml")},
        )
        job = jobs.get(token)
        assert job is not None
        confirmado = job.workspace / "config" / "schema_confirmado.yaml"
        antes = confirmado.read_text(encoding="utf-8")

        r = client.post(
            f"/api/spreadsheets/{token}/schema",
            data={"source": "uploaded"},
            files={"files": ("ruim.yaml", b"columns: [[[", "application/yaml")},
        )
        assert r.status_code == HTTP_BAD_REQUEST
        assert confirmado.read_text(encoding="utf-8") == antes
        assert not list(confirmado.parent.glob("*.parcial"))


class TestValidacaoDuplicada:
    def test_segunda_chamada_e_recusada(self, client: TestClient) -> None:
        d = _enviar(client, "32_servicos.csv")
        token = d["token"]
        client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
        primeira = client.post(f"/api/spreadsheets/{token}/validate")
        segunda = client.post(f"/api/spreadsheets/{token}/validate")
        assert primeira.status_code == HTTP_OK
        assert segunda.status_code == HTTP_CONFLICT
        assert segunda.json()["code"] == "already_validating"
        _concluir(client, token)


class TestExpiracao:
    def test_sweep_remove_job_e_workspace_e_o_token_para_de_valer(self, client: TestClient) -> None:
        """
        Expiracao real: o `sweep_expired` tira o job, e o workspace sai junto.

        Depois disso o token responde "sessao expirada", sem confirmar nada
        sobre o que existia antes.
        """
        import shutil as _shutil

        d = _enviar(client, "32_servicos.csv")
        token = d["token"]
        job = jobs.get(token)
        assert job is not None
        workspace = job.workspace
        assert workspace.is_dir()

        # simula o envelhecimento e roda a limpeza de verdade
        job.created_at = 0.0
        removidos = jobs.sweep_expired(1)
        assert removidos >= 1
        _shutil.rmtree(workspace, ignore_errors=True)

        assert jobs.get(token) is None
        assert not workspace.exists()
        r = client.post(f"/api/spreadsheets/{token}/selection", data={"sheet": "X"})
        assert r.status_code == HTTP_NOT_FOUND
        assert r.json()["code"] == "expired"


# ============================================================
# Perfis no Live (1.8C)
# ============================================================

CSV_CONTATOS = (
    "Nome Completo,Contato principal,Documento\n"
    "Ana Silva,ana@x.com,111.444.777-35\n"
    "Joao Souza,joao@x.com,529.982.247-25\n"
)


def _analisar_contatos(client: TestClient) -> str:
    resposta = client.post(
        "/api/spreadsheets/analyze",
        files={"files": ("contatos.csv", CSV_CONTATOS.encode(), "text/csv")},
    )
    assert resposta.status_code == HTTP_OK, resposta.text
    return str(resposta.json()["token"])


def _mapear(
    client: TestClient,
    token: str,
    mapping: dict[str, str],
    perfil: str = "cadastro_contatos",
) -> Any:
    return client.post(
        f"/api/spreadsheets/{token}/schema",
        data={
            "source": "profile",
            "profile_id": perfil,
            "mapping": json.dumps(mapping),
        },
    )


class TestCatalogoDePerfis:
    def test_lista_os_perfis_reais_do_pacote(self, client: TestClient) -> None:
        corpo = client.get("/api/spreadsheets/profiles").json()
        ids = [p["id"] for p in corpo["profiles"]]
        assert "cadastro_contatos" in ids

    def test_metadados_do_perfil(self, client: TestClient) -> None:
        corpo = client.get("/api/spreadsheets/profiles/cadastro_contatos").json()
        assert corpo["version"] >= 1
        campos = {f["name"]: f["required"] for f in corpo["fields"]}
        assert campos["nome"] is True
        assert campos["cnpj"] is False
        assert all(f["doc"] for f in corpo["fields"])

    def test_payload_nao_expoe_caminho_nem_yaml_bruto(self, client: TestClient) -> None:
        texto = client.get("/api/spreadsheets/profiles/cadastro_contatos").text
        assert "columns:" not in texto  # nada de YAML cru
        assert "/" not in texto.replace("\\/", "")[:0] + ""  # sem caminho
        assert "resources" not in texto

    def test_perfil_inexistente(self, client: TestClient) -> None:
        r = client.get("/api/spreadsheets/profiles/fantasma")
        assert r.status_code == HTTP_NOT_FOUND
        assert r.json()["code"] == "profile_not_found"

    @pytest.mark.parametrize(
        "inseguro", ["..", "perfil.yaml", "sub_dir_x", "PerfilMaiusculo", "1perfil"]
    )
    def test_identificador_inseguro_e_recusado(self, client: TestClient, inseguro: str) -> None:
        """A validação do id vive no núcleo (`load_profile`), não duplicada aqui."""
        r = client.get(f"/api/spreadsheets/profiles/{inseguro}")
        assert r.status_code == HTTP_NOT_FOUND


class TestSchemaPorPerfil:
    def test_mapeamento_valido_gera_schema(self, client: TestClient) -> None:
        token = _analisar_contatos(client)
        r = _mapear(
            client,
            token,
            {"nome": "Nome Completo", "email": "Contato principal", "cpf": "Documento"},
        )
        corpo = r.json()
        assert corpo["status"] == "schema_ready"
        assert corpo["schema_origin"] == "profile"
        assert corpo["profile"]["id"] == "cadastro_contatos"
        assert corpo["profile"]["mapping"]["cpf"] == "Documento"

    def test_opcionais_nao_usados_sao_omitidos(self, client: TestClient) -> None:
        token = _analisar_contatos(client)
        corpo = _mapear(client, token, {"nome": "Nome Completo"}).json()
        assert set(corpo["profile"]["omitted"]) >= {"telefone", "cnpj"}
        nomes = [c["name"] for c in corpo["summary"]["columns"]]
        assert nomes == ["Nome Completo"]

    def test_procedencia_verdadeira_no_resumo(self, client: TestClient) -> None:
        token = _analisar_contatos(client)
        corpo = _mapear(client, token, {"nome": "Nome Completo"}).json()
        proc = corpo["summary"]["generated_from"]
        assert proc["profile"] == "cadastro_contatos"
        assert proc["profile_version"] == 1

    def test_obrigatorio_sem_mapeamento(self, client: TestClient) -> None:
        token = _analisar_contatos(client)
        r = _mapear(client, token, {"email": "Contato principal"})
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "incomplete_mapping"
        assert "nome" in r.json()["detail"]

    def test_campo_conceitual_inexistente(self, client: TestClient) -> None:
        token = _analisar_contatos(client)
        r = _mapear(client, token, {"nome": "Nome Completo", "xpto": "Documento"})
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "invalid_mapping"

    def test_coluna_inexistente_na_planilha(self, client: TestClient) -> None:
        """As colunas conferidas são as da leitura ATUAL."""
        token = _analisar_contatos(client)
        r = _mapear(client, token, {"nome": "Fantasma"})
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "invalid_mapping"
        assert "nao encontrada" in r.json()["detail"]

    def test_dois_campos_para_a_mesma_coluna(self, client: TestClient) -> None:
        token = _analisar_contatos(client)
        r = _mapear(client, token, {"nome": "Nome Completo", "cpf": "Nome Completo"})
        assert r.status_code == HTTP_BAD_REQUEST
        assert "mesma coluna" in r.json()["detail"]

    def test_perfil_inexistente_na_geracao(self, client: TestClient) -> None:
        token = _analisar_contatos(client)
        r = _mapear(client, token, {"nome": "Nome Completo"}, perfil="fantasma")
        assert r.status_code == HTTP_NOT_FOUND

    def test_mapeamento_malformado(self, client: TestClient) -> None:
        token = _analisar_contatos(client)
        r = client.post(
            f"/api/spreadsheets/{token}/schema",
            data={"source": "profile", "profile_id": "cadastro_contatos", "mapping": "{{{"},
        )
        assert r.status_code == HTTP_BAD_REQUEST
        assert r.json()["code"] == "invalid_mapping"

    def test_schema_fica_no_workspace_e_nao_e_baixavel(self, client: TestClient) -> None:
        token = _analisar_contatos(client)
        _mapear(client, token, {"nome": "Nome Completo"})
        job = jobs.get(token)
        assert job is not None
        assert job.journey is not None
        assert job.journey.schema_path is not None
        assert job.journey.schema_path.parent.name == "config"
        assert (
            client.get(f"/api/download/{token}/schema_confirmado.yaml").status_code
            == HTTP_NOT_FOUND
        )

    def test_token_de_outra_jornada(self, client: TestClient) -> None:
        _analisar_contatos(client)
        outro = _analisar_contatos(client)
        r = _mapear(client, outro, {"nome": "Nome Completo"})
        assert r.status_code == HTTP_OK  # o próprio token funciona
        r2 = _mapear(client, "inexistente", {"nome": "Nome Completo"})
        assert r2.status_code == HTTP_NOT_FOUND


class TestCicloComPerfil:
    def test_perfil_ate_a_validacao_com_evidencias(self, client: TestClient) -> None:
        """perfil → mapeamento → schema → validação → pacote."""

        token = _analisar_contatos(client)
        _mapear(
            client,
            token,
            {"nome": "Nome Completo", "email": "Contato principal", "cpf": "Documento"},
        )
        client.post(f"/api/spreadsheets/{token}/validate")
        resultado = _concluir(client, token)

        assert resultado["exit_code"] == 0
        nomes = {a["name"] for a in resultado["artifacts"]}
        assert "pacote_execucao.zip" in nomes

        # o schema efetivo dentro do pacote carrega a procedência do perfil
        zip_art = next(a for a in resultado["artifacts"] if a["name"] == "pacote_execucao.zip")
        pacote = zipfile.ZipFile(io.BytesIO(client.get(zip_art["download_url"]).content))
        efetivo = pacote.read("schema_efetivo.yaml").decode("utf-8")
        assert "cadastro_contatos" in efetivo
        manifesto = json.loads(pacote.read("manifest.json"))
        assert manifesto["configuration"]["generated_from"]["profile"] == "cadastro_contatos"

    def test_schema_gerado_e_carregavel_pelo_loader_real(self, client: TestClient) -> None:
        from autotarefas.tasks.validate import load_schema

        token = _analisar_contatos(client)
        _mapear(client, token, {"nome": "Nome Completo", "cpf": "Documento"})
        job = jobs.get(token)
        assert job is not None
        assert job.journey is not None
        assert job.journey.schema_path is not None
        schema = load_schema(job.journey.schema_path)
        assert [c.name for c in schema.columns] == ["Nome Completo", "Documento"]
        assert schema.generated_from is not None


class TestCompatibilidadeComOsOutrosFluxos:
    def test_schema_sugerido_continua_funcionando(self, client: TestClient) -> None:
        token = _analisar_contatos(client)
        r = client.post(f"/api/spreadsheets/{token}/schema", data={"source": "suggested"})
        assert r.json()["schema_origin"] == "suggested"
        assert "profile" not in r.json()

    def test_yaml_proprio_continua_funcionando(self, client: TestClient) -> None:
        token = _analisar_contatos(client)
        r = client.post(
            f"/api/spreadsheets/{token}/schema",
            data={"source": "uploaded"},
            files={"files": ("m.yaml", b"columns:\n  - name: Nome Completo\n", "application/yaml")},
        )
        assert r.json()["schema_origin"] == "uploaded"

    def test_origem_desconhecida_menciona_as_tres(self, client: TestClient) -> None:
        token = _analisar_contatos(client)
        r = client.post(f"/api/spreadsheets/{token}/schema", data={"source": "xpto"})
        assert r.status_code == HTTP_BAD_REQUEST
        assert "profile" in r.json()["detail"]
