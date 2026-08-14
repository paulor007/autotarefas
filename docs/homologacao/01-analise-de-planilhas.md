# Homologação 01 — Análise e organização de planilhas

**Status: AGUARDANDO HOMOLOGAÇÃO DO USUÁRIO**
Card no Live: *Análise e validação de planilhas* (mesmo card; o catálogo usa
"validação" no título).

Esta é a primeira jornada preparada para teste humano com planilha real. Os
testes automatizados **não** encerram este item: o card só passa a CONCLUÍDO
depois que o proprietário rodar o fluxo no navegador e aprovar.

---

## Como subir o sistema

Dois terminais, a partir da raiz do repositório:

```bash
venv\Scripts\python.exe -m uvicorn live_demo.backend.app.main:app --port 7860
```

```bash
npm --prefix live_demo/frontend run dev
```

Abrir no navegador: **http://localhost:5173**

Conferência rápida de saúde: <http://localhost:7860/api/health>.

## Roteiro do teste

1. Na seção **Soluções disponíveis**, clicar em **Selecionar** no card
   *Análise e validação de planilhas*.
2. Escolher a origem:
   - **Testar com exemplo** — usa `clientes.csv`, do próprio servidor; ou
   - arrastar/selecionar o seu arquivo e clicar em **Analisar meus dados**
     (é aqui que entra o `Vendas - Dez (2).xlsx`).
3. Conferir o **Diagnóstico do arquivo**: nome, aba, linha do cabeçalho,
   confiança, linhas, colunas, tipos observados, observações e prévia.
4. **Escolher como validar**:
   - *schema sugerido* — análise geral, só a estrutura observada;
   - *perfil pronto* — regras de domínio (ex.: CPF/e-mail), com você indicando
     qual coluna corresponde a cada campo;
   - *meu schema YAML* — as regras do seu processo.
5. **Revisar configuração** e decidir sobre **Aplicar as correções seguras**
   (começa desligado).
6. **Executar validação** e acompanhar a saída real (SSE).
7. Conferir o resumo e **baixar os artefatos**.

## O que observar

- [ ] A aba e a linha de cabeçalho detectadas correspondem à sua planilha.
- [ ] Nenhuma coluna de CPF, e-mail ou telefone é exigida numa planilha de
      vendas: com o schema sugerido, as regras saem da estrutura observada.
- [ ] Zeros à esquerda continuam íntegros na prévia e nos artefatos.
- [ ] Com as correções **desligadas**, o contador *Normalizados* fica em 0 e
      nenhum valor muda.
- [ ] Com as correções **ligadas**, cada valor alterado aparece no antes/depois
      (aba *Auditoria* de `planilha_validada.xlsx`).
- [ ] Em XLSX com correções ligadas, aparece a **Planilha tratada**: abra e
      confira cores, larguras, painel congelado, filtros e formatos — devem
      estar como no seu arquivo.
- [ ] O arquivo que você enviou continua intacto no seu computador.
- [ ] Ambiguidade (várias abas candidatas) vira **pergunta**, não decisão
      automática.
- [ ] Mensagens de erro são compreensíveis, sem traceback nem caminho interno.

## Artefatos e equivalência de nomes

O contrato atual da CLI já tem nomes canônicos, e eles foram **preservados**.
A equivalência com a lista pedida:

| Pedido na homologação        | Artefato real do AutoTarefas       | Observação |
|---|---|---|
| `planilha_tratada.xlsx`      | `planilha_tratada.xlsx`            | Só em XLSX **com** correções confirmadas |
| `dados_limpos.csv`           | `registros_validos.csv`            | Registros que seguem para o próximo passo |
| `registros_para_revisao.csv` | `registros_invalidos.csv`          | Rotulado na tela como "Registros para revisão"; o pacote de evidências traz também `registros_para_revisao.csv` |
| `auditoria_report.json`      | `validacao_report.json`            | Resumo, contadores e problemas por categoria |

Extras da execução: `preservacao_report.json` (o que pôde ou não ser
preservado do original), `planilha_validada.xlsx` (relatório em 4 abas),
`schema_sugerido.yaml` e `pacote_execucao.zip` (manifesto + hashes).

## O que foi corrigido para esta homologação

A jornada rodava sempre em `--mode auditoria`: apontava problemas, mas **nunca
aplicava correção nem gerava a planilha tratada**. Agora a etapa de revisão
pede a confirmação explícita e, com ela, a execução roda em `--mode limpeza` —
que normaliza o que é seguro e, em XLSX, entrega a planilha tratada preservando
a apresentação original (RF-PLA-009).

## Limites conhecidos desta fatia

- Gráficos e imagens não sobrevivem à regravação do arquivo (limitação do
  openpyxl); isso é **declarado** em `preservacao_report.json`.
- CSV não tem apresentação para preservar — não existe planilha tratada nesse
  caso, e a tela avisa antes de executar.
- Upload limitado a 10 MB e execução a 60 s por padrão (variáveis
  `MAX_UPLOAD_MB` e `RUN_TIMEOUT_S`).
- Uma aba por execução: para conferir outra aba, rode a jornada de novo.
