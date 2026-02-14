# 🤝 Guia de Contribuição

Obrigado por considerar contribuir com o **AutoTarefas**! Este documento fornece diretrizes para contribuir com o projeto.

## 📋 Índice

- [Código de Conduta](#código-de-conduta)
- [Como Contribuir](#como-contribuir)
- [Configuração do Ambiente](#configuração-do-ambiente)
- [Padrões de Código](#padrões-de-código)
- [Commits e Pull Requests](#commits-e-pull-requests)
- [Testes](#testes)
- [Documentação](#documentação)

## 📜 Código de Conduta

Este projeto segue um código de conduta. Ao participar, espera-se que você mantenha esse código. Por favor, seja respeitoso e construtivo em todas as interações.

## 🚀 Como Contribuir

### Reportando Bugs

1. Verifique se o bug já não foi reportado nas [Issues](https://github.com/paulor007/autotarefas/issues)
2. Se não encontrar, crie uma nova issue usando o template de bug
3. Inclua:
   - Descrição clara do problema
   - Passos para reproduzir
   - Comportamento esperado vs atual
   - Versão do Python e sistema operacional
   - Logs relevantes

### Sugerindo Melhorias

1. Abra uma issue descrevendo a melhoria
2. Explique o caso de uso
3. Aguarde feedback antes de implementar

### Implementando Features

1. Comente na issue que deseja trabalhar nela
2. Faça fork do repositório
3. Crie uma branch para sua feature
4. Implemente seguindo os padrões do projeto
5. Adicione testes
6. Abra um Pull Request

## 💻 Configuração do Ambiente

### Pré-requisitos

- Python 3.12 ou superior
- Git
- Editor com suporte a Python (VS Code recomendado)

### Instalação

```bash
# Clone seu fork
git clone https://github.com/SEU-USUARIO/autotarefas.git
cd autotarefas

# Crie ambiente virtual
python -m venv venv

# Ative o ambiente
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Instale dependências de desenvolvimento
pip install -e ".[dev]"

# Verifique a instalação
autotarefas --version
pytest --version
```

### Configuração do Editor (VS Code)

Recomendamos as seguintes extensões:
- Python (Microsoft)
- Pylance
- Ruff
- GitLens

Configurações sugeridas (`.vscode/settings.json`):
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/Scripts/python.exe",
    "python.analysis.typeCheckingMode": "basic",
    "[python]": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "charliermarsh.ruff"
    }
}
```

## 📐 Padrões de Código

### Estilo

- Seguimos **PEP 8** com algumas customizações
- Usamos **Ruff** para linting e formatação
- Linha máxima: 100 caracteres
- Indentação: 4 espaços

### Formatação Automática

```bash
# Formatar código
ruff format .

# Verificar linting
ruff check .

# Corrigir automaticamente
ruff check . --fix
```

### Type Hints

Usamos type hints em todo o código:

```python
# ✅ Bom
def process_file(path: Path, encoding: str = "utf-8") -> dict[str, Any]:
    ...

# ❌ Evitar
def process_file(path, encoding="utf-8"):
    ...
```

### Docstrings

Usamos Google-style docstrings:

```python
def backup_directory(
    source: Path,
    destination: Path,
    compression: str = "zip",
) -> BackupResult:
    """
    Cria backup de um diretório.

    Args:
        source: Diretório de origem.
        destination: Diretório de destino.
        compression: Tipo de compressão ('zip', 'tar.gz').

    Returns:
        Resultado do backup com estatísticas.

    Raises:
        FileNotFoundError: Se o diretório de origem não existir.
        PermissionError: Se não houver permissão de escrita.

    Example:
        >>> result = backup_directory(Path("/home/user/docs"), Path("/backups"))
        >>> print(result.files_count)
        42
    """
```

### Estrutura de Arquivos

```python
"""
Módulo para [descrição].

O QUE ESTE MÓDULO FAZ:
======================
[Explicação clara]

EXEMPLO DE USO:
===============
    [código de exemplo]
"""

from __future__ import annotations

# Imports da biblioteca padrão
import os
from pathlib import Path

# Imports de terceiros
import click
from rich.console import Console

# Imports locais
from autotarefas.core.base import BaseTask

# Constantes
DEFAULT_TIMEOUT = 30

# Classes e funções
...
```

## 📝 Commits e Pull Requests

### Mensagens de Commit

Seguimos o padrão [Conventional Commits](https://www.conventionalcommits.org/):

```
tipo(escopo): descrição curta

[corpo opcional]

[rodapé opcional]
```

**Tipos:**
- `feat`: Nova funcionalidade
- `fix`: Correção de bug
- `docs`: Documentação
- `style`: Formatação (não afeta código)
- `refactor`: Refatoração
- `test`: Testes
- `chore`: Tarefas de manutenção

**Exemplos:**
```
feat(backup): adiciona suporte a compressão tar.bz2
fix(cleaner): corrige pattern matching no Windows
docs(readme): atualiza instruções de instalação
test(monitor): adiciona testes para alertas de disco
```

### Pull Requests

1. **Título**: Use o formato de commit convencional
2. **Descrição**: Explique o que foi feito e por quê
3. **Checklist**:
   - [ ] Código segue os padrões do projeto
   - [ ] Testes adicionados/atualizados
   - [ ] Documentação atualizada
   - [ ] Todos os testes passando
   - [ ] Sem conflitos com main

## 🧪 Testes

### Executando Testes

```bash
# Todos os testes
pytest

# Com cobertura
pytest --cov=autotarefas --cov-report=html

# Testes específicos
pytest tests/test_backup.py
pytest tests/test_backup.py::TestBackupTask::test_execute

# Por marcador
pytest -m "not slow"

# Com output verboso
pytest -v --tb=short
```

### Escrevendo Testes

```python
import pytest
from pathlib import Path

from autotarefas.tasks.backup import BackupTask


class TestBackupTask:
    """Testes para BackupTask."""

    def test_backup_creates_archive(self, tmp_path: Path) -> None:
        """Deve criar arquivo de backup."""
        # Arrange
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        # Act
        task = BackupTask()
        result = task.run(source=str(source))

        # Assert
        assert result.is_success
        assert result.data["files_count"] == 1

    @pytest.mark.parametrize("compression", ["zip", "tar.gz", "tar.bz2"])
    def test_backup_compression_types(
        self,
        tmp_path: Path,
        compression: str,
    ) -> None:
        """Deve suportar diferentes tipos de compressão."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("content")

        task = BackupTask()
        result = task.run(source=str(source), compression=compression)

        assert result.is_success
```

### Fixtures

Use fixtures do `conftest.py` quando possível:

```python
@pytest.fixture
def sample_directory(tmp_path: Path) -> Path:
    """Cria diretório com arquivos de exemplo."""
    d = tmp_path / "sample"
    d.mkdir()
    (d / "doc.pdf").write_bytes(b"PDF content")
    (d / "image.jpg").write_bytes(b"JPEG content")
    return d
```

### Cobertura Mínima

- Novos módulos: mínimo 80% de cobertura
- Código crítico (core): mínimo 90%
- Utilitários: mínimo 70%

## 📚 Documentação

### Atualizando Documentação

- **README.md**: Funcionalidades principais e quick start
- **docs/**: Documentação detalhada
- **Docstrings**: Documentação inline do código
- **CHANGELOG.md**: Registrar mudanças significativas

### Estilo de Documentação

- Escreva em português brasileiro
- Use exemplos práticos
- Mantenha atualizado com o código
- Inclua screenshots quando relevante

## 🏷️ Versionamento

Seguimos [Semantic Versioning](https://semver.org/):

- **MAJOR**: Mudanças incompatíveis na API
- **MINOR**: Novas funcionalidades compatíveis
- **PATCH**: Correções de bugs compatíveis

## ❓ Dúvidas?

- Abra uma [Discussion](https://github.com/paulor007/autotarefas/discussions)
- Entre em contato via Issues

---

Obrigado por contribuir! 🎉
