# AutoTarefas

Robô de automação operacional em Python, com foco em **segurança**, **rastreabilidade** (audit trail) e **robustez**. Automatiza tarefas com planilhas (CSV/Excel), arquivos, sistemas web (RPA), APIs REST e email — tudo por uma CLI única.

!!! note "Projeto de portfólio"
O AutoTarefas é um projeto pessoal, não comercial, criado para demonstrar engenharia de software em Python no mundo real: arquitetura limpa, testes, tipagem estrita, CI/CD e práticas de segurança.

## Destaques

- **9 comandos** numa CLI coesa (Click + Rich)
- **9 tasks** sobre uma base comum (`BaseTask`), cada uma com resultado padronizado e audit automático
- **Audit trail** em SQLite (append-only, com HMAC) — toda execução fica registrada
- **Segurança** levada a sério: senhas via variável de ambiente ou prompt, nunca em log/CLI; mascaramento de dados sensíveis
- **Tipagem estrita** (mypy strict), lint (ruff), análise de segurança (bandit) e **~960 testes**
- **CI/CD** no GitHub Actions rodando em Python 3.12 e 3.13

## O que ele faz

| Capacidade    | Comando        | Descrição                                                     |
| ------------- | -------------- | ------------------------------------------------------------- |
| Validar       | `validate`     | Valida planilhas por schema (CPF/CNPJ com dígito verificador) |
| Backup        | `backup`       | Compacta arquivos em ZIP com hash SHA-256                     |
| Organizar     | `organize`     | Organiza arquivos por regras declarativas (YAML)              |
| Relatórios    | `report`       | Consolida o audit trail em relatórios                         |
| RPA web       | `rpa cadastro` | Cadastro em massa via navegador (Playwright)                  |
| Extrair (API) | `extract api`  | Extrai de APIs REST paginadas                                 |
| Enviar (API)  | `send api`     | Cadastro em massa via POST por linha                          |
| Email         | `send email`   | Envia emails em massa com template `{coluna}`                 |
| Sincronizar   | `sync api`     | Liga extração e envio: origem → destino                       |

## Instalação

Requer **Python 3.12+**.

```bash
git clone https://github.com/paulor007/autotarefas.git
cd autotarefas

python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1
# Linux/Mac: source venv/bin/activate

pip install -e ".[dev]"
```

Extras disponíveis:

- `dev` — ferramentas de desenvolvimento (pytest, mypy, ruff, bandit…)
- `demo` — ambientes de teste local (servidor de API e de SMTP)
- `rpa` — Playwright para automação web
- `docs` — MkDocs Material para esta documentação

## Quick start

```bash
# Visão geral e versão
autotarefas info

# Validar uma planilha
autotarefas validate dados.csv --schema schema.yaml

# Backup de uma pasta
autotarefas backup ./documentos --output backup.zip

# Simular qualquer comando (sem efeitos)
autotarefas --dry-run send api -p clientes.csv -u https://api.exemplo.com/clientes
```

Veja a página [Comandos](comandos.md) para o guia completo de cada um.
