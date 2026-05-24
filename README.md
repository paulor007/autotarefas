# AutoTarefas

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen.svg)]()
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](http://mypy-lang.org/)
[![Security: documented](https://img.shields.io/badge/security-documented-green.svg)](SECURITY.md)

Robô de automação operacional para tarefas em planilhas (CSV, Excel),
arquivos e sistemas web (RPA). Projeto Python moderno com foco em
**segurança**, **rastreabilidade** (audit trail) e **robustez**.

> ⚠️ **Status atual: v0.4.0 (pré-release).** Validador + Backup +
> Organizador + Segurança + Relatórios prontos. Próximos releases: RPA,
> dashboard.

---

## ✨ Destaques

- **Validador de planilhas** com schema declarativo em YAML
- **Validadores brasileiros**: CPF e CNPJ com algoritmo módulo 11
- **Backup ZIP** com hash SHA-256 e excludes inteligentes
- **Organizador de arquivos** com regras YAML
- **Relatórios consolidados** do audit trail (summary/list/errors)
- **Segurança transversal documentada** — 13 princípios, threat model
- **Audit trail completo** — toda execução em SQLite append-only com HMAC-SHA256
- **Mascaramento automático** — CPFs, CNPJs, senhas e tokens nunca vazam em logs
- **Dry-run em tudo** — simula operações antes de fazer mudanças reais
- **Type-safe** — mypy strict, 0 erros
- **~610 testes**, 98% de cobertura

---

## 🚀 Instalação

```bash
git clone https://github.com/paulor007/autotarefas.git
cd autotarefas

python -m venv venv
source venv/bin/activate         # Linux/Mac
# .\venv\Scripts\Activate.ps1    # Windows PowerShell

pip install -e ".[dev]"
```

**Pré-requisitos**: Python 3.12+, Git.

---

## 🎯 Quick Start

```bash
autotarefas init                  # Inicializa ~/.autotarefas/
autotarefas info                  # Verifica o sistema
autotarefas --help                # Lista comandos
autotarefas report                # Vê o que você já fez!
```

---

## 📋 Validador de Planilhas (v0.2.0)

Valida planilhas CSV/Excel contra schemas YAML declarativos.

```bash
autotarefas validate dados.csv --schema schema.yaml \
    --report-json rel.json --report-csv rel.csv
```

Validações: tipo, intervalo, regex, enum, CPF, CNPJ.

---

## 💾 Backup de Arquivos (v0.3.0)

Compacta arquivos/pastas em ZIP com hash SHA-256 para integridade.

```bash
autotarefas backup D:\projeto --output backup.zip \
    --exclude "*.log"
```

---

## 🗂️ Organizador de Arquivos (v0.3.0)

Organiza arquivos em sub-pastas conforme regras declarativas em YAML.

```bash
autotarefas --dry-run organize D:\Downloads --rules rules.yaml
autotarefas organize D:\Downloads --rules rules.yaml
```

Variáveis no destination: `{year}`, `{month:02d}`, `{day:02d}`, `{ext}`.

---

## 📊 Relatórios Consolidados (v0.4.0 — NOVO)

Consulta o **audit trail** e gera estatísticas, listas ou apenas falhas.
Toda execução de qualquer comando é registrada automaticamente em
SQLite, e o `report` te dá visibilidade sobre tudo.

### Uso básico

```bash
# Summary das últimas 24h (default)
autotarefas report

# Última semana
autotarefas report --days 7

# Filtros
autotarefas report --task validate --status failure
autotarefas report --since 2026-05-01 --until 2026-05-15

# Tipos diferentes
autotarefas report --type list                   # lista detalhada
autotarefas report --type errors                 # só falhas

# Formatos diferentes
autotarefas report --format json
autotarefas report --format csv --output rel.csv
```

### Exemplo de saída (summary)

```
============================================================
 AutoTarefas - Relatorio Audit Trail
============================================================

Periodo:  2026-05-21 14:30  ->  2026-05-22 14:30
Total:    47 execucoes

Por task:
  - validate     23 ( 49.0%)  22 ok, 1 falha
  - backup        8 ( 17.0%)  8 ok
  - organize      6 ( 12.8%)  5 ok, 1 partial
  - init          5 ( 10.6%)  5 ok
  - info          5 ( 10.6%)  5 ok

Por status:
  - success      44 ( 93.6%)
  - failure       2 (  4.3%)
  - dry_run       1 (  2.1%)

Duracao media por task:
  - backup        550ms
  - organize     1.20s
  - validate     150ms
  - init          27ms

Falhas recentes (ultimas 5):
  X 2026-05-22 13:45  organize  path traversal bloqueado
  X 2026-05-22 09:12  validate  MissingColumnsError: 'idade'...
```

### Opções

| Flag                  | Descrição                     | Default   |
| --------------------- | ----------------------------- | --------- |
| `--task, -t NAME`     | Filtra por task               | —         |
| `--status, -s STATUS` | Filtra por status             | —         |
| `--days N`            | Últimos N dias                | `1` (24h) |
| `--since DATE`        | Data inicial (`YYYY-MM-DD`)   | —         |
| `--until DATE`        | Data final                    | —         |
| `--type`              | `summary` / `list` / `errors` | `summary` |
| `--format`            | `table` / `json` / `csv`      | `table`   |
| `--output, -o PATH`   | Salva em arquivo              | stdout    |
| `--limit N`           | Max linhas em list/errors     | `100`     |

---

## 🛡️ Segurança (v0.4.0 — REFORÇADA)

Este projeto adere a **13 princípios documentados** de segurança.
Consulte [SECURITY.md](SECURITY.md) para detalhes completos.

### Highlights

- **Audit trail imutável** (append-only, HMAC-SHA256)
- **Defense in depth** — múltiplas camadas independentes
- **Whitelist > blacklist** em extensões e paths
- **Validação de filename** em 7 camadas (anti `../../etc`, NUL, nomes
  reservados Windows, chars proibidos)
- **HTTPS obrigatório em produção**
- **Mascaramento automático** de dados sensíveis em logs e audit
- **Dry-run em operações destrutivas**

### Reportar vulnerabilidades

Veja [SECURITY.md](SECURITY.md) para o processo de **coordinated
disclosure**. Não abra issues públicas para questões de segurança.

---

## 📋 Outros Comandos

```bash
autotarefas info        # mostra info do sistema
autotarefas init        # cria estrutura ~/.autotarefas/
autotarefas validate    # valida planilha CSV/Excel
autotarefas backup      # compacta arquivos em ZIP
autotarefas organize    # organiza arquivos em pastas
autotarefas report      # NOVO em v0.4.0 - relatórios do audit
```

### Opções globais

| Flag            | Descrição                       |
| --------------- | ------------------------------- |
| `--verbose, -v` | Aumenta verbosidade             |
| `--quiet, -q`   | Diminui verbosidade             |
| `--dry-run`     | Simula sem fazer mudanças reais |
| `--yes, -y`     | Assume "sim" em confirmações    |
| `--version`     | Mostra a versão                 |
| `--help, -h`    | Mostra ajuda                    |

---

## 🛣️ Roadmap

- ✅ **v0.1.0** — Core + CLI base
- ✅ **v0.2.0** — Validador de planilhas
- ✅ **v0.3.0** — Backup + Organizador
- ✅ **v0.4.0** — Segurança Transversal + Relatórios _(atual)_
- ⏳ **v0.5.0** — Sistema demo + RPA Cadastro Web
- ⏳ **v0.6.0** — Extração (API + Browser)
- ⏳ **v0.7.0** — Sincronização assistida
- ⏳ **v0.8.0** — Dashboard web (opcional)
- ⏳ **v1.0.0** — Versão estável com CI/CD + docs completas

---

## 🧑‍💻 Desenvolvimento

```bash
pip install -e ".[dev]"
pre-commit install

ruff check src/ tests/
ruff format src/ tests/
mypy src/ tests/
pytest tests/ -v
pytest tests/ --cov
pre-commit run --all-files
```

### Stack

- **Python 3.12+**
- **Click** + **Rich** — CLI moderna
- **pydantic-settings** — config type-safe
- **loguru** — logging com mascaramento
- **SQLite** — audit trail local
- **pandas** + **openpyxl** + **PyYAML** — planilhas e schemas
- **zipfile** + **hashlib** + **shutil** — backup/organizador (stdlib!)
- **playwright** — RPA web (futuras fases)
- **pytest** + **mypy strict** + **ruff** + **bandit** + **detect-secrets**

---

## 📄 Licença

[MIT](LICENSE) © 2026 Paulo Lavarini
