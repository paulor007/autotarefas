# AutoTarefas

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/code%20style-ruff-000000.svg" alt="Code style: ruff">
  <img src="https://img.shields.io/badge/tests-986%20passed-success.svg" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-98%25-brightgreen.svg" alt="Coverage">
  <img src="https://img.shields.io/badge/version-1.0.0-blue.svg" alt="Version">
</p>

<p align="center">
  <b>Sistema completo de automação de tarefas para desenvolvedores e sysadmins</b>
</p>

<p align="center">
  <a href="#-funcionalidades">Funcionalidades</a> •
  <a href="#-instalação">Instalação</a> •
  <a href="#-uso-rápido">Uso Rápido</a> •
  <a href="#-cloud-storage">Cloud</a> •
  <a href="#-dashboard-web">Dashboard</a> •
  <a href="#-plugins">Plugins</a> •
  <a href="#-documentação">Docs</a>
</p>

---

## Sobre o Projeto

O **AutoTarefas** é uma ferramenta CLI modular e extensível para automação de tarefas do dia-a-dia. Desenvolvido em Python com foco em qualidade de código, testes e documentação, oferece funcionalidades como backup, limpeza, organização de arquivos, monitoramento do sistema, agendamento de tarefas, notificações por email, integrações com cloud e muito mais.

### Destaques

- **7 módulos principais** de automação
- **3 provedores cloud** integrados (Google Drive, Dropbox, AWS S3)
- **Dashboard web** com métricas em tempo real
- **Sistema de plugins** extensível
- **986 testes** automatizados
- **98% de cobertura** de código
- **Documentação completa** com MkDocs

---

## Funcionalidades

### Módulos Principais

| Módulo | Descrição | Comandos |
|--------|-----------|----------|
| **Backup** | Backup automático com compressão (ZIP, TAR, TAR.GZ) | `backup run`, `backup list`, `backup restore` |
| **Cleaner** | Limpeza inteligente de arquivos temporários | `clean run`, `clean preview`, `clean profiles` |
| **Organizer** | Organização automática por tipo (102 extensões) | `organize run`, `organize preview`, `organize stats` |
| **Monitor** | Monitoramento de CPU, RAM, disco em tempo real | `monitor status`, `monitor live` |
| **Scheduler** | Agendamento de tarefas com persistência | `schedule add`, `schedule list`, `schedule start` |
| **Email** | Notificações por email via SMTP | `email send`, `email test`, `email notify` |
| **Reporter** | Geração de relatórios em múltiplos formatos | `report generate`, `report templates` |

### Integrações Avançadas

| Módulo | Descrição | Recursos |
|--------|-----------|----------|
| **Cloud Storage** | Upload/download para nuvem | Google Drive, Dropbox, AWS S3 |
| **Dashboard Web** | Interface web para monitoramento | FastAPI, React, WebSocket |
| **Plugins** | Sistema extensível de plugins | Hooks, Registry, Entry Points |

---

## Instalação

### Requisitos

- **Python 3.12** ou superior
- **pip** (gerenciador de pacotes)
- Sistema operacional: Windows, Linux ou macOS

### Via pip (recomendado)

```bash
pip install autotarefas
```

### Instalação com extras

```bash
# Com suporte a cloud (Google Drive, Dropbox, S3)
pip install autotarefas[cloud]

# Com dashboard web
pip install autotarefas[api]

# Instalação completa
pip install autotarefas[all]
```

### Desenvolvimento

```bash
# Clone o repositório
git clone https://github.com/paulor007/autotarefas.git
cd autotarefas

# Crie um ambiente virtual
python -m venv venv

# Ative o ambiente
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Instale em modo desenvolvimento
pip install -e ".[dev]"

# Verifique a instalação
autotarefas --version
```

---

## Uso Rápido

### Ver ajuda

```bash
autotarefas --help
autotarefas backup --help
autotarefas monitor --help
```

### Monitor do Sistema

```bash
# Status básico
autotarefas monitor status

# Status completo com rede
autotarefas monitor status --all --network

# Monitoramento em tempo real
autotarefas monitor live --interval 2

# Saída em JSON
autotarefas monitor status --json
```

**Exemplo de saída:**
```
╭─────────────────────── Status do Sistema ────────────────────────╮
│   CPU          [██░░░░░░░░░░░░░░░░░░] 10.2%                      │
│   Memória      [████████░░░░░░░░░░░░] 40.8% (13.0 GB / 31.9 GB)  │
│   Disco C:\    [█████████████████░░░] 86.5% (62.4 GB livre)      │
│                                                                   │
│ ⚠️  Alertas:                                                      │
│   • Disco cheio (C:\): 86.5% (threshold: 80%)                    │
╰──────────────────────────────────────────────────────────────────╯
```

### Backup

```bash
# Criar backup
autotarefas backup run ~/Documents -d ~/backups

# Com compressão específica
autotarefas backup run ~/Documents -d ~/backups --compression tar.gz

# Listar backups
autotarefas backup list ~/backups

# Restaurar backup
autotarefas backup restore ~/backups/backup_20260210.zip -d ~/restored

# Backup para cloud (Google Drive)
autotarefas backup run ~/Documents --cloud google_drive --cloud-path /backups
```

### Organizar Arquivos

```bash
# Ver preview (não move arquivos)
autotarefas organize preview ~/Downloads

# Ver estatísticas
autotarefas organize stats ~/Downloads

# Organizar arquivos
autotarefas organize run ~/Downloads

# Organizar por data de modificação
autotarefas organize run ~/Downloads --profile by_date

# Incluir subpastas
autotarefas organize run ~/Downloads --recursive
```

**Exemplo de preview:**
```
                    12 arquivos seriam organizados
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Destino        ┃ Arquivos ┃ Exemplos                              ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 📁 Documentos/ │        5 │ relatorio.pdf, planilha.xlsx ...      │
│ 📁 Imagens/    │        4 │ foto.jpg, screenshot.png ...          │
│ 📁 Videos/     │        2 │ video.mp4, clip.mov                   │
│ 📁 Codigo/     │        1 │ script.py                             │
└────────────────┴──────────┴───────────────────────────────────────┘
```

### Limpeza

```bash
# Ver perfis disponíveis
autotarefas clean profiles

# Preview de limpeza
autotarefas clean preview ~/Downloads --profile temp_files

# Limpar arquivos temporários
autotarefas clean run ~/temp --profile temp_files

# Limpar arquivos mais velhos que 30 dias
autotarefas clean run ~/Downloads --days 30

# Usar lixeira (seguro)
autotarefas clean run ~/temp --use-trash
```

### Agendamento

```bash
# Ver tarefas disponíveis
autotarefas schedule tasks

# Adicionar backup diário às 2h
autotarefas schedule add backup-diario backup "0 2 * * *" --type cron

# Adicionar monitor a cada hora
autotarefas schedule add monitor-hourly monitor "3600" --type interval

# Listar jobs agendados
autotarefas schedule list

# Status do scheduler
autotarefas schedule status

# Iniciar scheduler
autotarefas schedule start
```

### Email

```bash
# Testar configuração
autotarefas email test

# Enviar email
autotarefas email send -t destino@email.com -s "Assunto" -b "Corpo do email"

# Enviar notificação
autotarefas email notify "Backup concluído com sucesso!" --level success
```

---

## Cloud Storage

O AutoTarefas suporta 3 provedores de cloud storage para backup e sincronização.

### Provedores Suportados

| Provedor | Autenticação | Recursos |
|----------|--------------|----------|
| **Google Drive** | OAuth2 | Upload, download, folders, shared links |
| **Dropbox** | Token/OAuth | Upload chunked, shared links |
| **AWS S3** | Access Key | Presigned URLs, buckets |

### Uso via Python

```python
from autotarefas.cloud import get_storage, GoogleDriveStorage

# Factory pattern
storage = get_storage("google_drive", credentials_file="credentials.json")
storage.connect()

# Upload
result = storage.upload(Path("backup.zip"), "/backups/backup.zip")
print(f"Uploaded: {result.file_url}")

# Download
storage.download("/backups/backup.zip", Path("./restored.zip"))

# Listar arquivos
files = storage.list_files("/backups")
for f in files:
    print(f"{f.name} - {f.size} bytes")

storage.disconnect()
```

### CloudBackupTask

```python
from autotarefas.tasks import CloudBackupTask

task = CloudBackupTask(
    name="backup_cloud",
    source=Path("/dados"),
    cloud_provider="google_drive",
    cloud_path="/backups",
    cloud_credentials={"credentials_file": "creds.json"},
    max_cloud_backups=10,  # Manter apenas os 10 mais recentes
)
result = task.run()
```

---

## Dashboard Web

Interface web moderna para monitoramento em tempo real.

### Iniciar o Dashboard

```bash
# Via CLI
autotarefas dashboard --port 8000

# Ou diretamente
python -m autotarefas.api.server
```

Acesse: **http://localhost:8000**

### Funcionalidades

- **Métricas em tempo real** - CPU, memória, disco, rede
- **Lista de Tasks** - Visualização das tasks disponíveis
- **Execução de Tasks** - Execute tasks diretamente pelo dashboard
- **Top Processos** - Monitore os processos que mais consomem recursos
- **WebSocket** - Atualizações a cada 2 segundos

### API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/` | Dashboard HTML |
| GET | `/health` | Health check |
| GET | `/api/system` | Informações do sistema |
| GET | `/api/tasks` | Lista de tasks |
| POST | `/api/tasks/{id}/run` | Executa uma task |
| GET | `/api/monitor` | Métricas de monitoramento |
| GET | `/api/monitor/processes` | Top processos |
| WS | `/ws/metrics` | WebSocket para métricas |

### Tecnologias

- **Backend**: FastAPI, Uvicorn, WebSockets, Pydantic
- **Frontend**: React 18, Tailwind CSS

---

## Plugins

Sistema extensível de plugins para adicionar novas funcionalidades.

### Criar um Plugin

```python
from autotarefas.plugins import PluginBase, PluginInfo, hook

class MeuPlugin(PluginBase):
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="meu-plugin",
            version="1.0.0",
            description="Meu plugin customizado",
            author="Seu Nome",
            tags=["custom", "example"],
        )

    def activate(self) -> None:
        # Registrar hooks, tasks, etc
        print("Plugin ativado!")

    def deactivate(self) -> None:
        # Limpar recursos
        print("Plugin desativado!")
```

### Registrar via Entry Point

```toml
# pyproject.toml
[project.entry-points."autotarefas.plugins"]
meu-plugin = "meu_pacote:MeuPlugin"
```

### Sistema de Hooks

```python
from autotarefas.plugins import hook, HookManager

# Via decorator
@hook("task.after_run")
def log_task_result(task_name, result):
    print(f"Task {task_name}: {result.status}")

# Via HookManager
HookManager.register("task.on_failure", minha_funcao)

# Disparar eventos
HookManager.trigger("task.after_run", task_name="backup", result=result)
```

### Eventos Disponíveis

| Evento | Descrição |
|--------|-----------|
| `task.before_run` | Antes de executar task |
| `task.after_run` | Após executar task |
| `task.on_success` | Task bem-sucedida |
| `task.on_failure` | Task falhou |
| `scheduler.job_added` | Job adicionado |
| `scheduler.job_executed` | Job executado |
| `backup.before_create` | Antes de criar backup |
| `backup.after_create` | Após criar backup |
| `plugin.activated` | Plugin ativado |
| `plugin.deactivated` | Plugin desativado |

### Plugins de Exemplo

| Plugin | Descrição |
|--------|-----------|
| `logging_plugin.py` | Logging avançado com histórico |
| `slack_plugin.py` | Notificações via Slack |
| `database_backup_plugin.py` | Backup de bancos de dados |

---

## Configuração

### Arquivo .env

```bash
cp .env.example .env
```

### Variáveis Principais

| Variável | Descrição | Default |
|----------|-----------|---------|
| `AUTOTAREFAS_HOME` | Diretório de dados | `~/.autotarefas` |
| `AUTOTAREFAS_LOG_LEVEL` | Nível de log | `INFO` |
| `EMAIL_HOST` | Servidor SMTP | `smtp.gmail.com` |
| `EMAIL_PORT` | Porta SMTP | `587` |
| `EMAIL_USER` | Usuário SMTP | - |
| `EMAIL_PASSWORD` | Senha SMTP | - |
| `MONITOR_CPU_THRESHOLD` | Alerta de CPU (%) | `90` |
| `MONITOR_MEMORY_THRESHOLD` | Alerta de memória (%) | `85` |
| `MONITOR_DISK_THRESHOLD` | Alerta de disco (%) | `80` |

### Configuração de Email (Gmail)

1. Acesse [Senhas de App do Google](https://myaccount.google.com/apppasswords)
2. Crie uma senha de app para "Email"
3. Configure no `.env`:

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USER=seu-email@gmail.com
EMAIL_PASSWORD=sua-senha-de-app
```

---

## Testes

```bash
# Rodar todos os testes
pytest

# Com cobertura
pytest --cov=autotarefas --cov-report=html

# Testes específicos
pytest tests/test_backup.py -v

# Apenas testes rápidos
pytest -m "not slow"

# Testes end-to-end
pytest tests/e2e/ -v

# Testes de integração
pytest tests/integration/ -v
```

### Status dos Testes

| Categoria | Quantidade | Status |
|-----------|------------|--------|
| Unit | 750+ | ✅ |
| Integration | 150+ | ✅ |
| E2E | 80+ | ✅ |
| **Total** | **986** | **✅ 98% cobertura** |

---

## Estrutura do Projeto

```
autotarefas/
├── src/autotarefas/
│   ├── cli/                 # Interface de linha de comando
│   │   ├── commands/        # Comandos (backup, clean, monitor, etc.)
│   │   └── utils/           # Utilitários do CLI
│   ├── core/                # Núcleo do sistema
│   │   ├── base.py          # BaseTask, TaskResult, TaskStatus
│   │   ├── scheduler.py     # Agendador de tarefas
│   │   ├── notifier.py      # Sistema de notificações
│   │   └── storage/         # JobStore, RunHistory
│   ├── tasks/               # Implementação das tarefas
│   │   ├── backup.py        # Backup de arquivos
│   │   ├── cleaner.py       # Limpeza de arquivos
│   │   ├── organizer.py     # Organização de arquivos
│   │   ├── monitor.py       # Monitoramento do sistema
│   │   └── reporter.py      # Geração de relatórios
│   ├── cloud/               # Integrações cloud
│   │   ├── base.py          # CloudStorageBase
│   │   ├── google_drive.py  # Google Drive
│   │   ├── dropbox_storage.py # Dropbox
│   │   └── s3_storage.py    # AWS S3
│   ├── plugins/             # Sistema de plugins
│   │   ├── base.py          # PluginBase
│   │   ├── hooks.py         # HookManager
│   │   ├── manager.py       # PluginManager
│   │   └── registry.py      # ComponentRegistry
│   ├── api/                 # Dashboard web
│   │   ├── main.py          # FastAPI app
│   │   ├── models.py        # Schemas Pydantic
│   │   └── server.py        # Servidor standalone
│   └── utils/               # Utilitários gerais
├── tests/                   # Testes automatizados
│   ├── e2e/                 # Testes end-to-end
│   ├── integration/         # Testes de integração
│   └── test_*.py            # Testes unitários
├── docs/                    # Documentação MkDocs
├── examples/                # Exemplos de uso e plugins
├── frontend/                # Dashboard React
├── .github/workflows/       # CI/CD GitHub Actions
├── .env.example             # Exemplo de configuração
├── pyproject.toml           # Configuração do projeto
├── CONTRIBUTING.md          # Guia de contribuição
├── CHANGELOG.md             # Histórico de versões
└── LICENSE                  # Licença MIT
```

---

## Métricas do Projeto

| Métrica | Valor |
|---------|-------|
| **Versão** | 1.0.0 |
| **Testes** | 986 |
| **Cobertura** | 98% |
| **Python** | 3.12+ |
| **Módulos** | 7 principais + 3 avançados |
| **Cloud Providers** | 3 (Google Drive, Dropbox, S3) |
| **Extensões suportadas** | 102 |
| **Hooks disponíveis** | 30+ |

---

## Contribuindo

Contribuições são bem-vindas! Por favor, leia o [CONTRIBUTING.md](CONTRIBUTING.md) para detalhes.

1. Fork o projeto
2. Crie sua branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'feat: adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

### Padrões de Código

- **Formatter**: Black, isort
- **Linter**: Ruff, Flake8
- **Type Checker**: MyPy
- **Testes**: Pytest
- **Pre-commit**: Configurado

---

## Roadmap

- [x] **v0.1.0** - Módulos principais (Backup, Cleaner, Organizer, Monitor)
- [x] **v0.2.0** - Scheduler e Email
- [x] **v0.3.0** - Reporter e melhorias CLI
- [x] **v0.4.0** - Cloud Storage (Google Drive, Dropbox, S3)
- [x] **v0.5.0** - Dashboard Web (FastAPI + React)
- [x] **v1.0.0** - Sistema de Plugins e versão estável
- [ ] **v1.1.0** - Plugins da comunidade
- [ ] **v1.2.0** - App mobile para monitoramento

---

## Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

## Suporte

- **Autor:** [Paulo Lavarini](https://www.linkedin.com/in/paulo-lavarini-20abaa38)
- **Portfolio:** [paulolavariniportfolio.netlify.app](https://paulolavariniportfolio.netlify.app/)
- **Email:** paulo.lavarini@gmail.com
- **Issues:** [GitHub Issues](https://github.com/paulor007/autotarefas/issues)
- **Discussões:** [GitHub Discussions](https://github.com/paulor007/autotarefas/discussions)

---

<p align="center">
  <b>AutoTarefas v1.0.0</b> - Automatize suas tarefas, simplifique sua vida 🚀
</p>

<p align="center">
  Feito com ❤️ por <a href="https://www.linkedin.com/in/paulo-lavarini-20abaa38">Paulo Lavarini</a>
</p>

<p align="center">
  <sub>⭐ Se este projeto te ajudou, deixe uma estrela!</sub>
</p>
