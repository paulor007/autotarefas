# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere a [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Não lançado]

Em desenvolvimento.

---

## [0.3.0] — 2026-05-21

🎉 **Backup + Organizador!** Dois novos casos de uso essenciais para
automação operacional.

Este release transforma o AutoTarefas em uma ferramenta versátil para
**manter dados seguros** (backup com hash) e **organizar arquivos
automaticamente** (regras YAML).

### Adicionado

#### Backup de Arquivos (Fase 4)

- **`autotarefas.tasks.backup`** — Task de compactação:
  - `BackupTask(BaseTask)`: segunda subclasse real
  - Compactação ZIP (algoritmo deflate, level 6)
  - Múltiplas fontes (pastas e/ou arquivos individuais)
  - 17 excludes padrão razoáveis: `__pycache__`, `*.pyc`, `.git`,
    `node_modules`, `.venv`, `.mypy_cache`, IDE configs, etc.
  - Excludes customizados via `fnmatch` (pattern shell)
  - Hash SHA-256 do ZIP final (calculado em chunks de 8KB para
    suportar arquivos grandes sem estourar RAM)
  - Estrutura preservada no ZIP (arcname inclui nome da source)
  - `TaskStatus.SKIPPED` quando não há arquivos a incluir
  - Operação **atômica**: se uma source falha, ZIP não é criado

- **Comando `autotarefas backup`**:
  - `autotarefas backup SOURCE [SOURCE ...] --output BACKUP.zip`
  - `--exclude PATTERN` (pode repetir): excludes customizados
  - `--no-default-excludes`: desabilita defaults (com aviso explícito)
  - Output humanizado: bytes formatados (B/KB/MB/GB)
  - Plural correto em português ("1 source" vs "2 sources")
  - Exit codes: 0 (sucesso/skipped/dry-run), 1 (falha), 2 (uso)

#### Organizador de Arquivos (Fase 5)

- **`autotarefas.tasks.organize`** — Task de organização:
  - `OrganizeTask(BaseTask)`: terceira subclasse real
  - `Rule` + `RuleSet` (Pydantic): regras declarativas em YAML
  - `load_rules()`: carrega YAML com 3 camadas de validação
  - **6 variáveis no destination**: `{year}`, `{month:02d}`, `{day:02d}`,
    `{ext}` (resolvidas a partir do mtime do arquivo)
  - **3 estratégias de conflito**:
    - `skip` (default): pula se destino existe
    - `rename`: gera `arquivo_1.ext`, `arquivo_2.ext`, etc.
    - `overwrite`: sobrescreve (perigoso!)
  - **2 actions**: `move` (default) ou `copy`
  - Primeira regra que bate ganha (ordem importa)
  - NÃO recursivo (só arquivos diretos do `source_dir`)
  - Audit detalhado: cada arquivo gera uma "operation" (limitado a 100)

- **Comando `autotarefas organize`**:
  - `autotarefas organize SOURCE_DIR --rules RULES.yaml`
  - **Confirmação interativa** se >N arquivos (default 50)
  - `--confirm-threshold N`: ajusta o threshold
  - `--no-confirm`: pula confirmação (mesmo acima do threshold)
  - `--yes/-y` global: também pula
  - **Proteção forte**: Enter sem digitar = cancela (default=False)
  - Cancelamento pelo usuário → exit 0 (não é erro)
  - `error_count > 0` → exit 1 (sinaliza pra CI)
  - Dry-run preliminar inteligente (só roda quando precisa)
  - Tags visuais no preview: `[OK]`, `[SKIP]`, `[ERR]`, `[N/A]`

### Mudado

- **`pyproject.toml`**: mantidos `ANN101`/`ANN102` no ignore do Ruff
  (compatibilidade com versões mais antigas do Ruff que ainda aplicam
  essas regras)

### Estatísticas

- **~485 testes** (vs ~340 em v0.2.0), cobertura mantida
- **~4500 linhas de código** em src/ (vs ~3000)
- **3 subclasses de BaseTask** (Validate, Backup, Organize)
- **5 comandos CLI** (info, init, validate, backup, organize)
- **0 erros** em mypy strict, ruff, bandit

### Lições aprendidas notáveis

- Em pytest sem `__init__.py`, **nomes de arquivos de teste devem ser
  únicos globalmente** (renomeado `test_backup.py` da CLI para `test_backup_cli.py`)
- `pip install -e ".[dev]"` necessário após bumps de versão
- Warnings do Ruff sobre "regras removidas" podem ser enganosos —
  verificar versão real antes de remover do `ignore`
- `CliRunner.invoke(input="y\n")` permite testar `click.confirm`
- Walrus operator `:=` é elegante para loops de leitura em chunks
- `fnmatch` deve ser aplicado em `path.parts`, não no path completo
- `pandas.read_csv` descarta linhas totalmente vazias por padrão
- Em Pydantic v2 + mypy strict, prefira defaults Python diretos a
  `Field(default, ...)`

---

## [0.2.0] — 2026-05-18

🎉 **Validador de planilhas** completo! Primeira task real do projeto.

### Adicionado

#### Validador de Planilhas (Fase 3)

- **`autotarefas.tasks.issues`** — `ValidationIssue`, `IssueSeverity`,
  `IssueCollector`
- **`autotarefas.tasks.validators_br`** — `is_valid_cpf`, `is_valid_cnpj`
  (algoritmo módulo 11)
- **`autotarefas.tasks.validators`** — Protocol `Validator` + 6 classes
  (Type, Regex, Range, Enum, CPF, CNPJ)
- **`autotarefas.tasks.validate`** — `ColumnSchema`, `Schema`,
  `ValidateTask(BaseTask)`, `load_schema()`
- **`autotarefas.tasks.report`** — `write_json_report`, `write_csv_report`,
  `generate_summary`
- **Comando `autotarefas validate`** com `--report-json`, `--report-csv`,
  `--max-issues`, `--strict-warnings`

### Mudado

- **`cli/main.py`**: aceita `-h` como atalho de `--help` (convenção Unix)

### Estatísticas

- ~340 testes, cobertura mantida

---

## [0.1.0] — 2026-05-15

🎉 **Primeiro release público.** Fundação completa: core, CLI base
com 2 comandos, ~220 testes.

### Adicionado

#### Core (Fase 1)

- **`autotarefas.core.settings`** — Configurações via `.env`
- **`autotarefas.core.logger`** — Logging com mascaramento automático
- **`autotarefas.core.exceptions`** — Hierarquia de 9 exceções
- **`autotarefas.core.base`** — `BaseTask` (Template Method), `TaskResult`
- **`autotarefas.core.audit`** — Audit Trail SQLite com HMAC-SHA256
- **`autotarefas.core.security`** — `safe_path`, `validate_url`, `hash_string`

#### CLI (Fase 2)

- Grupo raiz com `--verbose`, `--quiet`, `--dry-run`, `--yes`, `--version`
- Comandos `info` e `init`
- `Console` (Rich wrapper)
- Entry point `python -m autotarefas`

### Estatísticas

- ~220 testes, cobertura 98.87%
- 13 princípios de segurança aplicados

---

[Não lançado]: https://github.com/paulor007/autotarefas/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.3.0
[0.2.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.2.0
[0.1.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.1.0
