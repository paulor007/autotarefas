# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere a [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Não lançado]

Em desenvolvimento.

---

## [0.4.0] — 2026-05-23

🎉 **Segurança Transversal + Relatórios Consolidados!** Release que
**fortalece** as bases do projeto (Fase 6) e dá **voz** ao audit trail
que estava silenciosamente registrando tudo (Fase 7).

Este release adiciona **uma vulnerabilidade real corrigida** (path
traversal no organize), **documento profissional de segurança**
(SECURITY.md), e **comando novo** `autotarefas report` que gera
estatísticas, listas ou apenas falhas do histórico.

### Adicionado

#### Segurança Transversal (Fase 6)

- **`autotarefas.core.security`** — 4 helpers novos:
  - `validate_filename(name)`: 7 camadas defensivas (vazio, tamanho,
    path separators, traversal, chars de controle, chars proibidos
    Windows, nomes reservados CON/PRN/AUX/NUL/COM1-9/LPT1-9)
  - `safe_extension(filename, allowed)`: whitelist case-insensitive,
    detecta trick `.pdf.exe`
  - `is_within_directory(child, parent)`: versão "soft" do `safe_path`
    (retorna bool, não levanta exceção)
  - `mask_sensitive_in_dict(data)`: mascara CPF/CNPJ/senhas/tokens em
    dicts (recursivo, não modifica original, substring match)

- **Constantes privadas**: `_SENSITIVE_KEYS` (frozenset),
  `_WINDOWS_RESERVED_NAMES`, `_FORBIDDEN_FILENAME_CHARS`,
  `_MAX_FILENAME_LENGTH=255`

- **`SECURITY.md`** na raiz do repo:
  - Política de versões suportadas
  - Processo de reporting de vulnerabilidades (responsible disclosure)
  - **Threat model**: em escopo + fora de escopo + suposições
  - 13 princípios de segurança documentados
  - 4 camadas de proteção (filesystem, network, secrets, audit)
  - Hardening de dependências (`pip-audit`, `bandit`)
  - Best practices pra contribuidores (faça/evite)
  - GitHub auto-detecta o arquivo e exibe na aba Security

#### Vulnerabilidade real corrigida

- **`tasks/organize.py`** — Path traversal via destination malicioso:
  rule com `destination: "../../etc"` poderia mover arquivos pra fora
  de `target_root`. **Corrigido** com `safe_path` em
  `_resolve_destination`.

#### Relatórios Consolidados (Fase 7)

- **`autotarefas.tasks.report_audit`** — Task de relatórios:
  - `ReportAuditTask(BaseTask)`: quarta subclasse real
  - `ReportFilters` (dataclass frozen+slots) com `__post_init__`:
    validações de `limit > 0` e `since < until`
  - `ReportType = Literal["summary", "list", "errors"]`
  - 3 tipos de relatório:
    - `summary` (default): contagens, médias, falhas recentes
    - `list`: lista detalhada de execuções
    - `errors`: apenas execuções com falha (`failure` + `partial`)
  - Filtros: `task_name`, `status`, `since`, `until`, `limit` (default 100)
  - **Read-only**: apenas `SELECT`s no audit DB (princípio append-only
    preservado)
  - `TaskStatus.SKIPPED` quando audit DB não existe (não é erro)
  - SQL parametrizado anti-injection com `WHERE 1=1` + `AND` condicional
  - Aggregations: `by_task`, `by_status`, `by_task_and_status`
    (cross-tab), `avg_duration_ms_by_task` (round 2 casas)
  - `recent_failures`: top 5 com `status` em `failure`/`partial`
  - `audit_db_path` opcional no construtor (backward-compatible)

- **Comando `autotarefas report`**:
  - `autotarefas report` (summary das últimas 24h por default)
  - `--task NAME`, `--status STATUS`, `--days N`, `--since DATE`,
    `--until DATE`
  - `--type summary | list | errors`
  - `--format table | json | csv`
  - `--output PATH` (salva em arquivo)
  - `--limit N`
  - Tabelas formatadas manualmente (portável, sem deps de Rich Table)
  - `_format_size()` humaniza durações (`450ms`, `1.20s`)
  - `--since` sobrescreve `--days`
  - `tzinfo=UTC` automático em datetimes do Click
  - Dry-run mostra no terminal sem salvar arquivo
  - Aviso quando truncar em `--limit`
  - Exit codes: 0 (sucesso/skipped), 1 (falha), 2 (filtros inválidos)

### Estatísticas

- **~610 testes** (vs ~485 em v0.3.0), cobertura mantida
- **~5400 linhas de código** em src/ (vs ~4500)
- **4 subclasses de BaseTask** (Validate, Backup, Organize, ReportAudit)
- **6 comandos CLI** (info, init, validate, backup, organize, report)
- **0 erros** em mypy strict, ruff, bandit
- **+1 documento** profissional (SECURITY.md)

### Lições aprendidas notáveis

- **`# pragma: allowlist secret`** marca falso positivo do
  `detect-secrets` (use em testes com dados claramente fake)
- **Ruff vs Bandit em supressão**: ferramentas distintas, comentários
  distintos. Pra mesma regra, use ambos: `# noqa: S608 # nosec B608`
- **Pydantic computed properties** bloqueiam `monkeypatch.setattr` no
  objeto. Solução: substituir o nome do módulo
  (`monkeypatch.setattr("modulo.atributo", fake)`)
- **Click subcommands precisam de grupo pai** pro `ctx.obj` ser criado.
  Em testes, sempre `runner.invoke(cli, ["subcomando", ...])`
- **Fixture `autouse=True` idempotente** registra comando antes do
  `main.py` ser atualizado
- **`WHERE 1=1` + `AND` condicional** simplifica concatenação SQL
- **Placeholders dinâmicos** pra `IN (?, ?)`:
  `",".join("?" * len(items))`
- **`AVG()` ignora NULL** automaticamente em SQL
- **`SKIPPED` ≠ erro** (DB ausente é informação, não falha)

---

## [0.3.0] — 2026-05-21

🎉 **Backup + Organizador!** Dois novos casos de uso essenciais para
automação operacional.

### Adicionado

#### Backup de Arquivos (Fase 4)

- `tasks/backup.py` com `BackupTask`, ZIP DEFLATED + SHA-256
- 17 excludes padrão (caches, VCS, IDEs)
- Comando `autotarefas backup` com `--exclude`, `--no-default-excludes`

#### Organizador de Arquivos (Fase 5)

- `tasks/organize.py` com `OrganizeTask`, `Rule`, `RuleSet`
- Variáveis no destination: `{year}`, `{month:02d}`, `{day:02d}`, `{ext}`
- 3 conflict strategies: `skip`/`rename`/`overwrite`
- Comando `autotarefas organize` com confirmação em massa interativa

### Estatísticas

- ~485 testes, ~4500 linhas

---

## [0.2.0] — 2026-05-18

🎉 **Validador de planilhas** completo! Primeira task real do projeto.

### Adicionado

#### Validador de Planilhas (Fase 3)

- `tasks/issues`, `tasks/validators_br`, `tasks/validators`,
  `tasks/validate`, `tasks/report`
- Comando `autotarefas validate` com `--report-json`, `--report-csv`

### Estatísticas

- ~340 testes

---

## [0.1.0] — 2026-05-15

🎉 **Primeiro release público.** Fundação completa: core, CLI base
com 2 comandos, ~220 testes.

### Adicionado

#### Core (Fase 1)

- `core/settings`, `core/logger`, `core/exceptions`, `core/base`,
  `core/audit`, `core/security`

#### CLI (Fase 2)

- Grupo raiz com `--verbose`, `--quiet`, `--dry-run`, `--yes`, `--version`
- Comandos `info` e `init`

### Estatísticas

- ~220 testes, cobertura 98.87%

---

[Não lançado]: https://github.com/paulor007/autotarefas/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.4.0
[0.3.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.3.0
[0.2.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.2.0
[0.1.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.1.0
