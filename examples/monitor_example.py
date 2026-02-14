#!/usr/bin/env python3
"""
Exemplo de uso do módulo de Monitoramento do AutoTarefas.

Este script demonstra como usar a API de monitoramento programaticamente.

Uso:
    python monitor_example.py
"""

from autotarefas.tasks.monitor import MonitorTask


def exemplo_monitoramento_basico():
    """Exemplo básico de monitoramento."""
    print("=" * 50)
    print("Exemplo 1: Monitoramento Básico")
    print("=" * 50)

    task = MonitorTask()

    result = task.run()

    if result.is_success:
        metrics = result.data

        print("\n📊 Métricas do Sistema:\n")

        # CPU
        if "cpu" in metrics:
            cpu = metrics["cpu"]
            print(f"  CPU: {cpu['percent']}%")
            print(f"    Cores: {cpu.get('cores', 'N/A')}")

        # Memória
        if "memory" in metrics:
            mem = metrics["memory"]
            print(f"\n  Memória: {mem['percent']}%")
            print(f"    Usada: {mem.get('used_formatted', 'N/A')}")
            print(f"    Total: {mem.get('total_formatted', 'N/A')}")

        # Disco
        if "disks" in metrics:
            print("\n  Discos:")
            for disk in metrics["disks"]:
                print(f"    {disk['path']}: {disk['percent']}% usado")
                print(f"      Livre: {disk.get('free_formatted', 'N/A')}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_monitoramento_completo():
    """Exemplo de monitoramento com todas as métricas."""
    print("\n" + "=" * 50)
    print("Exemplo 2: Monitoramento Completo")
    print("=" * 50)

    task = MonitorTask()

    result = task.run(
        include_cpu=True,
        include_memory=True,
        include_disk=True,
        include_network=True,
        include_system=True,
    )

    if result.is_success:
        metrics = result.data

        # Sistema
        if "system" in metrics:
            sys = metrics["system"]
            print("\n🖥️  Sistema:")
            print(f"    Plataforma: {sys.get('platform', 'N/A')}")
            print(f"    Hostname: {sys.get('hostname', 'N/A')}")
            print(f"    Uptime: {sys.get('uptime_formatted', 'N/A')}")

        # Rede
        if "network" in metrics:
            net = metrics["network"]
            print("\n🌐 Rede:")
            print(f"    Enviado: {net.get('bytes_sent_formatted', 'N/A')}")
            print(f"    Recebido: {net.get('bytes_recv_formatted', 'N/A')}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_monitoramento_com_alertas():
    """Exemplo de monitoramento com thresholds de alerta."""
    print("\n" + "=" * 50)
    print("Exemplo 3: Monitoramento com Alertas")
    print("=" * 50)

    task = MonitorTask()

    # Definir thresholds baixos para demonstração
    result = task.run(
        include_cpu=True,
        include_memory=True,
        include_disk=True,
        cpu_threshold=50,  # Alerta se CPU > 50%
        memory_threshold=50,  # Alerta se memória > 50%
        disk_threshold=70,  # Alerta se disco > 70%
    )

    if result.is_success:
        metrics = result.data

        # Verificar alertas
        alerts = metrics.get("alerts", [])

        if alerts:
            print(f"\n⚠️  {len(alerts)} Alerta(s) encontrado(s):\n")
            for alert in alerts:
                print(f"  • {alert}")
        else:
            print("\n✅ Nenhum alerta - sistema saudável!")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_monitoramento_disco_especifico():
    """Exemplo de monitoramento de disco específico."""
    print("\n" + "=" * 50)
    print("Exemplo 4: Monitoramento de Disco Específico")
    print("=" * 50)

    task = MonitorTask()

    # Monitorar apenas discos específicos
    result = task.run(
        include_cpu=False,
        include_memory=False,
        include_disk=True,
        disk_paths=["/", "/home"],  # Linux
        # disk_paths=["C:\\", "D:\\"]  # Windows
    )

    if result.is_success:
        metrics = result.data

        print("\n💾 Discos monitorados:")
        for disk in metrics.get("disks", []):
            print(f"\n  {disk['path']}:")
            print(f"    Usado: {disk['percent']}%")
            print(f"    Livre: {disk.get('free_formatted', 'N/A')}")
            print(f"    Total: {disk.get('total_formatted', 'N/A')}")
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_saida_json():
    """Exemplo de saída em formato JSON."""
    print("\n" + "=" * 50)
    print("Exemplo 5: Saída JSON")
    print("=" * 50)

    import json

    task = MonitorTask()
    result = task.run()

    if result.is_success:
        # Converter para JSON formatado
        json_output = json.dumps(result.data, indent=2, default=str)
        print(f"\n{json_output[:500]}...")  # Primeiros 500 caracteres
    else:
        print(f"❌ Erro: {result.error}")

    return result


def exemplo_monitoramento_continuo():
    """Exemplo de monitoramento contínuo (loop)."""
    print("\n" + "=" * 50)
    print("Exemplo 6: Monitoramento Contínuo (3 iterações)")
    print("=" * 50)

    import time

    task = MonitorTask()

    for i in range(3):
        print(f"\n--- Iteração {i + 1} ---")

        result = task.run(include_cpu=True, include_memory=True)

        if result.is_success:
            cpu = result.data.get("cpu", {}).get("percent", "N/A")
            mem = result.data.get("memory", {}).get("percent", "N/A")
            print(f"  CPU: {cpu}% | Memória: {mem}%")

        if i < 2:  # Não esperar na última iteração
            time.sleep(2)

    print("\n✅ Monitoramento contínuo concluído!")


if __name__ == "__main__":
    print("\n📊 Exemplos de Monitor do AutoTarefas\n")

    try:
        # Executar exemplos
        exemplo_monitoramento_basico()
        exemplo_monitoramento_completo()
        exemplo_monitoramento_com_alertas()
        exemplo_saida_json()

        print("\n" + "=" * 50)
        print("✅ Exemplos concluídos!")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback

        traceback.print_exc()
