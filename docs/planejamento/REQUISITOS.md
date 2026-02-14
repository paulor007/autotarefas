# 📋 Definição de Requisitos - AutoTarefas

**Versão:** 1.0
**Data:** Dezembro 2025
**Status:** Aprovado

---

## 1. Visão Geral do Projeto

### 1.1 Descrição
O **AutoTarefas** é um sistema de automação de tarefas em Python, projetado para executar operações repetitivas de forma organizada, confiável e agendável. Funciona como um "assistente de sistema" via linha de comando.

### 1.2 Objetivo Principal
Automatizar tarefas comuns de manutenção e organização do computador, eliminando trabalho manual repetitivo e garantindo execução consistente.

### 1.3 Público-Alvo
- Desenvolvedores e profissionais de TI
- Usuários avançados que utilizam terminal
- Administradores de sistemas
- Qualquer pessoa que queira automatizar tarefas no computador

---

## 2. Requisitos Funcionais (RF)

### 2.1 Módulo de Backup (RF-BACKUP)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-BACKUP-01 | O sistema deve permitir criar backups de arquivos e pastas | Alta |
| RF-BACKUP-02 | O sistema deve suportar compressão (zip, tar.gz, tar.bz2) | Alta |
| RF-BACKUP-03 | O sistema deve permitir restaurar backups existentes | Alta |
| RF-BACKUP-04 | O sistema deve listar backups disponíveis com metadados | Média |
| RF-BACKUP-05 | O sistema deve validar integridade do backup após criação | Média |
| RF-BACKUP-06 | O sistema deve suportar backup incremental | Baixa |
| RF-BACKUP-07 | O sistema deve permitir definir políticas de retenção | Baixa |

### 2.2 Módulo de Limpeza (RF-CLEANER)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-CLEANER-01 | O sistema deve limpar arquivos temporários do sistema | Alta |
| RF-CLEANER-02 | O sistema deve suportar perfis de limpeza pré-definidos | Alta |
| RF-CLEANER-03 | O sistema deve exibir prévia antes de deletar (dry-run) | Alta |
| RF-CLEANER-04 | O sistema deve calcular espaço liberado | Média |
| RF-CLEANER-05 | O sistema deve gerenciar a lixeira do sistema | Média |
| RF-CLEANER-06 | O sistema deve permitir perfis personalizados | Baixa |
| RF-CLEANER-07 | O sistema deve proteger arquivos críticos do sistema | Alta |

### 2.3 Módulo de Monitoramento (RF-MONITOR)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-MONITOR-01 | O sistema deve exibir uso de CPU em tempo real | Alta |
| RF-MONITOR-02 | O sistema deve exibir uso de memória RAM | Alta |
| RF-MONITOR-03 | O sistema deve exibir uso de disco | Alta |
| RF-MONITOR-04 | O sistema deve suportar modo live (atualização contínua) | Média |
| RF-MONITOR-05 | O sistema deve manter histórico de métricas | Média |
| RF-MONITOR-06 | O sistema deve alertar quando limites forem atingidos | Média |
| RF-MONITOR-07 | O sistema deve exibir informações de rede | Baixa |

### 2.4 Módulo de Organização de Arquivos (RF-ORGANIZER)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-ORGANIZER-01 | O sistema deve organizar arquivos por extensão/tipo | Alta |
| RF-ORGANIZER-02 | O sistema deve suportar perfis de organização | Alta |
| RF-ORGANIZER-03 | O sistema deve exibir prévia antes de mover (dry-run) | Alta |
| RF-ORGANIZER-04 | O sistema deve permitir desfazer organização (undo) | Alta |
| RF-ORGANIZER-05 | O sistema deve manter histórico de movimentações | Média |
| RF-ORGANIZER-06 | O sistema deve resolver conflitos de nomes | Média |
| RF-ORGANIZER-07 | O sistema deve suportar regras personalizadas | Baixa |

### 2.5 Módulo de Agendamento (RF-SCHEDULER)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-SCHEDULER-01 | O sistema deve agendar tarefas para execução automática | Alta |
| RF-SCHEDULER-02 | O sistema deve suportar intervalos (a cada X minutos/horas) | Alta |
| RF-SCHEDULER-03 | O sistema deve suportar horários específicos (diário, semanal) | Alta |
| RF-SCHEDULER-04 | O sistema deve persistir jobs entre reinicializações | Alta |
| RF-SCHEDULER-05 | O sistema deve manter histórico de execuções | Média |
| RF-SCHEDULER-06 | O sistema deve permitir pausar/retomar jobs | Média |
| RF-SCHEDULER-07 | O sistema deve evitar execuções duplicadas (lock) | Média |
| RF-SCHEDULER-08 | O sistema deve permitir export/import de configurações | Baixa |

### 2.6 Módulo de Notificações (RF-NOTIFY)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-NOTIFY-01 | O sistema deve enviar notificações por email | Alta |
| RF-NOTIFY-02 | O sistema deve suportar templates HTML para emails | Média |
| RF-NOTIFY-03 | O sistema deve permitir anexos em emails | Média |
| RF-NOTIFY-04 | O sistema deve suportar níveis de severidade | Média |
| RF-NOTIFY-05 | O sistema deve manter fila de emails pendentes | Baixa |
| RF-NOTIFY-06 | O sistema deve suportar múltiplos provedores SMTP | Baixa |

### 2.7 Módulo de Relatórios (RF-REPORTER)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-REPORTER-01 | O sistema deve gerar relatórios de execução | Alta |
| RF-REPORTER-02 | O sistema deve processar relatórios de vendas (Excel) | Média |
| RF-REPORTER-03 | O sistema deve exportar relatórios em múltiplos formatos | Baixa |

### 2.8 Interface CLI (RF-CLI)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-CLI-01 | O sistema deve ter interface de linha de comando intuitiva | Alta |
| RF-CLI-02 | O sistema deve exibir ajuda detalhada para cada comando | Alta |
| RF-CLI-03 | O sistema deve usar cores e formatação rica no terminal | Média |
| RF-CLI-04 | O sistema deve exibir barras de progresso em operações longas | Média |
| RF-CLI-05 | O sistema deve suportar modo silencioso (quiet) | Baixa |
| RF-CLI-06 | O sistema deve suportar output em JSON para automação | Baixa |

---

## 3. Requisitos Não-Funcionais (RNF)

### 3.1 Desempenho

| ID | Requisito | Métrica |
|----|-----------|---------|
| RNF-PERF-01 | Tempo de inicialização da CLI | < 1 segundo |
| RNF-PERF-02 | Consumo de memória em idle | < 50 MB |
| RNF-PERF-03 | Processamento de backup (arquivos pequenos) | > 100 arquivos/s |

### 3.2 Confiabilidade

| ID | Requisito | Métrica |
|----|-----------|---------|
| RNF-REL-01 | Taxa de sucesso em operações de backup | > 99.9% |
| RNF-REL-02 | Recuperação após falha | Automática com log |
| RNF-REL-03 | Validação de dados antes de operações destrutivas | 100% |

### 3.3 Usabilidade

| ID | Requisito | Descrição |
|----|-----------|-----------|
| RNF-USA-01 | Mensagens de erro claras e acionáveis | Sempre indicar como resolver |
| RNF-USA-02 | Confirmação antes de operações destrutivas | Prompt interativo |
| RNF-USA-03 | Documentação completa | README, CLI help, docs online |

### 3.4 Manutenibilidade

| ID | Requisito | Métrica |
|----|-----------|---------|
| RNF-MAN-01 | Cobertura de testes | > 80% |
| RNF-MAN-02 | Código tipado (type hints) | 100% |
| RNF-MAN-03 | Documentação de código (docstrings) | 100% funções públicas |
| RNF-MAN-04 | Linting sem erros | ruff/flake8 clean |

### 3.5 Portabilidade

| ID | Requisito | Descrição |
|----|-----------|-----------|
| RNF-PORT-01 | Suporte a Windows 10/11 | Testado |
| RNF-PORT-02 | Suporte a Linux (Ubuntu 20.04+) | Testado |
| RNF-PORT-03 | Suporte a macOS 12+ | Testado |
| RNF-PORT-04 | Python 3.11, 3.12, 3.13 | Matriz de testes CI |

### 3.6 Segurança

| ID | Requisito | Descrição |
|----|-----------|-----------|
| RNF-SEC-01 | Credenciais em variáveis de ambiente | Nunca em código |
| RNF-SEC-02 | Logs sem dados sensíveis | Sanitização automática |
| RNF-SEC-03 | Validação de caminhos (path traversal) | Prevenção ativa |

---

## 4. Requisitos de Sistema

### 4.1 Ambiente de Execução

| Componente | Requisito Mínimo | Recomendado |
|------------|------------------|-------------|
| Python | 3.12 | 3.14+ |
| RAM | 256 MB | 512 MB |
| Disco | 50 MB (instalação) | 100 MB |
| SO | Windows 10 / Linux / macOS | Qualquer |

### 4.2 Dependências Principais

| Biblioteca | Versão | Propósito |
|------------|--------|-----------|
| click | >=8.1,<9 | CLI framework |
| rich | >=13,<15 | Interface terminal rica |
| loguru | >=0.7,<1 | Sistema de logging |
| schedule | >=1.2,<2 | Agendamento de tarefas |
| psutil | >=5.9,<8 | Monitoramento de sistema |
| pytest | >=8,<10 | Framework de testes |
| python-dotenv | >=1,<2 | Variáveis de ambiente |

### 4.3 Dependências Opcionais

| Biblioteca | Versão | Propósito |
|------------|--------|-----------|
| pandas | >= 2.0 | Processamento de relatórios |
| openpyxl | >= 3.1 | Leitura/escrita Excel |
| jinja2 | >= 3.1 | Templates de email |

---

## 5. Escopo do MVP (v0.1.0)

### 5.1 Incluído no MVP

| Módulo | Funcionalidades |
|--------|-----------------|
| **Backup** | Criar, listar, restaurar (zip) |
| **Cleaner** | Limpeza básica, dry-run, perfis padrão |
| **Monitor** | Status CPU/RAM/disco, modo minimal |
| **Organizer** | Organizar por extensão, preview, undo |
| **Scheduler** | Agendar, listar, pausar, persistência básica |
| **Email** | Envio básico, teste de conexão |
| **CLI** | Todos os comandos principais |

### 5.2 Fora do MVP (versões futuras)

| Funcionalidade | Versão Planejada |
|----------------|------------------|
| Backup incremental | v0.2.0 |
| Notificações Slack/Discord | v0.2.0 |
| Interface web (dashboard) | v0.3.0 |
| Plugins de terceiros | v0.4.0 |
| Sincronização cloud | v1.0.0 |

---

## 6. Restrições e Premissas

### 6.1 Restrições

1. **Sem interface gráfica** - Apenas CLI na v0.x
2. **Sem daemon em background** - Scheduler requer terminal aberto (v0.1)
3. **Apenas email** - Outros canais de notificação em versões futuras
4. **Sem autenticação** - Uso local, single-user

### 6.2 Premissas

1. Usuário tem permissões adequadas no sistema de arquivos
2. Conexão com internet para envio de emails
3. Python 3.12+ instalado no sistema
4. Familiaridade básica com terminal/linha de comando

---

## 7. Critérios de Aceitação

### 7.1 Para cada módulo

- [ ] Todos os requisitos de prioridade **Alta** implementados
- [ ] Testes unitários com cobertura > 80%
- [ ] Documentação de uso atualizada
- [ ] Sem erros de linting
- [ ] Code review aprovado

### 7.2 Para release MVP (v0.1.0)

- [ ] Todas as fases 0-8 concluídas
- [ ] Testes passando em Python 3.11, 3.12, 3.13
- [ ] Documentação completa (README, docs/, examples/)
- [ ] Instalável via pip (TestPyPI validado)
- [ ] CI/CD configurado e funcionando

---

## 8. Glossário

| Termo | Definição |
|-------|-----------|
| **CLI** | Command Line Interface - Interface de linha de comando |
| **Dry-run** | Execução simulada, sem efeitos reais |
| **Job** | Tarefa agendada para execução automática |
| **Task** | Unidade de trabalho executável (backup, limpeza, etc) |
| **Profile** | Conjunto pré-definido de configurações |
| **MVP** | Minimum Viable Product - Produto mínimo viável |

---

## 9. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|--------|------|-------|-----------|
| 1.0 | Dez/2025 | - | Versão inicial aprovada |

---

*Documento gerado como parte da Fase 0.1 - Definição de Requisitos*
