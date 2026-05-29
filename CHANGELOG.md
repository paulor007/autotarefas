# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere a [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Não lançado]

Em desenvolvimento. Próxima fase: extração de dados (API + Browser).

---

## [0.5.0] — 2026-05-28

🤖 **Automação Web (RPA) + Sistema Demo!** O AutoTarefas deixa de ser
apenas utilidades de arquivos e vira um **robô de automação web**
(Fase 8). Agora cadastra registros em sistemas web a partir de uma
planilha, usando um navegador real.

Este release também **corrige um bug crítico** descoberto durante o
desenvolvimento: o audit trail não estava registrando as tasks reais
(`validate`, `backup`, `organize`, etc.) — apenas comandos legados como
`init`. A descoberta veio justamente ao usar o `report` da v0.4.0 contra
o histórico de uma execução de RPA.

### Adicionado

#### Sistema Demo Local (Fase 8 etapa 1)

- **`tools/demo_server/`** — mini servidor Flask que simula um sistema
  de cadastro corporativo, usado como **alvo controlado** das automações
  durante o desenvolvimento (ninguém é prejudicado se quebrar):
  - Endpoints: `/` (landing), `/cadastro` (GET form / POST cria),
    `/sucesso/<id>`, `/cadastros` (lista JSON), `/limpar` (reset),
    `/health` (health check)
  - Validações server-side: nome (≥3 chars), email (regex), CPF
    (formato `XXX.XXX.XXX-XX`), telefone opcional (`(XX) XXXXX-XXXX`)
  - Storage local em JSON com `threading.Lock` (suporta requests
    paralelos)
  - IDs sequenciais e seletores estáveis (`#btn-cadastrar`,
    `#record-id`) pensados para a automação
  - Roda com `python -m tools.demo_server` em http://localhost:5555
  - Pasta `tools/` fica **fora** de `src/` (não é parte do pacote)

#### Wrapper Playwright (Fase 8 etapa 2)

- **`autotarefas.core.browser`** — abstração sobre o Playwright:
  - `BrowserSession`: context manager com cleanup garantido (browser
    fecha mesmo em erro)
  - Helpers de navegação: `go_to`, `fill`, `click`, `wait_for`
  - Helpers de inspeção: `text`, `is_visible`, `current_url`
  - Screenshots normais e com **mascaramento automático** de campos
    sensíveis (mask nativo do Playwright cobre CPF/CNPJ/senha/token/
    cartão com cor sólida, sem modificar o DOM real)
  - 11 seletores sensíveis default (case-insensitive)
  - Suporta Chromium (default), Firefox, WebKit; headless por default
    com flag para modo headful
  - `verify_playwright_installed()`: helper de troubleshooting
  - **Não** exportado em `core/__init__.py` (evita quebrar projetos sem
    o extra `[rpa]` instalado)

#### RPA Cadastro (Fase 8 etapa 3)

- **`autotarefas.tasks.rpa_cadastro`** — quinta task real:
  - `RPACadastroTask(BaseTask)`: lê planilha CSV/XLSX e cadastra cada
    linha em um sistema web
  - **Health check** via `httpx` antes de iniciar (servidor offline →
    `SKIPPED`, não tenta nada)
  - **Tolerante a falhas por linha**: uma linha ruim não interrompe as
    demais
  - Validação local de CPF (reusa `validators_br` da Fase 3) antes de
    gastar I/O com o browser
  - Status por linha: `success` / `skipped` / `error`
  - **CPF inválido** → `skipped`; **CPF duplicado** (detectado pela
    resposta do servidor) → `skipped`; **erro técnico** → `error` +
    screenshot mascarada automática
  - `dry_run` não abre browser nem faz requests (pula health check) —
    apenas valida e simula (`would_create`/`would_skip`)
  - Limite de 100 operations no `result.data` (audit não infla)
  - Callback `on_progress` opcional para progresso em tempo real
  - Status agregado: `SUCCESS` / `PARTIAL` / `FAILURE` / `SKIPPED`

#### Comando CLI (Fase 8 etapa 4)

- **Grupo `rpa`** preparado para subcomandos futuros (`consulta`,
  `exportar`)
- **Comando `autotarefas rpa cadastro`**:
  - `--planilha, -p`, `--site, -s`
  - `--show-browser` (mostra navegador; default headless)
  - `--no-screenshot` (desabilita screenshots em erro)
  - `--allow-remote` (permite URLs não-locais)
  - Progresso linha a linha em tempo real + sumário formatado ao final
  - Exit codes: `0` (success/partial/skipped), `1` (failure), `2` (erro
    de uso: URL inválida, etc.)

#### Testes (Fase 8 etapa 5)

- **~118 testes novos** cobrindo toda a fase, sem abrir browser real:
  - Demo server (Flask `test_client`, storage com `tmp_path`,
    concorrência com threads)
  - `BrowserSession` (Playwright 100% mockado)
  - `RPACadastroTask` (mock de `BrowserSession` e `httpx`, CSVs reais)
  - Comando CLI (`CliRunner` via grupo principal, mock da task)
  - Integração de audit no `BaseTask`

### Corrigido

- **Audit trail uniforme** — `BaseTask.run()` agora chama
  `_record_audit()` automaticamente. Antes, **apenas comandos legados**
  (como `init`) gravavam no audit; tasks que herdam de `BaseTask`
  (`validate`, `backup`, `organize`, `report_audit`, `rpa_cadastro`)
  **não eram registradas** — bug presente desde a Fase 1, mascarado
  porque nenhum consumidor lia o audit até a Fase 7. Agora toda execução
  (sucesso, falha, parcial, dry-run, skipped) é auditada. Erro na
  gravação do audit não interrompe a task (try/except defensivo).

### Segurança

- **RPA restrito a hosts locais por default** — o comando `rpa cadastro`
  só aceita URLs `localhost`/`127.0.0.1`/`::1` salvo uso explícito de
  `--allow-remote` (fail-safe default: automação contra sistema real
  exige ação consciente do operador)
- **Mascaramento de campos sensíveis em screenshots** — capturas de tela
  cobrem automaticamente CPF, CNPJ, senha, token, cartão etc., evitando
  vazamento de dados em imagens de debug

### Dependências

- Novo extra opcional **`demo`**: `flask>=3.0` (servidor demo, apenas
  desenvolvimento)
- Novo extra opcional **`rpa`**: `playwright>=1.40` (automação web).
  Requer `playwright install chromium` após instalar.

### Estatísticas

- **~720 testes** (vs ~610 em v0.4.0)
- **5 subclasses de BaseTask** (Validate, Backup, Organize, ReportAudit,
  **RPACadastro**)
- **7 comandos CLI** (info, init, validate, backup, organize, report,
  **rpa**)
- **0 erros** em mypy strict, ruff, bandit
- Servidor demo + wrapper de browser reutilizável

### Lições aprendidas notáveis

- **Audit no caminho crítico, não opcional**: features centrais
  (auditoria, segurança) devem estar no _template method_ da classe
  base, não em hooks que cada subclasse pode esquecer. Features que
  produzem dados sem consumidor mascaram bugs por muito tempo —
  construir o consumidor cedo (o `report`) forçou a integridade.
- **`@pytest.mark.usefixtures("_fixture")`** para fixtures _side-effect_
  (que só fazem `monkeypatch` e retornam `None`): resolve `PT004`
  (prefixo `_`) e `PT019` (não injetar como parâmetro) de uma vez.
- **`importlib.import_module("pkg.module")`** quando o pacote só exporta
  `__all__`: evita o erro do mypy "does not explicitly export" e deixa
  claro que se quer o **módulo** (para `monkeypatch`), não um atributo.
- **`pythonpath = [".", "src"]`** no pytest quando há código fora de
  `src/` (como `tools/`).
- **Cobertura de um arquivo**: usar `--cov=src/pkg/module` (caminho), não
  `--cov=pkg.module.name` (nome pontilhado, que pode dar `KeyError` no
  import durante o tracking).
- **`cast(T, valor)` > `# type: ignore[no-any-return]`** ao retornar
  valor de um `dict[str, Any]`.
- **`PT022`**: fixture com `yield` sem teardown deve usar `return` (e o
  tipo de retorno muda de `Generator[...]` para o tipo direto).
- **Mock encadeado do Playwright**: `monkeypatch.setattr` em
  `sync_playwright` no módulo permite testar `BrowserSession` sem abrir
  browser real (CI não precisa de `playwright install`).
- **`mask` nativo do Playwright** cobre regiões da página na screenshot
  sem modificar o DOM — mais limpo que injetar CSS.
- **`curl` no PowerShell** é alias de `Invoke-WebRequest` (sintaxe
  diferente); usar `curl.exe` ou `Invoke-RestMethod` para testar APIs.
- **CPF duplicado = `skipped`, não `error`**: erro de RPA é falha técnica
  (timeout, crash); dado ruim é responsabilidade do operador.

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

[Não lançado]: https://github.com/paulor007/autotarefas/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.5.0
[0.4.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.4.0
[0.3.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.3.0
[0.2.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.2.0
[0.1.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.1.0
