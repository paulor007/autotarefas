# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere a [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Não lançado]

Em desenvolvimento.

---

## [0.2.0] — 2026-05-18

🎉 **Validador de planilhas** completo! Primeira task real do projeto.

Este release transforma o AutoTarefas de "fundação + CLI" para uma
ferramenta com **caso de uso real**: validar planilhas CSV/Excel
contra schemas YAML declarativos com regras de negócio brasileiras.

### Adicionado

#### Validador de Planilhas (Fase 3)

- **`autotarefas.tasks.issues`** — Sistema de issues estruturados:
  - `ValidationIssue` (frozen dataclass): linha, coluna, mensagem, severidade
  - `IssueSeverity` (StrEnum): ERROR ou WARNING
  - `IssueCollector`: acumula issues sem parar na primeira falha

- **`autotarefas.tasks.validators_br`** — Validadores brasileiros:
  - `is_valid_cpf()`: algoritmo módulo 11, blacklist de identificadores uniformes
  - `is_valid_cnpj()`: algoritmo módulo 11, blacklist
  - Aceitam com ou sem máscara (`123.456.789-09` ou `12345678909`)

- **`autotarefas.tasks.validators`** — Validadores genéricos:
  - `Validator` (Protocol PEP 544): interface comum sem herança forçada
  - `TypeValidator`: int, float (aceita decimal BR), date (ISO), bool (pt/en/numeric)
  - `RegexValidator`: regex compilada com `re.fullmatch`
  - `RangeValidator`: min/max numéricos, ignora não-números
  - `EnumValidator`: lista de aceitos, case-sensitive opcional
  - `CPFValidator` / `CNPJValidator`: wrappers dos validadores brasileiros
  - Todos `@dataclass(frozen=True, slots=True)` — imutáveis, leves

- **`autotarefas.tasks.validate`** — Task principal:
  - `ColumnSchema` (pydantic): nome, required, type, nullable, min/max_value,
    regex, enum_values, validator_br
  - `Schema`: lista de columns com properties `column_names`, `required_columns`
  - `load_schema(path)`: carrega de YAML com validação
  - `ValidateTask(BaseTask)`: primeira subclasse real de BaseTask
  - Validação em 2 fases: estrutura (extensão, colunas) + conteúdo (célula-a-célula)
  - Auto-detecção de encoding (utf-8-sig, latin-1, cp1252)
  - Auto-detecção de delimitador (csv.Sniffer restrito a `,;\t|`)
  - Suporte: `.csv`, `.tsv`, `.xlsx`, `.xls`

- **`autotarefas.tasks.report`** — Geração de relatórios:
  - `write_json_report()`: JSON estruturado UTF-8 com `ensure_ascii=False`
  - `write_csv_report()`: CSV com BOM UTF-8 (Excel-friendly)
  - `generate_summary()`: resumo textual com truncamento configurável

#### CLI (Fase 3)

- **Comando `autotarefas validate`**:
  - `autotarefas validate ARQUIVO --schema SCHEMA.yaml`
  - `--report-json PATH` — salva relatório JSON
  - `--report-csv PATH` — salva relatório CSV (compatível Excel)
  - `--max-issues N` — limita issues mostrados no terminal (default 10)
  - `--strict-warnings` — trata warnings como erros (exit 1)
  - Respeita `--dry-run` global (não cria arquivos)
  - Audit trail automático via BaseTask
  - Exit codes: 0 (válido), 1 (validação falhou), 2 (erro de uso)

### Mudado

- **`cli/main.py`**: agora aceita `-h` como atalho de `--help` (convenção Unix)

### Estatísticas

- **~340 testes** (vs ~220 em v0.1.0), cobertura mantida
- **~3000 linhas de código** em src/ (vs ~1100)
- **6 tipos de validadores**
- **2 validadores brasileiros** (CPF, CNPJ)
- **0 erros** em mypy strict, ruff, bandit

### Lições aprendidas notáveis

- `pd.read_csv(sep=None)` é perigoso — aceita qualquer caractere como delimitador
- `csv.Sniffer` com delimitadores explícitos é a forma correta
- Em Pydantic v2 + mypy strict, prefira defaults Python diretos a `Field(default, ...)`
- `pandas.read_csv` descarta linhas totalmente vazias por padrão
- Em pytest sem `__init__.py`, nomes de arquivos devem ser únicos globalmente

---

## [0.1.0] — 2026-05-15

🎉 **Primeiro release público.** Estabelece a fundação do projeto:
core completo, CLI base com 2 comandos, ~220 testes, cobertura ≥ 90%.

> ⚠️ **Status**: Pré-release. API ainda pode mudar nos próximos releases
> menores. Não recomendado pra uso em produção ainda.

### Adicionado

#### Core (Fase 1)

- **`autotarefas.core.settings`** — Configurações via `.env` com
  pydantic-settings, `SecretStr` para senhas.
- **`autotarefas.core.logger`** — Logging com loguru e mascaramento
  automático de dados sensíveis (CPF, CNPJ, senhas, tokens, emails).
- **`autotarefas.core.exceptions`** — Hierarquia de 9 exceções customizadas.
- **`autotarefas.core.base`** — `BaseTask` (Template Method), `TaskResult`
  (frozen dataclass), `TaskStatus` (StrEnum).
- **`autotarefas.core.audit`** — Audit Trail SQLite append-only com
  HMAC-SHA256.
- **`autotarefas.core.security`** — `safe_path`, `validate_url`, `hash_string`.

#### CLI (Fase 2)

- Grupo raiz `autotarefas` com opções globais (`--verbose`, `--quiet`,
  `--dry-run`, `--yes`, `--version`).
- Comandos `info` e `init`.
- `Console` (Rich wrapper) e helpers de confirmação.
- Entry point `python -m autotarefas`.

#### Infraestrutura (Fase 0)

- `pyproject.toml` com 25+ dependências.
- `mypy strict`, `ruff`, 14 hooks de pre-commit.
- Conventional Commits, `.gitignore`, `LICENSE` MIT.

### Estatísticas

- ~220 testes, cobertura 98.87%
- 13 princípios de segurança aplicados

---

[Não lançado]: https://github.com/paulor007/autotarefas/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.2.0
[0.1.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.1.0
