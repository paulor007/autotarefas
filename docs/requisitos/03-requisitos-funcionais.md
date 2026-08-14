# 03 — Requisitos Funcionais (fichas completas)

Modelo de ficha (28 campos): ID · Nome · Objetivo · Problema resolvido · Usuário
· Descrição detalhada · Pré-condições · Entradas · Fluxo principal · Fluxos
alternativos · Saídas · Artefatos · Critérios de avaliação · Critérios de aceite
· Regras de negócio · Requisitos adicionais · Dependências · Segurança e
privacidade · Tratamento de falhas · Recuperação · Modo Live · Modo real ·
Testes necessários · Prioridade · Fase · Status · Evidências · Lacunas · Próxima
ação.

Convenções: **Prioridade** usa OBRIGATÓRIO V1 / RECOMENDADO V1 / PÓS-V1 / FORA DE
ESCOPO — **aprovada em 10/08/2026 pela DP-01** (41 obrigatórios; lista em 00 §3.1;
registro em `08` §4). Prioridade aprovada não altera status: requisito só passa a
CONCLUÍDO com código, testes, critérios de aceite cumpridos e evidência na
matriz. **Fase** referencia o roadmap (06).
**Evidências** citam somente caminhos reais deste snapshot e execuções desta
auditoria (00 §4). Campos idênticos ao padrão do módulo são marcados "padrão do
módulo" para não repetir texto.

---

## Módulo CORE — Fundação transversal

### RF-CORE-001 — Fundação de tasks
**Objetivo:** toda automação com interface, timing, status e erros padronizados.
**Problema resolvido:** comportamento imprevisível entre automações.
**Usuário:** desenvolvedor/mantenedor (interno).
**Descrição detalhada:** `BaseTask` abstrata + `TaskResult` (dados, `rows_affected`, duração) + `TaskStatus` (`SUCCESS/PARTIAL/FAILURE`); captura padronizada de exceções; integração automática com audit e logger.
**Pré-condições:** —. **Entradas:** parâmetros tipados da subclasse. **Fluxo principal:** instanciar → `run()` → resultado tipado. **Fluxos alternativos:** exceção → `FAILURE` com mensagem estruturada, sem stacktrace cru para o usuário.
**Saídas:** `TaskResult`. **Artefatos:** registro no audit.
**Critérios de avaliação:** nenhuma task no repositório fora do padrão.
**Critérios de aceite:** subclasse mínima herda timing+audit sem código extra; status agregado reflete falhas parciais.
**Regras de negócio:** dry-run jamais altera estado.
**Requisitos adicionais:** —. **Dependências:** loguru, pydantic.
**Segurança e privacidade:** resultado nunca inclui segredos.
**Tratamento de falhas:** exceção → resultado `FAILURE`. **Recuperação:** N/A.
**Modo Live:** indireto (todas as execuções). **Modo real:** base de tudo.
**Testes necessários:** unitários de contrato.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/core/base.py` (379 linhas); `tests/core/test_base.py`, `tests/core/test_base_audit.py`; suíte do núcleo **2052 passed** na árvore local (00 §4.1; 2023 no snapshot de 05/08).
**Lacunas:** —. **Próxima ação:** manter.

### RF-CORE-002 — Trilha de auditoria append-only
**Objetivo:** provar o que rodou, quando, sobre o quê e com que resultado.
**Problema resolvido:** falta de evidência de execução.
**Usuário:** operador e quem audita.
**Descrição detalhada:** SQLite local append-only; cada execução grava timestamp, task, usuário, status, duração e agregados; input identificado por HMAC-SHA256 (nunca conteúdo sensível).
**Pré-condições:** `AUTOTAREFAS_HOME` gravável (criado por `init`). **Entradas:** metadados da execução. **Fluxo principal:** task conclui → `audit.record(...)`. **Fluxos alternativos:** audit indisponível → execução não silencia erro de gravação.
**Saídas:** linhas no banco. **Artefatos:** `audit.db` sob o home.
**Critérios de avaliação:** nenhuma execução de task sem linha correspondente.
**Critérios de aceite:** consultas por período/status; hash confere via verificação (RF-GOV-004).
**Regras de negócio:** append-only — sem UPDATE/DELETE no caminho de produto.
**Requisitos adicionais:** segredo do HMAC via settings (`audit_secret_key`).
**Dependências:** sqlite3, cryptography. **Segurança e privacidade:** só hash do input.
**Tratamento de falhas:** erro de I/O reportado. **Recuperação:** banco recriável por `init` (histórico novo).
**Modo Live:** cada workspace tem home próprio → trilha da execução demonstrada. **Modo real:** trilha do usuário.
**Testes necessários:** gravação, consulta, imutabilidade.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/core/audit.py`; `tests/core/test_audit.py`.
**Lacunas:** retenção/expurgo tratados em RF-GOV-003. **Próxima ação:** manter.

### RF-CORE-003 — Segurança transversal
**Objetivo:** primitivas únicas contra os erros clássicos (path traversal, URL insegura, vazamento em log).
**Problema resolvido:** cada task reinventar (mal) segurança.
**Usuário:** interno.
**Descrição detalhada:** `safe_path()` (allowlist), `is_within_directory()`, `validate_filename()`, `safe_extension()`, `validate_url()` (HTTPS em prod), `hash_string()` (HMAC/SHA-256), `mask_sensitive_in_dict()`.
**Pré/Entradas/Fluxos:** funções puras chamadas pelas tasks. **Saídas:** valores validados ou exceção clara. **Artefatos:** —.
**Critérios de avaliação:** nenhum caminho/URL de entrada usado sem passar por aqui.
**Critérios de aceite:** casos maliciosos dos testes rejeitados (`..`, barra, extensão fora da lista).
**Regras de negócio:** negar por padrão. **Requisitos adicionais:** —.
**Dependências:** stdlib, cryptography. **Segurança e privacidade:** é o próprio requisito.
**Tratamento de falhas:** exceções específicas (`core/exceptions.py`). **Recuperação:** N/A.
**Modo Live:** usado por uploads/downloads. **Modo real:** idem.
**Testes:** `tests/core/test_security.py`. **Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/core/security.py` (406 linhas) + testes citados.
**Lacunas:** —. **Próxima ação:** manter.

### RF-CORE-004 — Configuração por ambiente
**Objetivo:** todo parâmetro operacional e segredo fora do código.
**Problema resolvido:** credencial hardcoded e configuração espalhada.
**Usuário:** operador do modo real.
**Descrição detalhada:** `Settings` (pydantic-settings) lendo `.env`: ambiente (`dev/demo/homolog/prod`), `autotarefas_home`, log level, SMTP (`email_*`, senha `SecretStr`), sistema demo, RPA (`rpa_default_timeout`, `rpa_max_retries`, `rpa_headless`), audit (`audit_secret_key`), screenshots (`screenshot_retention_days`, `screenshots_mask_sensitive`), limites (`max_file_size_mb`, `max_records_per_run`).
**Pré-condições:** —. **Entradas:** `.env`/variáveis. **Fluxo principal:** import lê e valida com faixas (`ge/le`). **Alternativos:** valor inválido → erro de validação na inicialização.
**Saídas:** objeto settings tipado. **Artefatos:** —.
**Critérios de avaliação:** nenhum segredo em código; faixas impedem valores absurdos.
**Critérios de aceite:** `SecretStr` nunca aparece em `repr`/log.
**Regras de negócio:** defaults seguros para rodar sem configurar.
**Requisitos adicionais:** `.env.example` completo e comentado.
**Dependências:** pydantic-settings. **Segurança e privacidade:** `SecretStr`.
**Falhas/Recuperação:** mensagens de validação.
**Modo Live:** config própria em `live_demo/backend/app/config.py` (env `PORT`, limites etc.). **Modo real:** este requisito.
**Testes:** `tests/core/test_settings.py`. **Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/core/settings.py`; teste citado.
**Lacunas:** **`.env.example` está vazio** (0 bytes) — não documenta as variáveis que `settings.py` consome. **Próxima ação:** preencher `.env.example` na Fase A (A2), sem mudar código.

### RF-CORE-005 — CLI unificada
**Objetivo:** um binário, ergonomia única.
**Problema resolvido:** cada automação com interface própria.
**Usuário:** operador técnico.
**Descrição detalhada:** grupo `autotarefas` (click) com 13 comandos; flags globais `-v/-q` (verbosidade acumulável), `--dry-run`, `-y/--yes`, `--version`; console rich; contexto compartilhado (`cli/context.py`); helpers de confirmação.
**Pré/Entradas:** argv. **Fluxo principal:** parse → task → saída formatada + exit code. **Alternativos:** erro de uso → mensagem amigável (não traceback).
**Saídas:** stdout/rich + exit codes. **Artefatos:** os das tasks.
**Critérios de avaliação:** `--help` completo em todos os níveis (evidência colhida).
**Critérios de aceite:** `--dry-run` global propaga; `--yes` suprime prompts; exit code ≠ 0 em falha.
**Regras de negócio:** destrutivo sem `--yes` pergunta ou simula.
**Requisitos adicionais:** registro simples de novos comandos (`cli.add_command`).
**Dependências:** click, rich. **Segurança:** não ecoa segredos.
**Falhas/Recuperação:** padrão do módulo.
**Modo Live:** o Live executa exatamente esta CLI por subprocesso. **Modo real:** interface principal.
**Testes:** `tests/cli/` (19 arquivos, 379 funções de teste).
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/cli/main.py` + `commands/`; saída real do `--help` (00 §4/02 §3).
**Lacunas:** —. **Próxima ação:** manter.

### RF-CORE-006 — Reutilização de configurações
**Objetivo:** configurar uma vez, reutilizar sempre.
**Problema resolvido:** repetir schema/mapeamento/parâmetros a cada execução.
**Usuário:** operador recorrente.
**Descrição detalhada (estado + alvo):** hoje o reuso existe por **arquivos YAML** (schemas do validate, regras do organize) e **perfis embutidos** exportáveis com remapeamento (RF-PLA-004). O alvo do requisito completo é a **receita nomeada**: um YAML do usuário descrevendo tarefa + parâmetros (+ futuramente encadeamento), executável por nome.
**Pré-condições:** —. **Entradas:** YAML do usuário. **Fluxo principal (alvo):** `autotarefas run minha-receita.yaml` → parâmetros aplicados → execução normal. **Alternativos:** receita inválida → erros de validação campo a campo.
**Saídas:** as da task subjacente. **Artefatos:** idem + receita versionável pelo usuário.
**Critérios de avaliação:** repetir uma operação típica sem redigitar nenhum parâmetro.
**Critérios de aceite (alvo):** receita cobre validate/organize/backup/extract/send; segredos jamais na receita (somente nomes de variáveis, padrão `*_env`).
**Regras de negócio:** receita não pode embutir credencial.
**Requisitos adicionais:** precedência CLI > receita > default, documentada.
**Dependências:** PyYAML, pydantic. **Segurança:** validação estrita, sem execução de código.
**Falhas/Recuperação:** padrão. **Modo Live:** N/A (parâmetros são do servidor). **Modo real:** principal beneficiário.
**Testes necessários:** parsing, precedência, recusa de segredo embutido.
**Recorte V1 (revisão 2, 05/08/2026):** obrigatória a *configuração reutilizável do fluxo de planilhas* — um YAML que descreve a operação completa (leitura/seleção, validação, tratamento autorizado, reconciliação, apresentação), executável por `autotarefas run fluxo.yaml`; internamente multi-etapas, externamente uma operação; primeiro consumidor: REC-004. O encadeamento genérico de tasks arbitrárias (envios, extrações, condicionais) fica FORA da V1 — é orquestração, não requisito do resultado operacional (justificativa: nenhuma etapa da seção 9.1 do doc 01 depende dele; complexidade ALTA sem valor novo para o fluxo).
**Prioridade:** OBRIGATÓRIO V1 no recorte acima — **recorte aprovado em 10/08/2026 (DP-01(d))**: configuração reutilizável do fluxo de planilhas, execução por `autotarefas run fluxo.yaml`, validação da configuração, precedência CLI > configuração > padrão e proibição de segredos embutidos; encadeamento genérico de tarefas arbitrárias permanece PÓS-V1. **Fase:** B6. **Status:** PARCIAL.
**Evidências (parte existente):** `src/autotarefas/profiles/` + `tests/profiles/`; schemas/regras YAML por toda a suíte.
**Lacunas:** não existe `run <fluxo.yaml>`; formato da configuração de fluxo não definido.
**Próxima ação:** especificar o formato na Fase B6, junto de REC-004.

### RF-CORE-007 — Sugestões automáticas de próximos passos
**Objetivo:** o produto propor, com base no resultado, o próximo passo útil.
**Problema resolvido:** usuário não saber o que fazer com o diagnóstico.
**Usuário:** operador e visitante do Live.
**Descrição detalhada (alvo):** motor **determinístico e explicável** de regras `condição → sugestão`, exibido junto ao resultado. Cada sugestão informa: por que foi sugerida, problema que resolve, ação executada, dados usados, risco, se exige confirmação e saída gerada. Regras iniciais: duplicidades → revisar/limpar; execução repetida → sugerir receita (quando existir) ; falhas parciais → reenviar só os falhos; arquivo sem backup antes de operação destrutiva → sugerir backup; divergências → gerar planilha de revisão.
**Pré-condições:** resultado estruturado da task. **Entradas:** `TaskResult`/relatórios. **Fluxo:** avaliar regras → listar sugestões → usuário aceita (nunca execução automática destrutiva).
**Saídas:** bloco "Próximos passos" (CLI e Live). **Artefatos:** sugestões registradas no relatório JSON.
**Critérios de avaliação:** zero falso-positivo nas regras iniciais (condições objetivas).
**Critérios de aceite:** cada sugestão com os 7 campos de transparência; nenhuma ação externa/destrutiva sem confirmação.
**Regras de negócio:** determinístico antes de qualquer IA (decisão do produto).
**Dependências:** nenhuma nova. **Segurança:** sugestão nunca vaza dado sensível.
**Falhas/Recuperação:** ausência de sugestão é estado válido.
**Modo Live:** semente já existente — o front oferece o CTA Auditoria→Cadastro após validar (`useSpreadsheetJourney`/`ValidationSummary`). **Modo real:** bloco no resumo do CLI.
**Testes:** uma suíte por regra (dispara/não dispara).
**Prioridade:** PÓS-V1. **Fase:** D1. **Status:** NÃO INICIADO (semente de UI no Live).
**Evidências da semente:** `live_demo/frontend/src/components/ValidationSummary.tsx` + hooks.
**Lacunas:** motor de regras inexistente. **Próxima ação:** especificar as 5 regras iniciais na Fase D1.

### RF-CORE-008 — Agendamento, gatilhos e encadeamento
**Objetivo:** execução recorrente e por evento (horário, chegada de arquivo), com pausa/cancelamento/retomada e aprovação humana em etapas críticas.
**Problema resolvido:** depender de alguém lembrar de rodar.
**Usuário:** operador recorrente.
**Descrição detalhada (alvo):** fase 1 = integração documentada com agendadores do SO (Task Scheduler/cron) usando receitas + exit codes; fase 2 = `autotarefas watch <pasta> --receita ...` (gatilho por arquivo); encadeamento entra pelas receitas (CORE-006). Monitoramento pelo audit + notificação de conclusão/falha (reusa COM).
**Critérios de aceite (fase 1):** guia testado de agendamento no Windows e Linux; execução agendada aparece no audit com origem.
**Regras de negócio:** etapa crítica pode exigir aprovação (pausa até confirmação).
**Prioridade:** PÓS-V1. **Fase:** D4. **Status:** NÃO INICIADO.
**Demais campos:** padrão do módulo; sem evidências (não há código).
**Próxima ação:** nenhum trabalho antes da Fase D.

---

## Módulo ARQ — Arquivos e pastas

### RF-ARQ-001 — Backup compactado com integridade
**Objetivo:** proteger arquivos antes de qualquer alteração.
**Problema resolvido:** perda de dados por operação subsequente.
**Usuário:** qualquer operador; visitante do Live.
**Descrição detalhada:** ZIP (deflate) de múltiplas fontes (arquivos e pastas), excludes por fnmatch com padrões default sensatos (`__pycache__`, `.git`, `node_modules`...), hash SHA-256 do pacote, dry-run listando o que entraria, contagem de arquivos e bytes no resultado, trilha no audit.
**Pré-condições:** fontes legíveis; destino gravável. **Entradas:** `sources`, `destination`, `exclude_patterns`. **Fluxo principal:** varrer → filtrar → compactar → hash → resultado. **Alternativos:** dry-run (nada criado); fonte inexistente → falha clara.
**Saídas:** `TaskResult` com `file_count`, tamanho, hash. **Artefatos:** `backup.zip`.
**Critérios de avaliação:** hash publicado confere com o arquivo.
**Critérios de aceite:** excludes aplicados; dry-run e execução real listam o mesmo conjunto.
**Regras de negócio:** original intocado.
**Requisitos adicionais:** —. **Dependências:** stdlib.
**Segurança:** caminhos validados. **Falhas:** por fonte, mensagem específica. **Recuperação:** reexecutável.
**Modo Live:** card ATIVO (upload ou exemplo "bagunca"; saída `out/backup.zip`). **Modo real:** `autotarefas backup SRC... -o destino.zip`.
**Testes:** `tests/tasks/test_backup.py`, `tests/cli/test_backup_cli.py`.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/tasks/backup.py` (344 linhas); receita Live `recipes.py` ramo `backup`.
**Lacunas:** ver ARQ-002/005. **Próxima ação:** manter.

### RF-ARQ-002 — Manifesto, validação e restauração de backup
**Objetivo:** backup que se prova completo e volta quando precisa.
**Problema resolvido:** ZIP existir mas ninguém saber o que tem dentro nem conseguir restaurar com segurança.
**Usuário:** operador.
**Descrição detalhada (alvo):** `manifest.json` dentro do ZIP (lista de arquivos, tamanhos, hashes individuais, origem, data, versão da ferramenta); `backup verificar <zip>` confere manifesto × conteúdo; `backup restaurar <zip> -d destino` com dry-run, tratamento de colisão (skip/rename/overwrite, padrão seguro) e relatório do restaurado.
**Entradas:** ZIP gerado por ARQ-001. **Fluxo principal:** ler manifesto → validar → extrair com política de colisão → relatório. **Alternativos:** manifesto ausente (ZIP antigo) → validação só global pelo hash externo, restauração ainda possível com aviso.
**Saídas/Artefatos:** relatório de verificação/restauração (JSON + resumo).
**Critérios de aceite:** restaurar sobre pasta com colisões não sobrescreve por padrão; verificação detecta arquivo corrompido injetado no teste.
**Regras de negócio:** restauração é a única operação que grava fora de `out/` no modo real — sempre com confirmação.
**Prioridade:** PÓS-V1. **Fase:** D2. **Status:** NÃO INICIADO.
**Demais campos:** padrão do módulo. **Próxima ação:** aguardar Fase D.

### RF-ARQ-003 — Organização por regras declarativas
**Objetivo:** pasta bagunçada → estrutura previsível, sem sustos.
**Problema resolvido:** organizar arquivos à mão.
**Usuário:** operador; visitante do Live.
**Descrição detalhada:** regras YAML (pydantic) com padrões de nome/extensão; destino com variáveis `{year}`, `{month:02d}`, `{day}`, `{ext}`; ação `move` ou `copy`; conflito `skip` (default) / `rename` / `overwrite`; primeira regra que casa vence; **não recursivo** (só arquivos diretos do source); dry-run lista cada operação; audit detalha arquivo a arquivo.
**Pré-condições:** YAML válido. **Entradas:** `source_dir`, regras. **Fluxo principal:** listar → casar regra → mover/copiar → relatório. **Alternativos:** dry-run; sem `--yes` no CLI, não executa de verdade (receita Live usa `--yes` explicitamente).
**Saídas:** operações executadas/planejadas. **Artefatos:** estrutura de pastas resultante; audit.
**Critérios de avaliação:** prévia = execução (mesma lista).
**Critérios de aceite:** colisão respeita política; ordem das regras respeitada.
**Regras de negócio:** default nunca sobrescreve.
**Requisitos adicionais:** criação automática das subpastas de destino.
**Dependências:** PyYAML, pydantic. **Segurança:** caminhos validados.
**Falhas:** por arquivo, sem abortar o lote. **Recuperação:** reexecução idempotente com `skip`.
**Modo Live:** card ATIVO (saída zipada da pasta organizada). **Modo real:** `autotarefas organize SRC -r regras.yaml`.
**Testes:** `tests/tasks/test_organize.py`, `tests/cli/test_organize_cli.py`.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/tasks/organize.py` (484 linhas); asset Live `organize_rules.yaml`.
**Lacunas:** undo (ARQ-004); modo recursivo é decisão futura consciente (limite documentado no módulo).
**Próxima ação:** manter.

### RF-ARQ-004 — Desfazer movimentações
**Objetivo:** reverter uma organização quando possível.
**Problema resolvido:** arrependimento pós-organização sem caminho de volta.
**Descrição detalhada (alvo):** cada execução real de organize grava um plano reverso (origem→destino por arquivo, já presente no audit `operations`); `organize desfazer --execucao <id>` reaplica ao contrário com dry-run e as mesmas políticas de colisão; irreversível quando `overwrite` destruiu conteúdo — o comando informa exatamente o que não pode voltar.
**Critérios de aceite:** mover 10 arquivos e desfazer devolve os 10 aos lugares originais; caso `overwrite`, o relatório lista a perda como irrecuperável.
**Prioridade:** PÓS-V1. **Fase:** D2. **Status:** NÃO INICIADO.
**Evidência da base existente:** lista `operations` no audit (task organize). **Demais campos:** padrão do módulo.

### RF-ARQ-005 — Histórico e retenção de backups
**Objetivo:** política simples de quantos backups manter e onde.
**Descrição detalhada (alvo):** convenção de nome com timestamp; `backup listar` mostra histórico via audit; `--manter N` remove os mais antigos **somente com confirmação** e registrando no audit o que expurgou.
**Prioridade:** PÓS-V1. **Fase:** D2. **Status:** NÃO INICIADO. **Demais campos:** padrão do módulo.

---

## Módulo PLA — Análise e tratamento de planilhas

### RF-PLA-001 — Leitura robusta de CSV/XLSX
**Objetivo:** ler o arquivo como ele é, sem adivinhar o que ele já afirma.
**Problema resolvido:** leitores que descartam metadados e escolhem aba errada em silêncio.
**Usuário:** todas as funcionalidades de planilha; operador via `analisar`/`validate`.
**Descrição detalhada:** XLSX via openpyxl preservando `number_format` e `data_type` de célula (moeda, data, percentual); CSV com inferência explícita; detecção estrutural de aba e linha de cabeçalho (rótulos distintos + dados consistentes) com **nota de confiança e lista de candidatas**; normalização tipada com trilha de conversões (`Conversion`), preservando zeros à esquerda e nunca apagando linha.
**Pré-condições:** arquivo legível. **Entradas:** caminho, `--sheet`, `--header-row` opcionais. **Fluxo principal:** abrir → detectar → normalizar → `WorkbookReadResult`. **Fluxos alternativos:** confiança baixa → recusa explícita pedindo `--sheet`/`--header-row` (nunca escolhe em silêncio).
**Saídas:** resultado tipado com DataFrame + metadados + conversões. **Artefatos:** —.
**Critérios de avaliação:** planilha errada jamais entregue sem aviso.
**Critérios de aceite:** ambiguidade lista candidatas; valor ambíguo permanece como está + aviso.
**Regras de negócio:** nada inventado, nada apagado.
**Requisitos adicionais:** —. **Dependências:** openpyxl, pandas.
**Segurança:** arquivo tratado como dado, nunca executado.
**Falhas:** mensagens por tipo (extensão, encoding, estrutura). **Recuperação:** reexecução com flags.
**Modo Live:** motor do `analyze` da jornada. **Modo real:** motor de `analisar`/`validate`.
**Testes:** `tests/reader/` (6 arquivos, 96 funções, incl. `test_arquitetura.py`).
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/reader/{workbook,table_detect,normalize,types,result}.py`.
**Lacunas:** —. **Próxima ação:** manter.

### RF-PLA-002 — Análise estrutural com veredito de ambiguidade
**Objetivo:** diagnóstico compreensível antes de qualquer validação.
**Problema resolvido:** validar sem saber o que a planilha é.
**Usuário:** operador; visitante da jornada Live.
**Descrição detalhada:** perfilagem genérica (tipos por coluna, vazios, exemplos, métricas) **sem conhecimento de domínio** — um teste percorre a AST do pacote e falha se termo de domínio aparecer; serviço de um passo (`analyze_file`) encadeia leitura→perfil→relatório→sugestão de schema→preview e adiciona veredito explícito de ambiguidade com limiar documentado.
**Entradas:** arquivo (+flags de seleção). **Fluxo principal:** `autotarefas analisar arquivo` → resumo no console. **Alternativos:** `--json`/`--out-dir` para relatório estruturado; `--preview` N linhas; ambíguo → pergunta.
**Saídas:** diagnóstico legível + JSON opcional. **Artefatos:** `analise_report.json` (quando pedido).
**Critérios de avaliação:** leigo entende o diagnóstico sem abrir o arquivo.
**Critérios de aceite:** mesmas escolhas (aba/linha) reproduzem o mesmo relatório.
**Regras de negócio:** observar, nunca alterar.
**Dependências:** módulo reader. **Segurança:** N/A adicional.
**Modo Live:** `POST /api/spreadsheets/analyze` (+`selection`). **Modo real:** comando `analisar`.
**Testes:** `tests/profiling/` (4 arquivos, 71 funções), `tests/services/test_analysis.py` (21), `tests/cli/test_analisar_cli.py` + `test_analisar_arquitetura.py`.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/profiling/`, `src/autotarefas/services/analysis.py`, `src/autotarefas/cli/commands/analisar.py`.
**Lacunas:** —. **Próxima ação:** manter.

### RF-PLA-003 — Schema sugerido
**Objetivo:** transformar a análise num ponto de partida editável para validar.
**Descrição detalhada:** gera `schema_sugerido.yaml` a partir do observado (tipos, obrigatórios prováveis), fechando o ciclo analisar→editar 2 linhas→validate.
**Critérios de aceite:** YAML gerado é aceito pelo `validate` sem edição (validação mínima) e comentado para edição humana.
**Modo Live:** baixável na jornada; pode ser confirmado como schema da validação. **Modo real:** `analisar --schema-sugerido`.
**Testes:** `tests/profiling/test_schema_suggestion.py`.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/profiling/schema_suggestion.py`. **Demais campos:** padrão do módulo.

### RF-PLA-004 — Perfis de validação prontos
**Objetivo:** validar cenários comuns sem escrever YAML.
**Descrição detalhada:** perfis YAML embutidos no pacote (importlib.resources — funcionam no wheel); `perfis listar/ver/exportar`; exportação troca campos conceituais (`email`, `documento`) pelas colunas reais em **todos** os pontos (columns, group_keys, consistent, derived target e referências `[Nome]` dentro de expressões), com procedência gravada e requeridos não mapeados marcados de forma inconfundível; id de perfil validado contra formato restrito (sem path traversal).
**Modo Live:** `GET /api/spreadsheets/profiles` + escolha na etapa de schema (perfil escolhido **somente pelo usuário** — decisão de produto respeitada). **Modo real:** comando `perfis`.
**Testes:** `tests/profiles/` (4 arquivos, 62 funções).
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/profiles/{catalog,remap,export}.py`; recurso `resources/cadastro_contatos.yaml`.
**Lacunas:** catálogo com **1 perfil**; ampliar (ex.: financeiro, estoque) é oportunidade da Fase B/C.
**Demais campos:** padrão do módulo.

### RF-PLA-005 — Validação completa
**Objetivo:** encontrar todos os problemas de uma vez, com linha e coluna.
**Problema resolvido:** conferência manual célula a célula.
**Descrição detalhada:** schema YAML declarativo; validadores de tipo (`int/float/date`...), Regex, Range, Enum, MinLength, CPF, CNPJ (módulo 11 + blacklist), e-mail, telefone; obrigatórios; **acumula** issues (não para na primeira) com severidade ERROR/WARNING; duplicatas por coluna (com normalização por chave) e linhas 100% idênticas; regras de **grupo** (linhas da mesma chave devem concordar em colunas) e **derivadas** (`[Total] = [Base] * [Fator]`) com mini-linguagem aritmética segura por AST — sem eval, sem função, sem atributo; `--strict-warnings` e `--max-issues`.
**Entradas:** planilha + schema (+ flags). **Fluxo principal:** ler (PLA-001) → validar estrutura → conteúdo → cross-row → issues. **Alternativos:** modo `limpeza` aplica PLA-006 antes de validar.
**Saídas:** issues estruturadas; exit code por resultado. **Artefatos:** via PLA-007/008.
**Critérios de avaliação:** todos os problemas plantados nas fixtures detectados com linha/coluna corretas.
**Critérios de aceite:** avisos não invalidam linha; `--strict-warnings` promove; expressão maliciosa recusada pelo parser.
**Regras de negócio:** linha inválida = ≥1 ERROR.
**Dependências:** PyYAML, pandas. **Segurança:** parser AST próprio (`expressions.py`).
**Falhas:** issue por problema; erro de schema → mensagem de configuração. **Recuperação:** corrigir e reexecutar.
**Modo Live:** etapa `validate` da jornada (modo auditoria) e card clássico (modo limpeza com schema fixo da demo). **Modo real:** `autotarefas validate`.
**Testes:** `tests/tasks/test_validate.py`, `test_validate_extended.py`, `test_validate_row_rules.py`, `test_validate_selection.py`, `test_validators.py`, `test_validators_br.py`, `test_duplicates.py`, `test_row_rules.py`, `test_expressions.py`, `test_issues.py`; `tests/cli/test_validate_cli.py`.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/tasks/validate.py` (1306 linhas) + módulos de apoio citados.
**Lacunas:** —. **Próxima ação:** manter.

### RF-PLA-006 — Limpeza segura com trilha
**Objetivo:** normalizar sem nunca inventar dado.
**Descrição detalhada:** transformações determinísticas: trim/colapso de espaços, e-mail minúsculo, máscara canônica de CPF/CNPJ/telefone **somente quando o valor já é válido** (senão mantém original); cada mudança vira `CleaningChange` (antes/depois/regra) no audit; funções puras, sem conhecer o Schema.
**Critérios de aceite:** valor inválido nunca "consertado"; trilha cobre 100% das mudanças.
**Modo Live:** card clássico `validate` roda `--mode limpeza`. **Modo real:** `validate --mode limpeza`.
**Testes:** `tests/tasks/test_cleaning.py`.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/tasks/cleaning.py`. **Demais campos:** padrão do módulo.

### RF-PLA-007 — Artefatos e relatórios da auditoria
**Objetivo:** resultado que encerra o trabalho de alguém, não só "23 problemas".
**Descrição detalhada:** separação `registros_validos.csv` / `registros_invalidos.csv` (+coluna `motivo`); categorização por tipo de problema; relatório JSON (integrações) e CSV (Excel) + resumo textual; `planilha_validada.xlsx` com 4 abas (Resumo com contadores e erros por categoria; Válidos com autofiltro e painel congelado; Inválidos com motivo; Auditoria antes/depois) — contadores gravados como **valores** (retrato, não modelo).
**Critérios de aceite:** soma válidos+inválidos = linhas de dados; XLSX abre limpo no Excel/LibreOffice.
**Modo Live:** artefatos baixáveis do `out/`. **Modo real:** `--out-dir`, `--report-json`, `--report-csv`.
**Testes:** `tests/tasks/test_artifacts.py`, `test_report.py`, `test_report_xlsx.py`.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/tasks/{artifacts,report,report_xlsx}.py`. **Demais campos:** padrão do módulo.

### RF-PLA-008 — Pacote de evidências
**Objetivo:** meses depois, provar qual arquivo e configuração produziram o resultado.
**Descrição detalhada:** diretório com `manifest.json` (o que rodou, hashes de entrada e saídas, versão), `resumo.json`, `problemas.csv`, `registros_validos.csv`, `registros_para_revisao.csv` e `schema_efetivo.yaml`; no Live é compactado em ZIP único para download seguro.
**Critérios de aceite:** hashes do manifesto conferem com os arquivos; pacote reproduzível byte a byte para a mesma entrada/config (exceto timestamps declarados).
**Testes:** `tests/tasks/test_execution_package.py`.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/tasks/execution_package.py` (477 linhas); flag `--artefatos`. **Demais campos:** padrão do módulo.

### RF-PLA-009 — Preservação da apresentação original
**Objetivo:** entregar `planilha_tratada.xlsx` que o cliente reconheça como a dele.
**Problema resolvido:** hoje as saídas têm formatação própria profissional, mas a formatação **original** (cores, larguras, filtros, congelamentos, formatos) não é copiada para a versão tratada.
**Descrição detalhada (alvo):** ao gerar a versão tratada de um XLSX, copiar estilos/larguras/alturas/filtros/painéis/formatos das células correspondentes quando tecnicamente possível (openpyxl), com relatório do que não pôde ser preservado; quando o original não tiver apresentação, cair na formatação profissional já existente (PLA-007).
**Critérios de aceite:** cabeçalho colorido, painel congelado e formato de moeda do original presentes na tratada; significado dos dados jamais alterado pela formatação.
**Riscos:** fidelidade limitada do openpyxl (gráficos, temas) — declarar limites no relatório de preservação (risco R-13).
**Prioridade:** OBRIGATÓRIO V1 (revisão 2 — etapa 6 do resultado operacional, 01 §9.1). **Fase:** B4. **Status:** CONCLUÍDO (14/08/2026).
**Evidências:** `src/autotarefas/tasks/presentation.py`; artefatos `planilha_tratada.xlsx` e `preservacao_report.json` gerados por `validate --mode limpeza --out-dir`; fixture `tests/fixtures/apresentacao/original_formatado.xlsx`; testes em `tests/tasks/test_presentation.py` e `tests/cli/test_validate_tratada_cli.py`.
**Como ficou (decisão técnica):** em vez de recriar estilos célula a célula, o AutoTarefas **parte de uma cópia do arquivo original e reescreve apenas as células que a limpeza mudou**. Consequência: cores, larguras, painel congelado, autofiltro, formatos de número, fórmulas não tocadas, validações e formatação condicional continuam exatamente como o cliente entregou — e o valor tratado entra **tipado** (vem do DataFrame processado, não do texto do audit trail).
**Limites declarados (R-13):** gráficos e imagens não sobrevivem ao round-trip do openpyxl; são **detectados antes de salvar** e listados em `preservacao_report.json` (`nao_preservado`). CSV não tem apresentação a preservar — nesse caso valem os artefatos formatados do PLA-007. O arquivo original nunca é alterado (verificado por hash nos testes).

### RF-PLA-010 — Correções por regras confirmadas
**Objetivo:** ir além da limpeza determinística quando o usuário autorizar regra explícita.
**Descrição detalhada (alvo):** catálogo de correções parametrizáveis (ex.: mapear valores de/para, completar campo por lookup fixo, padronizar categoria) **sempre** confirmadas por configuração, com separação clara no relatório entre automático-seguro, normalização, regra-confirmada e item-para-revisão.
**Regras de negócio:** nenhuma correção fora de regra confirmada; original preservado; nenhuma decisão incerta silenciosa — caso fora da regra vai para revisão.
**Prioridade:** OBRIGATÓRIO V1 (revisão 2 — etapa 4 do resultado operacional, 01 §9.1). **Fase:** B5 (após REC, que fornece o lookup). **Status:** CONCLUÍDO (14/08/2026).
**Evidências:** `src/autotarefas/tasks/{corrections,correction_artifacts}.py`, comando `autotarefas corrigir` (`src/autotarefas/cli/commands/corrigir.py`), fixtures em `tests/fixtures/correcoes/`; testes em `tests/tasks/test_corrections.py` e `tests/cli/test_corrigir_cli.py`.
**Catálogo inicial (3 tipos, declarados em YAML):** `de_para` (troca valores conhecidos por um canônico, ignorando caixa e acentos), `padronizar` (encaixa o valor em uma lista declarada) e `preencher` (completa **apenas células vazias** com um valor fixo). Cada regra declara `fora_da_regra: revisao | manter`.
**Separação exigida pela ficha:** o relatório traz as quatro naturezas em um só lugar — `automatico_seguro` (conversões do leitor), `normalizacao`, `regra_confirmada` e `revisao`.
**Comportamento seguro:** valor que já é o destino da regra não vira revisão (não se pede conferência do que está certo); valor desconhecido nunca é alterado — vai para `itens_para_revisao.csv` com o motivo. A planilha corrigida sai preservando a apresentação do original (reusa PLA-009) e o arquivo de entrada nunca é modificado (verificado por hash).
**Artefatos:** `planilha_corrigida.xlsx`, `planilha_corrigida.csv`, `itens_para_revisao.csv` e `correcoes_report.json`.

---

## Módulo REC — Reconciliação e transferência entre planilhas
*Iniciado na Fase B1: o pacote `src/autotarefas/reconcile/` existe e entrega a
comparação por chave (REC-001). REC-002 a REC-004 seguem pendentes e constroem
sobre esse núcleo.*

### RF-REC-001 — Comparação (diff) entre planilhas por chave
**Objetivo:** dizer com precisão o que difere entre duas versões/fontes de uma base.
**Problema resolvido:** conferência visual de duas planilhas lado a lado.
**Usuário:** administrativo/financeiro; qualquer um que recebe "a planilha atualizada".
**Descrição detalhada:** entradas A e B; chave simples ou composta; normalização prévia opcional (trim, caixa, dígitos de documento — reusa cleaning); saída classificando cada registro: só-em-A, só-em-B, idêntico, divergente (com lista de colunas e valores A×B); duplicatas de chave sinalizadas por fonte; sem tolerâncias nesta primeira ficha (ficam na REC-002).
**Pré-condições:** ambas legíveis pelo reader. **Entradas:** 2 arquivos + chave(s) + colunas comparadas (default: todas em comum). **Fluxo principal:** ler A e B → indexar por chave → classificar → artefatos. **Alternativos:** chave duplicada → registro vai para aba de conflitos, nunca pareado em silêncio; coluna ausente em uma fonte → aviso e exclusão da comparação.
**Saídas:** resumo por categoria. **Artefatos:** `comparacao_report.json`, `divergencias.xlsx` (abas por categoria, formatação PLA-007), `somente_a.csv`, `somente_b.csv`.
**Critérios de avaliação:** operador identifica cada diferença sem abrir os originais.
**Critérios de aceite:** fixtures com casos plantados (novo, removido, alterado em 1 coluna, duplicado) classificados 100% corretamente; nenhuma célula das fontes alterada.
**Regras de negócio:** leitura pura — este requisito nunca escreve nas fontes.
**Requisitos adicionais:** chave composta com ordem irrelevante para o pareamento.
**Dependências:** reader, cleaning, artifacts (tudo existente). **Segurança:** N/A adicional.
**Tratamento de falhas:** por arquivo; ambiguidade estrutural segue PLA-001. **Recuperação:** reexecução.
**Modo Live:** card futuro com dois uploads pequenos + exemplo pronto. **Modo real:** `autotarefas comparar A.xlsx B.xlsx --chave cpf`.
**Testes necessários:** unidade das classificações; CLI; fixtures com acento/zeros à esquerda.
**Prioridade:** OBRIGATÓRIO V1 (DP-04 decidida em 05/08/2026). **Fase:** B1. **Status:** CONCLUÍDO (14/08/2026).
**Evidências:** `src/autotarefas/reconcile/{result,compare,artifacts,task}.py`, comando `autotarefas comparar` (`src/autotarefas/cli/commands/comparar.py`), fixtures plantadas em `tests/fixtures/comparacao/` (idêntico, alterado em 1 coluna, removido, novo, chave repetida, divergência só por espaço/caixa, zeros à esquerda, XLSX×CSV); testes em `tests/reconcile/` e `tests/cli/test_comparar_cli.py`.
**Recorte desta entrega (limites declarados no próprio relatório, em `compare.LIMITATIONS`):** comparação textual sobre o dataframe FIEL do leitor — sem tolerância numérica ou de data (`10` ≠ `10,00`), que é da REC-002; normalização opcional e explícita (`--normalizar espacos|caixa|digitos`, com `digitos` valendo só para a chave) aplicada à comparação, nunca ao valor relatado; uma tabela por arquivo; chave duplicada ou vazia nunca é pareada (vai para conflitos com as linhas dos dois lados); coluna presente em apenas uma fonte fica fora, com aviso.
**Lacunas:** tolerâncias e base conciliada (REC-002); card no Live (fora do recorte do Live nesta fase).

### RF-REC-002 — Reconciliação com tolerâncias e base conciliada
**Objetivo:** das diferenças à decisão: qual valor vale, com que prioridade.
**Descrição detalhada:** sobre a REC-001: tolerâncias numéricas/percentuais e de datas; declaração de fonte principal × complementar; campos atualizáveis autorizados; geração de `base_conciliada.xlsx` + `conflitos_para_revisao.xlsx` + relatório de decisões (por registro: valor escolhido, fonte, regra aplicada).
**Regras de negócio:** conflito fora das regras declaradas nunca é resolvido automaticamente; toda decisão automática registrada com a regra que a justificou.
**Critérios de aceite:** tolerância de R$ 0,01 não gera divergência; conflito real sempre presente no arquivo de revisão.
**Prioridade:** OBRIGATÓRIO V1 — DP-04 (05/08/2026) e DP-01(a) (10/08/2026): realiza a etapa 3 do resultado operacional (01 §9.1). **Fase:** B2. **Status:** CONCLUÍDO (14/08/2026).
**Evidências:** `src/autotarefas/reconcile/{tolerance,merge,merge_artifacts}.py`, comando `autotarefas conciliar` (`src/autotarefas/cli/commands/conciliar.py`); testes em `tests/reconcile/test_tolerance.py`, `test_merge.py`, `test_merge_artifacts.py` e `tests/cli/test_conciliar_cli.py`.
**Como ficou:** tolerâncias declaradas por coluna em uma sintaxe (`coluna=0,01` absoluta, `coluna=1%` percentual, `coluna=2d` dias), aplicadas também no `comparar`; diferença tolerada nunca vira divergência, mas fica registrada (`RecordComparison.tolerated`, aba "Diferencas toleradas" e regra `tolerancia` no relatório de decisões). Política declarada: `--principal a|b`, `--atualizar COLUNA` (campos autorizados) e `--manter-novos/--revisar-novos`. Divergência em campo **não autorizado** preserva o valor da fonte principal e vai inteira para `conflitos_para_revisao.xlsx`; chave duplicada ou vazia nunca entra na base conciliada.
**Artefatos:** `base_conciliada.xlsx` (abas Base conciliada, Decisões e Resumo), `base_conciliada.csv`, `conflitos_para_revisao.xlsx` e `reconciliacao_report.json`.
**Lacunas:** configuração reutilizável em YAML (REC-004, fase B6).

### RF-REC-003 — Transferência e enriquecimento entre planilhas
**Objetivo:** preencher/atualizar colunas de uma base a partir de outra (o "PROCV com evidência").
**Descrição detalhada:** localizar registro correspondente na fonte, copiar campos autorizados para o destino **em arquivo novo**, coluna opcional `_origem_<campo>`, relatório de tudo que foi preenchido/atualizado/não-encontrado; combinação de bases em planilha consolidada com coluna de origem.
**Critérios de aceite:** campo não autorizado jamais alterado; não-encontrados listados com a chave buscada.
**Prioridade:** OBRIGATÓRIO V1 — DP-04 (05/08/2026) e DP-01(a) (10/08/2026): realiza a etapa 5 do resultado operacional (01 §9.1). **Fase:** B3. **Status:** CONCLUÍDO (14/08/2026).
**Evidências:** `src/autotarefas/reconcile/{transfer,transfer_artifacts}.py`, comando `autotarefas transferir` (`src/autotarefas/cli/commands/transferir.py`), fixtures em `tests/fixtures/transferencia/`; testes em `tests/reconcile/test_transfer.py` e `tests/cli/test_transferir_cli.py`.
**Como ficou:** o pareamento reusa a comparação da REC-001 (destino = A, fonte = B), o que dá chave composta, normalização e conflitos de chave sem código novo. Cada célula tocada vira uma linha de evidência com ação explícita (`preenchido`, `atualizado`, `mantido`, `sem_valor_na_fonte`); `--somente-vazios` nunca sobrescreve; `--marcar-origem` gera `_origem_<campo>`; campo ausente na fonte vira aviso, não erro. Não-encontrados saem em `nao_encontrados.csv` com a chave buscada e a linha do destino.
**Artefatos:** `planilha_enriquecida.xlsx` (abas Planilha enriquecida, Transferências, Não encontrados e Resumo), `planilha_enriquecida.csv`, `nao_encontrados.csv` e `transferencia_report.json`.
**Decisão de escopo:** a "planilha consolidada com coluna de origem" citada na descrição é entregue pelo `conciliar --manter-novos` (coluna `_origem`), em vez de um segundo caminho de código que faria a mesma coisa.

### RF-REC-004 — Configuração de reconciliação reutilizável
**Objetivo:** a conferência mensal configurada uma vez.
**Descrição detalhada:** YAML de reconciliação (fontes/aba/cabeçalho por padrão de nome, chaves, colunas, tolerâncias, prioridades, campos atualizáveis, tratamento de ausentes/conflitos) validado por pydantic; é o primeiro consumidor do formato de configuração de fluxo (CORE-006, recorte V1).
**Prioridade:** OBRIGATÓRIO V1 (revisão 2 — etapa 11 do resultado operacional). **Fase:** B6, junto de CORE-006. **Status:** NÃO INICIADO. **Demais campos:** padrão do módulo.

---

## Módulo INT — Integração com sistemas via API

### RF-INT-001 — Exportação via API paginada
**Objetivo:** dados que estão num sistema virarem planilha pronta.
**Problema resolvido:** exportação manual tela a tela.
**Usuário:** operador; visitante do Live.
**Descrição detalhada:** consome API no formato `{data, page, per_page, total, total_pages, has_next}`; paginação automática; retry exponencial (tenacity) só em erros temporários (timeout/conexão/5xx — 4xx propaga); rate limit por delay; auth opcional `X-API-Key` (nunca em log/audit); saída CSV/XLSX/JSON pela extensão ou `--out-dir` gerando `dados_extraidos.csv`, `dados_extraidos.xlsx` e `extracao_report.json`; dry-run busca só a 1ª página.
**Pré-condições:** URL acessível. **Entradas:** `-u URL`, `--per-page`, formato/out-dir, credencial via env. **Fluxo principal:** paginar → acumular → salvar → relatório. **Alternativos:** dry-run; página com erro temporário → retry; 4xx → falha clara.
**Saídas:** planilha(s) + relatório. **Artefatos:** os 3 acima.
**Critérios de avaliação:** total extraído = `total` reportado pela API.
**Critérios de aceite:** 47/47 produtos do mock em 5 páginas; credencial ausente do relatório.
**Regras de negócio:** leitura pura na origem.
**Requisitos adicionais:** —. **Dependências:** httpx, tenacity.
**Segurança:** header de auth mascarado. **Falhas/Recuperação:** retry + reexecução.
**Modo Live:** card ATIVO contra `/api/catalogo` (47 produtos, origem exibida ao visitante). **Modo real:** `autotarefas extract api`.
**Testes:** `tests/tasks/test_extract_api.py`, `test_extract_artifacts.py`; `tests/cli/test_extract_cli.py`; mock em `tests/tools/demo_server/test_catalogo.py`.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/tasks/{extract_api,extract_artifacts}.py`.
**Lacunas:** formato de paginação único (ver INT-004). **Próxima ação:** manter.

### RF-INT-002 — Importação/cadastro via API
**Objetivo:** planilha validada virar cadastros no sistema, sem duplicar.
**Problema resolvido:** digitação manual e o pavor do reenvio duplicar tudo.
**Usuário:** operador; visitante do Live.
**Descrição detalhada:** POST de um JSON por linha; tolerância por linha; retry só em temporários com respeito a `Retry-After` (sem o header, backoff exponencial com jitter); **`Idempotency-Key` determinística por linha** (mesma linha = mesma chave em toda tentativa e reenvio); rate limit por delay; auth opcional (`X-API-Key`/Bearer); relatório por linha; `--out-dir` gera 4 artefatos: `registros_enviados.csv`, `registros_falhos.csv` (com motivo/categoria, **reenviável** com as mesmas chaves), `resultado_envio.xlsx`, `envio_report.json`; colunas de controle prefixadas `_` não entram no payload; dry-run conta sem enviar.
**Critérios de avaliação:** reenviar `registros_falhos.csv` contra sistema idempotente não cria duplicata.
**Critérios de aceite:** 409 do mock (CPF já cadastrado) classificado como erro de dado, sem retry; 429 respeita `Retry-After` (cenário demonstrado no mock enriquecido).
**Regras de negócio:** erro de dado (400/409/422) nunca retentado.
**Modo Live:** card ATIVO contra `/api/clientes` com **reset automático** entre execuções (`reset_url` → `POST /limpar`). **Modo real:** `autotarefas send api`.
**Testes:** `tests/tasks/test_send_api.py`, `test_send_artifacts.py`, `test_send_result.py`; `tests/cli/test_send_cli.py`.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/tasks/{send_api,send_artifacts,send_result}.py` (549+328+221 linhas).
**Lacunas:** mapeamento de colunas configurável — **INT-005, OBRIGATÓRIO V1** (Fase B7); checkpoint — INT-006 (recomendado, não bloqueia).
**Demais campos:** padrão do módulo.

### RF-INT-003 — Sincronização API→API
**Objetivo:** ler de um sistema e gravar em outro num passo só.
**Descrição detalhada:** composição pura de ExtractApiTask + SendApiTask via arquivo intermediário temporário descartado; nada de HTTP reimplementado; audit granular com as três entradas (extract_api, send_api, sync_api).
**Critérios de aceite:** falha na extração aborta antes de qualquer envio; relatório final consolida os dois lados.
**Modo Live:** card "em breve" (mocks primário/secundário já sobem — `demo_servers.py`); ativação = LIVE-006. **Modo real:** `autotarefas sync api`.
**Testes:** `tests/tasks/test_sync_api.py`; `tests/cli/test_sync_cli.py`.
**Prioridade:** OBRIGATÓRIO V1 (modo real). **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/tasks/sync_api.py`. **Demais campos:** padrão do módulo.

### RF-INT-004 — Conectores declarativos por sistema
**Objetivo:** integrar com um sistema novo escrevendo 1 YAML, não 1 task.
**Problema resolvido:** cada API diferente exigir código novo.
**Descrição detalhada (alvo, decisão de design já registrada):** 1 YAML por sistema com base_url, auth (referenciando **somente** variáveis `*_env`), endpoints, `data_path` para achar os registros na resposta, e **4 estratégias de paginação** (page/per_page, offset/limit, cursor, link "next"); extract/send/sync passam a aceitar `--conector nome`.
**Critérios de aceite (alvo):** os mocks atuais e uma API pública gratuita descritos só por YAML; segredo literal no YAML → recusa na validação.
**Riscos:** generalizar cedo demais — mitigado por manter as tasks atuais funcionando sem conector (conector é açúcar, não requisito).
**Justificativa de não-bloqueio da V1:** (i) nenhuma etapa do resultado operacional (01 §9.1) depende dele — as integrações da V1 já funcionam com parâmetros explícitos e segredos via ambiente, e o mapeamento de colunas foi resolvido por RF-INT-005, que é obrigatório; (ii) abstração prematura: as 4 estratégias de paginação precisam de pelo menos **dois sistemas reais distintos** (contratos, autenticações e paginações diferentes) para validar o formato — congelar um YAML público errado custa compatibilidade depois; (iii) adiar não cria dívida: as tasks específicas continuam funcionando independentemente dos futuros conectores.
**Prioridade:** PÓS-V1 — **aprovado em 10/08/2026 (DP-01(b))**; decisão definitiva sobre o formato na Fase D, após os dois sistemas reais (DP-08 aprovada em 10/08/2026). **Fase:** D3. **Status:** NÃO INICIADO.
**Evidências:** apenas decisão registrada; nenhuma ocorrência de "conector" em `src/`. **Demais campos:** padrão do módulo.

### RF-INT-005 — Mapeamento de colunas configurável na importação
**Objetivo:** a planilha do cliente alimentar a API do sistema sem edição manual de cabeçalhos.
**Problema resolvido:** o arquivo tratado tem os nomes de coluna do cliente; o sistema de destino exige os nomes do seu contrato — hoje alguém renomeia colunas à mão antes de importar, e um nome errado só aparece como erro no meio do lote.
**Usuário:** operador que importa planilhas para sistemas de terceiros — o caso central da "Importação inteligente para sistemas".
**Descrição detalhada (escopo aprovado em DP-01(c)):** mapeamento declarado de **coluna da planilha → campo do sistema**, informado por parâmetros de CLI repetíveis (ex.: `--map "Nome Completo=nome"`) **ou** por arquivo simples de configuração; validação prévia dos **campos obrigatórios do destino** (falta de campo obrigatório impede o envio, em vez de gerar lote pela metade); detecção de **mapeamentos repetidos ou incompatíveis** (duas colunas para o mesmo campo, coluna inexistente na planilha, campo inexistente no contrato) com erro nomeando o conflito; **prévia do payload** de uma linha antes de qualquer envio; **dry-run** que valida e monta payloads sem gravar no sistema externo; **preservação do arquivo original** (o mapeamento nunca reescreve a planilha de entrada); **registro do mapeamento aplicado** nos artefatos e no audit; transformações limitadas às já existentes na limpeza, sem expressão dinâmica. Deliberadamente **não** é um framework universal de conectores: `base_url`, auth e paginação continuam parâmetros da task (conectores declarativos = RF-INT-004, PÓS-V1).
**Pré-condições:** planilha legível pelo reader; contrato do destino conhecido (campos e obrigatórios).
**Entradas:** planilha (idealmente o `registros_validos.csv` do fluxo), mapa de/para, lista de campos obrigatórios do destino, URL e credencial via ambiente.
**Fluxo principal:** carregar o mapa → validar contra as colunas reais e contra o contrato → montar o payload de exemplo e exibir a prévia → (dry-run encerra aqui com relatório) → enviar linha a linha reusando INT-002 (idempotência, retry, tolerância por linha) → relatório.
**Fluxos alternativos:** coluna do mapa ausente na planilha → erro de configuração antes do primeiro envio; campo obrigatório do destino sem origem → erro de configuração; coluna da planilha fora do mapa → ignorada com aviso explícito, nunca enviada por suposição; valor incompatível com o tipo do campo → linha para rejeitados com motivo.
**Saídas:** contagem de aceitos, rejeitados e falhos; prévia do payload no console.
**Artefatos:** `registros_enviados.csv`; `registros_rejeitados.csv` (reprovados antes do envio, com motivo); `registros_falhos.csv` (reenviável, herdado do INT-002); `envio_report.json` com o **mapa efetivo aplicado**; `mapeamento_efetivo.yaml` no pacote de evidências.
**Critérios de avaliação:** um operador importa uma planilha com cabeçalhos próprios sem renomear nada na origem; nenhum campo obrigatório do destino fica vazio por omissão silenciosa.
**Critérios de aceite — 12 exigências funcionais consolidadas em 11 critérios de aceite (aprovados em 10/08/2026; formulação padronizada em 10/08/2026):** as 12 exigências funcionais da DP-01(c) — mapeamento configurável coluna→campo; suporte por CLI ou arquivo simples; validação dos campos obrigatórios do destino; detecção de mapeamentos repetidos ou incompatíveis; prévia do payload; dry-run sem gravação externa; preservação do arquivo original; registro do mapeamento aplicado; relatório de aceitos, rejeitados e falhos; testes com estruturas diferentes (contatos, produtos, vendas); nenhuma credencial embutida na configuração; nenhuma decisão incerta aplicada silenciosamente — são verificadas pelos 11 critérios abaixo (as duas primeiras exigências são comprovadas em conjunto pelo critério 1, que exige resultado idêntico por CLI e por arquivo): (1) mapeamento por CLI e por arquivo produzem exatamente o mesmo resultado; (2) campo obrigatório do destino sem origem → falha de configuração com zero envio; (3) mapa com coluna repetida, coluna inexistente ou campo inexistente → erro nomeando o conflito; (4) prévia do payload exibida antes do primeiro envio; (5) dry-run não realiza nenhuma escrita externa, verificado contra o mock; (6) arquivo de entrada permanece byte-idêntico; (7) mapa aplicado consta do relatório e do audit; (8) relatório separa aceitos, rejeitados e falhos; (9) testes cobrem **três estruturas diferentes** — contatos, produtos e vendas; (10) nenhuma credencial aceita na configuração de mapeamento (somente nomes de variáveis de ambiente, padrão `*_env`); (11) nenhuma decisão incerta aplicada em silêncio — ambiguidade vira erro de configuração ou item de revisão.
**Regras de negócio:** o mapa é declaração explícita; nesta fase não há inferência automática por semelhança de nome; original preservado.
**Requisitos adicionais:** documentar a precedência quando existir configuração de fluxo (CORE-006): CLI > configuração > padrão.
**Dependências:** INT-002 (envio idempotente, concluído), reader/cleaning (concluídos), PLA-004 como referência de experiência de remapeamento. Nenhuma dependência nova.
**Segurança e privacidade:** credencial só por ambiente; mapa e relatórios sem segredo; prévia mascara campos sensíveis.
**Tratamento de falhas:** erro de configuração antes de qualquer envio; erro por linha não derruba o lote (herda INT-002).
**Recuperação:** reenvio de `registros_falhos.csv` com as mesmas chaves de idempotência.
**Modo Live:** o mapeamento permanece definido pelo servidor — o visitante nunca informa caminho, comando ou credencial; a demonstração pode exibir o mapa efetivo aplicado.
**Modo real:** `autotarefas send api --map "Coluna=campo" ...` ou `--map-file mapa.yaml`.
**Testes necessários:** unidade do validador de mapa (repetido, inexistente, obrigatório ausente); montagem de payload; dry-run sem I/O externo; CLI; três fixtures de estrutura distinta (contatos, produtos, vendas); teste de que a entrada não é modificada.
**Prioridade:** **OBRIGATÓRIO V1** — promovido em 10/08/2026 (DP-01(a) e DP-01(c)): corrigir a planilha e adequá-la ao contrato de uma API são responsabilidades distintas. **Fase:** B7, obrigatória, depois de B1–B6. **Status:** NÃO INICIADO.
**Evidências:** — nenhuma; busca por mapeamento configurável em `src/autotarefas/tasks/send_api.py` e no grupo de comandos `src/autotarefas/cli/commands/send/` sem resultados neste snapshot.
**Lacunas:** tudo — as 12 exigências funcionais consolidadas em 11 critérios de aceite acima.
**Próxima ação:** implementar na Fase B7; **bloqueia a homologação C1 e o release V1**.

### RF-INT-006 — Checkpoint e retomada
**Objetivo:** lote de 50 mil linhas cair no meio e continuar do ponto certo.
**Descrição detalhada (alvo):** arquivo de checkpoint por execução (última linha confirmada + chaves enviadas); `--continuar <checkpoint>` pula o já confirmado; complementa (não substitui) o reenvio de falhos existente.
**Critérios de aceite:** matar o processo no meio e retomar termina o lote sem duplicar (verificado pelas Idempotency-Keys no mock).
**Justificativa de não-bloqueio da V1 (revisão 2):** o risco de integridade que o checkpoint mitiga já está coberto — `Idempotency-Key` determinística torna a reexecução segura em sistemas idempotentes, e `registros_falhos.csv` já permite retomar apenas o que falhou; o checkpoint economiza reenvio dos confirmados após morte abrupta do processo, cenário raro no volume-alvo. Gatilho objetivo para promover a obrigatório: lotes reais recorrentes acima de ~10 mil linhas ou destino não idempotente em produção.
**Prioridade:** RECOMENDADO V1 — **confirmado em 10/08/2026 (DP-01(c))**: não bloqueia o release. **Fase:** B8 — etapa recomendada, posterior à B7; nenhum requisito recomendado atrasa um obrigatório. **Status:** NÃO INICIADO. **Demais campos:** padrão do módulo.

---

## Módulo COM — Comunicação

### RF-COM-001 — E-mails em massa com templates
**Objetivo:** notificar uma lista inteira a partir da planilha, com prova de envio.
**Descrição detalhada:** SMTP via stdlib; templates `{coluna}` em assunto e corpo; tolerância por linha; delay configurável; auth e STARTTLS opcionais; relatório por linha (CSV/XLSX/JSON); dry-run não conecta; senha só transita na conexão — nunca em log/audit/relatório.
**Critérios de aceite:** template com coluna ausente → erro claro por linha; relatório não contém a senha nem o corpo enviado.
**Modo Live:** card "em breve" (mock SMTP `tools/smtp_debug.py` pronto); ativação = LIVE-006. **Modo real:** `autotarefas send email` com `email_*` do `.env`.
**Testes:** `tests/tasks/test_send_email.py`; `tests/cli/test_send_email_cli.py`.
**Prioridade:** OBRIGATÓRIO V1 (modo real). **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/tasks/send_email.py` (445 linhas). **Demais campos:** padrão do módulo.
**Lacunas:** anexos por linha não suportados (registrar como oportunidade, não defeito).

### RF-COM-002 — Telegram em massa
**Objetivo:** notificação gratuita e imediata por bot.
**Descrição detalhada:** Bot API `sendMessage`; destino fixo (`chat_id`) ou por coluna (`chat_id_column`); template `{coluna}`; `base_url` configurável (mock nos testes/Live, `api.telegram.org` em produção); **token nunca persistido** — `_redact` remove o token até de dentro de exceções/URLs; relatório por linha **sem o texto enviado** (conteúdo não vai a disco); retry resiliente; dry-run.
**Critérios de aceite:** forçar exceção com token na URL → relatório e log sem o token.
**Modo Live:** card ATIVO contra o mock interno (`/bot<token>/sendMessage`). **Modo real:** `autotarefas send telegram`.
**Testes:** `tests/tasks/test_send_telegram.py`; `tests/cli/test_send_telegram_cli.py`; mock em `tests/tools/demo_server/test_telegram_mock.py`.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/tasks/send_telegram.py` (531 linhas). **Demais campos:** padrão do módulo.

### RF-COM-003 — Idempotência e limites de envio
**Objetivo:** reexecutar uma campanha sem mandar tudo de novo, e nunca estourar cota.
**Descrição detalhada (alvo):** chave determinística por mensagem (destinatário+template+linha) com registro local do já-enviado; `--limite N` por execução; reaproveita o desenho do reenvio de falhos do INT-002.
**Prioridade:** PÓS-V1. **Fase:** D1. **Status:** NÃO INICIADO. **Demais campos:** padrão do módulo.

---

## Módulo WEB — Web scraping e RPA

### RF-WEB-001 — Scraping HTML paginado
**Objetivo:** sites sem API virarem planilha.
**Descrição detalhada:** httpx + BeautifulSoup; linha por seletor CSS (`-r`), campos por `-f nome=seletor`, paginação por `-n` (href de "próxima"); mesma forma da extração via API (retry temporário, rate limit, CSV/XLSX/JSON, dry-run); limite documentado: conteúdo precisa estar no HTML.
**Critérios de aceite:** catálogo mock paginado extraído completo; seletor sem match → aviso, não crash.
**Modo Live:** card ATIVO contra `/catalogo` do mock. **Modo real:** `autotarefas extract web`.
**Testes:** `tests/tasks/test_extract_web.py`; `tests/cli/test_extract_web_cli.py`.
**Prioridade:** OBRIGATÓRIO V1. **Fase:** entregue. **Status:** CONCLUÍDO.
**Evidências:** `src/autotarefas/tasks/extract_web.py` (512 linhas). **Demais campos:** padrão do módulo.

### RF-WEB-002 — Scraping com JavaScript
**Objetivo:** páginas montadas por JS também virarem planilha.
**Descrição detalhada:** `--js` renderiza com Chromium headless (BrowserSession) e extrai o HTML pós-JS, reutilizando **uma** sessão de navegador na paginação; paginação continua por href (SPA de clique fora de escopo, documentado); exige `playwright install chromium`.
**Critérios de aceite:** `/catalogo-js` do mock (vazio sem JS) extraído completo com `--js`.
**Modo Live:** **fora da V1 pública por DP-02 (aprovada em 10/08/2026)** — a promessa de execução direta sai da vitrine e o funcionamento é demonstrado por vídeo/GIF; implementação, testes e CLI preservados; execução pública com Chromium reavaliada na Fase D. **Modo real:** `autotarefas extract web --js` (obrigatório V1).
**Testes:** `tests/tasks/test_extract_web_js.py` (unidade, browser mockado); `tests/e2e/test_extract_web_js_e2e.py` — medido na A1 (10/08/2026): **1 passa e 1 auto-skipa** sem Chromium (`verify_playwright_installed`).
**Prioridade:** OBRIGATÓRIO V1 (modo real). **Fase:** entregue (código); comprovação com navegador na Fase C1. **Status:** PARCIAL — implementação e testes de unidade prontos; critério de aceite com navegador ainda não demonstrado (legenda 00 §2: parte comprovada, parte ausente).
**Evidências:** ramo `--js` em `extract_web.py`; `src/autotarefas/core/browser.py`. **Lacunas:** execução com navegador instalado. **Próxima ação:** rodar `playwright install chromium && python -m pytest tests/e2e` na homologação (C1) e promover a CONCLUÍDO. **Demais campos:** padrão do módulo.

### RF-WEB-003 — RPA de cadastro
**Objetivo:** cadastrar em sistema web sem API, linha a linha, com evidência.
**Descrição detalhada:** lê planilha (`nome`, `email`, `cpf` obrigatórios; `telefone` opcional); health check do alvo antes de abrir navegador; CPF inválido → `skipped`; duplicado no destino → `skipped`; erro inesperado → `error` + **screenshot mascarada** automática; dry-run valida sem abrir navegador; status agregado SUCCESS/PARTIAL/FAILURE.
**Critérios de aceite:** linha ruim não interrompe; screenshot de erro não expõe campos sensíveis.
**Modo Live:** **fora da V1 pública por DP-02** (mesma razão e mesmas garantias do WEB-002: nada de código ou teste removido). **Modo real:** `autotarefas rpa cadastro` contra sistema autorizado (demo local incluída) — obrigatório V1.
**Testes:** `tests/tasks/test_rpa_cadastro.py`; `tests/cli/test_rpa_cli.py`; `tests/core/test_browser.py` — todos com navegador **mockado**. A A1 (10/08/2026) constatou que **não existe teste com navegador real para o RPA**: `tests/e2e/` contém apenas o caso de scraping com JavaScript.
**Prioridade:** OBRIGATÓRIO V1 (modo real). **Fase:** entregue (código); comprovação com navegador na Fase C1. **Status:** PARCIAL — implementação e testes de unidade prontos; critério de aceite com navegador ainda não demonstrado.
**Evidências:** `src/autotarefas/tasks/rpa_cadastro.py` (544 linhas). **Lacunas:** nenhuma verificação com navegador real. **Próxima ação:** **decisão aprovada em 10/08/2026** — criar teste automatizado com **navegador real** para o RPA antes de promover o requisito; a homologação manual é **complementar, não substituta**. Referência de execução na C1: `playwright install chromium && python -m pytest tests/e2e`. **Demais campos:** padrão do módulo.

### RF-WEB-004 — Retomada e resiliência de página
**Objetivo:** lote de RPA continuar após queda e avisar quando o site mudou.
**Descrição detalhada (alvo):** checkpoint por linha (compartilha desenho com INT-006); detecção de mudança estrutural (seletor obrigatório sumiu → abortar com diagnóstico e screenshot, em vez de erros em série).
**Prioridade:** PÓS-V1. **Fase:** D4. **Status:** NÃO INICIADO. **Demais campos:** padrão do módulo.

---

## Módulo GOV — Governança e auditoria

### RF-GOV-001 — Relatórios consolidados do audit
**Descrição detalhada:** read-only sobre o SQLite; tipos `summary` (contagens, médias, falhas recentes), `list` (com filtros por task/status/período) e `errors`; saída console/JSON.
**Critérios de aceite:** nenhuma escrita no audit em nenhuma consulta.
**Modo Live:** card "em breve" (ativação trivial — o workspace tem audit próprio). **Modo real:** `autotarefas report`.
**Testes:** `tests/tasks/test_report_audit.py`; `tests/cli/test_report_cli.py`.
**Prioridade:** OBRIGATÓRIO V1. **Status:** CONCLUÍDO. **Evidências:** `src/autotarefas/tasks/report_audit.py` (390 linhas). **Demais campos:** padrão do módulo.

### RF-GOV-002 — Painel HTML do audit
**Descrição detalhada:** camadas separadas `reader` (consulta tipada + `verify_input_hash`) e `renderer` (HTML autocontido, CSS embutido, `html.escape` em todo valor dinâmico, classe de badge de conjunto fechado); CLI `dashboard` com `--open`.
**Critérios de aceite:** arquivo único abre offline; entrada maliciosa no audit não injeta HTML.
**Modo Live:** card "em breve". **Modo real:** `autotarefas dashboard` (exemplos na raiz: `dashboard.html`, `dashboard_exemplo.html`).
**Testes:** `tests/dashboard/test_reader.py`, `test_renderer.py`; `tests/cli/test_dashboard_cli.py`.
**Prioridade:** OBRIGATÓRIO V1. **Status:** CONCLUÍDO. **Evidências:** `src/autotarefas/dashboard/{reader,renderer}.py`. **Demais campos:** padrão do módulo.

### RF-GOV-003 — Retenção, expurgo e mascaramento programáveis
**Objetivo:** dados e evidências com prazo de vida definido e cumprido (LGPD).
**Estado atual (PARCIAL):** mascaramento OK (`mask_sensitive_in_dict`, screenshots mascaradas, `SecretStr`, redação de token); logs com retenção **fixa de 30 dias** (`src/autotarefas/core/logger.py`, linha 142); `screenshot_retention_days` existe em settings **sem rotina que expurgue**; audit sem qualquer expurgo; workspaces do Live têm TTL 15 min (OK).
**Descrição detalhada (alvo):** comando `manutencao expurgar` aplicando: retenção de logs pela settings (não fixa), expurgo de screenshots além do prazo, expurgo opcional do audit além de N dias **com confirmação e registro do expurgo**; documentação da política em SECURITY/privacidade.
**Critérios de aceite:** rodar o expurgo remove exatamente o que a política manda e grava no audit o que removeu; padrão continua conservador (sem expurgo silencioso).
**Política aprovada em 10/08/2026 (DP-05), por ambiente:** Live público — uploads e artefatos com TTL de 15 min, logs operacionais sem dados sensíveis 30 dias, screenshots mascaradas 7 dias, audit 30 dias; modo real privado — uploads/artefatos configuráveis pelo operador, logs 30 dias por padrão (configurável), screenshots 30 dias por padrão (configurável), audit com retenção configurável e exclusão manual confirmada. O Live deve informar finalidade do processamento, tempo de retenção, existência de arquivos de exemplo, recomendação de não enviar dados pessoais desnecessários e a diferença entre demonstração pública e modo real privado. Registro obrigatório: **política técnica**, sujeita a revisão jurídica antes de uso comercial com dados pessoais de clientes. Dois pontos de aplicação ficaram em aberto e estão listados em `08` §5 (audit do Live e screenshots no Live).
**Prioridade:** OBRIGATÓRIO V1 (fecha o compromisso LGPD antes do release). **Fase:** A2. **Status:** PARCIAL.
**Evidências do existente:** caminhos citados acima. **Lacunas:** rotina de expurgo; retenção de log configurável.
**Próxima ação:** implementar na Fase A2 (após DP-05 fixar os prazos).

### RF-GOV-004 — Verificação de integridade das evidências
**Descrição detalhada:** `verify_input_hash` recalcula o HMAC do input e compara com o gravado; exposto no painel (GOV-002).
**Critérios de aceite:** alterar 1 byte do input → verificação acusa.
**Testes:** `tests/dashboard/test_reader.py`.
**Prioridade:** OBRIGATÓRIO V1. **Status:** CONCLUÍDO. **Evidências:** `src/autotarefas/dashboard/reader.py`. **Demais campos:** padrão do módulo.

---

## Módulo LIVE — Live System público

### RF-LIVE-001 — Catálogo curado com régua ativo/em breve
**Descrição detalhada:** 13 automações/7 categorias em dataclass congelada; payload público sem comandos/caminhos; régua = `engine.ACTIVE_AUTOMATIONS` (7 ids); front separa pelo health; backend responde **501** fora da régua; estado `oculto` da régua de design não implementado.
**Critérios de aceite:** id fora do catálogo → 404; dentro do catálogo mas fora da régua → 501.
**Testes:** cobertos em `live_demo/backend/tests/test_engine.py` (suite 127 passed).
**Prioridade:** OBRIGATÓRIO V1. **Status:** CONCLUÍDO. **Evidências:** `live_demo/backend/app/catalog.py` (249 linhas), `engine.py::ACTIVE_AUTOMATIONS`, `main.py::_precheck`. **Demais campos:** padrão do módulo.

### RF-LIVE-002 — Execução isolada em 2 fases com SSE
**Descrição detalhada:** `POST /api/run/{id}` cria workspace UUID (com `AUTOTAREFAS_HOME` próprio), agenda a execução e devolve `{token, stream_url}`; `GET /api/stream/{token}` transmite stdout linha a linha via SSE com evento final done/timeout; `GET /api/result/{token}` para reconexão; `GET /api/download/{token}/{name}` só serve **arquivos diretos de `out/` com nome simples** (anti path traversal); artefatos de subpastas são zipados (ex.: pacote de execução).
**Critérios de aceite:** reconectar no meio recupera o resultado; download de `../` recusado.
**Testes:** `live_demo/backend/tests/test_engine.py` (567 linhas), `test_streaming.py`.
**Prioridade:** OBRIGATÓRIO V1. **Status:** CONCLUÍDO. **Evidências:** `main.py` (264), `engine.py` (403), `jobs.py`, `streaming.py`. **Demais campos:** padrão do módulo.

### RF-LIVE-003 — Segurança do Live
**Descrição detalhada:** rate limit 12 req/min/IP; máx. 4 execuções simultâneas + 40 workspaces (TTL 15 min); timeout 60 s com kill (exit 124); stream limitado a 2.000 linhas/256 KB; upload ≤10 MB, ≤50 arquivos, allowlist de extensões por automação; sanitização de nomes; subprocesso **sem shell** com argv 100% do servidor; **egress lockdown** por proxy morto (`HTTP_PROXY` inválido + `NO_PROXY=127.0.0.1,localhost`) ligado por padrão; visitante nunca fornece caminho/comando/URL.
**Critérios de aceite:** todos os limites acima verificados por teste (suite 127); automação tentando sair para a internet falha.
**Prioridade:** OBRIGATÓRIO V1. **Status:** CONCLUÍDO. **Evidências:** `config.py`, `ratelimit.py`, `uploads.py`, `sanitize.py`, `engine.py` (linhas 143–152 do lockdown). **Demais campos:** padrão do módulo.

### RF-LIVE-004 — Jornada guiada de planilhas
**Descrição detalhada:** ver 02 §2; aceita exemplo, upload, perfil embutido ou **YAML próprio ≤256 KB**; mesmo token do fluxo clássico; upload nunca baixável; `config/` fora de `out/`; `schema_efetivo.yaml` no pacote.
**Critérios de aceite:** os 4 caminhos de schema chegam à validação; YAML inválido → erro campo a campo sem executar.
**Testes:** `live_demo/backend/tests/test_spreadsheets.py` (1002 linhas); front `SpreadsheetJourney.test.tsx` (14 testes).
**Prioridade:** OBRIGATÓRIO V1. **Status:** CONCLUÍDO. **Evidências:** `live_demo/backend/app/spreadsheets.py` (799 linhas) + componentes `Spreadsheet*` do front. **Demais campos:** padrão do módulo.

### RF-LIVE-005 — Mocks determinísticos internos
**Descrição detalhada:** ver 02 §4; gerenciados no lifespan (`demo_servers.py`, autostart configurável); saúde exposta no `/api/health`.
**Critérios de aceite:** health acusa mock morto; catálogo sempre com os mesmos 47 produtos.
**Testes:** `tests/tools/demo_server/` (5 arquivos, 68 funções).
**Prioridade:** OBRIGATÓRIO V1. **Status:** CONCLUÍDO. **Evidências:** `tools/demo_server/{app,storage}.py`, `tools/smtp_debug.py`. **Demais campos:** padrão do módulo.

### RF-LIVE-006 — Ativação dos cards "em breve"
**Objetivo:** vitrine sem promessas penduradas.
**Descrição detalhada (alvo):** para cada um dos 6 (sync_api, send_email, extract_web_js, rpa_cadastro, report, dashboard): ramo em `build_argv`, inclusão na régua, teste de engine, ajuste de front se houver saída específica. Custos distintos: **baratos** (sync_api, send_email, report, dashboard — mocks/saídas prontos) vs **caros** (extract_web_js, rpa_cadastro — Chromium no servidor).
**Critérios de aceite:** card ativado executa com exemplo em 1 clique e todos os downloads funcionam.
**Desdobramento aprovado em 10/08/2026:** **LIVE-006a** — ativar `sync_api`, `send_email`, `report` e `dashboard`: RECOMENDADO V1, Fase A3, não bloqueia o release. **LIVE-006b** — `extract_web_js` e `rpa_cadastro`: por **DP-02**, ficam **fora da V1 pública** como executáveis; o ajuste da vitrine (retirar a promessa de execução e publicar a demonstração em vídeo/GIF) é a subetapa **A4**, obrigatória antes do release; a execução pública com Chromium é reavaliada na **Fase D4**, após a definição da hospedagem. Nenhum código ou teste existente é removido.
**Prioridade:** LIVE-006a RECOMENDADO V1; LIVE-006b PÓS-V1 (com o ajuste de vitrine A4 dentro da V1). **Fase:** A3 / A4 / D4. **Status:** NÃO INICIADO.
**Evidências da lacuna:** `build_argv` cobre só 7 ids (KeyError nos demais). **Demais campos:** padrão do módulo.

### RF-LIVE-007 — Frontend integrado
**Descrição detalhada:** React 18 + Vite + TS + Tailwind 3.4 consumindo somente APIs reais (`/api/health`, `/api/catalog`, `/api/run`, `/api/stream`, `/api/sample`, `/api/spreadsheets/*`); terminal ao vivo, artefatos com download, resumos específicos (Validation/Import/Extract), jornada em etapas, estados de erro/offline, ErrorBoundary.
**Critérios de aceite:** typecheck e build verdes; teste de regressão "não desmonta com payload real" presente e verde.
**Testes:** **52 passed na árvore local (A1, 10/08/2026)** — 22 em `src/lib/spreadsheets.test.ts`, 16 em `src/components/SpreadsheetProfileMapping.test.tsx`, 14 em `src/components/SpreadsheetJourney.test.tsx`; typecheck e build aprovados. Histórico: o zip de 05/08 executava 31 (17 + 14).
**Prioridade:** OBRIGATÓRIO V1. **Status:** CONCLUÍDO. **Evidências:** `live_demo/frontend/src/` (24 componentes, 5 hooks, libs); typecheck/build/audit verdes também no zip (00 §4).
**Lacunas:** `src/lib/spreadsheets.test.ts` (22 testes) não aparece em `git ls-files` nem entre os não rastreados — risco R-18, confirmação na subetapa A1.2. **Demais campos:** padrão do módulo.
