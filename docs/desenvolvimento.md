# Desenvolvimento

## Ambiente

```bash
git clone https://github.com/paulor007/autotarefas.git
cd autotarefas

python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1
# Linux/Mac: source venv/bin/activate

pip install -e ".[dev,demo]"
pre-commit install
```

## Qualidade — o que o CI exige

O pipeline (GitHub Actions) roda em Python 3.12 e 3.13. Você pode rodar os mesmos passos localmente:

```bash
ruff check .              # lint
ruff format --check .     # formatação
mypy src/                 # tipos (strict)
bandit -c pyproject.toml -r src   # segurança estática
pytest                    # testes + cobertura (mínimo 85%)
```

!!! tip "pre-commit"
Com `pre-commit install`, os hooks (ruff, ruff-format, mypy, bandit, detect-secrets) rodam automaticamente a cada commit — você raramente verá o CI falhar.

## Testes

```bash
pytest                              # tudo (com cobertura)
pytest tests/tasks/ -v              # só as tasks
pytest tests/tasks/test_sync_api.py # um arquivo
pytest -k "sync" --no-cov           # por palavra-chave
```

Convenções dos testes:

- I/O externo é **mockado** — `httpx` e `smtplib` por fakes; o navegador (Playwright) por `MagicMock`. Os testes não tocam a rede nem abrem browsers.
- Um `conftest.py` isola o audit DB em um diretório temporário por teste, então a suíte nunca grava no audit real.
- Marker `e2e` reservado para testes end-to-end reais (que subiriam browser).

## Ambientes de teste local

Para testar manualmente os comandos de API e email sem serviços externos:

```bash
# API de teste (origem/destino para extract, send, sync)
python -m tools.demo_server          # http://localhost:5555

# Servidor SMTP de debug (recebe emails sem enviar à internet)
python -m tools.smtp_debug           # localhost:8025
```

## Documentação

Esta documentação usa MkDocs Material:

```bash
mkdocs serve     # http://127.0.0.1:8000 (recarrega ao salvar)
mkdocs build     # gera o site estático em site/
```

A página [Referência (API)](referencia.md) é gerada automaticamente a partir das docstrings.

## Versionamento

A versão vive em um único lugar: `src/autotarefas/__init__.py` (o build lê de lá). Releases seguem [SemVer](https://semver.org/lang/pt-BR/) e o histórico fica no `CHANGELOG.md`.
