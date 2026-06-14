"""
Testes da SendTelegramTask.

ESTRATEGIA:
- Mocka httpx.post (module-level) por um fake configuravel que devolve
  httpx.Response REAIS (raise_for_status funciona) e registra chamadas.
- tenacity.nap.sleep mockado (retry instantaneo).
- Sem rede real.

Cobre: validacao do construtor (incl. timeout/max_retries), normalizacao
de chat_id, template, destino fixo/coluna, recusa local de chat/texto
vazios, retry (5xx recupera/esgota, 4xx nao retenta), redacao do token em
erros, status agregado, dry-run, planilha vazia, coluna inexistente, e
relatorio (sem _texto, com metadados).
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

import httpx
import pandas as pd
import pytest

from autotarefas.core.base import TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.send_telegram import SendTelegramTask

if TYPE_CHECKING:
    from pathlib import Path

tg = importlib.import_module("autotarefas.tasks.send_telegram")

TOKEN = "123456789:AAH-super-secret-token"
BASE = "http://test.local"


# ============================================================
# Helpers / fixtures
# ============================================================


def make_planilha(
    tmp_path: Path,
    linhas: list[str],
    header: str = "nome,saldo,chat_id",
    nome: str = "dados.csv",
) -> Path:
    p = tmp_path / nome
    p.write_text("\n".join([header, *linhas]) + "\n", encoding="utf-8")
    return p


def make_task(planilha: Path, **kw: Any) -> SendTelegramTask:
    defaults: dict[str, Any] = {
        "token": TOKEN,
        "text_template": "Ola {nome}!",
        "chat_id_column": "chat_id",
        "base_url": BASE,
    }
    defaults.update(kw)
    return SendTelegramTask(planilha_path=planilha, **defaults)


@pytest.fixture
def mock_post(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """
    Mocka httpx.post. Configure:
      state["status_queue"]: lista de status (consumida por chamada); vazio = 200
      state["ok"]: valor do campo "ok" no corpo 200 (default True)
      state["description"]: descricao de erro
      state["raise"]: excecao a levantar (ex: httpx.ConnectError)
    Inspecione: state["calls"] (lista de {url, json, timeout}).
    """
    state: dict[str, Any] = {
        "status_queue": [],
        "ok": True,
        "description": "Bad Request",
        "raise": None,
        "calls": [],
    }

    def fake_post(
        url: str,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
        **_kw: Any,
    ) -> httpx.Response:
        state["calls"].append({"url": url, "json": json, "timeout": timeout})
        if state["raise"] is not None:
            raise state["raise"]
        code = state["status_queue"].pop(0) if state["status_queue"] else 200
        req = httpx.Request("POST", url)
        payload = json or {}
        if code == 200:
            body: dict[str, Any] = {"ok": state["ok"]}
            if state["ok"]:
                body["result"] = {
                    "message_id": len(state["calls"]),
                    "chat": {"id": payload.get("chat_id")},
                    "text": payload.get("text"),
                }
            else:
                body["description"] = state["description"]
            return httpx.Response(200, json=body, request=req)
        return httpx.Response(
            code,
            json={"ok": False, "error_code": code, "description": state["description"]},
            request=req,
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    return state


@pytest.fixture
def _fast_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tenacity.nap.sleep", lambda _s: None)


# ============================================================
# Helper puro: _normalizar_chat_id
# ============================================================


class TestNormalizarChatId:
    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("111", "111"),
            ("111.0", "111"),
            ("111.00", "111"),
            ("-100123.0", "-100123"),
            ("  42  ", "42"),
            ("@meu_canal", "@meu_canal"),
            ("111.05", "111.05"),  # nao e inteiro-como-float
            (111, "111"),  # int -> str
        ],
    )
    def test_normaliza(self, entrada: object, esperado: str) -> None:
        assert tg._normalizar_chat_id(entrada) == esperado


# ============================================================
# Construtor
# ============================================================


class TestConstrutor:
    def test_token_vazio(self, tmp_path: Path) -> None:
        p = make_planilha(tmp_path, ["Ana,1,42"])
        with pytest.raises(ValidationError):
            make_task(p, token="  ")

    def test_text_vazio(self, tmp_path: Path) -> None:
        p = make_planilha(tmp_path, ["Ana,1,42"])
        with pytest.raises(ValidationError):
            make_task(p, text_template="   ")

    def test_planilha_formato_invalido(self, tmp_path: Path) -> None:
        p = tmp_path / "x.txt"
        p.write_text("nada", encoding="utf-8")
        with pytest.raises(ValidationError):
            make_task(p)

    def test_sem_destino(self, tmp_path: Path) -> None:
        p = make_planilha(tmp_path, ["Ana,1,42"])
        with pytest.raises(ValidationError):
            SendTelegramTask(
                planilha_path=p,
                token=TOKEN,
                text_template="oi",
                base_url=BASE,
            )

    def test_ambos_destinos(self, tmp_path: Path) -> None:
        p = make_planilha(tmp_path, ["Ana,1,42"])
        with pytest.raises(ValidationError):
            SendTelegramTask(
                planilha_path=p,
                token=TOKEN,
                text_template="oi",
                chat_id="1",
                chat_id_column="chat_id",
                base_url=BASE,
            )

    def test_base_url_invalida(self, tmp_path: Path) -> None:
        p = make_planilha(tmp_path, ["Ana,1,42"])
        with pytest.raises(ValidationError):
            make_task(p, base_url="ftp://x")

    def test_parse_mode_invalido(self, tmp_path: Path) -> None:
        p = make_planilha(tmp_path, ["Ana,1,42"])
        with pytest.raises(ValidationError):
            make_task(p, parse_mode="Latex")

    def test_report_formato_invalido(self, tmp_path: Path) -> None:
        p = make_planilha(tmp_path, ["Ana,1,42"])
        with pytest.raises(ValidationError):
            make_task(p, report_path=tmp_path / "r.txt")

    def test_delay_negativo(self, tmp_path: Path) -> None:
        p = make_planilha(tmp_path, ["Ana,1,42"])
        with pytest.raises(ValidationError):
            make_task(p, delay_s=-1.0)

    def test_timeout_invalido(self, tmp_path: Path) -> None:
        p = make_planilha(tmp_path, ["Ana,1,42"])
        with pytest.raises(ValidationError):
            make_task(p, timeout_s=0)

    def test_max_retries_invalido(self, tmp_path: Path) -> None:
        p = make_planilha(tmp_path, ["Ana,1,42"])
        with pytest.raises(ValidationError):
            make_task(p, max_retries=0)

    def test_chat_id_fixo_normalizado(self, tmp_path: Path) -> None:
        p = make_planilha(tmp_path, ["Ana,1,42"])
        task = SendTelegramTask(
            planilha_path=p,
            token=TOKEN,
            text_template="oi",
            chat_id="111.0",
            base_url=BASE,
        )
        assert task.chat_id == "111"

    def test_chat_id_fixo_vazio(self, tmp_path: Path) -> None:
        p = make_planilha(tmp_path, ["Ana,1,42"])
        with pytest.raises(ValidationError):
            SendTelegramTask(
                planilha_path=p,
                token=TOKEN,
                text_template="oi",
                chat_id="   ",
                base_url=BASE,
            )


# ============================================================
# Template e destino
# ============================================================


class TestRenderEDestino:
    def test_render_substitui(self, tmp_path: Path) -> None:
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]))
        assert task._render("Ola {nome}, saldo {saldo}", {"nome": "Ana", "saldo": "9"}) == (
            "Ola Ana, saldo 9"
        )

    def test_render_campo_ausente_vazio(self, tmp_path: Path) -> None:
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]))
        assert task._render("Oi {sobrenome}", {"nome": "Ana"}) == "Oi "

    def test_render_malformado_vira_literal(self, tmp_path: Path) -> None:
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]))
        # chave numerica posicional invalida -> retorna literal sem quebrar
        assert task._render("Oi {0}", {"nome": "Ana"}) == "Oi {0}"

    def test_resolve_chat_id_coluna_normaliza(self, tmp_path: Path) -> None:
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]))
        assert task._resolve_chat_id({"chat_id": "55.0"}) == "55"

    def test_resolve_chat_id_fixo(self, tmp_path: Path) -> None:
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]), chat_id="9", chat_id_column=None)
        assert task._resolve_chat_id({"chat_id": "ignorado"}) == "9"


# ============================================================
# _enviar_um (com mock)
# ============================================================


@pytest.mark.usefixtures("_fast_retry")
class TestEnviarUm:
    def test_sucesso(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]))
        ok, msg = task._enviar_um("42", "oi")
        assert ok is True
        assert msg == "enviado"
        assert len(mock_post["calls"]) == 1

    def test_chat_vazio_nao_envia(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]))
        ok, msg = task._enviar_um("", "oi")
        assert ok is False
        assert "chat_id" in msg
        assert mock_post["calls"] == []

    def test_texto_vazio_nao_envia(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]))
        ok, msg = task._enviar_um("42", "   ")
        assert ok is False
        assert "texto" in msg
        assert mock_post["calls"] == []

    def test_4xx_nao_retenta(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        mock_post["status_queue"] = [400]
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]))
        ok, _ = task._enviar_um("42", "oi")
        assert ok is False
        assert len(mock_post["calls"]) == 1  # nao retentou

    def test_5xx_recupera(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        mock_post["status_queue"] = [500, 200]
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]))
        ok, _ = task._enviar_um("42", "oi")
        assert ok is True
        assert len(mock_post["calls"]) == 2

    def test_5xx_esgota(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        mock_post["status_queue"] = [500, 500, 500]
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]), max_retries=3)
        ok, _ = task._enviar_um("42", "oi")
        assert ok is False
        assert len(mock_post["calls"]) == 3

    def test_ok_false_no_corpo(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        mock_post["ok"] = False
        mock_post["description"] = "chat not found"
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]))
        ok, msg = task._enviar_um("42", "oi")
        assert ok is False
        assert "chat not found" in msg

    def test_erro_conexao_redige_token(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        # excecao cuja string contem a URL com o token
        url = f"{BASE}/bot{TOKEN}/sendMessage"
        mock_post["raise"] = httpx.ConnectError(
            f"falha ao conectar em {url}",
            request=httpx.Request("POST", url),
        )
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]))
        ok, msg = task._enviar_um("42", "oi")
        assert ok is False
        assert TOKEN not in msg  # token foi redigido
        assert "***" in msg

    def test_status_error_nao_vaza_token(
        self,
        tmp_path: Path,
        mock_post: dict[str, Any],
    ) -> None:
        mock_post["status_queue"] = [404]
        mock_post["description"] = "Not Found"
        task = make_task(make_planilha(tmp_path, ["Ana,1,42"]))
        ok, msg = task._enviar_um("42", "oi")
        assert ok is False
        assert TOKEN not in msg


# ============================================================
# execute (com mock)
# ============================================================


@pytest.mark.usefixtures("_fast_retry")
class TestExecute:
    def test_sucesso_total(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        p = make_planilha(tmp_path, ["Ana,1,11", "Bruno,2,22"])
        result = make_task(p).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 2
        assert result.rows_failed == 0

    def test_partial(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        # 1a ok (200), 2a falha (400)
        mock_post["status_queue"] = [200, 400]
        p = make_planilha(tmp_path, ["Ana,1,11", "Bruno,2,22"])
        result = make_task(p).run()
        assert result.status == TaskStatus.PARTIAL
        assert result.rows_affected == 1
        assert result.rows_failed == 1

    def test_failure_total(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        mock_post["status_queue"] = [400, 400]
        p = make_planilha(tmp_path, ["Ana,1,11", "Bruno,2,22"])
        result = make_task(p).run()
        assert result.status == TaskStatus.FAILURE
        assert result.rows_affected == 0

    def test_planilha_vazia(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        p = make_planilha(tmp_path, [])  # so cabecalho
        result = make_task(p).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 0
        assert mock_post["calls"] == []

    def test_coluna_chat_inexistente(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        p = make_planilha(tmp_path, ["Ana,1"], header="nome,saldo")
        result = make_task(p, chat_id_column="chat_id").run()
        assert result.status == TaskStatus.FAILURE
        assert mock_post["calls"] == []

    def test_dry_run_nao_envia(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        p = make_planilha(tmp_path, ["Ana,1,11", "Bruno,2,22"])
        result = make_task(p, dry_run=True).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.data["would_send"] == 2
        assert mock_post["calls"] == []  # nada enviado

    def test_chat_id_coluna_normalizado_no_envio(
        self,
        tmp_path: Path,
        mock_post: dict[str, Any],
    ) -> None:
        # chat_id "11.0" na planilha deve chegar "11" no payload
        p = make_planilha(tmp_path, ["Ana,1,11.0"])
        make_task(p).run()
        assert mock_post["calls"][0]["json"]["chat_id"] == "11"

    def test_relatorio_sem_texto_com_metadados(
        self,
        tmp_path: Path,
        mock_post: dict[str, Any],
    ) -> None:
        p = make_planilha(tmp_path, ["Ana,1,11"])
        rep = tmp_path / "rel.csv"
        make_task(p, report_path=rep).run()
        assert rep.exists()
        df = pd.read_csv(rep)
        cols = set(df.columns)
        # nao persiste o conteudo da mensagem
        assert "_texto" not in cols
        # mas mantem destino + status
        assert {"_chat_id", "_resultado", "_mensagem"} <= cols
        assert df.iloc[0]["_resultado"] == "ok"


# ============================================================
# _is_retryable
# ============================================================


class TestIsRetryable:
    def test_transport(self) -> None:
        assert tg._is_retryable(httpx.ConnectError("x")) is True

    def test_timeout(self) -> None:
        assert tg._is_retryable(httpx.ReadTimeout("x")) is True

    def test_5xx(self) -> None:
        req = httpx.Request("POST", BASE)
        exc = httpx.HTTPStatusError("e", request=req, response=httpx.Response(503, request=req))
        assert tg._is_retryable(exc) is True

    def test_4xx(self) -> None:
        req = httpx.Request("POST", BASE)
        exc = httpx.HTTPStatusError("e", request=req, response=httpx.Response(404, request=req))
        assert tg._is_retryable(exc) is False

    def test_outra(self) -> None:
        assert tg._is_retryable(ValueError("x")) is False
