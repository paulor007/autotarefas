# 07 — Sugestões e Oportunidades

Duas partes obrigatórias: (1) análise crítica de quem estudou o produto por
fora e por dentro, com as **10 melhores sugestões novas** (não previstas nos
requisitos existentes) ranqueadas e as 3 primeiras detalhadas — a revisão 2
acrescenta as **sugestões 11–14** em formato de 11 campos; (2) a
especificação do **mecanismo de sugestões automáticas dentro do produto**.

---

## Parte 1 — Análise crítica do produto

**O que o produto é, de verdade, hoje:** um funil de planilhas excepcionalmente
bem construído (ler → analisar → validar → limpar → evidenciar) acoplado a
saídas de integração (API, e-mail, Telegram, scraping, RPA), com uma vitrine
pública segura que executa o produto real. A engenharia é o ponto forte
inegociável: **2.052 testes** no núcleo (baseline local de 10/08/2026), regra de "nunca inventar dado" imposta por
arquitetura (até teste de AST contra vazamento de domínio), segurança levada a
sério em cada camada.

**Onde a percepção pode trair o produto:**

1. *A visão redigida é maior que o produto.* O texto de visão fala em
   "plataforma" e num fluxo com comparar/corrigir/entregar completo; o código
   entrega tratar+conectar. A decisão de posicionamento já tomada ("ferramenta
   que trata planilhas e as conecta a sistemas") é a correta — o documento 01 já
   escreve a visão nesses termos, e a palavra "plataforma" deve ficar fora do
   material público (DP-06).
2. *Seis promessas penduradas na vitrine.* 6 de 13 cards em "em breve" transmite
   exatamente a sensação que o projeto quer evitar. Quatro deles são baratos de
   ativar (Fase A3); os dois de navegador merecem decisão explícita (DP-02), e
   "remover da vitrine + vídeo curto" é uma saída digna.
3. *O problema nº 1 do público-alvo ainda não existe — e agora é V1.* Escritório
   vive de conferir base contra base. Por decisão do responsável (05/08/2026,
   DP-04), a reconciliação (REC) deixou de ser "próximo valor" e passou a ser
   requisito obrigatório da V1 (Fase B) — o produto tem, pronta, toda a fundação
   de que ela precisa (reader, cleaning, artifacts, pacote de evidências). O
   alerta que resta é de execução, não de escopo: risco R-12 em `08`.
4. *O modo real é sub-comunicado.* O Live mostra o produto rodando, mas quem
   assiste não vê o caminho "e na minha máquina, com meus arquivos?". O bloco
   "modo real equivalente" do catálogo (02 §1) deve aparecer na interface — um
   comando copiável por card resolveria.
5. *Reuso ainda é para quem sabe YAML.* Schemas e perfis são reutilizáveis, mas
   a promessa "configurar uma vez" só se completa com a configuração de fluxo
   (CORE-006, recorte V1) — por isso ela entrou na V1 (Fase B6); o encadeamento
   genérico de tasks fica para depois.

## As 10 melhores sugestões novas (ranqueadas)

Critério do ranking: valor real para o público-alvo × aproveitamento da
arquitetura existente ÷ complexidade. Classificação de cada uma:
**[valor/complexidade]**.

| # | Sugestão | Classificação | Quando |
|---|---|---|---|
| 1 | **Comparador de versões de planilha (diff por chave)** | ALTO VALOR / BAIXA COMPLEXIDADE | **Fase B1 — dentro da V1** (absorvida por RF-REC-001) |
| 2 | **Divisor/distribuidor de planilhas por coluna** (um arquivo por filial/responsável, com envio opcional a cada um) | ALTO VALOR / BAIXA COMPLEXIDADE | pós-V1 imediato |
| 3 | **Consolidador de múltiplos arquivos** (N planilhas do mesmo layout → uma, com `_origem` e relatório de divergência de layout) | ALTO VALOR / BAIXA COMPLEXIDADE | pós-V1 imediato |
| 4 | **Cobrador de pendências por prazo** (planilha de pendências + regra de vencimento → lembretes por e-mail/Telegram + relatório de quem falta) | ALTO VALOR / BAIXA COMPLEXIDADE | Fase D1 (após COM-003 — idempotência de comunicação) |
| 5 | **Receitas encadeadas (pipeline)** — validar→corrigir→enviar→notificar num YAML | ALTO VALOR / ALTA COMPLEXIDADE | pós-V1, Fase D4 (o recorte V1 de CORE-006 cobre só a configuração de fluxo) |
| 6 | **Deduplicação assistida com fusão** (agrupar prováveis duplicados, propor registro sobrevivente, decisão do usuário) | ALTO VALOR / MÉDIA COMPLEXIDADE | pós-V1 (estende `duplicates.py`) |
| 7 | **Monitor de pasta (watch)** — chegou arquivo, roda a receita | ALTO VALOR / ALTA COMPLEXIDADE | Fase D4 (CORE-008 fase 2) |
| 8 | **Conector declarativo YAML** para APIs de terceiros | ALTO VALOR / ALTA COMPLEXIDADE | Fase D3 (é RF-INT-004; fora da V1 — justificativa na ficha 03) |
| 9 | **Extração de tabelas de PDF para planilha** | VALOR MODERADO / ALTA COMPLEXIDADE | avaliar em V2 (qualidade de extração varia muito; risco de frustrar) |
| 10 | **Renomeador em massa por de-para** (planilha de nomes antigos→novos, dry-run e relatório) | VALOR MODERADO / BAIXA COMPLEXIDADE | encaixe oportunista no módulo ARQ |

## Top 3 detalhado (14 respostas cada)

### Sugestão 1 — Comparador de versões de planilha (diff por chave)

1. **Problema real:** "recebi a planilha atualizada — o que mudou?" hoje é
   conferência visual ou PROCV artesanal, lento e sem prova.
2. **Quem usaria:** administrativo, financeiro, RH, controle de estoque —
   qualquer rotina com versões mensais/semanais da mesma base.
3. **Como é feito hoje sem o sistema:** olho, filtros do Excel, PROCV/duplo
   PROCV, ou simplesmente confiando que "deve estar certo".
4. **Entrada necessária:** dois arquivos CSV/XLSX + coluna(s)-chave; opcional:
   colunas a comparar e normalização prévia.
5. **Como funcionaria (fluxo):** ler A e B com o reader existente → normalizar
   chaves (cleaning) → indexar → classificar cada registro (novo, removido,
   idêntico, divergente com colunas e valores lado a lado, chave duplicada) →
   gerar artefatos.
6. **Saída/resultado:** `divergencias.xlsx` com abas por categoria (formatação
   PLA-007), `somente_a.csv`, `somente_b.csv`, `comparacao_report.json`, resumo
   no console/Live.
7. **Valor (tempo economizado/erros evitados):** transforma horas de conferência
   em minutos e elimina a classe inteira de "diferença que ninguém viu"; também
   serve de prova (o relatório é evidência).
8. **Existe algo no sistema que já faça parecido?** Não como função; existem
   todas as peças (reader, cleaning, artifacts, duplicates para a noção de
   chave repetida).
9. **Reutiliza a arquitetura?** Integralmente — é uma task nova `BaseTask` com
   zero dependência nova.
10. **Complexidade:** BAIXA (núcleo puro + CLI + fixtures; sem rede, sem
    browser).
11. **Dependências:** PLA-001/006/007 concluídos (já estão).
12. **Riscos:** chaves sujas gerando falsos "removidos/novos" — mitigado pela
    normalização prévia opcional e pela aba de chaves duplicadas.
13. **V1 ou depois?** Primeira subetapa da V1.1 (Fase B1) — é o degrau natural
    para a reconciliação completa.
14. **Prioridade sugerida:** máxima entre as novidades (por isso virou o início
    de RF-REC-001).

### Sugestão 2 — Divisor/distribuidor de planilhas por coluna

1. **Problema real:** uma planilha-mãe precisa virar N planilhas (por filial,
   vendedor, cliente) e cada pedaço precisa chegar ao responsável certo.
2. **Quem usaria:** matriz→filiais, gestor→equipe, contabilidade→clientes.
3. **Hoje:** filtrar, copiar, colar, salvar como…, anexar e-mail por e-mail —
   repetido a cada fechamento.
4. **Entrada:** planilha + coluna de divisão; opcional: coluna/planilha de
   contatos (valor→e-mail ou chat) para distribuição.
5. **Fluxo:** validar (opcional, reusa PLA) → agrupar pela coluna → gerar um
   arquivo por valor (mantendo cabeçalho e, quando PLA-009 existir, a
   formatação) → se distribuição ativa, enviar cada arquivo ao seu responsável
   via COM-001, com relatório por destinatário.
6. **Saída:** pasta `divididos/` com N arquivos nomeados pelo valor + relatório
   de divisão/envio (quem recebeu o quê).
7. **Valor:** elimina uma tarefa mensal inteira e o erro clássico de mandar o
   arquivo da filial errada — com prova de envio.
8. **Já existe parecido?** Não; envio em massa existe (COM-001), divisão não.
9. **Reutiliza?** reader + artifacts + send_email; a distribuição é composição,
   como sync_api compõe extract+send.
10. **Complexidade:** BAIXA (divisão) / MÉDIA (com distribuição por anexo —
    exige suporte a anexo no COM-001, hoje inexistente).
11. **Dependências:** COM-001; anexo de arquivo como pequena extensão; C2 para
    idempotência antes de ligar a distribuição.
12. **Riscos:** anexo com dado sensível indo ao destinatário errado — mitigar
    com dry-run listando destino×arquivo e confirmação obrigatória.
13. **V1 ou depois?** Pós-V1 imediato: a divisão pura pode até acompanhar a Fase
    B como task irmã; a distribuição espera C2.
14. **Prioridade sugerida:** alta (é o tipo de demonstração que vende o produto
    em 30 segundos).

### Sugestão 3 — Consolidador de múltiplos arquivos

1. **Problema real:** o mesmo layout chega em N arquivos (um por filial, mês ou
   vendedor) e alguém cola tudo à mão numa planilha-mãe — errando cabeçalho,
   deslocando coluna e perdendo a origem de cada linha.
2. **Quem usaria:** matriz recebendo filiais; contabilidade recebendo clientes;
   RH consolidando unidades.
3. **Como é feito hoje sem o sistema:** copiar/colar aba a aba, com o erro
   clássico e silencioso da coluna deslocada.
4. **Entrada necessária:** pasta ou lista de arquivos CSV/XLSX; opcional: perfil
   ou schema do layout esperado.
5. **Como funcionaria (fluxo):** ler cada arquivo (reader) → conferir o layout
   contra o esperado/primeiro → empilhar com coluna `_origem` (nome do arquivo)
   → relatório de divergência de layout (colunas faltantes/extras por arquivo)
   → artefatos.
6. **Saída/resultado:** `consolidado.xlsx`/`.csv` + `consolidacao_report.json` +
   lista de arquivos rejeitados por layout, para revisão.
7. **Valor (tempo economizado/erros evitados):** elimina a colagem manual
   recorrente e a coluna deslocada que ninguém percebe; a origem rastreável linha
   a linha vira evidência.
8. **Existe algo no sistema que já faça parecido?** Não como função; existem
   todas as peças (reader, artifacts).
9. **Reutiliza a arquitetura?** Integralmente — task nova `BaseTask`, zero
   dependência nova.
10. **Complexidade:** BAIXA.
11. **Dependências:** PLA-001/007 concluídos (já estão).
12. **Riscos:** layouts quase-iguais (sinônimos de cabeçalho) gerando rejeição —
    mitigado exigindo igualdade estrita na v1 e listando as divergências para o
    usuário decidir; nada de "casar parecido" em silêncio.
13. **V1 ou depois?** Pós-V1 imediato — não bloqueia a V1 e é candidata natural à
    primeira leva após o release.
14. **Prioridade sugerida:** alta entre as novidades fora do fluxo aprovado.

### Detalhamento complementar — Sugestão 5: Receitas encadeadas (pipeline declarativo)

*(Texto mantido da versão anterior. Com a revisão 2, o recorte de configuração de
fluxo entrou na V1 via CORE-006/REC-004; este encadeamento genérico de tasks
permanece pós-V1, Fase D4.)*


1. **Problema real:** o valor do produto hoje exige comandar etapa por etapa;
   o trabalho típico é uma sequência fixa (validar → limpar → enviar →
   notificar) repetida toda semana.
2. **Quem usaria:** todo usuário recorrente do modo real; é o que transforma
   "ferramenta" em "rotina automatizada".
3. **Hoje:** scripts .bat/.sh caseiros ou repetição manual dos comandos.
4. **Entrada:** um YAML com passos nomeados (tarefa + parâmetros + condição
   simples "continua se sucesso/parcial") e referências de segredo `*_env`.
5. **Fluxo:** `autotarefas run rotina.yaml` → executa os passos em sequência →
   para na primeira falha não tolerada → relatório consolidado + audit por passo
   (como sync_api já faz com 3 entradas).
6. **Saída:** artefatos de cada passo + `rotina_report.json` com o desfecho de
   cada etapa.
7. **Valor:** é a promessa "configurar uma vez e reutilizar" completa; reduz a
   intervenção a "rodar e conferir o relatório".
8. **Já existe parecido?** O embrião conceitual é a SyncApiTask (composição de
   duas tasks com audit granular).
9. **Reutiliza?** Sim — orquestra tasks existentes; nada de lógica nova de
   domínio.
10. **Complexidade:** ALTA (formato, precedência, tolerância a falha por passo,
    passagem de artefato entre passos) — reduzível se a v1 for estritamente
    linear, sem condicionais além de "parar/continuar".
11. **Dependências:** CORE-006 (formato de receita) e DP-08; checkpoint (C2)
    torna o pipeline confiável em lotes longos.
12. **Riscos:** virar um mini-orquestrador genérico — mitigar limitando a v1 ao
    linear e recusando qualquer expressão/execução dinâmica.
13. **V1 ou depois?** Fase C1 (primeira versão linear) com evolução na D.
14. **Prioridade sugerida:** alta no médio prazo; é a terceira do ranking porque
    depende de decisões (DP-08) e disciplina de escopo.

**Recomendação consolidada (rev. 2):** a nº 1 já está dentro da V1 (Fase B1, via
RF-REC-001). Nenhuma outra sugestão entra na V1 — o escopo revisado já é o maior
que uma execução solo comporta (risco R-12). Primeira leva pós-release (Fase D1):
nº 2 (divisão pura; distribuição após COM-003), nº 11 (modelo de preenchimento) e
nº 12 (anonimizador). A nº 5 (receitas encadeadas) segue como evolução do recorte
de CORE-006 na Fase D4, com escopo linear rígido.

---

## Sugestões adicionais da revisão 2 (nº 11–14)

Acréscimos de 05/08/2026, no formato de 11 campos definido pelo responsável.
Critério mantido: valor operacional real, nunca "tecnicamente interessante".
Nenhuma delas entra na V1 (risco R-12); a posição indicada é em relação ao
ranking acima.

### Sugestão 11 — Gerador de modelo de preenchimento (template a partir de perfil/schema)

- **Problema operacional resolvido:** o cliente preenche errado porque a planilha
  "em branco" não carrega regra nenhuma — o retrabalho nasce na origem.
- **Usuário/cliente potencial:** quem recebe planilhas de terceiros (escritórios,
  RH, financeiro, órgãos que coletam dados).
- **Entrada:** perfil embutido ou schema YAML (os mesmos do validate).
- **Saída:** XLSX-modelo com cabeçalhos corretos, validação de dados nativa do
  Excel (listas para enum, número/data por coluna) e aba de instruções.
- **Benefício:** prevenção — menos erro para validar depois; padroniza o canal de
  entrada sem exigir que o cliente conheça a ferramenta.
- **Complexidade:** BAIXA (openpyxl já suporta data validation).
- **Riscos:** a validação do Excel é contornável — o modelo reduz erros, não
  substitui a validação do AutoTarefas; declarar isso na aba de instruções.
- **Dependências:** PLA-003/004 (schema sugerido e perfis) — concluídos.
- **Reaproveitamento da arquitetura:** alto (schema/perfis + estilo do
  `report_xlsx`).
- **Prioridade recomendada:** alta — posição ~entre a 3ª e a 4ª do ranking.
- **V1, pós-V1 ou futura:** pós-V1 imediato (Fase D1).

### Sugestão 12 — Anonimizador de planilhas (dados fictícios consistentes)

- **Problema operacional resolvido:** compartilhar uma planilha real para
  exemplo, suporte ou demonstração expõe dados pessoais (LGPD).
- **Usuário/cliente potencial:** qualquer operador que precisa mandar "um exemplo
  do arquivo"; o próprio projeto (fixtures e material de demonstração).
- **Entrada:** planilha + colunas sensíveis declaradas (ou detectadas pelos
  validadores existentes: CPF/CNPJ/e-mail/telefone).
- **Saída:** cópia anonimizada com substituições **consistentes** — o mesmo CPF
  real vira sempre o mesmo CPF fictício válido, preservando chaves e relações —
  mais relatório do que foi trocado.
- **Benefício:** compartilhamento seguro sem quebrar reconciliações e duplicatas;
  coerente com o compromisso LGPD do produto.
- **Complexidade:** BAIXA-MÉDIA (faker já é dependência de desenvolvimento;
  consistência via mapa determinístico local com HMAC).
- **Riscos:** falsa sensação de anonimização em colunas de texto livre — a v1
  cobre apenas colunas declaradas/detectadas e avisa isso com destaque.
- **Dependências:** `validators_br`, `cleaning` — concluídos.
- **Reaproveitamento da arquitetura:** alto.
- **Prioridade recomendada:** alta — posição ~5ª do ranking.
- **V1, pós-V1 ou futura:** pós-V1 imediato (Fase D1).

### Sugestão 13 — Pronto-socorro de CSV (conserto estrutural com trilha)

- **Problema operacional resolvido:** CSV chega com delimitador errado, encoding
  quebrado, quebra de linha dentro de campo ou linhas com colunas a mais/menos —
  e trava o fluxo antes mesmo da análise.
- **Usuário/cliente potencial:** quem recebe exportações de sistemas antigos.
- **Entrada:** o CSV problemático.
- **Saída:** CSV estruturalmente são + relatório linha a linha do que foi
  ajustado + linhas irrecuperáveis separadas para revisão.
- **Benefício:** destrava o fluxo sem edição manual às cegas, mantendo a regra da
  casa: nada corrigido em silêncio.
- **Complexidade:** MÉDIA (detecção de dialeto + reparo conservador).
- **Riscos:** reparo agressivo corromper significado — política conservadora: na
  dúvida a linha vai para revisão, nunca é "consertada no chute".
- **Dependências:** reader (diagnóstico), issues/artifacts (relato).
- **Reaproveitamento da arquitetura:** alto.
- **Prioridade recomendada:** média-alta — posição ~6ª.
- **V1, pós-V1 ou futura:** pós-V1 (Fase D).

### Sugestão 14 — Relatório executivo consolidado por período

- **Problema operacional resolvido:** quem opera o AutoTarefas para terceiros não
  tem um resumo apresentável do que foi feito no mês — a evidência existe, mas
  está em banco e JSONs.
- **Usuário/cliente potencial:** prestador de serviço/escritório; também uso
  interno para acompanhar a rotina.
- **Entrada:** audit trail + período (+ filtro opcional por task).
- **Saída:** HTML autocontido e/ou XLSX com execuções, volumes, taxas de sucesso
  e principais problemas do período.
- **Benefício:** transforma a trilha de auditoria em comunicação com
  cliente/gestor; valoriza a evidência que o produto já gera.
- **Complexidade:** BAIXA (reusa `report_audit` + renderer do dashboard).
- **Riscos:** nenhum relevante — trabalha só com dados agregados.
- **Dependências:** GOV-001/002 — concluídos.
- **Reaproveitamento da arquitetura:** alto.
- **Prioridade recomendada:** média — posição ~9ª.
- **V1, pós-V1 ou futura:** pós-V1 (Fase D).

---

## Parte 2 — Sugestões automáticas dentro do produto (espec. de RF-CORE-007)

**Princípio inegociável:** determinístico e explicável antes de qualquer IA;
nada destrutivo ou externo sem autorização expressa.

**Regras iniciais (condição objetiva → sugestão):**

| # | Condição detectada | Sugestão apresentada |
|---|---|---|
| S1 | Validação encontrou duplicatas (issues categoria `duplicado` > 0) | "Revisar duplicatas: abrir a aba de duplicados / rodar limpeza com normalização de chave" |
| S2 | Envio terminou `PARTIAL` com `registros_falhos.csv` gerado | "Reenviar somente os falhos (mesmas chaves de idempotência)" |
| S3 | Validação aprovou ≥1 registro (`registros_validos.csv` existe) | "Importar os válidos para o sistema (Cadastro automático)" — já existe como CTA no Live; generalizar para o CLI |
| S4 | Operação destrutiva prestes a rodar (organize/overwrite) sem backup recente no audit para aquela origem | "Fazer backup antes (1 comando pronto)" |
| S5 | Mesmo comando+parâmetros executado ≥3 vezes no audit | "Salvar como receita para rodar por nome" (quando CORE-006 existir) |

**Transparência obrigatória por sugestão (7 campos):** por que foi sugerida
(condição disparada, com números) · problema que resolve · ação exata que será
executada · dados que usa · risco/efeito colateral · exige confirmação? (sempre
que altera algo ou sai da máquina) · saída que produzirá.

**Onde aparece:** bloco "Próximos passos" ao final do resumo no CLI e painel
equivalente no Live; registrado também no relatório JSON (campo `sugestoes`),
para que a evidência mostre o que foi sugerido e o que o usuário aceitou.

**O que o mecanismo nunca faz:** executar sozinho, sugerir com base em conteúdo
sensível (só em contagens/estados), esconder a regra que disparou.
