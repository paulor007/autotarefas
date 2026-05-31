"""
Task de RPA: cadastra registros web a partir de planilha.

Quinta subclasse real de BaseTask. Le uma planilha (CSV/Excel),
itera linha a linha, e usa BrowserSession para cadastrar cada
registro num sistema web.

Comportamento:

- Antes de iniciar: verifica que servidor esta online (health check)
- Tolerante a falhas individuais: uma linha ruim NAO interrompe as outras
- CPF invalido -> linha marcada como 'skipped'
- CPF duplicado no destino -> linha marcada como 'skipped'
- Erro inesperado (timeout, crash) -> linha marcada como 'error' +
  screenshot mascarada salva automaticamente
- dry_run NAO abre browser nem faz requests; apenas valida dados e
  simula

Esquema esperado da planilha:

- ``nome`` (obrigatorio)
- ``email`` (obrigatorio)
- ``cpf`` (obrigatorio, validado por algoritmo modulo 11)
- ``telefone`` (opcional)

Status agregado:

- Todas success -> SUCCESS
- Mix success + error -> PARTIAL
- Todas error/skip -> FAILURE
- Servidor offline -> SKIPPED

Uso:
    from pathlib import Path
    from autotarefas.tasks.rpa_cadastro import RPACadastroTask

    task = RPACadastroTask(
        planilha_path=Path("clientes.csv"),
        base_url="http://localhost:5555",
        headless=True,
    )
    result = task.run()

    print(f"Total: {result.data['total']}")
    print(f"Sucesso: {result.data['success_count']}")
    print(f"Skipped: {result.data['skipped_count']}")
    print(f"Erros: {result.data['error_count']}")
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, ClassVar, Literal  # noqa

import httpx
import pandas as pd

from autotarefas.core.base import BaseTask, TaskResult, TaskStatus
from autotarefas.core.browser import BrowserSession
from autotarefas.core.exceptions import ValidationError
from autotarefas.core.logger import logger
from autotarefas.tasks.validators_br import is_valid_cpf

# ============================================================
# Constantes
# ============================================================

#: Colunas obrigatorias na planilha.
_REQUIRED_COLUMNS: tuple[str, ...] = ("nome", "email", "cpf")

#: Colunas opcionais (ausencia nao gera erro).
_OPTIONAL_COLUMNS: tuple[str, ...] = ("telefone",)

#: Limite de operations rastreadas no result.data.
_MAX_OPERATIONS_TRACKED: int = 100

#: Timeout do health check (segundos).
_HEALTH_TIMEOUT_S: float = 5.0

#: Timeout para resposta apos submit (ms).
_WAIT_FOR_RESPONSE_MS: int = 5000

#: Tipo do status de uma operacao individual.
OperationStatus = Literal[
    "success",
    "skipped",
    "error",
    "would_create",
    "would_skip",
    "would_error",
]


# ============================================================
# RPACadastroTask
# ============================================================


class RPACadastroTask(BaseTask):
    """
    Cadastra registros web a partir de planilha CSV/Excel.

    Args:
        planilha_path: Path do CSV/XLSX com os cadastros.
        base_url: URL base do sistema alvo (ex: "http://localhost:5555").
        headless: Se True (default), browser sem janela.
        screenshot_on_error: Se True (default), salva screenshot
            mascarada quando uma linha falhar.
        dry_run: Se True, NAO abre browser nem faz requests.
            Apenas valida dados e simula.

    Raises:
        ValidationError: Se planilha nao existir ou base_url for vazio.
    """

    name = "rpa_cadastro"
    description = "Cadastra registros web a partir de planilha"

    _HEALTH_TIMEOUT_S: ClassVar[float] = _HEALTH_TIMEOUT_S

    def __init__(  # noqa: PLR0913
        self,
        planilha_path: Path,
        *,
        base_url: str,
        headless: bool = True,
        screenshot_on_error: bool = True,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
        dry_run: bool = False,
    ) -> None:
        super().__init__(dry_run=dry_run)

        if not planilha_path.exists():
            raise ValidationError(
                f"Planilha nao encontrada: {planilha_path}",
                field="planilha_path",
                value=str(planilha_path),
            )

        if not base_url or not base_url.strip():
            raise ValidationError(
                "base_url eh obrigatorio",
                field="base_url",
                value=str(base_url),
            )

        self.planilha_path = planilha_path
        self.base_url = base_url.rstrip("/")
        self.headless = headless
        self.screenshot_on_error = screenshot_on_error
        self.on_progress = on_progress

    # --------------------------------------------------------
    # execute
    # --------------------------------------------------------

    def execute(self) -> TaskResult:
        """Fluxo principal: health -> read -> validate -> loop -> report."""
        started_at = datetime.now(UTC)

        # 1. Health check
        if not self.dry_run and not self._check_health():
            return self._make_result(
                status=TaskStatus.SKIPPED,
                started_at=started_at,
                error_message=(
                    f"Servidor nao respondeu em {self.base_url}/health "
                    f"(timeout {self._HEALTH_TIMEOUT_S}s)"
                ),
                data={"base_url": self.base_url},
            )

        # 2. Le planilha
        try:
            df = self._read_planilha()
        except (OSError, ValueError, pd.errors.ParserError, ValidationError) as exc:
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=f"Erro lendo planilha: {exc}",
                data={"planilha_path": str(self.planilha_path)},
            )

        # 3. Valida schema
        try:
            self._validate_schema(df)
        except ValidationError as exc:
            return self._make_result(
                status=TaskStatus.FAILURE,
                started_at=started_at,
                error_message=str(exc),
                data={
                    "planilha_path": str(self.planilha_path),
                    "columns_found": list(df.columns),
                },
            )

        # 4. Processa
        operations = self._run_dry_run(df) if self.dry_run else self._run_real(df)

        # 5. Stats agregados
        stats = self._compute_stats(operations)
        truncated = len(operations) > _MAX_OPERATIONS_TRACKED
        operations_to_report = operations[:_MAX_OPERATIONS_TRACKED]

        # 6. Determina status final
        final_status = self._determine_status(stats)

        return self._make_result(
            status=final_status,
            started_at=started_at,
            rows_affected=stats["success_count"],
            rows_failed=stats["error_count"],
            data={
                "planilha_path": str(self.planilha_path),
                "base_url": self.base_url,
                "total": len(df),
                "success_count": stats["success_count"],
                "skipped_count": stats["skipped_count"],
                "error_count": stats["error_count"],
                "operations": operations_to_report,
                "operations_truncated": truncated,
            },
        )

    # --------------------------------------------------------
    # Health check
    # --------------------------------------------------------

    def _check_health(self) -> bool:
        """Verifica se o servidor esta online via GET /health."""
        url = f"{self.base_url}/health"
        try:
            response = httpx.get(url, timeout=self._HEALTH_TIMEOUT_S)
        except (httpx.HTTPError, httpx.ConnectError) as exc:
            logger.warning(
                "Health check falhou ({url}): {err}",
                url=url,
                err=str(exc),
            )
            return False
        status_code: int = response.status_code
        return status_code == 200  # noqa: PLR2004

    # --------------------------------------------------------
    # Leitura / validacao
    # --------------------------------------------------------

    def _read_planilha(self) -> pd.DataFrame:
        """
        Le planilha como DataFrame, com tudo como string (sem inferencia).

        Suporta .csv, .xlsx, .xls.

        Raises:
            ValidationError: Formato nao suportado.
        """
        suffix = self.planilha_path.suffix.lower()

        if suffix == ".csv":
            df = pd.read_csv(self.planilha_path, dtype=str)
        elif suffix in (".xlsx", ".xls"):
            df = pd.read_excel(self.planilha_path, dtype=str)
        else:
            raise ValidationError(
                f"Formato nao suportado: '{suffix}'. Use .csv, .xlsx ou .xls.",
                field="planilha_path",
                value=str(self.planilha_path),
            )

        # NaN -> string vazia (mais previsivel)
        return df.fillna("")

    def _validate_schema(self, df: pd.DataFrame) -> None:
        """Valida que colunas obrigatorias existem."""
        columns_present = set(df.columns)
        missing = [c for c in _REQUIRED_COLUMNS if c not in columns_present]

        if missing:
            raise ValidationError(
                f"Colunas obrigatorias faltando: {missing}. "
                f"Esperadas: {list(_REQUIRED_COLUMNS)}. "
                f"Encontradas: {list(df.columns)}.",
                field="schema",
                value=missing,
            )

    # --------------------------------------------------------
    # Execucao
    # --------------------------------------------------------

    def _run_dry_run(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """Simula execucao sem abrir browser nem fazer requests."""
        operations: list[dict[str, Any]] = []
        for idx, (_, row) in enumerate(df.iterrows()):
            op = self._dry_run_row(idx, row)
            operations.append(op)
        return operations

    def _run_real(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """Execucao real: abre BrowserSession e processa linha a linha."""
        operations: list[dict[str, Any]] = []
        with BrowserSession(headless=self.headless) as browser:
            for idx, (_, row) in enumerate(df.iterrows()):
                op = self._process_row(browser, idx, row)
                operations.append(op)
                self._log_progress(op)
        return operations

    def _log_progress(self, op: dict[str, Any]) -> None:
        """Log de progresso por linha."""
        status = op.get("status", "?")
        nome = op.get("nome", "?")
        row = op.get("row", "?")
        if status == "success":
            logger.info(
                "[OK] linha {row}: {nome} -> ID {rid}",
                row=row,
                nome=nome,
                rid=op.get("record_id", "?"),
            )
        elif status == "skipped":
            logger.info(
                "[SKIP] linha {row}: {nome} ({reason})",
                row=row,
                nome=nome,
                reason=op.get("error", ""),
            )
        else:
            logger.warning(
                "[ERR] linha {row}: {nome} ({err})",
                row=row,
                nome=nome,
                err=op.get("error", ""),
            )

        if self.on_progress is not None:
            try:
                self.on_progress(op)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Callback on_progress falhou: {err}",
                    err=str(exc),
                )

    # --------------------------------------------------------
    # Processamento de linha (real e dry-run)
    # --------------------------------------------------------

    def _extract_row_data(self, row: pd.Series) -> dict[str, str]:
        """Extrai e normaliza os campos de uma linha (strings strip)."""
        result: dict[str, str] = {
            "nome": str(row.get("nome", "")).strip(),
            "email": str(row.get("email", "")).strip(),
            "cpf": str(row.get("cpf", "")).strip(),
            "telefone": "",
        }
        if "telefone" in row.index:
            result["telefone"] = str(row.get("telefone", "")).strip()
        return result

    def _validate_row_data(self, data: dict[str, str]) -> str | None:
        """
        Valida dados da linha. Retorna mensagem de erro ou None se OK.
        """
        if not data["nome"]:
            return "Nome vazio"
        if not data["email"]:
            return "Email vazio"
        if not data["cpf"]:
            return "CPF vazio"
        if not is_valid_cpf(data["cpf"]):
            return "CPF invalido (modulo 11)"
        return None

    def _dry_run_row(self, idx: int, row: pd.Series) -> dict[str, Any]:
        """Simula processamento de uma linha. Nao abre browser."""
        data = self._extract_row_data(row)
        op: dict[str, Any] = {
            "row": idx + 2,  # +1 (1-indexed) +1 (header)
            "nome": data["nome"],
            "cpf": data["cpf"],
        }

        validation_error = self._validate_row_data(data)
        if validation_error is not None:
            op["status"] = "would_skip"
            op["error"] = validation_error
            return op

        op["status"] = "would_create"
        return op

    def _process_row(
        self,
        browser: BrowserSession,
        idx: int,
        row: pd.Series,
    ) -> dict[str, Any]:
        """Processa uma linha: navega, preenche, submete, captura resultado."""
        data = self._extract_row_data(row)
        op: dict[str, Any] = {
            "row": idx + 2,
            "nome": data["nome"],
            "cpf": data["cpf"],
        }

        # Valida antes de gastar I/O com browser
        validation_error = self._validate_row_data(data)
        if validation_error is not None:
            op["status"] = "skipped"
            op["error"] = validation_error
            return op

        # Tenta cadastrar
        try:
            return self._fill_and_submit(browser, op, data)
        except Exception as exc:  # noqa: BLE001
            op["status"] = "error"
            op["error"] = f"Excecao: {type(exc).__name__}: {exc}"[:200]

            if self.screenshot_on_error:
                self._try_screenshot_error(browser, op)

            return op

    def _fill_and_submit(
        self,
        browser: BrowserSession,
        op: dict[str, Any],
        data: dict[str, str],
    ) -> dict[str, Any]:
        """
        Navega, preenche formulario, submete, analisa resposta.

        Pode levantar exception (sera capturada por _process_row).
        """
        browser.go_to(f"{self.base_url}/cadastro")
        browser.fill("#nome", data["nome"])
        browser.fill("#email", data["email"])
        browser.fill("#cpf", data["cpf"])
        if data["telefone"]:
            browser.fill("#telefone", data["telefone"])

        browser.click("#btn-cadastrar")

        # Apos submit, podem ocorrer 2 cenarios:
        # a) Sucesso -> redirect pra /sucesso/<id>, com #record-id visivel
        # b) Erro de validacao -> volta pro form, com .errors visivel
        # Esperamos o que aparecer primeiro.
        try:
            browser.wait_for(
                "#record-id",
                timeout_ms=_WAIT_FOR_RESPONSE_MS,
            )
            # Sucesso!
            record_id = browser.text("#record-id")
            op["status"] = "success"
            op["record_id"] = record_id
            return op
        except Exception:  # noqa: BLE001
            # Nao apareceu #record-id; talvez tenha tido erro de validacao
            if browser.is_visible(".errors"):
                error_text = browser.text(".errors")
                error_text_clean = error_text.strip()[:200]

                # CPF duplicado eh skipped, nao erro
                if "ja cadastrado" in error_text_clean.lower():
                    op["status"] = "skipped"
                    op["error"] = error_text_clean
                else:
                    op["status"] = "error"
                    op["error"] = error_text_clean
                    if self.screenshot_on_error:
                        self._try_screenshot_error(browser, op)
                return op

            # Estado inesperado
            op["status"] = "error"
            op["error"] = "Resposta inesperada apos submit"
            if self.screenshot_on_error:
                self._try_screenshot_error(browser, op)
            return op

    def _try_screenshot_error(
        self,
        browser: BrowserSession,
        op: dict[str, Any],
    ) -> None:
        """Tenta tirar screenshot. Erro aqui nao impede o restante."""
        try:
            nome_safe = op.get("nome", "sem_nome")[:20].replace(" ", "_")
            screenshot_name = f"erro-linha-{op['row']}-{nome_safe}"
            path = browser.screenshot_safe(screenshot_name)
            op["screenshot"] = str(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Falha ao tirar screenshot de erro: {err}",
                err=str(exc),
            )

    # --------------------------------------------------------
    # Stats e status final
    # --------------------------------------------------------

    def _compute_stats(self, operations: list[dict[str, Any]]) -> dict[str, int]:
        """Conta operacoes por categoria."""
        success_count = 0
        skipped_count = 0
        error_count = 0

        for op in operations:
            status = op.get("status", "")
            if status in ("success", "would_create"):
                success_count += 1
            elif status in ("skipped", "would_skip"):
                skipped_count += 1
            elif status in ("error", "would_error"):
                error_count += 1

        return {
            "success_count": success_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
        }

    def _determine_status(self, stats: dict[str, int]) -> TaskStatus:
        """Determina TaskStatus agregado."""
        if stats["error_count"] == 0 and stats["success_count"] > 0:
            return TaskStatus.SUCCESS
        if stats["error_count"] == 0 and stats["success_count"] == 0:
            # Tudo skipped (ex: planilha so com CPFs invalidos)
            return TaskStatus.SUCCESS  # Nao eh erro de RPA
        if stats["success_count"] > 0 and stats["error_count"] > 0:
            return TaskStatus.PARTIAL
        # Tudo erro
        return TaskStatus.FAILURE


__all__ = [
    "OperationStatus",
    "RPACadastroTask",
]
