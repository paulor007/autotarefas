# Monitoramento do Sistema

O módulo Monitor permite acompanhar o uso de CPU, memória, disco e rede em tempo real, com alertas configuráveis.

## Início Rápido

```bash
# Ver status atual
autotarefas monitor status

# Monitoramento contínuo
autotarefas monitor watch

# Monitoramento com alertas
autotarefas monitor watch --cpu 80 --memoria 90
```

## Comandos CLI

### `monitor status`

Mostra o status atual do sistema em um snapshot.

```bash
autotarefas monitor status [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--json` | Saída em formato JSON | `False` |
| `--detalhes`, `-v` | Mostrar informações detalhadas | `False` |

**Exemplo:**

```bash
autotarefas monitor status
```

Saída:
```
╭─────────────────────────────────────────────────────────╮
│                  Status do Sistema                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  CPU:      23.5%   ████████░░░░░░░░░░░░░░░░░░░░░░░░     │
│  Memória:  67.2%   ████████████████████░░░░░░░░░░░░     │
│  Disco:    45.0%   █████████████░░░░░░░░░░░░░░░░░░░     │
│  Swap:     12.3%   ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░     │
│                                                          │
│  Uptime: 5 dias, 3 horas                                │
│  Processos: 234 (5 em execução)                         │
│                                                          │
╰─────────────────────────────────────────────────────────╯
```

### `monitor watch`

Monitoramento contínuo em tempo real.

```bash
autotarefas monitor watch [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--intervalo`, `-i` | Intervalo em segundos | `5` |
| `--cpu` | Limite de alerta para CPU (%) | `None` |
| `--memoria` | Limite de alerta para memória (%) | `None` |
| `--disco` | Limite de alerta para disco (%) | `None` |
| `--notificar` | Enviar email quando alertar | `False` |

**Exemplos:**

```bash
# Monitoramento simples
autotarefas monitor watch

# Com alertas
autotarefas monitor watch --cpu 80 --memoria 90 --disco 85

# Intervalo de 10 segundos
autotarefas monitor watch -i 10

# Com notificação por email
autotarefas monitor watch --cpu 80 --notificar
```

### `monitor alerts`

Configura alertas permanentes.

```bash
autotarefas monitor alerts [OPÇÕES]
```

| Opção | Descrição |
|-------|-----------|
| `--cpu` | Limite para CPU |
| `--memoria` | Limite para memória |
| `--disco` | Limite para disco |
| `--email` | Email para notificações |
| `--listar` | Listar alertas configurados |
| `--limpar` | Remover todos os alertas |

**Exemplos:**

```bash
# Configurar alertas
autotarefas monitor alerts --cpu 80 --memoria 90 --disco 85

# Adicionar email para notificações
autotarefas monitor alerts --email admin@empresa.com

# Ver alertas configurados
autotarefas monitor alerts --listar
```

### `monitor history`

Mostra histórico de métricas coletadas.

```bash
autotarefas monitor history [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--ultimas` | Período (ex: `24h`, `7d`) | `24h` |
| `--metrica` | Métrica específica | `all` |
| `--formato` | Formato de saída | `table` |

**Exemplos:**

```bash
# Últimas 24 horas
autotarefas monitor history

# Última semana
autotarefas monitor history --ultimas 7d

# Apenas CPU
autotarefas monitor history --metrica cpu

# Exportar para CSV
autotarefas monitor history --formato csv > metricas.csv
```

### `monitor processes`

Lista os processos que mais consomem recursos.

```bash
autotarefas monitor processes [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--limite`, `-n` | Número de processos | `10` |
| `--ordenar` | Ordenar por: `cpu`, `memoria` | `cpu` |

**Exemplo:**

```bash
autotarefas monitor processes --limite 5 --ordenar memoria
```

Saída:
```
╭─────────────────────────────────────────────────────────╮
│             Top 5 Processos (por Memória)                │
├─────────┬────────────────────┬─────────┬────────────────┤
│ PID     │ Nome               │ CPU %   │ Memória        │
├─────────┼────────────────────┼─────────┼────────────────┤
│ 1234    │ chrome             │ 12.3%   │ 1.2 GB         │
│ 5678    │ code               │ 8.5%    │ 890 MB         │
│ 9012    │ python             │ 2.1%    │ 456 MB         │
│ 3456    │ spotify            │ 1.8%    │ 320 MB         │
│ 7890    │ slack              │ 0.5%    │ 280 MB         │
╰─────────┴────────────────────┴─────────┴────────────────╯
```

## Uso via Python

### Monitoramento Básico

```python
from autotarefas.tasks import MonitorTask

monitor = MonitorTask()
result = monitor.run()

if result.success:
    data = result.data
    print(f"CPU: {data['cpu']}%")
    print(f"Memória: {data['memory']}%")
    print(f"Disco: {data['disk']}%")
```

### Com Limites de Alerta

```python
from autotarefas.tasks import MonitorTask

monitor = MonitorTask(
    cpu_threshold=80,
    memory_threshold=90,
    disk_threshold=85
)

result = monitor.run()

if result.data.get('alerts'):
    print("⚠️ ALERTAS:")
    for alert in result.data['alerts']:
        print(f"  - {alert['metric']}: {alert['value']}% (limite: {alert['threshold']}%)")
```

### Monitorar Discos Específicos

```python
from autotarefas.tasks import MonitorTask

monitor = MonitorTask(
    disk_paths=["/", "/home", "/var"],
    disk_threshold=85
)

result = monitor.run()

for disk in result.data['disks']:
    print(f"{disk['mountpoint']}: {disk['percent']}% usado")
    print(f"  Livre: {disk['free']} / Total: {disk['total']}")
```

### Monitorar Rede

```python
from autotarefas.tasks import MonitorTask

monitor = MonitorTask(
    network=True
)

result = monitor.run()

net = result.data['network']
print(f"Enviado: {net['bytes_sent']}")
print(f"Recebido: {net['bytes_recv']}")
print(f"Pacotes enviados: {net['packets_sent']}")
print(f"Pacotes recebidos: {net['packets_recv']}")
```

### Callback de Alerta

```python
from autotarefas.tasks import MonitorTask

def on_alert(metric, value, threshold):
    print(f"🚨 ALERTA: {metric} está em {value}% (limite: {threshold}%)")
    # Enviar notificação, SMS, etc.

monitor = MonitorTask(
    cpu_threshold=80,
    memory_threshold=90,
    on_alert=on_alert
)

# Monitoramento contínuo
monitor.watch(interval=5)  # Verifica a cada 5 segundos
```

### Monitoramento Contínuo com Histórico

```python
from autotarefas.tasks import MonitorTask
import time

monitor = MonitorTask(
    cpu_threshold=80,
    memory_threshold=90,
    save_history=True,
    history_file="metrics.json"
)

# Loop de monitoramento
try:
    while True:
        result = monitor.run()
        print(f"[{result.timestamp}] CPU: {result.data['cpu']}%")
        time.sleep(5)
except KeyboardInterrupt:
    print("\nMonitoramento encerrado")
```

### Exportar Métricas

```python
from autotarefas.tasks import MonitorTask

monitor = MonitorTask()

# Coletar métricas
metrics = []
for _ in range(10):
    result = monitor.run()
    metrics.append(result.data)
    time.sleep(1)

# Exportar para DataFrame
import pandas as pd
df = pd.DataFrame(metrics)
df.to_csv("metricas.csv", index=False)
```

## Agendamento

### Verificação a Cada 5 Minutos

```bash
autotarefas schedule add monitor \
    --intervalo 5m \
    --cpu 80 \
    --memoria 90 \
    --notificar
```

### Relatório Diário

```bash
autotarefas schedule add monitor \
    --cron "0 8 * * *" \
    --relatorio \
    --email admin@empresa.com
```

### Via Python

```python
from autotarefas.core import TaskScheduler
from autotarefas.tasks import MonitorTask

scheduler = TaskScheduler()

monitor = MonitorTask(
    cpu_threshold=80,
    memory_threshold=90,
    disk_threshold=85
)

# Verificar a cada 5 minutos
scheduler.add_interval(monitor, minutes=5, name="monitor_sistema")

scheduler.run()
```

## Configuração

### Variáveis de Ambiente

```bash
# .env
MONITOR_CPU_THRESHOLD=80
MONITOR_MEMORY_THRESHOLD=90
MONITOR_DISK_THRESHOLD=85
MONITOR_INTERVAL_SECONDS=60
MONITOR_ALERT_EMAIL=admin@empresa.com
MONITOR_ALERT_COOLDOWN_MINUTES=15
```

### Arquivo de Configuração

```json
{
  "monitor": {
    "cpu_threshold": 80,
    "memory_threshold": 90,
    "disk_threshold": 85,
    "disk_paths": ["/", "/home"],
    "interval_seconds": 60,
    "network": true,
    "processes": true,
    "save_history": true,
    "history_retention_days": 30,
    "alert_cooldown_minutes": 15
  }
}
```

## Métricas Disponíveis

### CPU

| Métrica | Descrição |
|---------|-----------|
| `cpu_percent` | Uso total de CPU (%) |
| `cpu_count` | Número de núcleos |
| `cpu_freq` | Frequência atual (MHz) |
| `load_avg` | Carga média (1, 5, 15 min) |

### Memória

| Métrica | Descrição |
|---------|-----------|
| `memory_percent` | Uso de memória RAM (%) |
| `memory_total` | Total de RAM |
| `memory_available` | RAM disponível |
| `memory_used` | RAM em uso |
| `swap_percent` | Uso de swap (%) |

### Disco

| Métrica | Descrição |
|---------|-----------|
| `disk_percent` | Uso do disco (%) |
| `disk_total` | Tamanho total |
| `disk_used` | Espaço usado |
| `disk_free` | Espaço livre |
| `disk_read` | Bytes lidos |
| `disk_write` | Bytes escritos |

### Rede

| Métrica | Descrição |
|---------|-----------|
| `bytes_sent` | Total enviado |
| `bytes_recv` | Total recebido |
| `packets_sent` | Pacotes enviados |
| `packets_recv` | Pacotes recebidos |
| `errors_in` | Erros de entrada |
| `errors_out` | Erros de saída |

## Alertas

### Níveis de Alerta

| Nível | Cor | Descrição |
|-------|-----|-----------|
| Normal | 🟢 Verde | Abaixo de 60% |
| Atenção | 🟡 Amarelo | Entre 60% e 80% |
| Alerta | 🟠 Laranja | Entre 80% e 90% |
| Crítico | 🔴 Vermelho | Acima de 90% |

### Cooldown de Alertas

Para evitar spam de notificações, o sistema aguarda um tempo entre alertas da mesma métrica:

```python
monitor = MonitorTask(
    cpu_threshold=80,
    alert_cooldown_minutes=15  # Aguarda 15 min entre alertas
)
```

## Integração com Notificações

### Email

```python
from autotarefas.tasks import MonitorTask
from autotarefas.core import EmailSender

email = EmailSender()

def send_alert(metric, value, threshold):
    email.send(
        to="admin@empresa.com",
        subject=f"[ALERTA] {metric} em {value}%",
        body=f"O {metric} ultrapassou o limite de {threshold}%"
    )

monitor = MonitorTask(
    cpu_threshold=80,
    on_alert=send_alert
)
```

## Boas Práticas

!!! tip "Dicas"
    1. **Configure alertas** para métricas críticas
    2. **Use cooldown** para evitar muitas notificações
    3. **Monitore discos** específicos, não apenas `/`
    4. **Salve histórico** para análise posterior
    5. **Integre com email** para alertas em produção

!!! warning "Atenção"
    - Intervalos muito curtos podem impactar performance
    - Monitore o próprio uso de recursos do monitor
    - Alertas frequentes podem indicar necessidade de upgrade

## Troubleshooting

### Erro: "Permissão negada ao acessar /proc"

```bash
# Verificar se está rodando como root (necessário para algumas métricas)
sudo autotarefas monitor status
```

### Métricas de disco incorretas

```bash
# Verificar montagens
df -h

# Especificar disco correto
autotarefas monitor status --disco /dev/sda1
```

### Alto uso de CPU pelo próprio monitor

```python
# Aumentar intervalo
monitor = MonitorTask(interval_seconds=60)  # 1 minuto ao invés de 5 segundos
```

## Próximos Passos

- [Agendar monitoramento](scheduler.md)
- [Configurar alertas por email](email.md)
- [Limpar arquivos quando disco estiver cheio](cleaner.md)
