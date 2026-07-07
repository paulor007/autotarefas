"""
Task de envio de dados via API REST (POST em massa).

A SendApiTask le uma planilha (CSV/XLSX) e envia cada linha para uma
API, fazendo POST de um JSON por registro. E o complemento da
ExtractApiTask: enquanto aquela LE dados de uma API, esta ESCREVE.

Caso de uso tipico: cadastrar centenas/milhares de registros no
sistema de uma empresa que exponha uma API REST (muito mais rapido
que automacao via navegador).

Recursos:
- Tolerancia a falhas POR LINHA (uma linha ruim nao para as outras)
- Retry inteligente (tenacity) em erros TEMPORARIOS: timeout/conexao,
  HTTP 5xx e HTTP 429 (rate limit). A espera respeita o Retry-After da
  API quando informado; sem o header, backoff exponencial com jitter.
  Erros de dado/configuracao (400/409/422/...) NAO sao retentados.
- Idempotencia: cada registro envia um header Idempotency-Key
  deterministico (mesma linha = mesma chave, em toda tentativa e em
  todo reenvio) — sistemas compativeis nao duplicam o cadastro.
- Rate limiting (delay configuravel entre envios)
- Autenticacao opcional: header X-API-Key e/ou Bearer token
- Relatorio opcional (CSV/XLSX/JSON) com o resultado de cada linha
- dry-run: nao envia nada, mostra quantas linhas iriam

Setima subclasse concreta de BaseTask.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pandas as pd
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.core.logger import logger
from autotarefas.tasks.send_result import (
    ItemEnvio,
    classify_status,
    extract_external_id,
    falhas_por_categoria,
    idempotency_key,
    parse_retry_after,
    total_reenviaveis,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# ============================================================
# Constantes
# ============================================================

_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_MAX_RETRIES = 3
_HTTP_SERVER_ERROR = 500
_HTTP_TOO_MANY_REQUESTS = 429
_ERROR_TEXT_LIMIT = 120

#: Teto para o Retry-After informado pela API (defesa contra travar o
#: lote por causa de um header exagerado; o restante fica p/ reenvio).
_RETRY_AFTER_CAP_S = 30.0

_PLANILHA_FORMATS = (".csv", ".xlsx", ".xls")
_REPORT_FORMATS = (".csv", ".xlsx", ".xls", ".json")

ProgressInfo = dict[str, Any]


# ============================================================
# Predicado de retry e espera inteligente
# ============================================================


def _is_retryable(exc: BaseException) -> bool:
    """
    Decide se uma excecao justifica nova tentativa.

    Retry em erros TEMPORARIOS:
    - httpx.TransportError: timeout e erros de rede/conexao
    - HTTP 429 (rate limit): o servidor pediu calma, nao recusou o dado
    - HTTP >= 500: erro do servidor

    NAO faz retry nos 4xx de dado/configuracao (400/409/422/...):
    reenviar o mesmo conteudo nao mudaria o resultado.
    """
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = int(exc.response.status_code)
        return status_code == _HTTP_TOO_MANY_REQUESTS or status_code >= _HTTP_SERVER_ERROR
    return False


#: Backoff exponencial com jitter (espalha as retentativas no tempo,
#: evitando que varias linhas martelam a API no mesmo instante).
_FALLBACK_WAIT = wait_exponential_jitter(initial=0.5, max=5.0)


def _smart_wait(retry_state: RetryCallState) -> float:
    """
    Espera entre tentativas: respeita o Retry-After da API quando houver.

    Se a falha foi um 429 (ou qualquer HTTPStatusError) com header
    ``Retry-After: <segundos>``, aguarda exatamente o que a API pediu
    (limitado a `_RETRY_AFTER_CAP_S`). Sem o header, cai no backoff
    exponencial com jitter.
    """
    outcome = retry_state.outcome
    if outcome is not None and outcome.failed:
        exc = outcome.exception()
        if isinstance(exc, httpx.HTTPStatusError):
            seconds = parse_retry_after(exc.response.headers.get("Retry-After"))
            if seconds is not None:
                return min(seconds, _RETRY_AFTER_CAP_S)
    return float(_FALLBACK_WAIT(retry_state))


# ============================================================
# Task
# ============================================================


class SendApiTask(BaseTask):
    """Envia registros de uma planilha para uma API REST (POST)."""

    name = "send_api"
    description = "Envia registros de uma planilha para uma API (POST em massa)"

    def __init__(  # noqa: PLR0913 - task de config com parametros keyword-only
        self,
        planilha_path: Path,
        url: str,
        *,
        api_key: str | None = None,
        bearer_token: str | None = None,
        delay_s: float = 0.0,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        report_path: Path | None = None,
        on_progress: Callable[[ProgressInfo], None] | None = None,
        dry_run: bool = False,
    ) -> None:
        """
        Args:
            planilha_path: Planilha CSV/XLSX com os dados a enviar.
            url: Endpoint da API (recebe POST de cada linha).
            api_key: Chave opcional (header X-API-Key).
            bearer_token: Token opcional (header Authorization: Bearer).
            delay_s: Pausa em segundos entre envios (rate limit).
            timeout_s: Timeout de cada request.
            max_retries: Tentativas por linha em erro temporario.
            report_path: Se informado, salva relatorio por linha
                (.csv/.xlsx/.json).
            on_progress: Callback chamado a cada linha enviada.
            dry_run: Se True, nao envia nada; so conta as linhas.
        """
        super().__init__(dry_run=dry_run)

        if not url or not url.strip():
            msg = "url nao pode ser vazio"
            raise ValidationError(msg)

        suffix = planilha_path.suffix.lower()
        if suffix not in _PLANILHA_FORMATS:
            msg = (
                f"Formato de planilha nao suportado: '{suffix}'. "
                f"Use: {', '.join(_PLANILHA_FORMATS)}"
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

        if timeout_s <= 0:
            msg = "timeout_s deve ser maior que zero"
            raise ValidationError(msg)

        if max_retries < 1:
            msg = "max_retries deve ser >= 1"
            raise ValidationError(msg)

        self.planilha_path = planilha_path
        self.url = url.strip()
        self.api_key = api_key
        self.bearer_token = bearer_token
        self.delay_s = delay_s
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.report_path = report_path
        self.on_progress = on_progress
        #: DataFrame lido da planilha (preenchido no execute); usado pela
        #: geracao de artefatos (fase 4), como na Auditoria de planilha.
        self.processed_dataframe: pd.DataFrame | None = None

    # --------------------------------------------------------
    # Planilha
    # --------------------------------------------------------

    def _read_planilha(self) -> pd.DataFrame:
        """Le a planilha como strings, normalizando vazios."""
        suffix = self.planilha_path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(self.planilha_path, dtype=str)
        else:  # .xlsx / .xls
            df = pd.read_excel(self.planilha_path, dtype=str)
        return df.fillna("")

    # --------------------------------------------------------
    # HTTP
    # --------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """Monta os headers (auth opcional)."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def _post(self, payload: dict[str, Any], idem_key: str) -> httpx.Response:
        """
        POST de um registro (sem retry). Levanta em status >= 400.

        Envia o header ``Idempotency-Key`` em TODA tentativa — inclusive
        nas retentativas do mesmo registro (mesma chave), para que
        sistemas compativeis nao dupliquem o cadastro.
        """
        headers = self._headers()
        headers["Idempotency-Key"] = idem_key
        response = httpx.post(
            self.url,
            json=payload,
            headers=headers,
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        return response

    def _retryer(self) -> Retrying:
        """Retryer de erros temporarios (Retry-After ou backoff+jitter)."""
        return Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=_smart_wait,
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )

    def _post_with_retry(self, payload: dict[str, Any]) -> httpx.Response:
        """POST com retry inteligente em erros temporarios."""
        result: httpx.Response = self._retryer()(self._post, payload, idempotency_key(payload))
        return result

    def _extrair_erro(self, response: httpx.Response) -> str:
        """Extrai uma mensagem legivel do corpo de erro da API."""
        try:
            body = response.json()
        except ValueError:
            error_text: str = response.text
            return error_text[:_ERROR_TEXT_LIMIT]

        if isinstance(body, dict):
            msg = str(body.get("error", "")).strip()
            detalhes = body.get("detalhes")
            if isinstance(detalhes, list) and detalhes:
                juntos = ", ".join(str(d) for d in detalhes)
                return f"{msg}: {juntos}" if msg else juntos
            if msg:
                return msg

        fallback_text: str = response.text
        return fallback_text[:_ERROR_TEXT_LIMIT]

    @staticmethod
    def _attempts_of(retryer: Retrying) -> int:
        """Numero de tentativas feitas pelo retryer (1 = de primeira)."""
        value = retryer.statistics.get("attempt_number", 1)
        return int(value) if isinstance(value, (int, float)) else 1

    def _enviar_um(self, payload: dict[str, Any], *, linha: int) -> ItemEnvio:
        """
        Envia um registro e devolve o resultado ESTRUTURADO da linha.

        - 2xx: sucesso; captura o id criado pelo sistema (se o corpo trouxer).
        - 4xx: falha definitiva classificada (validacao/duplicado/rate_limit/
          outro) — nao foi retentado (dado ou configuracao e o problema).
        - 5xx apos retries: falha temporaria (pode reenviar).
        - Sem resposta (timeout/rede): falha de conexao (pode reenviar).
        """
        retryer = self._retryer()
        idem_key = idempotency_key(payload)
        try:
            response = retryer(self._post, payload, idem_key)
        except httpx.HTTPStatusError as exc:
            status = int(exc.response.status_code)
            categoria, pode_reenviar = classify_status(status)
            return ItemEnvio(
                linha=linha,
                status_http=status,
                categoria=categoria,
                sucesso=False,
                mensagem=f"HTTP {status}: {self._extrair_erro(exc.response)}",
                id_externo=None,
                idempotency_key=idem_key,
                tentativas=self._attempts_of(retryer),
                pode_reenviar=pode_reenviar,
            )
        except httpx.HTTPError as exc:
            return ItemEnvio(
                linha=linha,
                status_http=None,
                categoria="conexao",
                sucesso=False,
                mensagem=f"erro de conexao: {exc}",
                id_externo=None,
                idempotency_key=idem_key,
                tentativas=self._attempts_of(retryer),
                pode_reenviar=True,
            )

        try:
            body = response.json()
        except ValueError:
            body = None
        id_externo = extract_external_id(body)

        mensagem = "criado" if id_externo is None else f"criado (id {id_externo})"
        return ItemEnvio(
            linha=linha,
            status_http=int(response.status_code),
            categoria="sucesso",
            sucesso=True,
            mensagem=mensagem,
            id_externo=id_externo,
            idempotency_key=idem_key,
            tentativas=self._attempts_of(retryer),
            pode_reenviar=False,
        )

    # --------------------------------------------------------
    # Progresso
    # --------------------------------------------------------

    def _notify(self, posicao: int, total: int, item: ItemEnvio) -> None:
        """Chama o callback de progresso (se houver), sem propagar erro."""
        if self.on_progress is None:
            return
        info: ProgressInfo = {
            "linha": posicao,
            "total": total,
            "sucesso": item.sucesso,
            "mensagem": item.mensagem,
            "status_http": item.status_http,
            "categoria": item.categoria,
            "id_externo": item.id_externo,
            "tentativas": item.tentativas,
        }
        try:
            self.on_progress(info)
        except Exception:  # noqa: BLE001 - callback do usuario nao quebra a task
            logger.warning("Callback de progresso levantou excecao (ignorado)")

    # --------------------------------------------------------
    # Relatorio
    # --------------------------------------------------------

    def _salvar_relatorio(
        self,
        resultados: list[dict[str, Any]],
        path: Path,
    ) -> None:
        """Salva o relatorio por linha no formato indicado pela extensao."""
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(resultados)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df.to_csv(path, index=False)
        elif suffix in (".xlsx", ".xls"):
            df.to_excel(path, index=False)
        else:  # .json
            df.to_json(path, orient="records", indent=2, force_ascii=False)

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    @staticmethod
    def _registro_legado(payload: dict[str, Any], item: ItemEnvio) -> dict[str, Any]:
        """Linha do relatorio por item (payload + colunas de resultado)."""
        registro = dict(payload)
        registro["_resultado"] = "ok" if item.sucesso else "erro"
        registro["_mensagem"] = item.mensagem
        registro["_status_http"] = item.status_http
        registro["_categoria"] = item.categoria
        registro["_id_externo"] = item.id_externo
        registro["_idempotency_key"] = item.idempotency_key
        registro["_tentativas"] = item.tentativas
        registro["_pode_reenviar"] = item.pode_reenviar
        return registro

    def execute(self) -> TaskResult:  # noqa: PLR0912
        """Executa o envio."""
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

        total = len(df)
        rows = df.to_dict("records")

        # Guarda o DataFrame lido para a geracao de artefatos (fase 4),
        # mesma convencao do processed_dataframe da Auditoria.
        self.processed_dataframe = df

        auth_note = ""
        if self.api_key or self.bearer_token:
            auth_note = " (com auth)"
        logger.info(f"Enviando {total} registros para {self.url}{auth_note}")

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
                    "url": self.url,
                    "warning": "Planilha sem linhas",
                },
            )

        # Dry-run: nao envia
        if self.dry_run:
            logger.info(f"[dry-run] Enviaria {total} registros")
            return self._make_result(
                status=TaskStatus.SUCCESS,
                started_at=started_at,
                data={
                    "dry_run": True,
                    "would_send": total,
                    "url": self.url,
                    "planilha": str(self.planilha_path),
                },
            )

        # Envio real
        resultados: list[dict[str, Any]] = []
        items: list[ItemEnvio] = []
        enviados = 0
        falhas = 0

        for idx, row in enumerate(rows, start=1):
            # Colunas iniciadas por "_" sao metadado dos artefatos do
            # AutoTarefas (ex. _motivo do registros_falhos.csv) e NAO
            # fazem parte do registro: ignora-las torna o arquivo de
            # falhos reenviavel com a MESMA Idempotency-Key.
            payload = {str(k): v for k, v in row.items() if not str(k).startswith("_")}
            # linha FISICA na planilha (cabecalho = 1; 1a de dados = 2),
            # mesma convencao da Auditoria de planilha.
            item = self._enviar_um(payload, linha=idx + 1)
            items.append(item)
            resultados.append(self._registro_legado(payload, item))

            if item.sucesso:
                enviados += 1
            else:
                falhas += 1

            self._notify(idx, total, item)

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
                "reenviaveis": total_reenviaveis(items),
                "falhas_por_categoria": falhas_por_categoria(items),
                "items": [item.to_dict() for item in items],
                "url": self.url,
                "planilha": str(self.planilha_path),
                "report_path": report_saved,
            },
        )


__all__ = ["SendApiTask"]
