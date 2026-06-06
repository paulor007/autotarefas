"""
Testes da SyncApiTask.

ESTRATEGIA:
- A SyncApiTask compoe ExtractApiTask + SendApiTask. Aqui trocamos as
  DUAS por fakes (no modulo sync_api), retornando TaskResults
  configuraveis. Assim testamos a ORQUESTRACAO (sem rede): curto-circuito
  na extracao, agregacao do envio, dry-run, limpeza do temp e propagacao
  dos parametros.
- O FakeExtract cria o arquivo intermediario (como o extract real faria),
  para a Sync prosseguir ao envio.

Cobertura:
- Validacao do construtor
- Caminho feliz (extrai -> envia -> SUCCESS)
- Falha na extracao (curto-circuito, send nao chamado)
- Parcial / falha no envio
- Extracao vazia (nada a enviar)
- dry-run (extract com dry_run, send nao chamado)
- Propagacao de parametros para as sub-tasks
- Limpeza do diretorio temporario
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from autotarefas.core.base import TaskResult, TaskStatus
from autotarefas.core.exceptions import ValidationError
from autotarefas.tasks.sync_api import SyncApiTask

if TYPE_CHECKING:
    pass

sync_module = importlib.import_module("autotarefas.tasks.sync_api")

SOURCE = "http://origem.local/api/clientes"
DEST = "http://destino.local/api/clientes"


# ============================================================
# Helpers
# ============================================================


def make_result(
    status: TaskStatus,
    *,
    rows_affected: int = 0,
    rows_failed: int = 0,
    data: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> TaskResult:
    now = datetime.now(UTC)
    return TaskResult(
        task_name="sub",
        status=status,
        started_at=now,
        finished_at=now,
        duration_ms=10,
        rows_affected=rows_affected,
        rows_failed=rows_failed,
        data=data or {},
        error_message=error_message,
    )


# ============================================================
# Fixture: fakes para extract e send
# ============================================================


@pytest.fixture
def mock_subtasks(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """
    Troca ExtractApiTask e SendApiTask por fakes.

    Configure:
      state["extract_result"] / state["send_result"]
    Inspecione:
      state["extract_kwargs"] / state["send_kwargs"] / state["send_called"]
    """
    state: dict[str, Any] = {
        "extract_kwargs": None,
        "send_kwargs": None,
        "send_called": False,
        "extract_result": make_result(TaskStatus.SUCCESS, rows_affected=3),
        "send_result": make_result(
            TaskStatus.SUCCESS,
            rows_affected=3,
            data={"report_path": None},
        ),
    }

    class FakeExtract:
        def __init__(self, **kwargs: Any) -> None:
            state["extract_kwargs"] = kwargs

        def run(self) -> TaskResult:
            res: TaskResult = state["extract_result"]
            # Simula o extract real: cria o arquivo de saida quando ha dados
            output = state["extract_kwargs"].get("output_path")
            if output is not None and res.status != TaskStatus.FAILURE and res.rows_affected > 0:
                Path(output).write_text(
                    "nome,email\nAna,ana@x.com\n",
                    encoding="utf-8",
                )
            return res

    class FakeSend:
        def __init__(self, **kwargs: Any) -> None:
            state["send_kwargs"] = kwargs
            state["send_called"] = True

        def run(self) -> TaskResult:
            return state["send_result"]  # type: ignore[no-any-return]

    monkeypatch.setattr(sync_module, "ExtractApiTask", FakeExtract)
    monkeypatch.setattr(sync_module, "SendApiTask", FakeSend)
    return state


# ============================================================
# Construtor
# ============================================================


class TestConstrutor:
    def test_source_url_vazia(self) -> None:
        with pytest.raises(ValidationError):
            SyncApiTask(source_url="", dest_url=DEST)

    def test_dest_url_vazia(self) -> None:
        with pytest.raises(ValidationError):
            SyncApiTask(source_url=SOURCE, dest_url="")

    def test_formato_intermediario_invalido(self) -> None:
        with pytest.raises(ValidationError):
            SyncApiTask(source_url=SOURCE, dest_url=DEST, intermediate_format="json")

    def test_per_page_invalido(self) -> None:
        with pytest.raises(ValidationError):
            SyncApiTask(source_url=SOURCE, dest_url=DEST, per_page=0)

    def test_delay_negativo(self) -> None:
        with pytest.raises(ValidationError):
            SyncApiTask(source_url=SOURCE, dest_url=DEST, delay_s=-1.0)

    def test_report_extensao_invalida(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            SyncApiTask(
                source_url=SOURCE,
                dest_url=DEST,
                report_path=tmp_path / "r.txt",
            )


# ============================================================
# Caminho feliz
# ============================================================


class TestSucesso:
    def test_extrai_e_envia(self, mock_subtasks: dict[str, Any]) -> None:
        result = SyncApiTask(source_url=SOURCE, dest_url=DEST).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.rows_affected == 3
        assert result.data["extraidos"] == 3
        assert result.data["enviados"] == 3
        assert mock_subtasks["send_called"] is True

    def test_data_tem_urls(self, mock_subtasks: dict[str, Any]) -> None:
        result = SyncApiTask(source_url=SOURCE, dest_url=DEST).run()
        assert result.data["source_url"] == SOURCE
        assert result.data["dest_url"] == DEST


# ============================================================
# Falha na extracao (curto-circuito)
# ============================================================


class TestFalhaExtracao:
    def test_extract_falha_nao_envia(self, mock_subtasks: dict[str, Any]) -> None:
        mock_subtasks["extract_result"] = make_result(
            TaskStatus.FAILURE,
            error_message="origem fora do ar",
        )
        result = SyncApiTask(source_url=SOURCE, dest_url=DEST).run()
        assert result.status == TaskStatus.FAILURE
        assert result.data["stage"] == "extract"
        assert mock_subtasks["send_called"] is False


# ============================================================
# Parcial / falha no envio
# ============================================================


class TestEnvioParcialOuFalha:
    def test_envio_parcial(self, mock_subtasks: dict[str, Any]) -> None:
        mock_subtasks["send_result"] = make_result(
            TaskStatus.PARTIAL,
            rows_affected=2,
            rows_failed=1,
            data={"report_path": None},
        )
        result = SyncApiTask(source_url=SOURCE, dest_url=DEST).run()
        assert result.status == TaskStatus.PARTIAL
        assert result.rows_affected == 2
        assert result.rows_failed == 1

    def test_envio_falha_total(self, mock_subtasks: dict[str, Any]) -> None:
        mock_subtasks["send_result"] = make_result(
            TaskStatus.FAILURE,
            rows_failed=3,
            data={"report_path": None},
        )
        result = SyncApiTask(source_url=SOURCE, dest_url=DEST).run()
        assert result.status == TaskStatus.FAILURE


# ============================================================
# Extracao vazia
# ============================================================


class TestVazio:
    def test_zero_extraidos_nao_envia(self, mock_subtasks: dict[str, Any]) -> None:
        mock_subtasks["extract_result"] = make_result(
            TaskStatus.SUCCESS,
            rows_affected=0,
        )
        result = SyncApiTask(source_url=SOURCE, dest_url=DEST).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.data["extraidos"] == 0
        assert mock_subtasks["send_called"] is False


# ============================================================
# Dry-run
# ============================================================


class TestDryRun:
    def test_dry_run_nao_envia(self, mock_subtasks: dict[str, Any]) -> None:
        result = SyncApiTask(source_url=SOURCE, dest_url=DEST, dry_run=True).run()
        assert result.status == TaskStatus.SUCCESS
        assert result.data["dry_run"] is True
        assert mock_subtasks["send_called"] is False

    def test_extract_recebe_dry_run(self, mock_subtasks: dict[str, Any]) -> None:
        SyncApiTask(source_url=SOURCE, dest_url=DEST, dry_run=True).run()
        assert mock_subtasks["extract_kwargs"]["dry_run"] is True


# ============================================================
# Propagacao de parametros
# ============================================================


class TestParametros:
    def test_extract_recebe_origem(self, mock_subtasks: dict[str, Any]) -> None:
        SyncApiTask(
            source_url=SOURCE,
            dest_url=DEST,
            source_api_key="k-origem",  # pragma: allowlist secret
            per_page=25,
            max_pages=4,
        ).run()
        kw = mock_subtasks["extract_kwargs"]
        assert kw["url"] == SOURCE
        assert kw["api_key"] == "k-origem"  # pragma: allowlist secret
        assert kw["per_page"] == 25
        assert kw["max_pages"] == 4

    def test_send_recebe_destino(self, mock_subtasks: dict[str, Any]) -> None:
        SyncApiTask(
            source_url=SOURCE,
            dest_url=DEST,
            dest_api_key="k-dest",  # pragma: allowlist secret
            dest_bearer_token="t-dest",  # pragma: allowlist secret
        ).run()
        kw = mock_subtasks["send_kwargs"]
        assert kw["url"] == DEST
        assert kw["api_key"] == "k-dest"  # pragma: allowlist secret
        assert kw["bearer_token"] == "t-dest"  # pragma: allowlist secret


# ============================================================
# Limpeza do temporario
# ============================================================


class TestLimpezaTemp:
    def test_remove_tmp_dir(self, mock_subtasks: dict[str, Any]) -> None:
        SyncApiTask(source_url=SOURCE, dest_url=DEST).run()
        output = mock_subtasks["extract_kwargs"]["output_path"]
        # O diretorio temporario (pai do arquivo intermediario) foi removido
        assert not Path(output).parent.exists()

    def test_remove_tmp_dir_mesmo_em_falha(
        self,
        mock_subtasks: dict[str, Any],
    ) -> None:
        mock_subtasks["extract_result"] = make_result(TaskStatus.FAILURE)
        SyncApiTask(source_url=SOURCE, dest_url=DEST).run()
        output = mock_subtasks["extract_kwargs"]["output_path"]
        assert not Path(output).parent.exists()
