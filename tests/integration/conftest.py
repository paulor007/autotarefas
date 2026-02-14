"""
Fixtures específicas para testes de integração do AutoTarefas.

Este módulo estende as fixtures do conftest.py principal com fixtures
especializadas para testes de integração que envolvem múltiplos componentes.

Fixtures disponíveis:
    - integration_env: Ambiente completo de integração
    - full_config: Configuração completa com todos os módulos
    - populated_job_store: JobStore com jobs pré-configurados
    - populated_run_history: RunHistory com histórico de execuções
    - integration_notifier: Notifier configurado para testes
    - integration_scheduler: Scheduler com jobs e histórico
    - mock_smtp_server: Servidor SMTP mockado para testes de email
    - sample_backup_source: Diretório fonte para testes de backup
    - cli_integration_runner: CLI runner com ambiente completo

Markers aplicados automaticamente:
    - @pytest.mark.integration
    - @pytest.mark.slow
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

if TYPE_CHECKING:
    pass


# ============================================================================
# Marker automático para testes de integração
# ============================================================================


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Adiciona markers automaticamente para testes de integração."""
    _ = config

    for item in items:
        # Todos os testes neste diretório recebem marker 'integration'
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.slow)


# ============================================================================
# Fixtures de Ambiente de Integração
# ============================================================================


@pytest.fixture
def integration_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """
    Cria estrutura completa de diretórios para testes de integração.

    Estrutura criada:
        integration_test/
        ├── data/           # DATA_DIR
        ├── logs/           # LOG_PATH
        ├── backups/        # BACKUP_PATH
        ├── temp/           # TEMP_PATH
        ├── reports/        # REPORTS_PATH
        ├── source/         # Arquivos fonte para backup
        └── notifications/  # Logs de notificações

    Yields:
        Path: Diretório raiz da estrutura de integração
    """
    root = tmp_path / "integration_test"
    root.mkdir()

    # Criar subdiretórios
    (root / "data").mkdir()
    (root / "logs").mkdir()
    (root / "backups").mkdir()
    (root / "temp").mkdir()
    (root / "reports").mkdir()
    (root / "source").mkdir()
    (root / "notifications").mkdir()

    yield root


@pytest.fixture
def integration_env(
    integration_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[dict[str, Path], None, None]:
    """
    Configura ambiente completo para testes de integração.

    Define variáveis de ambiente apontando para diretórios temporários
    e retorna dicionário com os caminhos.

    Yields:
        dict: Mapeamento de nome → Path dos diretórios
    """
    import importlib

    paths = {
        "root": integration_dir,
        "data": integration_dir / "data",
        "logs": integration_dir / "logs",
        "backups": integration_dir / "backups",
        "temp": integration_dir / "temp",
        "reports": integration_dir / "reports",
        "source": integration_dir / "source",
        "notifications": integration_dir / "notifications",
    }

    # Limpar variáveis existentes
    for key in list(os.environ.keys()):
        if key.startswith(("AUTOTAREFAS_", "EMAIL_", "LOG_")):
            monkeypatch.delenv(key, raising=False)

    # Configurar ambiente
    monkeypatch.setenv("AUTOTAREFAS_ENV", "testing")
    monkeypatch.setenv("AUTOTAREFAS_DEBUG", "true")
    monkeypatch.setenv("DATA_DIR", str(paths["data"]))
    monkeypatch.setenv("LOG_PATH", str(paths["logs"]))
    monkeypatch.setenv("BACKUP_PATH", str(paths["backups"]))
    monkeypatch.setenv("TEMP_PATH", str(paths["temp"]))
    monkeypatch.setenv("REPORTS_PATH", str(paths["reports"]))

    # Recarregar config
    import autotarefas.config as config

    importlib.reload(config)

    yield paths

    # Cleanup: recarregar config novamente
    importlib.reload(config)


# ============================================================================
# Fixtures de Storage Populado
# ============================================================================


@pytest.fixture
def populated_job_store(integration_env: dict[str, Path]) -> Generator[Any, None, None]:
    """
    Cria JobStore com jobs pré-configurados.

    Jobs criados:
        - backup_diario: Backup às 2h
        - limpeza_temp: Limpeza às 3h
        - relatorio_semanal: Relatório segundas às 8h
        - monitor_continuo: Monitor a cada 5 min (desabilitado)

    Yields:
        JobStore: Store populado com jobs de teste
    """
    from autotarefas.core.storage.job_store import JobStore

    store_path = integration_env["data"] / "jobs.json"
    store = JobStore(store_path)

    # Job 1: Backup diário
    job1 = store.create(
        name="backup_diario",
        task="backup",
        schedule="0 2 * * *",
        params={"source": str(integration_env["source"]), "compress": True},
        description="Backup diário dos documentos",
        tags=["backup", "diario"],
    )
    store.save(job1)

    # Job 2: Limpeza de temporários
    job2 = store.create(
        name="limpeza_temp",
        task="cleaner",
        schedule="0 3 * * *",
        params={"path": str(integration_env["temp"]), "days": 7},
        description="Limpa arquivos temporários antigos",
        tags=["limpeza", "diario"],
    )
    store.save(job2)

    # Job 3: Relatório semanal
    job3 = store.create(
        name="relatorio_semanal",
        task="reporter",
        schedule="0 8 * * 1",
        params={"format": "html", "send_email": True},
        description="Relatório semanal de atividades",
        tags=["relatorio", "semanal"],
    )
    store.save(job3)

    # Job 4: Monitor contínuo (desabilitado)
    job4 = store.create(
        name="monitor_continuo",
        task="monitor",
        schedule="*/5 * * * *",
        params={"threshold": 80},
        description="Monitoramento contínuo do sistema",
        tags=["monitor"],
        enabled=False,
    )
    store.save(job4)

    yield store


@pytest.fixture
def populated_run_history(
    integration_env: dict[str, Path],
    populated_job_store: Any,
) -> Generator[Any, None, None]:
    """
    Cria RunHistory com histórico de execuções.

    Histórico criado:
        - backup_diario: 10 execuções (8 success, 2 failed)
        - limpeza_temp: 5 execuções (5 success)
        - relatorio_semanal: 4 execuções (3 success, 1 failed)

    Yields:
        RunHistory: Histórico populado com execuções de teste
    """
    from autotarefas.core.storage.run_history import RunHistory, RunStatus

    db_path = integration_env["data"] / "run_history.db"
    history = RunHistory(db_path)

    jobs = populated_job_store.list_all()
    job_map = {j.name: j for j in jobs}

    # Histórico do backup_diario (10 runs: 8 success, 2 failed)
    job = job_map["backup_diario"]
    for i in range(10):
        record = history.start_run(
            job_id=job.id,
            job_name=job.name,
            task=job.task,
            params=job.params,
        )
        if i in (3, 7):  # 2 falhas
            history.finish_run(
                record.id,
                RunStatus.FAILED,
                duration=5.0,
                error="Disk full",
            )
        else:
            history.finish_run(
                record.id,
                RunStatus.SUCCESS,
                duration=30.0 + i * 2,
                output=f"Backed up {100 + i * 10} files",
            )

    # Histórico da limpeza_temp (5 runs: 5 success)
    job = job_map["limpeza_temp"]
    for i in range(5):
        record = history.start_run(
            job_id=job.id,
            job_name=job.name,
            task=job.task,
        )
        history.finish_run(
            record.id,
            RunStatus.SUCCESS,
            duration=10.0 + i,
            output=f"Cleaned {50 + i * 5} files",
        )

    # Histórico do relatorio_semanal (4 runs: 3 success, 1 failed)
    job = job_map["relatorio_semanal"]
    for i in range(4):
        record = history.start_run(
            job_id=job.id,
            job_name=job.name,
            task=job.task,
        )
        if i == 2:  # 1 falha
            history.finish_run(
                record.id,
                RunStatus.FAILED,
                duration=15.0,
                error="Email server unavailable",
            )
        else:
            history.finish_run(
                record.id,
                RunStatus.SUCCESS,
                duration=60.0 + i * 5,
                output="Report generated and sent",
            )

    yield history


# ============================================================================
# Fixtures de Notificação
# ============================================================================


@pytest.fixture
def integration_notifier(
    integration_env: dict[str, Path],
) -> Generator[Any, None, None]:
    """
    Cria Notifier configurado para testes de integração.

    Canais configurados:
        - CONSOLE: Habilitado, min_level=DEBUG
        - FILE: Habilitado, arquivo em notifications/
        - CALLBACK: Habilitado, para captura de notificações

    Yields:
        Notifier: Notifier configurado com canais de teste
    """
    from autotarefas.core.notifier import (
        NotificationChannel,
        NotificationLevel,
        Notifier,
        reset_notifier,
    )

    reset_notifier()

    notifier = Notifier()

    # Console
    notifier.add_channel(
        NotificationChannel.CONSOLE,
        min_level=NotificationLevel.DEBUG,
    )

    # Arquivo
    log_path = integration_env["notifications"] / "notifications.log"
    notifier.add_channel(
        NotificationChannel.FILE,
        min_level=NotificationLevel.INFO,
        path=str(log_path),
    )

    # Callback para captura
    captured: list[Any] = []
    notifier.add_channel(NotificationChannel.CALLBACK)
    notifier.add_callback("test_capture", lambda n: captured.append(n))

    # Anexar lista de captura ao notifier para acesso nos testes
    notifier._test_captured = captured  # type: ignore

    yield notifier

    reset_notifier()


# ============================================================================
# Fixtures de Arquivos de Teste
# ============================================================================


@pytest.fixture
def sample_backup_source(integration_env: dict[str, Path]) -> Path:
    """
    Cria estrutura de arquivos para testes de backup.

    Estrutura:
        source/
        ├── documents/
        │   ├── report.txt
        │   ├── data.csv
        │   └── notes.md
        ├── images/
        │   ├── photo1.jpg (fake)
        │   └── photo2.png (fake)
        └── config.json

    Returns:
        Path: Diretório source populado
    """
    source = integration_env["source"]

    # Documentos
    docs = source / "documents"
    docs.mkdir()
    (docs / "report.txt").write_text("Annual Report 2024\n" * 100)
    (docs / "data.csv").write_text(
        "id,name,value\n" + "\n".join(f"{i},item{i},{i * 10}" for i in range(100))
    )
    (docs / "notes.md").write_text("# Notes\n\n- Item 1\n- Item 2\n- Item 3\n")

    # Imagens (fake)
    images = source / "images"
    images.mkdir()
    (images / "photo1.jpg").write_bytes(b"\xff\xd8\xff" + b"x" * 1000)
    (images / "photo2.png").write_bytes(b"\x89PNG" + b"x" * 1000)

    # Config
    (source / "config.json").write_text(json.dumps({"version": "1.0", "enabled": True}))

    return source


@pytest.fixture
def sample_temp_files(integration_env: dict[str, Path]) -> Path:
    """
    Cria arquivos temporários com diferentes idades para teste de limpeza.

    Arquivos criados:
        - recent_*.txt: Arquivos recentes (hoje)
        - old_*.txt: Arquivos antigos (30+ dias)
        - very_old_*.txt: Arquivos muito antigos (90+ dias)

    Returns:
        Path: Diretório temp populado
    """
    import time

    temp = integration_env["temp"]
    now = time.time()

    # Arquivos recentes
    for i in range(3):
        f = temp / f"recent_{i}.txt"
        f.write_text(f"Recent file {i}")

    # Arquivos antigos (30 dias)
    for i in range(3):
        f = temp / f"old_{i}.txt"
        f.write_text(f"Old file {i}")
        old_time = now - (35 * 24 * 60 * 60)  # 35 dias atrás
        os.utime(f, (old_time, old_time))

    # Arquivos muito antigos (90 dias)
    for i in range(2):
        f = temp / f"very_old_{i}.txt"
        f.write_text(f"Very old file {i}")
        very_old_time = now - (95 * 24 * 60 * 60)  # 95 dias atrás
        os.utime(f, (very_old_time, very_old_time))

    return temp


# ============================================================================
# Fixtures de CLI
# ============================================================================


@pytest.fixture
def cli_integration_runner(
    integration_env: dict[str, Path],
) -> Generator[CliRunner, None, None]:
    """
    CLI Runner configurado para testes de integração.

    O runner é configurado com:
        - Ambiente isolado
        - Diretórios de integração disponíveis

    Yields:
        CliRunner: Runner configurado para integração
    """
    runner = CliRunner()
    yield runner


# ============================================================================
# Fixtures de Mock SMTP
# ============================================================================


@pytest.fixture
def mock_smtp_server() -> Generator[MagicMock, None, None]:
    """
    Mock de servidor SMTP para testes de email.

    Captura todas as mensagens enviadas em uma lista acessível.

    Yields:
        MagicMock: Mock do SMTP com lista de mensagens capturadas
    """
    sent_messages: list[dict[str, Any]] = []

    def capture_send(
        from_addr: str, to_addrs: list[str], msg: str
    ) -> dict[str, tuple[int, bytes]]:
        sent_messages.append(
            {
                "from": from_addr,
                "to": to_addrs,
                "message": msg,
            }
        )
        return {}

    mock_smtp = MagicMock()
    mock_smtp.sendmail.side_effect = capture_send
    mock_smtp.noop.return_value = (250, b"OK")
    mock_smtp._sent_messages = sent_messages

    with patch("smtplib.SMTP") as smtp_class:
        smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        smtp_class.return_value.__exit__ = MagicMock(return_value=False)
        smtp_class.return_value = mock_smtp
        yield mock_smtp


# ============================================================================
# Fixtures de Contexto Completo
# ============================================================================


@pytest.fixture
def full_integration_context(
    integration_env: dict[str, Path],
    populated_job_store: Any,
    populated_run_history: Any,
    integration_notifier: Any,
    sample_backup_source: Path,
) -> Generator[dict[str, Any], None, None]:
    """
    Contexto completo para testes de integração end-to-end.

    Inclui:
        - Ambiente configurado
        - JobStore populado
        - RunHistory com histórico
        - Notifier configurado
        - Arquivos de teste

    Yields:
        dict: Contexto completo com todos os componentes
    """
    yield {
        "env": integration_env,
        "job_store": populated_job_store,
        "run_history": populated_run_history,
        "notifier": integration_notifier,
        "source": sample_backup_source,
    }


# ============================================================================
# Helpers
# ============================================================================


def assert_file_contains(filepath: Path, content: str) -> None:
    """Verifica se arquivo contém texto."""
    assert filepath.exists(), f"Arquivo não existe: {filepath}"
    text = filepath.read_text()
    assert content in text, f"Conteúdo '{content}' não encontrado em {filepath}"


def assert_job_executed(run_history: Any, job_id: str, expected_status: str) -> None:
    """Verifica se job foi executado com status esperado."""
    from autotarefas.core.storage.run_history import RunStatus

    runs = run_history.get_by_job(job_id, limit=1)
    assert len(runs) > 0, f"Nenhuma execução encontrada para job {job_id}"
    assert runs[0].status == RunStatus(expected_status)


def wait_for_file(filepath: Path, timeout: float = 5.0) -> bool:
    """Aguarda arquivo existir (para testes assíncronos)."""
    import time

    start = time.time()
    while time.time() - start < timeout:
        if filepath.exists():
            return True
        time.sleep(0.1)
    return False


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Ambiente
    "integration_dir",
    "integration_env",
    # Storage
    "populated_job_store",
    "populated_run_history",
    # Notificação
    "integration_notifier",
    # Arquivos
    "sample_backup_source",
    "sample_temp_files",
    # CLI
    "cli_integration_runner",
    # Mock
    "mock_smtp_server",
    # Contexto completo
    "full_integration_context",
    # Helpers
    "assert_file_contains",
    "assert_job_executed",
    "wait_for_file",
]
