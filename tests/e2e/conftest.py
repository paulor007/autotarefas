"""
Fixtures específicas para testes End-to-End (E2E) do AutoTarefas.

Este módulo estende as fixtures do conftest.py principal com fixtures
especializadas para testes E2E que simulam o uso real da CLI.

Fixtures disponíveis:
    - cli_runner: Runner do Click para invocar comandos
    - e2e_env: Ambiente completo para testes E2E
    - e2e_config: Configuração padrão para testes
    - sample_source_dir: Diretório fonte com arquivos de teste
    - sample_backup_dir: Diretório para backups
    - mock_smtp_e2e: Mock de SMTP para testes de email
    - cli_invoke: Helper para invocar comandos facilmente

Markers aplicados automaticamente:
    - @pytest.mark.e2e
    - @pytest.mark.slow
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner, Result

# ============================================================================
# Marker automático para testes E2E
# ============================================================================


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Adiciona markers automaticamente para testes E2E."""
    _ = config

    for item in items:
        # Todos os testes neste diretório recebem markers 'e2e' e 'slow'
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.slow)


# ============================================================================
# Fixtures de CLI
# ============================================================================


@pytest.fixture
def cli_runner() -> CliRunner:
    """
    Cria um CliRunner do Click para invocar comandos.

    O runner é configurado com:
        - env isolado
        - catch_exceptions=False para debug mais fácil

    Returns:
        CliRunner configurado para testes E2E
    """
    return CliRunner(env={"AUTOTAREFAS_ENV": "testing"})


@pytest.fixture
def cli_runner_isolated(cli_runner: CliRunner) -> Generator[CliRunner, None, None]:
    """
    CliRunner com filesystem isolado.

    Cria um diretório temporário isolado para cada teste.

    Yields:
        CliRunner em contexto isolado
    """
    with cli_runner.isolated_filesystem():
        yield cli_runner


# ============================================================================
# Fixtures de Ambiente E2E
# ============================================================================


@pytest.fixture
def e2e_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """
    Cria estrutura completa de diretórios para testes E2E.

    Estrutura criada:
        e2e_test/
        ├── source/         # Arquivos fonte
        ├── backups/        # Diretório de backups
        ├── temp/           # Arquivos temporários
        ├── logs/           # Logs
        ├── reports/        # Relatórios gerados
        ├── data/           # Dados persistentes
        └── config/         # Configurações

    Yields:
        Path: Diretório raiz da estrutura E2E
    """
    root = tmp_path / "e2e_test"
    root.mkdir()

    # Criar subdiretórios
    (root / "source").mkdir()
    (root / "backups").mkdir()
    (root / "temp").mkdir()
    (root / "logs").mkdir()
    (root / "reports").mkdir()
    (root / "data").mkdir()
    (root / "config").mkdir()

    yield root


@pytest.fixture
def e2e_env(
    e2e_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[dict[str, Path], None, None]:
    """
    Configura ambiente completo para testes E2E.

    Define variáveis de ambiente apontando para diretórios temporários
    e retorna dicionário com os caminhos.

    Yields:
        dict: Mapeamento de nome → Path dos diretórios
    """
    paths = {
        "root": e2e_dir,
        "source": e2e_dir / "source",
        "backups": e2e_dir / "backups",
        "temp": e2e_dir / "temp",
        "logs": e2e_dir / "logs",
        "reports": e2e_dir / "reports",
        "data": e2e_dir / "data",
        "config": e2e_dir / "config",
    }

    # Limpar variáveis existentes
    for key in list(os.environ.keys()):
        if key.startswith(("AUTOTAREFAS_", "EMAIL_", "LOG_")):
            monkeypatch.delenv(key, raising=False)

    # Configurar ambiente de teste
    monkeypatch.setenv("AUTOTAREFAS_ENV", "testing")
    monkeypatch.setenv("AUTOTAREFAS_DEBUG", "true")
    monkeypatch.setenv("DATA_DIR", str(paths["data"]))
    monkeypatch.setenv("LOG_PATH", str(paths["logs"]))
    monkeypatch.setenv("BACKUP_PATH", str(paths["backups"]))
    monkeypatch.setenv("TEMP_PATH", str(paths["temp"]))
    monkeypatch.setenv("REPORTS_PATH", str(paths["reports"]))

    yield paths


# ============================================================================
# Fixtures de Arquivos de Teste
# ============================================================================


@pytest.fixture
def sample_source_dir(e2e_env: dict[str, Path]) -> Path:
    """
    Cria diretório fonte com arquivos para testes.

    Estrutura:
        source/
        ├── documents/
        │   ├── report.txt
        │   ├── data.csv
        │   └── notes.md
        ├── images/
        │   └── photo.jpg (fake)
        ├── temp/
        │   ├── cache.tmp
        │   └── old.log
        └── config.json

    Returns:
        Path: Diretório source populado
    """
    source = e2e_env["source"]

    # Documentos
    docs = source / "documents"
    docs.mkdir()
    (docs / "report.txt").write_text("Annual Report 2024\n" * 50)
    (docs / "data.csv").write_text(
        "id,name,value\n" + "\n".join(f"{i},item{i},{i * 10}" for i in range(50))
    )
    (docs / "notes.md").write_text("# Notes\n\n- Item 1\n- Item 2\n- Item 3\n")

    # Imagens (fake)
    images = source / "images"
    images.mkdir()
    (images / "photo.jpg").write_bytes(b"\xff\xd8\xff" + b"x" * 500)

    # Temporários
    temp = source / "temp"
    temp.mkdir()
    (temp / "cache.tmp").write_text("cache data")
    log_file = temp / "old.log"
    log_file.write_text("old log data")
    # Fazer arquivo antigo
    old_time = time.time() - (40 * 24 * 60 * 60)  # 40 dias atrás
    os.utime(log_file, (old_time, old_time))

    # Config
    (source / "config.json").write_text(json.dumps({"version": "1.0", "enabled": True}))

    return source


@pytest.fixture
def sample_temp_files(e2e_env: dict[str, Path]) -> Path:
    """
    Cria arquivos temporários para teste de limpeza.

    Returns:
        Path: Diretório temp com arquivos
    """
    temp = e2e_env["temp"]

    # Arquivos recentes
    for i in range(3):
        (temp / f"recent_{i}.txt").write_text(f"Recent {i}")

    # Arquivos antigos
    for i in range(3):
        f = temp / f"old_{i}.tmp"
        f.write_text(f"Old {i}")
        old_time = time.time() - (35 * 24 * 60 * 60)
        os.utime(f, (old_time, old_time))

    return temp


# ============================================================================
# Fixtures de Mock
# ============================================================================


@pytest.fixture
def mock_smtp_e2e() -> Generator[MagicMock, None, None]:
    """
    Mock de servidor SMTP para testes E2E de email.

    Captura todas as mensagens enviadas.

    Yields:
        MagicMock: Mock do SMTP
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
# Helper: Invocar CLI
# ============================================================================


@pytest.fixture
def cli_invoke(cli_runner: CliRunner) -> Callable[..., Result]:
    """
    Helper para invocar comandos da CLI facilmente.

    Uso:
        def test_example(cli_invoke):
            result = cli_invoke("backup", "run", "/path")
            assert result.exit_code == 0

    Returns:
        Callable que invoca a CLI
    """
    from autotarefas.cli.main import cli

    def _invoke(*args: str, catch_exceptions: bool = True, **kwargs: Any) -> Result:
        return cli_runner.invoke(
            cli,
            args,
            catch_exceptions=catch_exceptions,
            **kwargs,
        )

    return _invoke


@pytest.fixture
def cli_invoke_isolated(
    cli_runner_isolated: CliRunner,
) -> Generator[Callable[..., Result], None, None]:
    """
    Helper para invocar comandos em filesystem isolado.

    Yields:
        Callable que invoca a CLI em ambiente isolado
    """
    from autotarefas.cli.main import cli

    def _invoke(*args: str, catch_exceptions: bool = True, **kwargs: Any) -> Result:
        return cli_runner_isolated.invoke(
            cli,
            args,
            catch_exceptions=catch_exceptions,
            **kwargs,
        )

    yield _invoke


# ============================================================================
# Helpers de Assertação
# ============================================================================


def assert_success(result: Result, message: str = "") -> None:
    """
    Verifica se comando foi executado com sucesso.

    Args:
        result: Resultado do comando
        message: Mensagem adicional para erro
    """
    if result.exit_code != 0:
        error_msg = f"Comando falhou com código {result.exit_code}"
        if message:
            error_msg += f": {message}"
        if result.output:
            error_msg += f"\nOutput: {result.output}"
        if result.exception:
            error_msg += f"\nException: {result.exception}"
        pytest.fail(error_msg)


def assert_failure(result: Result, expected_code: int | None = None) -> None:
    """
    Verifica se comando falhou como esperado.

    Args:
        result: Resultado do comando
        expected_code: Código de saída esperado (None = qualquer não-zero)
    """
    if result.exit_code == 0:
        pytest.fail(
            f"Comando deveria ter falhado, mas teve sucesso.\nOutput: {result.output}"
        )

    if expected_code is not None and result.exit_code != expected_code:
        pytest.fail(
            f"Esperado código {expected_code}, obtido {result.exit_code}.\nOutput: {result.output}"
        )


def assert_output_contains(result: Result, *texts: str) -> None:
    """
    Verifica se output contém textos.

    Args:
        result: Resultado do comando
        texts: Textos que devem estar no output
    """
    output = result.output or ""
    for text in texts:
        if text not in output:
            pytest.fail(f"Texto '{text}' não encontrado no output:\n{output}")


def assert_output_not_contains(result: Result, *texts: str) -> None:
    """
    Verifica se output NÃO contém textos.

    Args:
        result: Resultado do comando
        texts: Textos que NÃO devem estar no output
    """
    output = result.output or ""
    for text in texts:
        if text in output:
            pytest.fail(
                f"Texto '{text}' encontrado no output (não esperado):\n{output}"
            )


def assert_file_created(path: Path) -> None:
    """Verifica se arquivo foi criado."""
    if not path.exists():
        pytest.fail(f"Arquivo não foi criado: {path}")


def assert_file_not_exists(path: Path) -> None:
    """Verifica se arquivo NÃO existe."""
    if path.exists():
        pytest.fail(f"Arquivo deveria não existir: {path}")


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Runners
    "cli_runner",
    "cli_runner_isolated",
    # Ambiente
    "e2e_dir",
    "e2e_env",
    # Arquivos
    "sample_source_dir",
    "sample_temp_files",
    # Mock
    "mock_smtp_e2e",
    # Helpers
    "cli_invoke",
    "cli_invoke_isolated",
    # Assertações
    "assert_success",
    "assert_failure",
    "assert_output_contains",
    "assert_output_not_contains",
    "assert_file_created",
    "assert_file_not_exists",
]
