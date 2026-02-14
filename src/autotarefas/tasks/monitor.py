"""
Task de Monitoramento do AutoTarefas.

Fornece funcionalidades para monitoramento do sistema:
    - MonitorTask: Coleta métricas do sistema
    - SystemMetrics: Estrutura de dados das métricas
    - Alertas configuráveis por threshold

Uso:
    from autotarefas.tasks import MonitorTask

    task = MonitorTask()
    result = task.run()
    print(result.data["metrics"])
"""

from __future__ import annotations

import platform
import socket
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

try:
    import psutil  # type: ignore

    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore
    PSUTIL_AVAILABLE = False

from autotarefas.config import settings
from autotarefas.core.base import BaseTask, TaskResult
from autotarefas.core.logger import logger
from autotarefas.utils.helpers import format_size

# =============================================================================
# Models (métricas)
# =============================================================================


@dataclass(slots=True)
class DiskMetrics:
    """
    Métricas de disco.

    Attributes:
        path: Ponto de montagem
        total: Espaço total em bytes
        used: Espaço usado em bytes
        free: Espaço livre em bytes
        percent: Percentual de uso
    """

    path: str
    total: int
    used: int
    free: int
    percent: float

    @property
    def total_formatted(self) -> str:
        """Total formatado (ex: '120.5 GB')."""
        return format_size(self.total)

    @property
    def used_formatted(self) -> str:
        """Usado formatado."""
        return format_size(self.used)

    @property
    def free_formatted(self) -> str:
        """Livre formatado."""
        return format_size(self.free)

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa métricas de disco.

        Returns:
            Dict com valores brutos e formatados
        """
        return {
            "path": self.path,
            "total": self.total,
            "total_formatted": self.total_formatted,
            "used": self.used,
            "used_formatted": self.used_formatted,
            "free": self.free,
            "free_formatted": self.free_formatted,
            "percent": round(self.percent, 1),
        }


@dataclass(slots=True)
class MemoryMetrics:
    """
    Métricas de memória.

    Attributes:
        total: Memória total em bytes
        available: Memória disponível em bytes
        used: Memória usada em bytes
        percent: Percentual de uso
        swap_total: Swap total em bytes
        swap_used: Swap usado em bytes
        swap_percent: Percentual de uso do swap
    """

    total: int
    available: int
    used: int
    percent: float
    swap_total: int = 0
    swap_used: int = 0
    swap_percent: float = 0.0

    @property
    def total_formatted(self) -> str:
        """Total formatado."""
        return format_size(self.total)

    @property
    def available_formatted(self) -> str:
        """Disponível formatado."""
        return format_size(self.available)

    @property
    def used_formatted(self) -> str:
        """Usado formatado."""
        return format_size(self.used)

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa métricas de memória.

        Returns:
            Dict com valores brutos e formatados
        """
        return {
            "total": self.total,
            "total_formatted": self.total_formatted,
            "available": self.available,
            "available_formatted": self.available_formatted,
            "used": self.used,
            "used_formatted": self.used_formatted,
            "percent": round(self.percent, 1),
            "swap_total": self.swap_total,
            "swap_used": self.swap_used,
            "swap_percent": round(self.swap_percent, 1),
        }


@dataclass(slots=True)
class CpuMetrics:
    """
    Métricas de CPU.

    Attributes:
        percent: Percentual de uso total
        count_logical: Número de CPUs lógicas
        count_physical: Número de CPUs físicas
        per_cpu: Percentual por CPU
        load_avg: Load average (1, 5, 15 min)
    """

    percent: float
    count_logical: int
    count_physical: int | None = None
    per_cpu: list[float] = field(default_factory=list)
    load_avg: tuple[float, float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa métricas de CPU.

        Returns:
            Dict com métricas da CPU
        """
        result: dict[str, Any] = {
            "percent": round(self.percent, 1),
            "count_logical": self.count_logical,
            "count_physical": self.count_physical,
            "per_cpu": [round(p, 1) for p in self.per_cpu],
        }
        if self.load_avg:
            result["load_avg"] = {
                "1min": round(self.load_avg[0], 2),
                "5min": round(self.load_avg[1], 2),
                "15min": round(self.load_avg[2], 2),
            }
        return result


@dataclass(slots=True)
class NetworkMetrics:
    """
    Métricas de rede.

    Attributes:
        bytes_sent: Total de bytes enviados
        bytes_recv: Total de bytes recebidos
        packets_sent: Total de pacotes enviados
        packets_recv: Total de pacotes recebidos
        hostname: Nome do host
        ip_address: Endereço IP principal
    """

    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    hostname: str = ""
    ip_address: str = ""

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa métricas de rede.

        Returns:
            Dict com tráfego e identificação
        """
        return {
            "bytes_sent": self.bytes_sent,
            "bytes_sent_formatted": format_size(self.bytes_sent),
            "bytes_recv": self.bytes_recv,
            "bytes_recv_formatted": format_size(self.bytes_recv),
            "packets_sent": self.packets_sent,
            "packets_recv": self.packets_recv,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
        }


@dataclass(slots=True)
class SystemInfo:
    """
    Informações gerais do sistema.

    Attributes:
        platform: Sistema operacional
        platform_release: Versão do SO
        platform_version: Versão completa
        architecture: Arquitetura (x86_64, etc)
        processor: Nome do processador
        python_version: Versão do Python
        boot_time: Tempo de boot do sistema
    """

    platform: str
    platform_release: str
    platform_version: str
    architecture: str
    processor: str
    python_version: str
    boot_time: datetime | None = None

    @property
    def uptime_seconds(self) -> float:
        """Uptime em segundos (0.0 se não disponível)."""
        if self.boot_time:
            return (datetime.now() - self.boot_time).total_seconds()
        return 0.0

    @property
    def uptime_formatted(self) -> str:
        """Uptime em formato amigável (ex: '2d 3h 10m')."""
        seconds = self.uptime_seconds
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)

        parts: list[str] = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")

        return " ".join(parts) if parts else "< 1m"

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa informações do sistema.

        Returns:
            Dict com informações gerais e uptime
        """
        return {
            "platform": self.platform,
            "platform_release": self.platform_release,
            "platform_version": self.platform_version,
            "architecture": self.architecture,
            "processor": self.processor,
            "python_version": self.python_version,
            "uptime_seconds": self.uptime_seconds,
            "uptime_formatted": self.uptime_formatted,
        }


@dataclass(slots=True)
class SystemMetrics:
    """
    Conjunto completo de métricas do sistema.

    Attributes:
        timestamp: Momento da coleta
        cpu: Métricas de CPU
        memory: Métricas de memória
        disks: Lista de métricas de disco
        network: Métricas de rede
        system: Informações do sistema
        alerts: Lista de alertas gerados
    """

    timestamp: datetime
    cpu: CpuMetrics
    memory: MemoryMetrics
    disks: list[DiskMetrics] = field(default_factory=list)
    network: NetworkMetrics | None = None
    system: SystemInfo | None = None
    alerts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa o pacote completo de métricas.

        Returns:
            Dict completo pronto para JSON
        """
        result: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "cpu": self.cpu.to_dict(),
            "memory": self.memory.to_dict(),
            "disks": [d.to_dict() for d in self.disks],
            "alerts": self.alerts,
        }
        if self.network:
            result["network"] = self.network.to_dict()
        if self.system:
            result["system"] = self.system.to_dict()
        return result


# =============================================================================
# Task
# =============================================================================


class MonitorTask(BaseTask):
    """
    Task para monitoramento do sistema.

    Coleta métricas de CPU, memória, disco e rede,
    gerando alertas quando thresholds são excedidos.
    """

    @property
    def name(self) -> str:
        """Nome interno da task."""
        return "monitor"

    @property
    def description(self) -> str:
        """Descrição curta da task."""
        return "Monitora recursos do sistema (CPU, memória, disco, rede)"

    def validate(self, **_kwargs: Any) -> tuple[bool, str]:
        """
        Valida pré-requisitos.

        Returns:
            (ok, mensagem)
        """
        if not PSUTIL_AVAILABLE:
            return (
                False,
                "Dependência 'psutil' não instalada. Instale com: pip install psutil",
            )
        return True, ""

    def execute(
        self,
        check_cpu: bool = True,
        check_memory: bool = True,
        check_disk: bool = True,
        check_network: bool = False,
        include_system_info: bool = False,
        disk_paths: list[str] | None = None,
        cpu_threshold: int | None = None,
        memory_threshold: int | None = None,
        disk_threshold: int | None = None,
        cpu_interval: float = 0.5,
    ) -> TaskResult:
        """
        Coleta métricas do sistema.

        Args:
            check_cpu: Se deve coletar métricas de CPU
            check_memory: Se deve coletar métricas de memória
            check_disk: Se deve coletar métricas de disco
            check_network: Se deve coletar métricas de rede
            include_system_info: Se deve incluir info do sistema
            disk_paths: Caminhos específicos para verificar disco
            cpu_threshold: Threshold de alerta para CPU (%)
            memory_threshold: Threshold de alerta para memória (%)
            disk_threshold: Threshold de alerta para disco (%)
            cpu_interval: Intervalo para medição de CPU (psutil.cpu_percent)

        Returns:
            TaskResult com as métricas coletadas
        """
        started_at = datetime.now()

        cpu_threshold_i = int(
            settings.monitor.cpu_threshold if cpu_threshold is None else cpu_threshold
        )
        memory_threshold_i = int(
            settings.monitor.memory_threshold
            if memory_threshold is None
            else memory_threshold
        )
        disk_threshold_i = int(
            settings.monitor.disk_threshold
            if disk_threshold is None
            else disk_threshold
        )

        try:
            alerts: list[str] = []

            cpu_metrics = (
                self._get_cpu_metrics(interval=cpu_interval)
                if check_cpu
                else CpuMetrics(percent=0.0, count_logical=0)
            )
            if check_cpu and cpu_metrics.percent > cpu_threshold_i:
                alerts.append(
                    f"⚠️ CPU alta: {cpu_metrics.percent:.1f}% (threshold: {cpu_threshold_i}%)"
                )

            memory_metrics = (
                self._get_memory_metrics()
                if check_memory
                else MemoryMetrics(total=0, available=0, used=0, percent=0.0)
            )
            if check_memory and memory_metrics.percent > memory_threshold_i:
                alerts.append(
                    f"⚠️ Memória alta: {memory_metrics.percent:.1f}% (threshold: {memory_threshold_i}%)"
                )

            disk_metrics: list[DiskMetrics] = []
            if check_disk:
                disk_metrics = self._get_disk_metrics(disk_paths)
                for disk in disk_metrics:
                    if disk.percent > disk_threshold_i:
                        alerts.append(
                            f"⚠️ Disco cheio ({disk.path}): {disk.percent:.1f}% (threshold: {disk_threshold_i}%)"
                        )

            network_metrics = self._get_network_metrics() if check_network else None
            system_info = self._get_system_info() if include_system_info else None

            metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu=cpu_metrics,
                memory=memory_metrics,
                disks=disk_metrics,
                network=network_metrics,
                system=system_info,
                alerts=alerts,
            )

            message = f"Monitoramento concluído - CPU: {cpu_metrics.percent:.1f}%, Memória: {memory_metrics.percent:.1f}%"
            if alerts:
                message += f" ({len(alerts)} alertas)"

            return TaskResult.success(
                message=message,
                data={
                    "metrics": metrics.to_dict(),
                    "has_alerts": len(alerts) > 0,
                    "alerts_count": len(alerts),
                },
                started_at=started_at,
            )

        except Exception as e:
            logger.exception("Erro ao coletar métricas: %s", e)
            return TaskResult.failure(
                message=f"Falha ao coletar métricas: {e}",
                error=e,
                started_at=started_at,
            )

    def _get_cpu_metrics(self, *, interval: float) -> CpuMetrics:
        """
        Coleta métricas de CPU.

        Args:
            interval: Intervalo para cpu_percent()

        Returns:
            CpuMetrics
        """
        assert psutil is not None

        cpu_percent = psutil.cpu_percent(interval=interval)
        per_cpu = psutil.cpu_percent(interval=None, percpu=True)

        try:
            load_avg = psutil.getloadavg()
        except Exception:
            load_avg = None

        logical = psutil.cpu_count(logical=True) or 1
        physical = psutil.cpu_count(logical=False)

        return CpuMetrics(
            percent=float(cpu_percent),
            count_logical=int(logical),
            count_physical=int(physical) if physical is not None else None,
            per_cpu=[float(x) for x in per_cpu],
            load_avg=load_avg,
        )

    def _get_memory_metrics(self) -> MemoryMetrics:
        """
        Coleta métricas de memória.

        Returns:
            MemoryMetrics
        """
        assert psutil is not None

        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return MemoryMetrics(
            total=int(mem.total),
            available=int(mem.available),
            used=int(mem.used),
            percent=float(mem.percent),
            swap_total=int(swap.total),
            swap_used=int(swap.used),
            swap_percent=float(swap.percent),
        )

    def _get_disk_metrics(self, paths: list[str] | None = None) -> list[DiskMetrics]:
        """
        Coleta métricas de disco.

        Args:
            paths: Lista de paths específicos para checar (opcional)

        Returns:
            Lista de DiskMetrics
        """
        assert psutil is not None

        disks: list[DiskMetrics] = []

        if paths:
            for path in paths:
                try:
                    usage = psutil.disk_usage(path)
                    disks.append(
                        DiskMetrics(
                            path=str(path),
                            total=int(usage.total),
                            used=int(usage.used),
                            free=int(usage.free),
                            percent=float(usage.percent),
                        )
                    )
                except (OSError, PermissionError):
                    logger.debug("Sem permissão/erro ao ler disco em: %s", path)

            return disks

        for partition in psutil.disk_partitions(all=False):
            mount = partition.mountpoint
            try:
                usage = psutil.disk_usage(mount)
                disks.append(
                    DiskMetrics(
                        path=str(mount),
                        total=int(usage.total),
                        used=int(usage.used),
                        free=int(usage.free),
                        percent=float(usage.percent),
                    )
                )
            except (OSError, PermissionError):
                logger.debug("Sem permissão/erro ao ler partição: %s", mount)

        return disks

    def _get_network_metrics(self) -> NetworkMetrics:
        """
        Coleta métricas de rede.

        Returns:
            NetworkMetrics
        """
        assert psutil is not None

        net = psutil.net_io_counters()

        hostname = socket.gethostname()
        ip_address = "127.0.0.1"
        with suppress(socket.gaierror):
            ip_address = socket.gethostbyname(hostname)

        return NetworkMetrics(
            bytes_sent=int(net.bytes_sent),
            bytes_recv=int(net.bytes_recv),
            packets_sent=int(net.packets_sent),
            packets_recv=int(net.packets_recv),
            hostname=hostname,
            ip_address=ip_address,
        )

    def _get_system_info(self) -> SystemInfo:
        """
        Coleta informações do sistema.

        Returns:
            SystemInfo
        """
        assert psutil is not None

        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
        except Exception:
            boot_time = None

        processor = platform.processor() or "Unknown"

        return SystemInfo(
            platform=platform.system(),
            platform_release=platform.release(),
            platform_version=platform.version(),
            architecture=platform.machine(),
            processor=processor,
            python_version=platform.python_version(),
            boot_time=boot_time,
        )

    def quick_check(self) -> dict[str, float]:
        """
        Verificação rápida das métricas principais.

        Returns:
            Dict com cpu_percent, memory_percent, disk_percent
        """
        if not PSUTIL_AVAILABLE:
            return {"cpu_percent": 0.0, "memory_percent": 0.0, "disk_percent": 0.0}

        assert psutil is not None

        root = "C:\\" if platform.system().lower().startswith("win") else "/"

        return {
            "cpu_percent": float(psutil.cpu_percent(interval=0.1)),
            "memory_percent": float(psutil.virtual_memory().percent),
            "disk_percent": float(psutil.disk_usage(root).percent),
        }


__all__ = [
    "DiskMetrics",
    "MemoryMetrics",
    "CpuMetrics",
    "NetworkMetrics",
    "SystemInfo",
    "SystemMetrics",
    "MonitorTask",
]
