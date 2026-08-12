# 10 — Glossário

**Artefato** — arquivo gerado por uma execução para consumo do usuário
(relatórios, CSVs separados, planilha validada, pacote de evidências, ZIP).

**Audit trail (trilha de auditoria)** — banco SQLite append-only onde toda
execução de task registra timestamp, status, duração e o HMAC do input
(`core/audit.py`).

**BaseTask / TaskResult / TaskStatus** — contrato de toda automação: classe
base, resultado tipado e status `SUCCESS/PARTIAL/FAILURE` (`core/base.py`).

**Card** — entrada do catálogo do Live System (13 no total), com título público,
categoria e regras de upload/saída (`live_demo/backend/app/catalog.py`).

**Dry-run** — simulação fiel sem efeito colateral; flag global `--dry-run`.

**Egress lockdown** — bloqueio de saída de rede do subprocesso no Live via proxy
inválido, liberando apenas `127.0.0.1/localhost` (`engine.py`).

**Idempotency-Key** — cabeçalho determinístico por linha no envio via API; a
mesma linha gera sempre a mesma chave, em toda tentativa e reenvio, para o
sistema de destino não duplicar (`send_api.py`).

**Issue** — problema de validação acumulado (nunca exceção que para na
primeira), com linha, coluna, severidade ERROR/WARNING e categoria
(`tasks/issues.py`).

**Jornada guiada** — fluxo em etapas do card de planilhas no Live:
analisar → selecionar aba/cabeçalho → escolher schema → validar
(`spreadsheets.py`).

**Limpeza (modo)** — normalização segura com trilha antes/depois; jamais
"conserta" valor inválido (`tasks/cleaning.py`).

**Live System** — vitrine pública em `live_demo/` (FastAPI + React) que executa
o produto real em sandbox contra mocks internos. Não confundir com o
**dashboard**, que é o painel HTML estático do audit (`src/autotarefas/dashboard/`).

**Mock interno** — sistema de demonstração determinístico
(`tools/demo_server/`): CRM com API paginada, catálogo HTML/JS, bot Telegram
falso, SMTP de depuração.

**Pacote de evidências** — diretório/ZIP com `manifest.json` (hashes), resumo,
problemas, registros separados e `schema_efetivo.yaml`
(`tasks/execution_package.py`; flag `--artefatos`).

**Perfil** — conjunto de regras de validação pronto, embutido no pacote, que o
usuário exporta remapeando campos conceituais para as colunas reais
(`profiles/`).

**Receita (Live)** — mapeamento servidor-side de um card para o argv real da
CLI, via allowlist (`recipes.py::build_argv`). **Receita (do usuário)** — alvo
de RF-CORE-006: YAML nomeado com tarefa+parâmetros para reuso.

**Reconciliação** — comparar bases por chave, aplicar tolerâncias e decidir o
valor válido, com evidências (módulo REC — a construir).

**Régua (status do card)** — `ativo | em breve` hoje
(`engine.ACTIVE_AUTOMATIONS` + HTTP 501 fora dela); o estado `oculto` está
previsto em design e não implementado.

**Schema** — YAML declarativo de validação (colunas, tipos, validadores,
`group_checks`, `derived_checks` com expressões `[Coluna]`).

**Veredito de ambiguidade** — decisão explícita do serviço de análise sobre a
confiança da detecção de aba/cabeçalho; abaixo do limiar, o produto pergunta em
vez de escolher (`services/analysis.py`).

**Workspace** — diretório UUID isolado de uma execução no Live, com
`AUTOTAREFAS_HOME` próprio, TTL de 15 min e saída pública restrita a `out/`.

**Siglas de status/prioridade** — ver 00 §2 e 03 (cabeçalho). **DP-xx** —
decisão pendente registrada em 08. **RF-/RNF-** — requisito funcional / não
funcional.
