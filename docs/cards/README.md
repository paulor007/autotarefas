# Cards do AutoTarefas

Um documento por card, com o **contrato funcional**: o problema que resolve, o
que promete, o que **não** promete, as evidências e o registro da homologação.

Três regras valem para todos:

- um card só é "pronto" com entrada real do usuário, configuração pela
  interface, execução real, saída útil, tratamento de erros, segurança, testes,
  documentação e homologação **pela interface**;
- limitações e o que não foi testado ficam escritos com o mesmo destaque do que
  funciona;
- baselines de homologação são históricos e não se reescrevem.

---

## Índice

### [01 — Análise e organização de planilhas](01-analise-organizacao-planilhas.md)

| | |
| --- | --- |
| **Status** | **HOMOLOGADO** |
| **Homologação** | 19/08/2026, por Paulo Lavarini |
| **Problema** | Planilha que ninguém confere: duplicidade invisível, estrutura ambígua, apresentação que atrapalha a leitura — e o medo de que "arrumar" estrague o arquivo |
| **Limitações** | Só dados tabulares (linhas e colunas); XLSX é o único formato completo — CSV, XLS e ODS são apenas analisados; não interpreta regra contábil, legal ou de domínio; limite de 10 MB por arquivo no envio; planilha protegida por senha, com macro ou acima de 100 mil linhas não foi testada |
| **Próxima etapa** | Nenhuma. Card encerrado; melhorias registradas na seção M.5 do documento |

### [02 — Backup automático verificável](02-backup-automatico-verificavel.md)

| | |
| --- | --- |
| **Status** | **IMPLEMENTADO, AGUARDANDO HOMOLOGAÇÃO FINAL** |
| **Homologação** | roteiro em [02-homologacao-manual.md](02-homologacao-manual.md); os 20 passos passam automatizados, com navegador real |
| **Problema** | A rotina manual que não é executada, o backup que nunca foi testado e a cópia mantida no mesmo disco |
| **Limitações** | Pendem de hardware, privilégio ou credencial do proprietário: disco externo físico, VSS com elevação, envio de e-mail (SMTP no cofre) e nuvem S3 com endpoint externo. O pacote do Agente exige Python 3.13 instalado — não há executável único nesta versão |
| **Próxima etapa** | homologação final pelo proprietário |

---

## Entrega do Card 02

O que foi feito, o que foi provado, o que **não** foi provado e o que depende do
proprietário está em **[02-entrega.md](02-entrega.md)**. O roteiro de conferência
manual está em **[02-homologacao-manual.md](02-homologacao-manual.md)**.

---

## Roadmap de execução do Card 02

A matriz consolidada de etapas, dependências, ordem de execução e a decisão de
identidade (OIDC) estão em
**[02-roadmap-execucao.md](02-roadmap-execucao.md)**.

## Estado das subetapas do Card 02

Detalhamento, dependências e critérios de aceite na seção 21 do documento do
card. Resumo:

| Subetapa | Finalidade | Estado |
| --- | --- | --- |
| 02.A | Segurança de caminhos e ressalvas visíveis | implementada, **não homologada** |
| 02.B | Assinatura HMAC com chave externa | não iniciada |
| 02.C | Criptografia AES e gestão da senha | não iniciada |
| 02.D | VSS para arquivos abertos | não iniciada |
| 02.E | Agendamento, notificações e retenção | não iniciada |
| 02.F | Destinos externos e conector S3 | não iniciada |
| 02.G | Agente local e interface operacional | **G.0 concluída**; **G.1 implementada, aguardando homologação** (+ G.1.1); G.2–G.8 não iniciadas |
| 02.H | Restauração guiada pela interface | não iniciada |
| 02.I | Backup incremental com catálogo | não iniciada |
| 02.J | Hooks e proteção antes de ação destrutiva | não iniciada |
