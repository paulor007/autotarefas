# 🤖 AutoTarefas

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-986%20passed-success.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen.svg)](docs/COVERAGE_POLICY.md)

> 🚀 Sistema de automação de tarefas repetitivas do computador

O **AutoTarefas** é uma ferramenta CLI modular e poderosa para automatizar tarefas do dia-a-dia como backup de arquivos, limpeza de temporários, organização de downloads, monitoramento do sistema e muito mais.

---

## ✨ Funcionalidades

| Módulo | Descrição | Comandos |
|--------|-----------|----------|
| 📦 **Backup** | Backup automático com compressão (ZIP, TAR, TAR.GZ) | `backup run`, `backup list`, `backup restore` |
| 🧹 **Cleaner** | Limpeza inteligente de arquivos temporários | `clean run`, `clean preview`, `clean profiles` |
| 🗂️ **Organizer** | Organização automática por tipo (102 extensões) | `organize run`, `organize preview`, `organize stats` |
| 📊 **Monitor** | Monitoramento de CPU, RAM, disco em tempo real | `monitor status`, `monitor live` |
| ⏰ **Scheduler** | Agendamento de tarefas com persistência | `schedule add`, `schedule list`, `schedule start` |
| 📧 **Email** | Notificações por email via SMTP | `email send`, `email test`, `email status` |
| 📋 **Reporter** | Geração de relatórios em múltiplos formatos | `report sales`, `report templates` |

---

## 🚀 Instalação

### Requisitos

- **Python 3.12** ou superior
- **pip** (gerenciador de pacotes)
- Sistema operacional: Windows, Linux ou macOS

### Via pip (recomendado)

```bash
pip install autotarefas
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

## 📖 Uso Rápido

### Ver ajuda

```bash
autotarefas --help
autotarefas backup --help
autotarefas organize --help
```

### 📊 Monitor do Sistema

```bash
# Status básico
autotarefas monitor status

# Status completo com rede
autotarefas monitor status --all --network

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

### 📦 Backup

```bash
# Criar backup
autotarefas backup run ~/Documents -d ~/backups

# Com compressão específica
autotarefas backup run ~/Documents -d ~/backups --compression tar.gz

# Listar backups
autotarefas backup list ~/backups

# Restaurar backup
autotarefas backup restore ~/backups/backup_20260210.zip -d ~/restored
```

### 🗂️ Organizar Arquivos

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
                    📋 12 arquivos seriam organizados
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Destino        ┃ Arquivos ┃ Exemplos                              ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 📁 Documentos/ │        5 │ relatorio.pdf, planilha.xlsx ...      │
│ 📁 Imagens/    │        4 │ foto.jpg, screenshot.png ...          │
│ 📁 Videos/     │        2 │ video.mp4, clip.mov                   │
│ 📁 Codigo/     │        1 │ script.py                             │
└────────────────┴──────────┴───────────────────────────────────────┘
```

### 🧹 Limpeza

```bash
# Ver perfis disponíveis
autotarefas clean profiles

# Preview de limpeza
autotarefas clean preview ~/Downloads --profile temp_files

# Limpar arquivos temporários
autotarefas clean run ~/temp --profile temp_files

# Limpar arquivos mais velhos que 30 dias
autotarefas clean run ~/Downloads --days 30
```

### ⏰ Agendamento

```bash
# Ver tarefas disponíveis
autotarefas schedule tasks

# Adicionar backup diário às 2h
autotarefas schedule add backup-diario backup "02:00" --type daily

# Adicionar monitor a cada hora
autotarefas schedule add monitor-hourly monitor "3600" --type interval

# Listar jobs agendados
autotarefas schedule list

# Status do scheduler
autotarefas schedule status

# Iniciar scheduler
autotarefas schedule start
```

### 📧 Email

```bash
# Testar configuração
autotarefas email test

# Enviar email
autotarefas email send -t destino@email.com -s "Assunto" -b "Corpo do email"

# Enviar notificação
autotarefas email notify "Backup concluído com sucesso!" --level success
```

---

## ⚙️ Configuração

### Arquivo .env

Copie o arquivo de exemplo e configure:

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

## 🧪 Testes

```bash
# Rodar todos os testes
pytest

# Com cobertura
pytest --cov=autotarefas --cov-report=html

# Testes específicos
pytest tests/test_backup.py -v

# Apenas testes rápidos
pytest -m "not slow"
```

**Status atual:** 986 testes | 98% cobertura

---

## 📁 Estrutura do Projeto

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
│   └── utils/               # Utilitários gerais
├── tests/                   # Testes automatizados
│   ├── e2e/                 # Testes end-to-end
│   ├── integration/         # Testes de integração
│   └── test_*.py            # Testes unitários
├── docs/                    # Documentação
├── examples/                # Exemplos de uso
├── .env.example             # Exemplo de configuração
├── pyproject.toml           # Configuração do projeto
├── CONTRIBUTING.md          # Guia de contribuição
├── CHANGELOG.md             # Histórico de versões
└── LICENSE                  # Licença MIT
```

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor, leia o [CONTRIBUTING.md](CONTRIBUTING.md) para detalhes.

1. Fork o projeto
2. Crie sua branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'feat: adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

---

## 📋 Roadmap

- [x] **v0.1.0** - Versão inicial com módulos principais
- [ ] **v0.2.0** - Interface web (dashboard)
- [ ] **v0.3.0** - Plugins e extensões
- [ ] **v1.0.0** - Versão estável

---

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

## 📬 Suporte

- **Autor:** [Paulo Lavarini](https://www.linkedin.com/in/paulo-lavarini-20abaa38)
- **Email:** paulo.lavarini@gmail.com
- **Issues:** [GitHub Issues](https://github.com/paulor007/autotarefas/issues)
- **Discussões:** [GitHub Discussions](https://github.com/paulor007/autotarefas/discussions)

---

<p align="center">
  <b>AutoTarefas</b> - Automatize suas tarefas, simplifique sua vida 🚀
</p>

<p align="center">
  Feito com ❤️ por <a href="https://www.linkedin.com/in/paulo-lavarini-20abaa38">Paulo Lavarini</a>
</p>
