# AutoTarefas

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen.svg)]()
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](http://mypy-lang.org/)
[![Ruff](https://img.shields.io/badge/ruff-checked-orange.svg)](https://github.com/astral-sh/ruff)

Robô de automação operacional para tarefas em planilhas (CSV, Excel),
arquivos e sistemas web (RPA). Projeto Python moderno com foco em
**segurança**, **rastreabilidade** (audit trail) e **robustez**.

> ⚠️ **Status atual: v0.3.0 (pré-release).** Validador + Backup +
> Organizador prontos. Próximos releases: RPA, dashboard.

---

## ✨ Destaques

- **Validador de planilhas** com schema declarativo em YAML
- **Validadores brasileiros**: CPF e CNPJ com algoritmo módulo 11
- **Backup ZIP** com hash SHA-256 e excludes inteligentes
- **Organizador de arquivos** com regras YAML (CPF YAML)
- **Audit trail completo** — toda execução em SQLite append-only com HMAC-SHA256
- **Mascaramento automático** — CPFs, CNPJs, senhas e tokens nunca vazam em logs
- **Dry-run em tudo** — simula operações antes de fazer mudanças reais
- **Confirmação em massa** — operações destrutivas exigem confirmação
- **Type-safe** — mypy strict, 0 erros
- **~485 testes**, 98% de cobertura

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

# 3. Lista comandos disponiveis
autotarefas --help
```

---

## 📋 Validador de Planilhas (v0.2.0)

Valida planilhas CSV/Excel contra schemas YAML declarativos.

### Exemplo rápido

**Schema** (`schema.yaml`):

```yaml
columns:
  - name: nome
    type: str

  - name: idade
    type: int
    min_value: 0
    max_value: 150

  - name: cpf
    validator_br: cpf
    nullable: true
```

**Validar**:

```bash
autotarefas validate dados.csv --schema schema.yaml

# Com relatorios
autotarefas validate dados.csv --schema schema.yaml \
    --report-json rel.json --report-csv rel.csv
```

Validações: tipo, intervalo, regex, enum, CPF, CNPJ.

---

## 💾 Backup de Arquivos (v0.3.0 — NOVO)

Compacta arquivos/pastas em ZIP com hash SHA-256 para integridade.

### Uso básico

```bash
# Backup de uma pasta
autotarefas backup D:\meu-projeto --output D:\backups\proj.zip

# Multiplas fontes
autotarefas backup D:\projeto D:\docs --output D:\backups\full.zip

# Excludes customizados
autotarefas backup D:\projeto --output backup.zip \
    --exclude "*.log" --exclude "tmp/*"

# Sem excludes padrao (cuidado!)
autotarefas backup D:\projeto --output backup.zip --no-default-excludes
```

### Excludes padrão (automáticos)

Por padrão, o backup **ignora** essas pastas/arquivos:
`__pycache__`, `*.pyc`, `.git`, `node_modules`, `.venv`, `.mypy_cache`,
`.pytest_cache`, `.ruff_cache`, `.DS_Store`, `Thumbs.db`, `.idea`,
`.vscode`, e outros.

### Saída

```
Backup de 1 source -> D:\backups\proj.zip

Backup criado: D:\backups\proj.zip
Arquivos incluidos: 47
Arquivos excluidos: 12
Tamanho: 1.2 MB
SHA-256: 152f0e7049271c78580cccb05e2a52ba88058226de01ec85ff78ce47e84407f5
```

O **hash SHA-256** garante integridade — se algo mudar no ZIP depois,
você consegue detectar comparando o hash.

---

## 🗂️ Organizador de Arquivos (v0.3.0 — NOVO)

Organiza arquivos em sub-pastas conforme regras declarativas em YAML.
Perfeito para pastas bagunçadas como `Downloads`.

### Exemplo prático

**Regras** (`downloads.yaml`):

```yaml
# Pasta raiz onde os arquivos serao organizados
target_root: D:\Downloads-organizado

# O que fazer se arquivo ja existe no destino
on_conflict: rename # skip | rename | overwrite

# Move (default) ou copy
action: move

# Lista de regras (primeira que bate ganha)
rules:
  - name: Imagens
    patterns: ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp"]
    destination: imagens/{year}/{month:02d}

  - name: PDFs
    patterns: ["*.pdf"]
    destination: documentos/pdfs

  - name: Vídeos
    patterns: ["*.mp4", "*.mkv", "*.avi", "*.mov"]
    destination: videos

  - name: Áudio
    patterns: ["*.mp3", "*.wav", "*.flac"]
    destination: musicas

  - name: Instaladores
    patterns: ["*.exe", "*.msi"]
    destination: instaladores/{year}-{month:02d}

  - name: Compactados
    patterns: ["*.zip", "*.rar", "*.7z"]
    destination: compactados
```

**Uso** (sempre comece com dry-run!):

```bash
# 1. Veja o que seria feito sem mudar nada
autotarefas --dry-run organize D:\Downloads --rules downloads.yaml

# 2. Execute de verdade
autotarefas organize D:\Downloads --rules downloads.yaml

# 3. Em automacao, pula confirmacao
autotarefas --yes organize D:\Downloads --rules downloads.yaml
```

### Variáveis no `destination`

| Variável      | Resolvida como                  | Exemplo |
| ------------- | ------------------------------- | ------- |
| `{year}`      | Ano (4 dígitos) do mtime        | `2026`  |
| `{month}`     | Mês (sem padding)               | `5`     |
| `{month:02d}` | Mês com padding                 | `05`    |
| `{day}`       | Dia (sem padding)               | `21`    |
| `{day:02d}`   | Dia com padding                 | `21`    |
| `{ext}`       | Extensão (lowercase, sem ponto) | `pdf`   |

### Comportamentos de conflito

| `on_conflict`    | O que faz                                    |
| ---------------- | -------------------------------------------- |
| `skip` (default) | Não move. Registra como `skipped`            |
| `rename`         | Tenta `arquivo_1.pdf`, `arquivo_2.pdf`, etc. |
| `overwrite`      | ⚠️ Sobrescreve sem perguntar                 |

### Proteções automáticas

- **Dry-run sempre recomendado** (mostra o que seria feito)
- **Confirmação em massa**: se >50 arquivos, pede confirmação `[y/N]`
- **Default seguro**: apertar Enter sem digitar = cancela
- **Não recursivo**: só processa arquivos diretos do `source_dir`
- **Audit completo**: cada arquivo registrado (origem → destino)

---

## 📋 Outros Comandos

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
autotarefas info        # mostra info do sistema
autotarefas init        # cria estrutura ~/.autotarefas/
autotarefas validate    # valida planilha CSV/Excel
autotarefas backup      # compacta arquivos em ZIP    ← NOVO em v0.3.0
autotarefas organize    # organiza arquivos em pastas ← NOVO em v0.3.0
```

---

## 🛣️ Roadmap

- ✅ **v0.0.0** — Setup (Fase 0)
- ✅ **v0.1.0** — Core + CLI base
- ✅ **v0.2.0** — Validador de planilhas
- ✅ **v0.3.0** — Backup + Organizador _(atual)_
- ⏳ **v0.4.0** — Segurança transversal + relatórios consolidados
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
- **Dry-run em operações destrutivas**
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
- **zipfile** + **hashlib** + **shutil** — backup/organizador (stdlib!)
- **playwright** — RPA web (futuras fases)
- **pytest** + **mypy strict** + **ruff** + **bandit**

---

## 📄 Licença

[MIT](LICENSE) © 2026 Paulo Lavarini
