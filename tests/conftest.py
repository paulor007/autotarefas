"""
Configuração global de testes do AutoTarefas.

Este módulo contém fixtures reutilizáveis em todos os testes:
    - Fixtures de ambiente (temp_dir, env_vars)
    - Fixtures de configuração (test_settings, mock_settings)
    - Fixtures de arquivos (sample_files, sample_tree)
    - Fixtures de email/notificações (mock_smtp, mock_notifier)
    - Fixtures de CLI (cli_runner, cli_context)
    - Fixtures de tasks (sample_task_config, mock_task_result)

Uso:
    def test_example(temp_dir, test_settings):
        # temp_dir é um diretório temporário limpo
        # test_settings é uma configuração isolada
        pass
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from rich.console import Console

if TYPE_CHECKING:
    from autotarefas.config import Settings


# ============================================================================
# Fixture global: CWD estável
# ============================================================================


@pytest.fixture(autouse=True)
def stable_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Garante que cada teste inicie em um diretório estável (raiz do projeto).

    Isso evita FileNotFoundError no teardown do monkeypatch no Windows quando
    algum teste/fixture muda o CWD para um diretório temporário que é removido
    antes do pytest restaurar o cwd original.
    """
    project_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(project_root)


@pytest.fixture(autouse=True)
def reset_loguru_handlers() -> Generator[None, None, None]:
    """
    Reseta handlers do loguru antes de cada teste.

    Isso evita o erro "I/O operation on closed file" que ocorre
    quando testes compartilham handlers de log que foram fechados.
    """
    try:
        from loguru import logger

        # Remove todos os handlers existentes
        logger.remove()

        # Adiciona handler que descarta mensagens (evita erros de I/O)
        handler_id = logger.add(
            lambda _msg: None,  # noqa: ARG005
            format="{message}",
            level="WARNING",  # Só loga warnings+ para não poluir
        )

        yield

        # Cleanup
        with contextlib.suppress(ValueError):
            logger.remove(handler_id)
    except ImportError:
        yield  # loguru não instalado


# ============================================================================
# Constantes de Teste
# ============================================================================

TEST_EMAIL = "test@autotarefas.local"
TEST_SMTP_HOST = "smtp.test.local"
TEST_SMTP_PORT = 587


# ============================================================================
# Fixtures de Ambiente
# ============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Cria um diretório temporário limpo para cada teste.

    O diretório é automaticamente removido após o teste.

    Yields:
        Path: Caminho do diretório temporário.
    """
    with tempfile.TemporaryDirectory(prefix="autotarefas_test_") as tmp:
        yield Path(tmp)


@pytest.fixture
def temp_file(temp_dir: Path) -> Generator[Path, None, None]:
    """
    Cria um arquivo temporário dentro do diretório temporário.

    Yields:
        Path: Caminho do arquivo temporário.
    """
    file_path = temp_dir / "temp_file.txt"
    file_path.write_text("temporary content", encoding="utf-8")
    yield file_path


@pytest.fixture
def env_vars() -> Generator[dict[str, str], None, None]:
    """
    Gerencia variáveis de ambiente para testes.

    Restaura as variáveis originais após o teste.

    Yields:
        dict: Dicionário para definir variáveis de ambiente.

    Exemplo:
        def test_with_env(env_vars):
            env_vars["MY_VAR"] = "value"
            os.environ.update(env_vars)
            # ... teste ...
    """
    original_env = os.environ.copy()
    test_env: dict[str, str] = {}

    yield test_env

    # Restaura ambiente original
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def isolated_env(env_vars: dict[str, str]) -> Generator[None, None, None]:
    """
    Isola completamente as variáveis de ambiente do AutoTarefas.

    Remove todas as variáveis AUTOTAREFAS_*, EMAIL_* e LOG_* antes do teste
    e faz reload do módulo config para garantir valores limpos.

    Observação:
        Esta fixture depende de env_vars para garantir restauração total do ambiente.
    """
    import importlib

    keys_to_remove = [
        k
        for k in os.environ
        if k.startswith(("AUTOTAREFAS_", "EMAIL_", "LOG_", "APP_"))
    ]
    for key in keys_to_remove:
        os.environ.pop(key, None)

    # Reload config para pegar o ambiente limpo
    import autotarefas.config as config

    importlib.reload(config)

    yield

    # Reload novamente após o teste para limpar estado
    importlib.reload(config)


# ============================================================================
# Fixtures de Configuração
# ============================================================================


@pytest.fixture
def test_settings(
    temp_dir: Path, isolated_env: None
) -> Generator[Settings, None, None]:
    """
    Fornece configurações isoladas para teste.

    Cria uma instância de Settings com valores de teste
    e diretórios temporários.

    Yields:
        Settings: Instância de configuração para teste.
    """
    data_dir = temp_dir / "data"
    log_dir = temp_dir / "logs"
    backup_dir = temp_dir / "backups"
    data_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    os.environ["AUTOTAREFAS_ENV"] = "testing"
    os.environ["AUTOTAREFAS_DEBUG"] = "true"
    os.environ["AUTOTAREFAS_DATA_DIR"] = str(data_dir)
    os.environ["AUTOTAREFAS_LOG_DIR"] = str(log_dir)
    os.environ["AUTOTAREFAS_BACKUP_DIR"] = str(backup_dir)

    from autotarefas.config import Settings

    yield Settings()


@pytest.fixture
def mock_settings() -> Generator[MagicMock, None, None]:
    """
    Fornece um mock completo das configurações.

    Útil quando você precisa controlar completamente
    os valores retornados.

    Yields:
        MagicMock: Mock das configurações.
    """
    mock = MagicMock()
    mock.env = "testing"
    mock.debug = True
    mock.data_dir = Path("/tmp/autotarefas/data")
    mock.log_dir = Path("/tmp/autotarefas/logs")
    mock.backup_dir = Path("/tmp/autotarefas/backups")

    # Garante que mock.email exista como objeto próprio
    mock.email = MagicMock()
    mock.email.enabled = False
    mock.email.host = TEST_SMTP_HOST
    mock.email.port = TEST_SMTP_PORT
    mock.email.from_addr = TEST_EMAIL

    # Atalhos (se existirem no seu Settings real)
    mock.smtp_host = TEST_SMTP_HOST
    mock.smtp_port = TEST_SMTP_PORT
    mock.smtp_from = TEST_EMAIL

    with patch("autotarefas.config.settings", mock):
        yield mock


# ============================================================================
# Fixtures de Arquivos
# ============================================================================


@pytest.fixture
def sample_files(temp_dir: Path) -> dict[str, Path]:
    """
    Cria arquivos de exemplo para testes.

    Returns:
        dict: Mapeamento de tipo para caminho do arquivo.
    """
    files: dict[str, Path] = {}

    txt_file = temp_dir / "document.txt"
    txt_file.write_text("Hello, AutoTarefas!", encoding="utf-8")
    files["txt"] = txt_file

    json_file = temp_dir / "data.json"
    json_file.write_text(json.dumps({"key": "value", "number": 42}), encoding="utf-8")
    files["json"] = json_file

    csv_file = temp_dir / "data.csv"
    csv_file.write_text("name,age,city\nAlice,30,SP\nBob,25,RJ\n", encoding="utf-8")
    files["csv"] = csv_file

    log_file = temp_dir / "app.log"
    log_file.write_text(
        "[INFO] Application started\n[ERROR] Something failed\n", encoding="utf-8"
    )
    files["log"] = log_file

    bin_file = temp_dir / "binary.dat"
    bin_file.write_bytes(b"\x00\x01\x02\x03" * 100)
    files["bin"] = bin_file

    return files


@pytest.fixture
def sample_tree(temp_dir: Path) -> Path:
    """
    Cria uma estrutura de diretórios de exemplo.

    Returns:
        Path: Raiz da estrutura criada.
    """
    docs_dir = temp_dir / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "report.txt").write_text("Monthly report content", encoding="utf-8")
    (docs_dir / "notes.md").write_text(
        "# Notes\n\n- Item 1\n- Item 2", encoding="utf-8"
    )

    img_dir = temp_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    (img_dir / "photo.jpg").write_bytes(b"FAKE_JPEG_DATA")
    (img_dir / "icon.png").write_bytes(b"FAKE_PNG_DATA")

    dl_dir = temp_dir / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)
    (dl_dir / "file1.zip").write_bytes(b"FAKE_ZIP_DATA")
    (dl_dir / "file2.pdf").write_bytes(b"FAKE_PDF_DATA")

    tmp_dir = temp_dir / "temp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    (tmp_dir / "cache.tmp").write_text("cache data", encoding="utf-8")

    old_file = tmp_dir / "old_file.txt"
    old_file.write_text("old content", encoding="utf-8")
    old_time = (datetime.now(UTC) - timedelta(days=30)).timestamp()
    os.utime(old_file, (old_time, old_time))

    return temp_dir


@pytest.fixture
def large_file(temp_dir: Path) -> Path:
    """
    Cria um arquivo grande (1MB) para testes de performance.

    Returns:
        Path: Caminho do arquivo grande.
    """
    file_path = temp_dir / "large_file.bin"
    file_path.write_bytes(os.urandom(1024 * 1024))
    return file_path


# ============================================================================
# Fixtures de Email/Notificações
# ============================================================================


def _setup_smtp_mock(mock_smtp_class: MagicMock, *, with_tls: bool) -> MagicMock:
    """
    Configura um mock de SMTP/SMTP_SSL com comportamento de context manager.

    Args:
        mock_smtp_class: objeto retornado pelo patch do smtplib.SMTP / SMTP_SSL.
        with_tls: se True, adiciona respostas esperadas para starttls/ehlo.

    Returns:
        MagicMock: instância configurada do servidor SMTP.
    """
    mock_instance = MagicMock()

    smtp_obj = mock_smtp_class.return_value
    smtp_obj.__enter__ = MagicMock(return_value=mock_instance)
    smtp_obj.__exit__ = MagicMock(return_value=False)

    mock_instance.sendmail.return_value = {}
    mock_instance.login.return_value = (235, b"Authentication successful")

    if with_tls:
        mock_instance.ehlo.return_value = (250, b"OK")
        mock_instance.starttls.return_value = (220, b"Ready")

    return mock_instance


@pytest.fixture
def mock_smtp() -> Generator[MagicMock, None, None]:
    """
    Mock do servidor SMTP (sem SSL).

    Yields:
        MagicMock: Mock configurado do SMTP.
    """
    with patch("smtplib.SMTP") as mock_smtp_class:
        yield _setup_smtp_mock(mock_smtp_class, with_tls=True)


@pytest.fixture
def mock_smtp_ssl() -> Generator[MagicMock, None, None]:
    """
    Mock do servidor SMTP com SSL.

    Yields:
        MagicMock: Mock configurado do SMTP_SSL.
    """
    with patch("smtplib.SMTP_SSL") as mock_smtp_class:
        yield _setup_smtp_mock(mock_smtp_class, with_tls=False)


@pytest.fixture
def mock_notifier() -> Generator[MagicMock, None, None]:
    """
    Mock do sistema de notificações.

    Yields:
        MagicMock: Mock do Notifier.
    """
    with patch("autotarefas.core.notifier.get_notifier") as mock_get:
        mock_instance = MagicMock()
        mock_get.return_value = mock_instance

        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.success = True  # Compatibilidade
        mock_result.error = None
        mock_instance.notify.return_value = [mock_result]

        yield mock_instance


@pytest.fixture
def mock_email_sender() -> Generator[MagicMock, None, None]:
    """
    Mock do EmailSender.

    Yields:
        MagicMock: Mock do EmailSender.
    """
    with patch("autotarefas.core.email.get_email_sender") as mock_get:
        mock_instance = MagicMock()
        mock_get.return_value = mock_instance

        mock_instance.is_configured = False

        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.success = True  # Compatibilidade
        mock_result.message_id = "<test-123@autotarefas.local>"
        mock_result.error = None
        mock_instance.send.return_value = mock_result
        mock_instance.send_simple.return_value = mock_result

        yield mock_instance


# ============================================================================
# Fixtures de CLI
# ============================================================================


@pytest.fixture
def cli_runner() -> CliRunner:
    """
    Fornece um CliRunner do Click para testes de CLI.

    Observação:
        No Click 8.3.0, `mix_stderr` não é parâmetro do CliRunner,
        e sim do `invoke(...)`.
    """
    return CliRunner()


@pytest.fixture
def cli_runner_isolated(cli_runner: CliRunner) -> CliRunner:
    """
    Mantém compatibilidade com testes existentes.

    Observação:
        Para isolamento REAL de filesystem, prefira `isolated_fs`.
    """
    return cli_runner


@pytest.fixture
def isolated_fs(
    cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    """
    Cria um filesystem isolado para testes de CLI e altera o CWD.

    Yields:
        Path: diretório raiz do filesystem isolado.
    """
    with cli_runner.isolated_filesystem() as d:
        monkeypatch.chdir(d)
        yield Path(d)


@pytest.fixture
def cli_context() -> dict[str, Any]:
    """
    Contexto padrão para testes de comandos CLI.

    Returns:
        dict: Contexto com console e flags.
    """
    return {
        "console": Console(force_terminal=True, width=120),
        "verbose": False,
        "quiet": False,
        "dry_run": False,
    }


# ============================================================================
# Fixtures de Tasks
# ============================================================================


@pytest.fixture
def sample_task_config() -> dict[str, Any]:
    """
    Configuração de exemplo para uma task.

    Returns:
        dict: Configuração de task.
    """
    return {
        "name": "test_task",
        "description": "Task de teste",
        "enabled": True,
        "timeout": 60,
        "retry_count": 3,
        "retry_delay": 5,
        "params": {
            "param1": "value1",
            "param2": 42,
        },
    }


@pytest.fixture
def mock_task_result() -> MagicMock:
    """
    Mock de resultado de task.

    Returns:
        MagicMock: Resultado mockado.
    """
    now = datetime.now(UTC)

    result = MagicMock()
    result.is_success = True
    result.success = True  # Compatibilidade
    result.message = "Task completed successfully"
    result.data = {"processed": 10, "errors": 0}
    result.duration = 1.5
    result.started_at = now
    result.finished_at = now
    return result


# ============================================================================
# Fixtures de Scheduler
# ============================================================================


@pytest.fixture
def mock_scheduler() -> Generator[MagicMock, None, None]:
    """
    Mock do TaskScheduler.

    Yields:
        MagicMock: Mock do scheduler.
    """
    with patch("autotarefas.core.scheduler.get_scheduler") as mock_get:
        mock_instance = MagicMock()
        mock_get.return_value = mock_instance

        mock_instance.jobs = {}
        mock_instance.is_running = False

        yield mock_instance


@pytest.fixture
def mock_job_store(temp_dir: Path) -> Generator[MagicMock, None, None]:
    """
    Mock do JobStore com arquivo temporário.

    Yields:
        MagicMock: Mock do JobStore.
    """
    with patch("autotarefas.core.storage.job_store.JobStore") as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance

        mock_instance.jobs = {}
        mock_instance.storage_path = temp_dir / "jobs.json"

        yield mock_instance


# ============================================================================
# Fixtures de Logging
# ============================================================================


@pytest.fixture
def capture_logs(temp_dir: Path) -> Generator[Path, None, None]:
    """
    Captura logs em arquivo temporário.

    Yields:
        Path: Caminho do arquivo de log.
    """
    log_file = temp_dir / "test.log"

    from loguru import logger as loguru_logger

    handler_id = loguru_logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="DEBUG",
    )

    yield log_file

    loguru_logger.remove(handler_id)


@pytest.fixture
def mock_logger() -> Generator[MagicMock, None, None]:
    """
    Mock do logger do projeto.

    Yields:
        MagicMock: Mock do logger.
    """
    with patch("autotarefas.core.logger.logger") as mock:
        yield mock


# ============================================================================
# Fixtures de Dados
# ============================================================================


@pytest.fixture
def sample_json_data() -> dict[str, Any]:
    """
    Dados JSON de exemplo.

    Returns:
        dict: Dados estruturados.
    """
    return {
        "id": "test-001",
        "name": "Test Item",
        "created_at": datetime.now(UTC).isoformat(),
        "tags": ["test", "sample"],
        "metadata": {
            "version": "1.0",
            "author": "AutoTarefas",
        },
        "items": [
            {"id": 1, "value": "first"},
            {"id": 2, "value": "second"},
        ],
    }


@pytest.fixture
def sample_csv_data() -> str:
    """
    Dados CSV de exemplo.

    Returns:
        str: Conteúdo CSV.
    """
    return """id,name,email,age,city
1,Alice,alice@test.com,30,São Paulo
2,Bob,bob@test.com,25,Rio de Janeiro
3,Carol,carol@test.com,35,Belo Horizonte
4,David,david@test.com,28,Curitiba
5,Eve,eve@test.com,32,Porto Alegre
"""


# ============================================================================
# Markers Customizados
# ============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Registra markers customizados."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line(
        "markers", "requires_smtp: marks tests that require SMTP server"
    )
    config.addinivalue_line(
        "markers", "requires_network: marks tests that require network access"
    )


# ============================================================================
# Hooks
# ============================================================================


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """
    Modifica a coleta de testes.

    - Adiciona marker 'slow' automaticamente para testes de integração/e2e
    - Pula testes que requerem recursos não disponíveis
    """
    _ = config

    for item in items:
        nodeid = item.nodeid.lower()

        if "integration" in nodeid or "e2e" in nodeid:
            item.add_marker(pytest.mark.slow)

        if item.get_closest_marker("requires_smtp") and not os.environ.get(
            "TEST_SMTP_HOST"
        ):
            item.add_marker(pytest.mark.skip(reason="SMTP não configurado"))


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Ambiente
    "temp_dir",
    "temp_file",
    "env_vars",
    "isolated_env",
    # Configuração
    "test_settings",
    "mock_settings",
    # Arquivos
    "sample_files",
    "sample_tree",
    "large_file",
    # Email
    "mock_smtp",
    "mock_smtp_ssl",
    "mock_notifier",
    "mock_email_sender",
    # CLI
    "cli_runner",
    "cli_runner_isolated",
    "isolated_fs",
    "cli_context",
    # Tasks
    "sample_task_config",
    "mock_task_result",
    # Scheduler
    "mock_scheduler",
    "mock_job_store",
    # Logging
    "capture_logs",
    "mock_logger",
    # Dados
    "sample_json_data",
    "sample_csv_data",
]
