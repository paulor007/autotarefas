"""
Suite de Testes do AutoTarefas.

Este pacote contém todos os testes do projeto:

    tests/
    ├── conftest.py          # Fixtures globais
    ├── test_config.py       # Testes de configuração
    ├── test_logger.py       # Testes de logging
    ├── test_base.py         # Testes da BaseTask
    ├── test_utils.py        # Testes de utilitários
    ├── test_backup.py       # Testes de backup
    ├── test_cleaner.py      # Testes de limpeza
    ├── test_monitor.py      # Testes de monitoramento
    ├── test_scheduler.py    # Testes de agendamento
    ├── test_email.py        # Testes de email
    ├── test_notifier.py     # Testes de notificações
    ├── integration/         # Testes de integração
    │   └── test_cli.py
    └── e2e/                 # Testes end-to-end
        └── test_workflows.py

Execução:
    # Todos os testes
    pytest

    # Com cobertura
    pytest --cov=autotarefas --cov-report=html

    # Apenas testes rápidos
    pytest -m "not slow"

    # Apenas testes unitários
    pytest tests/test_*.py

    # Testes de integração
    pytest tests/integration/

    # Testes específicos
    pytest tests/test_backup.py -v

Markers disponíveis:
    - slow: testes lentos (inclui integration e e2e)
    - integration: testes de integração
    - e2e: testes end-to-end
    - requires_smtp: requer servidor SMTP
    - requires_network: requer acesso à rede

Fixtures principais (ver conftest.py):
    - temp_dir: diretório temporário
    - test_settings: configurações isoladas
    - mock_smtp: mock do servidor SMTP
    - cli_runner: runner para testes de CLI
    - sample_files: arquivos de exemplo
"""

__all__: list[str] = []
