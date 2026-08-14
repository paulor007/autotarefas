# Homologação 01 — Análise e organização de planilhas

**Status: AGUARDANDO HOMOLOGAÇÃO DO USUÁRIO**

**Implementação preparada para homologação.** Os testes automatizados — mesmo
os de navegador real — **não** homologam nada: eles reduzem o risco. O card só
passa a CONCLUÍDO depois que o proprietário rodar o fluxo no navegador, com o
próprio arquivo, e aprovar. Nada neste documento deve ser lido como
"homologação concluída".

> **Correção desta revisão.** A versão anterior deste documento afirmou que a
> planilha real tinha painel congelado em `A2`, cabeçalho `#1F4E78`, largura 40
> e códigos com zeros à esquerda. **Isso estava errado**: essas características
> são da fixture sintética `tests/fixtures/apresentacao/original_formatado.xlsx`,
> usada nos testes automatizados — não do arquivo do proprietário. A seção
> "O que foi comprovado" agora separa as três fontes de evidência.

---

## Como subir o sistema

Dois terminais, a partir da raiz do repositório:

```bash
venv\Scripts\python.exe -m uvicorn live_demo.backend.app.main:app --port 7860
```

```bash
npm --prefix live_demo/frontend run dev
```

Abrir no navegador: **http://localhost:5173** · saúde: <http://localhost:7860/api/health>.

## Roteiro do teste

1. Em **Soluções disponíveis**, clicar em **Selecionar** no card
   *Análise e organização de planilhas*.
2. Escolher a origem: **Testar com exemplo** (`clientes.csv`, do servidor) ou
   arrastar o seu arquivo e clicar em **Analisar meus dados**.
3. Conferir o **Diagnóstico do arquivo**: nome, aba, linha do cabeçalho,
   confiança, linhas, colunas, tipos observados, observações e prévia.
4. **Escolher como validar**:
   - *schema sugerido* — **análise geral**: só a estrutura observada, nenhuma
     regra de negócio inventada. É o caminho para uma planilha de vendas;
   - *perfil pronto* — **perfil de domínio**: traz regras já conhecidas (CPF,
     e-mail…) e pede que você indique qual coluna corresponde a cada campo;
   - *meu schema YAML* — as regras do seu processo.
5. **Revisar configuração**. Nesta tela ficam as duas confirmações:
   - **Aplicar as correções seguras** (começa desligado);
   - **Sinalizar as N linhas repetidas para revisão** (aparece **só quando a
     análise encontra linhas 100% idênticas**, e vem marcada).
6. **Executar validação** e acompanhar a saída real (SSE).
7. Conferir o resumo e **baixar os artefatos**.

## O que observar

- [ ] Aba e linha de cabeçalho detectadas correspondem à sua planilha.
- [ ] Nenhuma coluna de CPF, e-mail ou telefone é exigida numa planilha de
      vendas: com o schema sugerido, as regras saem da estrutura observada.
- [ ] Com as correções **desligadas**, *Normalizados* fica em 0 e nada muda.
- [ ] Com as correções **ligadas** e nada a corrigir, a tela diz
      **"Nenhuma correção segura foi necessária"** — não apenas um zero.
- [ ] Linhas repetidas aparecem como **N repetidas / N×2 linhas envolvidas**,
      e nenhuma é removida.
- [ ] Código de venda repetido (venda com vários itens) **não** é acusado.
- [ ] O arquivo que você enviou continua intacto no seu computador.
- [ ] Nenhum artefato traz caminho interno do servidor.

---

## O que foi comprovado — e em qual fonte

### A. Execução real com `Vendas - Dez (2).xlsx` (7.089 registros)

Rodada pelos endpoints reais da jornada, com correções seguras **ligadas** e
sinalização de repetidas **ligada**:

| Verificação | Resultado |
|---|---|
| Registros lidos | 7.089 (bate com o original) |
| Aba / cabeçalho | `Plan1` / linha 1 |
| Correções aplicadas | **0** — o arquivo não tinha nada a normalizar |
| `planilha_tratada.xlsx` × original | 7.089 registros, **todos idênticos** |
| Linhas 100% repetidas | **16 excedentes, 32 linhas envolvidas** |
| Linhas acusadas | 249, 3278, 3564, 3948, 3982, 4049, 4067, 4238, 4494, 4941, 5020, 5360, 5678, 6212, 6319, 6840 — as segundas ocorrências dos 16 pares medidos pelo proprietário |
| Códigos de venda | 3.787 distintos, 2.045 em mais de uma linha, até 8 itens por venda |
| Falso positivo por chave repetida | **nenhum**: 2.029 dos 2.045 códigos repetidos não geraram problema algum |
| `sha256` de cada artefato | confere com o informado pela API |
| `pacote_execucao.zip` | íntegro; `manifest.json` registra `sha256`, tamanho e 7.089 linhas da entrada |
| Caminho interno nos artefatos | **nenhum** (corrigido nesta revisão — ver abaixo) |

Aparência **real** do arquivo do proprietário (medida no arquivo, não suposta):
sem painel congelado; cabeçalho simples (sem preenchimento nem negrito);
larguras entre 7,6 e 12,1; autofiltro `A1:G7090`; formato de data `mm-dd-yy`;
formato monetário `R$ #,##0.00`; **sem fórmulas, sem gráficos, sem imagens** e
**sem códigos com zeros à esquerda** (`Código Venda` é inteiro).

### B. Comprovado por fixture sintética (`tests/fixtures/homologacao/`)

O arquivo real estava limpo demais para exercitar as correções. As fixturas
plantam cada caso e declaram o resultado esperado antes da execução:

| Fixture | O que prova |
|---|---|
| `A_vendas_com_anomalias.xlsx` | espaços nas pontas e internos, código `00123` como texto, quantidade como texto, data inválida, quantidade zero/negativa, valor unitário negativo, `Valor Final` ≠ `Quantidade × Valor Unitário`, linha inteira duplicada, obrigatório vazio, valor ambíguo (`1.234`) e **uma venda com 4 itens** (chave repetida legítima) |
| `B_duas_abas.xlsx` | duas abas plausíveis → o sistema **pergunta**, não escolhe |
| `C_apresentacao_rica.xlsx` | painel congelado, autofiltro, larguras, cabeçalho formatado, formato de data e monetário, fórmula e zeros à esquerda — todos preservados na planilha tratada |
| `D_com_grafico.xlsx` | gráfico é **detectado e declarado** como não preservável |

Cobertos por `tests/homologacao/test_jornada_planilhas.py` (24 testes).

### C. Comprovado por teste com NAVEGADOR REAL (Chromium)

**Arquivo:** `tests/e2e/test_jornada_planilhas_e2e.py`
**Comando:** `python -m pytest tests/e2e/test_jornada_planilhas_e2e.py -v`
**Resultado:** 1 passed (~8 s)

O teste sobe o Live de verdade (o backend serve o `dist/` na própria origem,
como em produção), abre o Chromium via Playwright e percorre a jornada
clicando na tela:

| Etapa | O que o teste faz / verifica |
|---|---|
| Abertura do Live | `page.goto` na URL do servidor recém-subido |
| Seleção do card | clica em **Selecionar** no card "Análise e organização de planilhas" |
| Upload | `set_input_files` com a fixture sintética `A_vendas_com_anomalias.xlsx` |
| Diagnóstico | espera o botão da etapa seguinte e confere nome do arquivo e aba detectada no texto renderizado |
| Escolha da validação | **Escolher como validar** → **Confirmar schema sugerido** |
| Revisão | confere que as correções seguras **começam desligadas** e que a sinalização de repetidas **vem marcada** ("Sinalizar as 1 linha…"); marca as correções |
| Execução | clica em **Executar validação** |
| SSE | espera o bloco "Arquivos desta execução", que só aparece quando o stream termina e o resultado chega |
| Resultado | confere "1 linha(s) repetida(s)" e "2 linha(s) envolvida(s)" |
| Downloads | confere os rótulos (Planilha tratada, Registros válidos, Pacote completo de evidências) e **baixa** o primeiro artefato: HTTP 200 com corpo |

**Limitações do teste:** exige `playwright install chromium` e o build do
frontend (`npm --prefix live_demo/frontend run build`) — sem qualquer um dos
dois ele **pula**, não falha. Usa só fixture sintética (nenhum arquivo
privado). Cobre um caminho: upload + schema sugerido; os caminhos de perfil
de domínio, schema YAML próprio e ambiguidade de aba seguem cobertos por
testes de componente e de API, não pelo navegador.

### D. Ainda NÃO testado

- **Perfil de domínio aplicado à planilha real**: os perfis existentes são de
  contatos/vendas-itens; o mapeamento foi exercitado por teste, não sobre o
  arquivo do proprietário.
- **Indicadores de vendas** (faturamento, ticket médio): **não existem** e não
  foram implementados. Só fariam sentido com o perfil e o mapeamento
  confirmando a semântica das colunas — no modo de análise geral, o
  AutoTarefas não sabe o que é "valor" nem "quantidade".
- **Navegador real nos caminhos de perfil, YAML próprio e duas abas.**

---

## Onde as 16 repetidas aparecem

| Artefato | Como aparece |
|---|---|
| Resumo na tela | bloco "16 linha(s) repetida(s) — 32 linha(s) envolvida(s)" + categoria `duplicado: 16` |
| `validacao_report.json` | 16 issues `severity: warning`, cada uma com `line` e `related_lines` (o par) |
| `pacote_execucao.zip → problemas.csv` | 16 linhas com `physical_line`, `related_lines` e a mensagem "Linha duplicada (identica a linha N)" |
| `pacote_execucao.zip → resumo.json` | `warnings: 16` e `warned_rows: 32` — a distinção explícita |
| `planilha_validada.xlsx` (aba Resumo) | "Duplicados: 16" na tabela de erros por categoria |
| `pacote_execucao.zip → registros_para_revisao.csv` | **as 32 linhas envolvidas**, em 16 grupos (`D01`…`D16`), com a linha canônica de cada um |
| `registros_invalidos.csv` | **vazio** — ele carrega só ERRO, e duplicidade é aviso |

**Severidade e os dois arquivos (decisão de produto, 14/08/2026).** Uma linha
100% repetida continua sendo **aviso**: ela não é inválida (o dado está
correto) e **não é removida**. Duas vendas idênticas do mesmo produto, no
mesmo dia, podem ser legítimas — quem decide é você. Por isso:

- `registros_invalidos.csv` continua contendo **somente erros**;
- `registros_para_revisao.csv` contém **erros e avisos que exigem decisão
  humana** — é lá que estão as 32 linhas;
- as linhas com aviso **também** seguem em `registros_validos.csv`.

**Os arquivos não são conjuntos exclusivos.** `registros_validos.csv` responde
"o que posso usar?"; `registros_para_revisao.csv` responde "o que preciso
olhar?". Somar as duas listas **não** dá o total de linhas.

Colunas de `registros_para_revisao.csv`: as colunas originais da sua planilha,
intactas, seguidas dos metadados `_linha`, `_severidade`, `_categoria`,
`_grupo_duplicidade`, `_linha_canonica`, `_linhas_relacionadas` e `_motivo`.
No `manifest.json`, `review_rows` conta só os erros e `review_file_rows` conta
o que foi de fato gravado no arquivo (na sua planilha: 0 e 32).

## Artefatos e equivalência de nomes

O contrato atual da CLI tem nomes canônicos, **preservados**. A interface usa
rótulos legíveis:

| Rótulo na tela | Arquivo | Observação |
|---|---|---|
| Planilha tratada (a sua, com as correções seguras) | `planilha_tratada.xlsx` | Só em XLSX **com** correções confirmadas |
| Registros válidos | `registros_validos.csv` | ≡ "dados limpos"; inclui linhas com aviso |
| Registros para revisão | `registros_invalidos.csv` | Linhas com **erro**. A fila completa (erros + avisos) está em `pacote_execucao.zip → registros_para_revisao.csv` |
| Relatório da validação (JSON) | `validacao_report.json` | ≡ "relatório da análise" |
| Relatório em planilha (resumo e registros) | `planilha_validada.xlsx` | Relatório profissional, 4 abas |
| O que foi preservado da planilha original | `preservacao_report.json` | |
| Pacote completo de evidências | `pacote_execucao.zip` | manifesto + hashes + `registros_para_revisao.csv` |

### Os dois XLSX não se confundem

- **`planilha_tratada.xlsx`** — cópia conservadora do **seu** arquivo, com
  somente as correções confirmadas e a apresentação original preservada.
- **`planilha_validada.xlsx`** — **relatório** da análise, em 4 abas:
  `Resumo` (contadores + erros por categoria), `Registros validos`,
  `Registros invalidos` (com o motivo) e `Auditoria` (antes/depois de cada
  normalização). Não é a sua planilha: é o laudo dela.

## O que foi corrigido nesta revisão

1. **Duplicatas não chegavam à validação.** O schema sugerido deixa
   `detect_duplicate_rows` comentado (o núcleo não inventa regra), então a
   execução dizia "Sem problemas encontrados" mesmo com 16 linhas repetidas.
   Agora a tela de revisão **oferece a sinalização quando a análise encontra
   repetidas**, já marcada, e a regra confirmada entra no `schema_efetivo.yaml`
   do pacote.
2. **Contador ambíguo.** O resultado agora diz "N repetidas — N×2 linhas
   envolvidas" e explica a diferença para chave repetida.
3. **Zero correções sem explicação.** Com as correções ligadas e nada a
   corrigir, a tela afirma "Nenhuma correção segura foi necessária".
4. **Vazamento de caminho interno.** `validacao_report.json` trazia o caminho
   completo do arquivo dentro do workspace do servidor. Agora guarda **só o
   nome** — vale também no modo real, onde relatórios circulam por e-mail.
5. **Nome do card** passou a ser "Análise e organização de planilhas".
6. **Fila de revisão vazia.** A tela oferecia "sinalizar as N linhas repetidas
   para revisão" e o `registros_para_revisao.csv` saía vazio, porque só
   carregava erros. Agora ele carrega **erros e avisos que exigem decisão
   humana**, com os metadados de contexto (grupo, linha canônica,
   relacionadas, motivo). A severidade **não** mudou: duplicidade continua
   sendo aviso e nenhuma linha é removida.
7. **Teste com navegador real** (Chromium) para a jornada — ver seção C.

## Limites conhecidos

- Gráficos e imagens não sobrevivem à regravação (openpyxl); **declarado** em
  `preservacao_report.json`.
- CSV não tem apresentação a preservar — não há planilha tratada nesse caso.
- Upload até 10 MB e execução até 60 s por padrão (`MAX_UPLOAD_MB`,
  `RUN_TIMEOUT_S`).
- Uma aba por execução.
- O teste de navegador real cobre **um** caminho (upload + schema sugerido);
  perfil de domínio, YAML próprio e duas abas seguem cobertos só por testes
  de componente e de API (seção D).
- A fila de revisão completa vive dentro do `pacote_execucao.zip`; a tela
  ainda não oferece esse CSV como download avulso.
