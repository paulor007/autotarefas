"""
Testes do módulo de monitoramento.

Testa:
    - DiskMetrics: Métricas de disco
    - MemoryMetrics: Métricas de memória
    - CpuMetrics: Métricas de CPU
    - NetworkMetrics: Métricas de rede
    - SystemInfo: Informações do sistema
    - SystemMetrics: Conjunto completo
    - MonitorTask: Coleta de métricas
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Testes de DiskMetrics
# =============================================================================


class TestDiskMetrics:
    """Testes da dataclass DiskMetrics."""

    def test_disk_metrics_creation(self):
        """Deve criar DiskMetrics corretamente."""
        from autotarefas.tasks.monitor import DiskMetrics

        metrics = DiskMetrics(
            path="/",
            total=100 * 1024**3,  # 100 GB
            used=60 * 1024**3,  # 60 GB
            free=40 * 1024**3,  # 40 GB
            percent=60.0,
        )

        assert metrics.path == "/"
        assert metrics.total == 100 * 1024**3
        assert metrics.percent == 60.0

    def test_disk_metrics_formatted_properties(self):
        """Deve formatar valores corretamente."""
        from autotarefas.tasks.monitor import DiskMetrics

        metrics = DiskMetrics(
            path="/home",
            total=1024**3,  # 1 GB
            used=512 * 1024**2,  # 512 MB
            free=512 * 1024**2,
            percent=50.0,
        )

        assert isinstance(metrics.total_formatted, str) and metrics.total_formatted
        assert isinstance(metrics.used_formatted, str) and metrics.used_formatted
        assert isinstance(metrics.free_formatted, str) and metrics.free_formatted

    def test_disk_metrics_to_dict(self):
        """to_dict deve retornar dicionário completo."""
        from autotarefas.tasks.monitor import DiskMetrics

        metrics = DiskMetrics(path="/", total=1000, used=600, free=400, percent=60.0)
        data = metrics.to_dict()

        assert isinstance(data, dict)
        assert data["path"] == "/"
        assert data["total"] == 1000
        assert data["percent"] == 60.0
        assert "total_formatted" in data
        assert "used_formatted" in data
        assert "free_formatted" in data


# =============================================================================
# Testes de MemoryMetrics
# =============================================================================


class TestMemoryMetrics:
    """Testes da dataclass MemoryMetrics."""

    def test_memory_metrics_creation(self):
        """Deve criar MemoryMetrics corretamente."""
        from autotarefas.tasks.monitor import MemoryMetrics

        metrics = MemoryMetrics(
            total=16 * 1024**3,  # 16 GB
            available=8 * 1024**3,
            used=8 * 1024**3,
            percent=50.0,
        )

        assert metrics.total == 16 * 1024**3
        assert metrics.percent == 50.0

    def test_memory_metrics_with_swap(self):
        """Deve aceitar métricas de swap (opcionais)."""
        from autotarefas.tasks.monitor import MemoryMetrics

        metrics = MemoryMetrics(
            total=16 * 1024**3,
            available=8 * 1024**3,
            used=8 * 1024**3,
            percent=50.0,
            swap_total=4 * 1024**3,
            swap_used=1 * 1024**3,
            swap_percent=25.0,
        )

        assert metrics.swap_total == 4 * 1024**3
        assert metrics.swap_used == 1 * 1024**3
        assert metrics.swap_percent == 25.0

    def test_memory_metrics_formatted(self):
        """Deve formatar valores."""
        from autotarefas.tasks.monitor import MemoryMetrics

        metrics = MemoryMetrics(
            total=8 * 1024**3,
            available=4 * 1024**3,
            used=4 * 1024**3,
            percent=50.0,
        )

        assert isinstance(metrics.total_formatted, str) and metrics.total_formatted
        assert (
            isinstance(metrics.available_formatted, str) and metrics.available_formatted
        )
        assert isinstance(metrics.used_formatted, str) and metrics.used_formatted

    def test_memory_metrics_to_dict(self):
        """to_dict deve retornar dicionário."""
        from autotarefas.tasks.monitor import MemoryMetrics

        metrics = MemoryMetrics(total=1000, available=500, used=500, percent=50.0)
        data = metrics.to_dict()

        assert isinstance(data, dict)
        assert data["total"] == 1000
        assert data["percent"] == 50.0
        assert "total_formatted" in data
        assert "available_formatted" in data
        assert "used_formatted" in data


# =============================================================================
# Testes de CpuMetrics
# =============================================================================


class TestCpuMetrics:
    """Testes da dataclass CpuMetrics."""

    def test_cpu_metrics_creation(self):
        """Deve criar CpuMetrics corretamente."""
        from autotarefas.tasks.monitor import CpuMetrics

        metrics = CpuMetrics(percent=45.5, count_logical=8)

        assert metrics.percent == 45.5
        assert metrics.count_logical == 8

    def test_cpu_metrics_with_optional_fields(self):
        """Deve aceitar campos opcionais."""
        from autotarefas.tasks.monitor import CpuMetrics

        metrics = CpuMetrics(
            percent=75.0,
            count_logical=8,
            count_physical=4,
            per_cpu=[50.0, 60.0, 70.0, 80.0],
            load_avg=(1.0, 2.0, 3.0),
        )

        assert metrics.count_physical == 4
        assert metrics.per_cpu is not None and len(metrics.per_cpu) == 4
        assert metrics.load_avg is not None and len(metrics.load_avg) == 3

    def test_cpu_metrics_to_dict(self):
        """to_dict deve retornar dicionário."""
        from autotarefas.tasks.monitor import CpuMetrics

        metrics = CpuMetrics(
            percent=50.0, count_logical=4, count_physical=2, per_cpu=[10.0, 20.0]
        )
        data = metrics.to_dict()

        assert isinstance(data, dict)
        assert data["percent"] == 50.0
        assert data["count_logical"] == 4
        assert "per_cpu" in data


# =============================================================================
# Testes de NetworkMetrics
# =============================================================================


class TestNetworkMetrics:
    """Testes da dataclass NetworkMetrics."""

    def test_network_metrics_creation(self):
        """Deve criar NetworkMetrics corretamente."""
        from autotarefas.tasks.monitor import NetworkMetrics

        metrics = NetworkMetrics(
            bytes_sent=1000000,
            bytes_recv=2000000,
            packets_sent=1000,
            packets_recv=2000,
            hostname="myhost",
            ip_address="127.0.0.1",
        )

        assert metrics.bytes_sent == 1000000
        assert metrics.bytes_recv == 2000000
        assert metrics.hostname == "myhost"
        assert metrics.ip_address == "127.0.0.1"

    def test_network_metrics_to_dict(self):
        """to_dict deve retornar dicionário."""
        from autotarefas.tasks.monitor import NetworkMetrics

        metrics = NetworkMetrics(
            bytes_sent=1024 * 1024,
            bytes_recv=2 * 1024 * 1024,
            packets_sent=10,
            packets_recv=20,
        )
        data = metrics.to_dict()

        assert isinstance(data, dict)
        assert data["bytes_sent"] == 1024 * 1024
        assert "bytes_sent_formatted" in data
        assert "bytes_recv_formatted" in data


# =============================================================================
# Testes de SystemInfo
# =============================================================================


class TestSystemInfo:
    """Testes da dataclass SystemInfo."""

    def test_system_info_creation(self):
        """Deve criar SystemInfo corretamente."""
        from autotarefas.tasks.monitor import SystemInfo

        boot_time = datetime.now() - timedelta(days=1)

        info = SystemInfo(
            platform="Linux",
            platform_release="5.15.0",
            platform_version="#1 SMP",
            architecture="x86_64",
            processor="generic-cpu",
            python_version="3.12.0",
            boot_time=boot_time,
        )

        assert info.platform == "Linux"
        assert info.processor == "generic-cpu"
        assert info.boot_time == boot_time

    def test_system_info_uptime_properties(self):
        """Deve calcular uptime a partir do boot_time."""
        from autotarefas.tasks.monitor import SystemInfo

        boot_time = datetime.now() - timedelta(seconds=86400)  # 1 dia
        info = SystemInfo(
            platform="Linux",
            platform_release="5.0",
            platform_version="#1",
            architecture="x86_64",
            processor="cpu",
            python_version="3.12",
            boot_time=boot_time,
        )

        assert info.uptime_seconds is not None
        assert info.uptime_seconds > 0
        assert isinstance(info.uptime_formatted, str) and info.uptime_formatted

    def test_system_info_to_dict(self):
        """to_dict deve retornar dicionário."""
        from autotarefas.tasks.monitor import SystemInfo

        info = SystemInfo(
            platform="Linux",
            platform_release="5.0",
            platform_version="#1",
            architecture="x86_64",
            processor="cpu",
            python_version="3.12",
            boot_time=datetime.now() - timedelta(seconds=10),
        )

        data = info.to_dict()
        assert isinstance(data, dict)
        assert data["platform"] == "Linux"
        assert "uptime_seconds" in data


# =============================================================================
# Testes de SystemMetrics
# =============================================================================


class TestSystemMetrics:
    """Testes da dataclass SystemMetrics."""

    def test_system_metrics_creation(self):
        """Deve criar SystemMetrics corretamente."""
        from autotarefas.tasks.monitor import CpuMetrics, MemoryMetrics, SystemMetrics

        metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu=CpuMetrics(percent=50.0, count_logical=4),
            memory=MemoryMetrics(total=8000, available=4000, used=4000, percent=50.0),
        )

        assert metrics.cpu is not None and metrics.cpu.percent == 50.0
        assert metrics.memory is not None and metrics.memory.percent == 50.0
        assert isinstance(metrics.disks, list)

    def test_system_metrics_with_disks(self):
        """Deve aceitar lista de discos."""
        from autotarefas.tasks.monitor import (
            CpuMetrics,
            DiskMetrics,
            MemoryMetrics,
            SystemMetrics,
        )

        metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu=CpuMetrics(percent=50.0, count_logical=4),
            memory=MemoryMetrics(total=8000, available=4000, used=4000, percent=50.0),
            disks=[
                DiskMetrics(path="/", total=100, used=50, free=50, percent=50.0),
                DiskMetrics(path="/home", total=200, used=100, free=100, percent=50.0),
            ],
        )

        assert len(metrics.disks) == 2

    def test_system_metrics_with_alerts(self):
        """Deve aceitar lista de alertas."""
        from autotarefas.tasks.monitor import CpuMetrics, MemoryMetrics, SystemMetrics

        metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu=CpuMetrics(percent=95.0, count_logical=4),
            memory=MemoryMetrics(total=8000, available=400, used=7600, percent=95.0),
            alerts=["CPU alta", "Memória alta"],
        )

        assert len(metrics.alerts) == 2

    def test_system_metrics_to_dict(self):
        """to_dict deve retornar dicionário completo."""
        from autotarefas.tasks.monitor import CpuMetrics, MemoryMetrics, SystemMetrics

        metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu=CpuMetrics(percent=50.0, count_logical=4),
            memory=MemoryMetrics(total=8000, available=4000, used=4000, percent=50.0),
        )

        data = metrics.to_dict()
        assert isinstance(data, dict)
        assert "timestamp" in data
        assert "cpu" in data
        assert "memory" in data
        assert "disks" in data


# =============================================================================
# Testes de MonitorTask
# =============================================================================


class TestMonitorTask:
    """Testes da classe MonitorTask."""

    def test_task_name(self):
        """Task deve ter nome 'monitor'."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        assert task.name == "monitor"

    def test_task_description(self):
        """Task deve ter descrição."""
        from autotarefas.tasks.monitor import MonitorTask

        task = MonitorTask()
        assert task.description is not None
        assert len(task.description) > 0


class TestMonitorTaskValidation:
    """Testes de validação do MonitorTask."""

    def test_validate_without_psutil(self):
        """Deve falhar se psutil não estiver disponível."""
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", False):
            task = MonitorTask()
            is_valid, error = task.validate()
            assert is_valid is False
            assert "psutil" in error.lower()

    def test_validate_with_psutil(self):
        """Deve passar com psutil disponível."""
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", True):
            task = MonitorTask()
            is_valid, error = task.validate()
            assert is_valid is True
            assert error == ""


class TestMonitorTaskExecution:
    """Testes de execução do MonitorTask."""

    @pytest.fixture
    def mock_psutil(self):
        """Mock do psutil."""
        with patch("autotarefas.tasks.monitor.psutil") as mock:
            # CPU
            def cpu_percent(*_args, **kwargs):
                if kwargs.get("percpu") is True:
                    return [50.0, 60.0, 70.0, 80.0]
                return 45.5

            def cpu_count(*_args, **kwargs):
                logical = kwargs.get("logical", True)
                return 8 if logical else 4

            mock.cpu_percent.side_effect = cpu_percent
            mock.cpu_count.side_effect = cpu_count

            # Load average
            mock.getloadavg.return_value = (1.0, 2.0, 3.0)

            # Memory (+ swap)
            mock.virtual_memory.return_value = MagicMock(
                total=16 * 1024**3,
                available=8 * 1024**3,
                used=8 * 1024**3,
                percent=50.0,
            )
            mock.swap_memory.return_value = MagicMock(
                total=4 * 1024**3,
                used=1 * 1024**3,
                percent=25.0,
            )

            # Disk
            mock.disk_partitions.return_value = [
                MagicMock(mountpoint="/", device="/dev/sda1"),
                MagicMock(mountpoint="/home", device="/dev/sda2"),
            ]

            def disk_usage(_mountpoint: str):
                return MagicMock(
                    total=100 * 1024**3,
                    used=60 * 1024**3,
                    free=40 * 1024**3,
                    percent=60.0,
                )

            mock.disk_usage.side_effect = disk_usage

            # Network
            mock.net_io_counters.return_value = MagicMock(
                bytes_sent=1000000,
                bytes_recv=2000000,
                packets_sent=1000,
                packets_recv=2000,
            )

            # Boot time (epoch seconds)
            mock.boot_time.return_value = (
                datetime.now() - timedelta(days=1)
            ).timestamp()

            yield mock

    def test_execute_basic(self, mock_psutil):
        """Deve executar coleta básica."""
        _ = mock_psutil
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", True):
            task = MonitorTask()
            result = task.execute()
            assert result.is_success
            assert isinstance(result.data, dict)
            assert "metrics" in result.data

    def test_execute_returns_metrics_dict(self, mock_psutil):
        """Deve retornar métricas no resultado."""
        _ = mock_psutil
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", True):
            task = MonitorTask()
            result = task.execute()
            assert result.is_success
            metrics = result.data["metrics"]
            assert isinstance(metrics, dict)
            assert "cpu" in metrics
            assert "memory" in metrics
            assert "disks" in metrics

    def test_execute_cpu_only(self, mock_psutil):
        """Deve coletar CPU e não coletar memória/disco/rede quando desabilitado."""
        _ = mock_psutil
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", True):
            task = MonitorTask()
            result = task.execute(
                check_cpu=True,
                check_memory=False,
                check_disk=False,
                check_network=False,
            )
            assert result.is_success

            metrics = result.data["metrics"]
            assert metrics.get("cpu") is not None

            # Memória vira zeros (não vira None).
            assert metrics["memory"]["total"] == 0
            assert metrics["memory"]["percent"] == 0.0

            # Discos vira lista vazia.
            assert metrics["disks"] == []

            # Rede não aparece quando desabilitada.
            assert "network" not in metrics

    def test_execute_with_thresholds_generates_alerts(self, mock_psutil):
        """Deve gerar alertas quando thresholds são excedidos."""

        def cpu_percent(*_args, **kwargs):
            if kwargs.get("percpu") is True:
                return [95.0, 95.0, 95.0, 95.0]
            return 95.0

        mock_psutil.cpu_percent.side_effect = cpu_percent

        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", True):
            task = MonitorTask()
            result = task.execute(cpu_threshold=80)
            assert result.is_success
            alerts = result.data["metrics"].get("alerts", [])
            assert isinstance(alerts, list)
            assert any("cpu" in str(a).lower() for a in alerts)

    def test_execute_with_disk_paths(self, mock_psutil):
        """Deve aceitar caminhos específicos de disco."""
        _ = mock_psutil
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", True):
            task = MonitorTask()
            result = task.execute(check_disk=True, disk_paths=["/"])
            assert result.is_success
            disks = result.data["metrics"].get("disks", [])
            assert isinstance(disks, list)
            assert len(disks) >= 1

    def test_execute_with_network(self, mock_psutil):
        """Deve coletar métricas de rede quando solicitado."""
        _ = mock_psutil
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", True):
            task = MonitorTask()
            result = task.execute(check_network=True)
            assert result.is_success
            metrics = result.data["metrics"]
            assert metrics.get("network") is not None

    def test_execute_with_system_info(self, mock_psutil):
        """Deve incluir info do sistema quando solicitado."""
        _ = mock_psutil
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", True):
            task = MonitorTask()
            result = task.execute(include_system_info=True)
            assert result.is_success
            metrics = result.data["metrics"]
            assert metrics.get("system") is not None


class TestMonitorTaskAlerts:
    """Testes de alertas do MonitorTask."""

    @pytest.fixture
    def mock_high_usage(self):
        """Mock com uso alto de recursos."""
        with patch("autotarefas.tasks.monitor.psutil") as mock:
            mock.cpu_percent.side_effect = lambda *_a, **kw: (
                [95.0, 95.0] if kw.get("percpu") else 95.0
            )
            mock.cpu_count.side_effect = lambda *_a, **kw: (
                4 if kw.get("logical", True) else 2
            )
            mock.getloadavg.return_value = (10.0, 10.0, 10.0)

            mock.virtual_memory.return_value = MagicMock(
                total=8 * 1024**3,
                available=400 * 1024**2,
                used=7600 * 1024**2,
                percent=95.0,
            )
            mock.swap_memory.return_value = MagicMock(
                total=4 * 1024**3,
                used=3 * 1024**3,
                percent=75.0,
            )

            mock.disk_partitions.return_value = [
                MagicMock(mountpoint="/", device="/dev/sda1")
            ]
            mock.disk_usage.return_value = MagicMock(
                total=100 * 1024**3,
                used=95 * 1024**3,
                free=5 * 1024**3,
                percent=95.0,
            )

            mock.net_io_counters.return_value = MagicMock(
                bytes_sent=1000000,
                bytes_recv=2000000,
                packets_sent=1000,
                packets_recv=2000,
            )

            mock.boot_time.return_value = (
                datetime.now() - timedelta(days=1)
            ).timestamp()
            yield mock

    def test_cpu_alert(self, mock_high_usage):
        """Deve gerar alerta de CPU alta."""
        _ = mock_high_usage
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", True):
            task = MonitorTask()
            result = task.execute(cpu_threshold=80)
            assert result.is_success
            alerts = result.data["metrics"].get("alerts", [])
            assert any("cpu" in str(a).lower() for a in alerts)

    def test_memory_alert(self, mock_high_usage):
        """Deve gerar alerta de memória alta."""
        _ = mock_high_usage
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", True):
            task = MonitorTask()
            result = task.execute(memory_threshold=80)
            assert result.is_success
            alerts = result.data["metrics"].get("alerts", [])
            assert any(
                ("memória" in str(a).lower()) or ("memoria" in str(a).lower())
                for a in alerts
            )

    def test_disk_alert(self, mock_high_usage):
        """Deve gerar alerta de disco cheio."""
        _ = mock_high_usage
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", True):
            task = MonitorTask()
            result = task.execute(disk_threshold=80)
            assert result.is_success
            alerts = result.data["metrics"].get("alerts", [])
            assert any(
                ("disco" in str(a).lower()) or ("disk" in str(a).lower())
                for a in alerts
            )


# =============================================================================
# Testes de Edge Cases
# =============================================================================


class TestMonitorEdgeCases:
    """Testes de casos extremos."""

    def test_psutil_not_installed(self):
        """Deve tratar psutil não instalado."""
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", False):
            task = MonitorTask()
            is_valid, _error = task.validate()
            assert is_valid is False

    def test_memory_failure_but_disabled(self):
        """Se memória falhar mas check_memory=False, deve continuar."""
        from autotarefas.tasks.monitor import MonitorTask

        with patch("autotarefas.tasks.monitor.psutil") as mock:
            mock.cpu_percent.return_value = 50.0
            mock.cpu_count.side_effect = lambda *_a, **kw: (
                4 if kw.get("logical", True) else 2
            )
            mock.getloadavg.return_value = (1.0, 1.0, 1.0)

            mock.virtual_memory.side_effect = Exception("Memory error")
            mock.swap_memory.return_value = MagicMock(total=0, used=0, percent=0)

            mock.disk_partitions.return_value = []
            mock.disk_usage.return_value = MagicMock(total=0, used=0, free=0, percent=0)
            mock.boot_time.return_value = (
                datetime.now() - timedelta(days=1)
            ).timestamp()

            with patch("autotarefas.tasks.monitor.PSUTIL_AVAILABLE", True):
                task = MonitorTask()
                result = task.execute(check_memory=False)
                assert result.status.is_finished

    def test_zero_values(self):
        """Deve tratar valores zero."""
        from autotarefas.tasks.monitor import DiskMetrics, MemoryMetrics

        disk = DiskMetrics(path="/", total=0, used=0, free=0, percent=0.0)
        assert disk.percent == 0.0

        memory = MemoryMetrics(total=0, available=0, used=0, percent=0.0)
        assert memory.percent == 0.0

    def test_very_large_values(self):
        """Deve tratar valores muito grandes."""
        from autotarefas.tasks.monitor import DiskMetrics

        disk = DiskMetrics(
            path="/",
            total=100 * 1024**4,  # 100 TB
            used=50 * 1024**4,
            free=50 * 1024**4,
            percent=50.0,
        )

        formatted = disk.total_formatted
        assert isinstance(formatted, str) and formatted
