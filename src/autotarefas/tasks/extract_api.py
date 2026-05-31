"""
Task de extracao de dados via API REST paginada.

A ExtractApiTask consome uma API que retorna dados paginados no
formato:

    {
      "data": [ {...}, {...} ],
      "page": 1,
      "per_page": 10,
      "total": 47,
      "total_pages": 5,
      "has_next": true
    }

Recursos:
- Paginacao automatica (segue ``has_next`` ate o fim)
- Retry com backoff exponencial (tenacity) em erros TEMPORARIOS
  (timeout, conexao, HTTP 5xx). Erros 4xx propagam (nao adianta tentar).
- Rate limiting (delay configuravel entre paginas)
- Autenticacao opcional via header X-API-Key (nao vai pro log/audit)
- Output em CSV / XLSX / JSON (decidido pela extensao do arquivo)
- dry-run: busca apenas a primeira pagina (preview), nao salva

Sexta subclasse concreta de BaseTask.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

_DATA_KEY = "data"
_HAS_NEXT_KEY = "has_next"
_TOTAL_KEY = "total"
_TOTAL_PAGES_KEY = "total_pages"

_DEFAULT_PER_PAGE = 50
_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_MAX_RETRIES = 3

#: Limite duro de paginas (evita loop infinito se a API tiver bug
#: e retornar has_next=true para sempre).
_MAX_PAGES_SAFETY = 10_000

#: Formatos de saida suportados (pela extensao do arquivo).
_SUPPORTED_FORMATS = (".csv", ".xlsx", ".xls", ".json")

#: Status que o callback de progresso recebe.
ProgressInfo = dict[str, Any]


# ============================================================
# Predicado de retry
# ============================================================


def _is_retryable(exc: BaseException) -> bool:
    """
    Decide se uma excecao justifica nova tentativa.

    Retry em erros TEMPORARIOS:
    - httpx.TransportError: cobre timeout e erros de rede/conexao
    - httpx.HTTPStatusError com status >= 500: erro do servidor

    NAO faz retry em 4xx (erro do cliente: URL errada, auth invalida,
    etc.) - tentar de novo nao resolveria.
    """
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = int(exc.response.status_code)
        return status_code >= 500  # noqa: PLR2004
    return False


# ============================================================
# Task
# ============================================================


class ExtractApiTask(BaseTask):
    """Extrai dados de uma API REST paginada e salva em arquivo."""

    name = "extract_api"
    description = "Extrai dados de uma API REST paginada (CSV/XLSX/JSON)"

    def __init__(  # noqa: PLR0913
        self,
        url: str,
        *,
        output_path: Path,
        per_page: int = _DEFAULT_PER_PAGE,
        max_pages: int | None = None,
        delay_s: float = 0.0,
        api_key: str | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        on_progress: Callable[[ProgressInfo], None] | None = None,
        dry_run: bool = False,
    ) -> None:
        """
        Args:
            url: Endpoint da API paginada.
            output_path: Caminho do arquivo de saida (.csv/.xlsx/.json).
            per_page: Itens por pagina a pedir (default 50).
            max_pages: Limite de paginas a buscar (None = todas).
            delay_s: Pausa em segundos entre paginas (rate limit).
            api_key: Chave de API opcional (header X-API-Key).
            timeout_s: Timeout de cada request em segundos.
            max_retries: Tentativas por pagina em erro temporario.
            on_progress: Callback chamado a cada pagina extraida.
            dry_run: Se True, busca so a primeira pagina e nao salva.
        """
        super().__init__(dry_run=dry_run)

        # Validacoes (falham cedo)
        if not url or not url.strip():
            msg = "url nao pode ser vazio"
            raise ValidationError(msg)

        suffix = output_path.suffix.lower()
        if suffix not in _SUPPORTED_FORMATS:
            msg = (
                f"Formato de saida nao suportado: '{suffix}'. "
                f"Use um de: {', '.join(_SUPPORTED_FORMATS)}"
            )
            raise ValidationError(msg)

        if per_page < 1:
            msg = "per_page deve ser >= 1"
            raise ValidationError(msg)

        if max_pages is not None and max_pages < 1:
            msg = "max_pages deve ser >= 1 (ou None para todas)"
            raise ValidationError(msg)

        if delay_s < 0:
            msg = "delay_s nao pode ser negativo"
            raise ValidationError(msg)

        self.url = url.strip()
        self.output_path = output_path
        self.per_page = per_page
        self.max_pages = max_pages
        self.delay_s = delay_s
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.on_progress = on_progress

    # --------------------------------------------------------
    # HTTP
    # --------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """Monta os headers (inclui auth se houver api_key)."""
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _fetch_page(self, page: int) -> dict[str, Any]:
        """
        Busca UMA pagina (sem retry). Levanta httpx.HTTPStatusError
        em status >= 400 (via raise_for_status).
        """
        params = {"page": page, "per_page": self.per_page}
        response = httpx.get(
            self.url,
            params=params,
            headers=self._headers(),
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        return payload

    def _fetch_page_with_retry(self, page: int) -> dict[str, Any]:
        """Busca uma pagina com retry (backoff exponencial)."""
        retryer = Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )
        result: dict[str, Any] = retryer(self._fetch_page, page)
        return result

    # --------------------------------------------------------
    # Progresso
    # --------------------------------------------------------

    def _notify(
        self,
        page: int,
        total_pages: int | None,
        page_count: int,
        accumulated: int,
    ) -> None:
        """Chama o callback de progresso (se houver), sem propagar erro."""
        if self.on_progress is None:
            return
        info: ProgressInfo = {
            "page": page,
            "total_pages": total_pages,
            "records": page_count,
            "accumulated": accumulated,
        }
        try:
            self.on_progress(info)
        except Exception:  # noqa: BLE001 - callback do usuario nao quebra a task
            logger.warning("Callback de progresso levantou excecao (ignorado)")

    # --------------------------------------------------------
    # Extracao
    # --------------------------------------------------------

    def _extract_all_pages(self) -> list[dict[str, Any]]:
        """Percorre todas as paginas e acumula os registros."""
        all_records: list[dict[str, Any]] = []
        page = 1

        while True:
            payload = self._fetch_page_with_retry(page)
            page_data: list[dict[str, Any]] = payload.get(_DATA_KEY, [])
            all_records.extend(page_data)

            total_pages = payload.get(_TOTAL_PAGES_KEY)
            self._notify(page, total_pages, len(page_data), len(all_records))

            # Condicoes de parada
            if not payload.get(_HAS_NEXT_KEY, False):
                break
            if self.max_pages is not None and page >= self.max_pages:
                logger.info(f"Limite max_pages={self.max_pages} atingido")
                break
            if page >= _MAX_PAGES_SAFETY:
                logger.warning(
                    f"Limite de seguranca de {_MAX_PAGES_SAFETY} paginas atingido - interrompendo",
                )
                break

            page += 1

            # Rate limit entre paginas
            if self.delay_s > 0:
                time.sleep(self.delay_s)

        return all_records

    def _dry_run_preview(self) -> dict[str, Any]:
        """Busca so a primeira pagina, para preview (nao salva)."""
        payload = self._fetch_page_with_retry(1)
        page_data: list[dict[str, Any]] = payload.get(_DATA_KEY, [])
        total = payload.get(_TOTAL_KEY, len(page_data))
        total_pages = payload.get(_TOTAL_PAGES_KEY, 1)
        return {
            "would_extract": total,
            "total_pages": total_pages,
            "first_page_count": len(page_data),
        }

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    def _save(self, records: list[dict[str, Any]], path: Path) -> None:
        """Salva os registros no formato indicado pela extensao."""
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(records)
        suffix = path.suffix.lower()

        if suffix == ".csv":
            df.to_csv(path, index=False)
        elif suffix in (".xlsx", ".xls"):
            df.to_excel(path, index=False)
        elif suffix == ".json":
            df.to_json(
                path,
                orient="records",
                indent=2,
                force_ascii=False,
            )
        else:  # pragma: no cover - validado no __init__
            msg = f"Formato nao suportado: {suffix}"
            raise ValidationError(msg)

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    def execute(self) -> TaskResult:
        """Executa a extracao."""
        started_at = datetime.now(UTC)

        auth_note = " (com auth)" if self.api_key else ""
        logger.info(f"Extraindo de {self.url}{auth_note}")

        # --- Dry-run: preview da primeira pagina, sem salvar ---
        if self.dry_run:
            try:
                preview = self._dry_run_preview()
            except httpx.HTTPError as exc:
                logger.error(f"Falha no preview (dry-run): {exc}")
                return self._make_result(
                    status=TaskStatus.FAILURE,
                    started_at=started_at,
                    error_message=f"Erro ao acessar a API: {exc}",
                )

            logger.info(
                f"[dry-run] Extrairia ~{preview['would_extract']} registros "
                f"em {preview['total_pages']} paginas",
            )
            return self._make_result(
                status=TaskStatus.SUCCESS,
                started_at=started_at,
                data={
                    "dry_run": True,
                    "would_extract": preview["would_extract"],
                    "total_pages": preview["total_pages"],
                    "url": self.url,
                    "output_path": str(self.output_path),
                },
            )

        # --- Extracao real ---
        try:
            records = self._extract_all_pages()
        except httpx.HTTPError as exc:
            logger.error(f"Falha na extracao: {exc}")
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=f"Erro ao acessar a API: {exc}",
            )

        # 0 registros nao eh erro - a API so nao tinha dados
        if not records:
            logger.warning("Nenhum registro retornado pela API")
            return self._make_result(
                status=TaskStatus.SUCCESS,
                started_at=started_at,
                rows_affected=0,
                data={
                    "extracted": 0,
                    "url": self.url,
                    "output_path": str(self.output_path),
                    "saved": False,
                    "warning": "Nenhum registro retornado",
                },
            )

        # Salva
        try:
            self._save(records, self.output_path)
        except (OSError, ValueError) as exc:
            logger.error(f"Falha ao salvar: {exc}")
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=f"Erro ao salvar o arquivo: {exc}",
            )

        logger.info(
            f"Extraidos {len(records)} registros -> {self.output_path}",
        )
        return self._make_result(
            status=TaskStatus.SUCCESS,
            started_at=started_at,
            rows_affected=len(records),
            data={
                "extracted": len(records),
                "url": self.url,
                "output_path": str(self.output_path),
                "output_format": self.output_path.suffix.lower().lstrip("."),
                "saved": True,
            },
        )


__all__ = ["ExtractApiTask"]
