# Security Policy

Documento de política de segurança do **AutoTarefas**.

Este documento descreve como reportar vulnerabilidades, o threat model
do projeto, os princípios de segurança aplicados e as boas práticas
esperadas de contribuidores.

---

## 📋 Versões suportadas

| Versão  | Suporte           | Notas                              |
| ------- | ----------------- | ---------------------------------- |
| 0.3.x   | ✅ Ativo          | Atual, recebe patches de segurança |
| 0.2.x   | ⚠️ Bugfix crítico | Apenas se vulnerabilidade crítica  |
| 0.1.x   | ❌ Sem suporte    | Use 0.3.x                          |
| < 0.1.0 | ❌ Sem suporte    | Pre-alpha                          |

Por estar em **pré-release (status: 2 - Pre-Alpha)**, recomenda-se sempre
usar a **versão mais recente**. Após v1.0.0, política de versões será
revisada.

---

## 🔒 Reportando vulnerabilidades

**Não abra issues públicas** para vulnerabilidades de segurança.

### Como reportar

**Email**: paulo.lavarini@gmail.com com assunto `[SECURITY] AutoTarefas`

Ou use **GitHub Security Advisories**:
https://github.com/paulor007/autotarefas/security/advisories/new

### O que incluir no report

- Descrição da vulnerabilidade
- Versão afetada (`autotarefas --version`)
- Passos pra reproduzir (idealmente com PoC mínimo)
- Impacto potencial (o que um atacante poderia fazer)
- Sugestão de fix (se tiver)

### Processo

1. **Recebimento**: confirmamos em até 7 dias
2. **Avaliação**: análise do impacto e prazo de fix
3. **Fix**: patch desenvolvido em branch privado
4. **Disclosure**: coordenamos publicação com você
5. **Credit**: seu nome aparece no CHANGELOG (se desejar)

**Não publique** detalhes técnicos antes do patch estar disponível.
Coordenated disclosure é o padrão.

---

## 🎯 Threat Model

### Em escopo (protegemos contra)

| Ameaça                                 | Proteção                                                                            |
| -------------------------------------- | ----------------------------------------------------------------------------------- |
| **Path traversal**                     | `safe_path()`, `is_within_directory()`, `validate_filename()`                       |
| **Filename injection**                 | `validate_filename()` bloqueia path separators, chars de controle, nomes reservados |
| **Extension spoofing** (`doc.pdf.exe`) | `safe_extension()` whitelist com lookup na última extensão                          |
| **Vazamento de credenciais em logs**   | Mascaramento automático em `core/logger.py` (CPF, CNPJ, senhas, tokens)             |
| **Vazamento em audit trail**           | `mask_sensitive_in_dict()` aplicada em argumentos                                   |
| **Vazamento via URL não-HTTPS**        | `validate_url()` exige HTTPS em produção                                            |
| **Modificação retroativa de audit**    | SQLite append-only + HMAC-SHA256 por linha                                          |
| **Operações destrutivas acidentais**   | Dry-run em todos os comandos + confirmação em massa                                 |
| **ZIP corrompido**                     | Verificação de hash SHA-256 + `zipfile.testzip()` em testes                         |
| **YAML malicioso**                     | `yaml.safe_load()` (nunca `yaml.load()`)                                            |

### Fora de escopo (não protegemos contra)

| Ameaça                        | Justificativa                                          |
| ----------------------------- | ------------------------------------------------------ |
| **Privilege escalation**      | Assumimos que o usuário já tem as permissões adequadas |
| **MITM em conexões TLS**      | Depende do TLS do servidor remoto, não do AutoTarefas  |
| **Ataques físicos**           | Laptop roubado, USB drop — fora do escopo de software  |
| **Side-channel attacks**      | Timing, cache, eletromagnético — fora do escopo        |
| **Insider threats**           | Alguém com acesso ao código-fonte ou ao filesystem     |
| **DoS**                       | Não é um serviço de rede; ferramentas locais           |
| **Supply chain de Python/OS** | Assumimos Python e SO de fonte confiável               |

### Suposições

- Sistema operacional **confiável** (Linux, macOS, Windows oficiais)
- Python instalado de **fonte oficial** (python.org, repositórios distros)
- Dependências do PyPI verificadas (use `pip --require-hashes` em prod)
- Usuário entende implicações de flags destrutivas (`--no-confirm`, `--no-default-excludes`)

---

## 🛡️ Princípios de Segurança

O projeto adere a **13 princípios** documentados:

### 1. Audit trail imutável

Toda operação é registrada em SQLite **append-only** com HMAC-SHA256 por
linha. Modificações retroativas são detectáveis.

### 2. Confirmação contextualizada em massa

Operações destrutivas (organize, futuras tasks de RPA) exigem confirmação
quando afetam **>N arquivos** (default 50, configurável via
`--confirm-threshold`).

### 3. Dry-run obrigatório em operações destrutivas

Todos os comandos com side effects (`organize`, `backup`, futuros)
suportam `--dry-run` global. **Recomendação**: sempre rode dry-run antes
da execução real.

### 4. HTTPS obrigatório em produção

`validate_url(url, environment="prod")` rejeita URLs HTTP em produção.
Em `dev`, `demo`, `homolog` é permitido pra facilitar desenvolvimento.

### 5. Mascaramento automático de dados sensíveis

`core/logger.py` aplica regex pra mascarar **automaticamente** em logs:
CPFs, CNPJs, senhas, tokens, emails, números de cartão. O dev **não
precisa lembrar** de mascarar.

### 6. Path traversal protection

Múltiplas camadas:

- `safe_path()` valida contra allowlist (strict)
- `is_within_directory()` checagem booleana (soft)
- `validate_filename()` bloqueia chars que permitem traversal

### 7. Defense in depth

Múltiplas camadas independentes pra cada ameaça. Exemplo:
`validate_filename` tem **7 camadas** (vazio, tamanho, separators,
traversal, chars de controle, chars proibidos, nomes reservados).

### 8. Fail-safe defaults

Em dúvida, **bloqueia**. Exemplos:

- `click.confirm(default=False)` — Enter sozinho cancela
- `on_conflict="skip"` no organize — não sobrescreve
- `include_default_excludes=True` no backup — exclui caches por padrão

### 9. Whitelist sobre blacklist

Listar o que é **permitido** > listar o que é proibido.
Aplicado em `safe_extension()` e `safe_path()`.

### 10. Princípio do menor privilégio

Tasks acessam **apenas** os paths necessários. Em RPA (futuras fases),
credenciais serão lidas via `SecretStr` (não logáveis) e nunca passadas
por argumento posicional.

### 11. Type safety (mypy strict)

Toda a base de código passa **mypy strict**. Type confusion bugs são
detectados em tempo de build, antes do runtime.

### 12. Operações atômicas

Operações destrutivas são **tudo ou nada**. Exemplo: se uma source falha
em `backup`, **nenhum ZIP** é criado (não fica meio backup corrompido).

### 13. Ambiente demo obrigatório pra RPA

Quando chegar a Fase 8 (RPA), automação de browser **só funcionará**
contra ambiente demo identificado (`environment != "prod"`). Proteção
contra automação acidental em sistemas reais durante desenvolvimento.

---

## 🧱 Camadas de Proteção

### Filesystem

| Função                               | Proteção                       |
| ------------------------------------ | ------------------------------ |
| `safe_path(path, allowed_roots)`     | Path traversal (strict)        |
| `is_within_directory(child, parent)` | Path traversal (soft)          |
| `validate_filename(name)`            | Filename injection (7 camadas) |
| `safe_extension(name, allowed)`      | Extension spoofing             |
| `mkdir(parents=True, exist_ok=True)` | Defensive directory creation   |
| Defaults de excludes em backup       | Ignora caches, VCS, IDEs       |

### Network

| Função                           | Proteção                   |
| -------------------------------- | -------------------------- |
| `validate_url(url, environment)` | HTTPS obrigatório em prod  |
| Stack: `httpx`                   | TLS via biblioteca moderna |
| Sem `requests`                   | Evita CVEs históricas      |

### Secrets

| Componente                       | Proteção                              |
| -------------------------------- | ------------------------------------- |
| `core/logger.py` (regex masking) | CPF, CNPJ, senhas, tokens, emails     |
| `mask_sensitive_in_dict()`       | Recursivo em dicts (audit args)       |
| `SecretStr` do Pydantic Settings | Não loga senhas mesmo em repr()       |
| `detect-secrets` pre-commit hook | Bloqueia commits com credenciais      |
| `# pragma: allowlist secret`     | Marca falsos positivos cirurgicamente |

### Audit Trail

| Característica | Detalhe                                                                                 |
| -------------- | --------------------------------------------------------------------------------------- |
| Storage        | SQLite local em `~/.autotarefas/audit.db`                                               |
| Tabela         | `audit_log` — **append-only** (sem UPDATE/DELETE)                                       |
| Hash por linha | HMAC-SHA256 com chave em settings                                                       |
| Cobertura      | Toda task que herda `BaseTask` registra automaticamente                                 |
| Conteúdo       | task_name, status, started_at, finished_at, duration_ms, args (mascarados), result data |

### Crypto

| Algoritmo                 | Uso                                             |
| ------------------------- | ----------------------------------------------- |
| SHA-256                   | Hash de arquivos (backup), strings, integridade |
| HMAC-SHA256               | Audit trail (chave separada)                    |
| Stdlib `hashlib` + `hmac` | Sem deps externas críticas                      |

---

## 📦 Hardening de Dependências

### Estratégia

1. **Pinning de versão** — todas as deps com `>=X.Y.Z,<W.0.0` em
   `pyproject.toml`
2. **Pre-commit hooks**:
   - `detect-secrets` — bloqueia credenciais em commits
   - `bandit` — análise estática de segurança
3. **Scans manuais** (rodar antes de releases):
   - `pip-audit` — vulnerabilidades conhecidas
   - `safety check` — CVEs em deps
4. **Atualizações regulares** — pelo menos a cada release menor

### Lista de dependências críticas

| Dependência    | Função             | Mitigação                                           |
| -------------- | ------------------ | --------------------------------------------------- |
| `cryptography` | HMAC pro audit     | Versão >=42, atualizada                             |
| `httpx`        | HTTP client        | TLS verification habilitada                         |
| `PyYAML`       | Parse YAML         | **Apenas** `yaml.safe_load()` (nunca `yaml.load()`) |
| `pydantic`     | Validação          | v2 com `extra="forbid"` (rejeita campos extras)     |
| `playwright`   | Browser automation | Apenas em demo (Fase 8+)                            |

### Comandos úteis

```bash
# Auditoria manual de dependências
pip-audit

# Scan de código
bandit -r src/
ruff check src/

# Tudo de uma vez
pre-commit run --all-files
```

---

## 🤝 Best Practices pra Contribuidores

### Code review obrigatório

PRs com mudanças em:

- `core/security.py`
- `core/audit.py`
- `core/logger.py`
- Qualquer arquivo com `safe_path`, `validate_url`, etc.

...exigem **revisão extra** focada em segurança.

### Antes de abrir PR

```bash
# Todos esses devem passar
ruff check src/ tests/
mypy src/ tests/
pytest tests/
pre-commit run --all-files
```

### Padrões a seguir

#### ✅ Faça

- Use type hints completos (mypy strict)
- Use `safe_path()` ao receber paths de usuário
- Use `validate_filename()` ao usar nomes em filesystem
- Use `mask_sensitive_in_dict()` ao logar argumentos
- Documente decisões de segurança em docstrings
- Adicione testes pra **cada camada** de proteção

#### ❌ Evite

- `os.system()`, `subprocess.run(shell=True)` — risco de command injection
- `eval()`, `exec()`, `pickle.loads()` em input não-confiável
- `yaml.load()` (use `yaml.safe_load()`)
- Concatenar paths com `+` ou `os.path.join` (use `Path` + `/`)
- Hardcode de credenciais (use `SecretStr` no Settings)
- Desabilitar pre-commit hooks pra "facilitar"

### Testes de segurança

Cada função de segurança deve ter testes que cobrem:

- **Caminho feliz** (input válido passa)
- **Cada camada de validação** (input inválido falha)
- **Edge cases** (vazio, muito longo, unicode, case sensitivity)
- **Vetores de ataque conhecidos** (path traversal, extension spoofing)

Veja `tests/core/test_security.py` como referência.

---

## 📜 Histórico de Issues de Segurança

Nenhuma vulnerabilidade reportada até o momento (estado em v0.3.0).

Quando reportadas, serão documentadas aqui após disclosure coordenado:

| Data | Severidade | CVE | Descrição | Versão fix |
| ---- | ---------- | --- | --------- | ---------- |
| —    | —          | —   | —         | —          |

---

## 🔗 Referências

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Python Security Documentation](https://docs.python.org/3/library/security_warnings.html)
- [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories)

---

**Última atualização**: 2026-05-22 (v0.3.0)

**Maintainer**: Paulo Lavarini (`paulor007`)
