# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não Lançado]

### Em Desenvolvimento
- Integração com serviços de nuvem (Google Drive, Dropbox)
- Dashboard web para monitoramento
- Suporte a plugins externos
- API REST para automação externa

---

## [1.0.0] - 2025-02-11

### 🎉 Primeira Versão Estável

Esta é a primeira versão estável do AutoTarefas, um sistema completo para automação
de tarefas repetitivas do computador.

### Adicionado

#### Core
- **BaseTask**: Classe base abstrata para todas as tarefas
  - Sistema de retry configurável com backoff exponencial
  - Timeout de execução por tarefa
  - Callbacks para sucesso, falha e conclusão
  - Hooks de pré e pós-execução
  - Contexto compartilhado entre tarefas

- **TaskResult**: Resultado padronizado de execução
  - Status (SUCCESS, FAILURE, SKIPPED, TIMEOUT, CANCELLED)
  - Tempo de execução e métricas
  - Mensagens de erro estruturadas
  - Suporte a dados adicionais

- **Logger**: Sistema de logging avançado com Loguru
  - Rotação automática de arquivos (10MB)
  - Retenção configurável (30 dias)
  - Formatação colorida no console
  - Logs JSON para integração com ferramentas

- **Scheduler**: Agendador de tarefas
  - Expressões cron completas
  - Intervalos (segundos, minutos, horas, dias)
  - Agendamento específico (data/hora exata)
  - Persistência de jobs em JSON
  - Histórico de execuções

- **Email**: Sistema de notificações
  - Envio via SMTP com TLS/SSL
  - Templates HTML com Jinja2
  - Suporte a anexos
  - Notificações de sucesso/falha
  - Relatórios formatados

#### Tarefas Implementadas

- **BackupTask**: Backup automático de arquivos
  - Backup completo ou incremental
  - Compressão ZIP ou TAR.GZ
  - Múltiplas origens por destino
  - Verificação de integridade
  - Estatísticas detalhadas

- **CleanerTask**: Limpeza de arquivos
  - Filtros por idade, tamanho e padrão
  - Modo preview (dry-run)
  - Proteção de arquivos por regex
  - Integração com lixeira do sistema
  - Relatório de espaço liberado

- **MonitorTask**: Monitoramento do sistema
  - CPU, memória, disco e rede
  - Alertas configuráveis por limite
  - Histórico de métricas
  - Detecção de processos problemáticos
  - Exportação de métricas

- **ReporterTask**: Geração de relatórios
  - Relatórios de vendas em Excel
  - Templates customizáveis
  - Múltiplos formatos (XLSX, CSV, HTML)
  - Gráficos automáticos

#### CLI Completa

- `autotarefas init` - Inicialização do projeto
  - Criação de estrutura de diretórios
  - Geração de arquivo .env de exemplo
  - Configuração interativa

- `autotarefas backup` - Gerenciamento de backups
  - `run` - Executar backup manual
  - `list` - Listar backups existentes
  - `restore` - Restaurar backup
  - `clean` - Limpar backups antigos

- `autotarefas clean` - Limpeza de arquivos
  - `run` - Executar limpeza
  - `preview` - Visualizar o que seria limpo
  - `stats` - Estatísticas de uso

- `autotarefas monitor` - Monitoramento
  - `status` - Status atual do sistema
  - `watch` - Monitoramento contínuo
  - `alerts` - Configurar alertas
  - `history` - Histórico de métricas

- `autotarefas schedule` - Agendamento
  - `add` - Adicionar tarefa agendada
  - `list` - Listar tarefas
  - `remove` - Remover tarefa
  - `run` - Executar agendador
  - `history` - Histórico de execuções

- `autotarefas email` - Notificações
  - `test` - Testar configuração
  - `send` - Enviar email manual
  - `templates` - Listar templates

- `autotarefas report` - Relatórios
  - `generate` - Gerar relatório
  - `templates` - Listar templates

#### Utilitários

- **datetime_utils**: Manipulação de datas
  - Parse de strings para datetime
  - Formatação localizada
  - Cálculo de períodos

- **format_utils**: Formatação de dados
  - Tamanhos de arquivo (bytes para KB/MB/GB)
  - Duração (segundos para formato legível)
  - Números com separadores de milhar

- **json_utils**: Manipulação de JSON
  - Encoder customizado para datetime, Path, etc.
  - Merge profundo de dicionários
  - Serialização segura

- **helpers**: Funções auxiliares
  - Decoradores de retry e timeout
  - Validadores de configuração
  - Geradores de identificadores

#### Configuração

- Arquivo `.env` para variáveis de ambiente
- `autotarefas.json` para configurações persistentes
- Validação de configuração na inicialização
- Valores padrão sensatos

#### Testes

- **93% de cobertura de código**
- Testes unitários para todos os módulos
- Testes de integração para fluxos completos
- Testes E2E para a CLI
- Fixtures reutilizáveis
- Mocks para serviços externos (SMTP, filesystem)

#### Documentação

- README.md com guia de início rápido
- Docstrings em todas as classes e funções
- Exemplos de uso em cada módulo
- CONTRIBUTING.md para contribuidores
- Este CHANGELOG

### Segurança

- Senhas não são logadas
- Credenciais via variáveis de ambiente
- Validação de caminhos (path traversal)
- Timeout em todas as operações de rede

### Compatibilidade

- Python 3.12, 3.13, 3.14
- Linux, macOS, Windows
- CLI multiplataforma com Rich

---

## [0.1.0] - 2025-01-15

### Adicionado
- Estrutura inicial do projeto
- Módulos core básicos
- Configuração inicial
- Primeiros testes

---

## Tipos de Mudanças

- `Adicionado` para novas funcionalidades
- `Modificado` para mudanças em funcionalidades existentes
- `Obsoleto` para funcionalidades que serão removidas em breve
- `Removido` para funcionalidades removidas
- `Corrigido` para correções de bugs
- `Segurança` para correções de vulnerabilidades

---

## Links

[Não Lançado]: https://github.com/paulor007/autotarefas/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/paulor007/autotarefas/releases/tag/v1.0.0
[0.1.0]: https://github.com/paulor007/autotarefas/releases/tag/v0.1.0
