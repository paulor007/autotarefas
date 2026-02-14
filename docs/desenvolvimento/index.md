# Desenvolvimento

Guias para contribuidores e desenvolvedores do AutoTarefas.

## Seções

<div class="grid cards" markdown>

-   :material-source-pull:{ .lg .middle } **[Contribuindo](contribuindo.md)**

    ---

    Como contribuir com o projeto: setup, guidelines, PR.

-   :material-sitemap:{ .lg .middle } **[Arquitetura](arquitetura.md)**

    ---

    Visão geral da arquitetura e decisões de design.

-   :material-history:{ .lg .middle } **[Changelog](changelog.md)**

    ---

    Histórico de versões e mudanças.

</div>

## Quick Start para Desenvolvedores

### 1. Clonar e Configurar

```bash
git clone https://github.com/paulor007/autotarefas.git
cd autotarefas

python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

pip install -e ".[dev,docs,all]"
```

### 2. Executar Testes

```bash
# Todos os testes
pytest

# Com cobertura
pytest --cov=src/autotarefas --cov-report=html

# Testes específicos
pytest tests/test_backup.py -v
```

### 3. Verificar Código

```bash
# Linting
ruff check src/

# Formatação
ruff format src/

# Type checking
mypy src/
```

### 4. Documentação

```bash
# Servidor local
mkdocs serve

# Build
mkdocs build
```

## Estrutura do Projeto

```
autotarefas/
├── src/autotarefas/    # Código fonte
│   ├── core/           # Módulos fundamentais
│   ├── tasks/          # Implementações de tarefas
│   ├── cli/            # Interface de linha de comando
│   └── utils/          # Utilitários
├── tests/              # Testes
├── docs/               # Documentação
├── scripts/            # Scripts auxiliares
└── pyproject.toml      # Configuração do projeto
```

## Links Úteis

- [GitHub](https://github.com/paulor007/autotarefas)
- [Issues](https://github.com/paulor007/autotarefas/issues)
- [Discussions](https://github.com/paulor007/autotarefas/discussions)
