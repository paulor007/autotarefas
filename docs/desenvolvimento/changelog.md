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

Esta é a primeira versão estável do AutoTarefas.

### Adicionado

#### Core
- **BaseTask**: Classe base para tarefas com retry e timeout
- **TaskResult**: Resultado padronizado de execução
- **Logger**: Sistema de logging com Loguru
- **Scheduler**: Agendador com cron e intervalos
- **Email**: Envio de notificações via SMTP

#### Tarefas
- **BackupTask**: Backup com compressão ZIP/TAR.GZ
- **CleanerTask**: Limpeza inteligente de arquivos
- **MonitorTask**: Monitoramento de CPU, memória, disco
- **ReporterTask**: Geração de relatórios

#### CLI
- `autotarefas init` - Inicialização
- `autotarefas backup` - Gerenciamento de backups
- `autotarefas clean` - Limpeza de arquivos
- `autotarefas monitor` - Monitoramento
- `autotarefas schedule` - Agendamento
- `autotarefas email` - Notificações
- `autotarefas report` - Relatórios

#### Documentação
- Documentação completa com MkDocs
- Guias de usuário para cada módulo
- Referência de API
- Guia de contribuição

### Segurança
- Senhas não são logadas
- Credenciais via variáveis de ambiente
- Validação de caminhos (path traversal)

### Compatibilidade
- Python 3.12, 3.13, 3.14
- Linux, macOS, Windows

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
