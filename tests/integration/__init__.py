"""
Testes de Integração do AutoTarefas.

Testes que verificam a integração entre múltiplos componentes do sistema,
validando que os módulos funcionam corretamente em conjunto.

Cenários cobertos:
    - CLI completa (comandos → tasks → resultado)
    - Tasks com storage (scheduler + job_store + run_history)
    - Scheduler com notificações (agendamento → execução → email)
    - Backup → Restore (ciclo completo)
    - Cleaner com monitoramento (limpeza → relatório de espaço)
    - Email end-to-end (config → envio → template → notificação)
    - Reporter com dados reais (coleta → formatação → arquivo)

Estrutura esperada:
    tests/integration/
    ├── __init__.py              # Este arquivo
    ├── test_cli_integration.py  # CLI com tasks reais
    ├── test_task_pipeline.py    # Pipeline completa de tasks
    ├── test_storage.py          # Persistência e histórico
    └── test_notification.py     # Fluxo de notificações

Markers:
    Todos os testes neste pacote são automaticamente marcados com:
    - @pytest.mark.integration
    - @pytest.mark.slow

Execução:
    # Todos os testes de integração
    pytest tests/integration/ -v

    # Via marker
    pytest -m integration

    # Com cobertura
    pytest tests/integration/ --cov=autotarefas -v

    # Excluir da suite rápida
    pytest -m "not integration"

Notas:
    - Testes de integração podem criar arquivos temporários em disco.
    - Alguns testes podem depender de configurações específicas (.env).
    - Testes que precisam de SMTP usam mock (não requerem servidor real).
    - Tempo médio estimado: 10-30s por módulo de teste.
"""

__all__: list[str] = []
