# Documento Oficial de Requisitos — AutoTarefas

*Formato inspirado na estrutura de um formulário institucional de solicitação de
desenvolvimento de software (identificação → objetivo → justificativa → requisitos
→ critérios → pós-implementação → suporte), estendido com controle de
desenvolvimento, testes, evidências e progresso. Após aprovação, este documento
poderá originar versões profissionais em DOCX e PDF.*

---

## 1. Capa

| | |
|---|---|
| **Documento** | Documento Oficial de Requisitos de Produto |
| **Projeto** | AutoTarefas — Robô de Automação Operacional |
| **Versão do documento** | 1.2 — **revisão 3: baseline documental aprovado** (10/08/2026) |
| **Situação** | BASELINE DOCUMENTAL APROVADO (escopo V1 e decisões DP-01/02/03/05/08 aprovados em 10/08/2026; implementação não iniciada) |
| **Local/Data** | Brasília/DF, 10 de agosto de 2026 |

## 2. Identificação do projeto

| Campo | Valor |
|---|---|
| Nome do produto | AutoTarefas |
| Repositório | `paulor007/autotarefas` (GitHub) |
| Versão do pacote no snapshot | `1.4.0` (`src/autotarefas/__init__.py`) + bloco "Não lançado" no CHANGELOG (Live System) |
| Licença | MIT |
| Linguagens/stack | Python ≥ 3.12 (núcleo, CLI, Live backend FastAPI) · TypeScript/React 18 + Vite + Tailwind (Live frontend) · SQLite (audit trail) |
| Natureza | Produto real de automação operacional, apresentado em portfólio e preparado para adaptação e utilização em ambientes profissionais |

## 3. Informações do responsável

| Campo | Valor |
|---|---|
| Responsável | Paulo Lavarini (`paulo.lavarini@gmail.com`, GitHub `paulor007`) |
| Papel | Desenvolvedor, analista de requisitos e mantenedor único |
| Aprovação de escopo | Exclusiva do responsável (registrada em `08-riscos-e-decisoes.md`) |

## 4. Título

**AutoTarefas — automação operacional de planilhas, arquivos e integrações, com
evidências auditáveis.**

## 5. Objetivo

Receber um trabalho operacional (arquivos, planilhas, dados ou configurações),
executar as etapas necessárias — analisar, validar, comparar, corrigir, organizar,
formatar, integrar — e devolver um **resultado pronto para uso**, sempre
acompanhado de **evidências** (relatórios, manifestos, hashes e trilha de
auditoria), reduzindo ao máximo a repetição manual do mesmo procedimento.

## 6. Justificativa

Empresas, órgãos públicos, escritórios e profissionais autônomos ainda executam
manualmente tarefas de alto volume e baixo valor cognitivo: conferir planilhas
célula a célula, digitar cadastros sistema a sistema, copiar dados entre bases,
organizar arquivos, disparar comunicações uma a uma. Esse trabalho é lento,
sujeito a erro, difícil de auditar e concentrado em pessoas específicas.

O AutoTarefas ataca esse problema com três compromissos verificáveis no código:

1. **Nunca inventar dado** — só transformações determinísticas e conservadoras,
   cada uma registrada (regra de ouro documentada em
   `src/autotarefas/tasks/cleaning.py` e `src/autotarefas/reader/normalize.py`).
2. **Nunca destruir dado** — o arquivo original é preservado; operações destrutivas
   exigem confirmação (`--yes`) e oferecem `--dry-run`.
3. **Sempre deixar evidência** — trilha append-only com HMAC
   (`src/autotarefas/core/audit.py`), relatórios por linha, manifestos com hashes
   (`src/autotarefas/tasks/execution_package.py`).

## 7. Problemas operacionais resolvidos

| # | Problema real | Como o AutoTarefas resolve hoje | Situação |
|---|---|---|---|
| 1 | Planilhas com erros invisíveis (CPF/CNPJ inválidos, vazios, duplicatas, tipos misturados, valores que não batem entre colunas) | Análise estrutural + validação por schema YAML + regras de grupo/derivadas; separa válidos de inválidos com motivo | Entregue |
| 2 | Limpeza manual arriscada | Modo limpeza com transformações seguras e trilha antes/depois | Entregue |
| 3 | Digitação de cadastros em sistemas | Importação via API com idempotência, retry e reenvio só dos falhos; RPA por navegador quando não há API | Entregue |
| 4 | Extração manual de dados de sistemas/sites | Exportação via API paginada e scraping (HTML e JavaScript) para CSV/XLSX/JSON | Entregue |
| 5 | Perda de arquivos antes de mexer neles | Backup ZIP com hash SHA-256 e dry-run | Entregue (sem restauração ainda) |
| 6 | Pastas desorganizadas | Organização por regras YAML com prévia | Entregue (sem undo ainda) |
| 7 | Comunicação em massa manual | E-mail e Telegram a partir de planilha, com templates e relatório por linha | Entregue |
| 8 | Falta de prova do que foi feito | Audit trail HMAC + relatórios + painel HTML + pacote de evidências | Entregue |
| 9 | Conferência entre duas bases (reconciliação) | — | **Não iniciado** (maior lacuna de valor; ver seção 26 e RF-REC) |
| 10 | Repetir a mesma configuração toda vez | Parcial: schemas e perfis YAML reutilizáveis; "receitas" completas salvas ainda não existem | Parcial |

## 8. Público-alvo

- **Primário (modo real):** profissionais autônomos, escritórios e pequenos
  negócios brasileiros que operam planilhas e sistemas simples; setores
  administrativos/financeiros/cadastro de empresas e órgãos públicos.
- **Secundário (Live System):** visitantes, clientes em potencial e recrutadores,
  que precisam **ver o produto funcionando de verdade** sem instalar nada e sem
  risco.
- Perfil de operação: usuário técnico ou semi-técnico no CLI; leigo assistido na
  interface Live (jornada guiada).

## 9. Escopo da Versão 1 — **aprovado em 10/08/2026 (DP-01)**

A V1 é definida pelo **propósito central do produto**, não pelo que já está
pronto: o fluxo de planilhas precisa entregar valor operacional completo
(subseção 9.1) e a planilha tratada precisa **chegar ao sistema de destino** com
mapeamento configurável.

**OBRIGATÓRIO V1 (41 requisitos):**

- Os 30 já CONCLUÍDOS: CORE-001..005, ARQ-001, ARQ-003, PLA-001..008,
  INT-001..003, COM-001..002, WEB-001, GOV-001/002/004, LIVE-001..005/007.
- Os 4 PARCIAIS, a concluir: **RF-GOV-003** (retenção/expurgo — política
  aprovada em DP-05), **RF-CORE-006** (no recorte aprovado em DP-01(d)),
  **RF-WEB-002** e **RF-WEB-003** (implementados e testados em unidade; viram
  CONCLUÍDO com a evidência e2e da homologação).
- Os 7 NÃO INICIADOS que realizam o propósito central: **RF-REC-001..004**
  (comparar, conciliar, transferir, configurar), **RF-PLA-009** (preservação da
  apresentação), **RF-PLA-010** (correções por regras confirmadas) e
  **RF-INT-005** (mapeamento configurável de colunas na importação — promovido a
  obrigatório em DP-01(c)).

**Recorte V1 de RF-CORE-006 (DP-01(d) aprovada):** obrigatória a *configuração
reutilizável do fluxo de planilhas* — um YAML descrevendo a operação completa
(leitura, validação, tratamento, reconciliação, apresentação), executável por
`autotarefas run fluxo.yaml`, com validação da configuração, precedência
CLI > configuração > padrão e proibição de segredos embutidos; internamente
multi-etapas, externamente uma operação. O **encadeamento genérico** de tasks
arbitrárias permanece PÓS-V1.

**Recorte V1 de RF-INT-005 (DP-01(c) aprovada):** mapeamento de coluna da
planilha para campo do sistema por parâmetros de CLI ou arquivo simples, com
validação dos campos obrigatórios do destino, detecção de mapeamentos repetidos
ou incompatíveis, prévia do payload, dry-run sem gravação externa, preservação do
arquivo original, registro do mapeamento aplicado e relatório de aceitos,
rejeitados e falhos. **Não** é um framework universal de conectores nesta fase —
conectores declarativos seguem PÓS-V1 (DP-01(b)/DP-08).

**RECOMENDADO V1 (entra se houver folga; não bloqueia o release):**
RF-LIVE-006a (ativar os 4 cards baratos) e **RF-INT-006** (checkpoint/retomada).

**PÓS-V1:** RF-INT-004 (conectores declarativos — formato definido só após
experiência com ao menos dois sistemas reais distintos), RF-CORE-007,
RF-CORE-008, RF-ARQ-002/004/005, RF-COM-003, RF-WEB-004, **RF-LIVE-006b** (cards
de navegador: por DP-02, saem da V1 pública como executáveis, com demonstração em
vídeo/GIF; implementação real mantida no Core e no CLI e reavaliação de execução
pública na Fase D) e o encadeamento genérico de CORE-006.

### 9.1 Resultado operacional mínimo da V1 (fluxo de planilhas completo)

O produto, na V1, precisa conseguir — de ponta a ponta e com evidências:

| # | Etapa do resultado | Requisito responsável |
|---|---|---|
| 1 | Analisar a planilha recebida | PLA-001, PLA-002, PLA-003 |
| 2 | Comparar com outra base/versão | REC-001 |
| 3 | Identificar divergências (com tolerâncias e prioridade de fontes) | REC-001, REC-002 |
| 4 | Corrigir o que estiver autorizado | PLA-006 (determinístico) + PLA-010 (regras confirmadas) |
| 5 | Transferir informações entre bases | REC-003 |
| 6 | Preservar a apresentação existente quando apropriado | PLA-009 |
| 7 | Aplicar apresentação profissional quando necessário | PLA-007 |
| 8 | Gerar uma nova planilha corrigida (original intocado) | PLA-007 + PLA-009 |
| 9 | Registrar tudo que foi alterado | CORE-002, PLA-006, PLA-008 |
| 10 | Separar situações ambíguas para revisão | PLA-005 (issues), REC-002 (conflitos) |
| 11 | Reutilizar a configuração em execuções futuras | CORE-006 (recorte V1) + REC-004 |

**Complemento aprovado em 10/08/2026:** além das 11 etapas acima, a V1 entrega o
resultado **ao sistema de destino** — a planilha tratada é importada com
mapeamento configurável de colunas, prévia de payload e dry-run (RF-INT-005).
Corrigir a planilha (PLA-010) e adequá-la ao contrato de uma API (INT-005) são
responsabilidades distintas e ambas obrigatórias.

**Regra transversal:** nenhuma decisão incerta é tomada silenciosamente — toda
ambiguidade ou conflito fora das regras declaradas vira item de revisão
identificado (reforça a regra global nº 3, seção 16).

## 10. Fora de escopo (produto, não apenas V1)

- Plataforma SaaS multiusuário com contas, cobrança e permissões.
- Serviços pagos ou por assinatura como dependência (convenção do projeto:
  somente soluções gratuitas/open-source).
- IA generativa decidindo transformações de dados (sugestões, quando existirem,
  serão determinísticas e explicáveis — RF-CORE-007).
- Scraping de SPAs com paginação por clique (limite documentado em
  `tasks/extract_web.py`).
- KPIs/analytics de negócio no MVP (decisão anterior mantida).
- Execução no Live de qualquer automação com credencial real ou URL externa livre.

## 11. Visão geral da solução

```
entrada (arquivo/planilha/API/página)
   → analisar (estrutura, tipos, confiança)
   → validar (schema, regras, duplicatas, grupos, derivadas)
   → corrigir com segurança (limpeza determinística com trilha)
   → organizar/formatar (artefatos CSV/JSON/XLSX profissionais)
   → integrar (API, e-mail, Telegram, RPA)
   → entregar resultado pronto
   → registrar evidências (audit HMAC, manifesto, hashes, relatórios)
```

Dois modos, mesma base de código:

- **Modo real** — CLI `autotarefas` sobre arquivos e sistemas do usuário,
  configurado por `.env`/variáveis (segredos via `SecretStr`, nunca em log).
- **Live System público** — vitrine segura em `live_demo/`: os mesmos comandos
  reais executados por subprocesso em sandbox, contra mocks internos, com
  streaming do stdout e artefatos baixáveis.

## 12. Arquitetura funcional

| Camada | Local | Papel |
|---|---|---|
| Núcleo transversal | `src/autotarefas/core/` | BaseTask/TaskResult, audit SQLite+HMAC, segurança, settings, logger, browser Playwright |
| Leitura de planilhas | `src/autotarefas/reader/` | XLSX (openpyxl, preservando `number_format`) e CSV; detecção de aba/cabeçalho com confiança; normalização com trilha |
| Perfilagem | `src/autotarefas/profiling/` | Observa a estrutura (sem domínio — teste de arquitetura garante), relatório, schema sugerido |
| Serviço de análise | `src/autotarefas/services/analysis.py` | Um passo: ler → perfilar → relatar → sugerir schema, com veredito de ambiguidade |
| Perfis | `src/autotarefas/profiles/` | Perfis YAML embutidos, remapeamento conceito→coluna real, exportação de schema |
| Tarefas | `src/autotarefas/tasks/` | 11 tasks concretas + módulos de apoio (issues, validators, duplicates, row_rules, expressions, cleaning, artifacts, relatórios, pacote de execução) |
| CLI | `src/autotarefas/cli/` | 13 comandos; flags globais `--dry-run`, `--yes`, `-v/-q` |
| Dashboard estático | `src/autotarefas/dashboard/` | Painel HTML autocontido do audit trail (não é o Live) |
| Mocks de desenvolvimento | `tools/demo_server/` | Sistema-alvo Flask: cadastro HTML (RPA), API paginada de clientes/catálogo, catálogo HTML e JS, mock do Telegram |
| Live backend | `live_demo/backend/app/` | FastAPI: catálogo curado, execução em sandbox com SSE, jornada guiada de planilhas |
| Live frontend | `live_demo/frontend/src/` | React consumindo somente APIs reais do backend |

## 13. Módulos (famílias de requisitos)

CORE (fundação) · ARQ (arquivos/pastas) · PLA (planilhas) · REC (reconciliação —
novo, ainda não iniciado) · INT (APIs) · COM (comunicação) · WEB (scraping/RPA) ·
GOV (governança) · LIVE (vitrine pública). IDs permanentes `RF-<MÓDULO>-NNN`.

## 14. Requisitos funcionais

A ficha completa de cada requisito (28 campos, incluindo fluxos, critérios de
aceite, modo Live vs. real, testes, evidências e lacunas) está em
`03-requisitos-funcionais.md`. Abaixo, o resumo no padrão do formulário de
referência, por módulo.

### 14.1 CORE — Fundação

| Campo | Conteúdo |
|---|---|
| Funcionalidades | RF-CORE-001 a 008 |
| Descrição detalhada | Toda automação herda de `BaseTask` e devolve `TaskResult` tipado com timing e status (`SUCCESS/PARTIAL/FAILURE`); toda execução vai para trilha append-only SQLite com HMAC do input; helpers de segurança (anti path-traversal, validação de URL, mascaramento); configuração por `.env` com `SecretStr`; CLI única com `--dry-run` e `--yes`. |
| Critérios de avaliação | Nenhuma task existe fora do padrão; nenhuma execução sem registro no audit; nenhum segredo em log/relatório. |
| Regras de negócio | Audit é append-only; dry-run nunca altera estado; confirmações destrutivas exigem `--yes` ou prompt. |
| Dependências | click, rich, loguru, pydantic v2, SQLite (stdlib), cryptography. |

### 14.2 ARQ — Arquivos e pastas

| Campo | Conteúdo |
|---|---|
| Funcionalidades | RF-ARQ-001 a 005 |
| Descrição detalhada | Backup ZIP (deflate) de múltiplas fontes com excludes tipo gitignore, hash SHA-256 do pacote e dry-run; organização de arquivos por regras YAML com variáveis `{year}/{month}/{ext}`, conflitos `skip/rename/overwrite`, não recursiva, primeira regra vence. |
| Critérios de avaliação | Backup íntegro (hash confere); organização listada em prévia idêntica à execução real. |
| Regras de negócio | Original nunca é alterado pelo backup; organize sem `--yes` só simula. |
| Requisitos adicionais (lacunas) | Manifesto de conteúdo, validação/restauração, undo e retenção de backups ainda não existem (RF-ARQ-002/004/005). |
| Dependências | zipfile/hashlib (stdlib), PyYAML, pydantic. |

### 14.3 PLA — Planilhas

| Campo | Conteúdo |
|---|---|
| Funcionalidades | RF-PLA-001 a 010 |
| Descrição detalhada | Leitura CSV/XLSX preservando metadados de célula; detecção de aba/cabeçalho com nota de confiança e recusa explícita quando ambíguo; perfilagem sem domínio; schema sugerido editável; perfis prontos com remapeamento; validação célula a célula (tipos, regex, faixas, enum, CPF/CNPJ/e-mail/telefone), duplicatas, consistência por grupos e colunas derivadas com mini-linguagem aritmética segura (AST, sem `eval`); modo limpeza com trilha antes/depois; artefatos `registros_validos.csv`, `registros_invalidos.csv` (+motivo), relatórios JSON/CSV, `planilha_validada.xlsx` com 4 abas formatadas e pacote de evidências com `manifest.json` e hashes. |
| Critérios de avaliação | Original intocado; nenhum dado inventado; toda alteração de limpeza auditável; planilha errada nunca entregue em silêncio (ambiguidade → pergunta). |
| Regras de negócio | Linha inválida = ao menos um problema ERROR (avisos não invalidam); zeros à esquerda preservados; contadores do XLSX gravados como valores. |
| Requisitos adicionais (lacunas) | Preservar a formatação original ao gerar versão tratada e correções por regra confirmada (RF-PLA-009/010). |
| Dependências | pandas, openpyxl, PyYAML. |

### 14.4 REC — Reconciliação e transferência (não iniciado)

| Campo | Conteúdo |
|---|---|
| Funcionalidades | RF-REC-001 a 004 |
| Descrição detalhada | Comparar duas ou mais planilhas por chaves simples/compostas com normalização prévia e tolerâncias; classificar registros (só na base A, só na B, iguais, divergentes, conflitos, duplicados); gerar base conciliada e relatório de decisões; transferir/enriquecer campos autorizados entre bases mantendo origem por informação; salvar a configuração para reuso. |
| Critérios de avaliação | Nenhuma célula da fonte alterada sem autorização de campo; todo conflito vai para revisão, nunca resolvido em silêncio. |
| Dependências | Reusa `reader` + `profiling` + `artifacts`/`execution_package`; sem dependência nova prevista. |

### 14.5 INT — Integração via API

| Campo | Conteúdo |
|---|---|
| Funcionalidades | RF-INT-001 a 006 |
| Descrição detalhada | Exportação de API paginada (formato `{data, has_next, ...}`) com retry exponencial, rate limit e dry-run, salvando CSV/XLSX/JSON; importação de planilha via POST por linha com `Idempotency-Key` determinística, retry que respeita `Retry-After`, relatório por linha e `registros_falhos.csv` reenviável com a mesma chave; sincronização origem→destino por composição das duas tasks (trilha granular: extract_api, send_api e sync_api no audit). |
| Critérios de avaliação | Reenvio dos falhos não duplica cadastros em sistemas idempotentes; erros de dado (4xx) não são retentados. |
| Requisitos adicionais | **RF-INT-005 — mapeamento de colunas configurável: OBRIGATÓRIO V1** (DP-01(c)); RF-INT-006 (checkpoint/retomada): RECOMENDADO V1, não bloqueia; RF-INT-004 (conectores declarativos, 1 YAML por sistema, segredos só via `*_env`, 4 estratégias de paginação): PÓS-V1 (DP-01(b)/DP-08). |
| Dependências | httpx, tenacity, pandas/openpyxl. |

### 14.6 COM — Comunicação

| Campo | Conteúdo |
|---|---|
| Funcionalidades | RF-COM-001 a 003 |
| Descrição detalhada | E-mail em massa via SMTP (stdlib) com templates `{coluna}` no assunto/corpo, STARTTLS opcional, rate limit e relatório por linha; Telegram via Bot API com destino fixo ou por coluna, token nunca persistido (redação inclusive dentro de exceções) e conteúdo da mensagem não gravado em disco. |
| Critérios de avaliação | Nenhuma credencial em log/audit/relatório; falha em uma linha não interrompe as demais. |
| Requisitos adicionais (lacunas) | Idempotência por mensagem e teto de envios por execução (RF-COM-003). |
| Dependências | smtplib/email (stdlib), httpx. |

### 14.7 WEB — Scraping e RPA

| Campo | Conteúdo |
|---|---|
| Funcionalidades | RF-WEB-001 a 004 |
| Descrição detalhada | Extração de páginas HTML por seletores CSS com paginação por link "próxima" (BeautifulSoup); modo `--js` renderizando com Chromium headless (Playwright) reutilizando uma sessão; RPA de cadastro lendo planilha e preenchendo formulário web com health check prévio, CPF validado (módulo 11), duplicado marcado como `skipped` e screenshot mascarado em erro. |
| Critérios de avaliação | Linha ruim não derruba o lote; evidência visual de falha sem expor dado sensível. |
| Requisitos adicionais (lacunas) | Retomada após falha e tratamento de mudança de layout de página (RF-WEB-004). |
| Dependências | beautifulsoup4, playwright (+ `playwright install chromium` no modo real). |

### 14.8 GOV — Governança e auditoria

| Campo | Conteúdo |
|---|---|
| Funcionalidades | RF-GOV-001 a 004 |
| Descrição detalhada | Relatórios do audit (`summary/list/errors`, com filtros) somente leitura; painel HTML autocontido (CSS embutido, escape de todo valor dinâmico) com verificação do `input_hash` HMAC; mascaramento de sensíveis em dicts; logs rotacionados. |
| Critérios de avaliação | Consultas jamais escrevem no audit; qualquer adulteração do input detectável pela verificação HMAC. |
| Requisitos adicionais (lacunas) | Retenção/expurgo programáveis do audit e de artefatos (hoje: logs 30 dias fixo em `core/logger.py`; `screenshot_retention_days` existe em settings sem rotina de expurgo) — RF-GOV-003. |
| Dependências | SQLite, cryptography, loguru. |

### 14.9 LIVE — Vitrine pública

| Campo | Conteúdo |
|---|---|
| Funcionalidades | RF-LIVE-001 a 007 |
| Descrição detalhada | Catálogo curado de 13 automações em 7 categorias, com 7 ativas e 6 "em breve" (front separa pelas `active_automations` do health; backend responde 501 fora da régua); execução em duas fases (POST `/api/run/{id}` → SSE `/api/stream/{token}` → `/api/result` → `/api/download`) em workspace UUID isolado com `AUTOTAREFAS_HOME` próprio; jornada guiada de planilhas (`/api/spreadsheets/analyze → selection → schema → validate`) aceitando exemplo, upload, perfil embutido ou YAML do visitante (limite 256 KB); mocks internos determinísticos; frontend React consumindo somente as APIs reais. |
| Critérios de avaliação | Visitante nunca informa caminho/comando; download só de nomes simples dentro de `out/`; segunda demonstração seguida funciona (reset automático do mock de CRM). |
| Regras de negócio | Sem credencial real, sem URL externa livre, egress bloqueado por proxy morto (`EGRESS_LOCKDOWN=true` por padrão) com exceção apenas de `127.0.0.1/localhost`. |
| Dependências | FastAPI, uvicorn, sse; React/Vite/Tailwind. |

## 15. Requisitos não funcionais

Detalhados e mensuráveis em `04-requisitos-nao-funcionais.md`. Resumo no padrão
do formulário de referência:

**DESEMPENHO (Live):** timeout de execução 60 s (kill); 4 execuções simultâneas;
rate limit 12 req/min/IP; upload ≤ 10 MB e ≤ 50 arquivos; stream ≤ 2.000
linhas/256 KB; ≤ 40 workspaces com TTL de 15 min (valores reais de
`live_demo/backend/app/config.py`, ajustáveis por env). Usuários simultâneos
esperados: vitrine pública de baixo volume — sem estimativa formal (DECISÃO
PENDENTE DP-03).

**CONFIABILIDADE:** suíte do núcleo com gate de cobertura ≥ 85 % (`pyproject.toml`);
retry com backoff apenas em erros temporários; status `PARTIAL` explícito;
disponibilidade do Live: DECISÃO PENDENTE (hospedagem ainda não fixada).

**SEGURANÇA:** criticidade dos dados — *Interno/possivelmente pessoal* (planilhas
de terceiros); autenticação — N/A no Live público (somente leitura/execução em
sandbox), segredos do modo real via variáveis de ambiente; auditoria — trilha
append-only com HMAC-SHA256 e verificação de integridade; subprocesso sem shell
com argv por allowlist; anti path-traversal em uploads e downloads.

**USABILIDADE:** interface e mensagens 100 % em português; Live responsivo
(Tailwind, grid 1→4 colunas); acessibilidade formal (WCAG): NÃO COMPROVADO —
DECISÃO PENDENTE DP-03.

**DADOS:** migração de sistema legado — Não. Dados do visitante no Live são
efêmeros (workspace TTL 15 min).

**INFRAESTRUTURA:** modo real on-premises (máquina do usuário); Live em
hospedagem gratuita a definir (DECISÃO PENDENTE); documentação via GitHub Pages.

## 16. Regras de negócio globais

1. Nunca inventar dado; transformações apenas determinísticas e registradas.
2. Original preservado sempre; saídas em arquivos novos.
3. Ambiguidade estrutural gera pergunta, não escolha silenciosa.
4. Toda execução registra evidência; segredos jamais persistem.
5. Operação destrutiva ou externa exige confirmação explícita ou dry-run prévio.
6. Linha com erro não interrompe o lote; resultado agregado reflete `PARTIAL`.
7. Live nunca executa fora da allowlist nem alcança a internet.

## 17. Dependências

Ver blocos por módulo na seção 14 e `pyproject.toml` (faixas com limite superior
de major). Dependências de execução do modo real que exigem passo extra:
`playwright install chromium` (WEB-002/003). Nenhuma dependência paga.

## 18. Segurança e privacidade

Síntese (detalhes em `04`, seção SEG/PRIV): allowlists de caminho e de argv;
`SecretStr` + mascaramento; redação de token em erros; screenshots mascarados;
HMAC no audit; egress lockdown no Live; conteúdo de mensagens de comunicação não
persistido. LGPD: dados pessoais tratados localmente pelo usuário (modo real) ou
efêmeros em sandbox (Live). **Política de retenção aprovada em 10/08/2026
(DP-05)**, com separação entre ambientes e implementação em RF-GOV-003 (Fase A2) —
detalhamento em `04` (RNF-PRIV). O Live passa a informar finalidade do
processamento, tempo de retenção, existência de arquivos de exemplo, recomendação
de não enviar dados pessoais desnecessários e a diferença entre demonstração
pública e modo real privado. Registro explícito: a política é **técnica** e deve
passar por revisão jurídica antes de uso comercial com dados pessoais de
clientes.

## 19. Critérios de sucesso

O software está pronto (V1) quando:

1. Todos os requisitos OBRIGATÓRIO V1 aprovados estiverem CONCLUÍDOS conforme o
   DoD (`09`), com evidências na matriz (`05`).
2. A jornada demonstrável de ponta a ponta funcionar no Live sem intervenção:
   analisar → validar → baixar evidências → importar `registros_validos.csv` →
   relatório de envio.
3. Nenhum card visível no Live falhar ou responder 501 — os cards de navegador
   (`extract_web_js`, `rpa_cadastro`) não são publicados como executáveis na V1
   (DP-02) e aparecem como demonstração em vídeo/GIF, com a implementação real
   preservada no Core e no CLI.
4. Suítes verdes: núcleo (pytest, cobertura ≥ 85 %), Live backend (pytest),
   frontend (vitest + typecheck + build + audit sem vulnerabilidades).

**Métricas de sucesso:** nº de requisitos V1 concluídos ÷ aprovados (única
métrica de progresso); tempo da jornada de demonstração ≤ 3 min; zero segredos em
logs/artefatos (verificação por teste); zero regressões conhecidas no release.

## 20. Critérios de homologação

Roteiro manual guiado (a registrar como evidência): executar cada card ativo do
Live com exemplo e com upload próprio; validar downloads e conteúdo dos
artefatos; repetir o Cadastro automático duas vezes seguidas (reset do mock);
provocar erros (extensão proibida, arquivo > 10 MB, YAML de schema inválido,
excesso de requisições) e conferir mensagens; no modo real, executar os 13
comandos com `--help` e um caso mínimo com `--dry-run`.

## 21. Implantação

Modo real: `pip install -e .` (ou wheel) + `playwright install chromium` quando
usar navegador + `.env` a partir do exemplo (`.env.example` hoje está vazio —
lacuna registrada em RF-CORE-004). Live: `uvicorn` do backend + build estático do
frontend; hospedagem-alvo gratuita a definir (DP-03). Publicação de documentação:
MkDocs → GitHub Pages (ritual de release já definido pelo projeto, fora desta
etapa).

## 22. Treinamento

Autotreinamento por documentação: `docs/` (MkDocs) + `--help` de todos os
comandos + jornada guiada do Live como tutorial vivo. Sem treinamento presencial
previsto (produto de operação individual).

## 23. Suporte

Nível 1 — dúvidas de uso: documentação publicada e issues no GitHub.
Nível 2 — manutenção/correções/melhorias: o próprio mantenedor, priorizando pela
matriz (`05`) e roadmap (`06`). Sem SLA formal nesta fase; tempo-alvo de primeira
resposta em issue: DECISÃO PENDENTE DP-03.

## 24. Riscos

Consolidados em `08-riscos-e-decisoes.md`. Destaques: (R-01/R-12) escopo V1
ampliado vs. capacidade de execução solo; (R-02) 6 cards "em breve" diluírem a
credibilidade da vitrine; (R-04) ausência de `.github/` no zip impede comprovar
CI; (R-06) dados pessoais reais enviados ao Live por visitantes; (R-13)
fidelidade limitada do openpyxl na preservação de apresentação (PLA-009). O
antigo R-03 (divergência de testes do frontend) foi **encerrado**: snapshot
desatualizado; baseline 52 informado pelo responsável, reconfirmação na A1.

## 25. Decisões pendentes

**Nenhuma decisão pendente bloqueia o início da Fase A1.** Aprovadas em
10/08/2026: DP-01 (a–d), DP-02, DP-03, DP-05, DP-08. Aprovadas em 05/08/2026:
DP-04, DP-06, DP-07. Registro completo em `08` §4.

Itens que voltarão a exigir decisão (acompanhamento em `08` §5): fixação dos
números de RNF após a escolha da hospedagem e medições reproduzíveis (DP-03);
formato definitivo dos conectores na Fase D, após ao menos dois sistemas reais
(DP-08); revisão jurídica da política de retenção antes de uso comercial com
dados pessoais de clientes (DP-05); e dois pontos técnicos levantados nesta
revisão sobre a aplicação da política de retenção no Live.

## 26. Roadmap

`06-roadmap-e-dependencias.md` (rev. 3): Fase A (**A1 reauditoria — concluída em
10/08/2026** · gates obrigatórios **A1.1** baseline documental, **A1.2**
reprodutibilidade e higiene do repositório, **A1.3** correção da dependência
vulnerável e **A1.4** consolidação da CI · A2 GOV-003 · A3 cards baratos,
recomendado · A4 ajuste da vitrine conforme DP-02) →
Fase B (B1–B6 fluxo completo de planilhas · **B7 RF-INT-005, obrigatório** · B8
RF-INT-006, recomendado) → Fase C (C1 homologação com e2e e INT-005 · C2 release
V1) → Fase D (pós-V1: sugestões, comunicação, backups, conectores, gatilhos).

## 27. Controle de progresso

`00-controle-mestre.md`, seções 3–5. Nenhum percentual antes de DP-01.

## 28. Matriz de rastreabilidade

`05-matriz-de-rastreabilidade.md` — caminhos reais de código, testes e evidências
desta auditoria.

## 29. Sugestões e oportunidades futuras

`07-sugestoes-e-oportunidades.md` — análise crítica do produto, ranking das dez
melhores sugestões novas, detalhamento das três primeiras e especificação do
mecanismo de sugestões automáticas dentro do produto.
