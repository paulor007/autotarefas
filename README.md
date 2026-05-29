# AutoTarefas

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.5.0-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen.svg)]()
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](http://mypy-lang.org/)
[![Security: documented](https://img.shields.io/badge/security-documented-green.svg)](SECURITY.md)

Robô de automação operacional para tarefas em planilhas (CSV, Excel),
arquivos e sistemas web (RPA). Projeto Python moderno com foco em
**segurança**, **rastreabilidade** (audit trail) e **robustez**.

> ⚠️ **Status atual: v0.5.0 (pré-release).** Validador + Backup +
> Organizador + Segurança + Relatórios + **RPA Cadastro Web** prontos.
> Próximos releases: extração de dados, dashboard.

---

## Destaques

- **Automação web (RPA)** — cadastra registros web a partir de planilha, com navegador real (Playwright)
- **Sistema demo local** — servidor Flask para testar automações com segurança
- **Validador de planilhas** com schema declarativo em YAML
- **Validadores brasileiros**: CPF e CNPJ com algoritmo módulo 11
- **Backup ZIP** com hash SHA-256 e excludes inteligentes
- **Organizador de arquivos** com regras YAML
- **Relatórios consolidados** do audit trail (summary/list/errors)
- **Segurança transversal documentada** — 13 princípios, threat model
- **Audit trail completo** — toda execução em SQLite append-only com HMAC-SHA256
- **Mascaramento automático** — CPFs, CNPJs, senhas e tokens nunca vazam em logs nem em screenshots
- **Dry-run em tudo** — simula operações antes de fazer mudanças reais
- **Type-safe** — mypy strict, 0 erros
- **~720 testes**, ~98% de cobertura

---

## Instalação

```bash
git clone https://github.com/paulor007/autotarefas.git
cd autotarefas

python -m venv venv
source venv/bin/activate         # Linux/Mac
# .\venv\Scripts\Activate.ps1    # Windows PowerShell

pip install -e ".[dev]"
```

**Pré-requisitos**: Python 3.12+, Git.

### Extras opcionais

```bash
pip install -e ".[rpa]"          # automação web (Playwright)
playwright install chromium      # baixa o navegador (~200MB)

pip install -e ".[demo]"         # servidor demo local (Flask)

pip install -e ".[dev,rpa,demo]" # tudo junto
```

---

## Quick Start

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

## Automação Web — RPA (v0.5.0 — NOVO)

Automatiza cadastros web a partir de uma planilha, usando um navegador
real (Chromium via Playwright). Valida CPF localmente, é tolerante a
falhas por linha e mascara dados sensíveis em screenshots.

### Instalação

```bash
pip install -e ".[rpa]"
playwright install chromium
```

### Uso

```bash
autotarefas rpa cadastro --planilha clientes.csv --site http://localhost:5555
```

### Exemplo de saída

```
============================================================
 RPA Cadastro
============================================================
Planilha: clientes.csv
Site:     http://localhost:5555
Modo:     headless

Processando...

[1/3] Ana Silva Santos    ... [OK] ID: 1
[2/3] Bruno Costa Lima    ... [OK] ID: 2
[3/3] Carlos Pereira      ... [SKIP] CPF invalido (modulo 11)

============================================================
Total:    3 linhas processadas
Sucesso:  2 cadastros realizados
Skipped:  1 linhas puladas
Erros:    0
Tempo:    3.4s
============================================================
```

### Esquema da planilha

| Coluna     | Obrigatório | Validação           |
| ---------- | ----------- | ------------------- |
| `nome`     | Sim         | Não vazio           |
| `email`    | Sim         | Não vazio           |
| `cpf`      | Sim         | Algoritmo módulo 11 |
| `telefone` | Não         | —                   |

### Opções

| Flag              | Descrição                                            | Default    |
| ----------------- | ---------------------------------------------------- | ---------- |
| `--planilha, -p`  | Caminho da planilha CSV/XLSX                         | —          |
| `--site, -s`      | URL base do sistema alvo                             | —          |
| `--show-browser`  | Mostra a janela do navegador                         | headless   |
| `--no-screenshot` | Desabilita screenshots automáticas em erro           | habilitado |
| `--allow-remote`  | Permite URLs não-locais (por padrão, só `localhost`) | bloqueado  |

### Comportamento

- **CPF inválido** → linha pulada (`skipped`), não interrompe as demais
- **CPF duplicado** no sistema → linha pulada (`skipped`)
- **Erro técnico** (timeout, etc.) → linha marcada como `error` + screenshot mascarada
- **Servidor offline** → task termina como `skipped` (não tenta nada)

### Dry-run

Simule sem tocar no sistema (não abre navegador):

```bash
autotarefas --dry-run rpa cadastro --planilha clientes.csv --site http://localhost:5555
```

### Sistema demo (para testes)

Um servidor demo local está disponível para testar a automação com
segurança, sem tocar em sistemas reais:

```bash
pip install -e ".[demo]"
python -m tools.demo_server
# Acesse http://localhost:5555
```

⚠️ Por segurança, a automação só roda contra `localhost`/`127.0.0.1` por
default. Para sistemas reais, use `--allow-remote` (com responsabilidade).

---

## Relatórios Consolidados (v0.4.0)

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
  - rpa_cadastro  5 ( 10.6%)  4 ok, 1 partial
  - init          5 ( 10.6%)  5 ok

Por status:
  - success      44 ( 93.6%)
  - failure       2 (  4.3%)
  - dry_run       1 (  2.1%)

Duracao media por task:
  - rpa_cadastro 6.80s
  - organize     1.20s
  - backup        550ms
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

## Segurança (v0.4.0 — REFORÇADA)

Este projeto adere a **13 princípios documentados** de segurança.
Consulte [SECURITY.md](SECURITY.md) para detalhes completos.

### Highlights

- **Audit trail imutável** (append-only, HMAC-SHA256)
- **Defense in depth** — múltiplas camadas independentes
- **Whitelist > blacklist** em extensões e paths
- **Validação de filename** em 7 camadas (anti `../../etc`, NUL, nomes
  reservados Windows, chars proibidos)
- **RPA restrito a hosts locais** — automação contra sistema real exige
  `--allow-remote` explícito (fail-safe default)
- **Mascaramento em screenshots** — CPF, CNPJ, senha, token e cartão são
  cobertos automaticamente em capturas de tela
- **HTTPS obrigatório em produção**
- **Mascaramento automático** de dados sensíveis em logs e audit
- **Dry-run em operações destrutivas**

### Reportar vulnerabilidades

Veja [SECURITY.md](SECURITY.md) para o processo de **coordinated
disclosure**. Não abra issues públicas para questões de segurança.

---

## Outros Comandos

```bash
autotarefas info        # mostra info do sistema
autotarefas init        # cria estrutura ~/.autotarefas/
autotarefas validate    # valida planilha CSV/Excel
autotarefas backup      # compacta arquivos em ZIP
autotarefas organize    # organiza arquivos em pastas
autotarefas report      # relatórios do audit trail
autotarefas rpa         # NOVO em v0.5.0 - automação web (RPA)
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

## Roadmap

- ✅ **v0.1.0** — Core + CLI base
- ✅ **v0.2.0** — Validador de planilhas
- ✅ **v0.3.0** — Backup + Organizador
- ✅ **v0.4.0** — Segurança Transversal + Relatórios
- ✅ **v0.5.0** — Sistema demo + RPA Cadastro Web _(atual)_
- ⏳ **v0.6.0** — Extração (API + Browser)
- ⏳ **v0.7.0** — Sincronização assistida
- ⏳ **v0.8.0** — Dashboard web (opcional)
- ⏳ **v1.0.0** — Versão estável com CI/CD + docs completas

---

## Desenvolvimento

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
- **Playwright** — automação web (RPA)
- **Flask** — servidor demo local (desenvolvimento)
- **httpx** — health check do alvo RPA
- **pytest** + **mypy strict** + **ruff** + **bandit** + **detect-secrets**

---

## 📄 Licença

[MIT](LICENSE) © 2026 Paulo Lavarini
