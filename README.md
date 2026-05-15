# AutoTarefas

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen.svg)]()
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](http://mypy-lang.org/)
[![Ruff](https://img.shields.io/badge/ruff-checked-orange.svg)](https://github.com/astral-sh/ruff)

Robô de automação operacional para tarefas em planilhas (CSV, Excel) e
sistemas web (RPA). Projeto Python moderno com foco em **segurança**,
**rastreabilidade** (audit trail) e **robustez**.

> ⚠️ **Status atual: v0.1.0 (pré-release).** A fundação está pronta, mas
> os módulos de negócio (validador, backup, RPA) ainda estão em
> desenvolvimento. Veja o [roadmap](#-roadmap) abaixo.

---

## ✨ Destaques

- **Audit trail completo** — toda execução fica registrada em SQLite
  append-only com HMAC-SHA256
- **Mascaramento automático** — CPFs, CNPJs, senhas e tokens nunca
  vazam em logs
- **Dry-run em tudo** — simula operações antes de fazer mudanças reais
- **Confirmação em massa** — operações destrutivas exigem escrita
  explícita do número de itens
- **Type-safe** — mypy strict, 0 erros
- **98% de cobertura de testes**

---

## 🚀 Instalação

```bash
# Clone o repositorio
git clone https://github.com/paulor007/autotarefas.git
cd autotarefas

# Cria virtual env (recomendado)
python -m venv venv
source venv/bin/activate         # Linux/Mac
# .\venv\Scripts\Activate.ps1    # Windows PowerShell

# Instala em modo desenvolvimento com todas as deps
pip install -e ".[dev]"
```

**Pré-requisitos**: Python 3.12+, Git.

---

## 🎯 Quick Start

```bash
# 1. Inicializa a estrutura em ~/.autotarefas/
autotarefas init

# 2. Edita o .env gerado (configuracoes locais)

# 3. Verifica o sistema
autotarefas info
```

---

## 📋 Comandos (v0.1.0)

### Opções globais

| Flag            | Descrição                                 |
| --------------- | ----------------------------------------- |
| `--verbose, -v` | Aumenta verbosidade (`-v`, `-vv`, `-vvv`) |
| `--quiet, -q`   | Diminui verbosidade (`-q`, `-qq`)         |
| `--dry-run`     | Simula sem fazer mudanças reais           |
| `--yes, -y`     | Assume "sim" em todas as confirmações     |
| `--version`     | Mostra a versão                           |
| `--help, -h`    | Mostra ajuda                              |

### Subcomandos

```bash
autotarefas init     # cria estrutura ~/.autotarefas/
autotarefas info     # mostra info do sistema
```

### Exemplos

```bash
autotarefas --dry-run -vv init       # simula, com debug
autotarefas init --data-dir ./custom # dir custom
python -m autotarefas info           # equivalente
```

---

## 🛣️ Roadmap

- ✅ **v0.0.0** — Setup (Fase 0)
- ✅ **v0.1.0** — Core + CLI base _(atual)_
- ⏳ **v0.2.0** — Validador de planilhas (CSV/Excel)
- ⏳ **v0.3.0** — Backup + Organizador de arquivos
- ⏳ **v0.4.0** — Base operacional estável
- ⏳ **v0.5.0** — Sistema demo + RPA Cadastro Web
- ⏳ **v0.6.0** — Extração (API + Browser)
- ⏳ **v0.7.0** — Sincronização assistida
- ⏳ **v0.8.0** — Dashboard web (opcional)
- ⏳ **v1.0.0** — Versão estável com CI/CD + docs completas

---

## 🛡️ Princípios de Segurança

Este projeto adere a **13 princípios** documentados, entre eles:

- **Audit trail imutável** (append-only, HMAC-SHA256)
- **Confirmação contextualizada em massa** (escrita do número exato)
- **HTTPS obrigatório em produção**
- **Mascaramento automático** de dados sensíveis em logs
- **Path traversal protection**
- **Ambiente demo obrigatório para RPA**

---

## 🧑‍💻 Desenvolvimento

```bash
pip install -e ".[dev]"
pre-commit install

# Validadores
ruff check src/ tests/      # linter
ruff format src/ tests/     # formatter
mypy src/ tests/             # type checker
pytest tests/ -v             # testes
pytest tests/ --cov         # cobertura
pre-commit run --all-files  # tudo de uma vez
```

### Stack

- **Python 3.12+**
- **Click** + **Rich** — CLI moderna
- **pydantic-settings** — config type-safe
- **loguru** — logging com mascaramento
- **SQLite** — audit trail local
- **pandas** + **openpyxl** — planilhas
- **playwright** — RPA web (futuras fases)
- **pytest** + **mypy strict** + **ruff** + **bandit**

---

## 📄 Licença

[MIT](LICENSE) © 2026 Paulo Lavarini
