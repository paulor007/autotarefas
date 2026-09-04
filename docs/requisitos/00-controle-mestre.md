# 00 — Controle Mestre do AutoTarefas

> **Fonte oficial de acompanhamento do projeto.** Após a aprovação deste conjunto de
> documentos, nenhuma funcionalidade é considerada existente, concluída ou planejada
> se não estiver registrada aqui.
>
> Baseline gerado pela auditoria de **05/08/2026** sobre o snapshot do repositório
> (versão do pacote: `1.4.0` em `src/autotarefas/__init__.py`; CHANGELOG com bloco
> "Não lançado" contendo o Live System).
>
> **Revisão 3 — baseline documental aprovado (10/08/2026).** Histórico: a
> estrutura foi aprovada em 05/08/2026 (revisão 2); em **10/08/2026** o
> responsável aprovou formalmente o **escopo obrigatório da V1, o baseline
> documental e as decisões DP-01 (a–d), DP-02, DP-03, DP-05 e DP-08** — registro
> completo em `08` §4. Mudança material desta revisão: **RF-INT-005 promovido a
> OBRIGATÓRIO V1**, elevando o escopo de 40 para **41** requisitos obrigatórios.
>
> Esta revisão é **documental**: a versão do software permanece `1.4.0` e nenhum
> requisito muda de status sem código, testes, critérios de aceite cumpridos e
> evidência na matriz. Em 10/08/2026 foram também resolvidos os pontos **PA-01** e
> **PA-02** (retenção no Live) e **autorizada a Fase A1** — reauditoria do
> repositório Git atual.
>
> **Fase A1: CONCLUÍDA em 10/08/2026 como atividade de auditoria.** Evidências
> coletadas, suítes executadas, workflows locais inspecionados, estado do Git
> identificado, inconsistências comprovadas e **nenhuma correção aplicada em
> silêncio**. Registro em `08` §4; baseline técnico local em §4.1 deste documento.
>
> **Auditoria concluída ≠ achados corrigidos.** Os achados da A1 originaram quatro
> subetapas **obrigatórias antes da A2**: **A1.1** (aplicação do baseline
> documental), **A1.2** (reprodutibilidade dos testes e higiene do repositório),
> **A1.3** (correção mínima da dependência vulnerável) e **A1.4** (consolidação da
> integração contínua) — planejamento operacional em `06`. Nenhum requisito
> funcional é concluído pela conclusão da A1.
>
> **Revisão 4 — alinhamento ao placar real (31/08/2026).** Este documento havia
> parado em **30/41**, número correto em 10/08/2026 e desatualizado desde então:
> as fases B1 a B7 concluíram REC-001..004, PLA-009, PLA-010, INT-005 e o
> recorte aprovado de CORE-006, todos já registrados com evidência na matriz
> (`05`) e com status CONCLUÍDO nas fichas (`03`). O controle mestre era o único
> dos três a divergir — e, sendo a fonte oficial de acompanhamento, era o pior
> lugar para uma divergência.
>
> **Nada mudou de status por causa desta revisão.** Ela é documental no sentido
> estrito: transcreve para cá o que a matriz e as fichas já comprovavam. Os
> números de 05/08 e 10/08 permanecem no texto, marcados como históricos.
> **Placar vigente: 39/41** — ver §3.

---

## 1. Como este conjunto de documentos funciona

| Documento | Conteúdo | Quando consultar |
|---|---|---|
| `00-controle-mestre.md` | Este arquivo: legenda de status, checklist mestre, fórmula de progresso, ritual de atualização | Sempre, antes de qualquer entrega |
| `01-documento-de-requisitos-autotarefas.md` | Documento formal de requisitos (padrão do formulário de solicitação de software usado como referência) | Visão oficial do produto; base para DOCX/PDF |
| `02-catalogo-de-automacoes.md` | Catálogo das automações: cards do Live, comandos CLI, status ativo/em breve | Entender o que o usuário vê e executa |
| `03-requisitos-funcionais.md` | Fichas completas de todos os RFs (modelo de 28 campos) | Planejar/implementar qualquer requisito |
| `04-requisitos-nao-funcionais.md` | RNFs mensuráveis (desempenho, segurança, LGPD, testes, CI...) | Definir limites e critérios transversais |
| `05-matriz-de-rastreabilidade.md` | Requisito × status × código × teste × evidência × lacuna × próxima ação | Atualizar a cada entrega |
| `06-roadmap-e-dependencias.md` | Fases, épicos, subetapas pequenas, commits sugeridos | Decidir o que fazer a seguir |
| `07-sugestoes-e-oportunidades.md` | Análise crítica + ranking das 10 melhores sugestões novas + top 3 detalhado + mecanismo de sugestões automáticas | Evoluir o produto |
| `08-riscos-e-decisoes.md` | Riscos técnicos/de produto + decisões pendentes (DP-xx) | Antes de aprovar escopo |
| `09-criterios-de-aceite-e-dod.md` | Definition of Done geral e por tipo de requisito | Antes de marcar CONCLUÍDO |
| `10-glossario.md` | Termos do projeto | Referência |

## 2. Legenda de status (única permitida)

- **CONCLUÍDO** — implementado, integrado, testado, com tratamento de erros, saída
  útil, critérios de aceite comprovados e evidência registrada na matriz (05).
  Interfaces exigem também teste manual registrado.
- **PARCIAL** — parte comprovada, parte ausente; a lacuna está descrita na matriz.
- **NÃO INICIADO** — não há código do requisito no repositório.
- **BLOQUEADO** — depende de decisão pendente (DP-xx) ou de outro requisito.
- **NÃO COMPROVADO** — existe afirmação (README, badge, relato) sem evidência
  reproduzível neste snapshot.
- **NÃO APLICÁVEL** — fora do contexto do requisito (ex.: "Modo Live" de um
  requisito interno).

Proibido: percentuais arbitrários, "quase pronto", "90%".

## 3. Fórmula de progresso (após aprovação do escopo V1)

```
progresso V1 = requisitos OBRIGATÓRIO V1 com status CONCLUÍDO
               ÷ total de requisitos OBRIGATÓRIO V1 aprovados
```

Escopo aprovado em **10/08/2026** (DP-01): **41 requisitos OBRIGATÓRIO V1**, dos
quais **39 CONCLUÍDOS**.

**Progresso vigente da V1: 39/41.**

Este número muda somente quando um requisito obrigatório passa a CONCLUÍDO pelo
DoD (`09`), com evidência na matriz (`05`) — nunca por aprovação documental.

> **Onde ler 30/41.** O número aparece adiante, na §4 (fotografia da auditoria
> de 05/08/2026) e na §4.1 (baseline técnico da A1, 10/08/2026). Ali ele é
> **histórico** e está correto: descreve o que se media naquelas datas. O placar
> vigente é o desta seção. Nenhuma outra parte deste documento pode citar 30/41
> sem dizer a que data se refere.

### 3.1 Escopo obrigatório aprovado da V1 (41 requisitos)

| Grupo | Requisitos | Situação |
|---|---|---|
| Concluídos (39) | CORE-001..006 · ARQ-001, ARQ-003 · PLA-001..010 · REC-001..004 · INT-001..003, INT-005 · COM-001..002 · WEB-001 · GOV-001..004 · LIVE-001..005/007 | manter (regressão = bloqueio) |
| Parciais (2) | WEB-002 · WEB-003 | concluir |
| Não iniciados (0) | — | — |

**Nenhum requisito obrigatório da V1 permanece NÃO INICIADO.** Os sete que
estavam nessa condição em 10/08/2026 — REC-001..004, PLA-009, PLA-010 e
INT-005 — foram concluídos nas fases B1 a B7 (14/08/2026), e RF-CORE-006 foi
concluído no **recorte aprovado** (DP-01(d)) na fase B6; o encadeamento genérico
de tarefas arbitrárias segue PÓS-V1 e **não** faz parte do recorte. Evidência de
cada um na matriz (`05`).

**RECOMENDADOS V1 (não bloqueiam o release):** LIVE-006a (4 cards baratos) e
RF-INT-006 (checkpoint/retomada).
**PÓS-V1:** RF-INT-004 (conectores declarativos), CORE-007, CORE-008,
ARQ-002/004/005, COM-003, WEB-004, LIVE-006b (cards de navegador — DP-02) e o
encadeamento genérico de CORE-006.

## 4. Fotografia da auditoria de 05/08/2026 (histórica)

> **Seção histórica.** Os números abaixo são o retrato de **05/08/2026** e não
> são atualizados: eles registram o que a auditoria mediu naquele dia. O placar
> vigente está na §3.

Contagem por status (**51** requisitos funcionais catalogados em `03` — a
revisão 2 corrigiu o total: a soma das listas de IDs sempre foi 51, e o texto
anterior dizia 49 por erro de fechamento de conta; os IDs em si não mudaram):

| Status | Quantidade | IDs |
|---|---|---|
| CONCLUÍDO | 30 | CORE-001..005 · ARQ-001, ARQ-003 · PLA-001..008 · INT-001..003 · COM-001..002 · WEB-001 · GOV-001, GOV-002, GOV-004 · LIVE-001..005, LIVE-007 |
| PARCIAL | 4 | CORE-006 · GOV-003 · WEB-002 · WEB-003 (implementação e testes de unidade prontos; comprovação e2e pendente) |
| NÃO INICIADO | 17 | CORE-007, CORE-008 · ARQ-002, ARQ-004, ARQ-005 · PLA-009, PLA-010 · REC-001..004 · INT-004..006 · COM-003 · WEB-004 · LIVE-006 |
| BLOQUEADO / NÃO COMPROVADO / NÃO APLICÁVEL | 0 como status principal | ressalvas pontuais registradas na matriz (05), seção "Evidências com ressalva" |

Evidências de execução colhidas nesta auditoria (ambiente Linux, Python 3.12.3,
Node 22.22.2):

- Suíte do núcleo **no snapshot de 05/08 auditado**: `python -m pytest tests` →
  **2023 passed, 1 skipped** (2024 coletados; o único *skip* é o teste que exige
  Chromium, que se auto-desativa). **O baseline vigente é o da árvore local:
  2052 testes** — ver §4.1.
- Suíte do Live backend: `python -m pytest apps/api/tests` → **127 passed**
  (confere com o número informado da última etapa).
- Frontend: `npx vitest run` sobre o zip → **31 passed** (2 arquivos: 14 + 17).
  **Resolvido (DP-07):** a validação local do responsável em 05/08/2026, posterior
  ao zip, comprovou **52 testes + typecheck + build + npm audit 0** — o zip estava
  desatualizado no frontend. Baseline oficial passa a ser 52 (informado pelo
  responsável); o auditor reconfirma na reauditoria do repositório atual (Fase A1).
- Frontend: `npm run typecheck` → OK; `npm run build` → OK (Vite, `dist/` gerado);
  `npm audit` → *found 0 vulnerabilities*.
- CI GitHub Actions: badge presente no README, mas **`.github/` não veio no zip** —
  NÃO COMPROVADO neste snapshot (ressalva na matriz).

### 4.1 Baseline técnico local comprovado (A1, 10/08/2026)

Fonte de verdade: **árvore local** do responsável. O remoto público
(`origin/main`) é apenas referência histórica desatualizada.

| Item | Valor comprovado |
|---|---|
| Commit local | `f3f95deed7a831fb8177bf2476ed03a77a4a24a7` |
| Branch | `main` — **22 commits à frente de `origin/main`** |
| Último commit | *feat(profiles): adiciona perfil vendas_itens com regras de grupo e calculo* (05/08/2026) |
| Suíte principal | **2052 passed** |
| Cobertura | **92,39 %** (gate ≥ 85 %) |
| Backend Live | **127 passed** |
| Frontend | **52 passed** — 22 em `spreadsheets.test.ts`, 16 em `SpreadsheetProfileMapping.test.tsx`, 14 em `SpreadsheetJourney.test.tsx` |
| `npm run typecheck` / `npm run build` | aprovados |
| `npm audit` | **1 vulnerabilidade alta de desenvolvimento** (R-15) |
| `npm audit --omit=dev` | **0 vulnerabilidades** |
| `git diff` do `package-lock.json` | vazio (lockfile inalterado) |

Substituições de baseline: **2052** substitui os 2023 do snapshot anterior; **52**
substitui os 31. Os números antigos permanecem no texto **apenas** quando
identificados como resultado do snapshot de 05/08.

**As contagens de requisitos não mudaram com a A1** — a A1 foi auditoria, e
auditoria não conclui requisito. Em **10/08/2026** eram: 51 catalogados ·
30 CONCLUÍDOS · 4 PARCIAIS · 17 NÃO INICIADOS · 41 obrigatórios da V1 ·
progresso **30/41**.

> Estes são os valores **daquela data**. As fases B1 a B7 (14/08/2026) levaram o
> placar a **39/41** — ver §3.

## 5. Checklist mestre (marcar somente com evidência na matriz 05)

### CORE — fundação transversal
- [x] RF-CORE-001 Fundação de tasks (BaseTask/TaskResult/TaskStatus) — CONCLUÍDO
- [x] RF-CORE-002 Trilha de auditoria append-only (SQLite + HMAC) — CONCLUÍDO
- [x] RF-CORE-003 Segurança transversal (paths, URLs, mascaramento) — CONCLUÍDO
- [x] RF-CORE-004 Configuração por ambiente (.env, SecretStr) — CONCLUÍDO
- [x] RF-CORE-005 CLI unificada (--dry-run, --yes, verbosidade) — CONCLUÍDO
- [x] RF-CORE-006 Reutilização de configurações — CONCLUÍDO no **recorte aprovado** (DP-01(d)): `autotarefas run fluxo.yaml`; encadeamento genérico de tarefas arbitrárias permanece PÓS-V1
- [ ] RF-CORE-007 Sugestões automáticas de próximos passos — NÃO INICIADO
- [ ] RF-CORE-008 Agendamento, gatilhos e encadeamento — NÃO INICIADO

### ARQ — arquivos e pastas
- [x] RF-ARQ-001 Backup ZIP com hash SHA-256 e dry-run — CONCLUÍDO
- [ ] RF-ARQ-002 Manifesto, validação e restauração de backup — NÃO INICIADO
- [x] RF-ARQ-003 Organização por regras YAML — CONCLUÍDO
- [ ] RF-ARQ-004 Desfazer movimentações (undo) — NÃO INICIADO
- [ ] RF-ARQ-005 Histórico e retenção de backups — NÃO INICIADO

### PLA — análise e tratamento de planilhas
- [x] RF-PLA-001 Leitura robusta CSV/XLSX com metadados e detecção — CONCLUÍDO
- [x] RF-PLA-002 Análise estrutural com veredito de ambiguidade — CONCLUÍDO
- [x] RF-PLA-003 Schema sugerido — CONCLUÍDO
- [x] RF-PLA-004 Perfis prontos (listar/ver/exportar + remapeamento) — CONCLUÍDO
- [x] RF-PLA-005 Validação completa (tipos, BR, duplicatas, grupos, derivadas) — CONCLUÍDO
- [x] RF-PLA-006 Limpeza segura com trilha de alterações — CONCLUÍDO
- [x] RF-PLA-007 Artefatos e relatórios da auditoria (CSV/JSON/XLSX) — CONCLUÍDO
- [x] RF-PLA-008 Pacote de evidências com manifesto e hashes — CONCLUÍDO
- [x] RF-PLA-009 Preservação da formatação original na versão tratada — CONCLUÍDO
- [x] RF-PLA-010 Correções por regras confirmadas (além da limpeza) — CONCLUÍDO

### REC — reconciliação e transferência entre planilhas
- [x] RF-REC-001 Comparação (diff) entre planilhas por chave — CONCLUÍDO
- [x] RF-REC-002 Reconciliação com tolerâncias e base conciliada — CONCLUÍDO
- [x] RF-REC-003 Transferência/enriquecimento entre planilhas — CONCLUÍDO
- [x] RF-REC-004 Configuração de reconciliação salva e reutilizável — CONCLUÍDO

### INT — integração com sistemas via API
- [x] RF-INT-001 Exportação via API paginada — CONCLUÍDO
- [x] RF-INT-002 Importação/cadastro via API (idempotência + reenvio de falhos) — CONCLUÍDO
- [x] RF-INT-003 Sincronização API→API por composição — CONCLUÍDO
- [ ] RF-INT-004 Conectores declarativos por sistema (YAML) — NÃO INICIADO · PÓS-V1 (DP-01(b) e DP-08)
- [x] RF-INT-005 Mapeamento de colunas configurável na importação — CONCLUÍDO · **OBRIGATÓRIO V1** (DP-01(c), 10/08/2026) · Fase B7
- [ ] RF-INT-006 Checkpoint e retomada de execuções longas — NÃO INICIADO · RECOMENDADO V1, não bloqueia (DP-01(c))

### COM — comunicação
- [x] RF-COM-001 E-mails em massa com templates e relatório — CONCLUÍDO
- [x] RF-COM-002 Telegram em massa com proteção de token — CONCLUÍDO
- [ ] RF-COM-003 Idempotência e limites de envio em comunicação — NÃO INICIADO

### WEB — web scraping e RPA
- [x] RF-WEB-001 Scraping HTML paginado por seletores CSS — CONCLUÍDO
- [ ] RF-WEB-002 Scraping com JavaScript (navegador) — PARCIAL (código + testes de unidade prontos; e2e pendente → CONCLUÍDO na Fase C1)
- [ ] RF-WEB-003 RPA de cadastro com screenshots mascarados — PARCIAL (código + testes de unidade prontos; e2e pendente → CONCLUÍDO na Fase C1)
- [ ] RF-WEB-004 Retomada e resiliência a mudanças de página — NÃO INICIADO

### GOV — governança e auditoria
- [x] RF-GOV-001 Relatórios consolidados do audit trail — CONCLUÍDO
- [x] RF-GOV-002 Painel HTML do audit trail — CONCLUÍDO
- [x] RF-GOV-003 Retenção, expurgo e mascaramento programáveis
- [x] RF-GOV-004 Verificação de integridade das evidências (HMAC) — CONCLUÍDO

### LIVE — Live System público
- [x] RF-LIVE-001 Catálogo curado com régua ativo/em breve — CONCLUÍDO
- [x] RF-LIVE-002 Execução isolada em 2 fases com SSE e downloads — CONCLUÍDO
- [x] RF-LIVE-003 Segurança do Live (rate limit, timeout+kill, egress lockdown...) — CONCLUÍDO
- [x] RF-LIVE-004 Jornada guiada de planilhas — CONCLUÍDO
- [x] RF-LIVE-005 Mocks determinísticos internos — CONCLUÍDO
- [ ] RF-LIVE-006 Ativação dos cards "em breve" — NÃO INICIADO · 006a (4 baratos) RECOMENDADO V1; 006b (extract_web_js, rpa_cadastro) fora da V1 pública por DP-02 — demonstração em vídeo/GIF, reavaliação na Fase D
- [x] RF-LIVE-007 Frontend integrado consumindo APIs reais — CONCLUÍDO

## 6. Ritual de atualização (obrigatório a cada entrega)

```
selecionar requisito (aqui e em 03)
  → planejar (subetapa em 06)
  → implementar
  → testar (automatizado; manual quando interface)
  → validar critérios de aceite (03 + 09)
  → registrar evidências (comando executado + resultado + caminhos)
  → atualizar a matriz (05)
  → marcar o requisito (aqui, seção 5)
  → commit correspondente (mensagem sugerida em 06)
```

Um requisito só muda para CONCLUÍDO com todos os itens do DoD aplicável (09).

## 7. Restrições vigentes desta etapa

**Fase A1 concluída (10/08/2026).** Próximas etapas autorizadas a serem
**planejadas** (não executadas nesta etapa): A1.1, A1.2, A1.3 e A1.4, na ordem, e
somente depois delas a A2.

Nesta etapa alteram-se **apenas os Markdown do pacote documental**. Permanecem
**proibidos**: alterar código, `.gitignore`, fixtures, `.vscode`, dependências ou
workflows; executar `npm audit fix`; e ainda: alterar código de produto, testes,
dependências ou configurações; corrigir problemas encontrados sem autorização
expressa; mover ou excluir arquivos; commit; push; tag; release; bump de versão;
README final; CHANGELOG final; iniciar A2 ou B1; e marcar qualquer requisito como
concluído sem código, testes e evidências.

Falha encontrada na A1 é registrada com evidência, impacto e correção recomendada —
nunca corrigida em silêncio. O README atual está **desatualizado de
propósito** (banner/badge `v1.1.0` vs pacote `1.4.0` + trabalho não lançado) e será
regenerado apenas no ritual de fechamento de release já definido pelo projeto.
