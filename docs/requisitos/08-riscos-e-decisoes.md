# 08 — Riscos e Decisões (revisão 3 — baseline aprovado em 10/08/2026)

## 1. Riscos técnicos

| ID | Risco | Evidência/base | Mitigação proposta |
|---|---|---|---|
| R-03 | ~~Baseline de testes do frontend divergente (52 × 31)~~ — **ENCERRADO em 05/08/2026**: o zip estava desatualizado; a validação local do responsável comprovou 52 + typecheck + build + audit 0 | execução da auditoria (31 no zip) + validação local do responsável | reconfirmação dos 52 pelo auditor na reauditoria do repositório atual (A1), mapeando os 21 testes ausentes do zip |
| R-04 | ~~CI não comprovável no snapshot~~ — **ENCERRADO na A1 (10/08/2026)**: `.github/workflows/ci.yml` e `docs.yml` existem e foram inspecionados | clone público de `origin/main` | evidência registrada em `04` RNF-CI-01 e `05` ressalva 2; lacunas da CI passam a ser o risco R-16 |
| R-07 | **Nenhuma execução automatizada cobre o caminho real de navegador**, e o marcador `e2e` não é usado por teste nenhum (`pytest -m e2e` seleciona zero) — regressões de scraping com JS e de RPA podem passar batidas | medido na A1: `tests/e2e/` = 1 arquivo, 1 passa + 1 *skipped* sem Chromium; `pytest -m e2e` → 0 selecionados | verificação com navegador obrigatória na C1 (`playwright install chromium && pytest tests/e2e`) e no ritual de release; corrigir a convenção de marcador; WEB-002/003 só viram CONCLUÍDO com essa evidência |
| R-15 | **`npm audit` com 1 vulnerabilidade alta — CONFIRMADO na árvore local (A1, 10/08/2026)**: `nanoid < 3.3.17` (GHSA-2v37-7h3g-55p8), alcançado na **cadeia de desenvolvimento** (`vite → postcss`). `npm audit --omit=dev` retornou **0** e a produção **não apresentou vulnerabilidade conhecida nesta auditoria** — o que **não autoriza ignorar o problema** | medição local do responsável + medição do auditor sobre o snapshot; `git diff` do `package-lock.json` **vazio** | **nenhuma correção aplicada e lockfile inalterado**; correção mínima planejada na subetapa **A1.3** (`06`): `npm explain nanoid` → `npm audit fix --dry-run` → menor atualização compatível, preservando o Tailwind atual (sem migrar para v4) e sem atualização ampla. **`npm audit fix --force` é proibido** |
| R-16 | **Lacunas da CI — CONFIRMADO com os workflows locais (A1, 10/08/2026), risco mantido aberto**: a CI roda Python 3.12/3.13, `ruff check`, `ruff format --check`, `mypy src/`, bandit, `pytest` do núcleo e gate de cobertura, mas **não executa** `apps/api/tests`, `npm ci`, `npm audit`, `npm audit --omit=dev`, `npm run typecheck`, `npm test`, `npm run build` nem Playwright real | inspeção de `.github/workflows/ci.yml` e `docs.yml` locais (idênticos aos do remoto) + `pyproject.toml` (`testpaths = ["tests"]`) | consolidação planejada na subetapa **A1.4** (`06`), com workflow de documentação mantido separado; hoje "CI verde" **não** significa Live backend e frontend verdes |
| R-17 | **Trabalho preservado somente em uma máquina — quantificado na A1**: `main` local está **22 commits à frente** de `origin/main` (commit `f3f95de`, 05/08/2026); o remoto público está em `ac3e58d` (15/07/2026) e não contém os testes do frontend nem os componentes da jornada | `git status -sb` e `git rev-parse HEAD` locais | push, release e publicação continuam **proibidos** nesta etapa; recomendação registrada (não executada): backup local recuperável fora do diretório do projeto, por exemplo `git bundle create ..\autotarefas-backup-AAAAMMDD.bundle --all`, sem alterar o remoto |
| R-18 | **22 dos 52 testes de frontend podem não estar preservados pelo Git**: `apps/web/src/lib/spreadsheets.test.ts` existe e executou 22 testes, mas **não apareceu em `git ls-files` nem entre os arquivos não rastreados**. Hipótese **não confirmada** de regra de `.gitignore` alcançando diretórios `lib` | saída local de `git ls-files` e `git status --short` (A1) | confirmar na **A1.2** com `git check-ignore -v` e `git ls-files --error-unmatch` antes de qualquer conclusão; se confirmado, corrigir a regra (com autorização) para que o arquivo seja rastreado |
| R-19 | **Clonagem limpa pode não reproduzir os 2052 testes**: `tests/fixtures/planilhas/build_fixtures.py` está versionado, mas os **32 arquivos CSV/XLSX gerados não estão** | saída local de `git status --short` e `git ls-files` (A1) | avaliar na **A1.2**: determinismo do gerador, execução automática pelos testes/`conftest.py`, tamanho e conteúdo (apenas dados sintéticos, sem dados pessoais) e viabilidade de clonagem limpa; decidir entre versionar, gerar antes da suíte ou gerar em diretório temporário — **nenhuma decisão automática** |
| R-20 | **Baseline documental fora do controle de versão**: `git ls-files docs/requisitos` e `git status --short docs/requisitos` não retornaram arquivos — `docs/requisitos` **não está versionado no Git local**; o baseline aprovado existe apenas no pacote entregue | saída local dos dois comandos (A1) | subetapa **A1.1**: aplicar os 12 Markdown oficiais, verificar se a pasta não está sendo ignorada, validar links e contagens, e fazer um commit exclusivamente documental |

## 2. Riscos de produto

| ID | Risco | Base | Mitigação |
|---|---|---|---|
| R-01 | Visão maior que a capacidade de execução solo — 17 requisitos não iniciados, 7 deles obrigatórios da V1 | contagem da auditoria (51 requisitos) | subetapas pequenas e sequenciais (B1–B7); regra "fase nova só após fechar a anterior" |
| R-02 | 6 de 13 cards "em breve" minam a credibilidade da vitrine | `catalog.py` × `ACTIVE_AUTOMATIONS` | **DP-02 aprovada**: A3 ativa os 4 baratos (recomendado) e A4 substitui a promessa dos 2 de navegador por demonstração em vídeo/GIF |
| R-05 | Reconciliação — o problema mais universal do público-alvo — ainda não existe | grep sem resultados em `src/` | Fase B inteira, dentro da V1 (DP-04) |
| R-06 | Visitante enviando dados pessoais reais ao Live | uploads reais são aceitos | texto de transparência + TTL de 15 min + destaque para os arquivos de exemplo (DP-05, Fase A2) |
| R-11 | Posicionamento oscilando entre "plataforma" e "ferramenta" | texto de visão × decisão registrada | DP-06: natureza corrigida + tagline única |
| R-12 | **Escopo V1 alonga o caminho até o primeiro release** — com a promoção de INT-005 são 11 itens de trabalho novo ou parcial (10 requisitos + ajuste de vitrine A4) antes de lançar, em execução solo | escopo aprovado: 41 obrigatórios, 30 prontos | fases pequenas, cada uma entregando valor isolado; se o prazo apertar, cortam-se os RECOMENDADOS (A3, B8), nunca obrigatórios; nenhuma frente nova (sugestões do doc 07) antes de fechar a Fase B |

## 3. Decisões pendentes

**Nenhuma decisão pendente bloqueia o início da Fase A1.** Todas as DP abertas
foram aprovadas em 05/08/2026 e 10/08/2026 — registro na seção 4.

Itens que voltarão a exigir decisão, sem bloquear a V1:

| Item | Quando decidir | Origem |
|---|---|---|
| Fixar os números de RNF (disponibilidade, SLA, benchmark de volume, acessibilidade, capacidade da hospedagem) | após escolher a hospedagem e obter medições reproduzíveis | DP-03 (adiar, aprovado) |
| Formato definitivo dos conectores declarativos | Fase D, após pelo menos dois sistemas reais com contratos, autenticações e paginações diferentes | DP-01(b) + DP-08 |
| Revisão jurídica da política de retenção | antes de uso comercial com dados pessoais de clientes | DP-05 |
| Execução pública dos cards de navegador com Chromium | Fase D4, conforme hospedagem | DP-02 |

## 4. Registro de decisões tomadas

| Data | DP | Decisão | Documentos atualizados |
|---|---|---|---|
| 05/08/2026 | — | **Estrutura da documentação aprovada** como base oficial | nota no 00 |
| 05/08/2026 | DP-04 | **Reconciliação entra na V1**: REC-001..004 obrigatórios — a V1 representa o propósito central do produto | 00, 01, 03, 05, 06, 07 |
| 05/08/2026 | DP-06 | **Natureza e posicionamento**: "produto real de automação operacional, apresentado em portfólio e preparado para adaptação e utilização em ambientes profissionais"; tagline "ferramenta que trata planilhas e as conecta a sistemas" | 01 |
| 05/08/2026 | DP-07 | **Snapshot desatualizado**: baseline oficial de testes do frontend = 52 (+ typecheck, build, audit 0); reconfirmação na A1 | 00, 03, 04, 05, 08 |
| 05/08/2026 | — | **Convenção de status**: proibido status fora da legenda; WEB-002/003 como PARCIAL até o e2e | 00, 03, 05, 09 |
| 05/08/2026 | — | **Correção de contagem**: total catalogado = **51** requisitos (30 concluídos, 4 parciais, 17 não iniciados) | 00, 08 |
| **10/08/2026** | **DP-01(a)** | **Escopo obrigatório da V1 aprovado com ajuste: 41 requisitos** — os 40 propostos na revisão 2 mais a promoção de **RF-INT-005**. Progresso documental: **30/41**. Total catalogado permanece 51; situação geral permanece 30 concluídos, 4 parciais e 17 não iniciados. A promoção não altera a situação de implementação de INT-005 | 00, 01, 03, 05, 06, 09, README |
| **10/08/2026** | **DP-01(b)** | **RF-INT-004 (conectores declarativos) é PÓS-V1**; o formato só será definido após experiência com pelo menos dois sistemas reais diferentes | 01, 03, 05, 06 |
| **10/08/2026** | **DP-01(c)** | **RF-INT-005 OBRIGATÓRIO na V1** (mapeamento pertence ao contrato de importação: corrigir a planilha e adequá-la a uma API são responsabilidades distintas), com **12 exigências funcionais consolidadas em 11 critérios de aceite** registradas na ficha (formulação padronizada em 10/08/2026); **RF-INT-006 RECOMENDADO e não bloqueante**. Vedado transformar INT-005 em framework universal de conectores nesta fase | 01, 02, 03, 05, 06, 09 |
| **10/08/2026** | **DP-01(d)** | **Recorte de RF-CORE-006 aprovado**: configuração reutilizável do fluxo de planilhas, execução por `autotarefas run fluxo.yaml`, validação da configuração, precedência CLI > configuração > padrão, proibição de segredos embutidos; encadeamento genérico de tarefas arbitrárias permanece PÓS-V1 | 01, 03, 05, 06 |
| **10/08/2026** | **DP-02** | **Cards de navegador**: retirar da V1 pública a promessa de execução direta no Live; demonstrar por vídeo/GIF; manter implementação real no Core e no CLI; não excluir código nem testes; reavaliar execução pública com Chromium na Fase D, após a hospedagem. Implementação do ajuste: subetapa **A4** (obrigatória antes do release) | 01, 02, 03, 05, 06 |
| **10/08/2026** | **DP-03** | **Manter pendentes** os números de disponibilidade, SLA, benchmark de volume, acessibilidade e capacidade da hospedagem; nenhum valor provisório inventado. Definição após a escolha da hospedagem e medições reproduzíveis | 04 |
| **10/08/2026** | **DP-05** | **Política de retenção aprovada com separação por ambiente** — Live: uploads/artefatos TTL 15 min, logs sem dados sensíveis 30 dias, screenshots mascaradas 7 dias, audit 30 dias; modo real: uploads/artefatos configuráveis, logs 30 dias por padrão (configurável), screenshots 30 dias por padrão (configurável), audit configurável com exclusão manual confirmada. O Live deve informar finalidade, retenção, arquivos de exemplo, recomendação sobre dados pessoais e a diferença entre demonstração pública e modo real. **Política técnica, sujeita a revisão jurídica antes de uso comercial com dados pessoais de clientes** | 01, 03, 04, 06 |
| **10/08/2026** | **DP-08** | **Decisão definitiva sobre conectores YAML na Fase D**, após testar pelo menos dois sistemas reais com contratos, autenticações e paginações diferentes; as tasks específicas existentes continuam funcionando independentemente | 03, 05, 06 |
| **10/08/2026** | **PA-01** | **Resolvida — opção (a).** O audit do Live permanece somente durante a vida do workspace, com **retenção máxima de 15 minutos**; **não existe audit agregado do servidor na V1**; a retenção de 30 dias fica **reservada para um futuro audit agregado**, caso venha a ser aprovado; **nenhum RF-LIVE-008 criado agora**; a documentação não promete 30 dias para um recurso ausente da arquitetura atual | 04 (RNF-PRIV-04/07), 06 (A2), 08 |
| **10/08/2026** | **PA-02** | **Resolvida — opção (a) com qualificação.** Screenshots do RPA **não são aplicáveis ao Live público da V1**, porque o RPA não roda publicamente (DP-02); o prazo preventivo de **7 dias** vale **somente se** a execução pública com navegador for habilitada na Fase D; no modo real privado permanece o padrão configurável de **30 dias**; a decisão **não cria implementação nova na V1** | 04 (RNF-PRIV-04/08), 06 (A2), 08 |
| **10/08/2026** | — | **Padronização de RF-INT-005**: a formulação oficial passa a ser "**12 exigências funcionais consolidadas em 11 critérios de aceite**", sem remover nenhum comportamento especificado | 03, 05, 08, 09 |
| **10/08/2026** | — | **Fase A1 autorizada** (reauditoria do repositório Git atual). Permanecem proibidos: código de produto, release, tag, push e alteração de versão até a conclusão da A1; versão do software mantida em `1.4.0`; PDF final não gerado nesta etapa | 00 (§7), 06, README |
| **10/08/2026** | — | **Fase A1 CONCLUÍDA como atividade de auditoria** (decisão do responsável): evidências coletadas, suítes executadas, workflows locais inspecionados, estado do Git identificado, inconsistências comprovadas e nenhuma correção aplicada em silêncio. **Auditoria concluída ≠ achados corrigidos**: os achados originam as subetapas obrigatórias A1.1, A1.2, A1.3 e A1.4, que precedem a A2. A conclusão da A1 **não conclui nenhum requisito funcional** | 00, 04, 05, 06, 08, 09, README |
| **10/08/2026** | — | **Baseline técnico local registrado**: commit `f3f95de`, branch `main` 22 commits à frente de `origin/main`, suíte principal **2052 passed** com cobertura **92,39 %**, backend Live **127 passed**, frontend **52 passed** (22 + 16 + 14), typecheck e build aprovados, `npm audit` com 1 alta de desenvolvimento e `--omit=dev` em 0, `package-lock.json` inalterado. O remoto público passa a ser referência histórica desatualizada | 00 §4.1, 04, 05 |
| **10/08/2026** | — | **RF-WEB-003**: teste automatizado com **navegador real** é obrigatório antes da promoção a CONCLUÍDO; homologação manual é **complementar, não substituta**; se o teste não existir, deve ser criado antes da conclusão | 03, 05, 09 |
| **10/08/2026** | — | **Revisão documental 3** — baseline documental aprovado. Versão do software inalterada (`1.4.0`); implementação de produto não iniciada | todos |

## 5. Pontos levantados na revisão 3 — **resolvidos em 10/08/2026**

Nenhum ponto pendente. Registro para rastreabilidade (decisões completas em §4):

| ID | Ponto | Resolução aprovada |
|---|---|---|
| PA-01 | Retenção do audit no Live ("30 dias" × workspace com TTL de 15 min) | **Opção (a)**: audit do Live vive dentro do workspace, retenção máxima de 15 min; sem audit agregado do servidor na V1; os 30 dias ficam reservados a um futuro audit agregado, se aprovado; nenhum requisito novo criado — detalhado em `04` RNF-PRIV-07 e refletido na A2 (`06`) |
| PA-02 | Prazo de 7 dias para screenshots no Live, com o RPA fora da vitrine | **Opção (a) com qualificação**: não aplicável ao Live público da V1; os 7 dias valem somente se a execução pública com navegador for habilitada na Fase D; modo real permanece com 30 dias configuráveis; sem implementação nova na V1 — detalhado em `04` RNF-PRIV-08 |
