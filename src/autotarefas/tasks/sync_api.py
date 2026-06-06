"""
Task de sincronizacao entre duas APIs (origem -> destino).

A SyncApiTask combina as tasks ja existentes: extrai dados de uma API
origem (ExtractApiTask) e envia para uma API destino (SendApiTask),
usando um arquivo intermediario temporario que e descartado ao final.

E o "ciclo de dados" completo num passo so: ler de um sistema e gravar
em outro. Caso de uso tipico: migrar/replicar cadastros entre dois
sistemas que exponham APIs REST.

Arquitetura: esta task NAO reimplementa HTTP/paginacao/retry. Ela
**compoe** ExtractApiTask + SendApiTask (cada uma ja testada). Os dois
passos aparecem no audit (extract_api, send_api), alem do proprio
sync_api — rastreabilidade granular.

Nona subclasse concreta de BaseTask.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.core.logger import logger
from autotarefas.tasks.extract_api import ExtractApiTask
from autotarefas.tasks.send_api import SendApiTask

if TYPE_CHECKING:
    from collections.abc import Callable

# ============================================================
# Constantes
# ============================================================

_DEFAULT_PER_PAGE = 50
_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_MAX_RETRIES = 3
_INTERMEDIATE_FORMATS = ("csv", "xlsx")
_REPORT_FORMATS = (".csv", ".xlsx", ".xls", ".json")

ProgressInfo = dict[str, Any]


# ============================================================
# Task
# ============================================================


class SyncApiTask(BaseTask):
    """Sincroniza dados de uma API origem para uma API destino."""

    name = "sync_api"
    description = "Sincroniza dados de uma API origem para uma API destino"

    def __init__(  # noqa: PLR0913 - task de config com parametros keyword-only
        self,
        source_url: str,
        dest_url: str,
        *,
        source_api_key: str | None = None,
        dest_api_key: str | None = None,
        dest_bearer_token: str | None = None,
        per_page: int = _DEFAULT_PER_PAGE,
        max_pages: int | None = None,
        delay_s: float = 0.0,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        report_path: Path | None = None,
        intermediate_format: str = "csv",
        on_progress: Callable[[ProgressInfo], None] | None = None,
        dry_run: bool = False,
    ) -> None:
        """
        Args:
            source_url: Endpoint da API origem (paginada, para extrair).
            dest_url: Endpoint da API destino (recebe POST por registro).
            source_api_key: Chave da origem (header X-API-Key).
            dest_api_key: Chave do destino (header X-API-Key).
            dest_bearer_token: Token Bearer do destino.
            per_page: Itens por pagina na extracao.
            max_pages: Limite de paginas a extrair (None = todas).
            delay_s: Pausa entre paginas (extracao) e entre envios.
            timeout_s: Timeout de cada request.
            max_retries: Tentativas por pagina/linha em erro temporario.
            report_path: Relatorio por linha do envio (.csv/.xlsx/.json).
            intermediate_format: Formato do arquivo intermediario (csv/xlsx).
            on_progress: Callback chamado a cada registro enviado.
            dry_run: Se True, testa a extracao (pagina 1) e nao envia.
        """
        super().__init__(dry_run=dry_run)

        if not source_url or not source_url.strip():
            msg = "source_url nao pode ser vazio"
            raise ValidationError(msg)

        if not dest_url or not dest_url.strip():
            msg = "dest_url nao pode ser vazio"
            raise ValidationError(msg)

        fmt = intermediate_format.lower().lstrip(".")
        if fmt not in _INTERMEDIATE_FORMATS:
            msg = (
                f"intermediate_format invalido: '{intermediate_format}'. "
                f"Use: {', '.join(_INTERMEDIATE_FORMATS)}"
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

        if report_path is not None and report_path.suffix.lower() not in _REPORT_FORMATS:
            msg = (
                f"Formato de relatorio nao suportado: '{report_path.suffix}'. "
                f"Use: {', '.join(_REPORT_FORMATS)}"
            )
            raise ValidationError(msg)

        self.source_url = source_url.strip()
        self.dest_url = dest_url.strip()
        self.source_api_key = source_api_key
        self.dest_api_key = dest_api_key
        self.dest_bearer_token = dest_bearer_token
        self.per_page = per_page
        self.max_pages = max_pages
        self.delay_s = delay_s
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.report_path = report_path
        self.intermediate_format = fmt
        self.on_progress = on_progress

    # --------------------------------------------------------
    # Sub-tasks (composicao)
    # --------------------------------------------------------

    def _extrair(self, destino: Path) -> TaskResult:
        """Extrai da API origem para o arquivo intermediario."""
        return ExtractApiTask(
            url=self.source_url,
            output_path=destino,
            per_page=self.per_page,
            max_pages=self.max_pages,
            api_key=self.source_api_key,
            delay_s=self.delay_s,
            timeout_s=self.timeout_s,
            max_retries=self.max_retries,
            dry_run=self.dry_run,
        ).run()

    def _enviar(self, origem: Path) -> TaskResult:
        """Envia o arquivo intermediario para a API destino."""
        return SendApiTask(
            planilha_path=origem,
            url=self.dest_url,
            api_key=self.dest_api_key,
            bearer_token=self.dest_bearer_token,
            delay_s=self.delay_s,
            timeout_s=self.timeout_s,
            max_retries=self.max_retries,
            report_path=self.report_path,
            on_progress=self.on_progress,
            dry_run=False,
        ).run()

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    def execute(self) -> TaskResult:
        """Executa a sincronizacao (extrai da origem, envia ao destino)."""
        started_at = datetime.now(UTC)
        tmp_dir = Path(tempfile.mkdtemp(prefix="autotarefas-sync-"))
        temp_file = tmp_dir / f"sync_data.{self.intermediate_format}"

        try:
            # 1) Extracao
            logger.info(f"Sync: extraindo de {self.source_url}")
            extract_result = self._extrair(temp_file)

            if extract_result.status == TaskStatus.FAILURE:
                return self._make_result(
                    status=TaskStatus.FAILURE,
                    started_at=started_at,
                    error_message=(f"Extracao da origem falhou: {extract_result.error_message}"),
                    data={
                        "stage": "extract",
                        "source_url": self.source_url,
                        "dest_url": self.dest_url,
                    },
                )

            extraidos = extract_result.rows_affected

            # Dry-run: o extract so testou a pagina 1 e nao salvou
            if self.dry_run:
                logger.info("[dry-run] Extracao testada; envio nao executado")
                return self._make_result(
                    status=TaskStatus.SUCCESS,
                    started_at=started_at,
                    data={
                        "dry_run": True,
                        "source_url": self.source_url,
                        "dest_url": self.dest_url,
                        "nota": "extracao testada (pagina 1); envio nao executado",
                    },
                )

            # Nada extraido -> nada a enviar (sucesso vazio)
            if extraidos == 0 or not temp_file.exists():
                logger.warning("Sync: nenhum registro extraido da origem")
                return self._make_result(
                    status=TaskStatus.SUCCESS,
                    started_at=started_at,
                    rows_affected=0,
                    data={
                        "extraidos": 0,
                        "enviados": 0,
                        "falhas": 0,
                        "source_url": self.source_url,
                        "dest_url": self.dest_url,
                    },
                )

            # 2) Envio
            logger.info(f"Sync: enviando {extraidos} registros para {self.dest_url}")
            send_result = self._enviar(temp_file)

            enviados = send_result.rows_affected
            falhas = send_result.rows_failed

            logger.info(
                f"Sync concluido: {extraidos} extraidos, {enviados} enviados, {falhas} falhas",
            )
            return self._make_result(
                status=send_result.status,
                started_at=started_at,
                rows_affected=enviados,
                rows_failed=falhas,
                data={
                    "extraidos": extraidos,
                    "enviados": enviados,
                    "falhas": falhas,
                    "source_url": self.source_url,
                    "dest_url": self.dest_url,
                    "report_path": send_result.data.get("report_path"),
                },
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


__all__ = ["SyncApiTask"]
