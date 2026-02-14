# Mapeamento: Estrutura de Arquivos × Cronograma

**Versão:** 1.0
**Data:** Dezembro 2025

Este documento mapeia **cada arquivo/pasta** para a **fase do cronograma** em que será criado.

---

## Resumo Visual

```
AUTOTAREFAS/
│
├── .github/                    ──────► FASE 11 (CI/CD)
├── docs/
│   ├── planejamento/           ──────► FASE 0  (Docs técnicos - para desenvolvedor)
│   ├── tutorials/              ──────► FASE 9  (Docs para usuário final)
│   └── *.md                    ──────► FASE 9  (Docs para usuário final)
├── examples/                   ──────► FASE 9  (Documentação)
├── scripts/                    ──────► FASE 7  (Testes) + FASE 10 (Empacotamento)
├── src/autotarefas/           ──────► FASES 2-6 (Core, Tasks, CLI, Scheduler, Email)
├── tests/                      ──────► FASE 7  (Testes)
└── [configs raiz]              ──────► FASES 1, 7, 9, 10, 11 (varia)
```

---

## Mapeamento Detalhado

### FASE 0: Planejamento (Documentação Técnica)

| Arquivo/Pasta | Item do Cronograma |
|---------------|-------------------|
| `docs/planejamento/REQUISITOS.md` | 0.1 - Definição de requisitos |
| `docs/planejamento/ARQUITETURA.md` | 0.2 - Arquitetura do sistema |
| `docs/planejamento/ESTRUTURA_PASTAS.md` | 0.3 - Estrutura de pastas |
| `docs/planejamento/TECNOLOGIAS.md` | 0.4 - Escolha de tecnologias |
| `docs/planejamento/CRONOGRAMA.md` | 0.5 - Cronograma inicial |
| `docs/planejamento/MAPEAMENTO_ARQUIVOS_FASES.md` | 0.3 - (auxiliar) |

> Estes documentos são para **você (desenvolvedor)**, não para usuário final.

### FASE 1: Setup do Ambiente (🔄 33%)

| Arquivo/Pasta | Item do Cronograma | Status |
|---------------|-------------------|--------|
| `.vscode/settings.json` | 1.1 - Config VS Code | ⏳ |
| `.vscode/extensions.json` | 1.1 - Extensões recomendadas | ⏳ |
| `.vscode/launch.json` | 1.1 - Debug configs | ⏳ |
| `src/autotarefas/` (pasta) | 1.3 - Estrutura de diretórios | ⏳ |
| `src/autotarefas/__init__.py` | 1.3 - Pacote principal | ⏳ |
| `tests/` (pasta) | 1.3 - Estrutura de diretórios | ⏳ |
| `tests/__init__.py` | 1.3 - Pacote de testes | ⏳ |
| `docs/` (pasta) | 1.3 - Estrutura de diretórios | ⏳ |
| `.gitignore` | 1.8 - Arquivos ignorados | ✅ |
| `.env.example` | 1.7 - Variáveis de ambiente | ✅ |
| `pyproject.toml` | 1.6 - Configuração do projeto | ✅ |
| `README.md` | 1.9 - Documentação inicial | ✅ |

### FASE 2: Core do Sistema

| Arquivo/Pasta | Item do Cronograma |
|---------------|-------------------|
| `src/autotarefas/__init__.py` | 2.1.1 |
| `src/autotarefas/config.py` | 2.1.2 |
| `src/autotarefas/core/__init__.py` | 2.2.1 |
| `src/autotarefas/core/logger.py` | 2.2.2 |
| `src/autotarefas/core/base.py` | 2.3.1, 2.3.2, 2.3.3 |
| `src/autotarefas/utils/__init__.py` | 2.4.1 |
| `src/autotarefas/utils/helpers.py` | 2.4.2 |

### FASE 3: Tasks Core (Produção)

| Arquivo/Pasta | Item do Cronograma |
|---------------|-------------------|
| `src/autotarefas/tasks/__init__.py` | 3.1.1 |
| `src/autotarefas/tasks/backup.py` | 3.1.2 - 3.1.5 |
| `src/autotarefas/tasks/cleaner.py` | 3.2.1 - 3.2.4 |
| `src/autotarefas/tasks/monitor.py` | 3.3.1 - 3.3.5 |
| `src/autotarefas/tasks/reporter.py` | 3.4.1 |
| `src/autotarefas/tasks/sales_report.py` | 3.4.2 |

### FASE 4: Interface CLI

| Arquivo/Pasta | Item do Cronograma |
|---------------|-------------------|
| `src/autotarefas/cli/__init__.py` | 4.1.1 |
| `src/autotarefas/cli/main.py` | 4.1.2 |
| `src/autotarefas/cli/commands/__init__.py` | 4.1.3 |
| `src/autotarefas/cli/commands/init.py` | 4.2.1 |
| `src/autotarefas/cli/commands/backup.py` | 4.3.1 - 4.3.3 |
| `src/autotarefas/cli/commands/cleaner.py` | 4.4.1 - 4.4.2 |
| `src/autotarefas/cli/commands/monitor.py` | 4.5.1 - 4.5.3 |
| `src/autotarefas/cli/commands/reporter.py` | 4.6.1 - 4.6.2 |

### FASE 5: Agendamento

| Arquivo/Pasta | Item do Cronograma |
|---------------|-------------------|
| `src/autotarefas/core/scheduler.py` | 5.1.1 - 5.1.7 |
| `src/autotarefas/cli/commands/scheduler.py` | 5.2.1 - 5.2.10 |
| `src/autotarefas/core/storage/__init__.py` | 5.3.1 |
| `src/autotarefas/core/storage/job_store.py` | 5.3.1 |
| `src/autotarefas/core/storage/run_history.py` | 5.3.2 |

### FASE 6: Notificações (Email)

| Arquivo/Pasta | Item do Cronograma |
|---------------|-------------------|
| `src/autotarefas/core/email.py` | 6.1.1 - 6.1.6 |
| `src/autotarefas/core/notifier.py` | 6.2.1 - 6.2.2 |
| `src/autotarefas/resources/templates/email/base.html` | 6.2.3 |
| `src/autotarefas/resources/templates/email/report.html` | 6.2.3 |
| `src/autotarefas/resources/templates/email/notify.html` | 6.2.3 |
| `src/autotarefas/cli/commands/email.py` | 6.3.1 - 6.3.5 |

### FASE 7: Testes

| Arquivo/Pasta | Item do Cronograma |
|---------------|-------------------|
| `tests/__init__.py` | 7.1.1 |
| `tests/conftest.py` | 7.1.2 |
| `tests/test_config.py` | 7.2.1 |
| `tests/test_logger.py` | 7.2.2 |
| `tests/test_base.py` | 7.2.3 |
| `tests/test_utils.py` | 7.2.4 |
| `tests/test_backup.py` | 7.2.5 |
| `tests/test_cleaner.py` | 7.2.6 |
| `tests/test_monitor.py` | 7.2.7 |
| `tests/test_scheduler.py` | 7.2.8 |
| `tests/test_email.py` | 7.2.9 |
| `tests/test_sales_report.py` | 7.2.10 |
| `tests/test_job_store.py` | 7.2.11 |
| `tests/test_run_history.py` | 7.2.12 |
| `tests/integration/__init__.py` | 7.3.1 |
| `tests/integration/conftest.py` | 7.3.2 |
| `tests/integration/test_*_integration.py` | 7.3.3 - 7.3.7 |
| `tests/e2e/__init__.py` | 7.4.1 |
| `tests/e2e/conftest.py` | 7.4.2 |
| `tests/e2e/test_cli_*.py` | 7.4.3 - 7.4.9 |
| `.coveragerc` | 7.5.2 |
| `scripts/check_coverage.py` | 7.5.3 |

### FASE 8: Organizador de Arquivos

| Arquivo/Pasta | Item do Cronograma |
|---------------|-------------------|
| `src/autotarefas/tasks/organizer.py` | 8.1.1 - 8.1.8 |
| `src/autotarefas/cli/commands/organizer.py` | 8.2.1 - 8.2.5 |
| `tests/test_organizer.py` | 8.3.1 |
| `tests/integration/test_organizer_integration.py` | 8.3.2 |
| `tests/e2e/test_cli_organizer.py` | 8.3.3 |

### FASE 9: Documentação

| Arquivo/Pasta | Item do Cronograma |
|---------------|-------------------|
| `README.md` (completo) | 9.1.1 |
| `CONTRIBUTING.md` | 9.1.2 |
| `CHANGELOG.md` | 9.1.3 |
| `LICENSE` | 9.1.4 |
| `CODE_OF_CONDUCT.md` | 9.1.5 |
| `SECURITY.md` | 9.1.6 |
| `mkdocs.yml` | 9.2.1 |
| `docs/index.md` | 9.2.2 |
| `docs/installation.md` | 9.2.3 |
| `docs/configuration.md` | 9.2.4 |
| `docs/cli-reference.md` | 9.2.5 |
| `docs/api-reference.md` | 9.2.6 |
| `docs/quickstart.md` | 9.3.1 |
| `docs/tutorials/backup.md` | 9.3.2 |
| `docs/tutorials/cleaner.md` | 9.3.3 |
| `docs/tutorials/monitor.md` | 9.3.4 |
| `docs/tutorials/scheduler.md` | 9.3.5 |
| `docs/tutorials/email.md` | 9.3.6 |
| `docs/tutorials/organizer.md` | 9.3.7 |
| `docs/faq.md` | 9.3.8 |
| `examples/backup_example.py` | 9.4.1 |
| `examples/cleaner_example.py` | 9.4.2 |
| `examples/monitor_example.py` | 9.4.3 |
| `examples/scheduler_example.py` | 9.4.4 |
| `examples/organizer_example.py` | 9.4.5 |

### FASE 10: Empacotamento

| Arquivo/Pasta | Item do Cronograma |
|---------------|-------------------|
| `pyproject.toml` (metadados completos) | 10.1.1 |
| `MANIFEST.in` | 10.1.2 |
| `src/autotarefas/py.typed` | 10.1.3 |

### FASE 11: CI/CD

| Arquivo/Pasta | Item do Cronograma |
|---------------|-------------------|
| `.github/workflows/tests.yml` | 11.1.1 |
| `.github/workflows/lint.yml` | 11.2.1 |
| `.github/workflows/release.yml` | 11.3.1 |
| `.pre-commit-config.yaml` | 11.4.1 |
| `.github/dependabot.yml` | 11.4.2 |

### FASE 12: Release & Distribuição

| Arquivo/Pasta | Item do Cronograma |
|---------------|-------------------|
| Tag Git v0.1.0 | 12.1.3 |
| GitHub Release | 12.2.1 |

---

## Tabela Consolidada (Ordem Alfabética)

| Arquivo/Pasta | Fase | Item |
|---------------|------|------|
| `.coveragerc` | 7 | 7.5.2 |
| `.env.example` | 1 | 1.7 |
| `.github/dependabot.yml` | 11 | 11.4.2 |
| `.github/workflows/lint.yml` | 11 | 11.2.1 |
| `.github/workflows/release.yml` | 11 | 11.3.1 |
| `.github/workflows/tests.yml` | 11 | 11.1.1 |
| `.gitignore` | 1 | 1.8 |
| `.pre-commit-config.yaml` | 11 | 11.4.1 |
| `CHANGELOG.md` | 9 | 9.1.3 |
| `CODE_OF_CONDUCT.md` | 9 | 9.1.5 |
| `CONTRIBUTING.md` | 9 | 9.1.2 |
| `LICENSE` | 9 | 9.1.4 |
| `MANIFEST.in` | 10 | 10.1.2 |
| `README.md` (inicial) | 1 | 1.9 |
| `README.md` (completo) | 9 | 9.1.1 |
| `SECURITY.md` | 9 | 9.1.6 |
| `docs/*` | 9 | 9.2.x, 9.3.x |
| `examples/*` | 9 | 9.4.x |
| `mkdocs.yml` | 9 | 9.2.1 |
| `pyproject.toml` (básico) | 1 | 1.6 |
| `pyproject.toml` (completo) | 10 | 10.1.1 |
| `scripts/check_coverage.py` | 7 | 7.5.3 |
| `src/autotarefas/cli/*` | 4 | 4.x.x |
| `src/autotarefas/cli/commands/email.py` | 6 | 6.3.x |
| `src/autotarefas/cli/commands/organizer.py` | 8 | 8.2.x |
| `src/autotarefas/cli/commands/scheduler.py` | 5 | 5.2.x |
| `src/autotarefas/config.py` | 2 | 2.1.2 |
| `src/autotarefas/core/base.py` | 2 | 2.3.x |
| `src/autotarefas/core/email.py` | 6 | 6.1.x |
| `src/autotarefas/core/logger.py` | 2 | 2.2.2 |
| `src/autotarefas/core/notifier.py` | 6 | 6.2.x |
| `src/autotarefas/core/scheduler.py` | 5 | 5.1.x |
| `src/autotarefas/core/storage/*` | 5 | 5.3.x |
| `src/autotarefas/py.typed` | 10 | 10.1.3 |
| `src/autotarefas/resources/templates/*` | 6 | 6.2.3 |
| `src/autotarefas/tasks/backup.py` | 3 | 3.1.x |
| `src/autotarefas/tasks/cleaner.py` | 3 | 3.2.x |
| `src/autotarefas/tasks/monitor.py` | 3 | 3.3.x |
| `src/autotarefas/tasks/organizer.py` | 8 | 8.1.x |
| `src/autotarefas/tasks/reporter.py` | 3 | 3.4.x |
| `src/autotarefas/utils/*` | 2 | 2.4.x |
| `tests/*` | 7 | 7.x.x |
| `tests/test_organizer.py` | 8 | 8.3.1 |

---

## Observações Importantes

### 1. Arquivos que Evoluem
Alguns arquivos são criados em uma fase e **completados** em outra:

| Arquivo | Criado | Completado |
|---------|--------|------------|
| `README.md` | Fase 1 (básico) | Fase 9 (completo) |
| `pyproject.toml` | Fase 1 (básico) | Fase 10 (metadados) |

### 2. Pastas Criadas Vazias
Na **Fase 1**, criamos a estrutura de diretórios vazia:
```
src/autotarefas/
tests/
docs/
```
Os arquivos dentro são criados nas fases subsequentes.

### 3. Testes Acompanham Código
Embora a **Fase 7** seja dedicada a testes, na prática você pode (e deve) escrever testes junto com o código. A Fase 7 é para:
- Completar cobertura
- Testes de integração
- Testes E2E
- Configuração de coverage

### 4. Documentação de Planejamento
Os arquivos que estamos criando agora (Fase 0):
```
docs/REQUISITOS.md
docs/ARQUITETURA.md
docs/ESTRUTURA_PASTAS.md
docs/TECNOLOGIAS.md (próximo)
```
São **documentação de planejamento**, diferentes da documentação de usuário (Fase 9).

---

## Resumo por Fase

| Fase | O que é criado |
|------|----------------|
| **0** | Documentos de planejamento (REQUISITOS, ARQUITETURA, etc.) |
| **1** | Estrutura base, .gitignore, pyproject.toml básico, README inicial |
| **2** | Core: config, logger, base, utils |
| **3** | Tasks: backup, cleaner, monitor, reporter |
| **4** | CLI: main.py, comandos básicos |
| **5** | Scheduler: agendamento, storage, persistência |
| **6** | Email: sender, notifier, templates |
| **7** | Testes: unitários, integração, E2E, coverage |
| **8** | Organizer: task, CLI, testes específicos |
| **9** | Docs: tutoriais, mkdocs, examples, CONTRIBUTING, LICENSE |
| **10** | Empacotamento: MANIFEST.in, py.typed, pyproject.toml completo |
| **11** | CI/CD: GitHub Actions, pre-commit, dependabot |
| **12** | Release: tag, publicação PyPI, GitHub Release |

---

*Documento auxiliar para Fase 0.3 - Estrutura de Pastas*
