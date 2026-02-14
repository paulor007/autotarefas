# Notificações por Email

O módulo de Email permite enviar notificações sobre o resultado das tarefas, alertas de monitoramento e relatórios automáticos.

## Início Rápido

```bash
# Testar configuração de email
autotarefas email test

# Enviar email manual
autotarefas email send --para destino@email.com --assunto "Teste" --mensagem "Olá!"

# Ver templates disponíveis
autotarefas email templates
```

## Configuração SMTP

### Variáveis de Ambiente

Crie ou edite o arquivo `.env` na raiz do projeto:

```bash
# .env

# === CONFIGURAÇÃO SMTP ===
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@gmail.com
SMTP_PASSWORD=sua-senha-de-app
SMTP_FROM=seu-email@gmail.com
SMTP_USE_TLS=true

# === NOTIFICAÇÕES ===
NOTIFY_EMAIL=destino@email.com
NOTIFY_ON_SUCCESS=false
NOTIFY_ON_FAILURE=true
```

### Configurações por Provedor

=== "Gmail"

    ```bash
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=seu-email@gmail.com
    SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx  # App Password
    SMTP_USE_TLS=true
    ```

    !!! warning "Gmail App Password"
        O Gmail requer uma **Senha de App**, não sua senha normal.

        1. Acesse [Conta Google > Segurança](https://myaccount.google.com/security)
        2. Ative a "Verificação em duas etapas"
        3. Em "Senhas de app", crie uma nova senha
        4. Use essa senha no `SMTP_PASSWORD`

=== "Outlook/Hotmail"

    ```bash
    SMTP_HOST=smtp.office365.com
    SMTP_PORT=587
    SMTP_USER=seu-email@outlook.com
    SMTP_PASSWORD=sua-senha
    SMTP_USE_TLS=true
    ```

=== "Yahoo"

    ```bash
    SMTP_HOST=smtp.mail.yahoo.com
    SMTP_PORT=587
    SMTP_USER=seu-email@yahoo.com
    SMTP_PASSWORD=senha-de-app
    SMTP_USE_TLS=true
    ```

=== "Servidor Próprio"

    ```bash
    SMTP_HOST=mail.seudominio.com
    SMTP_PORT=465
    SMTP_USER=usuario@seudominio.com
    SMTP_PASSWORD=senha
    SMTP_USE_TLS=false
    SMTP_USE_SSL=true
    ```

## Comandos CLI

### `email test`

Testa a configuração SMTP enviando um email de teste.

```bash
autotarefas email test [OPÇÕES]
```

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--para` | Email de destino | Usa `NOTIFY_EMAIL` |

**Exemplo:**

```bash
autotarefas email test --para meu-email@gmail.com
```

Saída:
```
Testando configuração de email...

  SMTP Host: smtp.gmail.com
  SMTP Port: 587
  From: seu-email@gmail.com
  To: meu-email@gmail.com

✓ Conexão estabelecida
✓ Autenticação bem-sucedida
✓ Email de teste enviado!

Verifique sua caixa de entrada (e spam).
```

### `email send`

Envia um email manualmente.

```bash
autotarefas email send [OPÇÕES]
```

| Opção | Descrição | Obrigatório |
|-------|-----------|-------------|
| `--para`, `-t` | Destinatário | Sim |
| `--assunto`, `-s` | Assunto do email | Sim |
| `--mensagem`, `-m` | Corpo do email | Sim |
| `--html` | Enviar como HTML | Não |
| `--anexo`, `-a` | Arquivo para anexar | Não |
| `--template` | Usar template | Não |

**Exemplos:**

```bash
# Email simples
autotarefas email send \
    --para destino@email.com \
    --assunto "Relatório Diário" \
    --mensagem "Backup concluído com sucesso!"

# Email HTML
autotarefas email send \
    --para destino@email.com \
    --assunto "Alerta" \
    --mensagem "<h1>Alerta</h1><p>CPU em 95%</p>" \
    --html

# Com anexo
autotarefas email send \
    --para destino@email.com \
    --assunto "Relatório" \
    --mensagem "Segue relatório em anexo" \
    --anexo ./relatorio.pdf

# Usando template
autotarefas email send \
    --para destino@email.com \
    --template notify \
    --assunto "Notificação"
```

### `email templates`

Lista os templates de email disponíveis.

```bash
autotarefas email templates
```

Saída:
```
╭─────────────────────────────────────────────────────────╮
│                 Templates Disponíveis                    │
├──────────────┬──────────────────────────────────────────┤
│ Nome         │ Descrição                                │
├──────────────┼──────────────────────────────────────────┤
│ base         │ Template base (header/footer)            │
│ notify       │ Notificação de tarefa                    │
│ report       │ Relatório formatado                      │
│ alert        │ Alerta de monitoramento                  │
╰──────────────┴──────────────────────────────────────────╯
```

## Uso via Python

### Configuração Básica

```python
from autotarefas.core import EmailSender

# Usar configurações do .env
email = EmailSender()

# Ou configurar manualmente
email = EmailSender(
    host="smtp.gmail.com",
    port=587,
    username="seu-email@gmail.com",
    password="sua-senha-de-app",
    use_tls=True
)
```

### Enviar Email Simples

```python
from autotarefas.core import EmailSender

email = EmailSender()

result = email.send(
    to="destino@email.com",
    subject="Assunto do Email",
    body="Corpo do email em texto simples"
)

if result.success:
    print("✓ Email enviado!")
else:
    print(f"✗ Erro: {result.error}")
```

### Enviar Email HTML

```python
email.send(
    to="destino@email.com",
    subject="Email HTML",
    body="""
    <html>
    <body>
        <h1>Relatório</h1>
        <p>Backup concluído com <strong>sucesso</strong>!</p>
        <ul>
            <li>Arquivos: 1,234</li>
            <li>Tamanho: 456 MB</li>
        </ul>
    </body>
    </html>
    """,
    html=True
)
```

### Usar Templates Jinja2

```python
from autotarefas.core import EmailSender

email = EmailSender()

# Enviar com template
email.send_template(
    to="destino@email.com",
    subject="Backup Concluído",
    template="notify",
    context={
        "task_name": "Backup Diário",
        "status": "success",
        "duration": "2m 34s",
        "details": {
            "files_count": 1234,
            "total_size": "456 MB"
        }
    }
)
```

### Enviar com Anexos

```python
email.send(
    to="destino@email.com",
    subject="Relatório com Anexo",
    body="Segue o relatório em anexo.",
    attachments=[
        "/path/to/relatorio.pdf",
        "/path/to/dados.xlsx"
    ]
)
```

### Múltiplos Destinatários

```python
# Lista de destinatários
email.send(
    to=["usuario1@email.com", "usuario2@email.com"],
    subject="Alerta do Sistema",
    body="CPU em nível crítico!"
)

# Com CC e BCC
email.send(
    to="principal@email.com",
    cc=["copia1@email.com", "copia2@email.com"],
    bcc="oculto@email.com",
    subject="Relatório",
    body="..."
)
```

## Integração com Tarefas

### Notificação Automática

```python
from autotarefas.tasks import BackupTask
from autotarefas.core import EmailSender, Notifier

email = EmailSender()
notifier = Notifier(email_sender=email)

# Tarefa com notificação automática
backup = BackupTask(
    source="/dados",
    destination="/backup",
    notifier=notifier,
    notify_on_success=True,
    notify_on_failure=True,
    notify_email="admin@empresa.com"
)

result = backup.run()
# Email enviado automaticamente baseado no resultado
```

### Callback Personalizado

```python
from autotarefas.tasks import MonitorTask
from autotarefas.core import EmailSender

email = EmailSender()

def send_alert(metric, value, threshold):
    email.send(
        to="admin@empresa.com",
        subject=f"[ALERTA] {metric.upper()} em {value}%",
        body=f"""
        <h2>Alerta de Sistema</h2>
        <p>O <strong>{metric}</strong> ultrapassou o limite configurado.</p>
        <ul>
            <li>Valor atual: {value}%</li>
            <li>Limite: {threshold}%</li>
        </ul>
        """,
        html=True
    )

monitor = MonitorTask(
    cpu_threshold=80,
    memory_threshold=90,
    on_alert=send_alert
)
```

### Relatório por Email

```python
from autotarefas.tasks import ReporterTask
from autotarefas.core import EmailSender

email = EmailSender()

# Gerar relatório
reporter = ReporterTask(
    report_type="backup_summary",
    period="weekly"
)
result = reporter.run()

# Enviar por email
if result.success:
    email.send(
        to="gerente@empresa.com",
        subject="Relatório Semanal de Backups",
        body="Segue o relatório em anexo.",
        attachments=[result.data['report_file']]
    )
```

## Templates

### Estrutura de Templates

Os templates ficam em `src/autotarefas/resources/templates/email/`:

```
templates/email/
├── base.html       # Template base
├── notify.html     # Notificações
├── report.html     # Relatórios
└── alert.html      # Alertas
```

### Template Base (base.html)

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .header { background: #1e2a5e; color: white; padding: 20px; }
        .content { padding: 20px; }
        .footer { background: #f5f5f5; padding: 10px; font-size: 12px; }
        .success { color: #27ae60; }
        .error { color: #e74c3c; }
    </style>
</head>
<body>
    <div class="header">
        <h1>AutoTarefas</h1>
    </div>
    <div class="content">
        {% block content %}{% endblock %}
    </div>
    <div class="footer">
        <p>Enviado automaticamente por AutoTarefas</p>
    </div>
</body>
</html>
```

### Template de Notificação (notify.html)

```html
{% extends "base.html" %}

{% block content %}
<h2>{{ task_name }}</h2>

{% if status == 'success' %}
<p class="success">✓ Tarefa concluída com sucesso!</p>
{% else %}
<p class="error">✗ Tarefa falhou</p>
{% endif %}

<table>
    <tr><td><strong>Duração:</strong></td><td>{{ duration }}</td></tr>
    {% for key, value in details.items() %}
    <tr><td><strong>{{ key }}:</strong></td><td>{{ value }}</td></tr>
    {% endfor %}
</table>
{% endblock %}
```

### Criar Template Personalizado

```python
# Registrar template personalizado
from autotarefas.core import EmailSender

email = EmailSender()

# Adicionar template inline
email.register_template(
    name="meu_template",
    content="""
    <h1>{{ titulo }}</h1>
    <p>{{ mensagem }}</p>
    """
)

# Usar template
email.send_template(
    to="destino@email.com",
    template="meu_template",
    context={"titulo": "Olá", "mensagem": "Mundo!"}
)
```

## Configuração Avançada

### Arquivo de Configuração

```json
{
  "email": {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "seu-email@gmail.com",
    "smtp_password": "sua-senha",
    "smtp_from": "AutoTarefas <seu-email@gmail.com>",
    "use_tls": true,
    "templates_dir": "templates/email",
    "default_template": "notify"
  },
  "notifications": {
    "default_recipient": "admin@empresa.com",
    "on_success": false,
    "on_failure": true,
    "include_logs": true,
    "max_log_lines": 50
  }
}
```

### Rate Limiting

Para evitar enviar muitos emails:

```python
email = EmailSender(
    rate_limit=10,          # máx 10 emails
    rate_limit_period=60    # por minuto
)
```

### Retry

```python
email = EmailSender(
    max_retries=3,
    retry_delay=30  # segundos
)
```

## Boas Práticas

!!! tip "Dicas"
    1. **Use App Passwords** para Gmail/Outlook
    2. **Teste a configuração** antes de usar em produção
    3. **Não envie em excesso** - configure rate limiting
    4. **Use templates** para emails consistentes
    5. **Inclua logs resumidos**, não completos
    6. **Configure fallback** para falhas de envio

!!! warning "Segurança"
    - **Nunca** commite senhas no código
    - Use variáveis de ambiente ou secrets manager
    - Revogue senhas de app se comprometidas
    - Use TLS/SSL sempre que possível

## Troubleshooting

### Erro: "Authentication failed"

```bash
# Verificar credenciais
autotarefas email test

# Para Gmail, criar App Password
# Para outros, verificar se a conta permite SMTP
```

### Erro: "Connection refused"

```bash
# Verificar host e porta
telnet smtp.gmail.com 587

# Verificar firewall
sudo ufw status
```

### Email vai para spam

- Adicione SPF/DKIM no seu domínio
- Use um endereço "From" válido
- Evite palavras de spam no assunto
- Inclua link de descadastro

### Email não chega

```bash
# Verificar se foi enviado
autotarefas email test --verbose

# Verificar pasta de spam
# Verificar logs do servidor SMTP
```

## Próximos Passos

- [Configurar alertas de monitoramento](monitor.md)
- [Agendar envio de relatórios](scheduler.md)
- [Integrar com backup](backup.md)
