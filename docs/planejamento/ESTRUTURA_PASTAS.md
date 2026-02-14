# 📁 Estrutura de Pastas - AutoTarefas

**Versão:** 1.0
**Data:** Dezembro 2025
**Status:** Aprovado

---

## 1. Visão Geral

O projeto segue o **src layout**, padrão recomendado para projetos Python modernos que serão distribuídos via PyPI.

```
AUTOTAREFAS/
├── .github/                    # CI/CD e configurações GitHub
├── docs/                       # Documentação do projeto
├── examples/                   # Exemplos de uso
├── scripts/                    # Scripts auxiliares
├── src/                        # Código fonte principal
│   └── autotarefas/           # Pacote Python
├── tests/                      # Testes automatizados
└── [arquivos de configuração]  # Na raiz do projeto
```

---

## 2. Estrutura Completa Detalhada

```
AUTOTAREFAS/
│
├── 📁 .github/                         # Configurações do GitHub
│   ├── 📁 workflows/                   # GitHub Actions
│   │   ├── tests.yml                   # Pipeline de testes
│   │   ├── lint.yml                    # Pipeline de linting
│   │   └── release.yml                 # Pipeline de release
│   ├── dependabot.yml                  # Atualização automática de deps
│   ├── ISSUE_TEMPLATE/                 # Templates de issues
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── PULL_REQUEST_TEMPLATE.md        # Template de PR
│
├── 📁 docs/                            # Documentação
│   ├── 📁 planejamento/                # Docs técnicos (Fase 0) - para desenvolvedor
│   │   ├── REQUISITOS.md               # Requisitos do projeto
│   │   ├── ARQUITETURA.md              # Arquitetura do sistema
│   │   ├── ESTRUTURA_PASTAS.md         # Estrutura de diretórios
│   │   ├── TECNOLOGIAS.md              # Tecnologias escolhidas
│   │   ├── MAPEAMENTO_ARQUIVOS_FASES.md # Arquivos × Fases
│   │   └── CRONOGRAMA.md               # Cronograma do projeto
│   ├── 📁 tutorials/                   # Tutoriais (Fase 9) - para usuário final
│   │   ├── backup.md                   # Tutorial de backup
│   │   ├── cleaner.md                  # Tutorial de limpeza
│   │   ├── monitor.md                  # Tutorial de monitoramento
│   │   ├── scheduler.md                # Tutorial de agendamento
│   │   ├── email.md                    # Tutorial de notificações
│   │   └── organizer.md                # Tutorial do organizador
│   ├── index.md                        # Página inicial (MkDocs) - Fase 9
│   ├── installation.md                 # Guia de instalação - Fase 9
│   ├── configuration.md                # Guia de configuração - Fase 9
│   ├── quickstart.md                   # Início rápido - Fase 9
│   ├── cli-reference.md                # Referência completa da CLI - Fase 9
│   ├── api-reference.md                # Referência da API Python - Fase 9
│   └── faq.md                          # Perguntas frequentes - Fase 9
│
├── 📁 examples/                        # Exemplos de código
│   ├── backup_example.py               # Exemplo de backup programático
│   ├── cleaner_example.py              # Exemplo de limpeza
│   ├── monitor_example.py              # Exemplo de monitoramento
│   ├── scheduler_example.py            # Exemplo de agendamento
│   └── organizer_example.py            # Exemplo de organização
│
├── 📁 scripts/                         # Scripts de desenvolvimento
│   ├── check_coverage.py               # Verificar cobertura de testes
│   ├── build.py                        # Script de build
│   └── dev_setup.py                    # Setup do ambiente de dev
│
├── 📁 src/                             # Código fonte (src layout)
│   └── 📁 autotarefas/                 # Pacote principal
│       │
│       ├── 📁 cli/                     # Interface de linha de comando
│       │   ├── 📁 commands/            # Comandos CLI
│       │   │   ├── __init__.py         # Exporta comandos
│       │   │   ├── init.py             # Comando: autotarefas init
│       │   │   ├── backup.py           # Comandos: backup run/list/restore
│       │   │   ├── cleaner.py          # Comandos: clean run/trash
│       │   │   ├── monitor.py          # Comandos: monitor status/live/history
│       │   │   ├── reporter.py         # Comandos: report sales/template
│       │   │   ├── scheduler.py        # Comandos: schedule add/list/start/...
│       │   │   ├── email.py            # Comandos: email test/send/notify
│       │   │   └── organizer.py        # Comandos: organize run/preview/undo
│       │   ├── __init__.py             # Exporta CLI
│       │   └── main.py                 # Ponto de entrada principal
│       │
│       ├── 📁 core/                    # Núcleo do sistema
│       │   ├── 📁 storage/             # Persistência de dados
│       │   │   ├── __init__.py         # Exporta classes de storage
│       │   │   ├── job_store.py        # Persistência de jobs agendados
│       │   │   └── run_history.py      # Histórico de execuções
│       │   ├── __init__.py             # Exporta classes core
│       │   ├── base.py                 # BaseTask, TaskResult, TaskStatus
│       │   ├── logger.py               # Sistema de logging (Loguru)
│       │   ├── scheduler.py            # Scheduler, ScheduledJob, Registry
│       │   ├── email.py                # EmailSender, EmailMessage
│       │   └── notifier.py             # Notificador central
│       │
│       ├── 📁 tasks/                   # Implementação das tarefas
│       │   ├── __init__.py             # Exporta todas as tasks
│       │   ├── backup.py               # BackupTask, RestoreTask, BackupManager
│       │   ├── cleaner.py              # CleanerTask, CleaningProfiles, TrashManager
│       │   ├── monitor.py              # MonitorTask, SystemMetrics, Dashboard
│       │   ├── reporter.py             # ReporterTask base
│       │   ├── sales_report.py         # SalesReportTask específica
│       │   └── organizer.py            # OrganizerTask, UndoTask, Journal
│       │
│       ├── 📁 utils/                   # Utilitários compartilhados
│       │   ├── __init__.py             # Exporta funções utilitárias
│       │   └── helpers.py              # Funções helper (format_size, etc.)
│       │
│       ├── 📁 resources/               # Recursos estáticos empacotáveis
│       │   └── 📁 templates/           # Templates
│       │       └── 📁 email/           # Templates de email HTML
│       │           ├── base.html       # Template base
│       │           ├── report.html     # Template de relatório
│       │           └── notify.html     # Template de notificação
│       │
│       ├── __init__.py                 # Inicialização do pacote + versão
│       ├── config.py                   # Configurações globais
│       └── py.typed                    # Marker para type checking
│
├── 📁 tests/                           # Testes automatizados
│   ├── 📁 integration/                 # Testes de integração
│   │   ├── __init__.py
│   │   ├── conftest.py                 # Fixtures de integração
│   │   ├── test_backup_integration.py
│   │   ├── test_cleaner_integration.py
│   │   ├── test_monitor_integration.py
│   │   ├── test_scheduler_integration.py
│   │   ├── test_email_integration.py
│   │   └── test_organizer_integration.py
│   │
│   ├── 📁 e2e/                         # Testes end-to-end (CLI)
│   │   ├── __init__.py
│   │   ├── conftest.py                 # Fixtures E2E
│   │   ├── test_cli_main.py
│   │   ├── test_cli_backup.py
│   │   ├── test_cli_cleaner.py
│   │   ├── test_cli_monitor.py
│   │   ├── test_cli_scheduler.py
│   │   ├── test_cli_email.py
│   │   ├── test_cli_report.py
│   │   └── test_cli_organizer.py
│   │
│   ├── __init__.py
│   ├── conftest.py                     # Fixtures globais
│   ├── test_config.py                  # Testes de configuração
│   ├── test_logger.py                  # Testes do logger
│   ├── test_base.py                    # Testes de BaseTask
│   ├── test_utils.py                   # Testes de utilitários
│   ├── test_backup.py                  # Testes de backup
│   ├── test_cleaner.py                 # Testes de cleaner
│   ├── test_monitor.py                 # Testes de monitor
│   ├── test_scheduler.py               # Testes do scheduler
│   ├── test_email.py                   # Testes de email
│   ├── test_sales_report.py            # Testes de sales report
│   ├── test_organizer.py               # Testes do organizer
│   ├── test_job_store.py               # Testes de persistência jobs
│   └── test_run_history.py             # Testes de histórico
│
├── .coveragerc                         # Configuração de cobertura
├── .env.example                        # Exemplo de variáveis de ambiente
├── .gitignore                          # Arquivos ignorados pelo Git
├── .pre-commit-config.yaml             # Hooks de pre-commit
├── CHANGELOG.md                        # Histórico de versões
├── CODE_OF_CONDUCT.md                  # Código de conduta
├── CONTRIBUTING.md                     # Guia de contribuição
├── LICENSE                             # Licença (MIT)
├── MANIFEST.in                         # Arquivos incluídos no pacote
├── mkdocs.yml                          # Configuração do MkDocs
├── pyproject.toml                      # Configuração do projeto Python
├── README.md                           # Documentação principal
└── SECURITY.md                         # Política de segurança
```

---

## 3. Detalhamento por Diretório

### 3.1 `.github/` - Configurações GitHub

| Arquivo/Pasta | Propósito |
|---------------|-----------|
| `workflows/tests.yml` | Executa testes em Python 3.11, 3.12, 3.13 em cada push/PR |
| `workflows/lint.yml` | Verifica código com ruff, mypy, formatação |
| `workflows/release.yml` | Build e publicação automática no PyPI |
| `dependabot.yml` | Atualiza dependências automaticamente |
| `ISSUE_TEMPLATE/` | Padroniza criação de issues |
| `PULL_REQUEST_TEMPLATE.md` | Checklist para PRs |

### 3.2 `docs/` - Documentação

| Arquivo/Pasta | Propósito | Fase |
|---------------|-----------|------|
| `planejamento/` | Documentação técnica para desenvolvedores | **Fase 0** |
| `planejamento/REQUISITOS.md` | Requisitos funcionais e não-funcionais | 0 |
| `planejamento/ARQUITETURA.md` | Arquitetura técnica do sistema | 0 |
| `planejamento/ESTRUTURA_PASTAS.md` | Estrutura de diretórios | 0 |
| `planejamento/TECNOLOGIAS.md` | Tecnologias e justificativas | 0 |
| `planejamento/CRONOGRAMA.md` | Cronograma do projeto | 0 |
| `tutorials/` | Tutoriais para usuário final | **Fase 9** |
| `index.md` | Página inicial da documentação online | 9 |
| `installation.md` | Como instalar o AutoTarefas | 9 |
| `configuration.md` | Como configurar (env vars, config files) | 9 |
| `quickstart.md` | Primeiros passos em 5 minutos | 9 |
| `cli-reference.md` | Todos os comandos CLI documentados | 9 |
| `api-reference.md` | API Python para uso programático | 9 |
| `faq.md` | Perguntas frequentes | 9 |

> **Importante:** A pasta `planejamento/` contém docs **técnicos** criados antes do código.
> Os demais arquivos são documentação para **usuário final**, criados após o código funcionar.

### 3.3 `src/autotarefas/` - Código Fonte

#### 3.3.1 `cli/` - Interface de Linha de Comando

| Arquivo | Propósito | Principais Componentes |
|---------|-----------|------------------------|
| `main.py` | Ponto de entrada | `cli` group, `version`, `status` |
| `commands/init.py` | Inicialização | `init` command |
| `commands/backup.py` | Backup/Restore | `run`, `list`, `restore` |
| `commands/cleaner.py` | Limpeza | `run`, `trash` |
| `commands/monitor.py` | Monitoramento | `status`, `live`, `history` |
| `commands/scheduler.py` | Agendamento | `add`, `list`, `start`, `stop`, etc. |
| `commands/email.py` | Notificações | `test`, `send`, `notify`, `queue` |
| `commands/organizer.py` | Organização | `run`, `preview`, `undo`, `history` |
| `commands/reporter.py` | Relatórios | `sales`, `template` |

#### 3.3.2 `core/` - Núcleo do Sistema

| Arquivo | Propósito | Principais Componentes |
|---------|-----------|------------------------|
| `base.py` | Classes base | `BaseTask`, `TaskResult`, `TaskStatus` |
| `logger.py` | Logging | `get_logger()`, configuração Loguru |
| `config.py` | Configurações | `Config`, `Settings`, carregamento |
| `scheduler.py` | Agendamento | `Scheduler`, `ScheduledJob`, `TaskRegistry` |
| `email.py` | Email | `EmailSender`, `EmailMessage`, `EmailStatus` |
| `notifier.py` | Notificações | `Notifier`, `get_notifier()` |
| `storage/job_store.py` | Persistência jobs | `JobStore`, salvar/carregar JSON |
| `storage/run_history.py` | Histórico | `RunHistory`, SQLite queries |

#### 3.3.3 `tasks/` - Implementação das Tarefas

| Arquivo | Propósito | Principais Componentes |
|---------|-----------|------------------------|
| `backup.py` | Backup | `BackupTask`, `RestoreTask`, `BackupManager`, `CompressionType` |
| `cleaner.py` | Limpeza | `CleanerTask`, `CleaningProfiles`, `CleaningReporter`, `TrashManager` |
| `monitor.py` | Monitor | `MonitorTask`, `SystemMetrics`, `MetricsHistory`, `SystemDashboard` |
| `organizer.py` | Organização | `OrganizerTask`, `OrganizerUndoTask`, `OrganizeJournal`, `FileMove` |
| `reporter.py` | Relatórios base | `ReporterTask` |
| `sales_report.py` | Vendas | `SalesReportTask` |

#### 3.3.4 `utils/` - Utilitários

| Arquivo | Propósito | Principais Funções |
|---------|-----------|-------------------|
| `helpers.py` | Funções auxiliares | `format_size()`, `format_time()`, `safe_path()`, `ensure_dir()`, `hash_file()` |

#### 3.3.5 `resources/` - Recursos Estáticos

| Arquivo | Propósito |
|---------|-----------|
| `templates/email/base.html` | Template base HTML para emails |
| `templates/email/report.html` | Template para relatórios |
| `templates/email/notify.html` | Template para notificações |

### 3.4 `tests/` - Testes Automatizados

| Diretório | Tipo | Propósito |
|-----------|------|-----------|
| `tests/` (raiz) | Unitários | Testa funções/classes isoladamente |
| `tests/integration/` | Integração | Testa módulos trabalhando juntos |
| `tests/e2e/` | End-to-End | Testa CLI como usuário faria |

| Arquivo | O que testa |
|---------|-------------|
| `conftest.py` | Fixtures compartilhadas (temp dirs, mocks) |
| `test_config.py` | Carregamento e validação de config |
| `test_base.py` | BaseTask, TaskResult, TaskStatus |
| `test_backup.py` | Criação, compressão, restauração |
| `test_cleaner.py` | Limpeza, profiles, dry-run |
| `test_scheduler.py` | Agendamento, persistência, execução |
| `test_email.py` | Envio, templates, fila |

---

## 4. Arquivos de Configuração (Raiz)

### 4.1 Configuração do Projeto

| Arquivo | Propósito | Tecnologia |
|---------|-----------|------------|
| `pyproject.toml` | Metadados, dependências, scripts | PEP 518/621 |
| `MANIFEST.in` | Arquivos extras no pacote | setuptools |
| `mkdocs.yml` | Configuração documentação | MkDocs |

### 4.2 Qualidade de Código

| Arquivo | Propósito | Tecnologia |
|---------|-----------|------------|
| `.pre-commit-config.yaml` | Hooks automáticos | pre-commit |
| `.coveragerc` | Configuração cobertura | pytest-cov |

### 4.3 Ambiente

| Arquivo | Propósito |
|---------|-----------|
| `.env.example` | Exemplo de variáveis de ambiente |
| `.gitignore` | Arquivos ignorados pelo Git |

### 4.4 Documentação (Raiz)

| Arquivo | Propósito |
|---------|-----------|
| `README.md` | Apresentação do projeto, quickstart |
| `CHANGELOG.md` | Histórico de versões (Keep a Changelog) |
| `CONTRIBUTING.md` | Como contribuir com o projeto |
| `CODE_OF_CONDUCT.md` | Código de conduta da comunidade |
| `SECURITY.md` | Política de segurança, reportar vulnerabilidades |
| `LICENSE` | Licença MIT |

---

## 5. Estrutura de Dados em Runtime

### 5.1 Diretório de Dados do Usuário

Quando o AutoTarefas é executado, ele cria/usa:

```
~/.autotarefas/                     # AUTOTAREFAS_HOME
├── config.yaml                     # Configurações do usuário
├── jobs.json                       # Jobs agendados persistidos
├── history.db                      # SQLite com histórico de execuções
├── 📁 logs/                        # Logs da aplicação
│   ├── autotarefas.log            # Log atual
│   ├── autotarefas.log.1          # Rotação 1
│   ├── autotarefas.log.2          # Rotação 2
│   └── ...
├── 📁 backups/                     # Backups criados (padrão)
│   ├── backup_2024-12-01_143022.zip
│   └── ...
├── 📁 cache/                       # Cache temporário
│   └── ...
├── 📁 journals/                    # Journals do organizer (undo)
│   ├── organize_2024-12-01_143022.json
│   └── ...
└── 📁 templates/                   # Templates customizados do usuário
    └── 📁 email/
        └── custom.html
```

### 5.2 Variáveis de Ambiente

```bash
# Diretório de dados
AUTOTAREFAS_HOME=~/.autotarefas

# Logging
AUTOTAREFAS_LOG_LEVEL=INFO
AUTOTAREFAS_LOG_FILE=~/.autotarefas/logs/autotarefas.log

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=seu@email.com
EMAIL_PASSWORD=sua_senha_app
EMAIL_FROM=seu@email.com
EMAIL_USE_TLS=true
```

---

## 6. Convenções de Nomenclatura

### 6.1 Arquivos Python

| Tipo | Convenção | Exemplo |
|------|-----------|---------|
| Módulos | snake_case | `backup.py`, `sales_report.py` |
| Classes | PascalCase | `BackupTask`, `CleaningProfiles` |
| Funções | snake_case | `format_size()`, `get_logger()` |
| Constantes | UPPER_SNAKE | `DEFAULT_EXTENSION_MAP` |
| Privados | _prefixo | `_execute()`, `_validate()` |

### 6.2 Arquivos de Configuração

| Tipo | Convenção | Exemplo |
|------|-----------|---------|
| Markdown | UPPER_CASE | `README.md`, `CHANGELOG.md` |
| YAML/JSON | lowercase | `config.yaml`, `jobs.json` |
| Dotfiles | .nome | `.env`, `.gitignore` |

### 6.3 Testes

| Convenção | Exemplo |
|-----------|---------|
| `test_<módulo>.py` | `test_backup.py` |
| `test_<módulo>_integration.py` | `test_backup_integration.py` |
| `test_cli_<comando>.py` | `test_cli_backup.py` |
| Função: `test_<ação>_<cenário>` | `test_backup_creates_zip_file()` |

---

## 7. Dependências entre Módulos

```
┌─────────────────────────────────────────────────────────────┐
│                    IMPORT HIERARCHY                          │
│                                                              │
│  Nível 0 (sem deps internas):                               │
│  └── utils/helpers.py                                        │
│                                                              │
│  Nível 1 (depende de utils):                                │
│  ├── core/logger.py                                          │
│  └── core/config.py                                          │
│                                                              │
│  Nível 2 (depende de core básico):                          │
│  ├── core/base.py                                            │
│  └── core/storage/*                                          │
│                                                              │
│  Nível 3 (depende de base):                                 │
│  ├── core/scheduler.py                                       │
│  ├── core/email.py                                           │
│  ├── core/notifier.py                                        │
│  └── tasks/*                                                 │
│                                                              │
│  Nível 4 (depende de tudo):                                 │
│  └── cli/*                                                   │
│                                                              │
│  ⚠️  REGRA: Imports só podem ir para níveis inferiores!     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Checklist de Criação

Ao iniciar o projeto, criar na ordem:

### Fase 1 - Estrutura Base
- [ ] Criar diretório raiz `autotarefas/`
- [ ] Criar `src/autotarefas/__init__.py`
- [ ] Criar `pyproject.toml`
- [ ] Criar `.gitignore`
- [ ] Criar `README.md`
- [ ] Inicializar Git

### Fase 2 - Core
- [ ] Criar `src/autotarefas/config.py`
- [ ] Criar `src/autotarefas/core/__init__.py`
- [ ] Criar `src/autotarefas/core/logger.py`
- [ ] Criar `src/autotarefas/core/base.py`
- [ ] Criar `src/autotarefas/utils/__init__.py`
- [ ] Criar `src/autotarefas/utils/helpers.py`

### Fase 3 - Tasks
- [ ] Criar `src/autotarefas/tasks/__init__.py`
- [ ] Criar cada task em seu arquivo

### Fase 4 - CLI
- [ ] Criar `src/autotarefas/cli/__init__.py`
- [ ] Criar `src/autotarefas/cli/main.py`
- [ ] Criar `src/autotarefas/cli/commands/__init__.py`
- [ ] Criar cada comando em seu arquivo

### Fase 5+ - Complementares
- [ ] Criar estrutura de testes
- [ ] Criar documentação
- [ ] Criar CI/CD

---

## 9. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|--------|------|-------|-----------|
| 1.0 | Dez/2025 | - | Versão inicial aprovada |

---

*Documento gerado como parte da Fase 0.3 - Estrutura de Pastas*
