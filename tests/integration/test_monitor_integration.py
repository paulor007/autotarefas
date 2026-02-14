"""
Testes de integração do módulo de monitoramento (monitor).

Este arquivo testa o MonitorTask que é responsável por coletar métricas
do sistema (CPU, memória, disco, rede) e gerar alertas quando os valores
excedem thresholds configurados.

=============================================================================
OBJETIVO DO MÓDULO monitor.py
=============================================================================

O módulo de monitoramento serve para:

1. **Coleta de Métricas do Sistema**
   - CPU: percentual de uso, número de cores, load average
   - Memória: total, disponível, usada, percentual, swap
   - Disco: espaço total/usado/livre por partição
   - Rede: bytes enviados/recebidos, hostname, IP

2. **Geração de Alertas**
   - Quando CPU excede threshold (ex: 80%)
   - Quando memória excede threshold (ex: 85%)
   - Quando disco excede threshold (ex: 90%)

3. **Informações do Sistema**
   - Sistema operacional, versão, arquitetura
   - Tempo de uptime
   - Versão do Python

=============================================================================
O QUE ESTES TESTES VERIFICAM
=============================================================================

- Coleta correta de métricas reais do sistema
- Formato e estrutura dos dados retornados
- Geração de alertas quando thresholds são excedidos
- Integração com JobStore e RunHistory
- Tratamento quando psutil não está disponível
- Coleta seletiva (apenas CPU, apenas memória, etc.)
- Métricas de disco para paths específicos

=============================================================================
CENÁRIOS DE INTEGRAÇÃO
=============================================================================

1. MonitorTask → Coleta → SystemMetrics → Alertas
2. MonitorTask → RunHistory (registro de execução)
3. MonitorTask → Notifier (envio de alertas)
4. JobStore → MonitorTask (execução agendada)

Estes testes usam o sistema real (não mockado) para garantir que as métricas
são coletadas corretamente no ambiente de execução.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ============================================================================
# Verificação de Dependências
# ============================================================================


def psutil_available() -> bool:
    """Verifica se psutil está disponível."""
    try:
        import psutil  # noqa: F401

        return True
    except ImportError:
        return False


# Marker para testes que requerem psutil
requires_psutil = pytest.mark.skipif(
    not psutil_available(),
    reason="psutil não instalado",
)


# ============================================================================
# Testes de Coleta de Métricas
# ============================================================================


@requires_psutil
class TestMonitorMetricsCollection:
    """
    Testes de coleta de métricas do sistema.

    Estes testes verificam se o MonitorTask consegue coletar métricas
    reais do sistema operacional onde os testes estão rodando.
    """

    def test_collect_all_metrics(self) -> None:
        """Deve coletar todas as métricas quando habilitadas."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=True,
            check_memory=True,
            check_disk=True,
            check_network=True,
            include_system_info=True,
        )

        assert result.is_success is True
        assert "metrics" in result.data

        metrics = result.data["metrics"]

        # Verificar estrutura
        assert "timestamp" in metrics
        assert "cpu" in metrics
        assert "memory" in metrics
        assert "disks" in metrics
        assert "network" in metrics
        assert "system" in metrics

    def test_collect_cpu_metrics(self) -> None:
        """Deve coletar métricas de CPU corretamente."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=True,
            check_memory=False,
            check_disk=False,
            cpu_interval=0.1,  # Intervalo curto para teste
        )

        assert result.is_success is True

        cpu = result.data["metrics"]["cpu"]

        # Verificar campos
        assert "percent" in cpu
        assert "count_logical" in cpu
        assert isinstance(cpu["percent"], float)
        assert cpu["percent"] >= 0
        assert cpu["count_logical"] >= 1

    def test_collect_memory_metrics(self) -> None:
        """Deve coletar métricas de memória corretamente."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=False,
            check_memory=True,
            check_disk=False,
        )

        assert result.is_success is True

        memory = result.data["metrics"]["memory"]

        # Verificar campos
        assert "total" in memory
        assert "available" in memory
        assert "used" in memory
        assert "percent" in memory
        assert memory["total"] > 0
        assert memory["percent"] >= 0

    def test_collect_disk_metrics(self) -> None:
        """Deve coletar métricas de disco corretamente."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=False,
            check_memory=False,
            check_disk=True,
        )

        assert result.is_success is True

        disks = result.data["metrics"]["disks"]

        # Deve ter pelo menos uma partição
        assert len(disks) >= 1

        # Verificar estrutura do primeiro disco
        disk = disks[0]
        assert "path" in disk
        assert "total" in disk
        assert "used" in disk
        assert "free" in disk
        assert "percent" in disk

    def test_collect_disk_specific_path(self) -> None:
        """Deve coletar métricas de disco para path específico."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=False,
            check_memory=False,
            check_disk=True,
            disk_paths=["/"],  # Raiz do sistema
        )

        assert result.is_success is True

        disks = result.data["metrics"]["disks"]
        assert len(disks) >= 1

    def test_collect_network_metrics(self) -> None:
        """Deve coletar métricas de rede corretamente."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=False,
            check_memory=False,
            check_disk=False,
            check_network=True,
        )

        assert result.is_success is True

        network = result.data["metrics"]["network"]

        assert "bytes_sent" in network
        assert "bytes_recv" in network
        assert "hostname" in network

    def test_collect_system_info(self) -> None:
        """Deve coletar informações do sistema."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=False,
            check_memory=False,
            check_disk=False,
            include_system_info=True,
        )

        assert result.is_success is True

        system = result.data["metrics"]["system"]

        assert "platform" in system
        assert "python_version" in system
        assert "uptime_seconds" in system


# ============================================================================
# Testes de Alertas
# ============================================================================


@requires_psutil
class TestMonitorAlerts:
    """
    Testes de geração de alertas.

    O MonitorTask gera alertas quando métricas excedem thresholds
    configurados. Estes testes verificam esse comportamento.
    """

    def test_no_alerts_with_high_threshold(self) -> None:
        """Não deve gerar alertas com threshold muito alto."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=True,
            check_memory=True,
            check_disk=True,
            cpu_threshold=100,  # Impossível exceder
            memory_threshold=100,
            disk_threshold=100,
            cpu_interval=0.1,
        )

        assert result.is_success is True
        assert result.data["has_alerts"] is False
        assert result.data["alerts_count"] == 0

    def test_cpu_alert_with_low_threshold(self) -> None:
        """Deve gerar alerta de CPU com threshold baixo."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=True,
            check_memory=False,
            check_disk=False,
            cpu_threshold=0,  # Sempre vai exceder
            cpu_interval=0.1,
        )

        assert result.is_success is True

        # Verifica se há alerta de CPU
        alerts = result.data["metrics"]["alerts"]
        cpu_alerts = [a for a in alerts if "CPU" in a]
        assert len(cpu_alerts) >= 1

    def test_memory_alert_with_low_threshold(self) -> None:
        """Deve gerar alerta de memória com threshold baixo."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=False,
            check_memory=True,
            check_disk=False,
            memory_threshold=0,  # Sempre vai exceder
        )

        assert result.is_success is True

        alerts = result.data["metrics"]["alerts"]
        memory_alerts = [a for a in alerts if "Memória" in a or "Memory" in a]
        assert len(memory_alerts) >= 1

    def test_disk_alert_with_low_threshold(self) -> None:
        """Deve gerar alerta de disco com threshold baixo."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=False,
            check_memory=False,
            check_disk=True,
            disk_threshold=0,  # Sempre vai exceder
        )

        assert result.is_success is True

        alerts = result.data["metrics"]["alerts"]
        disk_alerts = [a for a in alerts if "Disco" in a or "disk" in a.lower()]
        assert len(disk_alerts) >= 1

    def test_multiple_alerts(self) -> None:
        """Deve gerar múltiplos alertas quando necessário."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=True,
            check_memory=True,
            check_disk=True,
            cpu_threshold=0,
            memory_threshold=0,
            disk_threshold=0,
            cpu_interval=0.1,
        )

        assert result.is_success is True
        assert result.data["has_alerts"] is True
        # Pelo menos CPU e memória devem gerar alertas
        assert result.data["alerts_count"] >= 2


# ============================================================================
# Testes de Integração com Storage
# ============================================================================


@requires_psutil
class TestMonitorWithStorage:
    """
    Testes de integração com JobStore e RunHistory.

    Verifica se o MonitorTask pode ser executado como um job
    agendado e registrar seu histórico de execução.
    """

    def test_monitor_with_run_history(
        self,
        integration_env: dict[str, Path],
    ) -> None:
        """Deve registrar execução no RunHistory."""
        from autotarefas.core.storage.run_history import RunHistory, RunStatus
        from autotarefas.tasks.monitor import MonitorTask

        history = RunHistory(integration_env["data"] / "monitor_history.db")

        # Registrar início
        record = history.start_run(
            job_id="monitor-job-1",
            job_name="monitor_sistema",
            task="monitor",
            params={"check_cpu": True, "check_memory": True},
        )

        # Executar
        result = MonitorTask().run(
            check_cpu=True,
            check_memory=True,
            check_disk=False,
            cpu_interval=0.1,
        )

        # Registrar fim
        history.finish_run(
            record.id,
            RunStatus.SUCCESS if result.is_success else RunStatus.FAILED,
            duration=result.duration_seconds,
            output=result.message,
        )

        # Verificar histórico
        runs = history.get_by_job("monitor-job-1")
        assert len(runs) == 1
        assert runs[0].status == RunStatus.SUCCESS

    def test_monitor_job_from_store(
        self,
        populated_job_store: Any,
    ) -> None:
        """Deve executar monitoramento usando configuração do JobStore."""
        from autotarefas.tasks.monitor import MonitorTask

        # Obter job de monitoramento do store (se existir)
        job = populated_job_store.get_by_name("monitor_continuo")

        if job is None:
            pytest.skip("Job monitor_continuo não encontrado no store")

        # Executar
        result = MonitorTask().run(
            check_cpu=True,
            check_memory=True,
            cpu_interval=0.1,
        )

        assert result.is_success is True


# ============================================================================
# Testes de Integração com Notifier
# ============================================================================


@requires_psutil
class TestMonitorWithNotifier:
    """
    Testes de integração com o sistema de notificações.

    Quando alertas são gerados, o monitor pode enviar notificações.
    """

    def test_monitor_alerts_can_notify(
        self,
        integration_notifier: Any,
    ) -> None:
        """Alertas devem poder ser enviados via Notifier."""
        from autotarefas.core.notifier import NotificationLevel
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=True,
            check_memory=True,
            check_disk=False,
            cpu_threshold=0,  # Força alerta
            memory_threshold=0,
            cpu_interval=0.1,
        )

        # Se há alertas, enviar notificação
        if result.data["has_alerts"]:
            for alert in result.data["metrics"]["alerts"]:
                integration_notifier.notify(
                    alert,
                    level=NotificationLevel.WARNING,
                    title="Monitor Alert",
                )

            # Verificar que notificações foram capturadas
            captured = integration_notifier._test_captured
            assert len(captured) >= 1


# ============================================================================
# Testes de Validação
# ============================================================================


class TestMonitorValidation:
    """
    Testes de validação de pré-requisitos.

    O MonitorTask requer a biblioteca psutil para funcionar.
    """

    def test_validate_with_psutil(self) -> None:
        """Deve validar com sucesso quando psutil está disponível."""
        from autotarefas.tasks.monitor import PSUTIL_AVAILABLE, MonitorTask

        task = MonitorTask()
        valid, msg = task.validate()

        if PSUTIL_AVAILABLE:
            assert valid is True
        else:
            assert valid is False
            assert "psutil" in msg.lower()

    def test_validate_without_psutil(self) -> None:
        """Deve falhar validação sem psutil."""
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", False):
            task = MonitorTask()
            valid, msg = task.validate()

            assert valid is False
            assert "psutil" in msg.lower()


# ============================================================================
# Testes de Formato de Dados
# ============================================================================


@requires_psutil
class TestMonitorDataFormat:
    """
    Testes de formato e estrutura dos dados retornados.

    Verifica se os dados estão no formato esperado para
    serialização JSON e uso por outros componentes.
    """

    def test_metrics_serializable(self) -> None:
        """Métricas devem ser serializáveis para JSON."""
        import json

        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=True,
            check_memory=True,
            check_disk=True,
            cpu_interval=0.1,
        )

        # Tentar serializar para JSON
        json_str = json.dumps(result.data["metrics"])
        assert json_str is not None

        # Deserializar de volta
        parsed = json.loads(json_str)
        assert "cpu" in parsed
        assert "memory" in parsed

    def test_timestamp_format(self) -> None:
        """Timestamp deve estar em formato ISO."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=True, check_memory=False, check_disk=False, cpu_interval=0.1
        )

        timestamp = result.data["metrics"]["timestamp"]

        # Deve ser parseável como ISO
        parsed = datetime.fromisoformat(timestamp)
        assert isinstance(parsed, datetime)

    def test_formatted_values_present(self) -> None:
        """Valores formatados devem estar presentes."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=False,
            check_memory=True,
            check_disk=True,
            cpu_interval=0.1,
        )

        memory = result.data["metrics"]["memory"]
        assert "total_formatted" in memory
        assert "GB" in memory["total_formatted"] or "MB" in memory["total_formatted"]

        if result.data["metrics"]["disks"]:
            disk = result.data["metrics"]["disks"][0]
            assert "total_formatted" in disk


# ============================================================================
# Testes de Coleta Seletiva
# ============================================================================


@requires_psutil
class TestMonitorSelectiveCollection:
    """
    Testes de coleta seletiva de métricas.

    O MonitorTask permite habilitar/desabilitar cada tipo de métrica.
    """

    def test_only_cpu(self) -> None:
        """Deve coletar apenas CPU quando outras estão desabilitadas."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=True,
            check_memory=False,
            check_disk=False,
            check_network=False,
            include_system_info=False,
            cpu_interval=0.1,
        )

        assert result.is_success is True

        metrics = result.data["metrics"]
        assert metrics["cpu"]["percent"] >= 0
        # Memória deve ter valores zerados
        assert metrics["memory"]["total"] == 0

    def test_only_memory(self) -> None:
        """Deve coletar apenas memória quando outras estão desabilitadas."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=False,
            check_memory=True,
            check_disk=False,
            check_network=False,
        )

        assert result.is_success is True

        metrics = result.data["metrics"]
        assert metrics["memory"]["total"] > 0
        # CPU deve ter valores zerados
        assert metrics["cpu"]["percent"] == 0

    def test_all_disabled(self) -> None:
        """Deve funcionar mesmo com tudo desabilitado."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=False,
            check_memory=False,
            check_disk=False,
            check_network=False,
            include_system_info=False,
        )

        assert result.is_success is True
        assert "metrics" in result.data


# ============================================================================
# Testes de Edge Cases
# ============================================================================


@requires_psutil
class TestMonitorEdgeCases:
    """Testes de casos extremos."""

    def test_rapid_successive_calls(self) -> None:
        """Deve suportar chamadas sucessivas rápidas."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()

        results = []
        for _ in range(5):
            result = task.run(
                check_cpu=True,
                check_memory=True,
                check_disk=False,
                cpu_interval=0.05,
            )
            results.append(result)

        # Todas devem ter sucesso
        assert all(r.success for r in results)

    def test_nonexistent_disk_path(self) -> None:
        """Deve tratar path de disco inexistente graciosamente."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=False,
            check_memory=False,
            check_disk=True,
            disk_paths=["/nonexistent/path/12345"],
        )

        # Não deve falhar, apenas ignorar o path
        assert result.is_success is True

    def test_result_message_format(self) -> None:
        """Mensagem do resultado deve ter formato esperado."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        result = task.run(
            check_cpu=True,
            check_memory=True,
            check_disk=False,
            cpu_interval=0.1,
        )

        assert "CPU:" in result.message
        assert "Memória:" in result.message or "Memory:" in result.message
        assert "%" in result.message
