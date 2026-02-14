# Publicação PyPI/TestPyPI

> **Objetivo:** Documentar o processo completo de publicação do pacote AutoTarefas no TestPyPI (testes) e PyPI (produção).

---

## 1. Visão Geral do Processo

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Build     │ → │  TestPyPI   │ → │    PyPI     │
│  (local)    │    │  (teste)    │    │ (produção)  │
└─────────────┘    └─────────────┘    └─────────────┘
```

| Etapa | Descrição |
|-------|-----------|
| **Build** | Gerar arquivos wheel (.whl) e sdist (.tar.gz) |
| **TestPyPI** | Publicar versão de teste para validação |
| **PyPI** | Publicar versão oficial para usuários |

---

## 2. Pré-requisitos

### 2.1 Ferramentas Necessárias

```bash
# Instalar ferramentas de build e upload
pip install build twine
```

| Ferramenta | Função |
|------------|--------|
| `build` | Gera os pacotes (wheel e sdist) |
| `twine` | Upload seguro para PyPI/TestPyPI |

### 2.2 Contas Necessárias

1. **TestPyPI**: https://test.pypi.org/account/register/
2. **PyPI**: https://pypi.org/account/register/

> ⚠️ São contas **separadas**! Criar conta em um não cria no outro.

### 2.3 Tokens de API

Após criar as contas, gerar tokens de API:

1. Acesse **Account Settings** → **API tokens**
2. Clique em **Add API token**
3. Nome: `autotarefas-upload`
4. Escopo: `Entire account` (ou projeto específico após primeira publicação)
5. **Copie o token** (começa com `pypi-`)

---

## 3. Configuração do Twine

### 3.1 Arquivo ~/.pypirc

Criar arquivo de configuração em `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

> ⚠️ **Segurança:** Definir permissões restritas: `chmod 600 ~/.pypirc`

### 3.2 Alternativa: Variáveis de Ambiente

Para CI/CD, usar variáveis de ambiente:

```bash
# TestPyPI
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-xxxxx
export TWINE_REPOSITORY_URL=https://test.pypi.org/legacy/

# PyPI
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-xxxxx
```

---

## 4. Build do Pacote

### 4.1 Limpar Builds Anteriores

```bash
# Remover diretórios de build anteriores
rm -rf dist/ build/ *.egg-info src/*.egg-info
```

### 4.2 Gerar Pacotes

```bash
# Gerar wheel e sdist
python -m build
```

**Saída esperada:**

```
dist/
├── autotarefas-0.1.0-py3-none-any.whl    # Wheel (instalação rápida)
└── autotarefas-0.1.0.tar.gz               # Source distribution
```

### 4.3 Verificar Pacotes

```bash
# Validar metadados e estrutura
twine check dist/*
```

**Saída esperada:**

```
Checking dist/autotarefas-0.1.0-py3-none-any.whl: PASSED
Checking dist/autotarefas-0.1.0.tar.gz: PASSED
```

---

## 5. Publicação no TestPyPI

### 5.1 Upload para TestPyPI

```bash
twine upload --repository testpypi dist/*
```

**Ou com URL explícita:**

```bash
twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

### 5.2 Verificar no TestPyPI

Acesse: `https://test.pypi.org/project/autotarefas/`

### 5.3 Testar Instalação do TestPyPI

```bash
# Criar ambiente virtual de teste
python -m venv test-env
source test-env/bin/activate  # Linux/macOS
# test-env\Scripts\activate   # Windows

# Instalar do TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    autotarefas

# Testar
autotarefas --version
autotarefas --help

# Limpar
deactivate
rm -rf test-env
```

> **Nota:** `--extra-index-url` é necessário porque as dependências (click, rich, etc.) estão no PyPI real, não no TestPyPI.

---

## 6. Publicação no PyPI (Produção)

### 6.1 Checklist Pré-Publicação

- [ ] Versão atualizada no `pyproject.toml`
- [ ] CHANGELOG.md atualizado
- [ ] Todos os testes passando (`pytest`)
- [ ] Cobertura adequada (`pytest --cov`)
- [ ] README.md atualizado
- [ ] Testado no TestPyPI
- [ ] Tag git criada

### 6.2 Upload para PyPI

```bash
twine upload dist/*
```

### 6.3 Verificar no PyPI

Acesse: `https://pypi.org/project/autotarefas/`

### 6.4 Testar Instalação do PyPI

```bash
# Em um ambiente limpo
pip install autotarefas
autotarefas --version
```

---

## 7. Versionamento e Releases

### 7.1 Atualizar Versão

Editar `pyproject.toml`:

```toml
[project]
version = "0.2.0"  # Incrementar conforme semver
```

Ou em `src/autotarefas/__init__.py`:

```python
__version__ = "0.2.0"
```

### 7.2 Criar Tag Git

```bash
# Commit das alterações
git add .
git commit -m "chore: bump version to 0.2.0"

# Criar tag
git tag -a v0.2.0 -m "Release v0.2.0"

# Push
git push origin main
git push origin v0.2.0
```

### 7.3 Versionamento Semântico (SemVer)

| Tipo | Quando Incrementar | Exemplo |
|------|-------------------|---------|
| **MAJOR** (X.0.0) | Breaking changes | 0.1.0 → 1.0.0 |
| **MINOR** (0.X.0) | Novas funcionalidades | 0.1.0 → 0.2.0 |
| **PATCH** (0.0.X) | Bug fixes | 0.1.0 → 0.1.1 |

---

## 8. Script de Release Automatizado

### 8.1 Criar Script `scripts/release.py`

```python
#!/usr/bin/env python3
"""Script de release do AutoTarefas."""

import subprocess
import sys
from pathlib import Path

def run(cmd: str) -> None:
    """Executa comando e exibe saída."""
    print(f"\n>>> {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"Erro ao executar: {cmd}")
        sys.exit(1)

def main() -> None:
    """Executa processo de release."""
    # 1. Limpar builds anteriores
    print("\n🧹 Limpando builds anteriores...")
    run("rm -rf dist/ build/ *.egg-info src/*.egg-info")

    # 2. Executar testes
    print("\n🧪 Executando testes...")
    run("pytest --tb=short")

    # 3. Build
    print("\n📦 Gerando pacotes...")
    run("python -m build")

    # 4. Verificar
    print("\n✅ Verificando pacotes...")
    run("twine check dist/*")

    # 5. Confirmar upload
    print("\n" + "="*50)
    print("Pacotes prontos para upload!")
    print("="*50)

    if input("\nEnviar para TestPyPI? (s/n): ").lower() == 's':
        run("twine upload --repository testpypi dist/*")
        print("\n✅ Publicado no TestPyPI!")
        print("Teste com: pip install -i https://test.pypi.org/simple/ autotarefas")

    if input("\nEnviar para PyPI (produção)? (s/n): ").lower() == 's':
        run("twine upload dist/*")
        print("\n✅ Publicado no PyPI!")
        print("Instale com: pip install autotarefas")

if __name__ == "__main__":
    main()
```

### 8.2 Uso do Script

```bash
python scripts/release.py
```

---

## 9. Troubleshooting

### 9.1 Erro: "File already exists"

O PyPI não permite sobrescrever versões. Solução:
- Incrementar versão em `pyproject.toml`
- Para desenvolvimento, usar sufixos: `0.1.0.dev1`, `0.1.0a1`, `0.1.0rc1`

### 9.2 Erro: "Invalid token"

- Verificar se o token está correto
- Verificar se está usando o token do repositório correto (TestPyPI vs PyPI)
- Tokens devem começar com `pypi-`

### 9.3 Erro: "Package name already taken"

- Escolher nome único no PyPI
- Verificar disponibilidade: `pip index versions nome-do-pacote`

### 9.4 Erro de Dependências no TestPyPI

O TestPyPI não tem todas as dependências. Usar:

```bash
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    autotarefas
```

---

## 10. Checklist Completo de Release

```markdown
## Release v0.X.X

### Preparação
- [ ] Atualizar versão em pyproject.toml
- [ ] Atualizar CHANGELOG.md
- [ ] Atualizar README.md se necessário
- [ ] Verificar requirements estão corretos

### Qualidade
- [ ] pytest (todos os testes passando)
- [ ] pytest --cov (cobertura > 80%)
- [ ] ruff check src/ (sem erros de lint)
- [ ] mypy src/ (sem erros de tipo)

### Build
- [ ] rm -rf dist/ build/
- [ ] python -m build
- [ ] twine check dist/*

### TestPyPI
- [ ] twine upload --repository testpypi dist/*
- [ ] Testar instalação do TestPyPI
- [ ] Verificar página do projeto

### Produção
- [ ] twine upload dist/*
- [ ] Verificar página do PyPI
- [ ] Testar instalação do PyPI
- [ ] Criar tag git (git tag -a vX.X.X)
- [ ] Push tag (git push origin vX.X.X)
- [ ] Criar release no GitHub
```

---

## 11. Resumo de Comandos

| Ação | Comando |
|------|---------|
| Instalar ferramentas | `pip install build twine` |
| Limpar builds | `rm -rf dist/ build/ *.egg-info` |
| Gerar pacotes | `python -m build` |
| Verificar pacotes | `twine check dist/*` |
| Upload TestPyPI | `twine upload --repository testpypi dist/*` |
| Upload PyPI | `twine upload dist/*` |
| Instalar do TestPyPI | `pip install -i https://test.pypi.org/simple/ autotarefas` |
| Instalar do PyPI | `pip install autotarefas` |

---

## Próximos Passos

- [10.3 Versionamento](fase_10_3_versionamento.md) - Estratégias de versão
- [10.4 CI/CD](fase_10_4_ci_cd.md) - GitHub Actions para automação

---

*Fase 10.2 - Publicação PyPI/TestPyPI | AutoTarefas*
