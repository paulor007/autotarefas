#!/usr/bin/env python3
"""
Exemplo de uso do módulo Scheduler do AutoTarefas.

Este script demonstra como usar a API de agendamento programaticamente.

Uso:
    python scheduler_example.py
"""

from datetime import datetime, timedelta

from autotarefas.core.scheduler import (
    ScheduleType,
    TaskRegistry,
    get_scheduler,
    reset_scheduler,
)


def exemplo_registrar_tasks():
    """Exemplo de registro de tasks no TaskRegistry."""
    print("=" * 50)
    print("Exemplo 1: Tasks Registradas")
    print("=" * 50)

    registry = TaskRegistry()

    # Listar tasks disponíveis (retorna lista de nomes)
    task_names = registry.list_tasks()

    print(f"\n📦 {len(task_names)} task(s) registrada(s):\n")
    for name in task_names:
        task_class = registry.get(name)
        if task_class:
            print(f"  • {name}")
            # Tentar obter descrição da classe
            desc = getattr(task_class, "description", "Sem descrição")
            if callable(desc):
                desc = "Task registrada"
            print(f"    Descrição: {str(desc)[:50]}...")
        print()


def exemplo_adicionar_job():
    """Exemplo de adição de jobs."""
    print("\n" + "=" * 50)
    print("Exemplo 2: Adicionar Jobs")
    print("=" * 50)

    scheduler = get_scheduler()

    # Job diário às 2h
    job = scheduler.add_job(
        name="backup-diario",
        task="backup",
        schedule="02:00",
        schedule_type=ScheduleType.DAILY,
        params={
            "source": "/home/user/documents",
            "destination": "/backups",
            "compression": "zip",
        },
    )
    print(f"\n✅ Job criado: backup-diario (ID: {job.job_id})")

    # Job por intervalo (a cada 1 hora = 3600 segundos)
    job2 = scheduler.add_job(
        name="monitor-hourly",
        task="monitor",
        schedule="3600",
        schedule_type=ScheduleType.INTERVAL,
        params={"include_cpu": True, "include_memory": True, "include_disk": True},
    )
    print(f"✅ Job criado: monitor-hourly (ID: {job2.job_id})")

    # Job cron (todo domingo às 3h)
    job3 = scheduler.add_job(
        name="limpeza-semanal",
        task="cleaner",
        schedule="0 3 * * 0",
        schedule_type=ScheduleType.CRON,
        params={"paths": ["/tmp"], "profile": "temp_files"},
    )
    print(f"✅ Job criado: limpeza-semanal (ID: {job3.job_id})")

    return scheduler


def exemplo_listar_jobs():
    """Exemplo de listagem de jobs."""
    print("\n" + "=" * 50)
    print("Exemplo 3: Listar Jobs")
    print("=" * 50)

    scheduler = get_scheduler()
    jobs = scheduler.list_jobs()

    print(f"\n📋 {len(jobs)} job(s) agendado(s):\n")
    for job in jobs:
        print(f"  📌 {job.job_name}")
        print(f"     Task: {job.task_name}")
        print(f"     Schedule: {job.schedule} ({job.schedule_type})")
        print(f"     Habilitado: {'✅' if job.enabled else '❌'}")
        print(f"     Próxima execução: {job.next_run or 'N/A'}")
        print()


def exemplo_executar_job():
    """Exemplo de execução manual de job."""
    print("\n" + "=" * 50)
    print("Exemplo 4: Executar Job Manualmente")
    print("=" * 50)

    scheduler = get_scheduler()

    # Buscar job pelo nome
    job = scheduler.get_job_by_name("monitor-hourly")

    if job:
        # Executar job manualmente
        success = scheduler.run_job(job.job_id)

        print(f"\n{'✅' if success else '❌'} Job executado!")
        print(f"   Sucesso: {success}")
        print(f"   Execuções: {job.run_count}")
    else:
        print("❌ Job não encontrado")

    return job


def exemplo_pausar_resumir():
    """Exemplo de pause/resume de jobs."""
    print("\n" + "=" * 50)
    print("Exemplo 5: Pausar e Resumir Jobs")
    print("=" * 50)

    scheduler = get_scheduler()

    # Buscar job pelo nome
    job = scheduler.get_job_by_name("backup-diario")

    if job:
        # Pausar job
        scheduler.disable_job(job.job_id)
        print("\n⏸️  Job 'backup-diario' pausado")

        # Verificar status
        job_updated = scheduler.get_job(job.job_id)
        if job_updated:
            print(f"   Habilitado: {job_updated.enabled}")

        # Resumir job
        scheduler.enable_job(job.job_id)
        print("\n▶️  Job 'backup-diario' resumido")

        job_final = scheduler.get_job(job.job_id)
        if job_final:
            print(f"   Habilitado: {job_final.enabled}")


def exemplo_remover_job():
    """Exemplo de remoção de job."""
    print("\n" + "=" * 50)
    print("Exemplo 6: Remover Job")
    print("=" * 50)

    scheduler = get_scheduler()

    # Buscar job pelo nome
    job = scheduler.get_job_by_name("limpeza-semanal")

    if job:
        # Remover job
        removed = scheduler.remove_job(job.job_id)

        if removed:
            print("\n🗑️  Job 'limpeza-semanal' removido")
        else:
            print("\n❌ Erro ao remover job")
    else:
        print("\n❌ Job não encontrado")

    # Listar jobs restantes
    jobs = scheduler.list_jobs()
    print(f"\n   Jobs restantes: {len(jobs)}")


def exemplo_status_scheduler():
    """Exemplo de verificação de status do scheduler."""
    print("\n" + "=" * 50)
    print("Exemplo 7: Status do Scheduler")
    print("=" * 50)

    scheduler = get_scheduler()
    status = scheduler.get_status()

    print("\n📊 Status do Scheduler:\n")
    print(f"   Estado: {status.get('state', 'N/A')}")
    print(f"   Total de jobs: {status.get('total_jobs', 0)}")
    print(f"   Jobs habilitados: {status.get('enabled_jobs', 0)}")
    print(f"   Próximo job: {status.get('next_job', 'N/A')}")
    print(f"   Próxima execução: {status.get('next_run', 'N/A')}")


def exemplo_job_unico():
    """Exemplo de job que executa uma única vez."""
    print("\n" + "=" * 50)
    print("Exemplo 8: Job Único (Once)")
    print("=" * 50)

    scheduler = get_scheduler()

    # Agendar para daqui 1 minuto
    run_at = datetime.now() + timedelta(minutes=1)

    job = scheduler.add_job(
        name="backup-unico",
        task="backup",
        schedule=run_at.isoformat(),
        schedule_type=ScheduleType.ONCE,
        params={"source": "/important/data", "destination": "/backups"},
    )

    print("\n✅ Job único criado: backup-unico")
    print(f"   Execução em: {run_at.strftime('%H:%M:%S')}")
    print("   (Este job será desabilitado após executar)")

    return job


def exemplo_ciclo_completo():
    """Exemplo de ciclo completo de uso do scheduler."""
    print("\n" + "=" * 50)
    print("Exemplo 9: Ciclo Completo")
    print("=" * 50)

    # Resetar para começar limpo
    reset_scheduler()
    scheduler = get_scheduler()

    print("\n1️⃣  Criando jobs...")
    scheduler.add_job("job1", "monitor", "60", ScheduleType.INTERVAL)
    scheduler.add_job("job2", "backup", "03:00", ScheduleType.DAILY)
    print(f"   {len(scheduler.list_jobs())} jobs criados")

    print("\n2️⃣  Verificando status...")
    status = scheduler.get_status()
    print(f"   Total jobs: {status.get('total_jobs', 0)}")

    print("\n3️⃣  Executando job manualmente...")
    job = scheduler.get_job_by_name("job1")
    if job:
        success = scheduler.run_job(job.job_id)
        print(f"   Resultado: {'sucesso' if success else 'falha'}")

    print("\n4️⃣  Status final:")
    status = scheduler.get_status()
    print(f"   Estado: {status.get('state', 'N/A')}")
    print(f"   Jobs: {status.get('total_jobs', 0)}")

    print("\n✅ Ciclo completo finalizado!")


if __name__ == "__main__":
    print("\n⏰ Exemplos de Scheduler do AutoTarefas\n")

    try:
        # Resetar scheduler para exemplos limpos
        reset_scheduler()

        # Executar exemplos
        exemplo_registrar_tasks()
        exemplo_adicionar_job()
        exemplo_listar_jobs()
        exemplo_executar_job()
        exemplo_pausar_resumir()
        exemplo_status_scheduler()
        exemplo_remover_job()

        # Limpar
        reset_scheduler()

        print("\n" + "=" * 50)
        print("✅ Exemplos concluídos!")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback

        traceback.print_exc()
