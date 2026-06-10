"""
Task de envio de mensagens via Telegram (Bot API).

A SendTelegramTask le uma planilha, monta uma mensagem por linha a partir
de um template ({coluna} -> valor) e envia via Bot API (sendMessage). E a
irma da SendApiTask/SendEmailTask: mesma forma (retry resiliente, relatorio
por linha, dry-run), para notificacoes gratuitas pelo Telegram.

O destino (chat) pode ser fixo (`chat_id`) ou vir de uma coluna da planilha
(`chat_id_column`). O `base_url` e configuravel: nos testes/demo aponta para
o mock local; em producao, para https://api.telegram.org.

Decima primeira task (decima primeira subclasse concreta de BaseTask).

SEGURANCA: o token do bot e sensivel. Ele nunca aparece em logs, no audit
nem no resultado — so e usado internamente para montar a URL.
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx
import pandas as pd
from tenacity import (
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.core.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable

# ============================================================
# Constantes
# ============================================================

_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_MAX_RETRIES = 3
_HTTP_SERVER_ERROR = 500
_ERROR_TEXT_LIMIT = 120

_DEFAULT_BASE_URL = "https://api.telegram.org"
_PLANILHA_FORMATS = (".csv", ".xlsx", ".xls")
_REPORT_FORMATS = (".csv", ".xlsx", ".xls", ".json")
_VALID_PARSE_MODES = ("MarkdownV2", "Markdown", "HTML")

ProgressInfo = dict[str, Any]


# ============================================================
# Predicado de retry (igual a SendApiTask)
# ============================================================


def _is_retryable(exc: BaseException) -> bool:
    """Retry em erros temporarios (transporte/timeout e HTTP 5xx)."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return int(exc.response.status_code) >= _HTTP_SERVER_ERROR
    return False


# ============================================================
# Task
# ============================================================


class SendTelegramTask(BaseTask):
    """Envia mensagens via Telegram (Bot API) a partir de uma planilha."""

    name = "send_telegram"
    description = "Envia mensagens via Telegram (Bot API) a partir de uma planilha"

    def __init__(  # noqa: PLR0913 - task de config com parametros keyword-only
        self,
        planilha_path: Path,
        *,
        token: str,
        text_template: str,
        chat_id: str | None = None,
        chat_id_column: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        parse_mode: str | None = None,
        delay_s: float = 0.0,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        report_path: Path | None = None,
        on_progress: Callable[[ProgressInfo], None] | None = None,
        dry_run: bool = False,
    ) -> None:
        """
        Args:
            planilha_path: Planilha CSV/XLSX com os dados.
            token: Token do bot (sensivel; nunca logado).
            text_template: Template da mensagem (aceita {coluna}).
            chat_id: Destino fixo (todas as mensagens vao para este chat).
            chat_id_column: OU a coluna da planilha com o chat_id de cada linha.
            base_url: Base da API (default Telegram; mock nos testes).
            parse_mode: Formatacao opcional (MarkdownV2/Markdown/HTML).
            delay_s: Pausa em segundos entre envios (rate limit).
            timeout_s: Timeout de cada request.
            max_retries: Tentativas por mensagem em erro temporario.
            report_path: Se informado, salva relatorio por linha (.csv/.xlsx/.json).
            on_progress: Callback chamado a cada mensagem.
            dry_run: Se True, nao envia nada; so conta as linhas.
        """
        super().__init__(dry_run=dry_run)

        if not token or not token.strip():
            msg = "token nao pode ser vazio"
            raise ValidationError(msg)

        if not text_template or not text_template.strip():
            msg = "text_template nao pode ser vazio"
            raise ValidationError(msg)

        suffix = planilha_path.suffix.lower()
        if suffix not in _PLANILHA_FORMATS:
            msg = (
                f"Formato de planilha nao suportado: '{suffix}'. "
                f"Use: {', '.join(_PLANILHA_FORMATS)}"
            )
            raise ValidationError(msg)

        if chat_id is None and chat_id_column is None:
            msg = "Informe chat_id (fixo) OU chat_id_column (coluna da planilha)"
            raise ValidationError(msg)
        if chat_id is not None and chat_id_column is not None:
            msg = "Informe apenas um: chat_id OU chat_id_column, nao ambos"
            raise ValidationError(msg)

        if not base_url.startswith(("http://", "https://")):
            msg = "base_url deve comecar com http:// ou https://"
            raise ValidationError(msg)

        if parse_mode is not None and parse_mode not in _VALID_PARSE_MODES:
            msg = (
                f"parse_mode invalido: '{parse_mode}'. "
                f"Use um de: {', '.join(_VALID_PARSE_MODES)} (ou nenhum)"
            )
            raise ValidationError(msg)

        if report_path is not None:
            rep_suffix = report_path.suffix.lower()
            if rep_suffix not in _REPORT_FORMATS:
                msg = (
                    f"Formato de relatorio nao suportado: '{rep_suffix}'. "
                    f"Use: {', '.join(_REPORT_FORMATS)}"
                )
                raise ValidationError(msg)

        if delay_s < 0:
            msg = "delay_s nao pode ser negativo"
            raise ValidationError(msg)

        self.planilha_path = planilha_path
        self.token = token.strip()
        self.text_template = text_template
        self.chat_id = chat_id
        self.chat_id_column = chat_id_column
        self.base_url = base_url.rstrip("/")
        self.parse_mode = parse_mode
        self.delay_s = delay_s
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.report_path = report_path
        self.on_progress = on_progress

    # --------------------------------------------------------
    # Planilha
    # --------------------------------------------------------

    def _read_planilha(self) -> pd.DataFrame:
        """Le a planilha como texto (faltantes viram '')."""
        suffix = self.planilha_path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(self.planilha_path, dtype=str)
        else:
            df = pd.read_excel(self.planilha_path, dtype=str)
        return df.fillna("")

    # --------------------------------------------------------
    # Template / destino
    # --------------------------------------------------------

    def _render(self, template: str, row: dict[str, Any]) -> str:
        """Substitui {coluna} pelos valores da linha (faltantes -> '')."""
        safe: defaultdict[str, str] = defaultdict(str)
        for k, v in row.items():
            safe[str(k)] = str(v)
        try:
            return template.format_map(safe)
        except (IndexError, ValueError):
            # template malformado (ex: chave entre chaves solta) -> literal
            return template

    def _resolve_chat_id(self, row: dict[str, Any]) -> str:
        """Resolve o chat_id de uma linha (fixo ou da coluna)."""
        if self.chat_id is not None:
            return self.chat_id
        col = self.chat_id_column
        if col is None:  # pragma: no cover - garantido pelo __init__
            return ""
        return str(row.get(col, "")).strip()

    # --------------------------------------------------------
    # Envio (HTTP) com retry
    # --------------------------------------------------------

    def _endpoint(self) -> str:
        """URL do sendMessage (contem o token; uso interno apenas)."""
        return f"{self.base_url}/bot{self.token}/sendMessage"

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        """POST de uma mensagem (sem retry). Levanta em status >= 400."""
        response = httpx.post(
            self._endpoint(),
            json=payload,
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        return response

    def _post_with_retry(self, payload: dict[str, Any]) -> httpx.Response:
        """POST com retry (backoff exponencial) em erros temporarios."""
        retryer = Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )
        result: httpx.Response = retryer(self._post, payload)
        return result

    def _extrair_erro(self, response: httpx.Response) -> str:
        """Extrai a 'description' do corpo de erro da Bot API."""
        try:
            body = response.json()
        except ValueError:
            error_text: str = response.text
            return error_text[:_ERROR_TEXT_LIMIT]

        if isinstance(body, dict):
            desc = str(body.get("description", "")).strip()
            if desc:
                return desc[:_ERROR_TEXT_LIMIT]

        fallback_text: str = response.text
        return fallback_text[:_ERROR_TEXT_LIMIT]

    def _enviar_um(self, chat_id: str, text: str) -> tuple[bool, str]:
        """
        Envia uma mensagem. Retorna (sucesso, mensagem).

        - 2xx e ok=true: (True, "enviado")
        - 4xx: (False, "HTTP 4xx: ...") - nao foi retentado
        - 5xx apos retries / erro de conexao: (False, "...")
        """
        if not chat_id:
            return False, "chat_id vazio"

        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if self.parse_mode:
            payload["parse_mode"] = self.parse_mode

        try:
            response = self._post_with_retry(payload)
        except httpx.HTTPStatusError as exc:
            status = int(exc.response.status_code)
            return False, f"HTTP {status}: {self._extrair_erro(exc.response)}"
        except httpx.HTTPError as exc:
            return False, f"erro de conexao: {exc}"

        # Bot API pode sinalizar erro tambem no corpo (ok=false)
        try:
            body = response.json()
        except ValueError:
            return True, "enviado"
        if isinstance(body, dict) and body.get("ok") is False:
            return False, str(body.get("description", "resposta ok=false"))
        return True, "enviado"

    # --------------------------------------------------------
    # Progresso
    # --------------------------------------------------------

    def _notify(
        self,
        linha: int,
        total: int,
        *,
        sucesso: bool,
        mensagem: str,
    ) -> None:
        """Chama o callback de progresso; nunca quebra a task."""
        if self.on_progress is None:
            return
        try:
            self.on_progress(
                {
                    "linha": linha,
                    "total": total,
                    "sucesso": sucesso,
                    "mensagem": mensagem,
                },
            )
        except Exception:  # noqa: BLE001 - callback do usuario nao pode quebrar a task
            logger.warning("Callback de progresso levantou excecao; ignorando")

    # --------------------------------------------------------
    # Relatorio
    # --------------------------------------------------------

    def _salvar_relatorio(self, resultados: list[dict[str, Any]], path: Path) -> None:
        """Salva o relatorio por linha no formato indicado pela extensao."""
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(resultados)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df.to_csv(path, index=False)
        elif suffix in (".xlsx", ".xls"):
            df.to_excel(path, index=False)
        elif suffix == ".json":
            df.to_json(path, orient="records", indent=2, force_ascii=False)
        else:  # pragma: no cover - validado no __init__
            msg = f"Formato nao suportado: {suffix}"
            raise ValidationError(msg)

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    def execute(self) -> TaskResult:  # noqa: PLR0912
        """Executa o envio das mensagens."""
        started_at = datetime.now(UTC)

        # Ler planilha
        try:
            df = self._read_planilha()
        except (OSError, ValueError) as exc:
            logger.error(f"Falha ao ler a planilha: {exc}")
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=f"Erro ao ler a planilha: {exc}",
            )

        # Valida a coluna de chat_id (quando usada)
        if self.chat_id_column is not None and self.chat_id_column not in df.columns:
            msg = (
                f"Coluna de chat_id '{self.chat_id_column}' nao encontrada. "
                f"Colunas: {', '.join(df.columns)}"
            )
            logger.error(msg)
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=msg,
            )

        total = len(df)
        rows = [
            {str(key): value for key, value in row.items()}
            for row in cast(list[dict[Any, Any]], df.to_dict("records"))
        ]
        logger.info(f"Enviando {total} mensagens via Telegram (base: {self.base_url})")

        # Planilha vazia: nao e erro
        if total == 0:
            logger.warning("Planilha sem linhas")
            return self._make_result(
                status=TaskStatus.SUCCESS,
                started_at=started_at,
                rows_affected=0,
                data={
                    "total": 0,
                    "enviados": 0,
                    "falhas": 0,
                    "base_url": self.base_url,
                    "warning": "Planilha sem linhas",
                },
            )

        # Dry-run: nao envia (mostra um exemplo da 1a mensagem)
        if self.dry_run:
            exemplo = self._render(self.text_template, rows[0])
            logger.info(f"[dry-run] Enviaria {total} mensagens")
            return self._make_result(
                status=TaskStatus.SUCCESS,
                started_at=started_at,
                data={
                    "dry_run": True,
                    "would_send": total,
                    "exemplo_texto": exemplo[:200],
                    "base_url": self.base_url,
                    "planilha": str(self.planilha_path),
                },
            )

        # Envio real
        resultados: list[dict[str, Any]] = []
        enviados = 0
        falhas = 0

        for idx, row in enumerate(rows, start=1):
            chat = self._resolve_chat_id(row)
            texto = self._render(self.text_template, row)
            sucesso, mensagem = self._enviar_um(chat, texto)

            registro = dict(row)
            registro["_chat_id"] = chat
            registro["_texto"] = texto
            registro["_resultado"] = "ok" if sucesso else "erro"
            registro["_mensagem"] = mensagem
            resultados.append(registro)

            if sucesso:
                enviados += 1
            else:
                falhas += 1

            self._notify(idx, total, sucesso=sucesso, mensagem=mensagem)

            if self.delay_s > 0 and idx < total:
                time.sleep(self.delay_s)

        # Relatorio
        report_saved: str | None = None
        if self.report_path is not None:
            try:
                self._salvar_relatorio(resultados, self.report_path)
                report_saved = str(self.report_path)
            except (OSError, ValueError) as exc:
                logger.warning(f"Falha ao salvar relatorio: {exc}")

        # Status agregado
        if falhas == 0:
            status = TaskStatus.SUCCESS
        elif enviados == 0:
            status = TaskStatus.FAILURE
        else:
            status = TaskStatus.PARTIAL

        logger.info(f"Envio concluido: {enviados} enviados, {falhas} falhas")
        return self._make_result(
            status=status,
            started_at=started_at,
            rows_affected=enviados,
            rows_failed=falhas,
            data={
                "total": total,
                "enviados": enviados,
                "falhas": falhas,
                "base_url": self.base_url,
                "planilha": str(self.planilha_path),
                "report_path": report_saved,
            },
        )


__all__ = ["SendTelegramTask"]
