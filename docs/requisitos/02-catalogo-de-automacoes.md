# 02 — Catálogo de Automações

Inventário do que o usuário vê e executa, nos dois modos. Fonte de verdade dos
cards: `apps/api/app/catalog.py` (13 automações, 7 categorias) e
`apps/api/app/engine.py::ACTIVE_AUTOMATIONS` (régua do que roda ao
vivo). Fonte de verdade do modo real: `src/autotarefas/cli/main.py` (13 comandos).

## 1. Cards do Live System

| ID do card | Título público | Categoria | Live | Comando real equivalente | RFs |
|---|---|---|---|---|---|
| `validate` | Análise e validação de planilhas (jornada guiada) | Validação & Qualidade | **ATIVO** | `autotarefas analisar` + `autotarefas validate` | PLA-001..008, LIVE-004 |
| `backup` | Backup compactado | Backup & Organização | **ATIVO** | `autotarefas backup` | ARQ-001 |
| `organize` | Organizar por tipo | Backup & Organização | **ATIVO** | `autotarefas organize` | ARQ-003 |
| `send_api` | Cadastro automático via planilha | Integração de API | **ATIVO** | `autotarefas send api` | INT-002, **INT-005** (mapeamento — obrigatório V1) |
| `extract_api` | Exportação automática de dados | Integração de API | **ATIVO** | `autotarefas extract api` | INT-001 |
| `sync_api` | Sincronizar API | Integração de API | em breve | `autotarefas sync api` | INT-003, LIVE-006 |
| `send_email` | Disparar e-mails | Notificações | em breve | `autotarefas send email` | COM-001, LIVE-006 |
| `send_telegram` | Mensagens no Telegram | Notificações | **ATIVO** | `autotarefas send telegram` | COM-002 |
| `extract_web` | Scraping de catálogo | Web Scraping | **ATIVO** | `autotarefas extract web` | WEB-001 |
| `extract_web_js` | Scraping com JavaScript | Web Scraping | em breve | `autotarefas extract web --js` | WEB-002, LIVE-006 |
| `rpa_cadastro` | RPA de cadastro | RPA (Navegador) | em breve | `autotarefas rpa cadastro` | WEB-003, LIVE-006 |
| `report` | Relatório de auditoria | Auditoria | em breve | `autotarefas report` | GOV-001, LIVE-006 |
| `dashboard` | Painel de auditoria | Auditoria | em breve | `autotarefas dashboard` | GOV-002, LIVE-006 |

Mecânica da régua: o front separa ativos de "em breve" pelas
`health.active_automations` (`apps/web/src/App.tsx` +
`components/Catalog.tsx`); o backend recusa fora da régua com **HTTP 501** em
`main.py::_precheck`. A receita de execução (`recipes.py::build_argv`) cobre
exatamente os 7 ativos — os demais nem possuem argv definido (KeyError). O estado
`oculto` previsto na régua de design (`ativo | em_breve | oculto`) **não está
implementado** — hoje só existem os dois primeiros.

**Situação aprovada para a V1 (DP-02, 10/08/2026).** Os cards de navegador
`extract_web_js` e `rpa_cadastro` **não** são publicados como executáveis no Live
da V1: a promessa de execução pública sai da vitrine e o funcionamento passa a ser
demonstrado por vídeo/GIF. A implementação real permanece no Core e no CLI
(RF-WEB-002 e RF-WEB-003 seguem obrigatórios da V1 no modo real, com e2e na
homologação) e nenhum código ou teste existente é removido. A execução pública com
Chromium volta a ser avaliada na Fase D, depois da definição da hospedagem. Os 4
cards restantes hoje "em breve" (`sync_api`, `send_email`, `report`, `dashboard`)
são de ativação barata e entram como RECOMENDADO V1 (LIVE-006a, Fase A3). O ajuste
da vitrine em si é a subetapa A4 do roadmap.

**Fluxo de importação (V1).** O card `send_api` passa a exigir, além do envio
idempotente já entregue (INT-002), o **mapeamento configurável de colunas para os
campos do sistema** (INT-005): de/para por CLI ou arquivo simples, validação dos
campos obrigatórios do destino, prévia do payload e dry-run sem gravação externa.
No Live, o mapeamento continua fixo pelo servidor (o visitante nunca informa
caminho, comando ou credencial).

Exemplos com 1 clique (`samples.py`): `validate` (clientes.csv), `backup` e
`organize` (pasta "bagunca"), `send_api` (leads.csv). Reset automático de estado
entre execuções: apenas `send_api` (`recipes.py::reset_url` → `POST /limpar` no
mock).

## 2. Jornada guiada de planilhas (card `validate`)

Endpoints reais (`apps/api/app/spreadsheets.py`):

```
GET  /api/spreadsheets/profiles            perfis embutidos (público)
GET  /api/spreadsheets/profiles/{id}       detalhe do perfil
POST /api/spreadsheets/analyze             upload OU exemplo → diagnóstico
POST /api/spreadsheets/{token}/selection   aba / linha de cabeçalho
POST /api/spreadsheets/{token}/schema      sugerido | perfil | YAML próprio (≤256 KB)
POST /api/spreadsheets/{token}/validate    executa e gera evidências
```

O token é o mesmo do fluxo clássico, então `stream/result/download` continuam
valendo. O upload nunca é baixável; o schema confirmado fica em `config/` (fora
de `out/`) e o que executou aparece como `schema_efetivo.yaml` dentro do pacote.

## 3. Comandos do modo real (CLI)

Saída real de `python -m autotarefas --help` (evidência da auditoria):
`analisar`, `backup`, `dashboard`, `extract` (`api`, `web`), `info`, `init`,
`organize`, `perfis` (`listar`, `ver`, `exportar`), `report`, `rpa` (`cadastro`),
`send` (`api`, `email`, `telegram`), `sync` (`api`), `validate`. Flags globais:
`--version`, `-v/-q`, `--dry-run`, `-y/--yes`.

Opções que definem o produto:

- `validate`: `--schema`, `--mode auditoria|limpeza`, `--sheet`, `--header-row`,
  `--strict-warnings`, `--max-issues`, `--report-json`, `--report-csv`,
  `--out-dir`, `--artefatos` (pacote de evidências).
- `analisar`: `--json`, `--out-dir`, `--preview`, `--schema-sugerido`, `--sheet`,
  `--header-row`, `--strict-warnings`.

## 4. Sistemas de demonstração internos

`tools/demo_server/` (Flask, porta 5555 por padrão) — alvo das automações em
desenvolvimento e no Live: formulário `/cadastro` (RPA), `/api/clientes` paginada
com 409 para CPF duplicado e `Retry-After` na cota, `/api/catalogo` com 47
produtos determinísticos, `/catalogo` HTML paginado, `/catalogo-js` renderizado
por JavaScript, mock do Telegram (`/bot<token>/sendMessage`, caixa de entrada e
`/telegram/limpar`), `/limpar` e `/seed`. SMTP de depuração: `tools/smtp_debug.py`.
No Live, o ciclo de vida dos mocks é gerenciado por
`apps/api/app/demo_servers.py` (autostart configurável).

## 5. Renomeações públicas planejadas (IDs preservados)

Decisão de produto anterior, ainda não aplicada ao catálogo: `validate` →
"Analisar" já refletido no título da jornada; `send_api` → "Importação para
sistemas" (que na V1 inclui o mapeamento configurável de colunas — INT-005);
`extract_api` → "Exportação de sistemas". Os títulos atuais do
`catalog.py` ("Cadastro automático via planilha", "Exportação automática de
dados") já comunicam o benefício; a unificação final de nomenclatura entra na
Fase A do roadmap (06) como ajuste de texto, sem troca de ID.
