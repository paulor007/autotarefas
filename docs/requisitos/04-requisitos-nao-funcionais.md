# 04 — Requisitos Não Funcionais

Regra deste documento: **todo RNF é mensurável e verificável**. Onde não existe
número com base real, o campo fica marcado **A DEFINIR (DP-03)** — nunca um número
inventado. **DP-03 foi aprovada em 10/08/2026** com a decisão de *manter esses
números em aberto* até a escolha da hospedagem e medições reproduzíveis; a decisão
está tomada, os valores não. **DP-05 foi aprovada em 10/08/2026** e seus prazos
constam em RNF-PRIV. Valores "vigentes" vêm do código deste snapshot;
"alvo" é proposta a aprovar.

## RNF-DES — Desempenho e capacidade

| ID | Requisito | Valor vigente (fonte) | Verificação |
|---|---|---|---|
| RNF-DES-01 | Tempo máximo de uma execução no Live | 60 s, processo morto ao estourar (`RUN_TIMEOUT_S`, `config.py`; kill em `engine.py`, exit 124) | teste da suíte 127 |
| RNF-DES-02 | Execuções simultâneas no Live | 4 (`MAX_CONCURRENT_RUNS`); acima → 429 | teste + homologação |
| RNF-DES-03 | Requisições por visitante | 12/min/IP (`RATE_LIMIT_PER_MIN`); acima → 429 | teste |
| RNF-DES-04 | Upload | ≤ 10 MB e ≤ 50 arquivos (`MAX_UPLOAD_MB`, `MAX_UPLOAD_FILES`); acima → 413 | teste |
| RNF-DES-05 | Stream de stdout | ≤ 2.000 linhas e ≤ 256 KB por execução | teste |
| RNF-DES-06 | Workspaces | ≤ 40 simultâneos, TTL 15 min (`MAX_WORKSPACES`, `WORKSPACE_TTL_MIN`); cheio → 503 | teste |
| RNF-DES-07 | Schema YAML enviado na jornada | ≤ 256 KB (`_MAX_SCHEMA_BYTES`, `spreadsheets.py`) | teste |
| RNF-DES-08 | Modo real — teto de processamento | `max_records_per_run` default 10.000 (settings, ajustável 1–1.000.000) | teste de settings |
| RNF-DES-09 | Volume-alvo de planilha com desempenho aceitável | **A DEFINIR (DP-03 aprovada em 10/08/2026: adiar)** — a medir com a fixture real de vendas quando houver benchmark reproduzível | benchmark futuro |
| RNF-DES-10 | Usuários simultâneos esperados no Live | **A DEFINIR (DP-03: adiar até a hospedagem)** — vitrine de baixo volume; os limites acima já protegem o servidor | — |

## RNF-CONF — Confiabilidade e disponibilidade

- RNF-CONF-01 — Falha em uma linha nunca aborta o lote (validação, envios, RPA);
  resultado agregado usa `PARTIAL`. *Verificado pelas suítes das tasks.*
- RNF-CONF-02 — Retry automático somente para erros temporários
  (timeout/conexão/5xx/429), com backoff exponencial e jitter; 4xx de dado nunca
  retentado; `Retry-After` respeitado quando presente. *Fonte: `send_api.py`,
  `extract_api.py`; verificado por teste.*
- RNF-CONF-03 — Reexecução segura: reenvio de falhos com `Idempotency-Key`
  idêntica não duplica em sistemas idempotentes. *Verificado contra o mock.*
- RNF-CONF-04 — Disponibilidade do Live: **A DEFINIR (DP-03 aprovada: adiar)** —
  depende da hospedagem a escolher; nenhum SLA provisório será publicado.

## RNF-INTG — Integridade de dados

- RNF-INTG-01 — Arquivo original de entrada nunca é modificado; toda saída é
  arquivo novo. *Regra de ouro; verificada por testes de reader/cleaning.*
- RNF-INTG-02 — Backup com hash SHA-256 publicado do pacote. *`backup.py`.*
- RNF-INTG-03 — Pacote de evidências com hashes de entrada e saídas no
  `manifest.json`. *`execution_package.py`.*
- RNF-INTG-04 — Zeros à esquerda e valores ambíguos preservados (nunca
  "corrigidos no chute"). *`normalize.py`.*

## RNF-SEG — Segurança

- RNF-SEG-01 — Subprocesso do Live sem shell; argv integralmente construído pelo
  servidor a partir de allowlist (`recipes.py::build_argv`); visitante nunca
  fornece caminho, comando ou URL.
- RNF-SEG-02 — Egress lockdown do robô no Live ligado por padrão
  (`EGRESS_LOCKDOWN=true`): proxy morto + exceção apenas `127.0.0.1/localhost`.
- RNF-SEG-03 — Anti path traversal em upload (nomes sanitizados, extensão por
  allowlist) e download (apenas nome simples, apenas `out/`).
- RNF-SEG-04 — Segredos exclusivamente via ambiente (`SecretStr`); nunca em
  código, log, audit, relatório ou receita; token do Telegram com redação até em
  exceções.
- RNF-SEG-05 — Trilha de auditoria append-only com HMAC-SHA256 do input e
  verificação de integridade disponível.
- RNF-SEG-06 — `validate_url()` exige HTTPS em produção; mocks locais liberados
  em dev/demo.
- RNF-SEG-07 — Dependências do frontend sem vulnerabilidades conhecidas:
  `npm audit` = 0 nesta auditoria; manter 0 como gate de release.

## RNF-PRIV — Privacidade e LGPD

- RNF-PRIV-01 — Dados pessoais do modo real permanecem na máquina do usuário;
  o produto não envia nada para terceiros fora do que o operador configurar.
- RNF-PRIV-02 — Live: dados do visitante são efêmeros (workspace TTL 15 min) e
  jamais saem do servidor (RNF-SEG-02).
- RNF-PRIV-03 — Conteúdo de mensagens (e-mail/Telegram) não é persistido em
  relatórios; screenshots de RPA mascaram campos sensíveis por padrão
  (`screenshots_mask_sensitive=True`).
- RNF-PRIV-04 — **Política de retenção aprovada em 10/08/2026 (DP-05)**, com
  separação entre ambientes. Implementação em RF-GOV-003 (Fase A2):

  | Dado | Live System público | Modo real privado |
  |---|---|---|
  | Uploads e artefatos | TTL de 15 minutos | configurável pelo operador |
  | Logs operacionais sem dados sensíveis | 30 dias | 30 dias por padrão, configurável |
  | Screenshots mascaradas | **não aplicável na V1** (ver RNF-PRIV-08) | 30 dias por padrão, configurável |
  | Audit | **vida do workspace, máximo de 15 minutos** (ver RNF-PRIV-07) | retenção configurável e exclusão manual confirmada |

  Estado atual do código: logs com retenção fixa de 30 dias
  (`core/logger.py:142` — precisa virar configurável),
  `screenshot_retention_days` (default 30) **sem rotina de expurgo**, audit do
  modo real sem expurgo, workspaces do Live com TTL de 15 min (já conforme).
  As duas qualificações da tabela foram decididas em 10/08/2026 (PA-01 e PA-02,
  registro em `08` §4) e estão detalhadas em RNF-PRIV-07 e RNF-PRIV-08.
- RNF-PRIV-05 — **Transparência obrigatória no Live (DP-05)**: informar
  finalidade do processamento, tempo de retenção, disponibilidade de arquivos de
  exemplo, recomendação de não enviar dados pessoais desnecessários e a diferença
  entre demonstração pública e modo real privado. Texto entra na Fase A2, junto da
  implementação da política.
- RNF-PRIV-06 — A política de retenção é **técnica**; revisão jurídica é
  obrigatória antes de uso comercial com dados pessoais de clientes (registro da
  DP-05).
- RNF-PRIV-07 — **Audit no Live (PA-01, resolvida em 10/08/2026 — opção (a)).**
  No Live, o audit existe apenas dentro do workspace da execução, com
  `AUTOTAREFAS_HOME` isolado, e é apagado junto com o workspace: **retenção máxima
  de 15 minutos**. **Não existe audit agregado do servidor na V1** e nenhum
  requisito novo foi criado para isso (nada de RF-LIVE-008 nesta fase). A retenção
  de **30 dias fica reservada para um futuro audit agregado**, caso esse recurso
  seja aprovado depois — enquanto não existir, a documentação não promete 30 dias
  para o Live, porque a arquitetura atual não sustenta esse prazo.
- RNF-PRIV-08 — **Screenshots no Live (PA-02, resolvida em 10/08/2026 — opção (a)
  com qualificação).** Screenshots mascaradas são geradas somente pelo RPA
  (`rpa_cadastro`), que **não é executado publicamente na V1** (DP-02); portanto o
  item é **não aplicável ao Live público da V1**. O prazo preventivo de **7 dias**
  passa a valer **somente se** a execução pública com navegador for habilitada na
  Fase D. No **modo real privado** permanece o padrão configurável de **30 dias**.
  Esta decisão **não cria implementação nova na V1**.

## RNF-AUD — Auditabilidade

- RNF-AUD-01 — 100% das execuções de task registradas no audit com timestamp,
  status, duração e hash do input.
- RNF-AUD-02 — Relatórios do audit são somente leitura (nenhum UPDATE/DELETE).
- RNF-AUD-03 — Toda alteração de limpeza tem antes/depois/regra registrados.

## RNF-USAB — Usabilidade

- RNF-USAB-01 — Toda a interface (CLI, Live, mensagens de erro) em português.
- RNF-USAB-02 — Erros sempre orientam a correção (ex.: ambiguidade lista
  candidatas e as flags a usar); tracebacks crus não chegam ao usuário final.
- RNF-USAB-03 — Live responsivo de celular a desktop (grid Tailwind 1→4
  colunas). *Verificação manual na homologação (roteiro em 01 §20).*
- RNF-USAB-04 — Demonstração de ponta a ponta em ≤ 3 min (alvo do critério de
  sucesso; medir na homologação).
- RNF-USAB-05 — Acessibilidade (WCAG): meta **A DEFINIR (DP-03: adiar)**. Estado
  atual: componentes usam atributos ARIA pontuais (`aria-disabled` no FileDrop),
  sem verificação formal — NÃO COMPROVADO como conformidade.

## RNF-COMPAT — Compatibilidade

- RNF-COMPAT-01 — Python ≥ 3.12 (`pyproject.toml`); auditoria executou em 3.12.3.
- RNF-COMPAT-02 — Node 22 para o frontend (auditoria em 22.22.2).
- RNF-COMPAT-03 — Planilhas: `.csv` e `.xlsx` (leitura estruturada); uploads do
  Live aceitam a lista de `allowed_upload_extensions` por automação.
- RNF-COMPAT-04 — Modo real multiplataforma Windows/Linux (desenvolvimento
  primário em Windows; suíte verde em Linux nesta auditoria).
- RNF-COMPAT-05 — Navegador para RPA/JS: Chromium via Playwright
  (`playwright install chromium`).

## RNF-OBS — Observabilidade

- RNF-OBS-01 — Logs estruturados (loguru) com rotação e retenção de 30 dias;
  nível configurável por env e por `-v/-q`.
- RNF-OBS-02 — Live expõe `/api/health` com estado dos mocks e automações ativas.
- RNF-OBS-03 — stdout das execuções do Live transmitido ao visitante (SSE) até
  os limites de RNF-DES-05.

## RNF-MAN — Manutenibilidade e qualidade de código

- RNF-MAN-01 — Tipagem estática estrita: mypy em `src/ tests/` (convenção do
  projeto: testes também type-clean).
- RNF-MAN-02 — Cobertura de testes do núcleo ≥ 85 % como gate
  (`--cov-fail-under=85` no `pyproject.toml`). **Medida na árvore local (A1,
  10/08/2026): 92,39 %.**
- RNF-MAN-03 — Suíte do núcleo rápida o bastante para rodar sempre: **2052 testes**
  na árvore local (A1); ~50 s para os 2023 do snapshot de 05/08 no ambiente do
  auditor (informativo, não gate).
- RNF-MAN-04 — pre-commit configurado (`.pre-commit-config.yaml`) + baseline de
  segredos (`.secrets.baseline`).
- RNF-MAN-05 — Zero dependência paga; faixas de versão com teto de major no
  `pyproject.toml`.

## RNF-TEST — Testes (estado verificado nesta auditoria)

**Baseline vigente: árvore local, comprovado na A1 de 10/08/2026** (commit
`f3f95de`, 22 commits à frente de `origin/main`).

| Suíte | Comando | Resultado no baseline local |
|---|---|---|
| Núcleo | `python -m pytest tests` | **2052 passed**, cobertura **92,39 %** |
| Live backend | `python -m pytest apps/api/tests` | **127 passed** |
| Frontend | `npm test` (`vitest run`) | **52 passed** — 22 em `spreadsheets.test.ts`, 16 em `SpreadsheetProfileMapping.test.tsx`, 14 em `SpreadsheetJourney.test.tsx` |
| Frontend estático | `npm run typecheck` / `npm run build` | aprovados |
| Frontend — vulnerabilidades | `npm audit` / `npm audit --omit=dev` | **1 alta de desenvolvimento** (`nanoid < 3.3.17`, GHSA-2v37-7h3g-55p8) / **0** em produção; `git diff` do `package-lock.json` vazio — nenhuma correção aplicada (R-15, subetapa A1.3) |
| Navegador (`tests/e2e/`) | `playwright install chromium && python -m pytest tests/e2e` | **não executado** — pertence à homologação C1; sem Chromium, 1 teste passa e 1 auto-skipa (`verify_playwright_installed`) |

Medições anteriores, preservadas apenas como histórico do **snapshot de 05/08**
auditado pelo zip: núcleo 2023 passed + 1 skipped; frontend 31 passed (17 + 14);
`npm audit` 0 na data da primeira auditoria.

**Correção de convenção (A1, 10/08/2026):** o marcador `e2e` está declarado no
`pyproject.toml` mas **nenhum teste o usa** — `pytest -m e2e` seleciona zero
testes e `pytest -m "not e2e"` não exclui nada. O arquivo `tests/e2e/test_extract_web_js_e2e.py`
usa `pytest.mark.integration` + `skipif` por ausência de navegador. Comandos
corretos: a suíte completa é `python -m pytest tests`; a verificação com navegador
é `playwright install chromium` seguido de `python -m pytest tests/e2e`.

## RNF-CI — Integração contínua

- RNF-CI-01 — **COMPROVADO na A1 (10/08/2026)**: `.github/workflows/ci.yml`
  existe e roda a cada push/PR em `main`, com matriz Python 3.12 e 3.13:
  `ruff check` → `ruff format --check` → `mypy src/` → `bandit -c pyproject.toml -r src`
  → `pytest` (com gate de cobertura ≥ 85 % vindo do `addopts`). Há também
  `.github/workflows/docs.yml` (build `mkdocs --strict` + deploy no GitHub Pages).
- RNF-CI-02 — **Lacunas da CI identificadas na A1** (nenhuma corrigida nesta
  etapa; registro em `08` R-16):
  1. `testpaths = ["tests"]` no `pyproject.toml` faz o `pytest` da CI cobrir
     **somente o núcleo** — a suíte do Live backend (`apps/api/tests`,
     127 testes) **não roda na CI**;
  2. **nenhum job de frontend**: `npm ci`, `npm test`, `npm run typecheck`,
     `npm run build` e `npm audit` não aparecem em nenhum workflow;
  3. `mypy src/` contraria a convenção do projeto, que exige `mypy src/ tests/`;
  4. o teste que depende de navegador passa como *skipped* na CI, o que é
     adequado, mas significa que **nenhuma execução automatizada cobre o caminho
     real de navegador** (Playwright real) — tarefa da homologação C1 ou de
     workflow manual específico.

  **Confirmado na A1 com os workflows locais** (idênticos aos do remoto): as
  lacunas 1 a 4 valem para a árvore local. Consolidação planejada na subetapa
  **A1.4** (`06`); risco R-16 permanece aberto até lá.

## RNF-DOC — Documentação

- RNF-DOC-01 — Documentação de uso via MkDocs (`mkdocs.yml`, `docs/`, build em
  `site/`) publicada no GitHub Pages pelo ritual de release.
- RNF-DOC-02 — `docs/requisitos/` (este conjunto) é a fonte oficial de
  requisitos e progresso após aprovação.
- RNF-DOC-03 — `--help` completo em todos os comandos e subcomandos (verificado).
- RNF-DOC-04 — `.env.example` documentando todas as variáveis de `settings.py`
  — **pendente** (arquivo hoje vazio; fecha com RF-CORE-004 na Fase A).

## RNF-IMPL — Implantação

- RNF-IMPL-01 — Instalação do modo real por `pip install` padrão (PEP 621,
  hatch); sem passos manuais além do `playwright install chromium` opcional.
- RNF-IMPL-02 — Live: backend uvicorn + frontend estático buildado; porta e
  limites por env; hospedagem a definir — **A DEFINIR (DP-03: adiar até a escolha)**.

## RNF-SUP — Suporte

- RNF-SUP-01 — Canal: issues do GitHub + documentação (nível 1); mantenedor
  (nível 2). Tempo-alvo de primeira resposta: **A DEFINIR (DP-03: adiar)**.
