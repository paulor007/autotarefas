"""
Testes End-to-End do AutoTarefas.

Testes que simulam fluxos completos de usuário do início ao fim,
validando o comportamento do sistema como um todo.

Cenários cobertos:
    - Workflow de backup completo:
        Configuração → Criação → Verificação → Restauração → Validação
    - Workflow de limpeza agendada:
        Configuração → Agendamento → Execução → Relatório → Notificação
    - Workflow de monitoramento:
        Coleta de métricas → Alertas → Relatório → Envio por email
    - Workflow de CLI interativa:
        Inicialização → Comandos → Feedback → Arquivos gerados
    - Workflow de relatórios periódicos:
        Agendamento → Geração → Formatação → Salvamento → Envio

Estrutura esperada:
    tests/e2e/
    ├── __init__.py              # Este arquivo
    ├── test_backup_workflow.py  # Fluxo completo de backup
    ├── test_clean_workflow.py   # Fluxo completo de limpeza
    ├── test_monitor_workflow.py # Fluxo completo de monitoramento
    └── test_full_cycle.py       # Ciclo completo do sistema

Markers:
    Todos os testes neste pacote são automaticamente marcados com:
    - @pytest.mark.e2e
    - @pytest.mark.slow

Execução:
    # Todos os testes e2e
    pytest tests/e2e/ -v

    # Via marker
    pytest -m e2e

    # Com cobertura completa
    pytest tests/e2e/ --cov=autotarefas --cov-report=html -v

    # Excluir da suite rápida
    pytest -m "not e2e"

Notas:
    - Testes e2e são os mais lentos da suite (30s-2min cada).
    - Simulam o uso real do sistema por um usuário.
    - Podem criar estruturas de diretórios temporários complexas.
    - Utilizam mocks apenas para dependências externas (SMTP, rede).
    - Ideais para validação antes de release (Fase 12).
"""

__all__: list[str] = []
