"""
Task de extracao via web scraping (paginas HTML).

A ExtractWebTask busca o HTML de uma pagina, extrai linhas por seletores
CSS (via BeautifulSoup), segue a paginacao automaticamente e salva os
dados em CSV/XLSX/JSON.

E a irma da ExtractApiTask: mesma forma (paginacao, retry resiliente,
multi-formato, dry-run), mas para sites que NAO expoem API — so HTML.

Decima task real (decima subclasse concreta de BaseTask).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import httpx
import pandas as pd
from bs4 import BeautifulSoup
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

#: Limite duro de paginas (evita loop infinito se a paginacao tiver bug).
_MAX_PAGES_SAFETY = 10_000

#: Formatos de saida suportados (pela extensao do arquivo).
_SUPPORTED_FORMATS = (".csv", ".xlsx", ".xls", ".json")

#: User-Agent honesto: o scraper se identifica.
_USER_AGENT = "AutoTarefas/1.1 (+https://github.com/paulor007/autotarefas)"

#: Status que o callback de progresso recebe.
ProgressInfo = dict[str, Any]


# ============================================================
# Predicado de retry (igual a ExtractApiTask)
# ============================================================


def _is_retryable(exc: BaseException) -> bool:
    """Retry em erros temporarios (transporte/timeout e HTTP 5xx)."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return int(exc.response.status_code) >= 500  # noqa: PLR2004
    return False


# ============================================================
# Task
# ============================================================


class ExtractWebTask(BaseTask):
    """Extrai dados de paginas HTML por seletores CSS e salva em arquivo."""

    name = "extract_web"
    description = "Extrai dados de paginas HTML por seletores CSS (CSV/XLSX/JSON)"

    def __init__(  # noqa: PLR0913 - task de config com parametros keyword-only
        self,
        url: str,
        *,
        output_path: Path,
        row_selector: str,
        fields: dict[str, str],
        next_selector: str | None = None,
        max_pages: int | None = None,
        delay_s: float = 0.0,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        on_progress: Callable[[ProgressInfo], None] | None = None,
        dry_run: bool = False,
    ) -> None:
        """
        Args:
            url: URL inicial da pagina a raspar.
            output_path: Arquivo de saida (.csv/.xlsx/.json).
            row_selector: Seletor CSS de cada linha/item (ex: "tr.produto").
            fields: Mapa {coluna: seletor_relativo}, ex:
                {"nome": "td.nome", "preco": "td.preco"}.
            next_selector: Seletor CSS do link "proxima pagina" (ex:
                "a.next"); None desliga a paginacao (so a 1a pagina).
            max_pages: Limite de paginas a seguir (None = todas).
            delay_s: Pausa em segundos entre paginas (rate limit / educacao).
            timeout_s: Timeout de cada request.
            max_retries: Tentativas por pagina em erro temporario.
            on_progress: Callback chamado a cada pagina raspada.
            dry_run: Se True, raspa so a 1a pagina e nao salva.
        """
        super().__init__(dry_run=dry_run)

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

        if not row_selector or not row_selector.strip():
            msg = "row_selector nao pode ser vazio"
            raise ValidationError(msg)

        if not fields:
            msg = "fields nao pode ser vazio (informe ao menos uma coluna)"
            raise ValidationError(msg)

        if max_pages is not None and max_pages < 1:
            msg = "max_pages deve ser >= 1 (ou None para todas)"
            raise ValidationError(msg)

        if delay_s < 0:
            msg = "delay_s nao pode ser negativo"
            raise ValidationError(msg)

        self.url = url.strip()
        self.output_path = output_path
        self.row_selector = row_selector.strip()
        self.fields = dict(fields)
        self.next_selector = next_selector.strip() if next_selector else None
        self.max_pages = max_pages
        self.delay_s = delay_s
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.on_progress = on_progress

    # --------------------------------------------------------
    # Busca (HTTP) com retry
    # --------------------------------------------------------

    def _fetch_html(self, url: str) -> str:
        """Busca o HTML de uma URL (levanta em status >= 400)."""
        with httpx.Client(timeout=self.timeout_s, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
            html: str = resp.text
            return html

    def _fetch_html_with_retry(self, url: str) -> str:
        """Busca o HTML com retry (backoff exponencial)."""
        retryer = Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )
        result: str = retryer(self._fetch_html, url)
        return result

    # --------------------------------------------------------
    # Parsing (BeautifulSoup)
    # --------------------------------------------------------

    def _process_page(
        self,
        html: str,
        base_url: str,
    ) -> tuple[list[dict[str, str]], str | None]:
        """Extrai as linhas da pagina e descobre a URL da proxima (se houver)."""
        soup = BeautifulSoup(html, "html.parser")

        rows: list[dict[str, str]] = []
        for el in soup.select(self.row_selector):
            registro: dict[str, str] = {}
            for coluna, seletor in self.fields.items():
                found = el.select_one(seletor)
                registro[coluna] = found.get_text(strip=True) if found is not None else ""
            rows.append(registro)

        next_url: str | None = None
        if self.next_selector:
            link = soup.select_one(self.next_selector)
            if link is not None:
                href = link.get("href")
                if isinstance(href, str) and href:
                    next_url = urljoin(base_url, href)

        return rows, next_url

    # --------------------------------------------------------
    # Progresso
    # --------------------------------------------------------

    def _notify(self, page: int, page_count: int, total: int) -> None:
        """Chama o callback de progresso; nunca quebra a task."""
        if self.on_progress is None:
            return
        try:
            self.on_progress(
                {"page": page, "page_count": page_count, "total": total},
            )
        except Exception:  # noqa: BLE001 - callback do usuario nao pode quebrar a task
            logger.warning("Callback de progresso levantou excecao; ignorando")

    # --------------------------------------------------------
    # Paginacao
    # --------------------------------------------------------

    def _scrape_all_pages(self) -> list[dict[str, str]]:
        """Raspa a 1a pagina e segue o link de proxima ate o fim."""
        todos: list[dict[str, str]] = []
        url: str | None = self.url
        page = 0
        limite = self.max_pages if self.max_pages is not None else _MAX_PAGES_SAFETY
        visitadas: set[str] = set()

        while url is not None and page < limite:
            page += 1
            visitadas.add(url)
            html = self._fetch_html_with_retry(url)
            rows, next_url = self._process_page(html, url)
            todos.extend(rows)
            self._notify(page, len(rows), len(todos))

            # Para se nao ha proxima, ou se ela repete uma ja visitada (loop)
            if next_url is None or next_url in visitadas:
                break
            url = next_url
            if self.delay_s > 0 and page < limite:
                time.sleep(self.delay_s)

        return todos

    def _dry_run_preview(self) -> dict[str, Any]:
        """Raspa so a 1a pagina (sem salvar) para um preview."""
        html = self._fetch_html_with_retry(self.url)
        rows, next_url = self._process_page(html, self.url)
        return {"would_extract_first_page": len(rows), "has_next": next_url is not None}

    # --------------------------------------------------------
    # Salvamento
    # --------------------------------------------------------

    def _save(self, records: list[dict[str, str]], path: Path) -> None:
        """Salva os registros no formato indicado pela extensao."""
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(records)
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

    def execute(self) -> TaskResult:
        """Executa o scraping."""
        started_at = datetime.now(UTC)
        logger.info(f"Raspando {self.url}")

        # --- Dry-run: preview da 1a pagina, sem salvar ---
        if self.dry_run:
            try:
                preview = self._dry_run_preview()
            except httpx.HTTPError as exc:
                logger.error(f"Falha no preview (dry-run): {exc}")
                return self._make_result(
                    status=TaskStatus.FAILURE,
                    started_at=started_at,
                    error_message=f"Erro ao acessar a pagina: {exc}",
                )

            logger.info(
                f"[dry-run] Extrairia ~{preview['would_extract_first_page']} itens na 1a pagina",
            )
            return self._make_result(
                status=TaskStatus.SUCCESS,
                started_at=started_at,
                data={
                    "dry_run": True,
                    "would_extract_first_page": preview["would_extract_first_page"],
                    "has_next": preview["has_next"],
                    "url": self.url,
                    "output_path": str(self.output_path),
                },
            )

        # --- Scraping real ---
        try:
            records = self._scrape_all_pages()
        except httpx.HTTPError as exc:
            logger.error(f"Falha no scraping: {exc}")
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=f"Erro ao acessar a pagina: {exc}",
            )

        # 0 itens nao eh erro - a pagina so nao tinha o que casar
        if not records:
            logger.warning("Nenhum item casou o seletor de linhas")
            return self._make_result(
                status=TaskStatus.SUCCESS,
                started_at=started_at,
                rows_affected=0,
                data={
                    "extracted": 0,
                    "url": self.url,
                    "output_path": str(self.output_path),
                    "saved": False,
                    "warning": "Nenhum item casou row_selector",
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

        logger.info(f"Extraidos {len(records)} itens -> {self.output_path}")
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


__all__ = ["ExtractWebTask"]
