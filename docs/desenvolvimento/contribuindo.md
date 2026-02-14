# Contribuindo

Obrigado pelo interesse em contribuir com o AutoTarefas! 🎉

## Como Contribuir

### Reportar Bugs

1. Verifique se o bug já foi reportado nas [Issues](https://github.com/paulor007/autotarefas/issues)
2. Crie uma nova issue com:
   - Descrição clara do problema
   - Passos para reproduzir
   - Comportamento esperado vs atual
   - Versão do Python e SO
   - Logs relevantes

### Sugerir Features

1. Abra uma [Discussion](https://github.com/paulor007/autotarefas/discussions)
2. Descreva o caso de uso
3. Aguarde feedback antes de implementar

### Contribuir com Código

1. Fork o repositório
2. Crie uma branch (`git checkout -b feature/minha-feature`)
3. Faça suas alterações
4. Execute os testes
5. Commit (`git commit -m "feat: adiciona minha feature"`)
6. Push (`git push origin feature/minha-feature`)
7. Abra um Pull Request

## Setup do Ambiente

```bash
# Clonar
git clone https://github.com/SEU_USUARIO/autotarefas.git
cd autotarefas

# Ambiente virtual
python -m venv .venv
source .venv/bin/activate

# Instalar dependências de desenvolvimento
pip install -e ".[dev,docs,all]"

# Instalar pre-commit hooks
pre-commit install
```

## Padrões de Código

### Style Guide

- **PEP 8** - Seguimos o PEP 8 com linha máxima de 120 caracteres
- **Ruff** - Usamos Ruff para linting e formatação

```bash
# Verificar
ruff check src/ tests/

# Formatar
ruff format src/ tests/
```

### Type Hints

Usamos type hints em todo o código:

```python
def process_files(
    source: Path,
    patterns: list[str] | None = None
) -> TaskResult:
    ...
```

Verificar com mypy:

```bash
mypy src/
```

### Docstrings

Usamos Google style:

```python
def backup_files(source: Path, destination: Path) -> TaskResult:
    """Cria backup dos arquivos.

    Args:
        source: Diretório de origem.
        destination: Diretório de destino.

    Returns:
        TaskResult com informações do backup.

    Raises:
        ValueError: Se source não existir.

    Example:
        >>> result = backup_files(Path("/dados"), Path("/backup"))
        >>> print(result.success)
        True
    """
```

### Commits

Seguimos [Conventional Commits](https://www.conventionalcommits.org/):

| Prefixo | Uso |
|---------|-----|
| `feat:` | Nova funcionalidade |
| `fix:` | Correção de bug |
| `docs:` | Documentação |
| `test:` | Testes |
| `refactor:` | Refatoração |
| `chore:` | Manutenção |

Exemplos:

```
feat: adiciona suporte a backup incremental
fix: corrige timeout em conexões SMTP
docs: atualiza guia de instalação
test: adiciona testes para CleanerTask
```

## Testes

### Executar Testes

```bash
# Todos
pytest

# Com cobertura
pytest --cov=src/autotarefas --cov-report=html

# Verbose
pytest -v

# Teste específico
pytest tests/test_backup.py::test_backup_compress -v

# Por marcador
pytest -m "not slow"
pytest -m integration
```

### Escrever Testes

```python
import pytest
from autotarefas.tasks import BackupTask

class TestBackupTask:
    """Testes para BackupTask."""

    def test_backup_simple(self, tmp_path):
        """Testa backup simples."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("test")

        dest = tmp_path / "backup"
        dest.mkdir()

        task = BackupTask(source=source, destination=dest)
        result = task.run()

        assert result.success
        assert result.data["files_count"] == 1

    @pytest.mark.slow
    def test_backup_large(self, tmp_path):
        """Testa backup com muitos arquivos."""
        ...

    @pytest.fixture
    def backup_task(self, tmp_path):
        """Fixture para BackupTask."""
        return BackupTask(
            source=tmp_path / "source",
            destination=tmp_path / "dest"
        )
```

### Cobertura

Mantemos cobertura mínima de **80%**:

```bash
pytest --cov=src/autotarefas --cov-fail-under=80
```

## Pull Requests

### Checklist

- [ ] Testes passando
- [ ] Cobertura adequada
- [ ] Código formatado (ruff)
- [ ] Type hints adicionados
- [ ] Docstrings atualizadas
- [ ] CHANGELOG atualizado (se necessário)
- [ ] Documentação atualizada (se necessário)

### Template

```markdown
## Descrição
Breve descrição das mudanças.

## Tipo de Mudança
- [ ] Bug fix
- [ ] Nova feature
- [ ] Breaking change
- [ ] Documentação

## Como Testar
Passos para testar as mudanças.

## Checklist
- [ ] Testes adicionados
- [ ] Documentação atualizada
```

## Releases

O processo de release é automatizado via GitHub Actions:

1. Atualizar versão: `python scripts/bump_version.py minor`
2. Atualizar CHANGELOG.md
3. Commit: `git commit -m "chore: bump version to X.Y.Z"`
4. Tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
5. Push: `git push origin main --tags`
6. GitHub Actions publica no PyPI automaticamente

## Dúvidas?

- Abra uma [Discussion](https://github.com/paulor007/autotarefas/discussions)
- Pergunte nas Issues relacionadas

Obrigado por contribuir! 🙏
