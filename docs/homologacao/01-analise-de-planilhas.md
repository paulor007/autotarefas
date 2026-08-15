# Card 01 — Análise e organização de planilhas

**Status: Implementação preparada para homologação.**
A homologação é sua. Este documento diz o que foi feito, como verificar e —
com a mesma clareza — o que **não** foi feito e o que **não** foi testado.

Escopo congelado em 15 seções pelo proprietário. Este roteiro cobre esse
contrato, não o escopo anterior do card.

---

## A. O que o card faz hoje

Você envia um CSV ou XLSX. O AutoTarefas:

1. lê a estrutura (aba, cabeçalho, colunas, tipos) e mostra o diagnóstico;
2. faz **sempre** a análise geral — incluindo a verificação de linhas 100%
   duplicadas, que não depende de schema, perfil nem opção escondida;
3. avalia a **apresentação** com critérios objetivos e diz um dos três
   veredictos: já organizada / pode ser melhorada / estrutura ambígua;
4. oferece, **desligado por padrão**: correções seguras, versão organizada,
   ordenação (coluna + direção) e indicadores (papéis das colunas);
5. executa e entrega no máximo três downloads principais, com o pacote
   técnico em "Downloads avançados".

O arquivo original nunca é alterado. Tudo acontece sobre uma cópia.

---

## B. A jornada, tela a tela

| Etapa | O que aparece |
| --- | --- |
| 1. Arquivo | Enviar CSV/XLSX ou testar com exemplo |
| 2. Análise | Diagnóstico, abas classificadas, prévia, observações |
| 3. Revisão e opções | Veredicto da apresentação + as quatro confirmações |
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
| `estrutura_tabular` | ausência de mesclagens na área de dados | **estrutural** |
| `cabecalho_presente` | linha de cabeçalho identificável, sem vazios | **estrutural** |
| `cabecalho_destacado` | negrito ou preenchimento na linha do cabeçalho | cosmético |
| `larguras_adequadas` | largura ≠ padrão nas colunas com texto longo | cosmético |
| `texto_nao_cortado` | conteúdo cabe na largura declarada | cosmético |
| `formatos_consistentes` | mesmo `number_format` na coluna inteira | cosmético |
| `alinhamento_coerente` | número à direita, texto à esquerda | cosmético |
| `filtro` | `auto_filter` aplicado | cosmético |
| `painel_congelado` | `freeze_panes` abaixo do cabeçalho | cosmético |
| `cores_moderadas` | no máximo 4 cores de preenchimento distintas | cosmético |
| `tabela_estruturada` | Tabela do Excel — quando não há, é "não aplicável" | cosmético |

**Regra do veredicto:** falha em critério estrutural → `ambígua`; nenhuma falha
→ `organizada`; só falhas cosméticas → `melhorável`.

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

---

## F. Downloads

Área principal — no máximo três:

1. **Arquivo original** (como você enviou);
2. **Planilha organizada** — só existe se você confirmou a formatação;
3. **Relatório da análise** (`relatorio_analise.xlsx`) — sempre.

O relatório traz as abas Resumo, Abas do arquivo, Problemas encontrados,
Linhas para revisão, Alterações realizadas, Antes e depois e Indicadores
confirmados. Abas vazias são omitidas em vez de aparecerem em branco.

Em **Downloads avançados** ficam os artefatos técnicos: registros válidos,
registros para revisão, relatórios em JSON, schema aplicado e o pacote
`pacote_execucao.zip` com as somas de verificação.

---

## G. Os quatro desfechos

| Situação | O que a tela diz |
| --- | --- |
| Organizada e sem pendências | "Concluído — nada exigiu a sua decisão" |
| Formatação aplicada | "Concluído — versão organizada gerada" |
| Há o que decidir | "Concluído — há pontos que dependem da sua decisão" |
| Não deu para concluir | "Não foi possível concluir com segurança" + motivo |

O terceiro caso **não é erro do sistema**: é a análise fazendo o trabalho dela.

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

### I.1 Comprovado na planilha real do proprietário (`Vendas - Dez (2).xlsx`)

O arquivo **não está versionado** e **não entra em fixture, commit ou ZIP**.

- 7.089 registros lidos;
- 16 grupos de linhas 100% duplicadas → 32 linhas envolvidas;
- as linhas sinalizadas são exatamente as segundas ocorrências dos 16 pares;
- 3.787 códigos de venda distintos, 2.045 repetidos, até 8 itens por venda —
  **nenhum falso positivo** de duplicidade entre eles;
- `validacao_report.json` sem caminho de servidor (só o nome do arquivo);
- somas sha256 conferem e o ZIP abre íntegro.

### I.2 Comprovado por fixture sintética

- os três veredictos de apresentação (`tests/organize/test_card_planilhas.py`);
- preservação de zeros à esquerda e de formato texto;
- recusa de ordenação em planilha com fórmulas;
- classificação de abas (dados/apresentação/auxiliar/vazia/ambígua) e a
  pergunta quando há mais de uma aba com dados;
- geração do `relatorio_analise.xlsx` com as abas previstas;
- indicadores só com papéis confirmados (confiança mínima 0,6).

### I.3 Comprovado em navegador real (Chromium)

`tests/e2e/test_jornada_planilhas_e2e.py` — 5 testes, **5 passaram em 30,6 s**.
O backend serve o `dist/` na própria origem, sem dev server no meio.

| Teste | Cenário do contrato |
| --- | --- |
| `test_planilha_ja_organizada_nao_recebe_proposta_de_formatacao` | 1 |
| `test_planilha_sem_formatacao_aceita_a_organizacao` | 2 |
| `test_planilha_com_duplicidade_relata_sem_remover` | 3 |
| `test_recusar_a_formatacao_nao_gera_planilha_organizada` | 4 |
| `test_downloads_reais_da_planilha_organizada_e_do_relatorio` | 5 |

O cenário 5 baixa os arquivos pela mesma URL que o navegador usa e compara o
**arquivo original byte a byte** com o que foi enviado.

```bash
python -m pytest tests/e2e/test_jornada_planilhas_e2e.py -q --no-cov
```

Limitações honestas deste E2E: roda só em Chromium; usa fixtures pequenas
(dezenas de linhas), não um arquivo de 7 mil registros; e não cobre rede
instável, upload interrompido ou sessão expirando no meio.

### I.4 Não testado

- planilhas protegidas por senha e arquivos com macro (`.xlsm`);
- arquivos acima do limite de upload configurado;
- Firefox e Safari;
- leitores de tela reais (o teclado e os rótulos ARIA existem, mas ninguém
  navegou a jornada inteira com NVDA/JAWS);
- planilhas com mais de 100 mil linhas.

---

## J. Segurança e preservação

- o original nunca é escrito — só copiado;
- execução em diretório temporário isolado, com proteção contra travessia de
  caminho;
- nenhum caminho interno de servidor aparece nos artefatos;
- fórmulas e macros não são executadas na leitura;
- nada é enviado a serviço externo neste fluxo.

---

## K. Validações desta entrega

| Verificação | Resultado |
| --- | --- |
| `pytest` (núcleo) | 2.448 passaram · cobertura 92,93% (mínimo 85%) |
| `pytest live_demo/backend/tests` | 159 passaram |
| `npm test` (vitest) | 66 passaram |
| `npm run typecheck` | sem erros |
| `npm run build` | build gerado |
| `ruff check .` | limpo |
| `ruff format --check .` | limpo |
| `mypy src/` | 115 arquivos, sem problemas |
| E2E Chromium | 5 passaram em 30,6 s |

---

## L. O que decidir na homologação

1. Os três veredictos batem com o que você esperaria de cada planilha?
2. A versão organizada ficou boa — e ficou **igual** onde tinha de ficar
   (valores, fórmulas, códigos, ordem das linhas)?
3. O relatório da análise responde às suas perguntas?
4. Três downloads principais são suficientes na tela inicial?
5. Falta alguma pergunta que o sistema deveria estar fazendo, em vez de
   decidir sozinho?
