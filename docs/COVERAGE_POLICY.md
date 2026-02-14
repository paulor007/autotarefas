# 📊 Política de Cobertura de Testes

Este documento define as regras e metas de cobertura de testes do AutoTarefas.

---

## 🎯 Meta de Cobertura

| Tipo | Meta | Obrigatório |
|------|------|-------------|
| **Global** | ≥ 80% | ✅ Sim |
| **Novos arquivos** | ≥ 80% | ✅ Sim |
| **Código crítico** | ≥ 90% | ⚠️ Recomendado |

### Código Crítico (meta 90%)
- `src/autotarefas/core/base.py`
- `src/autotarefas/core/scheduler.py`
- `src/autotarefas/tasks/backup.py`
- `src/autotarefas/tasks/cleaner.py`

---

## 🔧 Como Verificar a Cobertura

### Verificação Rápida
```bash
# Roda testes e mostra cobertura no terminal
pytest --cov=src/autotarefas --cov-report=term-missing
```

### Relatório HTML (Visual)
```bash
# Gera relatório em htmlcov/index.html
pytest --cov=src/autotarefas --cov-report=html

# Abrir no navegador
# Windows: start htmlcov\index.html
# Linux: xdg-open htmlcov/index.html
# Mac: open htmlcov/index.html
```

### Usando o Script
```bash
python scripts/check_coverage.py          # Verificação padrão
python scripts/check_coverage.py --html   # Com relatório HTML
python scripts/check_coverage.py --quick  # Apenas unitários
```

---

## 📁 O Que é Coberto

### ✅ Incluído na Cobertura
- `src/autotarefas/**/*.py` - Todo código fonte

### ❌ Excluído da Cobertura
- `tests/` - Arquivos de teste
- `*/__init__.py` - Arquivos de inicialização vazios
- `*/__pycache__/` - Cache do Python
- Linhas com `pragma: no cover`
- Linhas com `if TYPE_CHECKING:`
- Métodos `__repr__` e `__str__`
- `raise NotImplementedError`

---

## 📝 Linhas que Podem Ser Ignoradas

Use `# pragma: no cover` apenas quando fizer sentido:

```python
# ✅ OK - Código de debug que nunca roda em produção
if DEBUG:  # pragma: no cover
    print("Debug info")

# ✅ OK - Tratamento de erro impossível de testar
except SomeRareException:  # pragma: no cover
    log.error("Erro raro")

# ❌ NÃO OK - Ignorar código importante
def funcao_importante():  # pragma: no cover  ← NÃO FAÇA ISSO
    ...
```

---

## 🚦 O Que Acontece se Cobertura Cair

### No Desenvolvimento Local
```bash
$ pytest --cov=src/autotarefas --cov-fail-under=80

# Se cobertura < 80%:
FAIL Required test coverage of 80.0% not reached. Total coverage: 75.2%
```

### No CI/CD (GitHub Actions)
- ❌ Pull Request é bloqueado
- ❌ Merge não é permitido
- 📧 Notificação é enviada

---

## 📈 Como Melhorar a Cobertura

### 1. Identificar Arquivos com Baixa Cobertura
```bash
pytest --cov=src/autotarefas --cov-report=term-missing
```

Procure por linhas como:
```
src/autotarefas/tasks/backup.py    156    23    85%   45-50, 78-82
                                   ↑      ↑     ↑     ↑
                                   total  miss  %     linhas não cobertas
```

### 2. Ver Detalhes no HTML
```bash
pytest --cov=src/autotarefas --cov-report=html
# Abrir htmlcov/index.html
```

Linhas vermelhas = não testadas

### 3. Adicionar Testes
```python
# Exemplo: testar linha 45-50 do backup.py
def test_backup_com_erro():
    """Testa comportamento quando backup falha."""
    # Seu teste aqui
    ...
```

---

## 📋 Checklist para Pull Requests

Antes de abrir um PR, verifique:

- [ ] `pytest --cov` passa sem erros
- [ ] Cobertura total ≥ 80%
- [ ] Novos arquivos têm cobertura ≥ 80%
- [ ] Não há `# pragma: no cover` desnecessários

---

## 🔗 Arquivos de Configuração

| Arquivo | Descrição |
|---------|-----------|
| `pyproject.toml` | Configuração principal (seção `[tool.coverage.*]`) |
| `.coveragerc` | Configuração alternativa (compatibilidade) |
| `scripts/check_coverage.py` | Script para verificar cobertura |

---

## 📚 Referências

- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
