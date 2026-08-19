# Card 01 — Análise e organização de planilhas

**Status: HOMOLOGADO.**
Homologado por Paulo Lavarini (proprietário do produto) em **19/08/2026**, ao
final de uma sessão de homologação humana guiada, conduzida com a planilha real
`Vendas - Dez.xlsx` (7.089 registros) e com as planilhas de teste sintéticas.

Este documento diz o que foi feito, como verificar e — com a mesma clareza — o
que **não** foi feito e o que **não** foi testado. O registro da homologação,
com os defeitos encontrados e corrigidos durante ela, está na seção M.

---

## A. O que o card faz hoje

Você envia um CSV, XLSX, XLS ou ODS. O AutoTarefas:

1. lê a estrutura (aba, cabeçalho, colunas, tipos) e mostra o diagnóstico;
2. faz **sempre** a análise geral — incluindo a verificação de linhas 100%
   duplicadas, que não depende de schema, perfil nem opção escondida;
3. avalia a **apresentação** com critérios objetivos e diz um dos três
   veredictos: já organizada / pode ser melhorada / estrutura ambígua;
4. oferece, **desligado por padrão**: correções seguras, versão organizada,
   ordenação (coluna + direção), indicadores e aba de Dashboard;
5. executa e entrega no máximo três downloads principais, com o pacote
   técnico em "Downloads avançados".

O arquivo original nunca é alterado. Tudo acontece sobre uma cópia.

---

## A.1 Para que tipo de planilha (o escopo de entrada)

**O Card 01 não é uma ferramenta de vendas.** `Vendas - Dez.xlsx` foi apenas o
arquivo real usado na homologação.

A entrada é: **dados tabulares** — registros em linhas, campos em colunas.
Nenhuma verificação depende do nome das colunas nem presume o assunto do
arquivo. Vale igualmente para financeiro, estoque, clientes, serviços e
agendamentos, protocolos e atendimentos públicos, assistência social, compras e
contratos, recursos humanos, logística, educação, saúde administrativa,
pesquisas e bases públicas, projetos e patrimônio.

**XLSX** — análise geral, avaliação da apresentação e versão organizada.
É o único formato completo, porque é o único que o openpyxl abre para
inspecionar formatação.

**CSV** — análise geral. Não há apresentação para avaliar: é texto puro.

**ODS (LibreOffice)** — análise geral. Sem avaliação de apresentação e sem
versão organizada. *Verificado de ponta a ponta* (seção I.2).

**XLS (Excel antigo)** — análise geral, pelo mesmo caminho do ODS.
**Não verificado com um arquivo válido** — ver a ressalva na seção I.4.

Nos três últimos a tela **não oferece** a versão organizada, e diz o porquê.
Prometer organização neles seria mentira.

O que é verificado automaticamente, em qualquer área, quando aplicável:

| Verificação | Como aparece |
| --- | --- |
| Existência e localização do cabeçalho | campo "Cabeçalho" + pergunta quando ambíguo |
| Abas, linhas e colunas | diagnóstico e aba "Abas do arquivo" |
| Tipos observados nas colunas | inferidos do conteúdo, nunca do nome |
| Células vazias | contador por coluna + `coluna_vazia` |
| Linhas 100% duplicadas | sempre, como aviso, sem remover |
| Títulos de coluna repetidos | critério estrutural → veredicto ambíguo |
| Mistura de tipos | `coluna_mista` e `tipos_misturados`, sem converter à força |
| Espaços desnecessários | `espacos_extras` |
| Fórmulas existentes | `formulas` (usa o valor salvo) e recusa de ordenação |
| Mais de uma tabela na mesma aba | critério estrutural → veredicto ambíguo, com a linha |
| Números guardados como texto | observação na revisão e no relatório, sem converter |
| Rodapé de totais | `rodape_suspeito`, sem remover |
| Data em formato americano | observação na revisão e no relatório, sem alterar |
| Apresentação, cabeçalho, larguras, filtro, painel | 11 critérios objetivos (seção C) |

**O que o sistema não faz sem confirmação, em nenhuma área:** concluir que
código repetido é erro, excluir duplicidade, calcular faturamento, interpretar
regra contábil ou legal, ordenar, criar gráfico ou indicador, e alterar
fórmula, identificador, zero à esquerda ou valor. Regra de negócio só entra
por confirmação de papéis de coluna ou por schema YAML.

---

## B. A jornada, tela a tela

| Etapa | O que aparece |
| --- | --- |
| 1. Arquivo | Enviar planilha ou testar com exemplo |
| 2. Análise | Diagnóstico, abas classificadas, prévia, observações |
| 3. Revisão e opções | Veredicto da apresentação + as confirmações |
| 4. Resultado | Um dos quatro desfechos + downloads |

**O que saiu do fluxo principal** (mudança do escopo congelado):

- "Confirmar schema sugerido" — não existe mais como parada obrigatória;
- "Baixar schema sugerido" — deixou de ser etapa; virou link auxiliar dentro
  da opção avançada;
- "Usar um perfil pronto" — saiu da jornada de análise de planilhas.

Sobrou uma única porta avançada: **"Adicionar regras do meu processo (YAML)"**,
com botão de voltar sem enviar.

Prova automatizada: `live_demo/frontend/src/components/SpreadsheetJourney.test.tsx`,
teste `vai do diagnóstico direto para a revisão, sem etapa de schema` — ele
verifica que os botões antigos **não existem** e que a trilha tem quatro etapas.

---

## C. Avaliação da apresentação — critérios objetivos

Nada aqui é opinião de estilo. Cada critério é verificável em
`src/autotarefas/organize/presentation.py`:

| Critério | Como é medido | Peso |
| --- | --- | --- |
| `estrutura_tabular` | mesclagens, títulos repetidos, colunas sem título | **estrutural** |
| `tabela_unica` | uma só tabela na aba, sem outra base colada abaixo | **estrutural** |
| `cabecalho_presente` | linha de cabeçalho identificável, sem vazios | **estrutural** |
| `cabecalho_destacado` | negrito ou preenchimento na linha do cabeçalho | cosmético |
| `larguras_legiveis` | largura em faixa legível **e** título não cortado | cosmético |
| `formatos_consistentes` | mesmo `number_format` na coluna inteira | cosmético |
| `alinhamento_coerente` | número à direita, texto à esquerda | cosmético |
| `filtro` | `auto_filter` aplicado | cosmético |
| `painel_congelado` | `freeze_panes` abaixo do cabeçalho | cosmético |
| `cores_moderadas` | no máximo 4 cores de preenchimento distintas | cosmético |
| `tabela_estruturada` | Tabela do Excel — quando não há, é "não aplicável" | cosmético |

**Regra do veredicto:** falha em critério estrutural → `ambígua`; nenhuma falha
→ `organizada`; só falhas cosméticas → `melhorável`.

Cada pendência mostrada na tela traz o **motivo**, não só o nome do critério —
por exemplo, "Estrutura tabular clara — títulos de coluna repetidos".

Consequência prática, que é o ponto do contrato: **planilha já organizada não
recebe proposta de reformatação**, e **estrutura ambígua não é organizada por
chute** — ela vira pergunta.

---

## D. O que a organização faz e o que ela nunca faz

`src/autotarefas/organize/organizer.py` copia o arquivo e mexe **só na camada
de apresentação**:

- destaca o cabeçalho, ajusta larguras, aplica filtro e congela o painel;
- uniformiza formatos numéricos e alinhamento por coluna.

Nunca:

- altera valores, fórmulas ou resultados;
- altera identificadores, códigos ou zeros à esquerda (células com formato
  texto `@` são deixadas intactas);
- reordena linhas sem confirmação de coluna **e** direção;
- renomeia colunas;
- inventa gráfico, aba ou indicador.

Ordenação tem duas recusas explícitas: coluna inexistente e **planilha com
fórmulas** (reordenar quebraria referências).

**Ordenar é a única opção que mexe na posição das linhas.** Organizar, resumir
e gerar o dashboard não tocam na ordem nem no conteúdo da aba de dados.

---

## E. Como verificar você mesmo

```bash
npm --prefix live_demo/frontend run build
python -m uvicorn live_demo.backend.app.main:app --port 8000
```

Abra `http://127.0.0.1:8000`, escolha o card e teste com estas fixtures
sintéticas (`tests/fixtures/dominios/`):

| Arquivo | O que deve acontecer |
| --- | --- |
| `financeiro_profissional.xlsx` | veredicto **já organizada**; nenhuma proposta de formatação |
| `vendas_simples.xlsx` | veredicto **pode ser melhorada**; a caixa aparece desligada |
| `pesquisa_ambigua.xlsx` | veredicto **estrutura ambígua**; organização não é oferecida |
| `servico_publico.xlsx` | 1 par de linhas repetidas relatado; zeros à esquerda preservados |
| `estoque_com_formulas.xlsx` | ordenação recusada com explicação |
| `atendimentos_duas_abas.xlsx` | pergunta qual aba usar, sem escolher em silêncio |
| `contratos_sem_anomalia.xlsx` | conclui sem nada a decidir |
| `clientes.csv` | CSV: sem avaliação de apresentação, análise normal |

Nota de operação: o Live aceita **40 sessões simultâneas** e cada uma expira em
**15 minutos**. Passando disso, o envio responde "servidor ocupado, tente em
instantes" — é o limite funcionando, não uma falha. Sessões antigas somem
sozinhas.

---

## F. Downloads

Área principal — no máximo três:

1. **Arquivo original** (como você enviou);
2. **Planilha organizada** — só existe se você confirmou a formatação;
3. **Relatório da análise** (`relatorio_analise.xlsx`) — sempre.

O relatório traz as abas Resumo, Abas do arquivo, Ocorrências encontradas,
Linhas para revisão, Alterações realizadas, Antes e depois e Indicadores
confirmados. Abas vazias são omitidas em vez de aparecerem em branco.

A aba passou a se chamar **Ocorrências encontradas**: duplicidade é aviso,
nunca problema, e "16 problemas" assustava sem motivo.

Em **Downloads avançados** ficam os artefatos técnicos: registros válidos,
registros para revisão, relatórios em JSON, schema aplicado e o pacote
`pacote_execucao.zip` com as somas de verificação.

---

## F.1 Resumo visual, prévia e Dashboard

Os três seletores do resumo dizem o que cada papel faz, e a coluna que o
sistema identificou aparece marcada como **(sugerida)**:

| Papel | O que é | O que vira |
| --- | --- | --- |
| **Valor** | o número que será somado | a altura das barras |
| **Categoria** | por quem agrupar | as barras |
| **Data** | agrupa por mês | a linha do tempo |

Regras que a tela aplica antes de executar:

- valor sozinho, sem categoria nem data, **não** gera resumo — e a tela avisa;
- coluna de Valor que não é numérica **avisa na hora da escolha**, usando o
  tipo que a análise já tinha observado;
- **"Ver prévia do resumo"** calcula os totais antes de executar, com o mesmo
  cálculo da execução final — prévia e resultado não podem divergir.

Marcando **"Adicionar uma aba de Dashboard na planilha organizada"**, a
`planilha_organizada.xlsx` ganha uma aba nova, na frente das outras, com as
tabelas e os gráficos. Três condições, todas necessárias: versão organizada
confirmada (é onde a aba mora), coluna de valor confirmada e a caixa marcada.

O topo da aba declara de quais colunas os números vieram. A aba dos seus dados
**não** recebe gráfico, total nem coluna nova. Os indicadores saem também no
`relatorio_analise.xlsx`, na aba "Indicadores confirmados", mesmo sem o
dashboard.

---

## G. Os quatro desfechos

| Situação | O que a tela diz |
| --- | --- |
| Organizada e sem pendências | "Concluído — nada exigiu a sua decisão" |
| Formatação aplicada | "Concluído — versão organizada gerada" |
| Há o que decidir | "Concluído — há pontos que dependem da sua decisão" |
| Não deu para concluir | "Não foi possível concluir com segurança" + motivo |

O terceiro caso **não é erro do sistema**: é a análise fazendo o trabalho dela.
Quando há pendências **e** a versão organizada foi gerada, a tela mostra as duas
notícias — a confirmação da formatação não fica escondida atrás do aviso.

---

## H. Duplicidade — o que é e o que não é

- Linha 100% duplicada é **aviso**, nunca erro, e **nenhuma linha é removida**.
- A primeira ocorrência é tratada como canônica; as excedentes são apontadas
  com número da linha física, grupo, linha canônica e motivo.
- **Chave repetida não é duplicidade.** A mesma venda com vários itens é o
  comportamento normal de uma planilha de vendas.

`registros_para_revisao.csv` inclui erros **e** avisos que exigem decisão
humana (com as colunas `_linha`, `_severidade`, `_categoria`,
`_grupo_duplicidade`, `_linha_canonica`, `_linhas_relacionadas`, `_motivo`).
`registros_invalidos.csv` continua contendo apenas erros — a severidade não
foi alterada para forçar o arquivo a ficar cheio.

---

## I. O que foi comprovado, e como

Esta separação é obrigatória e foi pedida explicitamente. Nada aqui mistura o
que rodou na planilha real com o que rodou em fixture.

### I.1 Comprovado na planilha real do proprietário (`Vendas - Dez.xlsx`)

O arquivo **não está versionado** e **não entra em fixture, commit ou ZIP**.

- 7.089 registros lidos, aba `Plan1`, cabeçalho na linha 1, confiança 100%;
- 16 grupos de linhas 100% duplicadas → 32 linhas envolvidas;
- as linhas sinalizadas são exatamente as segundas ocorrências dos 16 pares;
- 3.787 códigos de venda distintos, 2.045 repetidos, até 8 itens por venda —
  **nenhum falso positivo** de duplicidade entre eles;
- veredicto **"pode ser melhorada"**, com as três pendências corretas
  (cabeçalho sem destaque, títulos cortados, sem painel congelado);
- planilha organizada auditada célula a célula: **valores idênticos**, 7.090
  linhas nos dois arquivos, formatos de moeda e data preservados, filtro
  mantido, painel congelado em `A2`, larguras ajustadas nas 7 colunas,
  **nenhuma coluna, aba ou gráfico inventado**;
- indicadores confirmados (Valor Final por Produto e por mês) com total de
  R$ 2.917.311 e dois gráficos, sem tocar na aba de dados;
- `validacao_report.json` sem caminho de servidor (só o nome do arquivo);
- nenhum caminho interno nos quatro arquivos baixados;
- somas sha256 conferem e o ZIP abre íntegro.

### I.2 Comprovado por fixture sintética

- os três veredictos de apresentação (`tests/organize/test_card_planilhas.py`);
- preservação de zeros à esquerda e de formato texto;
- recusa de ordenação em planilha com fórmulas;
- classificação de abas (dados/apresentação/auxiliar/vazia/ambígua) e a
  pergunta quando há mais de uma aba com dados;
- classificação correta em planilhas de 20, 112, 500 e 3.000 linhas;
- detecção de segunda tabela na mesma aba, com a linha onde ela começa;
- números guardados como texto e datas em formato americano;
- geração do `relatorio_analise.xlsx` com as abas previstas;
- indicadores só com papéis confirmados (confiança mínima 0,6);
- leitura de `.ods` e recusa explicada de `.xls` ilegível
  (`tests/reader/test_formatos_legados.py`).

### I.3 Comprovado em navegador real (Chromium)

`tests/e2e/test_jornada_planilhas_e2e.py` — 6 testes, **6 passaram em 30,3 s**.
O backend serve o `dist/` na própria origem, sem dev server no meio.

| Teste | Cenário do contrato |
| --- | --- |
| `test_planilha_ja_organizada_nao_recebe_proposta_de_formatacao` | 1 |
| `test_planilha_sem_formatacao_aceita_a_organizacao` | 2 |
| `test_planilha_com_duplicidade_relata_sem_remover` | 3 |
| `test_recusar_a_formatacao_nao_gera_planilha_organizada` | 4 |
| `test_downloads_reais_da_planilha_organizada_e_do_relatorio` | 5 |
| `test_dashboard_so_nasce_com_os_papeis_confirmados` | 6 (dashboard) |

O cenário 5 baixa os arquivos pela mesma URL que o navegador usa e compara o
**arquivo original byte a byte** com o que foi enviado.

```bash
python -m pytest tests/e2e/test_jornada_planilhas_e2e.py -q --no-cov
```

Limitações honestas deste E2E: roda só em Chromium; usa fixtures pequenas
(dezenas de linhas), não um arquivo de 7 mil registros; e não cobre rede
instável, upload interrompido ou sessão expirando no meio.

### I.4 Não testado

- **`.xls` válido.** A leitura de `.xls` usa exatamente o mesmo caminho do
  `.ods` (pandas + motor específico), e o `.ods` foi verificado de ponta a
  ponta. Mas nenhum `.xls` legítimo foi lido: o projeto não tem como *criar*
  um — `xlrd` só lê, e `xlwt` (a única biblioteca que escreve) está sem
  manutenção desde 2017 e não foi adicionada como dependência só para isso.
  O que **foi** verificado é a rede de proteção: um `.xls` que não abre vira
  recusa com o motivo, nunca erro técnico. Se aparecer um `.xls` real, basta
  enviá-lo pela tela — e o teste automatizado pode então ser escrito;
- planilhas realmente protegidas por senha (a recusa foi verificada com
  arquivo ilegível, não com um arquivo cifrado de verdade);
- arquivos com macro — `.xlsm` é recusado no envio, por decisão de projeto;
- arquivos acima do limite de upload configurado;
- Firefox e Safari;
- leitores de tela reais (o teclado e os rótulos ARIA existem, mas ninguém
  navegou a jornada inteira com NVDA/JAWS);
- planilhas com mais de 100 mil linhas.

---

## I.5 Observações que o sistema faz sem alterar nada

Aparecem na tela de revisão, **antes** de executar, e também no relatório:

- **data em formato americano** (`mm-dd-yy`, mês antes do dia);
- **números guardados como texto** — o valor é entendido pela análise, mas
  dentro do Excel a coluna não soma nem ordena como número.

Nos dois casos nada é convertido: trocar o formato mudaria como a planilha é
lida, e essa decisão é do dono do arquivo. Identificador com zero à esquerda
fica de fora do aviso de propósito — `000123` é código, não quantidade.

---

## J. Estruturas que exigem cautela

Comportamento observado em sondas de 18 e 19/08/2026 — exceto na linha
marcada como não verificada:

| Estrutura | Comportamento |
| --- | --- |
| Cabeçalho não identificável | pergunta qual linha usar |
| Mesclagens na área de dados | veredicto **ambíguo**; não organiza |
| Títulos de coluna repetidos | veredicto **ambíguo**; não organiza |
| Várias tabelas na mesma aba | veredicto **ambíguo**, dizendo em que linha a segunda começa |
| Formulário/relatório sem estrutura tabular | aba classificada como "apresentação" |
| Arquivo corrompido ou ilegível | recusa com o motivo — **verificado** |
| Planilha protegida por senha | espera-se a mesma recusa, pela mesma porta — **não verificado** (I.4) |
| Macros (`.xlsm`) | recusado no envio, explicando que o motivo é macro |
| Gráficos, imagens e tabelas dinâmicas | declarados em "Observações e limites" |
| Números guardados como texto | observação, sem converter |

---

## K. Segurança e preservação

- o original nunca é escrito — só copiado;
- execução em diretório temporário isolado, com proteção contra travessia de
  caminho;
- nenhum caminho interno de servidor aparece nos artefatos;
- fórmulas e macros não são executadas na leitura;
- nada é enviado a serviço externo neste fluxo (`egress_lockdown`);
- a planilha real do proprietário nunca foi versionada nem incluída em
  fixture, commit ou pacote.

---

## L. Validações da entrega final

| Verificação | Resultado |
| --- | --- |
| `pytest` (núcleo) | **2.485** passaram · cobertura 92,86% (mínimo 85%) |
| `pytest live_demo/backend/tests` | **172** passaram |
| `npm test` (vitest) | **72** passaram |
| `npm run typecheck` | sem erros |
| `npm run build` | build gerado |
| `ruff check .` | limpo |
| `ruff format --check .` | limpo |
| `mypy src/` | 116 arquivos, sem problemas |
| E2E Chromium | **6** passaram em 30,3 s |

---

## M. Registro da homologação humana

**Data:** 19/08/2026 · **Homologado por:** Paulo Lavarini (proprietário)
**Verificações técnicas:** 18 e 19/08/2026
**Arquivo real usado:** `Vendas - Dez.xlsx` (7.089 registros, não versionado)

### M.1 O que a homologação humana encontrou

Sete achados que **nenhum dos 2.448 testes automatizados existentes naquele
momento, nem o teste de navegador, haviam pego**. Todos corrigidos antes da
homologação; a suíte terminou a sessão com 2.485 testes de núcleo, já
incluindo as regressões escritas para cada um destes achados.

**1. Classificação de aba errada em toda planilha real** *(informação falsa)*
Qualquer tabela com mais de 111 linhas era rotulada "ambígua — 1% preenchida":
a contagem de células olhava 50 linhas e dividia pela área da planilha inteira.
*Correção:* conta refeita, com regressão em 20, 112, 500 e 3.000 linhas.

**2. Avaliação da apresentação levava 16 s** *(desempenho)*
Numa planilha de 7 mil linhas, e rodava duas vezes — a jornada parecia travada.
*Correção:* uma passada com `values_only` (16 s → 0,5 s; jornada de ~40 s →
8,6 s), mais um teste de guarda de 5 s para 5 mil linhas.

**3. Barra dizia "Conectando…" para sempre** *(informação falsa)*
Media se os servidores de demonstração estavam vivos, não o sistema.
*Correção:* passou a refletir a saúde do backend.

**4. Lista dos seletores ilegível** *(usabilidade)*
Texto branco sobre fundo branco, visível só ao passar o mouse: a classe
`bg-panel` não existia na paleta, então o campo ficava sem fundo.
*Correção:* token real, mais uma regra explícita para `select` e `option`.

**5. "16 problemas encontrados"** *(vocabulário)*
Contradizia o próprio produto, que trata duplicidade como aviso.
*Correção:* "Ocorrências encontradas", sem destaque de erro.

**6. "Larguras legíveis: OK" seguido de "Títulos visíveis: melhorar"**
*(vocabulário)* — duas linhas do relatório se contradizendo.
*Correção:* um critério só.

**7. Motivo errado quando faltava a dimensão** *(informação falsa)*
O relatório dizia "nenhuma coluna de valor foi confirmada" mesmo quando ela
tinha sido escolhida e o que faltava era categoria ou data.
*Correção:* três motivos distintos, cada um verdadeiro.

### M.2 Lacunas de escopo fechadas na homologação

O proprietário registrou que o card deve servir a qualquer área, não só
vendas. Três itens do contrato não estavam cobertos e foram implementados:

- **várias tabelas na mesma aba** — eram lidas como uma só, com a contagem de
  registros misturada e sem aviso;
- **números guardados como texto** — o valor era entendido, mas nada era dito;
- **tabelas dinâmicas** — não eram declaradas como não preserváveis.

### M.3 Melhorias entregues a pedido do proprietário

- aba de **Dashboard** opcional dentro da planilha organizada;
- **prévia do resumo** antes de executar;
- **aviso imediato** quando a coluna de Valor não é numérica;
- leitura de **`.xls` e `.ods`**, com o limite declarado na tela.

### M.4 Commits desta homologação

`c91276a` · `d6b8fa6` · `844e06c` · `733ab43` · `0d9a327` · `5b413c9` ·
`f7f1c11` — todos locais. Sem push, tag, PR, release ou mudança de versão.

### M.5 Sugestões registradas, não implementadas

Nenhuma bloqueia o uso; ficam para uma próxima rodada, se aparecerem no uso
real:

1. permitir escolher **qual** tabela usar quando há mais de uma na mesma aba
   (hoje o sistema explica e devolve a decisão, mas não oferece a escolha);
2. lembrar as opções confirmadas entre execuções do mesmo arquivo;
3. detectar planilha protegida por senha com mensagem específica, em vez da
   recusa genérica de arquivo ilegível.
