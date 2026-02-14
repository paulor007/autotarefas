# Cronograma do Projeto - AutoTarefas

**Versão:** 1.0
**Data:** Dezembro 2025
**Status:** Aprovado

---

## 1. Visão Geral

Este documento apresenta o cronograma completo do projeto AutoTarefas, incluindo fases, estimativas de tempo, dependências e marcos importantes.

### 1.1 Resumo Executivo

| Métrica | Valor |
|---------|-------|
| **Total de Fases** | 13 (0-12) |
| **Total de Itens** | ~165 |
| **Estimativa Total** | 8-12 semanas |
| **Versão Alvo** | v0.1.0 (MVP) |

---

## 2. Fases do Projeto

### 2.1 Visão Geral das Fases

```
┌─────────────────────────────────────────────────────────────────┐
│                    TIMELINE DO PROJETO                           │
│                                                                  │
│  FASE 0   ████████████████████  Planejamento                    │
│  FASE 1   ████████              Setup do Ambiente               │
│  FASE 2   ████████████          Core do Sistema                 │
│  FASE 3   ████████████████      Tasks Core                      │
│  FASE 4   ████████████          Interface CLI                   │
│  FASE 5   ████████████          Agendamento                     │
│  FASE 6   ████████              Notificações                    │
│  FASE 7   ████████████████      Testes                          │
│  FASE 8   ████████              Organizador                     │
│  FASE 9   ████████████          Documentação                    │
│  FASE 10  ████████              Empacotamento                   │
│  FASE 11  ████████              CI/CD                           │
│  FASE 12  ████                  Release                         │
│                                                                  │
│  ──────────────────────────────────────────────────────────►    │
│  Semana 1   2   3   4   5   6   7   8   9  10  11  12           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Tabela de Fases

| Fase | Nome | Estimativa | Dependências | Prioridade |
|------|------|------------|--------------|------------|
| 0 | Planejamento | 3-5 dias | - | 🔴 Crítica |
| 1 | Setup do Ambiente | 1-2 dias | Fase 0 | 🔴 Crítica |
| 2 | Core do Sistema | 3-5 dias | Fase 1 | 🔴 Crítica |
| 3 | Tasks Core | 5-7 dias | Fase 2 | 🔴 Crítica |
| 4 | Interface CLI | 3-5 dias | Fase 3 | 🔴 Crítica |
| 5 | Agendamento | 4-6 dias | Fase 2, 3 | 🟡 Alta |
| 6 | Notificações | 2-4 dias | Fase 2 | 🟡 Alta |
| 7 | Testes | 5-7 dias | Fase 3, 4, 5, 6 | 🟡 Alta |
| 8 | Organizador | 3-4 dias | Fase 2, 4 | 🟢 Média |
| 9 | Documentação | 3-5 dias | Fase 4, 8 | 🟢 Média |
| 10 | Empacotamento | 2-3 dias | Fase 7 | 🟡 Alta |
| 11 | CI/CD | 2-3 dias | Fase 7, 10 | 🟡 Alta |
| 12 | Release | 1-2 dias | Todas | 🔴 Crítica |

---

## 3. Diagrama de Dependências

```
┌─────────────────────────────────────────────────────────────────┐
│                  DEPENDÊNCIAS ENTRE FASES                        │
│                                                                  │
│                        ┌─────────┐                              │
│                        │ FASE 0  │ Planejamento                 │
│                        │ (start) │                              │
│                        └────┬────┘                              │
│                             │                                    │
│                             ▼                                    │
│                        ┌─────────┐                              │
│                        │ FASE 1  │ Setup                        │
│                        └────┬────┘                              │
│                             │                                    │
│                             ▼                                    │
│                        ┌─────────┐                              │
│                        │ FASE 2  │ Core                         │
│                        └────┬────┘                              │
│                             │                                    │
│              ┌──────────────┼──────────────┐                    │
│              │              │              │                    │
│              ▼              ▼              ▼                    │
│        ┌─────────┐   ┌─────────┐    ┌─────────┐                │
│        │ FASE 3  │   │ FASE 5  │    │ FASE 6  │                │
│        │ Tasks   │   │Scheduler│    │ Email   │                │
│        └────┬────┘   └────┬────┘    └────┬────┘                │
│             │             │              │                      │
│             ▼             │              │                      │
│        ┌─────────┐        │              │                      │
│        │ FASE 4  │        │              │                      │
│        │  CLI    │        │              │                      │
│        └────┬────┘        │              │                      │
│             │             │              │                      │
│             ├─────────────┴──────────────┘                      │
│             │                                                    │
│             ▼                                                    │
│        ┌─────────┐                                              │
│        │ FASE 8  │ Organizador                                  │
│        └────┬────┘                                              │
│             │                                                    │
│             ▼                                                    │
│        ┌─────────┐                                              │
│        │ FASE 7  │ Testes                                       │
│        └────┬────┘                                              │
│             │                                                    │
│        ┌────┴────┐                                              │
│        ▼         ▼                                              │
│   ┌─────────┐ ┌─────────┐                                       │
│   │ FASE 9  │ │ FASE 10 │                                       │
│   │  Docs   │ │ Package │                                       │
│   └────┬────┘ └────┬────┘                                       │
│        │           │                                            │
│        │      ┌────┘                                            │
│        │      ▼                                                 │
│        │ ┌─────────┐                                            │
│        │ │ FASE 11 │ CI/CD                                      │
│        │ └────┬────┘                                            │
│        │      │                                                 │
│        └──────┤                                                 │
│               ▼                                                 │
│          ┌─────────┐                                            │
│          │ FASE 12 │ Release                                    │
│          │  (end)  │                                            │
│          └─────────┘                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Detalhamento por Fase

### FASE 0: Planejamento
**Estimativa:** 3-5 dias | **Status:** ✅ 100%

| Item | Descrição | Artefato | Status |
|------|-----------|----------|--------|
| 0.1 | Definição de requisitos | `docs/planejamento/REQUISITOS.md` | ✅ |
| 0.2 | Arquitetura do sistema | `docs/planejamento/ARQUITETURA.md` | ✅ |
| 0.3 | Estrutura de pastas | `docs/planejamento/ESTRUTURA_PASTAS.md` | ✅ |
| 0.4 | Escolha de tecnologias | `docs/planejamento/TECNOLOGIAS.md` | ✅ |
| 0.5 | Cronograma inicial | `docs/planejamento/CRONOGRAMA.md` | ✅ |

**Documento auxiliar:** `docs/planejamento/MAPEAMENTO_ARQUIVOS_FASES.md`

---

### FASE 1: Setup do Ambiente
**Estimativa:** 1-2 dias | **Depende de:** Fase 0

| Item | Descrição | Artefato |
|------|-----------|----------|
| 1.1 | Configuração VS Code / IDE | `.vscode/settings.json` |
| 1.2 | Inicialização Git | `.git/` |
| 1.3 | Estrutura de diretórios | `src/`, `tests/`, `docs/` |
| 1.4 | Ambiente virtual (venv) | `venv/` (não versionado) |
| 1.5 | Dependências iniciais | `pyproject.toml` |
| 1.6 | pyproject.toml básico | `pyproject.toml` |
| 1.7 | Variáveis de ambiente | `.env.example` |
| 1.8 | Arquivos ignorados | `.gitignore` |
| 1.9 | Documentação inicial | `README.md` |

---

### FASE 2: Core do Sistema
**Estimativa:** 3-5 dias | **Depende de:** Fase 1

| Bloco | Descrição | Arquivos |
|-------|-----------|----------|
| 2.1 | Configuração | `__init__.py`, `config.py` |
| 2.2 | Logger | `core/logger.py` |
| 2.3 | Base | `core/base.py` (TaskResult, TaskStatus, BaseTask) |
| 2.4 | Utils | `utils/helpers.py` |

---

### FASE 3: Tasks Core (Produção)
**Estimativa:** 5-7 dias | **Depende de:** Fase 2

| Bloco | Descrição | Arquivos |
|-------|-----------|----------|
| 3.1 | Backup | `tasks/backup.py` |
| 3.2 | Cleaner | `tasks/cleaner.py` |
| 3.3 | Monitor | `tasks/monitor.py` |
| 3.4 | Reporter | `tasks/reporter.py`, `tasks/sales_report.py` |

---

### FASE 4: Interface CLI
**Estimativa:** 3-5 dias | **Depende de:** Fase 3

| Bloco | Descrição | Arquivos |
|-------|-----------|----------|
| 4.1 | Estrutura Base | `cli/main.py`, `cli/commands/__init__.py` |
| 4.2 | Comando Init | `cli/commands/init.py` |
| 4.3 | Comandos Backup | `cli/commands/backup.py` |
| 4.4 | Comandos Cleaner | `cli/commands/cleaner.py` |
| 4.5 | Comandos Monitor | `cli/commands/monitor.py` |
| 4.6 | Comandos Reporter | `cli/commands/reporter.py` |

---

### FASE 5: Agendamento (com Persistência)
**Estimativa:** 4-6 dias | **Depende de:** Fase 2, 3

| Bloco | Descrição | Arquivos |
|-------|-----------|----------|
| 5.1 | Core Scheduler | `core/scheduler.py` |
| 5.2 | CLI Scheduler | `cli/commands/scheduler.py` |
| 5.3 | Persistência | `core/storage/job_store.py`, `core/storage/run_history.py` |

---

### FASE 6: Notificações (Email + canais)
**Estimativa:** 2-4 dias | **Depende de:** Fase 2

| Bloco | Descrição | Arquivos |
|-------|-----------|----------|
| 6.1 | Core Email | `core/email.py` |
| 6.2 | Notifier | `core/notifier.py`, templates HTML |
| 6.3 | CLI Email | `cli/commands/email.py` |

---

### FASE 7: Testes
**Estimativa:** 5-7 dias | **Depende de:** Fase 3, 4, 5, 6

| Bloco | Descrição | Arquivos |
|-------|-----------|----------|
| 7.1 | Configuração | `conftest.py`, pyproject.toml |
| 7.2 | Testes Unitários | `test_*.py` |
| 7.3 | Testes Integração | `integration/test_*_integration.py` |
| 7.4 | Testes E2E | `e2e/test_cli_*.py` |
| 7.5 | Cobertura | `.coveragerc`, `scripts/check_coverage.py` |

---

### FASE 8: Organizador de Arquivos
**Estimativa:** 3-4 dias | **Depende de:** Fase 2, 4

| Bloco | Descrição | Arquivos |
|-------|-----------|----------|
| 8.1 | Módulo Organizer | `tasks/organizer.py` |
| 8.2 | CLI Organizer | `cli/commands/organizer.py` |
| 8.3 | Testes | `test_organizer.py`, integração, E2E |
| 8.4 | Integração | TaskRegistry, notificações |

---

### FASE 9: Documentação
**Estimativa:** 3-5 dias | **Depende de:** Fase 4, 8

| Bloco | Descrição | Arquivos |
|-------|-----------|----------|
| 9.1 | Arquivos Base | `README.md`, `CONTRIBUTING.md`, `LICENSE`, etc. |
| 9.2 | MkDocs | `mkdocs.yml`, `docs/*.md` |
| 9.3 | Tutoriais | `docs/tutorials/*.md` |
| 9.4 | Exemplos | `examples/*.py` |

---

### FASE 10: Empacotamento
**Estimativa:** 2-3 dias | **Depende de:** Fase 7

| Bloco | Descrição | Arquivos |
|-------|-----------|----------|
| 10.1 | Configuração | `pyproject.toml`, `MANIFEST.in`, `py.typed` |
| 10.2 | Build/Distribuição | wheel, sdist, TestPyPI, PyPI |

---

### FASE 11: CI/CD
**Estimativa:** 2-3 dias | **Depende de:** Fase 7, 10

| Bloco | Descrição | Arquivos |
|-------|-----------|----------|
| 11.1 | Testes | `.github/workflows/tests.yml` |
| 11.2 | Qualidade | `.github/workflows/lint.yml` |
| 11.3 | Release | `.github/workflows/release.yml` |
| 11.4 | Ferramentas | `.pre-commit-config.yaml`, `dependabot.yml` |

---

### FASE 12: Release & Distribuição
**Estimativa:** 1-2 dias | **Depende de:** Todas

| Bloco | Descrição | Ação |
|-------|-----------|------|
| 12.1 | Preparação | Versionamento, release notes, checklist |
| 12.2 | Publicação | GitHub Release, PyPI, GitHub Pages |

---

## 5. Marcos (Milestones)

| Marco | Descrição | Fases | Data Alvo |
|-------|-----------|-------|-----------|
| **M1** | Planejamento Completo | 0 | Semana 1 |
| **M2** | Core Funcional | 1, 2 | Semana 2 |
| **M3** | MVP Funcional | 3, 4 | Semana 4 |
| **M4** | Features Completas | 5, 6, 8 | Semana 6 |
| **M5** | Qualidade Garantida | 7 | Semana 8 |
| **M6** | Pronto para Release | 9, 10, 11 | Semana 10 |
| **M7** | v0.1.0 Publicado | 12 | Semana 12 |

---

## 6. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Escopo cresce demais | Média | Alto | MVP bem definido, features para v0.2+ |
| Compatibilidade OS | Baixa | Médio | Testes em matrix CI (Win/Linux/Mac) |
| Dependência quebra | Baixa | Médio | Versões fixadas, Dependabot |
| Falta de tempo | Média | Alto | Priorização, fases opcionais |

---

## 7. Progresso Atual

```
FASE 0  [####################] 100% ✅ Planejamento
FASE 1  [....................]   0% ⏳ Setup
FASE 2  [....................]   0% ⏳ Core
FASE 3  [....................]   0% ⏳ Tasks
FASE 4  [....................]   0% ⏳ CLI
FASE 5  [....................]   0% ⏳ Agendamento
FASE 6  [....................]   0% ⏳ Notificações
FASE 7  [....................]   0% ⏳ Testes
FASE 8  [....................]   0% ⏳ Organizador
FASE 9  [....................]   0% ⏳ Documentação
FASE 10 [....................]   0% ⏳ Empacotamento
FASE 11 [....................]   0% ⏳ CI/CD
FASE 12 [....................]   0% ⏳ Release

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROGRESSO TOTAL: ██.................. 8% (1/13 fases)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 8. Próximos Passos

### Imediato (Fase 1 - Setup)
1. [ ] Criar repositório Git
2. [ ] Configurar ambiente virtual
3. [ ] Criar pyproject.toml básico
4. [ ] Criar estrutura de diretórios
5. [ ] Criar .gitignore e .env.example
6. [ ] Criar README.md inicial

### Curto Prazo (Fases 2-4)
1. [ ] Implementar config.py e logger.py
2. [ ] Implementar BaseTask
3. [ ] Implementar tasks principais
4. [ ] Implementar CLI básica

---

## 9. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|--------|------|-------|-----------|
| 1.0 | Dez/2025 | - | Versão inicial aprovada |

---

*Documento gerado como parte da Fase 0.5 - Cronograma Inicial*
*Localização: `docs/planejamento/CRONOGRAMA.md`*
