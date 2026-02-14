# 🛠️ Escolha de Tecnologias - AutoTarefas

**Versão:** 1.0
**Data:** Dezembro 2024
**Status:** ✅ Aprovado

---

## 1. Visão Geral

Este documento detalha todas as tecnologias escolhidas para o projeto AutoTarefas, incluindo justificativas técnicas, alternativas consideradas e critérios de decisão.

### 1.1 Critérios de Seleção

| Critério | Peso | Descrição |
|----------|------|-----------|
| **Maturidade** | Alto | Biblioteca estável, bem mantida, comunidade ativa |
| **Simplicidade** | Alto | API intuitiva, curva de aprendizado baixa |
| **Performance** | Médio | Adequada para o caso de uso |
| **Documentação** | Alto | Docs completas, exemplos práticos |
| **Dependências** | Médio | Poucas dependências transitivas |
| **Licença** | Alto | Compatível com MIT (projeto open source) |

---

## 2. Linguagem e Runtime

### 2.1 Python 3.12+

| Aspecto | Detalhe |
|---------|---------|
| **Versão Mínima** | 3.12 |
| **Versões Suportadas** | 3.12, 3.13, 3.14 |
| **Versão Estável Atual** | 3.14.2 |
| **Licença** | PSF License |

#### Por que Python?
- ✅ Excelente para automação e scripts
- ✅ Rico ecossistema de bibliotecas
- ✅ Sintaxe clara e legível
- ✅ Multiplataforma (Windows, Linux, macOS)
- ✅ Grande comunidade

#### Por que 3.12+?
- ✅ **Performance**: Melhorias significativas de velocidade
- ✅ **Error messages**: Mensagens de erro ainda melhores
- ✅ **Type hints**: Suporte completo a typing moderno (PEP 695)
- ✅ **tomllib**: Parsing TOML nativo (útil para configs)
- ✅ **f-strings melhorados**: Expressões mais flexíveis
- ✅ **Suporte de longo prazo**: 3.11 entra em security-only em 2027

#### Alternativas Descartadas

| Alternativa | Por que não? |
|-------------|--------------|
| Python 3.10/3.11 | Falta recursos modernos, EOL se aproximando |
| Rust | Curva de aprendizado alta, overkill para CLI |
| Go | Menos bibliotecas para automação desktop |
| Node.js | Menos natural para scripts de sistema |

---

## 3. Dependências Principais

### 3.1 CLI Framework: Click

```toml
click = ">=8.1.0,<9.0.0"
```

| Aspecto | Detalhe |
|---------|---------|
| **Versão Testada** | 8.3.1 |
| **Faixa Suportada** | >=8.1.0,<9.0.0 |
| **Licença** | BSD-3-Clause |
| **Mantido por** | Pallets (mesmos do Flask) |

#### Por que Click?

```python
# Exemplo: Sintaxe limpa com decorators
@click.command()
@click.option('--name', '-n', help='Nome do backup')
@click.option('--compress', is_flag=True, help='Comprimir arquivo')
@click.argument('source', type=click.Path(exists=True))
def backup(name, compress, source):
    """Cria um backup do diretório SOURCE."""
    pass
```

- ✅ **Decorators intuitivos**: Menos boilerplate
- ✅ **Grupos de comandos**: Estrutura `autotarefas backup run`
- ✅ **Validação automática**: Tipos, paths, choices
- ✅ **Help automático**: Gerado dos docstrings
- ✅ **Testável**: `CliRunner` para testes
- ✅ **Colorido**: Suporte a cores no terminal

#### Alternativas Descartadas

| Alternativa | Por que não? |
|-------------|--------------|
| `argparse` | Muito verboso, sem grupos nativos |
| `typer` | Baseado em Click, dependência extra desnecessária |
| `fire` | Mágico demais, menos controle |
| `docopt` | Menos flexível, parsing por docstring |

---

### 3.2 Interface Terminal: Rich

```toml
rich = ">=13.0.0,<15.0.0"
```

| Aspecto | Detalhe |
|---------|---------|
| **Versão Testada** | 14.2.0 |
| **Faixa Suportada** | >=13.0.0,<15.0.0 |
| **Licença** | MIT |
| **Mantido por** | Will McGugan (Textualize) |

#### Por que Rich?

```python
# Exemplo: Output bonito com pouco código
from rich.console import Console
from rich.table import Table
from rich.progress import track

console = Console()

# Tabela formatada
table = Table(title="Status do Sistema")
table.add_column("Métrica", style="cyan")
table.add_column("Valor", style="green")
table.add_row("CPU", "45%")
table.add_row("RAM", "2.1 GB")
console.print(table)

# Barra de progresso
for file in track(files, description="Processando..."):
    process(file)
```

- ✅ **Tabelas bonitas**: Formatação automática
- ✅ **Progress bars**: Múltiplos estilos
- ✅ **Syntax highlighting**: Código colorido
- ✅ **Markdown**: Renderiza MD no terminal
- ✅ **Panels e Trees**: Organização visual
- ✅ **Spinners**: Feedback em operações longas
- ✅ **Logging handler**: Integra com logging

#### Alternativas Descartadas

| Alternativa | Por que não? |
|-------------|--------------|
| `colorama` | Só cores, sem tabelas/progress |
| `termcolor` | Muito básico |
| `tqdm` | Só progress bars |
| `blessed` | API mais complexa |

---

### 3.3 Logging: Loguru

```toml
loguru = ">=0.7.0,<1.0.0"
```

| Aspecto | Detalhe |
|---------|---------|
| **Versão Testada** | 0.7.3 |
| **Faixa Suportada** | >=0.7.0,<1.0.0 |
| **Licença** | MIT |
| **Mantido por** | Delgan |

#### Por que Loguru?

```python
# Exemplo: Setup em 1 linha vs 10+ com logging stdlib
from loguru import logger

# Configuração simples
logger.add("app.log", rotation="10 MB", retention="7 days")

# Uso intuitivo
logger.info("Backup iniciado")
logger.success("Backup concluído em {time}s", time=elapsed)
logger.warning("Espaço em disco baixo: {free}GB", free=free_space)
logger.error("Falha ao conectar: {err}", err=str(e))

# Contexto automático
logger.bind(task="backup", user="admin").info("Operação executada")
```

- ✅ **Zero config**: Funciona out-of-the-box
- ✅ **Rotação automática**: Por tamanho ou tempo
- ✅ **Retenção**: Remove logs antigos automaticamente
- ✅ **Formatação rica**: Cores, ícones, estruturado
- ✅ **Exception handling**: Stack traces bonitos
- ✅ **Lazy evaluation**: `logger.debug("valor: {x}", x=func())` só executa se DEBUG
- ✅ **Thread-safe**: Seguro para uso concorrente

#### Alternativas Descartadas

| Alternativa | Por que não? |
|-------------|--------------|
| `logging` (stdlib) | Muito verboso, config complexa |
| `structlog` | Mais complexo, foco em JSON |
| `logbook` | Menos mantido |

---

### 3.4 Agendamento: Schedule

```toml
schedule = ">=1.2.0,<2.0.0"
```

| Aspecto | Detalhe |
|---------|---------|
| **Versão Testada** | 1.2.2 |
| **Faixa Suportada** | >=1.2.0,<2.0.0 |
| **Licença** | MIT |
| **Mantido por** | Dan Bader |

#### Por que Schedule?

```python
# Exemplo: API fluente e legível
import schedule

# Intervalos
schedule.every(10).minutes.do(backup_task)
schedule.every().hour.do(cleanup_task)

# Horários específicos
schedule.every().day.at("02:00").do(full_backup)
schedule.every().monday.at("09:00").do(weekly_report)

# Tags para gerenciamento
schedule.every().day.at("00:00").do(job).tag('backup', 'daily')
schedule.clear('backup')  # Remove todos com tag 'backup'

# Loop principal
while True:
    schedule.run_pending()
    time.sleep(1)
```

- ✅ **API fluente**: Lê como inglês
- ✅ **Leve**: Sem dependências
- ✅ **In-process**: Não precisa de daemon externo
- ✅ **Tags**: Organização de jobs
- ✅ **Flexível**: Intervalos e horários fixos

#### Limitações Conhecidas
- ⚠️ Não persiste entre reinícios (implementaremos JobStore)
- ⚠️ Não é distribuído (ok para uso local)
- ⚠️ Precisa de loop rodando (ok para CLI)

#### Alternativas Descartadas

| Alternativa | Por que não? |
|-------------|--------------|
| `APScheduler` | Mais complexo, mais features que precisamos |
| `celery` | Overkill, precisa de broker (Redis/RabbitMQ) |
| `cron` (sistema) | Menos portável, config externa |
| `rq` | Precisa de Redis |

---

### 3.5 Monitoramento: psutil

```toml
psutil = ">=5.9.0,<8.0.0"
```

| Aspecto | Detalhe |
|---------|---------|
| **Versão Testada** | 7.2.1 |
| **Faixa Suportada** | >=5.9.0,<8.0.0 |
| **Licença** | BSD-3-Clause |
| **Mantido por** | Giampaolo Rodola |

#### Por que psutil?

```python
# Exemplo: Acesso fácil a métricas do sistema
import psutil

# CPU
cpu_percent = psutil.cpu_percent(interval=1)
cpu_count = psutil.cpu_count()

# Memória
mem = psutil.virtual_memory()
print(f"Total: {mem.total}, Usado: {mem.used}, Livre: {mem.available}")

# Disco
disk = psutil.disk_usage('/')
print(f"Total: {disk.total}, Usado: {disk.used}, Livre: {disk.free}")

# Processos
for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
    print(proc.info)

# Rede
net = psutil.net_io_counters()
print(f"Enviado: {net.bytes_sent}, Recebido: {net.bytes_recv}")
```

- ✅ **Completo**: CPU, RAM, disco, rede, processos
- ✅ **Multiplataforma**: Windows, Linux, macOS, BSD
- ✅ **Maduro**: 10+ anos, muito estável
- ✅ **Performático**: Implementado em C
- ✅ **Bem documentado**: Exemplos para tudo

#### Alternativas Descartadas

| Alternativa | Por que não? |
|-------------|--------------|
| `/proc` direto | Só Linux, parsing manual |
| `os` + `shutil` | Incompleto, não tem CPU/RAM |
| `py-cpuinfo` | Só CPU |
| `memory_profiler` | Só memória do processo Python |

---

### 3.6 Variáveis de Ambiente: python-dotenv

```toml
python-dotenv = ">=1.0.0,<2.0.0"
```

| Aspecto | Detalhe |
|---------|---------|
| **Versão Testada** | 1.2.1 |
| **Faixa Suportada** | >=1.0.0,<2.0.0 |
| **Licença** | BSD-3-Clause |
| **Mantido por** | Saurabh Kumar |

#### Por que python-dotenv?

```python
# Exemplo: Carregamento automático de .env
from dotenv import load_dotenv
import os

load_dotenv()  # Carrega .env do diretório atual

# Agora disponível via os.environ
email_host = os.getenv('EMAIL_HOST', 'localhost')
email_port = int(os.getenv('EMAIL_PORT', '587'))
```

```bash
# Arquivo .env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=user@gmail.com
EMAIL_PASSWORD=app_password
```

- ✅ **Simples**: Uma função para carregar
- ✅ **Padrão da indústria**: Usado em quase todo projeto Python
- ✅ **Seguro**: Mantém secrets fora do código
- ✅ **Override**: Variáveis de ambiente reais têm precedência

#### Alternativas Descartadas

| Alternativa | Por que não? |
|-------------|--------------|
| `environs` | Mais features que precisamos |
| `dynaconf` | Complexo demais para nosso uso |
| Manual | Reinventar a roda |

---

## 4. Dependências de Desenvolvimento

### 4.1 Testes: pytest

```toml
pytest = ">=8.0.0,<10.0.0"
pytest-cov = ">=4.1.0,<8.0.0"
pytest-mock = ">=3.11.0,<4.0.0"
```

| Aspecto | Detalhe |
|---------|---------|
| **pytest Testada** | 9.0.2 |
| **pytest-cov Testada** | 7.0.0 |
| **pytest-mock Testada** | 3.15.1 |
| **Licença** | MIT |
| **Mantido por** | pytest-dev |

#### Por que pytest?

```python
# Exemplo: Testes limpos e expressivos
import pytest
from autotarefas.tasks.backup import BackupTask

# Fixtures reutilizáveis
@pytest.fixture
def temp_dir(tmp_path):
    """Cria estrutura de teste."""
    (tmp_path / "file1.txt").write_text("content")
    (tmp_path / "file2.txt").write_text("content")
    return tmp_path

# Teste simples
def test_backup_creates_zip(temp_dir):
    task = BackupTask(source=temp_dir, compress=True)
    result = task.run()

    assert result.status == TaskStatus.SUCCESS
    assert result.data['output_file'].endswith('.zip')

# Parametrização
@pytest.mark.parametrize("compress,ext", [
    (True, '.zip'),
    (False, '.tar'),
])
def test_backup_compression(temp_dir, compress, ext):
    task = BackupTask(source=temp_dir, compress=compress)
    result = task.run()
    assert result.data['output_file'].endswith(ext)
```

- ✅ **Fixtures**: Setup/teardown elegante
- ✅ **Parametrize**: Múltiplos inputs, um teste
- ✅ **Asserts simples**: Sem `self.assertEqual`
- ✅ **Plugins**: Enorme ecossistema
- ✅ **Discovery**: Encontra testes automaticamente

#### Plugins Utilizados

| Plugin | Propósito |
|--------|-----------|
| `pytest-cov` | Cobertura de código |
| `pytest-mock` | Mocking simplificado |
| `pytest-xdist` | Execução paralela (opcional) |

---

### 4.2 Linting: Ruff

```toml
ruff = ">=0.1.0"
```

| Aspecto | Detalhe |
|---------|---------|
| **Versão** | >= 0.1.0 |
| **Licença** | MIT |
| **Mantido por** | Astral (Charlie Marsh) |

#### Por que Ruff?

```bash
# 10-100x mais rápido que flake8 + isort + pyupgrade
$ ruff check .                    # Lint
$ ruff check . --fix              # Auto-fix
$ ruff format .                   # Formatação (substitui black)
```

- ✅ **Extremamente rápido**: Escrito em Rust
- ✅ **Tudo-em-um**: Substitui flake8, isort, pyupgrade, autoflake
- ✅ **Compatível**: Mesmas regras do flake8
- ✅ **Auto-fix**: Corrige automaticamente
- ✅ **Formatter**: Substitui Black também

#### Alternativas Descartadas

| Alternativa | Por que não? |
|-------------|--------------|
| `flake8` | Mais lento, menos features |
| `pylint` | Muito lento, verboso |
| `black` + `isort` | Ruff faz tudo |

---

### 4.3 Type Checking: mypy

```toml
mypy = ">=1.5.0"
```

| Aspecto | Detalhe |
|---------|---------|
| **Versão** | >= 1.5.0 |
| **Licença** | MIT |
| **Mantido por** | Python/Jukka Lehtosalo |

#### Por que mypy?

```python
# Exemplo: Tipos que mypy valida
from pathlib import Path
from typing import Optional

def backup_files(
    source: Path,
    destination: Path,
    compress: bool = True
) -> Optional[Path]:
    """
    Cria backup dos arquivos.

    Args:
        source: Diretório fonte
        destination: Diretório destino
        compress: Se deve comprimir

    Returns:
        Caminho do arquivo criado ou None se falhar
    """
    ...
```

```bash
$ mypy src/
Success: no issues found
```

- ✅ **Padrão da indústria**: Mais usado
- ✅ **Gradual**: Pode adotar incrementalmente
- ✅ **IDE integration**: VSCode, PyCharm entendem
- ✅ **Strict mode**: Para projetos novos

#### Alternativas Descartadas

| Alternativa | Por que não? |
|-------------|--------------|
| `pyright` | Bom, mas mypy é mais estabelecido |
| `pytype` | Menos popular |
| Nenhum | Tipos ajudam muito em manutenção |

---

## 5. Dependências Opcionais

### 5.1 Processamento de Dados: pandas

```toml
pandas = { version = ">=2.0.0,<3.0.0", optional = true }
openpyxl = { version = ">=3.1.0,<4.0.0", optional = true }
```

| Aspecto | Detalhe |
|---------|---------|
| **pandas Testada** | 2.3.3 |
| **Grupo** | `[project.optional-dependencies.reports]` |
| **Instalação** | `pip install autotarefas[reports]` |

#### Quando usar?
- Relatórios de vendas (SalesReportTask)
- Processamento de Excel/CSV
- Análise de dados

---

### 5.2 Templates: Jinja2

```toml
jinja2 = { version = ">=3.1.0,<4.0.0", optional = true }
```

| Aspecto | Detalhe |
|---------|---------|
| **Versão Testada** | 3.1.x |
| **Grupo** | `[project.optional-dependencies.email]` |
| **Instalação** | `pip install autotarefas[email]` |

#### Quando usar?
- Templates de email HTML
- Geração de relatórios formatados

---

## 6. Ferramentas de Build

### 6.1 Build Backend: Hatchling

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

| Aspecto | Detalhe |
|---------|---------|
| **Versão** | >= 1.18.0 |
| **Licença** | MIT |
| **Mantido por** | PyPA |

#### Por que Hatchling?
- ✅ **Moderno**: PEP 517/518/621 compliant
- ✅ **Rápido**: Builds mais rápidos que setuptools
- ✅ **Configurável**: Tudo no pyproject.toml
- ✅ **Versioning**: Suporte a version dinâmica

#### Alternativas Descartadas

| Alternativa | Por que não? |
|-------------|--------------|
| `setuptools` | Mais verboso, setup.py legado |
| `flit` | Menos features |
| `poetry` | Lock file, mais opinativo |

---

## 7. Documentação

### 7.1 Site de Docs: MkDocs + Material

```toml
mkdocs = ">=1.5.0,<2.0.0"
mkdocs-material = ">=9.4.0,<10.0.0"
```

| Aspecto | Detalhe |
|---------|---------|
| **mkdocs Testada** | 1.6.1 |
| **Licença** | MIT |
| **Output** | Site estático |

#### Por que MkDocs?

```yaml
# mkdocs.yml - Configuração simples
site_name: AutoTarefas
theme:
  name: material
  palette:
    primary: blue
nav:
  - Home: index.md
  - Instalação: installation.md
  - Tutoriais:
    - Backup: tutorials/backup.md
```

- ✅ **Markdown**: Fácil de escrever
- ✅ **Material theme**: Visual moderno
- ✅ **Search**: Busca client-side
- ✅ **GitHub Pages**: Deploy fácil

#### Alternativas Descartadas

| Alternativa | Por que não? |
|-------------|--------------|
| `Sphinx` | Mais complexo, RST por padrão |
| `docsify` | Menos features |
| `GitBook` | Pago para features avançadas |

---

## 8. CI/CD

### 8.1 GitHub Actions

| Workflow | Propósito |
|----------|-----------|
| `tests.yml` | Testes em matrix Python 3.11/3.12/3.13 |
| `lint.yml` | Ruff + mypy |
| `release.yml` | Build e publicação PyPI |

#### Por que GitHub Actions?
- ✅ **Integrado**: Já usamos GitHub
- ✅ **Gratuito**: Para projetos open source
- ✅ **Matrix builds**: Múltiplas versões Python
- ✅ **Marketplace**: Actions prontas

---

## 9. Persistência de Dados

### 9.1 Jobs Agendados: JSON

```python
# jobs.json - Formato legível e editável
{
    "jobs": [
        {
            "id": "uuid-here",
            "name": "backup-diario",
            "task_type": "backup",
            "schedule": {"type": "daily", "at": "02:00"},
            "config": {"source": "/home/user/docs"}
        }
    ]
}
```

#### Por que JSON?
- **Legível**: Usuário pode editar manualmente
- **Portável**: Fácil backup/restore
- **Simples**: stdlib, sem dependências

### 9.2 Histórico de Execuções: SQLite

```sql
-- Estrutura do banco
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    status TEXT,
    result_json TEXT,
    error TEXT
);
```

#### Por que SQLite?
- **Queries**: Filtros, ordenação, agregação
- **Performance**: Lida com milhares de registros
- **Stdlib**: `sqlite3` já vem no Python
- **Arquivo único**: Fácil backup

---

## 10. Matriz de Compatibilidade

### 10.1 Sistemas Operacionais

| SO | Versão | Status |
|----|--------|--------|
| Windows | 10, 11 | ✅ Suportado |
| Ubuntu | 20.04, 22.04, 24.04 | ✅ Suportado |
| macOS | 12+ (Monterey+) | ✅ Suportado |
| Debian | 11, 12 | ✅ Suportado |
| Fedora | 38, 39 | ✅ Suportado |

### 10.2 Python

| Versão | Status | Notas |
|--------|--------|-------|
| 3.11 | ❌ Não suportado | Usar 3.12+ |
| 3.12 | ✅ Suportado | Versão mínima |
| 3.13 | ✅ Suportado | Recomendado |
| 3.14 | ✅ Suportado | Mais recente (3.14.2) |

---

## 11. Resumo de Dependências

### 11.1 Estratégia de Versionamento

> ⚠️ **Importante:** Usamos **faixas de versão** (`>=min,<max`) ao invés de "sempre última versão" para evitar quebras de compatibilidade.

| Estratégia | Onde | Exemplo |
|------------|------|---------|
| **Faixa segura** | `pyproject.toml` | `click>=8.1.0,<9.0.0` |
| **Lock exato** | `requirements-lock.txt` | `click==8.3.1` |

**Por quê?**
- Uma versão nova pode quebrar compatibilidade
- Lock garante builds reproduzíveis
- Faixa permite atualizações de segurança

### 11.2 Dependências de Produção

```toml
[project]
requires-python = ">=3.12"
dependencies = [
    "click>=8.1.0,<9.0.0",           # CLI framework (testado: 8.3.1)
    "rich>=13.0.0,<15.0.0",          # Terminal UI (testado: 14.2.0)
    "loguru>=0.7.0,<1.0.0",          # Logging (testado: 0.7.3)
    "schedule>=1.2.0,<2.0.0",        # Agendamento (testado: 1.2.2)
    "psutil>=5.9.0,<8.0.0",          # Monitoramento (testado: 7.2.1)
    "python-dotenv>=1.0.0,<2.0.0",   # Config (testado: 1.2.1)
]
```

### 11.3 Dependências Opcionais

```toml
[project.optional-dependencies]
reports = [
    "pandas>=2.0.0,<3.0.0",          # (testado: 2.3.3)
    "openpyxl>=3.1.0,<4.0.0",        # Excel support
]
email = [
    "jinja2>=3.1.0,<4.0.0",          # Templates HTML
]
all = [
    "autotarefas[reports,email]",
]
```

### 11.4 Dependências de Desenvolvimento

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0,<10.0.0",         # (testado: 9.0.2)
    "pytest-cov>=4.1.0,<8.0.0",      # (testado: 7.0.0)
    "pytest-mock>=3.11.0,<4.0.0",    # (testado: 3.15.1)
    "ruff>=0.1.0,<1.0.0",            # Linting
    "mypy>=1.5.0,<2.0.0",            # Type checking
    "pre-commit>=3.4.0,<4.0.0",      # Git hooks
]
docs = [
    "mkdocs>=1.5.0,<2.0.0",          # (testado: 1.6.1)
    "mkdocs-material>=9.4.0,<10.0.0",
]
```

### 11.5 Arquivo de Lock (para desenvolvimento)

```bash
# Gerar lock das versões exatas instaladas
pip freeze > requirements-lock.txt

# Instalar versões exatas do lock
pip install -r requirements-lock.txt
```

**Exemplo de `requirements-lock.txt`:**
```
click==8.3.1
rich==14.2.0
loguru==0.7.3
schedule==1.2.2
psutil==7.2.1
python-dotenv==1.2.1
pytest==9.0.2
pytest-cov==7.0.0
pytest-mock==3.15.1
pandas==2.3.3
mkdocs==1.6.1
```

### 11.6 Comandos de Instalação

```bash
# Instalação básica
pip install autotarefas

# Com suporte a relatórios Excel
pip install autotarefas[reports]

# Com suporte a email com templates
pip install autotarefas[email]

# Tudo incluído
pip install autotarefas[all]

# Para desenvolvimento (com versões exatas)
pip install -e ".[dev,docs]"
pip freeze > requirements-lock.txt

# Ou usando lock existente
pip install -r requirements-lock.txt
```

---

## 12. Diagrama de Dependências

```
┌─────────────────────────────────────────────────────────────────┐
│                      AUTOTAREFAS                                 │
│                   Python >=3.12                                  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 DEPENDÊNCIAS CORE                        │   │
│  │                                                          │   │
│  │   click >=8.1,<9       ─────► CLI Framework             │   │
│  │   rich >=13,<15        ─────► Terminal UI               │   │
│  │   loguru >=0.7,<1      ─────► Logging                   │   │
│  │   schedule >=1.2,<2    ─────► Agendamento               │   │
│  │   psutil >=5.9,<8      ─────► Monitoramento             │   │
│  │   python-dotenv >=1,<2 ─────► Configuração              │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 OPCIONAIS                                │   │
│  │                                                          │   │
│  │   [reports]     pandas >=2,<3 | openpyxl >=3.1,<4       │   │
│  │   [email]       jinja2 >=3.1,<4                         │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 DESENVOLVIMENTO                          │   │
│  │                                                          │   │
│  │   [dev]   pytest >=8,<10 | ruff | mypy | pre-commit     │   │
│  │   [docs]  mkdocs >=1.5,<2 | mkdocs-material            │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 LOCK (desenvolvimento)                   │   │
│  │                                                          │   │
│  │   requirements-lock.txt ─► Versões exatas testadas      │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|--------|------|-------|-----------|
| 1.0 | Dez/2025 | - | Versão inicial |
| 1.1 | Dez/2025 | - | Atualização de versões (verificadas em 31/dez/2025) |

---

## 14. Versões Verificadas (31/Dez/2025)

| Biblioteca | Versão PyPI |
|------------|-------------|
| click | 8.3.1 |
| rich | 14.2.0 |
| loguru | 0.7.3 |
| schedule | 1.2.2 |
| psutil | 7.2.1 |
| python-dotenv | 1.2.1 |
| pytest | 9.0.2 |
| pytest-cov | 7.0.0 |
| pytest-mock | 3.15.1 |
| pandas | 2.3.3 |
| mkdocs | 1.6.1 |
| Python (stable) | 3.14.2 |

---

*Documento gerado como parte da Fase 0.4 - Escolha de Tecnologias*
*Localização: `docs/planejamento/TECNOLOGIAS.md`*
