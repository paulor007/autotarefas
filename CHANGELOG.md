# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere a [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Não lançado]

Em desenvolvimento. Próxima: notificações via mensagem (ex: Telegram).

---

## [1.1.0] — 2026-06-10

🕸️ **Web scraping!** Nova capacidade de extracao para sites que NAO
expoem API: o comando `extract web` raspa paginas HTML por seletores
CSS, segue a paginacao e salva em CSV/XLSX/JSON — espelhando o
`extract api`. A decima task do projeto.

### Adicionado

#### Extracao via web scraping

- **`autotarefas.tasks.extract_web`** — decima task:
  - `ExtractWebTask(BaseTask)`: busca o HTML (httpx), extrai linhas por
    seletores CSS (BeautifulSoup) e segue a paginacao automaticamente
  - Campos declarativos: `row_selector` + `fields` ({coluna: seletor})
  - Paginacao via `next_selector` (resolve hrefs relativos com urljoin;
    protecao anti-loop)
  - Saida CSV/XLSX/JSON; retry so em erros temporarios (5xx/timeout);
    dry-run (1a pagina, sem salvar)
  - User-Agent honesto; `delay` entre paginas (rate limit)
- **Comando `autotarefas extract web`**:
  - Subcomando do grupo `extract` (ao lado de `api`)
  - `--row-selector`, `--field coluna=seletor` (repetivel),
    `--next-selector`, `--max-pages`, `--delay`, `--timeout`,
    `--max-retries`
  - Exit codes (0/1/2); valida a URL e o formato dos campos

#### Demo

- Pagina **`/catalogo`** no servidor demo: catalogo de produtos paginado
  (HTML estatico, deterministico) — alvo de teste para o `extract web`

#### Testes

- ~49 testes novos (catalogo + ExtractWebTask + comando extract web):
  parsing por seletores, paginacao (segue/limita/anti-loop), dry-run,
  0 itens, retry e o parse de `--field` na CLI

### Mudado

- **Nova dependencia**: `beautifulsoup4` (parser `html.parser` da stdlib,
  sem `lxml`) — uma dependencia so
- README e roadmap atualizados com a secao de web scraping

### Estatisticas

- **10 comandos** (incl. `extract web`) · **10 tasks** (`BaseTask`) ·
  **~1081 testes** · **~92% de cobertura** · **0 erros** em mypy / ruff / bandit

---

## [1.0.0] — 2026-06-06

🏆 **Versão estável!** O AutoTarefas chega à 1.0.0 com a infraestrutura
que faltava para um projeto maduro: **sincronização entre APIs**,
**integração contínua** (CI/CD) e **documentação publicada**. As nove
tasks agora rodam sob uma suíte de 1032 testes, verificada
automaticamente a cada push em Python 3.12 e 3.13.

### Adicionado

#### Sincronizacao API->API

- **`autotarefas.tasks.sync_api`** — nona task real:
  - `SyncApiTask(BaseTask)`: extrai de uma API origem e envia para uma
    API destino, num passo so
  - **Composicao**: reaproveita `ExtractApiTask` + `SendApiTask` (nao
    reimplementa HTTP, paginacao nem retry), ligadas por um arquivo
    intermediario temporario descartado ao final
  - **Curto-circuito**: se a extracao falha, o envio nem comeca
  - Status agregado do envio: `SUCCESS` / `PARTIAL` / `FAILURE`
  - **dry-run**: testa a origem (pagina 1) sem enviar
- **Comando `autotarefas sync api`**:
  - Novo grupo `sync` (ao lado de `extract` e `send`)
  - `--source-url`/`--dest-url`, autenticacao por lado
    (`--source-api-key`, `--dest-api-key`, `--dest-bearer`),
    `--per-page`, `--max-pages`, `--delay`, `--timeout`,
    `--max-retries`, `--report`, `--format` (csv/xlsx)
  - Progresso colorido + exit codes (`0`/`1`/`2`); valida ambas as URLs

#### Integracao continua (CI/CD)

- **`.github/workflows/ci.yml`** — pipeline a cada push e pull request:
  - Matriz Python **3.12** e **3.13**
  - `ruff check` + `ruff format --check` + `mypy src/` +
    `bandit -r src` + `pytest` (cobertura minima de 85%)
  - `concurrency` com cancelamento de execucoes antigas
- Badge de CI no README

#### Documentacao

- **MkDocs Material** publicado no **GitHub Pages**:
  <https://paulor007.github.io/autotarefas/>
  - Paginas: inicio, comandos, arquitetura, desenvolvimento
  - **Referencia de API gerada das docstrings** (via `mkdocstrings`)
- **`.github/workflows/docs.yml`** — build (`mkdocs build --strict`) e
  deploy automatico no Pages (modo GitHub Actions, sem branch `gh-pages`)
- Badge de Docs no README

#### Testes

- **`conftest.py`** — isola o banco de audit em diretorio temporario por
  teste; a suite nunca grava no audit real
- ~50 testes novos da sincronizacao (`SyncApiTask` + comando `sync api`):
  caminho feliz, curto-circuito, parcial/falha, dry-run, limpeza do
  arquivo temporario e propagacao de parametros

### Mudado

- **Versao dinamica**: o build (`hatchling`) passa a ler a versao de
  `src/autotarefas/__init__.py` (`[tool.hatch.version]`) — fonte unica,
  fim da divergencia entre `pyproject.toml` e o pacote
- **`ruff` fixado em `0.15.14`** no `pyproject.toml` e no
  `.pre-commit-config.yaml` — CI e pre-commit usam exatamente a mesma
  versao (formatacao reproduzivel)
- README reescrito com badges de CI e Docs, secoes de Sincronizacao e
  Documentacao, e o roadmap atualizado

### Corrigido

- Teste de CLI do backup tornado tolerante a quebra de linha do Rich
  (caminhos longos eram quebrados em varias linhas, falhando o `assert`)

### Estatisticas

- **9 comandos** · **9 tasks** (`BaseTask`) · **1032 testes** ·
  **~92% de cobertura** · **0 erros** em mypy strict / ruff / bandit

---

## [0.8.0] — 2026-06-03

📧 **Notificacoes por Email!** O AutoTarefas agora le uma planilha de
destinatarios e envia um email **personalizado por linha**, via SMTP. O
assunto e o corpo aceitam {coluna}: trechos como {nome} sao trocados
pelos valores da linha.

Com isso o robo cobre tambem a comunicacao: alem de cadastrar, extrair e
enviar dados, ele **notifica** pessoas a partir de uma planilha.

### Adicionado

#### Notificacoes por Email

- **`autotarefas.tasks.send_email`** — oitava task real:
  - `SmtpConfig` (dataclass): host, port, usuario, senha, usar_tls
  - `SendEmailTask(BaseTask)`: le uma planilha e envia 1 email por linha
    via `smtplib` + `email.message` (ambos da stdlib)
  - **Templates** {coluna} no assunto e no corpo (faltante -> "")
  - **Conexao reaproveitada**: um login para todos os envios
  - **Tolerancia a falhas por linha**: um email ruim nao interrompe os
    demais; erro de conexao/login = falha geral
  - **Rate limiting** (`delay_s`), STARTTLS e autenticacao opcionais
  - **Corpo texto ou HTML** (`is_html`)
  - **Relatorio opcional** (CSV/XLSX/JSON) com `_resultado`/`_mensagem`
  - **dry-run**: nao conecta; mostra um preview dos emails
  - Status agregado: `SUCCESS` / `PARTIAL` / `FAILURE`

- **Comando `autotarefas send email`**:
  - Subcomando do grupo `send` (ao lado de `send api`)
  - Opcoes SMTP (`--smtp-host`, `--smtp-port`, `--from`, `--user`,
    `--no-tls`), conteudo (`--subject`, `--body`/`--body-file`,
    `--email-column`, `--html`), `--delay`, `--timeout`, `--report`
  - Progresso linha a linha colorido (OK/FALHA) + exit codes
    (`0` success/partial, `1` failure, `2` erro de uso)

#### Ambiente de teste

- **`tools/smtp_debug.py`** — servidor SMTP de debug local (via
  `aiosmtpd`): recebe emails sem envia-los para a internet, mostra no
  console e salva como `.eml`. Alvo de teste para a `SendEmailTask`.

#### Testes

- ~51 testes novos: `SendEmailTask` (envio, template, parcial, falha de
  conexao, dry-run, relatorio, HTML) e o comando CLI (corpo, exit codes,
  flags). `smtplib.SMTP` trocado por um fake que captura emails e simula
  falhas; senha testada via env var e via prompt mockados.

### Segurança

- **Senha SMTP nunca na linha de comando** — vem da env var
  `AUTOTAREFAS_SMTP_PASSWORD` ou de um prompt oculto (`getpass`)
- **Senha fora de logs/audit/relatorio** — transita apenas pela conexao
- **Aviso de TLS** — alerta ao logar sem TLS em host externo

### Dependências

- **Core sem novas dependencias** — `smtplib` e `email` sao da stdlib.
- **`aiosmtpd`** adicionado ao extra `demo` (apenas para o servidor de
  teste local; nao e usado pelo codigo de envio).

### Estatísticas

- **~870 testes** (vs ~820 em v0.7.0)
- **8 subclasses de BaseTask** (+ `SendEmail`)
- **Grupo `send`** com 2 subcomandos: `api` e `email`
- **0 erros** em mypy strict, ruff, bandit

### Lições aprendidas notáveis

- **`message_from_bytes()` retorna `Message`, nao `EmailMessage`**: para
  usar `.get_body()`/`.get_content()` sem erro de mypy, usar
  `BytesParser(policy=...).parsebytes()` + `cast(EmailMessage, ...)`.
- **`aiosmtpd` nao tem stubs**: `ignore_missing_imports = true` nos
  overrides do mypy.
- **Conexao SMTP stateful**: ao contrario do POST por linha (HTTP), no
  email abre-se uma conexao e reaproveita-se para todos os envios.
- **Senha via env var/prompt, nunca CLI**: argumento de linha de comando
  vaza no historico do shell e em logs de processo.
- **`mypy` strict do projeto cobre `tools/` tambem** (nao so `src/`).

### Anotado para o futuro

- **Web scraping** (`extract web`), v0.9.0
- **Sincronizacao** (extract + send combinados), rumo a v1.0.0
- **Mensagens** (SMS/WhatsApp) — dependem de servicos externos

---

## [0.7.0] — 2026-06-02

📤 **Envio de Dados via API!** O complemento da v0.6.0: se a extração
_le_ dados de uma API, o envio _escreve_ dados em sistemas externos. O
AutoTarefas agora le uma planilha e faz **POST de cada registro** numa
API REST — o caminho profissional para cadastro em massa (muito mais
rapido que automacao via navegador).

Com isso, o projeto fecha o ciclo de **entrada e saida de dados**:
`extract` (puxar de fora) e `send` (empurrar pra dentro).

### Adicionado

#### Envio via API

- **`autotarefas.tasks.send_api`** — setima task real:
  - `SendApiTask(BaseTask)`: le uma planilha (CSV/XLSX) e faz POST de
    cada linha para uma API
  - **Tolerancia a falhas por linha**: uma linha ruim nao interrompe as
    demais (igual ao RPA)
  - **Retry com backoff exponencial** (`tenacity`): so em erros
    TEMPORARIOS (timeout, conexao, HTTP 5xx). Erros 4xx (400/409/422)
    NAO sao retentados — sao erros do dado, registrados como falha da linha
  - **Rate limiting**: pausa configuravel (`delay_s`) entre envios
  - **Autenticacao opcional**: header `X-API-Key` e/ou Bearer token
  - **Relatorio opcional** (CSV/XLSX/JSON): resultado de cada linha, com
    colunas `_resultado` e `_mensagem`
  - **dry-run**: conta as linhas sem enviar
  - Status agregado: `SUCCESS` (todas) / `PARTIAL` (algumas) / `FAILURE`

- **Comando `autotarefas send api`**:
  - Grupo `send` (simetrico ao `extract`)
  - Opcoes: `--planilha`, `--url`, `--api-key`, `--bearer`, `--delay`,
    `--timeout`, `--max-retries`, `--report`
  - Progresso linha a linha colorido (OK/FALHA) + exit codes
    (`0` success/partial, `1` failure, `2` erro de uso)
  - Aviso de seguranca ao enviar credencial sobre `http://` externo

#### Sistema demo estendido

- **`tools/demo_server`**: `POST /api/clientes` — cria cliente via JSON,
  valida os campos, detecta duplicata por CPF. Status semanticos:
  `201` criado, `400` JSON invalido, `422` validacao, `409` duplicata.

#### Testes

- ~48 testes novos: `SendApiTask` (envio, parcial, falha, retry,
  relatorio, auth, progresso) e o comando CLI (validacao, exit codes,
  propagacao de flags, aviso de seguranca). Sem rede: `httpx.post`
  mockado com `httpx.Response` reais e `tenacity.nap.sleep` mockado.

### Segurança

- **Credenciais fora de logs e audit** — `--api-key`/`--bearer` vao so
  no header
- **Aviso de TLS** — alerta ao enviar credencial sobre `http://` externo
- **Retry seletivo** — 4xx nao e retentado (evita reenvio inutil de
  dados duplicados/invalidos)

### Dependências

- **Nenhuma nova** — `httpx`, `tenacity` e `pandas` ja presentes.

### Estatísticas

- **~820 testes** (vs ~775 em v0.6.0)
- **7 subclasses de BaseTask** (+ `SendApi`)
- **9 comandos CLI** (+ grupo `send`)
- **3 grupos de comandos**: `rpa`, `extract`, `send`
- **0 erros** em mypy strict, ruff, bandit

### Lições aprendidas notáveis

- **Retry distingue erro do dado de erro temporario**: 4xx (duplicata,
  validacao) nao deve ser retentado; 5xx/timeout sim. Isso torna o envio
  em massa eficiente.
- **Tolerancia por linha + relatorio**: numa carga de 1000, registrar
  cada falha (com motivo) num arquivo separado e mais util que abortar
  tudo no primeiro erro.
- **PowerShell 5.x nao tem `-SkipHttpErrorCheck`** (so PS 7+): para
  testar respostas 4xx, usar `try/catch` com
  `[int]$_.Exception.Response.StatusCode`.
- **pre-commit `mixed-line-ending`**: colar codigo pode misturar
  CRLF/LF; o hook corrige sozinho — depois `git add` e recommit. Um
  `.gitattributes` com `* text=auto eol=lf` previne.
- **`_is_retryable` duplicado de proposito** entre send e extract: evita
  acoplar as tasks; poderia virar um helper compartilhado no futuro.

### Anotado para o futuro

- **Notificacoes por Email** (proxima fase, v0.8.0)
- **Web scraping** (`extract web`), v0.9.0
- **Mensagens** (SMS/WhatsApp) — dependem de servicos externos

---

## [0.6.0] — 2026-05-29

🔌 **Extração de Dados via API!** O complemento natural da Fase 8: se o
RPA _insere_ dados em sistemas web (cadastro), a extração _lê_ dados de
fontes externas. O AutoTarefas agora consome **APIs REST paginadas** e
salva tudo em CSV, XLSX ou JSON — com paginação automática, retry
resiliente e controle de taxa.

> Escopo desta fase: **somente API**. Web scraping (`extract web`,
> reaproveitando o `BrowserSession` da Fase 8) fica anotado para uma
> versão futura.

### Adicionado

#### Extração via API (Fase 9)

- **`autotarefas.tasks.extract_api`** — sexta task real:
  - `ExtractApiTask(BaseTask)`: consome uma API paginada e salva em arquivo
  - **Paginação automática**: segue `has_next` até o fim (com limite de
    segurança de 10.000 páginas contra loop infinito)
  - **Retry com backoff exponencial** (`tenacity`): só em erros
    TEMPORÁRIOS (`httpx.TransportError` — timeout/conexão — e HTTP 5xx);
    **4xx propaga** (não adianta retentar URL errada ou auth inválida)
  - **Rate limiting**: pausa configurável (`delay_s`) entre páginas
  - **Output multi-formato**: CSV / XLSX / JSON, decidido pela extensão
    do arquivo de saída
  - **Autenticação opcional**: header `X-API-Key` (enviado só no header,
    nunca no log nem no audit)
  - **dry-run**: busca apenas a primeira página (preview do total), sem salvar
  - Callback `on_progress` para acompanhamento página a página

- **Comando `autotarefas extract api`**:
  - Grupo `extract` (preparado para um futuro subcomando `web`)
  - Opções: `--url`, `--output`, `--per-page`, `--max-pages`, `--delay`,
    `--api-key`, `--timeout`, `--max-retries`
  - Progresso em tempo real + exit codes (`0` sucesso, `1` falha,
    `2` erro de uso)
  - Aviso de segurança ao usar `--api-key` sobre `http://` externo (sem TLS)

#### Sistema demo estendido

- **`tools/demo_server`**:
  - `GET /api/clientes?page=N&per_page=N`: API paginada (JSON com `data`,
    `page`, `per_page`, `total`, `total_pages`, `has_next`)
  - `POST /seed?n=N&clear=bool`: popula o storage com clientes fake
    (**Faker** locale pt_BR) — dados realistas para testar a paginação
  - `Storage.create_many()`: criação em massa numa única escrita

#### Testes

- ~53 testes novos: `ExtractApiTask` (paginação, formatos, dry-run,
  retry, `_is_retryable`, auth, progresso) e o comando CLI (validação de
  URL, exit codes, propagação de flags, aviso de segurança).
- Estratégia sem rede: `httpx.get` mockado com `httpx.Response` **reais**
  (raise_for_status/json autênticos) e `tenacity.nap.sleep` mockado para
  testes de retry instantâneos.

### Segurança

- **API key fora de logs e audit** — enviada exclusivamente no header
- **Aviso de TLS** — ao mandar `--api-key` sobre `http://` externo, o CLI
  alerta que a chave trafegaria sem criptografia (mas não bloqueia: a
  decisão é do operador)
- **Limite de segurança de páginas** — guarda contra APIs que retornem
  `has_next: true` indefinidamente (bug do servidor)

### Dependências

- **Nenhuma nova** — `httpx`, `tenacity` e `pandas` já estavam presentes.

### Estatísticas

- **~775 testes** (vs ~720 em v0.5.0)
- **6 subclasses de BaseTask** (+ `ExtractApi`)
- **8 comandos CLI** (+ `extract`)
- **0 erros** em mypy strict, ruff, bandit

### Lições aprendidas notáveis

- **Retry seletivo**: distinguir erro temporário (timeout, 5xx → vale
  retentar) de erro do cliente (4xx → não adianta) é o que separa um
  retry útil de um que só multiplica chamadas inúteis.
- **`tenacity.Retrying` (objeto) > `@retry` (decorator)** quando os
  parâmetros dependem de `self` (ex.: `max_retries` configurável).
- **`httpx.Response` real em testes** faz `raise_for_status()` e
  `.json()` se comportarem como em produção — sem fingir.
- **`tenacity.nap.sleep` mockado** torna testes de retry instantâneos.
- **Ativar o grupo `PLR` herda `PLR0913`** (máx. 5 args): tasks de
  configuração e comandos Click legitimamente têm muitos parâmetros →
  exceção via `per-file-ignores` ou `# noqa` pontual.
- **`RUF100`**: um `# noqa` para uma regra que não está no `select`
  vira "unused noqa" — habilite a regra ou remova o noqa.
- **`dict[str, object]` > `dict`** no modo estrito do mypy (`type-arg`).
- **Raw string em docstring** (`r"""..."""`) quando há caminhos
  Windows/PowerShell, para evitar `W605` (escape inválido como `\P`).

### Anotado para o futuro

- **`extract web`** (web scraping) reaproveitando o `BrowserSession` da
  Fase 8 — possível v0.6.x incremental ou v0.7.

---

## [0.5.0] — 2026-05-26

🤖 **Automação Web (RPA) + Sistema Demo!** O AutoTarefas deixa de ser
apenas utilidades de arquivos e vira um **robô de automação web**
(Fase 8). Agora cadastra registros em sistemas web a partir de uma
planilha, usando um navegador real.

Este release também **corrige um bug crítico** descoberto durante o
desenvolvimento: o audit trail não estava registrando as tasks reais
(`validate`, `backup`, `organize`, etc.) — apenas comandos legados como
`init`. A descoberta veio justamente ao usar o `report` da v0.4.0 contra
o histórico de uma execução de RPA.

### Adicionado

#### Sistema Demo Local (Fase 8 etapa 1)

- **`tools/demo_server/`** — mini servidor Flask que simula um sistema
  de cadastro corporativo, usado como **alvo controlado** das automações
  durante o desenvolvimento (ninguém é prejudicado se quebrar):
  - Endpoints: `/` (landing), `/cadastro` (GET form / POST cria),
    `/sucesso/<id>`, `/cadastros` (lista JSON), `/limpar` (reset),
    `/health` (health check)
  - Validações server-side: nome (≥3 chars), email (regex), CPF
    (formato `XXX.XXX.XXX-XX`), telefone opcional (`(XX) XXXXX-XXXX`)
  - Storage local em JSON com `threading.Lock` (suporta requests
    paralelos)
  - IDs sequenciais e seletores estáveis (`#btn-cadastrar`,
    `#record-id`) pensados para a automação
  - Roda com `python -m tools.demo_server` em http://localhost:5555
  - Pasta `tools/` fica **fora** de `src/` (não é parte do pacote)

#### Wrapper Playwright (Fase 8 etapa 2)

- **`autotarefas.core.browser`** — abstração sobre o Playwright:
  - `BrowserSession`: context manager com cleanup garantido (browser
    fecha mesmo em erro)
  - Helpers de navegação: `go_to`, `fill`, `click`, `wait_for`
  - Helpers de inspeção: `text`, `is_visible`, `current_url`
  - Screenshots normais e com **mascaramento automático** de campos
    sensíveis (mask nativo do Playwright cobre CPF/CNPJ/senha/token/
    cartão com cor sólida, sem modificar o DOM real)
  - 11 seletores sensíveis default (case-insensitive)
  - Suporta Chromium (default), Firefox, WebKit; headless por default
    com flag para modo headful
  - `verify_playwright_installed()`: helper de troubleshooting
  - **Não** exportado em `core/__init__.py` (evita quebrar projetos sem
    o extra `[rpa]` instalado)

#### RPA Cadastro (Fase 8 etapa 3)

- **`autotarefas.tasks.rpa_cadastro`** — quinta task real:
  - `RPACadastroTask(BaseTask)`: lê planilha CSV/XLSX e cadastra cada
    linha em um sistema web
  - **Health check** via `httpx` antes de iniciar (servidor offline →
    `SKIPPED`, não tenta nada)
  - **Tolerante a falhas por linha**: uma linha ruim não interrompe as
    demais
  - Validação local de CPF (reusa `validators_br` da Fase 3) antes de
    gastar I/O com o browser
  - Status por linha: `success` / `skipped` / `error`
  - **CPF inválido** → `skipped`; **CPF duplicado** (detectado pela
    resposta do servidor) → `skipped`; **erro técnico** → `error` +
    screenshot mascarada automática
  - `dry_run` não abre browser nem faz requests (pula health check) —
    apenas valida e simula (`would_create`/`would_skip`)
  - Limite de 100 operations no `result.data` (audit não infla)
  - Callback `on_progress` opcional para progresso em tempo real
  - Status agregado: `SUCCESS` / `PARTIAL` / `FAILURE` / `SKIPPED`

#### Comando CLI (Fase 8 etapa 4)

- **Grupo `rpa`** preparado para subcomandos futuros (`consulta`,
  `exportar`)
- **Comando `autotarefas rpa cadastro`**:
  - `--planilha, -p`, `--site, -s`
  - `--show-browser` (mostra navegador; default headless)
  - `--no-screenshot` (desabilita screenshots em erro)
  - `--allow-remote` (permite URLs não-locais)
  - Progresso linha a linha em tempo real + sumário formatado ao final
  - Exit codes: `0` (success/partial/skipped), `1` (failure), `2` (erro
    de uso: URL inválida, etc.)

#### Testes (Fase 8 etapa 5)

- **~118 testes novos** cobrindo toda a fase, sem abrir browser real:
  - Demo server (Flask `test_client`, storage com `tmp_path`,
    concorrência com threads)
  - `BrowserSession` (Playwright 100% mockado)
  - `RPACadastroTask` (mock de `BrowserSession` e `httpx`, CSVs reais)
  - Comando CLI (`CliRunner` via grupo principal, mock da task)
  - Integração de audit no `BaseTask`

### Corrigido

- **Audit trail uniforme** — `BaseTask.run()` agora chama
  `_record_audit()` automaticamente. Antes, **apenas comandos legados**
  (como `init`) gravavam no audit; tasks que herdam de `BaseTask`
  (`validate`, `backup`, `organize`, `report_audit`, `rpa_cadastro`)
  **não eram registradas** — bug presente desde a Fase 1, mascarado
  porque nenhum consumidor lia o audit até a Fase 7. Agora toda execução
  (sucesso, falha, parcial, dry-run, skipped) é auditada. Erro na
  gravação do audit não interrompe a task (try/except defensivo).

### Segurança

- **RPA restrito a hosts locais por default** — o comando `rpa cadastro`
  só aceita URLs `localhost`/`127.0.0.1`/`::1` salvo uso explícito de
  `--allow-remote` (fail-safe default: automação contra sistema real
  exige ação consciente do operador)
- **Mascaramento de campos sensíveis em screenshots** — capturas de tela
  cobrem automaticamente CPF, CNPJ, senha, token, cartão etc., evitando
  vazamento de dados em imagens de debug

### Dependências

- Novo extra opcional **`demo`**: `flask>=3.0` (servidor demo, apenas
  desenvolvimento)
- Novo extra opcional **`rpa`**: `playwright>=1.40` (automação web).
  Requer `playwright install chromium` após instalar.

### Estatísticas

- **~720 testes** (vs ~610 em v0.4.0)
- **5 subclasses de BaseTask** (Validate, Backup, Organize, ReportAudit,
  **RPACadastro**)
- **7 comandos CLI** (info, init, validate, backup, organize, report,
  **rpa**)
- **0 erros** em mypy strict, ruff, bandit
- Servidor demo + wrapper de browser reutilizável

### Lições aprendidas notáveis

- **Audit no caminho crítico, não opcional**: features centrais
  (auditoria, segurança) devem estar no _template method_ da classe
  base, não em hooks que cada subclasse pode esquecer. Features que
  produzem dados sem consumidor mascaram bugs por muito tempo —
  construir o consumidor cedo (o `report`) forçou a integridade.
- **`@pytest.mark.usefixtures("_fixture")`** para fixtures _side-effect_
  (que só fazem `monkeypatch` e retornam `None`): resolve `PT004`
  (prefixo `_`) e `PT019` (não injetar como parâmetro) de uma vez.
- **`importlib.import_module("pkg.module")`** quando o pacote só exporta
  `__all__`: evita o erro do mypy "does not explicitly export" e deixa
  claro que se quer o **módulo** (para `monkeypatch`), não um atributo.
- **`pythonpath = [".", "src"]`** no pytest quando há código fora de
  `src/` (como `tools/`).
- **Cobertura de um arquivo**: usar `--cov=src/pkg/module` (caminho), não
  `--cov=pkg.module.name` (nome pontilhado, que pode dar `KeyError` no
  import durante o tracking).
- **`cast(T, valor)` > `# type: ignore[no-any-return]`** ao retornar
  valor de um `dict[str, Any]`.
- **`PT022`**: fixture com `yield` sem teardown deve usar `return` (e o
  tipo de retorno muda de `Generator[...]` para o tipo direto).
- **Mock encadeado do Playwright**: `monkeypatch.setattr` em
  `sync_playwright` no módulo permite testar `BrowserSession` sem abrir
  browser real (CI não precisa de `playwright install`).
- **`mask` nativo do Playwright** cobre regiões da página na screenshot
  sem modificar o DOM — mais limpo que injetar CSS.
- **`curl` no PowerShell** é alias de `Invoke-WebRequest` (sintaxe
  diferente); usar `curl.exe` ou `Invoke-RestMethod` para testar APIs.
- **CPF duplicado = `skipped`, não `error`**: erro de RPA é falha técnica
  (timeout, crash); dado ruim é responsabilidade do operador.

---

## [0.4.0] — 2026-05-23

🎉 **Segurança Transversal + Relatórios Consolidados!** Release que
**fortalece** as bases do projeto (Fase 6) e dá **voz** ao audit trail
que estava silenciosamente registrando tudo (Fase 7).

Este release adiciona **uma vulnerabilidade real corrigida** (path
traversal no organize), **documento profissional de segurança**
(SECURITY.md), e **comando novo** `autotarefas report` que gera
estatísticas, listas ou apenas falhas do histórico.

### Adicionado

#### Segurança Transversal (Fase 6)

- **`autotarefas.core.security`** — 4 helpers novos:
  - `validate_filename(name)`: 7 camadas defensivas (vazio, tamanho,
    path separators, traversal, chars de controle, chars proibidos
    Windows, nomes reservados CON/PRN/AUX/NUL/COM1-9/LPT1-9)
  - `safe_extension(filename, allowed)`: whitelist case-insensitive,
    detecta trick `.pdf.exe`
  - `is_within_directory(child, parent)`: versão "soft" do `safe_path`
    (retorna bool, não levanta exceção)
  - `mask_sensitive_in_dict(data)`: mascara CPF/CNPJ/senhas/tokens em
    dicts (recursivo, não modifica original, substring match)

- **Constantes privadas**: `_SENSITIVE_KEYS` (frozenset),
  `_WINDOWS_RESERVED_NAMES`, `_FORBIDDEN_FILENAME_CHARS`,
  `_MAX_FILENAME_LENGTH=255`

- **`SECURITY.md`** na raiz do repo:
  - Política de versões suportadas
  - Processo de reporting de vulnerabilidades (responsible disclosure)
  - **Threat model**: em escopo + fora de escopo + suposições
  - 13 princípios de segurança documentados
  - 4 camadas de proteção (filesystem, network, secrets, audit)
  - Hardening de dependências (`pip-audit`, `bandit`)
  - Best practices pra contribuidores (faça/evite)
  - GitHub auto-detecta o arquivo e exibe na aba Security

#### Vulnerabilidade real corrigida

- **`tasks/organize.py`** — Path traversal via destination malicioso:
  rule com `destination: "../../etc"` poderia mover arquivos pra fora
  de `target_root`. **Corrigido** com `safe_path` em
  `_resolve_destination`.

#### Relatórios Consolidados (Fase 7)

- **`autotarefas.tasks.report_audit`** — Task de relatórios:
  - `ReportAuditTask(BaseTask)`: quarta subclasse real
  - `ReportFilters` (dataclass frozen+slots) com `__post_init__`:
    validações de `limit > 0` e `since < until`
  - `ReportType = Literal["summary", "list", "errors"]`
  - 3 tipos de relatório:
    - `summary` (default): contagens, médias, falhas recentes
    - `list`: lista detalhada de execuções
    - `errors`: apenas execuções com falha (`failure` + `partial`)
  - Filtros: `task_name`, `status`, `since`, `until`, `limit` (default 100)
  - **Read-only**: apenas `SELECT`s no audit DB (princípio append-only
    preservado)
  - `TaskStatus.SKIPPED` quando audit DB não existe (não é erro)
  - SQL parametrizado anti-injection com `WHERE 1=1` + `AND` condicional
  - Aggregations: `by_task`, `by_status`, `by_task_and_status`
    (cross-tab), `avg_duration_ms_by_task` (round 2 casas)
  - `recent_failures`: top 5 com `status` em `failure`/`partial`
  - `audit_db_path` opcional no construtor (backward-compatible)

- **Comando `autotarefas report`**:
  - `autotarefas report` (summary das últimas 24h por default)
  - `--task NAME`, `--status STATUS`, `--days N`, `--since DATE`,
    `--until DATE`
  - `--type summary | list | errors`
  - `--format table | json | csv`
  - `--output PATH` (salva em arquivo)
  - `--limit N`
  - Tabelas formatadas manualmente (portável, sem deps de Rich Table)
  - `_format_size()` humaniza durações (`450ms`, `1.20s`)
  - `--since` sobrescreve `--days`
  - `tzinfo=UTC` automático em datetimes do Click
  - Dry-run mostra no terminal sem salvar arquivo
  - Aviso quando truncar em `--limit`
  - Exit codes: 0 (sucesso/skipped), 1 (falha), 2 (filtros inválidos)

### Estatísticas

- **~610 testes** (vs ~485 em v0.3.0), cobertura mantida
- **~5400 linhas de código** em src/ (vs ~4500)
- **4 subclasses de BaseTask** (Validate, Backup, Organize, ReportAudit)
- **6 comandos CLI** (info, init, validate, backup, organize, report)
- **0 erros** em mypy strict, ruff, bandit
- **+1 documento** profissional (SECURITY.md)

### Lições aprendidas notáveis

- **`# pragma: allowlist secret`** marca falso positivo do
  `detect-secrets` (use em testes com dados claramente fake)
- **Ruff vs Bandit em supressão**: ferramentas distintas, comentários
  distintos. Pra mesma regra, use ambos: `# noqa: S608 # nosec B608`
- **Pydantic computed properties** bloqueiam `monkeypatch.setattr` no
  objeto. Solução: substituir o nome do módulo
  (`monkeypatch.setattr("modulo.atributo", fake)`)
- **Click subcommands precisam de grupo pai** pro `ctx.obj` ser criado.
  Em testes, sempre `runner.invoke(cli, ["subcomando", ...])`
- **Fixture `autouse=True` idempotente** registra comando antes do
  `main.py` ser atualizado
- **`WHERE 1=1` + `AND` condicional** simplifica concatenação SQL
- **Placeholders dinâmicos** pra `IN (?, ?)`:
  `",".join("?" * len(items))`
- **`AVG()` ignora NULL** automaticamente em SQL
- **`SKIPPED` ≠ erro** (DB ausente é informação, não falha)

---

## [0.3.0] — 2026-05-21

🎉 **Backup + Organizador!** Dois novos casos de uso essenciais para
automação operacional.

### Adicionado

#### Backup de Arquivos (Fase 4)

- `tasks/backup.py` com `BackupTask`, ZIP DEFLATED + SHA-256
- 17 excludes padrão (caches, VCS, IDEs)
- Comando `autotarefas backup` com `--exclude`, `--no-default-excludes`

#### Organizador de Arquivos (Fase 5)

- `tasks/organize.py` com `OrganizeTask`, `Rule`, `RuleSet`
- Variáveis no destination: `{year}`, `{month:02d}`, `{day:02d}`, `{ext}`
- 3 conflict strategies: `skip`/`rename`/`overwrite`
- Comando `autotarefas organize` com confirmação em massa interativa

### Estatísticas

- ~485 testes, ~4500 linhas

---

## [0.2.0] — 2026-05-18

🎉 **Validador de planilhas** completo! Primeira task real do projeto.

### Adicionado

#### Validador de Planilhas (Fase 3)

- `tasks/issues`, `tasks/validators_br`, `tasks/validators`,
  `tasks/validate`, `tasks/report`
- Comando `autotarefas validate` com `--report-json`, `--report-csv`

### Estatísticas

- ~340 testes

---

## [0.1.0] — 2026-05-15

🎉 **Primeiro release público.** Fundação completa: core, CLI base
com 2 comandos, ~220 testes.

### Adicionado

#### Core (Fase 1)

- `core/settings`, `core/logger`, `core/exceptions`, `core/base`,
  `core/audit`, `core/security`

#### CLI (Fase 2)

- Grupo raiz com `--verbose`, `--quiet`, `--dry-run`, `--yes`, `--version`
- Comandos `info` e `init`

### Estatísticas

- ~220 testes, cobertura 98.87%

---

[Não lançado]: https://github.com/paulor007/autotarefas/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.8.0
[0.7.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.7.0
[0.6.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.6.0
[0.5.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.5.0
[0.4.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.4.0
[0.3.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.3.0
[0.2.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.2.0
[0.1.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.1.0
