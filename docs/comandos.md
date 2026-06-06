# Comandos

A CLI tem opções globais que valem para qualquer comando:

| Opção           | Efeito                                   |
| --------------- | ---------------------------------------- |
| `--dry-run`     | Simula a operação, sem efeitos reais     |
| `--verbose, -v` | Aumenta a verbosidade (repetível: `-vv`) |
| `--quiet, -q`   | Reduz a verbosidade                      |
| `--yes, -y`     | Assume "sim" nas confirmações            |

!!! tip "Dry-run"
Quase todos os comandos suportam `--dry-run`, que mostra o que aconteceria sem executar de fato. Ótimo para conferir antes de uma operação em massa.

Os exit codes seguem um padrão: **0** sucesso (ou parcial), **1** falha, **2** erro de uso.

---

## validate

Valida uma planilha contra um schema declarativo (YAML), incluindo CPF/CNPJ com dígito verificador.

```bash
autotarefas validate dados.csv --schema schema.yaml
```

## backup

Compacta arquivos/pastas em um ZIP e gera um hash **SHA-256** para conferência de integridade.

```bash
autotarefas backup ./documentos --output backup.zip
```

## organize

Organiza arquivos de uma pasta segundo regras declarativas (por extensão, padrão de nome etc.) definidas em YAML.

```bash
autotarefas organize ./downloads --rules regras.yaml
```

## report

Consolida o **audit trail** (todas as execuções de tasks) em um relatório legível.

```bash
autotarefas report --task send_api --limit 50
```

---

## rpa cadastro

Cadastro em massa via **navegador** (Playwright), para sistemas web sem API. Lê uma planilha e preenche o formulário linha a linha.

```bash
autotarefas rpa cadastro --planilha clientes.csv --url https://sistema.exemplo.com/cadastro
```

!!! info "Quando usar RPA"
Use RPA quando o sistema-alvo **não** expõe uma API. Se houver API, prefira `extract`/`send` — é muito mais rápido e estável.

---

## extract api

Extrai dados de uma **API REST paginada** e salva em CSV, XLSX ou JSON. Segue a paginação automaticamente, com retry em erros temporários.

```bash
autotarefas extract api --url https://api.exemplo.com/clientes --output clientes.csv
```

| Opção           | Default | Descrição                                |
| --------------- | ------- | ---------------------------------------- |
| `--per-page`    | `50`    | Itens por página                         |
| `--max-pages`   | todas   | Limite de páginas                        |
| `--api-key`     | —       | Header `X-API-Key`                       |
| `--max-retries` | `3`     | Tentativas por página em erro temporário |

## send api

Envio em massa: lê uma planilha e faz **POST de cada linha** em uma API. Tolerante a falhas — uma linha ruim não interrompe as demais.

```bash
autotarefas send api --planilha clientes.csv --url https://api.exemplo.com/clientes --report resultado.csv
```

!!! note "Retry inteligente"
Erros temporários (timeout, HTTP 5xx) são retentados; erros do dado (4xx, como duplicata ou validação) **não** são — reenviar não mudaria o resultado.

## send email

Envia um email **personalizado por linha** de uma planilha, via SMTP. Assunto e corpo aceitam `{coluna}` (ex.: `Olá {nome}!`).

```bash
autotarefas send email -p contatos.csv --smtp-host smtp.exemplo.com --smtp-port 587 \
  --from voce@exemplo.com --subject "Olá {nome}!" --body-file corpo.txt --user voce@exemplo.com
```

!!! warning "Senha do SMTP"
A senha **nunca** é passada na linha de comando. Defina a variável de ambiente `AUTOTAREFAS_SMTP_PASSWORD` ou informe `--user` para que ela seja solicitada em um prompt oculto. Assim a senha não vaza no histórico do shell nem em logs.

---

## sync api

Sincronização **origem → destino**: extrai de uma API e envia para outra, em um passo só. Internamente compõe `extract api` + `send api`.

```bash
autotarefas sync api \
  --source-url https://origem.exemplo.com/api/clientes \
  --dest-url https://destino.exemplo.com/api/clientes \
  --report resultado.csv
```

| Opção                                                   | Descrição                                       |
| ------------------------------------------------------- | ----------------------------------------------- |
| `--source-url, -s`                                      | API origem (extração)                           |
| `--dest-url, -d`                                        | API destino (envio)                             |
| `--source-api-key` / `--dest-api-key` / `--dest-bearer` | Autenticação por lado                           |
| `--format`                                              | Formato do arquivo intermediário (`csv`/`xlsx`) |

---

## Utilitários

```bash
autotarefas info     # versão e informações do ambiente
autotarefas init     # cria a estrutura inicial de configuração
```
