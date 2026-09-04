# 05 — Matriz de Rastreabilidade

Atualizar a cada entrega (ritual em 00 §6). Colunas: **prioridade aprovada** pela
DP-01 em 10/08/2026 (41 obrigatórios; ver 00 §3.1); código e teste são caminhos
reais deste snapshot; "Evid." referencia
as execuções registradas em 00 §4 e §4.1: **[N]** suíte núcleo — **2052 passed,
cobertura 92,39 % na árvore local (A1, 10/08/2026)**; 2023 passed + 1 skipped no
snapshot de 05/08 · **[L]** Live backend 127 passed · **[F]** frontend — **52 passed na árvore local**
(22 `spreadsheets.test.ts` + 16 `SpreadsheetProfileMapping.test.tsx` + 14
`SpreadsheetJourney.test.tsx`), com typecheck e build aprovados; 31 (17 + 14) no
snapshot de 05/08 · **[A1]** evidência da Fase A1,
concluída em 10/08/2026 — saídas locais do responsável (commit `f3f95de`) e
inspeção dos workflows locais; o clone público serviu apenas de referência
histórica · **[B1]** Fase B1 (RF-REC-001, 14/08/2026) — suíte local **2161 passed,
cobertura 92,75 %**, `ruff check .`, `ruff format --check .` e `mypy src/`
aprovados; comando `autotarefas comparar` homologado sobre as fixtures
`tests/fixtures/comparacao/` com os 4 artefatos gerados · **[B2]** Fase B2
(RF-REC-002, 14/08/2026) — comando `autotarefas conciliar` homologado sobre as
mesmas fixtures (campo autorizado atualizado, divergência não autorizada para
revisão, chave duplicada fora da base) com os 4 artefatos gerados; suíte local
verde · **[B3]** Fase B3 (RF-REC-003, 14/08/2026) — comando `autotarefas
transferir` homologado sobre `tests/fixtures/transferencia/` (e-mail vazio
preenchido, e-mail antigo atualizado, valor igual mantido, `nome` não autorizado
intacto, `00129` sem correspondente listado); hashes dos dois arquivos de
entrada conferidos antes e depois · **[B4]** Fase B4 (RF-PLA-009,
14/08/2026) — `validate --mode limpeza --out-dir` sobre
`tests/fixtures/apresentacao/original_formatado.xlsx` gerou
`planilha_tratada.xlsx` com painel congelado, autofiltro, largura, fonte e
preenchimento do cabeçalho e formato `R$ #,##0.00` intactos, valores
normalizados aplicados e `preservacao_report.json` sem perdas · **[B5]** Fase B5
(RF-PLA-010, 14/08/2026) — `autotarefas corrigir` sobre
`tests/fixtures/correcoes/` aplicou 7 correções confirmadas (de/para,
padronização e preenchimento de vazios) e mandou apenas o valor desconhecido
("Sao Jorge") para `itens_para_revisao.csv`, com a apresentação do original
preservada na planilha corrigida · **[B7]** Fase B7 (RF-INT-005, 14/08/2026) —
`send api --map/--map-file/--obrigatorio/--previa` exercitado com as três
estruturas da ficha (contatos, produtos e vendas): payload sai no vocabulário do
destino, mapeamento inválido aborta antes do primeiro POST (exit 2) e linha com
obrigatório vazio é rejeitada com motivo, sem virar requisição · **[B6]** Fase B6
(RF-CORE-006 recorte + RF-REC-004, 14/08/2026) — `autotarefas run
tests/fixtures/fluxo/conferencia_mensal.yaml --out-dir …` executou os 4 passos
(comparar → conciliar → transferir → corrigir) gravando cada um em sua pasta;
segredo embutido no YAML é recusado na leitura (exit 2) e `--out-dir` da CLI
vence o do arquivo · **[G3]** conferência do RF-GOV-003 (31/08/2026) — leitura
do código e dos testes no repositório, sem alteração de nada: existem
`src/autotarefas/core/retention.py` (plano de expurgo calculado antes de apagar
e registro do removido no audit sob `manutencao.expurgar`),
`src/autotarefas/cli/commands/manutencao.py` (comando `expurgar`),
`log_retention_days`/`screenshot_retention_days`/`audit_retention_days` em
`core/settings.py` consumidos em `core/logger.py:142`, e o TTL de 15 min do Live
em `apps/api/app/config.py::workspace_ttl_min` varrido por
`jobs.py::sweep_expired`; testes correspondentes em `tests/core/test_retention.py`
e `tests/cli/test_manutencao_cli.py`. **A conferência não promoveu o requisito**:
ela mostrou que as duas lacunas restantes não são de código — ver a linha do
GOV-003 e a ressalva 12 · **[G4]** fechamento do RF-GOV-003 (03/09/2026) — as
duas lacunas documentais fechadas: a política escrita em `SECURITY.md`
(seção "Retenção de dados e privacidade", com os dois ambientes separados e
cada prazo conferido no código) e a transparência no Live pelo
`AvisoDePrivacidade`, renderizado antes do campo de upload nos dois caminhos
que existem (`ExecutionPanel` e `SpreadsheetJourney`); coberto por 6 asserções
de unidade e por um passo do e2e da jornada do visitante que confere, em
navegador real, que o aviso está visível e **acima** da área de envio ·
**[C1]** homologação C1 do RF-WEB-002
(04/09/2026) — `playwright install chromium` e depois
`pytest tests/e2e/test_extract_web_js_e2e.py -v --no-cov`: **2 passed**, nenhum
*skipped*, em 10,90s. O arquivo prova por contraste, rodando a mesma
`ExtractWebTask` contra a mesma pagina `/catalogo-js` do servidor demo (cujo
conteúdo só existe depois do JavaScript): **sem `--js` extrai 0 itens; com
`--js` o Chromium renderiza e extrai os 3 produtos**. O contraste 0 vs 3 é o
que separa a renderização do parser — sem ele, um parser que lesse HTML cru
passaria pelo mesmo assert. O caso com navegador tem `skipif` ligado a
`verify_playwright_installed()`, entao ver "2 passed" (e nao "1 passed, 1
skipped") e a propria prova de que o navegador rodou · **[H]** evidência
colhida manualmente na auditoria
(saídas de `--help`, leitura de código com linha citada).

| Requisito | Status | Prioridade | Código principal | Teste principal | Evid. | Lacuna | Depende de | Próxima ação |
|---|---|---|---|---|---|---|---|---|
| RF-CORE-001 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/core/base.py` | `tests/core/test_base.py`, `test_base_audit.py` | [N] | — | — | manter |
| RF-CORE-002 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/core/audit.py` | `tests/core/test_audit.py` | [N] | expurgo → GOV-003 | CORE-001 | manter |
| RF-CORE-003 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/core/security.py` | `tests/core/test_security.py` | [N] | — | — | manter |
| RF-CORE-004 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/core/settings.py` | `tests/core/test_settings.py` | [N] | `.env.example` vazio | — | preencher exemplo (A2) |
| RF-CORE-005 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/cli/main.py` + `commands/` | `tests/cli/` (19 arquivos) | [N][H] | — | CORE-001 | manter |
| RF-CORE-006 | CONCLUÍDO (recorte V1) | **OBRIG. V1** (recorte aprovado — DP-01(d)) | `src/autotarefas/flow.py` + `cli/commands/run.py` (+ `profiles/`) | `tests/test_flow.py`, `tests/profiles/` | [B6] | encadeamento genérico e agendamento seguem PÓS-V1 (D4) | REC-004 | manter |
| RF-CORE-007 | NÃO INICIADO | PÓS-V1 | — (semente: `apps/web/src/components/ValidationSummary.tsx`) | — | [H] | motor de regras | CORE-006 | Fase D1 |
| RF-CORE-008 | NÃO INICIADO | PÓS-V1 | — | — | — | tudo | CORE-006 | Fase D4 |
| RF-ARQ-001 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/tasks/backup.py` | `tests/tasks/test_backup.py`, `tests/cli/test_backup_cli.py` | [N][L] | manifesto/restauração → ARQ-002 | CORE-001 | manter |
| RF-ARQ-002 | NÃO INICIADO | PÓS-V1 | — | — | [H] (grep sem "manifest" em backup.py) | tudo | ARQ-001 | Fase D2 |
| RF-ARQ-003 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/tasks/organize.py` | `tests/tasks/test_organize.py`, `tests/cli/test_organize_cli.py` | [N][L] | undo → ARQ-004 | CORE-001 | manter |
| RF-ARQ-004 | NÃO INICIADO | PÓS-V1 | — (base: `operations` no audit) | — | [H] | comando desfazer | ARQ-003 | Fase D2 |
| RF-ARQ-005 | NÃO INICIADO | PÓS-V1 | — | — | — | tudo | ARQ-001 | Fase D2 |
| RF-PLA-001 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/reader/` | `tests/reader/` (6 arquivos) | [N] | — | — | manter |
| RF-PLA-002 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/profiling/` + `services/analysis.py` + `cli/commands/analisar.py` | `tests/profiling/`, `tests/services/test_analysis.py`, `tests/cli/test_analisar_cli.py` | [N] | — | PLA-001 | manter |
| RF-PLA-003 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/profiling/schema_suggestion.py` | `tests/profiling/test_schema_suggestion.py` | [N] | — | PLA-002 | manter |
| RF-PLA-004 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/profiles/{catalog,remap,export}.py` | `tests/profiles/` (4 arquivos) | [N] | catálogo com 1 perfil | PLA-003 | ampliar perfis (B/C) |
| RF-PLA-005 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/tasks/validate.py` + validators/duplicates/row_rules/expressions/issues | `tests/tasks/test_validate*.py`, `test_validators*.py`, `test_duplicates.py`, `test_row_rules.py`, `test_expressions.py`, `test_issues.py` | [N] | — | PLA-001 | manter |
| RF-PLA-006 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/tasks/cleaning.py` | `tests/tasks/test_cleaning.py` | [N] | — | PLA-005 | manter |
| RF-PLA-007 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/tasks/{artifacts,report,report_xlsx}.py` | `tests/tasks/test_artifacts.py`, `test_report.py`, `test_report_xlsx.py` | [N] | — | PLA-005 | manter |
| RF-PLA-008 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/tasks/execution_package.py` | `tests/tasks/test_execution_package.py` | [N] | — | PLA-007 | manter |
| RF-PLA-009 | CONCLUÍDO | **OBRIG. V1** (etapa 6 do resultado, 01 §9.1) | `src/autotarefas/tasks/presentation.py` (+ `cli/commands/validate.py`) | `tests/tasks/test_presentation.py`, `tests/cli/test_validate_tratada_cli.py` | [B4] | gráficos/imagens declarados como não preserváveis (R-13) | PLA-007 | manter |
| RF-PLA-010 | CONCLUÍDO | **OBRIG. V1** (etapa 4 do resultado) | `src/autotarefas/tasks/{corrections,correction_artifacts}.py` + `cli/commands/corrigir.py` | `tests/tasks/test_corrections.py`, `tests/cli/test_corrigir_cli.py` | [B5] | catálogo com 3 tipos (de_para, padronizar, preencher) | PLA-006, REC-003 | ampliar catálogo sob demanda real |
| RF-REC-001 | CONCLUÍDO | **OBRIG. V1** (DP-04 decidida 05/08) | `src/autotarefas/reconcile/` + `cli/commands/comparar.py` | `tests/reconcile/` (3 arquivos), `tests/cli/test_comparar_cli.py` | [B1] | tolerâncias → REC-002 | PLA-001/006 | manter |
| RF-REC-002 | CONCLUÍDO | **OBRIG. V1** | `src/autotarefas/reconcile/{tolerance,merge,merge_artifacts}.py` + `cli/commands/conciliar.py` | `tests/reconcile/test_{tolerance,merge,merge_artifacts}.py`, `tests/cli/test_conciliar_cli.py` | [B2] | YAML da reconciliação → REC-004 | REC-001 | manter |
| RF-REC-003 | CONCLUÍDO | **OBRIG. V1** | `src/autotarefas/reconcile/{transfer,transfer_artifacts}.py` + `cli/commands/transferir.py` | `tests/reconcile/test_transfer.py`, `tests/cli/test_transferir_cli.py` | [B3] | — | REC-001 | manter |
| RF-REC-004 | CONCLUÍDO | **OBRIG. V1** (etapa 11 do resultado) | `src/autotarefas/flow.py` (passos `comparar`/`conciliar`/`transferir`/`corrigir`) + fixture `tests/fixtures/fluxo/conferencia_mensal.yaml` | `tests/test_flow.py` | [B6] | — | REC-002, CORE-006 | manter |
| RF-INT-001 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/tasks/{extract_api,extract_artifacts}.py` | `tests/tasks/test_extract_api.py`, `test_extract_artifacts.py`, `tests/cli/test_extract_cli.py` | [N][L] | paginação única | CORE-001 | manter |
| RF-INT-002 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/tasks/{send_api,send_artifacts,send_result}.py` | `tests/tasks/test_send_api.py`, `test_send_artifacts.py`, `test_send_result.py`, `tests/cli/test_send_cli.py` | [N][L] | mapeamento → INT-005 (obrig. V1) | CORE-001 | manter |
| RF-INT-003 | CONCLUÍDO | OBRIG. V1 (real) | `src/autotarefas/tasks/sync_api.py` | `tests/tasks/test_sync_api.py`, `tests/cli/test_sync_cli.py` | [N] | Live → LIVE-006a | INT-001, INT-002 | ativar no Live (A3) |
| RF-INT-004 | NÃO INICIADO | PÓS-V1 (DP-01(b) e DP-08 aprovadas; formato só após 2 sistemas reais) | — | — | [H] (grep "conector" vazio) | tudo | — | Fase D3 |
| RF-INT-005 | CONCLUÍDO | **OBRIG. V1** (promovido em 10/08 — DP-01(c)) | `src/autotarefas/tasks/field_mapping.py` + `tasks/send_api.py` + `cli/commands/send/api.py` | `tests/tasks/test_field_mapping.py` (inclui contatos, produtos e vendas), `tests/cli/test_send_mapping_cli.py` | [B7] | — | INT-002 | manter |
| RF-INT-006 | NÃO INICIADO | RECOM. V1 (confirmado em DP-01(c); não bloqueia) | — | — | — | checkpoint | INT-002 | Fase B8 (posterior a B7) |
| RF-COM-001 | CONCLUÍDO | OBRIG. V1 (real) | `src/autotarefas/tasks/send_email.py` | `tests/tasks/test_send_email.py`, `tests/cli/test_send_email_cli.py` | [N] | Live → LIVE-006a; anexos | CORE-004 | ativar no Live (A3) |
| RF-COM-002 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/tasks/send_telegram.py` | `tests/tasks/test_send_telegram.py`, `tests/cli/test_send_telegram_cli.py`, `tests/tools/demo_server/test_telegram_mock.py` | [N][L] | — | CORE-001 | manter |
| RF-COM-003 | NÃO INICIADO | PÓS-V1 | — | — | [H] (grep "idempot" vazio em send_email/telegram) | tudo | INT-002 (desenho) | Fase D1 |
| RF-WEB-001 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/tasks/extract_web.py` | `tests/tasks/test_extract_web.py`, `tests/cli/test_extract_web_cli.py` | [N][L] | — | CORE-001 | manter |
| RF-WEB-002 | CONCLUÍDO | OBRIG. V1 (modo real) | ramo `--js` em `src/autotarefas/tasks/extract_web.py` + `BrowserSession` em `src/autotarefas/core/browser.py` | `tests/tasks/test_extract_web_js.py` (unidade, browser mockado) + `tests/e2e/test_extract_web_js_e2e.py` (**os 2 passam** com Chromium instalado) | [N][A1][C1] | — (execução pública segue fora da V1 por DP-02, o que não é lacuna deste requisito) | WEB-001 | manter |
| RF-WEB-003 | **PARCIAL** | OBRIG. V1 (modo real) | `src/autotarefas/tasks/rpa_cadastro.py` | `tests/tasks/test_rpa_cadastro.py`, `tests/cli/test_rpa_cli.py`, `tests/core/test_browser.py` (navegador mockado) | [N][A1] | **não existe teste com navegador real para o RPA**; decisão de 10/08/2026: teste automatizado com navegador real é obrigatório antes de CONCLUÍDO, homologação manual é complementar | CORE browser | criar o teste com navegador real antes da C1 |
| RF-WEB-004 | NÃO INICIADO | PÓS-V1 | — | — | — | tudo | INT-006 | Fase D4 |
| RF-GOV-001 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/tasks/report_audit.py` | `tests/tasks/test_report_audit.py`, `tests/cli/test_report_cli.py` | [N] | Live → LIVE-006a | CORE-002 | ativar no Live (A3) |
| RF-GOV-002 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/dashboard/{reader,renderer}.py` | `tests/dashboard/`, `tests/cli/test_dashboard_cli.py` | [N] | Live → LIVE-006a | GOV-001 | ativar no Live (A3) |
| RF-GOV-003 | CONCLUÍDO | **OBRIG. V1** | mascaramento em `core/security.py`; retenção configurável em `core/settings.py` + `core/logger.py:142`; expurgo em `core/retention.py`; comando em `cli/commands/manutencao.py`; TTL do Live em `apps/api/app/config.py` + `jobs.py::sweep_expired`; política escrita em `SECURITY.md` §"Retenção de dados e privacidade"; aviso na tela em `apps/web/src/components/AvisoDePrivacidade.tsx`, antes do `FileDrop` em `ExecutionPanel.tsx` e `SpreadsheetJourney.tsx` | `tests/core/test_retention.py`, `tests/cli/test_manutencao_cli.py`, `tests/core/test_logger.py`, `tests/core/test_security.py`, `apps/web/src/components/AvisoDePrivacidade.test.tsx`, `tests/e2e/test_jornada_do_visitante_e2e.py::test_15_sabe_o_que_acontece_com_o_arquivo_antes_de_envia_lo` | [N][G3][G4] | — | — (DP-05 aprovada) | manter |
| RF-GOV-004 | CONCLUÍDO | OBRIG. V1 | `src/autotarefas/dashboard/reader.py` (`verify_input_hash`) | `tests/dashboard/test_reader.py` | [N] | — | CORE-002 | manter |
| RF-LIVE-001 | CONCLUÍDO | OBRIG. V1 | `apps/api/app/catalog.py`, `engine.py::ACTIVE_AUTOMATIONS`, `main.py::_precheck` | `apps/api/tests/test_engine.py` | [L][H] | estado `oculto` da régua não implementado | — | manter |
| RF-LIVE-002 | CONCLUÍDO | OBRIG. V1 | `apps/api/app/{main,engine,jobs,streaming}.py` | `test_engine.py`, `test_streaming.py` | [L] | — | LIVE-001 | manter |
| RF-LIVE-003 | CONCLUÍDO | OBRIG. V1 | `apps/api/app/{config,ratelimit,uploads,sanitize,engine}.py` | suíte 127 (limites) | [L][H] | — | LIVE-002 | manter |
| RF-LIVE-004 | CONCLUÍDO | OBRIG. V1 | `apps/api/app/spreadsheets.py` | `test_spreadsheets.py` (1002 linhas) + front 14 testes | [L][F] | — | PLA-002/005, LIVE-002 | manter |
| RF-LIVE-005 | CONCLUÍDO | OBRIG. V1 | `tools/demo_server/`, `apps/api/app/demo_servers.py` | `tests/tools/demo_server/` (5 arquivos) | [N][L] | — | — | manter |
| RF-LIVE-006 | NÃO INICIADO | 006a RECOM. V1 · 006b PÓS-V1 (DP-02) | — (lacuna: `recipes.py::build_argv` cobre só 7 ids) | — | [H] | 006a: 4 ramos de receita + régua + testes · 006b: ajuste da vitrine + vídeo/GIF | LIVE-001..003 | **A3** (006a) · **A4** (vitrine, obrigatória antes do release) · D4 (reavaliação) |
| RF-LIVE-007 | CONCLUÍDO | OBRIG. V1 | `apps/web/src/` | **52 passed** na árvore local (22 + 16 + 14), typecheck e build aprovados — A1, 10/08/2026 | [F][A1] | `spreadsheets.test.ts` (22 testes) **não aparece em `git ls-files` nem como não rastreado** — risco R-18, a confirmar na A1.2 | LIVE-002/004 | confirmar rastreamento do arquivo de teste (A1.2) |

## Evidências com ressalva (honestidade da auditoria)

1. **Verificação com navegador — medida na A1 (10/08/2026).** `tests/e2e/` tem
   **um** arquivo (`test_extract_web_js_e2e.py`) com 2 testes: 1 passa sem
   navegador e 1 é *skipped* automaticamente por `verify_playwright_installed`.
   Não existe teste com navegador real para o **RPA (WEB-003)**. Além disso, o
   marcador `e2e` está declarado no `pyproject.toml` mas **nenhum teste o usa** —
   `pytest -m e2e` seleciona zero testes; o comando correto é
   `playwright install chromium && python -m pytest tests/e2e`. WEB-002 e WEB-003
   permanecem PARCIAL; a promoção a CONCLUÍDO depende da C1.
2. **CI COMPROVADA na A1 (10/08/2026)** — `.github/workflows/ci.yml` roda a cada
   push/PR em `main` (Python 3.12 e 3.13): ruff lint, ruff format, `mypy src/`,
   bandit e `pytest` com gate de cobertura ≥ 85 %; `docs.yml` faz
   `mkdocs build --strict` e publica no Pages. **Lacunas registradas** (04
   RNF-CI-02 e 08 R-16): a suíte do Live backend não é executada pela CI
   (`testpaths = ["tests"]`), não há nenhum job de frontend e o mypy da CI cobre
   apenas `src/`.
3. **Frontend: os 52 testes seguem sem execução independente (A1, 10/08/2026).**
   O que a A1 conseguiu comprovar: (i) o snapshot de 05/08 executa **31 passed**
   (17 em `spreadsheets.test.ts` + 14 em `SpreadsheetJourney.test.tsx`), com
   typecheck e build verdes; (ii) a aritmética informada fecha exatamente sobre
   essa base — 17 + 5 = 22 em `spreadsheets.test.ts`, mais 16 do novo
   `SpreadsheetProfileMapping.test.tsx`, mais 14 da jornada = **52**; (iii) o
   remoto público `origin/main` está em `ac3e58d` (15/07/2026) e **não contém
   nenhum teste de frontend** nem os componentes da jornada — ou seja, os 52 vivem
   somente na árvore local, ainda não publicada, coerente com a convenção
   "commits locais até a revisão final". **Pendência da A1:** executar no
   repositório local `npm ci && npm test && npm run typecheck && npm run build`
   e anexar a saída aqui.
4. **Prioridades aprovadas, status inalterados (10/08/2026)** — a DP-01 fixou o
   recorte obrigatório em 41 requisitos e promoveu RF-INT-005; nenhum status mudou
   por causa disso, e RF-INT-005 seguiu NÃO INICIADO enquanto não teve código,
   testes, critérios de aceite cumpridos e evidência aqui.
   **Atualização (14/08/2026):** essa condição foi cumprida na Fase B7 — o
   requisito passou a CONCLUÍDO com a evidência **[B7]**, registrada na linha
   dele. A regra que esta ressalva enunciava continua valendo; o que mudou foi o
   requisito tê-la satisfeito.
4b. **`origin/main` atrasado em relação à árvore local (A1) — quantificado na ressalva 10.** HEAD público em
   `ac3e58d` "feat(cli): adiciona comando analisar com perfilagem sem schema"
   (15/07/2026), `__version__ = "1.4.0"`. Ausentes no remoto: testes do frontend,
   componentes da jornada de planilhas e o `package.json` com script `test`. O
   remoto **não serve** como fonte de verdade para o baseline de testes; a fonte é
   a árvore local do responsável.

5. **README/CHANGELOG defasados de propósito** — badge/banner v1.1.0 vs pacote
   1.4.0 + bloco "Não lançado". Não é defeito: é a convenção "sem README/CHANGELOG
   até a revisão final". Registrado para ninguém confiar no README como fonte.
6. **Baseline documental não versionado (A1, 10/08/2026).** `git status --short docs/requisitos`
   e `git ls-files docs/requisitos` **não retornaram arquivos**. Conclusão
   comprovável: **`docs/requisitos` não está versionado no Git local.** Não se
   afirma aqui que a pasta esteja fisicamente ausente ou ignorada — isso exige
   verificação adicional, prevista na subetapa **A1.1**. Enquanto isso, o baseline
   oficial vive no pacote entregue (12 Markdown), fora do controle de versão.

7. **`spreadsheets.test.ts` sem rastreamento aparente (A1).** Entre os testes de
   frontend versionados aparecem somente `SpreadsheetJourney.test.tsx` e
   `SpreadsheetProfileMapping.test.tsx`. O arquivo
   `apps/web/src/lib/spreadsheets.test.ts` **existe e executou 22
   testes**, mas não apareceu em `git ls-files` nem entre os não rastreados.
   Hipótese **não confirmada**: regra de `.gitignore` alcançando diretórios
   `lib`. Confirmação exigida na A1.2 com
   `git check-ignore -v apps/web/src/lib/spreadsheets.test.ts` e
   `git ls-files --error-unmatch apps/web/src/lib/spreadsheets.test.ts`.
   Risco R-18.

8. **Fixtures de planilhas (A1).** `tests/fixtures/planilhas/build_fixtures.py`
   está **versionado**; os **32 arquivos CSV/XLSX gerados não estão**. Nenhuma
   decisão tomada: a A1.2 avaliará determinismo do gerador, execução automática
   pelos testes/`conftest.py`, viabilidade de clonagem limpa rodar os 2052 testes,
   tamanho e conteúdo (apenas dados sintéticos) antes de escolher entre versionar,
   gerar antes dos testes ou gerar em diretório temporário. Risco R-19.

9. **`.vscode/settings.json` (127 bytes) não rastreado (A1).** Conteúdo ainda não
   inspecionado; a A1.2 decide entre versionar deliberadamente (se for configuração
   útil e impessoal do projeto) ou ignorar (se for preferência pessoal do editor).
   Nada movido, versionado ou alterado.

10. **Divergência local × remoto (A1).** `main` local está **22 commits à frente**
   de `origin/main`, no commit `f3f95de` (05/08/2026); o remoto público está em
   `ac3e58d` (15/07/2026). Os workflows locais (`ci.yml`, `docs.yml`) são idênticos
   aos do remoto. Sem push nesta etapa; risco de perda registrado em R-17, com
   recomendação de backup local recuperável (`git bundle` fora do diretório do
   projeto) — apenas recomendado, não executado.

11. **Artefatos soltos na raiz** — `contatos.csv`, `relatorio.csv`,
   `dashboard.html`, `dashboard_exemplo.html` parecem resíduos de execução usados
   como exemplo. Decidir na Fase A1 se viram `examples/` ou saem do versionamento
   (nenhuma ação nesta etapa).

12. **RF-GOV-003: o que a conferência de 31/08/2026 achou, e o que ela não fez.**
   Achou implementação e testes para tudo o que a DP-05 pediu do lado do código —
   retenção configurável, rotina de expurgo com registro no audit, comando de
   manutenção e TTL no Live (evidência **[G3]**). **Não** promoveu o requisito a
   CONCLUÍDO, e o motivo importa: as duas lacunas que restam não se resolvem com
   código. Falta a **política de retenção e privacidade escrita** — a DP-05 fixou
   prazos numa decisão interna, não num documento publicável — e falta o **Live
   dizer isso a quem envia arquivo**: finalidade do processamento, tempo de
   retenção, existência de arquivos de exemplo, recomendação de não enviar dados
   pessoais desnecessários e a diferença entre demonstração pública e modo real
   privado. Um sistema que cumpre em silêncio uma política que ninguém enunciou
   não é transparente — é apenas bem-comportado por acaso, e ninguém consegue
   verificar. Enquanto as duas faltarem, **PARCIAL**.

   **Fechado em 03/09/2026 (evidência [G4]).** A política foi escrita no
   `SECURITY.md` e o Live passou a dizê-la antes do upload. A ordem importou:
   escrever primeiro obrigou a conferir cada prazo no código, e a conferência
   corrigiu o que seria dito — não há audit de 30 dias no Live (PA-01), as
   screenshots de 7 dias não se aplicam (DP-02/PA-02), e o log é apagado
   automaticamente pelo sink, sem confirmação. O aviso na tela repete só o que
   o código sustenta. Continua **fora** do escopo deste requisito, e registrado
   na própria seção do `SECURITY.md`: a trilha de auditoria da **plataforma**
   nasceu depois da DP-05 e ainda não tem prazo definido.
