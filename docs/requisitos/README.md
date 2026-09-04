# Documentação de Requisitos do AutoTarefas

**Revisão 3 — baseline documental aprovado em 10/08/2026.**
Versão do software: `1.4.0` (inalterada — esta revisão é documental).
Escopo obrigatório da V1: **41 requisitos**, dos quais **40 CONCLUÍDOS**
(progresso documental **40/41**). Total catalogado: **51** requisitos funcionais.

> **Atualização de 14/08/2026 — Fase B concluída.** Entraram como CONCLUÍDOS:
> RF-REC-001 (`comparar`), RF-REC-002 (`conciliar`), RF-REC-003 (`transferir`),
> RF-PLA-009 (planilha tratada com a apresentação preservada), RF-PLA-010
> (`corrigir` por regras confirmadas), RF-INT-005 (mapeamento na importação) e
> RF-CORE-006 (recorte) + RF-REC-004 (`run fluxo.yaml`). Os três obrigatórios
> restantes dependiam de execução com **navegador real** (RF-WEB-002 e
> RF-WEB-003) e do fechamento do RF-GOV-003; as evidências por requisito estão
> no `05`.

> **Atualização de 03/09/2026 — RF-GOV-003 CONCLUÍDO (39/41).** As duas lacunas
> eram documentais: a política de retenção e privacidade foi escrita no
> `SECURITY.md` e o Live passou a enunciá-la antes do upload. Restam **dois**
> obrigatórios, ambos dependentes de execução com navegador real: RF-WEB-002 e
> RF-WEB-003.

> **Atualização de 04/09/2026 — RF-WEB-002 CONCLUÍDO (40/41).** Com o Chromium
> instalado, o e2e de `extract web --js` passa inteiro (2 de 2, nenhum skip) e
> prova por contraste que a mesma página rende 0 itens sem `--js` e 3 com
> `--js`. Resta **um** obrigatório: RF-WEB-003 (RPA de cadastro).

---

## 1. Para que serve esta documentação

Esta pasta é a **fonte oficial de requisitos e de acompanhamento** do AutoTarefas.
Depois da aprovação do baseline, vale a regra: *nenhuma funcionalidade é
considerada existente, concluída ou planejada se não estiver registrada aqui.*

Ela existe para três coisas:

1. **decidir** — o que entra na V1, o que fica para depois e por quê;
2. **implementar** — cada requisito com fluxos, critérios de aceite e dependências;
3. **provar** — status apenas com evidência reproduzível (comando, resultado,
   caminho), nunca com percentual ou impressão.

## 2. Responsabilidade de cada arquivo

| Arquivo | Responsabilidade | Não use para |
|---|---|---|
| `README.md` | Porta de entrada: finalidade, ordem de leitura, ritual de atualização | Consultar status ou escopo (isso é do 00 e do 01) |
| `00-controle-mestre.md` | **Controla o status.** Legenda oficial, escopo obrigatório aprovado (§3.1), fórmula de progresso, checklist mestre dos 51 requisitos, ritual de atualização | Detalhar requisito |
| `01-documento-de-requisitos-autotarefas.md` | Documento formal do produto: objetivo, justificativa, público, **escopo da V1 (§9) e resultado operacional mínimo (§9.1)**, arquitetura, RNFs em resumo, critérios de sucesso e de homologação | Rastrear evidência por requisito |
| `02-catalogo-de-automacoes.md` | O que o usuário vê e executa: cards do Live, régua ativo/em breve, comandos do CLI, mocks internos | Definir requisito |
| `03-requisitos-funcionais.md` | **Fichas completas** dos 51 requisitos (28 campos): fluxos, critérios de aceite, testes, prioridade, fase, status, lacunas | Acompanhar progresso agregado |
| `04-requisitos-nao-funcionais.md` | RNFs mensuráveis: desempenho, confiabilidade, segurança, **privacidade e retenção (DP-05)**, testes, CI, documentação | Requisito funcional |
| `05-matriz-de-rastreabilidade.md` | **Onde ficam as evidências:** requisito × status × código × teste × evidência × lacuna × próxima ação | Escrever requisito novo |
| `06-roadmap-e-dependencias.md` | Fases A–D, subetapas pequenas, dependências, bloqueadores do release e commits sugeridos | Definir critério de aceite |
| `07-sugestoes-e-oportunidades.md` | Análise crítica, ranking de sugestões (1–14) e especificação do mecanismo de sugestões automáticas | Escopo aprovado (é material de evolução) |
| `08-riscos-e-decisoes.md` | Riscos técnicos e de produto (R-01 a R-20), **registro das decisões aprovadas (§4)** e os pontos levantados e resolvidos na revisão 3 (§5) | Status de requisito |
| `09-criterios-de-aceite-e-dod.md` | **Critérios de aceite e Definition of Done** — geral, por tipo e anti-critérios | Planejamento de fases |
| `10-glossario.md` | Termos do projeto (artefato, audit trail, régua, workspace, receita...) | Decisões |

Os 11 documentos modulares **não devem ser fundidos nem excluídos**: cada um tem
uma responsabilidade distinta, e duplicar conteúdo entre eles cria divergência com
o controle mestre.

## 3. Ordem de leitura para aprovar

1. `08` §4 — o que já foi decidido, com data.
2. `00` §2, §3 e §3.1 — legenda, fórmula de progresso e o escopo obrigatório de 41.
3. `01` §5–§10 — objetivo, problemas resolvidos, público e escopo da V1.
4. `01` §9.1 — o resultado operacional mínimo que define a V1.
5. `06` — a sequência de implementação e os bloqueadores do release.
6. `08` §1, §2 e §5 — riscos e os pontos que ainda precisam de resposta.
7. `07` — o que fica de fora e por quê (evolução).

## 4. Ordem de leitura para implementar

1. `00` §5 — escolher o requisito no checklist.
2. `06` — localizar a subetapa (fase, arquivos prováveis, riscos, commit sugerido).
3. `03` — ler a ficha completa do requisito: fluxos, critérios de aceite, testes.
4. `04` — conferir os RNFs que o requisito toca (limites, segurança, privacidade).
5. `09` — DoD geral + DoD do tipo antes de considerar pronto.
6. `05` — registrar evidências e atualizar status.
7. `00` §5 — marcar o requisito.

## 5. Quem controla o quê

- **Status e progresso:** `00-controle-mestre.md` (legenda em §2, checklist em §5).
  Nenhum outro documento inventa status.
- **Critérios de aceite:** por requisito em `03`; transversais e por tipo em `09`.
- **Evidências:** `05-matriz-de-rastreabilidade.md` — comando executado, resultado
  e caminho de código/teste. Sem entrada na matriz, não há CONCLUÍDO.
- **Decisões:** `08` §4 (aprovadas, com data) e §5 (pendentes de confirmação).
  Uma decisão só vira texto normativo depois de registrada lá.
- **Escopo:** `01` §9 (com o recorte aprovado) e `00` §3.1 (a lista dos 41).

## 6. Ritual de atualização após cada entrega

```
selecionar requisito (00 §5 e 03)
  → planejar a subetapa (06)
  → implementar
  → testar (automatizado; manual quando interface)
  → validar critérios de aceite (03 + 09)
  → registrar evidências (comando + resultado + caminhos) na matriz (05)
  → marcar o requisito no checklist (00 §5)
  → commit local com a mensagem sugerida (06)
```

Regras que não mudam: status só da legenda oficial; requisito só vira CONCLUÍDO
com código, testes, critérios cumpridos e evidência; nenhum requisito recomendado
atrasa um obrigatório; nenhuma decisão incerta é tomada em silêncio.

## 7. Markdown é a fonte; PDF é apresentação

- **Fontes editáveis oficiais:** os arquivos `.md` desta pasta. Toda alteração
  acontece aqui.
- **PDF consolidado:** versão de **leitura e apresentação**, gerada a partir destes
  Markdown. Não é fonte de verdade e pode estar defasado; em caso de divergência,
  vale o Markdown.
- Ordem de prioridade para conferir qualquer informação: **repositório Git**
  (código, testes, evidências) → **Markdown desta pasta** (baseline documental) →
  `08` §4 (decisões) → PDF (apresentação).

## 8. Estado atual em uma tela

| Item | Valor |
|---|---|
| Revisão documental | 3 — baseline aprovado (10/08/2026) |
| Requisitos catalogados | 51 |
| Situação | 30 CONCLUÍDOS · 4 PARCIAIS · 17 NÃO INICIADOS |
| Escopo obrigatório V1 | 41 (progresso 30/41) |
| Recomendados V1 (não bloqueiam) | LIVE-006a · RF-INT-006 |
| Fase A1 | **CONCLUÍDA em 10/08/2026** como atividade de auditoria (auditoria concluída ≠ achados corrigidos) |
| Baseline técnico local | commit `f3f95de`, `main` 22 à frente de `origin/main`; núcleo **2052 passed** (cobertura 92,39 %); Live backend **127 passed**; frontend **52 passed** (22 + 16 + 14) |
| Gates obrigatórios antes da A2 | **A1.1** baseline documental versionado · **A1.2** reprodutibilidade e higiene do repositório · **A1.3** correção mínima da dependência vulnerável · **A1.4** consolidação da CI |
| Próxima subetapa | A1.1 (planejada em `06`, não executada) |
| Implementação de produto | não iniciada |
