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
| **Homologação** | roteiro em [02-homologacao-manual.md](02-homologacao-manual.md); os 20 passos passam automatizados, com navegador real. A jornada de quem só chega e olha tem homologação própria: [02-vitrine-publica.md](02-vitrine-publica.md), 15 passos |
| **Problema** | A rotina manual que não é executada, o backup que nunca foi testado e a cópia mantida no mesmo disco |
| **Limitações** | Pendem de hardware, privilégio ou credencial do proprietário: disco externo físico, VSS com elevação, envio de e-mail (SMTP no cofre) e nuvem S3 com endpoint externo. O pacote do Agente exige Python 3.13 instalado — não há executável único nesta versão |
| **Próxima etapa** | credencial de um balde S3 real, para o ambiente público sair de "Proteção parcial"; depois, homologação final pelo proprietário |

### [02 — A vitrine pública](02-vitrine-publica.md)

O AutoTarefas publicado num portfólio: como a porta do visitante se abre, o que
o ambiente controlado tem dentro, o escopo da retenção por política, a entrega
diferida na nuvem, e a lista honesta do que ainda falta.

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
| 02.A | Segurança de caminhos e ressalvas visíveis | ✅ implementada |
| 02.B | Assinatura HMAC com chave externa | ✅ implementada |
| 02.C | Criptografia AES e gestão da senha | ✅ implementada |
| 02.D | VSS para arquivos abertos | ✅ implementada · **teste com elevação pendente** |
| 02.E | Agendamento, notificações e retenção | ✅ implementada · **envio de e-mail exige SMTP no cofre** |
| 02.F | Destinos externos e conector S3 | ✅ implementada · **nuvem real pendente** |
| 02.G | Agente local e interface operacional | ✅ implementada — trilha G inteira (G.0 a G.10.5), com a homologação de 20 passos em navegador real (G.9) |
| 02.H | Restauração guiada pela interface | ✅ implementada |
| 02.I | Backup incremental com catálogo | ✅ implementada |
| 02.J | Hooks e proteção antes de ação destrutiva | ✅ implementada |

**As três ressalvas acima são reais e continuam abertas**, e nenhuma delas é de
código faltando — as três dependem de algo que só existe fora do repositório:

- **02.D — VSS:** o instantâneo de volume está implementado, mas o teste com
  **elevação** exige privilégio administrativo numa máquina física;
- **02.E — notificação por e-mail:** o agendamento e a retenção funcionam; o
  **envio** espera credencial SMTP guardada no cofre;
- **02.F — destino na nuvem:** o conector S3 compatível está pronto e
  exercitado, mas a **entrega contra um balde real** depende de conta e
  credencial. Enquanto não houver, o painel mostra "proteção parcial", e isso é
  honestidade de estado, não defeito.
