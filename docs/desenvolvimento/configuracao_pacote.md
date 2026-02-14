# Empacotamento

## Configuração de Pacote

> **Objetivo:** Documentar a configuração completa do `pyproject.toml`, incluindo metadados, dependências, ferramentas de build, linting e testes para o projeto AutoTarefas.

---

## 1. Visão Geral do Empacotamento Python

O empacotamento Python moderno utiliza o arquivo **pyproject.toml** como configuração centralizada, seguindo a PEP 517/518. Este arquivo substitui os antigos `setup.py`, `setup.cfg`, `MANIFEST.in` e `requirements.txt` em um único local padronizado.

### 1.1 Evolução do Empacotamento

| Abordagem Antiga | Abordagem Moderna | Benefício |
|------------------|-------------------|-----------|
| `setup.py` | `pyproject.toml [build-system]` | Declarativo, sem execução de código |
| `setup.cfg` | `pyproject.toml [project]` | Formato padronizado (TOML) |
| `requirements.txt` | `[project.dependencies]` | Versionamento semântico integrado |
| `MANIFEST.in` | `[tool.hatch.build]` | Configuração clara de inclusões |
| `tox.ini`, `.flake8`, etc. | `[tool.*]` sections | Todas as ferramentas em um arquivo |

---

## 2. Sistema de Build

O AutoTarefas utiliza o **Hatchling** como backend de build, uma escolha moderna que oferece simplicidade e convenções inteligentes.

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 2.1 Comparação de Build Backends

| Backend | Prós | Contras |
|---------|------|---------|
| **Hatchling** ✓ | Simples, rápido, convenções modernas | Menos customizável que setuptools |
| Setuptools | Maduro, muito flexível, ampla documentação | Configuração mais verbosa |
| Poetry | Gerencia deps + build, lock file | Opinionado, menos padrão |
| Flit | Extremamente simples | Recursos limitados |

---

## 3. Metadados do Projeto

Os metadados do projeto seguem a especificação **PEP 621** e são essenciais para publicação no PyPI.

```toml
[project]
name = "autotarefas"
version = "0.1.0"
description = "Sistema de automação de tarefas repetitivas"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.12"
authors = [{name = "AutoTarefas Team", email = ""}]
```

### 3.1 Keywords e Classifiers

Keywords ajudam na descoberta do pacote, enquanto classifiers categorizam o projeto no PyPI.

```toml
keywords = [
    "automation",
    "backup",
    "cleaner",
    "monitor",
    "scheduler",
    "cli",
    "tasks",
]

classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: System :: Systems Administration",
    "Topic :: Utilities",
]
```

| Classifier | Significado |
|------------|-------------|
| `Development Status :: 3 - Alpha` | Projeto em fase inicial |
| `Environment :: Console` | Aplicação de linha de comando |
| `License :: OSI Approved :: MIT` | Licença open source permissiva |
| `Programming Language :: Python :: 3.12` | Suporta Python 3.12+ |

---

## 4. Gerenciamento de Dependências

O AutoTarefas organiza dependências em grupos lógicos: produção, opcionais e desenvolvimento.

### 4.1 Dependências de Produção

```toml
dependencies = [
    "click>=8.1.0,<9.0.0",           # CLI framework
    "rich>=13.0.0,<15.0.0",          # Terminal UI
    "loguru>=0.7.0,<1.0.0",          # Logging
    "schedule>=1.2.0,<2.0.0",        # Agendamento
    "psutil>=5.9.0,<8.0.0",          # Monitoramento
    "python-dotenv>=1.0.0,<2.0.0",   # Config
]
```

| Pacote | Versão | Função |
|--------|--------|--------|
| `click` | >=8.1.0,<9.0.0 | Framework CLI - criação de comandos e argumentos |
| `rich` | >=13.0.0,<15.0.0 | Interface de terminal rica (cores, tabelas, progress) |
| `loguru` | >=0.7.0,<1.0.0 | Sistema de logging simplificado e poderoso |
| `schedule` | >=1.2.0,<2.0.0 | Agendamento de tarefas em Python puro |
| `psutil` | >=5.9.0,<8.0.0 | Monitoramento de sistema (CPU, memória, disco) |
| `python-dotenv` | >=1.0.0,<2.0.0 | Carregamento de variáveis de ambiente (.env) |

### 4.2 Especificação de Versões

A notação `>=X.Y.0,<Z.0.0` segue versionamento semântico:

| Notação | Significado | Exemplo |
|---------|-------------|---------|
| `>=8.1.0` | Versão mínima requerida | click 8.1.0 ou superior |
| `<9.0.0` | Limite superior (exclusive) | Não aceita major version 9 |
| `~=8.1` | Compatible release | Equivale a >=8.1,<9.0 |

### 4.3 Dependências Opcionais (Extras)

```toml
[project.optional-dependencies]
# Para relatórios com Excel
reports = [
    "pandas>=2.0.0,<3.0.0",
    "openpyxl>=3.1.0,<4.0.0",
]

# Para templates de email
email = [
    "jinja2>=3.1.0,<4.0.0",
]

# Todas as dependências opcionais
all = [
    "autotarefas[reports,email]",
]

# Para desenvolvimento
dev = [
    "pytest>=8.0.0,<10.0.0",
    "pytest-cov>=4.1.0,<8.0.0",
    "pytest-mock>=3.11.0,<4.0.0",
    "ruff>=0.1.0,<1.0.0",
    "mypy>=1.5.0,<2.0.0",
    "pre-commit>=3.4.0,<4.0.0",
]

# Para documentação
docs = [
    "mkdocs>=1.5.0,<2.0.0",
    "mkdocs-material>=9.4.0,<10.0.0",
]
```

**Instalação:**

```bash
pip install autotarefas[reports]    # Apenas relatórios
pip install autotarefas[all]        # Todos os extras
pip install autotarefas[dev]        # Ambiente de desenvolvimento
```

---

## 5. Ponto de Entrada CLI

A seção `[project.scripts]` define comandos executáveis instalados no sistema.

```toml
[project.scripts]
autotarefas = "autotarefas.cli.main:cli"
```

### 5.1 Anatomia do Entry Point

| Componente | Valor | Descrição |
|------------|-------|-----------|
| Comando | `autotarefas` | Nome do executável no terminal |
| Módulo | `autotarefas.cli.main` | Caminho Python até o módulo |
| Função | `cli` | Função decorada com `@click.group()` |

Após instalação, o comando `autotarefas` estará disponível globalmente no sistema.

---

## 6. Configuração do Hatch (Build)

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/autotarefas"]

[tool.hatch.build.targets.sdist]
include = [
    "/src",
    "/tests",
    "/README.md",
    "/LICENSE",
    "/CHANGELOG.md",
]
```

### 6.1 Tipos de Distribuição

| Tipo | Descrição | Conteúdo |
|------|-----------|----------|
| **Wheel** (.whl) | Formato binário, instalação rápida | Apenas código Python compilado |
| **Sdist** (.tar.gz) | Source distribution, código completo | Código fonte + tests + docs |

---

## 7. Ferramentas de Qualidade de Código

### 7.1 Ruff (Linter + Formatter)

O Ruff é um linter e formatter extremamente rápido (escrito em Rust) que substitui flake8, black, isort e outros.

```toml
[tool.ruff]
target-version = "py312"
line-length = 120
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
]
ignore = [
    "E501",   # line too long (handled by formatter)
    "B008",   # do not perform function calls in argument defaults
]

[tool.ruff.lint.isort]
known-first-party = ["autotarefas"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*" = ["ARG001"]  # Unused function args (fixtures)
```

### 7.2 MyPy (Type Checking)

```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
strict_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
show_error_codes = true
namespace_packages = true
explicit_package_bases = true

[[tool.mypy.overrides]]
module = [
    "schedule.*",
    "loguru.*",
]
ignore_missing_imports = true
```

### 7.3 Pytest (Testes)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
python_classes = ["Test*"]
addopts = [
    "-v",
    "--tb=short",
    "--strict-markers",
    "-ra",
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "e2e: marks tests as end-to-end tests",
]
filterwarnings = [
    "ignore::DeprecationWarning",
]
```

---

## 8. Configuração de Cobertura

```toml
[tool.coverage.run]
source = ["src/autotarefas"]
branch = true
omit = [
    "*/tests/*",
    "*/__pycache__/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
fail_under = 80
show_missing = true
```

**Cobertura mínima:** 80% (configurado em `fail_under`). O build falha se a cobertura estiver abaixo deste threshold.

---

## 9. URLs do Projeto

```toml
[project.urls]
Homepage = "https://github.com/paulor007/autotarefas"
Documentation = "https://paulor007.github.io/autotarefas"
Repository = "https://github.com/paulor007/autotarefas"
Issues = "https://github.com/paulor007/autotarefas/issues"
Changelog = "https://github.com/paulor007/autotarefas/blob/main/CHANGELOG.md"
```

Estas URLs aparecem na página do PyPI e ajudam usuários a encontrar documentação, reportar bugs e contribuir.

---

## 10. Comandos de Build e Publicação

| Comando | Descrição |
|---------|-----------|
| `pip install -e .[dev]` | Instala em modo editável com deps de dev |
| `python -m build` | Gera wheel e sdist em `dist/` |
| `twine check dist/*` | Valida os pacotes gerados |
| `twine upload dist/*` | Publica no PyPI |
| `ruff check src/` | Executa linting |
| `ruff format src/` | Formata o código |
| `mypy src/` | Verifica tipos |
| `pytest --cov` | Executa testes com cobertura |

---

## 11. Resumo da Configuração

| Aspecto | Configuração |
|---------|--------------|
| **Build System** | Hatchling (moderno, rápido, convenções inteligentes) |
| **Python** | >=3.12 |
| **Dependências** | 6 de produção + 4 grupos opcionais (reports, email, dev, docs) |
| **CLI** | Entry point `autotarefas` → `autotarefas.cli.main:cli` |
| **Linting** | Ruff (substitui flake8, black, isort) |
| **Type Check** | MyPy com modo strict |
| **Testes** | Pytest com markers customizados |
| **Cobertura** | Mínimo 80%, branch coverage habilitado |

---

## Próximos Passos

- [Publicação PyPI](publicacao_pypi.md) - Como publicar no TestPyPI e PyPI
- [Versionamento](versionamento.md) - Estratégias de versionamento semântico

---

*Configuração de Pacote | AutoTarefas*
