# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere a [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Não lançado]

Em desenvolvimento.

---

## [0.1.0] — 2026-05-15

🎉 **Primeiro release público.** Estabelece a fundação do projeto:
core completo, CLI base com 2 comandos, ~220 testes, cobertura ≥ 90%.

> ⚠️ **Status**: Pré-release. API ainda pode mudar nos próximos releases
> menores. Não recomendado pra uso em produção ainda.

### Adicionado

#### Core (Fase 1)

- **`autotarefas.core.settings`** — Configurações via `.env` com
  pydantic-settings, `SecretStr` para senhas, validação de ambientes
  (dev/demo/homolog/prod), Literal types.
- **`autotarefas.core.logger`** — Logging com loguru e mascaramento
  automático de dados sensíveis (CPF, CNPJ, senhas em PT/EN, tokens,
  emails). Rotação diária, retenção 30 dias.
- **`autotarefas.core.exceptions`** — Hierarquia de 9 exceções
  customizadas: `AutoTarefasError` (raiz), `ConfigError`,
  `ValidationError`, `SecurityError`, `AuditError`, `RPAError`,
  `LoginError`, `SelectorNotFoundError`, `RPATimeoutError`.
- **`autotarefas.core.base`** — Abstrações de Task:
  - `TaskStatus` (`StrEnum`): SUCCESS, FAILURE, PARTIAL, DRY_RUN, SKIPPED
  - `TaskResult` (dataclass `frozen`+`slots`): resultado imutável com
    timing, contadores de linhas, dados arbitrários
  - `BaseTask` (ABC): padrão **Template Method** com `execute()`,
    `pre_execute()`, `post_execute()` e validação de subclasses
- **`autotarefas.core.audit`** — Sistema de **Audit Trail** SQLite
  append-only com HMAC-SHA256 para integridade. Best-effort (falhas não
  propagam). Métodos `record()` e `query()`.
- **`autotarefas.core.security`** — Helpers de segurança:
  - `safe_path()` — proteção contra path traversal
  - `validate_url()` — HTTPS obrigatório em produção
  - `hash_string()` — SHA-256 e HMAC-SHA256

#### CLI (Fase 2)

- **Grupo raiz `autotarefas`** (Click) com opções globais:
  - `--verbose, -v` (cumulativo)
  - `--quiet, -q` (cumulativo)
  - `--dry-run` (simulação)
  - `--yes, -y` (assume sim em confirmações)
  - `--version` / `--help`
- **`CLIContext`** — dataclass compartilhada entre comandos com property
  derivada `log_level` (quiet tem prioridade sobre verbose).
- **`Console`** — wrapper Rich com 5 níveis (`info`, `success`, `warning`,
  `error`, `debug`) que respeitam verbose/quiet.
- **Helpers de confirmação**:
  - `confirm()` — sim/não simples
  - `confirm_bulk()` — **Princípio de Segurança 1.6**: exige escrita
    explícita do número de itens em massa
- **Comandos**:
  - `autotarefas info` — mostra informações do sistema
  - `autotarefas init` — inicializa estrutura em `~/.autotarefas/`
- **Entry point** `python -m autotarefas`.

#### Infraestrutura (Fase 0)

- `pyproject.toml` com 25+ dependências, hatchling backend.
- `mypy strict` configurado.
- `ruff` (lint + format) configurado.
- 14 hooks de **pre-commit**: ruff, mypy, bandit, detect-secrets,
  trim-whitespace, end-of-files, mixed-line-ending, check-yaml/toml/json,
  check-merge-conflicts, large-files, private-keys.
- Estrutura `src/` layout com testes em `tests/`.
- Conventional Commits adotado.
- `.gitignore`, `.env.example`, `LICENSE` (MIT).

### Estatísticas

- **~220 testes** passando, cobertura **98.87%**
- **13 princípios de segurança** documentados e aplicados
- **0 warnings** em pytest
- **0 erros** em mypy strict, ruff, bandit

---

[Não lançado]: https://github.com/paulor007/autotarefas/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.1.0
