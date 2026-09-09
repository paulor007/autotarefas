# 06 — Roadmap e Dependências (revisão 3 — baseline aprovado em 10/08/2026)

Escopo obrigatório aprovado: **41 requisitos** (DP-01). A V1 fecha quando o fluxo
de planilhas entrega o resultado operacional completo (01 §9.1) **e** a planilha
tratada chega ao sistema de destino com mapeamento configurável (RF-INT-005).
Cada subetapa termina com testes, evidência na matriz e um commit local.

Regras vigentes: **nenhum requisito recomendado atrasa um obrigatório**; nenhuma
fase nova antes de fechar a anterior no controle mestre; requisito só vira
CONCLUÍDO com código, testes, critérios de aceite cumpridos e evidência (`09`).

Visão geral:

```
FASE A — Auditoria, gates técnicos, política de dados e vitrine   (dentro da V1)
FASE B — Fluxo completo de planilhas + importação    (coração da V1)
FASE C — Homologação, e2e e release V1
FASE D — Pós-V1 (sugestões, comunicação, backups, conectores, gatilhos)
```

---

## FASE A — Consolidação, política de dados e vitrine

**A1. Reauditoria do repositório atual — CONCLUÍDA em 10/08/2026**
*(RNF-CI-01; DP-07; baseline técnico em `00` §4.1)*

Encerrada como **atividade de auditoria**, por decisão do responsável: evidências
coletadas, suítes executadas, workflows locais inspecionados, estado do Git
identificado, inconsistências comprovadas e nenhuma correção aplicada em silêncio.
**Auditoria concluída ≠ achados corrigidos.**

Comprovado: commit local `f3f95de`, `main` **22 commits à frente** de
`origin/main`; suíte principal **2052 passed** com cobertura **92,39 %**; backend
Live **127 passed**; frontend **52 passed** (22 `spreadsheets.test.ts` + 16
`SpreadsheetProfileMapping.test.tsx` + 14 `SpreadsheetJourney.test.tsx`); typecheck
e build aprovados; `npm audit` com **1 alta de desenvolvimento** e `--omit=dev` em
**0**, com `package-lock.json` inalterado; `.github/workflows/ci.yml` e `docs.yml`
inspecionados (CI cobre só o núcleo em Python); `docs/requisitos` **não versionado**;
`spreadsheets.test.ts` sem rastreamento aparente; 32 fixtures geradas não
versionadas; `.vscode/settings.json` não rastreado. Evidências em `05` (ressalvas 1
a 11) e riscos R-15 a R-20 em `08`.

Os achados originaram **quatro gates obrigatórios antes da A2** — nenhum deles
altera o escopo funcional de 41 requisitos:

---

### A1.1 — Aplicação do baseline documental oficial *(OBRIGATÓRIA)*

**Objetivo:** colocar os 12 Markdown oficiais sob controle de versão em
`docs/requisitos/`, com o `README.md` preservado como porta de entrada, e fechar o
risco R-20.

**Situação comprovada:** `git status --short docs/requisitos` e
`git ls-files docs/requisitos` não retornaram nada — a pasta **não está
versionada** no Git local. Não se afirma ausência física nem `.gitignore`: isso é
verificação desta subetapa.

**Arquivos criados (12, conteúdo exatamente o do pacote entregue — nenhum texto
novo é escrito aqui):** `README.md`, `00-controle-mestre.md`,
`01-documento-de-requisitos-autotarefas.md`, `02-catalogo-de-automacoes.md`,
`03-requisitos-funcionais.md`, `04-requisitos-nao-funcionais.md`,
`05-matriz-de-rastreabilidade.md`, `06-roadmap-e-dependencias.md`,
`07-sugestoes-e-oportunidades.md`, `08-riscos-e-decisoes.md`,
`09-criterios-de-aceite-e-dod.md`, `10-glossario.md`.
**Arquivos alterados:** nenhum. **Motivo por arquivo:** cada um tem
responsabilidade documental própria (ver `README.md` §2); não podem ser fundidos
nem substituídos por resumo.

**Riscos:** (a) a pasta estar coberta por regra de `.gitignore` e o `git add`
falhar em silêncio — mitigado por `git check-ignore -v` antes do add; (b) misturar
documentação com código, fixtures, dependências ou CI no mesmo commit — mitigado
por `git add` restrito ao caminho e conferência do `--cached --stat`; (c)
**sobrescrever uma versão local divergente** — mitigado por extrair o pacote
primeiro numa pasta temporária exclusiva, nunca sobre o repositório, e por
interromper a aplicação se `docs/requisitos` já existir, pedindo comparação antes
de qualquer cópia; (d) pacote incompleto ou trocado — mitigado por conferir que
contém exatamente 12 arquivos Markdown antes de copiar.

**Pacote de origem:** `autotarefas-docs-requisitos-rev3-a1-concluida-r1.zip`
(único baseline; contém apenas `docs/requisitos/` com 12 Markdown).

**Comandos (Windows PowerShell 5.1) — extrair em pasta temporária exclusiva, nunca
sobre o repositório; sem `-Force` sobre `docs/requisitos`; interromper se a pasta
já existir:**
```powershell
$ErrorActionPreference = 'Stop'
$repo    = (Get-Location).Path
$pacote  = Join-Path $repo 'autotarefas-docs-requisitos-rev3-a1-concluida-r1.zip'
$destino = Join-Path $repo 'docs\requisitos'
$temp    = Join-Path ([System.IO.Path]::GetTempPath()) ("at-docs-" + [Guid]::NewGuid().ToString('N'))

Push-Location $repo
try {
    git status --short
    if (-not (Test-Path $pacote)) { throw "Pacote nao encontrado: $pacote" }

    # 1) extracao em pasta temporaria exclusiva (jamais sobre o repositorio)
    New-Item -ItemType Directory -Path $temp | Out-Null
    Expand-Archive -LiteralPath $pacote -DestinationPath $temp
    $origem = Join-Path $temp 'docs\requisitos'
    if (-not (Test-Path $origem)) { throw "Pacote sem docs/requisitos" }

    # 2) o pacote precisa ter exatamente 12 Markdown
    $md = Get-ChildItem -LiteralPath $origem -Filter *.md -File
    if ($md.Count -ne 12) { throw "Esperados 12 arquivos .md, encontrados $($md.Count)" }
    $md | Select-Object Name, Length

    # 3) se o destino existir, PARAR e comparar - nada e sobrescrito
    if (Test-Path $destino) {
        Write-Warning "docs/requisitos JA EXISTE. Aplicacao interrompida - compare antes de decidir:"
        Write-Host "  Compare-Object (Get-ChildItem '$origem' -Filter *.md).Name (Get-ChildItem '$destino' -Filter *.md).Name"
        Write-Host "  Get-ChildItem '$origem' -Filter *.md | ForEach-Object { fc.exe /b `$_.FullName (Join-Path '$destino' `$_.Name) }"
        Write-Host "  Pasta temporaria preservada em: $temp"
        return
    }

    # 4) copia (destino inexistente, portanto nao ha sobrescrita)
    New-Item -ItemType Directory -Path $destino | Out-Null
    Copy-Item -LiteralPath $md.FullName -Destination $destino
    (Get-ChildItem -LiteralPath $destino -Filter *.md -File).Count   # esperado: 12

    # 5) regras de ignore ANTES do add
    git check-ignore -v -- docs/requisitos            # esperado: nenhuma saida
    git check-ignore -v -- docs/requisitos/README.md  # esperado: nenhuma saida

    # 6) adicionar somente a pasta documental e conferir o staged diff
    git add -- docs/requisitos
    git diff --cached --stat                          # somente docs/requisitos
    git diff --cached --name-only | Where-Object { $_ -notlike 'docs/requisitos/*' }
    # a linha acima nao deve imprimir nada
}
finally {
    Pop-Location
    if ((Test-Path $temp) -and (-not (Test-Path $destino))) { Remove-Item -LiteralPath $temp -Recurse -Force }
}
```
Se o passo 3 interromper, a pasta temporária é preservada de propósito para a
comparação; remova-a manualmente depois de decidir.

**Testes/validações:** contagem de 12 arquivos; nenhuma referência interna
quebrada; contagens **51**, **30/4/17**, **41 obrigatórios** e progresso **30/41**
presentes; nenhum arquivo fora de `docs/requisitos/` no diff.

**Critérios de aceite:** os 12 arquivos rastreados por `git ls-files docs/requisitos`;
`git check-ignore` sem regra para a pasta; diff exclusivamente documental; README
como porta de entrada.

**Evidências para a matriz:** saída de `git ls-files docs/requisitos` (12 linhas),
saída de `git check-ignore -v -- docs/requisitos` (vazia), saída de
`git diff --cached --name-only` (todas as linhas em `docs/requisitos/`) e hash do
commit documental.

**Cuidados de Git:** `git add` por caminho, nunca `git add -A`; nada de `.vscode`,
fixtures, lockfile ou workflows no mesmo commit; sem push.

**Commit local sugerido:**
`docs(requisitos): versiona baseline documental aprovado (rev3 + evidencias da A1)`

---

### A1.2 — Reprodutibilidade dos testes e higiene do repositório *(OBRIGATÓRIA)*

**Objetivo:** garantir que uma clonagem limpa reproduza o baseline (2052 + 127 +
52) e resolver R-18, R-19 e a situação do `.vscode`, sem decidir nada por
automatismo.

**Situação comprovada:** `spreadsheets.test.ts` (22 testes) executa mas não
aparece em `git ls-files` nem entre os não rastreados;
`tests/fixtures/planilhas/build_fixtures.py` versionado e **32** CSV/XLSX gerados
não versionados; `.vscode/settings.json` (127 bytes) não rastreado.

**Arquivos criados:** nenhum nesta subetapa (eventuais ajustes de `.gitignore` ou
`conftest.py` só depois da análise e com autorização expressa).
**Arquivos alterados:** nenhum antes da decisão. Candidatos, **cada um com
autorização própria**: `.gitignore` (se a regra estiver capturando o teste),
`tests/conftest.py` ou o gerador (se a decisão for gerar fixtures na suíte).
**Ação e motivo:** primeiro diagnosticar; a decisão sobre as 32 fixtures obedece
aos critérios: determinismo do gerador, execução automática pelos testes, sucesso
em clonagem limpa, tamanho/conteúdo e confirmação de que são **apenas dados
sintéticos, sem informação pessoal**.

**Riscos:** (a) versionar planilhas grandes ou com dado real — mitigado pela
inspeção de conteúdo e tamanho antes de decidir; (b) alterar `.gitignore` e passar
a rastrear lixo — mitigado por regra mínima e específica; (c) perder os 22 testes
num `git clean` — é exatamente o risco que a subetapa fecha.

**Comandos (Windows PowerShell 5.1) — diagnóstico, sem alterar nada:**
```powershell
$ErrorActionPreference = 'Continue'   # aqui queremos ver as saidas, inclusive as de erro
git check-ignore -v -- apps/web/src/lib/spreadsheets.test.ts
git ls-files --error-unmatch -- apps/web/src/lib/spreadsheets.test.ts
git check-ignore -v -- tests/fixtures/planilhas/01_csv_limpo.csv
Get-Content -LiteralPath '.vscode\settings.json'
Get-ChildItem -LiteralPath 'tests\fixtures\planilhas' -File |
    Measure-Object -Property Length -Sum
Select-String -Path 'tests\conftest.py' -Pattern 'build_fixtures|fixtures/planilhas'
```

**Clonagem limpa em pasta temporária exclusiva** (nome único gerado por GUID, sem
caminho fixo, sem encadeamento por operador de shell, localização restaurada por
`Push-Location`/`Pop-Location` dentro de `try/finally` — compatível com Windows
PowerShell 5.1):
```powershell
$ErrorActionPreference = 'Stop'
$repo = (Get-Location).Path
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("at-clone-" + [Guid]::NewGuid().ToString('N'))

try {
    git clone --no-hardlinks -- $repo $temp
    Push-Location $temp
    try {
        python -m venv .venv
        & '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
        & '.\.venv\Scripts\python.exe' -m pip install -e ".[dev,demo]"
        & '.\.venv\Scripts\python.exe' -m pytest tests -q
        # esperado: 2052 passed. Se falhar por fixture ausente, registrar quais.
    }
    finally { Pop-Location }
}
finally {
    if (Test-Path $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
}
```
A clonagem usa `--no-hardlinks` sobre o próprio repositório e leva apenas o que o
Git rastreia — é exatamente esse o teste de reprodutibilidade. O ambiente virtual
dentro da pasta temporária evita mexer no Python do projeto.

**Testes/validações:** clonagem limpa deve chegar a **2052 passed**; se falhar,
registrar exatamente quais testes dependem das fixtures ausentes.

**Critérios de aceite:** hipótese do `.gitignore` confirmada ou refutada com saída
de comando; os 22 testes de `spreadsheets.test.ts` rastreados (ou justificativa
registrada); decisão sobre as 32 fixtures registrada em `08` §4 com o critério que
a sustentou; `.vscode/settings.json` versionado deliberadamente **ou** ignorado,
conforme o conteúdo; clonagem limpa reproduzindo a suíte.

**Evidências para a matriz:** saídas de `git check-ignore -v` e
`git ls-files --error-unmatch`; soma de tamanho das fixtures; resultado da suíte na
clonagem limpa; conteúdo do `settings.json`.

**Cuidados de Git:** nada de `git clean` no repositório real; clonagem sempre em
pasta temporária; um commit por assunto (rastreamento de teste ≠ fixtures ≠ editor).

**Commits locais sugeridos:** `fix(git): garante rastreamento dos testes do frontend` ·
`test(fixtures): define estrategia de fixtures para clonagem limpa` ·
`chore(vscode): versiona configuracao impessoal do projeto` *(apenas os que a
análise justificar)*

---

### A1.3 — Correção mínima da dependência vulnerável *(OBRIGATÓRIA)*

**Objetivo:** eliminar a vulnerabilidade alta de desenvolvimento (`nanoid < 3.3.17`)
com a **menor** atualização compatível, sem migração de Tailwind e sem atualização
ampla — fecha R-15.

**Situação comprovada:** `npm audit` = 1 alta (GHSA-2v37-7h3g-55p8) via
`vite → postcss`; `npm audit --omit=dev` = 0; `package-lock.json` inalterado;
nenhuma correção aplicada.

**Arquivos criados:** nenhum. **Arquivos alterados:**
`apps/web/package-lock.json` (obrigatório) e
`apps/web/package.json` (**somente** se a menor correção exigir mexer em
faixa declarada). **Motivo:** atualizar a versão resolvida de `nanoid`/`postcss`
mantendo o restante intacto.

**Riscos:** (a) `npm audit fix --force` subir major e quebrar o build — **proibido**;
(b) atualização ampla arrastar Tailwind para v4, contra a convenção do projeto —
mitigado por inspeção do diff antes de aceitar; (c) quebrar os 52 testes — mitigado
pela bateria completa após a correção.

**Comandos (PowerShell):**
```powershell
cd apps\frontend
npm explain nanoid
npm audit fix --dry-run            # avaliar o diff esperado; NUNCA --force
npm audit fix                      # só depois de aprovar o dry-run
git diff -- package.json package-lock.json
npm ci; npm audit; npm audit --omit=dev; npm run typecheck; npm test; npm run build
```

**Testes/validações:** `npm audit` sem vulnerabilidade alta; `--omit=dev` em 0;
**52 testes** verdes de novo (22 + 16 + 14); typecheck e build aprovados.

**Critérios de aceite:** vulnerabilidade resolvida; Tailwind permanece na
configuração atual (3.4.x, modelo tradicional); diff restrito a
`package.json`/`package-lock.json`; suíte do frontend íntegra.

**Evidências para a matriz:** `npm explain nanoid` (antes), saídas de `npm audit` e
`npm audit --omit=dev` (depois), diff resumido do lockfile e saída dos 52 testes.

**Cuidados de Git:** commit exclusivo de dependência, sem misturar documentação,
código ou CI.

**Commit local sugerido:**
`fix(deps): atualiza nanoid para corrigir GHSA-2v37-7h3g-55p8 (cadeia de dev)`

---

### A1.4 — Consolidação da integração contínua *(OBRIGATÓRIA)*

**Objetivo:** fazer a CI rápida cobrir o que o projeto realmente valida — núcleo,
backend Live e frontend — mantendo o workflow de documentação separado e o
navegador real em workflow manual próprio. Fecha R-16.

**Situação comprovada:** `ci.yml` roda Python 3.12/3.13 com ruff, ruff format,
`mypy src/`, bandit, `pytest` do núcleo e gate de cobertura. Faltam **sete
verificações regulares na CI rápida**:

| # | Verificação ausente |
|---|---|
| 1 | `python -m pytest apps/api/tests` (127 testes do backend Live) |
| 2 | `npm ci` (instalação reprodutível do frontend) |
| 3 | `npm audit` |
| 4 | `npm audit --omit=dev` |
| 5 | `npm run typecheck` |
| 6 | `npm test` (52 testes) |
| 7 | `npm run build` |

**Oitava lacuna, de natureza distinta:** o **Playwright com navegador real** não é
uma verificação regular da CI rápida — é lacuna separada, tratada por **workflow
manual específico** (`workflow_dispatch`) e **obrigatória novamente na C1**. Ela
não entra no fluxo de cada push por custo e tempo, e sua ausência ali é
deliberada, não esquecimento.

`docs.yml` cuida da documentação e permanece separado. Os acentos corrompidos na
captura por PowerShell **não** indicam arquivo corrompido — confirmar lendo os
originais.

**Arquivos criados:** possivelmente `.github/workflows/frontend.yml` (job
independente) e/ou `.github/workflows/e2e.yml` (manual, `workflow_dispatch`).
**Arquivos alterados:** `.github/workflows/ci.yml` (passo do backend Live e,
condicionalmente, `mypy src/ tests/`); eventualmente `pyproject.toml` **só** se a
inclusão da suíte do Live exigir ajuste de `testpaths` — decisão a registrar.
**Motivo:** a suíte do Live está fora por `testpaths = ["tests"]`; o frontend não
tem job nenhum.

**Riscos:** (a) `mypy src/ tests/` falhar na CI e travar o pipeline — por isso
**verificar localmente antes** de mudar o comando; (b) mexer em `testpaths` e
alterar o comportamento local do `pytest` — preferir passo explícito
`pytest apps/api/tests`; (c) job de frontend quebrar por falta de fixtures
ou de versão de Node fixada — fixar Node LTS explícito e depender de A1.2; (d)
duplicar instalação de dependências e encarecer o tempo — usar cache e jobs
separados.

**Comandos (Windows PowerShell 5.1) — verificação prévia, antes de tocar em
workflow:**
```powershell
$ErrorActionPreference = 'Continue'
mypy src/ tests/                                  # autoriza (ou nao) trocar o comando da CI
python -m pytest apps/api/tests -q
node --version                                    # registrar a LTS usada no job

Push-Location 'apps\frontend'
try {
    npm ci
    npm audit
    npm audit --omit=dev
    npm run typecheck
    npm test
    npm run build
}
finally { Pop-Location }
```

**Testes/validações:** CI rápida verde com os três blocos (núcleo com matriz
3.12/3.13, backend Live, frontend com auditoria + typecheck + 52 testes + build),
cobrindo as sete verificações da tabela acima; workflow de navegador real
disparável manualmente (oitava lacuna) e obrigatório na C1; clonagem limpa com todas
as fixtures necessárias (depende de A1.2).

**Critérios de aceite:** as **sete verificações regulares** passam a rodar na CI
rápida; o **Playwright real** existe como workflow manual próprio, fora do fluxo
rápido e obrigatório na C1; `docs.yml` mantido separado; "CI rápida verde" passa a
significar núcleo + backend Live + frontend verdes.

**Evidências para a matriz:** link da execução verde da CI com os três jobs, versão
de Node fixada e resultado do `mypy src/ tests/` local que autorizou (ou não) a
mudança do comando.

**Cuidados de Git:** commit exclusivo de CI; não misturar com dependências,
fixtures ou documentação; sem push nesta fase.

**Commit local sugerido:**
`ci: adiciona backend Live e job de frontend ao pipeline`

---

**A2. RF-GOV-003 — política de dados aprovada + higiene de configuração**
*(GOV-003 obrigatório; lacuna de CORE-004; DP-05 aprovada)*
**PENDENTE — só pode começar depois de A1.1, A1.2, A1.3 e A1.4 concluídas.**
Implementar a política da DP-05 com separação por ambiente, já com as
qualificações de **PA-01 e PA-02 (resolvidas em 10/08/2026)**:

- **Live:** uploads/artefatos com TTL de 15 min (já conforme) e logs sem dados
  sensíveis 30 d. **Audit do Live = vida do workspace, máximo 15 min** — não
  implementar retenção de 30 dias nem audit agregado do servidor nesta fase
  (nenhum requisito novo criado). **Screenshots: não aplicável** ao Live da V1,
  porque o RPA não roda publicamente (DP-02) — nada a implementar aqui; o prazo
  preventivo de 7 dias só entra se a execução pública com navegador for habilitada
  na Fase D.
- **Modo real:** uploads/artefatos configuráveis pelo operador, logs 30 d por
  padrão (configurável), screenshots 30 d por padrão (configurável), audit com
  retenção configurável e exclusão manual confirmada.

Tornar a retenção de logs configurável (`core/logger.py`), criar a rotina de
expurgo (logs, screenshots e audit do modo real), preencher `.env.example` e
publicar no Live o texto de transparência (finalidade, retenção efetiva,
existência de arquivos de exemplo, recomendação sobre dados pessoais, diferença
demo × modo real).
Arquivos prováveis: novo comando de manutenção, `core/logger.py`,
`core/settings.py`, `.env.example`, textos do front do Live, testes em
`tests/tasks/` e `tests/core/`.
Critério: expurgo remove exatamente o previsto e registra no audit; `.env.example`
cobre 100 % das settings; texto de transparência visível antes do upload e
coerente com a retenção real (15 min no Live, sem promessa de 30 dias).
Commit: `feat(gov): politica de retencao por ambiente, expurgo e transparencia do Live`

**A3. LIVE-006a — ativar os 4 cards baratos** *(RECOMENDADO V1 — não bloqueia)*
`sync_api`, `send_email`, `report` e `dashboard`: 4 ramos em
`recipes.py::build_argv`, régua em `engine.py::ACTIVE_AUTOMATIONS`, exemplo para
e-mail em `samples.py`, testes em `apps/api/tests/test_engine.py`.
Riscos: SMTP mock no lifespan (porta 8025 já prevista em `config.py`);
report/dashboard sobre audit recém-criado → semear o audit do workspace (risco
R-10).
Commit: `feat(live): ativa sync_api, send_email, report e dashboard na regua`

**A4. Ajuste da vitrine conforme DP-02** *(obrigatório antes do release)*
Retirar da vitrine pública a promessa de execução direta de `extract_web_js` e
`rpa_cadastro`, publicando no lugar a demonstração em vídeo/GIF com o comando real
equivalente. **Nada de código ou teste é removido**: RF-WEB-002 e RF-WEB-003
continuam obrigatórios da V1 no modo real. Arquivos prováveis: `catalog.py`
(apresentação), front (bloco de demonstração), assets do vídeo/GIF.
Critério: nenhum card visível responde 501; a página deixa claro que a automação
existe e roda no modo real.
Commit: `feat(live): demonstracao em video dos cards de navegador (DP-02)`

## FASE B — Fluxo completo de planilhas + importação

**B1. RF-REC-001 — comparador por chave** — núcleo puro (pacote
`src/autotarefas/reconcile/` ou `tasks/compare.py`), CLI `comparar`, artefatos via
PLA-007; fixtures com casos plantados (novo/removido/alterado/duplicado, acentos,
zeros à esquerda). Depende: nada novo.
Critério: classificação 100 % correta nas fixtures; fontes intocadas.
Commit: `feat(rec): comparacao de planilhas por chave com relatorio de divergencias`

**B2. RF-REC-002 — tolerâncias e base conciliada** — regras de decisão, fontes
prioritárias, `base_conciliada.xlsx` + `conflitos_para_revisao.xlsx` + relatório de
decisões. Depende: B1. Critério: tolerância declarada não vira divergência;
conflito fora de regra sempre vai para revisão.
Commit: `feat(rec): reconciliacao com tolerancias e relatorio de decisoes`

**B3. RF-REC-003 — transferência e enriquecimento** — lookup autorizado entre
bases em arquivo novo, `_origem_<campo>`, consolidação com coluna de origem.
Depende: B1. Critério: campo não autorizado jamais alterado.
Commit: `feat(rec): transferencia autorizada entre planilhas`

**B4. RF-PLA-009 — preservação da apresentação** — cópia de
estilos/larguras/painéis/formatos do original na `planilha_tratada.xlsx` quando
tecnicamente possível (openpyxl), relatório do não-preservável e fallback para a
formatação profissional (PLA-007). Risco R-13: declarar limites.
Commit: `feat(pla): preservacao da apresentacao original na planilha tratada`

**B5. RF-PLA-010 — correções por regras confirmadas** — catálogo inicial (de/para
de valores, lookup fixo ou vindo da base conciliada, padronização de categoria),
sempre por configuração explícita; relatório separando automático-seguro ×
normalização × regra-confirmada × revisão. Depende: B2/B3, PLA-006.
Commit: `feat(pla): correcoes autorizadas por regras confirmadas`

**B6. RF-CORE-006 (recorte aprovado) + RF-REC-004 — configuração de fluxo
reutilizável** — YAML da operação completa validado por pydantic;
`autotarefas run fluxo.yaml`; precedência CLI > configuração > padrão; recusa de
segredo embutido; REC-004 como primeiro consumidor. Depende: B1–B5.
Critério: a conferência mensal roda por um comando, sem redigitar parâmetros.
Commit: `feat(core): configuracao de fluxo reutilizavel (run) + config de reconciliacao`

**B7. RF-INT-005 — mapeamento configurável na importação** *(OBRIGATÓRIO V1 —
DP-01(c); bloqueia C1 e o release)*
De/para coluna → campo por CLI (`--map "Coluna=campo"`) ou arquivo simples;
validação dos campos obrigatórios do destino; detecção de mapeamentos repetidos ou
incompatíveis; prévia do payload; dry-run sem gravação externa; preservação do
arquivo original; registro do mapeamento aplicado no relatório e no audit;
relatório de aceitos, rejeitados e falhos; testes com três estruturas (contatos,
produtos, vendas); nenhuma credencial na configuração; nenhuma decisão incerta
aplicada em silêncio. **Não** virar framework universal de conectores.
Depende: INT-002 (pronto); conversa com B6 para a precedência de configuração.
Arquivos prováveis: `src/autotarefas/tasks/send_api.py` (+ módulo de mapeamento),
grupo de comandos `src/autotarefas/cli/commands/send/`, `tests/tasks/`, `tests/cli/`
e fixtures novas.
Commit: `feat(int): mapeamento configuravel de colunas na importacao via API`

**B8. RF-INT-006 — checkpoint e retomada** *(RECOMENDADO — etapa posterior a B7)*
`--continuar` pulando confirmados; complementa o reenvio de falhos. Só entra se
houver folga depois de B7 e nunca atrasa um obrigatório. Gatilho para virar
obrigatório: lotes reais acima de ~10 mil linhas ou destino não idempotente.
Commit: `feat(int): checkpoint e retomada de envios longos`

## FASE C — Homologação, e2e e release V1

**C1. Homologação guiada + e2e** — depende de **A1, A2, A4 e B1–B7 concluídos**.
Instalar Chromium e rodar `playwright install chromium` seguido de `python -m pytest tests/e2e` verde (**promove WEB-002**; para **WEB-003**, o teste automatizado com navegador real é **obrigatório** e a homologação manual é apenas complementar, não o substitui — `05` ressalva 1),
roteiro manual de 01 §20 estendido ao fluxo completo (analisar → comparar →
conciliar → corrigir → planilha tratada → **importar com mapeamento** →
evidências), jornada cronometrada ≤ 3 min, evidências registradas na matriz.
Commit: `docs(requisitos): evidencias de homologacao V1 (e2e e importacao mapeada)`

**C1.1 — O instalador nao e verificavel pela CI, e isso e estrutural.**
Os seis testes de `tests/e2e/test_instalador_exe_e2e.py` dependem de
`dist-agente/AutoTarefas-Agente.exe`, que e **artefato de build e nao esta
versionado** — num checkout limpo ele nunca existe, e no Linux da CI ele **nao
pode** existir, porque e um executavel do Windows gerado pelo PyInstaller. A
consequencia precisa ficar escrita: **CI verde nao significa instalador
verificado.** Ele so e exercitado numa maquina Windows onde alguem rodou
`pip install -e ".[instalador]"` e `python tools/construir_agente.py` antes da
suite. Fora dai os seis pulam, com o motivo na propria mensagem do skip.

Por isso a verificacao do instalador entra no **roteiro manual** desta fase, e
nao no portao automatico: gerar o `.exe`, rodar
`pytest tests/e2e/test_instalador_exe_e2e.py` na maquina que o gerou, e
registrar a saida como evidencia. Publicar um instalador que a esteira nunca
executou seria confiar num artefato que ninguem viu rodar.

Registrado em 09/09/2026, depois de a guarda do executavel subir da fixture
`live` para o `pytestmark` do modulo. Ate entao ela alcancava so os testes que
pediam a fixture, e o unico que chamava o `.exe` direto escapava — quebrando a
CI com `FileNotFoundError` em vez de pular.

**C2. Ritual de release V1** — fora do escopo desta etapa documental:
README/CHANGELOG completos, bump em `__init__.py`, tag, push com tags (deploy do
Pages). Só após A1, A2, A4, B1–B7 e C1.

## FASE D — Pós-V1

**D1.** CORE-007 (sugestões automáticas: 5 regras + 7 campos de transparência) ·
COM-003 (idempotência/limites de comunicação) · sugestões nº 2 (divisor/
distribuidor), nº 11 (modelo de preenchimento) e nº 12 (anonimizador) do doc 07.
**D2.** ARQ-002 (manifesto/verificação/restauração de backup) · ARQ-004 (undo do
organize) · ARQ-005 (retenção de backups).
**D3.** INT-004 — conectores declarativos: formato definido **somente após
experiência com pelo menos dois sistemas reais distintos** (DP-01(b)/DP-08);
generalização do mapeamento de B7 sobre conectores. As tasks específicas continuam
funcionando independentemente.
**D4.** CORE-008 (agendamento fase 1 + watch) · WEB-004 (retomada/resiliência de
RPA) · **LIVE-006b** — reavaliar execução pública dos cards de navegador com
Chromium, após a definição da hospedagem (DP-02) · encadeamento genérico de
CORE-006.

### Pedidos de mudança registrados (V2)

| ID | Pedido | Estado |
|---|---|---|
| **CR-001** | **Formulário de feedback embutido no Live** — quem experimenta consegue dizer o que achou sem sair da página | registrado, não planejado |

Duas observações que a estimativa precisa carregar. A **versão sem código já
existe**: um link para as *GitHub Issues* do repositório entrega o essencial —
o visitante fala, a fala fica pública e rastreável, e nada disso custa
manutenção. O **formulário próprio** é outra coisa: exige endpoint que aceite
POST anônimo, anti-spam (um campo aberto na internet vira alvo em dias),
moderação de quem lê e responde, e — o ponto que costuma passar em branco —
**uma decisão nova de retenção**, porque texto livre é o único lugar do Live
onde alguém pode digitar dado pessoal por conta própria. A DP-05 não cobre esse
caso: ela trata de arquivo enviado e log de execução, não de campo de texto. O
CR-001 só entra em planejamento junto com essa decisão.

### Card 02 — Backup automático verificável

Fora da V1 por **DP-09** (07/09/2026): o card não tem nenhum ID RF, e sem ID não
há critério pelo qual declará-lo concluído. Código e vitrine permanecem. Criar
os IDs RF do Card 02, com critérios de aceite próprios, é trabalho de V2 — e é
o que destravaria as três pendências dele (elevação para o VSS, balde S3 real,
SMTP no cofre), que dependem de hardware ou credencial, não de código.

## Bloqueadores do release V1

Gates técnicos e documentais: **A1.1, A1.2, A1.3 e A1.4** (obrigatórios antes da
A2; não alteram o escopo funcional).
Trabalho de requisito obrigatório: **REC-001, REC-002, REC-003, REC-004, PLA-009,
PLA-010, CORE-006 (recorte), INT-005, GOV-003** · verificação com **navegador
real** promovendo WEB-002 e **teste automatizado com navegador real para WEB-003**
(obrigatório; homologação manual apenas complementar) · **A4**
(ajuste da vitrine, DP-02) · **C1** (homologação).
Não bloqueiam: LIVE-006a (A3) e INT-006 (B8).

## Mapa de dependências (resumo)

```
A1 (concluída) ─ A1.1 ─ A1.2 ─ A1.3 ─ A1.4 ─┬─ A2 ──────────────────┐
                                            ├─ A3 (recomendado)     │
                                            ├─ A4 (p/ release) ─────┤
                                            └─ B1 ─┬─ B2 ─┬─ B5 ─ B6 ─ B7 ─┼─ C1 ─ C2
                                                   │      └─ B3 ──┘        │
                                                   └─ B4 ─────────────────┘
B8 (recomendado) — posterior a B7, se houver folga
C2 ─── D1 .. D4
```

Ordem obrigatória vigente: **A1 (concluída) → A1.1 → A1.2 → A1.3 → A1.4 → A2**.
