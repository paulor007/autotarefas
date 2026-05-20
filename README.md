# AutoTarefas

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen.svg)]()
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](http://mypy-lang.org/)
[![Ruff](https://img.shields.io/badge/ruff-checked-orange.svg)](https://github.com/astral-sh/ruff)

Robô de automação operacional para tarefas em planilhas (CSV, Excel) e
sistemas web (RPA). Projeto Python moderno com foco em **segurança**,
**rastreabilidade** (audit trail) e **robustez**.

> ⚠️ **Status atual: v0.2.0 (pré-release).** Fundação + Validador de
> planilhas prontos. Próximos releases: backup, organizador, RPA.

---

## ✨ Destaques

- **Validador de planilhas** com schema declarativo em YAML
- **Validadores brasileiros**: CPF e CNPJ com algoritmo módulo 11
- **Audit trail completo** — toda execução em SQLite append-only com HMAC-SHA256
- **Mascaramento automático** — CPFs, CNPJs, senhas e tokens nunca vazam em logs
- **Dry-run em tudo** — simula operações antes de fazer mudanças reais
- **Confirmação em massa** — operações destrutivas exigem escrita explícita
- **Type-safe** — mypy strict, 0 erros
- **~340 testes**, 98% de cobertura

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

# 2. Verifica o sistema
autotarefas info
```

---

## 📋 Validador de Planilhas (v0.2.0)

O destaque deste release! Valida planilhas CSV/Excel contra schemas
YAML declarativos.

### Exemplo prático

**1. Crie um schema** (`schema.yaml`):

```yaml
columns:
  - name: nome
    type: str
    nullable: false

  - name: idade
    type: int
    min_value: 0
    max_value: 150

  - name: cpf
    validator_br: cpf
    nullable: true

  - name: uf
    enum_values: [SP, RJ, MG, ES, BA, PR, RS, SC]

  - name: cep
    regex: '\d{5}-?\d{3}'
    regex_message: CEP deve ter 8 digitos
    nullable: true
```

**2. Tenha sua planilha** (`dados.csv`):

```csv
nome,idade,cpf,uf,cep
Alice Silva,30,529.982.247-25,SP,01310-100
Bob Costa,200,111.111.111-11,XX,abc
,abc,12345,RJ,01000000
```

**3. Valide**:

```bash
autotarefas validate dados.csv --schema schema.yaml
```

**Saída**:

```
Arquivo:  dados.csv
Linhas:   3
Colunas:  5

Encontrados 6 problema(s):
  - 6 erro(s)
  - 0 aviso(s)

  [ERROR] Linha 3, coluna 'idade': Valor 200.0 maior que o maximo 150.0
  [ERROR] Linha 3, coluna 'cpf': CPF invalido: '111.111.111-11'
  [ERROR] Linha 3, coluna 'uf': Valor 'XX' nao esta entre os aceitos
  [ERROR] Linha 3, coluna 'cep': CEP deve ter 8 digitos
  [ERROR] Linha 4, coluna 'nome': Valor obrigatorio nao informado
  [ERROR] Linha 4, coluna 'idade': Valor 'abc' nao e um int valido

Validacao falhou: 6 erro(s).
```

### Gerando relatórios

```bash
# Relatorio JSON (estruturado, para integracoes)
autotarefas validate dados.csv --schema schema.yaml --report-json rel.json

# Relatorio CSV (Excel-friendly)
autotarefas validate dados.csv --schema schema.yaml --report-csv rel.csv

# Ambos juntos
autotarefas validate dados.csv --schema schema.yaml \
    --report-json rel.json --report-csv rel.csv
```

### Opções do comando validate

| Flag                 | Descrição                                 |
| -------------------- | ----------------------------------------- |
| `--schema, -s PATH`  | (obrigatório) Caminho do schema YAML      |
| `--report-json PATH` | Salva relatório detalhado em JSON         |
| `--report-csv PATH`  | Salva relatório compacto em CSV           |
| `--max-issues, -m N` | Máximo de issues no terminal (default 10) |
| `--strict-warnings`  | Trata warnings como erros (exit 1)        |

### Tipos de validações suportadas

| Tipo                   | Como declarar                           | Exemplo                 |
| ---------------------- | --------------------------------------- | ----------------------- |
| **Tipo de dado**       | `type: int / float / date / bool / str` | `type: int`             |
| **Obrigatório**        | `nullable: false` (default)             | —                       |
| **Intervalo numérico** | `min_value: N`, `max_value: N`          | `min_value: 0`          |
| **Regex (formato)**    | `regex: 'PADRAO'`                       | `regex: '\d{5}'`        |
| **Lista de valores**   | `enum_values: [A, B]`                   | `enum_values: [SP, RJ]` |
| **CPF**                | `validator_br: cpf`                     | —                       |
| **CNPJ**               | `validator_br: cnpj`                    | —                       |

---

## 📋 Outros Comandos (v0.1.0)

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
autotarefas init        # cria estrutura ~/.autotarefas/
autotarefas info        # mostra info do sistema
autotarefas validate    # valida planilha CSV/Excel  ← NOVO em v0.2.0
```

---

## 🛣️ Roadmap

- ✅ **v0.0.0** — Setup (Fase 0)
- ✅ **v0.1.0** — Core + CLI base
- ✅ **v0.2.0** — Validador de planilhas _(atual)_
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
- **Confirmação contextualizada em massa**
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
- **pandas** + **openpyxl** + **PyYAML** — planilhas e schemas
- **playwright** — RPA web (futuras fases)
- **pytest** + **mypy strict** + **ruff** + **bandit**

---

## 📄 Licença

[MIT](LICENSE) © 2026 Paulo Lavarini
