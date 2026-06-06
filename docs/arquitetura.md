# Arquitetura

O AutoTarefas é construído sobre poucos conceitos, combinados de forma consistente.

## BaseTask — o coração

Toda funcionalidade é uma **task** que herda de `BaseTask`. A subclasse implementa apenas `execute()`; a base cuida do resto.

```python
class MinhaTask(BaseTask):
    name = "minha_task"

    def execute(self) -> TaskResult:
        # lógica aqui
        return self._make_result(status=TaskStatus.SUCCESS, started_at=..., rows_affected=10)
```

Ao chamar `run()`, a base:

1. Loga o início (e o modo: real ou dry-run)
2. Executa `pre_execute()` → `execute()` → `post_execute()`
3. **Grava o audit trail** automaticamente
4. Captura erros previstos (`AutoTarefasError`) e devolve um `TaskResult` com `FAILURE`
5. Loga o fim

Isso significa que toda task ganha logging, audit e tratamento de erro **de graça** — sem repetição.

## TaskResult — resultado padronizado

Todo `execute()` devolve um `TaskResult` imutável (`frozen`), com: `status`, tempos, `rows_affected`, `rows_failed`, `data` (extras) e mensagens de erro. Os status possíveis:

- **SUCCESS** — tudo certo
- **PARTIAL** — parte funcionou, parte falhou (típico em operações em massa)
- **FAILURE** — nada concluído
- **DRY_RUN** / **SKIPPED** — variações de execução

## Composição de tasks

Tasks podem ser combinadas. A `SyncApiTask` é o melhor exemplo: ela **não reimplementa** HTTP nem paginação — apenas orquestra `ExtractApiTask` e `SendApiTask`, ligadas por um arquivo intermediário temporário.

```text
sync api  =  extract api  →  [arquivo temporário]  →  send api
```

Esse design modular (peças pequenas que se combinam) é o que mantém o código simples mesmo com 9 tasks.

## Audit Trail

Cada execução é registrada em um SQLite **append-only** (`~/.autotarefas/audit.db`): nunca há UPDATE ou DELETE — o histórico é imutável por design.

- Falhas no audit **não** interrompem a task (é "best effort")
- Dados sensíveis **nunca** entram: apenas um hash HMAC-SHA256 do input
- Consultável via `autotarefas report`

## Segurança

A segurança é transversal (veja `SECURITY.md` no repositório). Princípios centrais:

- **Credenciais fora do código e dos logs** — senhas vêm de variável de ambiente ou prompt (`getpass`), nunca de argumentos de linha de comando
- **Mascaramento** de dados sensíveis em logs e screenshots
- **Retry seletivo** — não reenvia o que não tem conserto (erros 4xx)
- **Avisos de TLS** — alerta ao enviar credenciais sobre conexões sem criptografia

## Stack

`click` + `rich` (CLI), `pydantic`/`pydantic-settings` (config tipada), `loguru` (logs), `pandas`/`openpyxl` (planilhas), `httpx` + `tenacity` (HTTP com retry), `playwright` (RPA), `smtplib` + `email` (email, stdlib), `cryptography` (segurança). Qualidade: `pytest`, `mypy` (strict), `ruff`, `bandit`.
