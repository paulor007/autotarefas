# Uso Básico

Guia rápido para começar a usar o AutoTarefas.

---

## Visão Geral

O AutoTarefas é uma ferramenta de linha de comando (CLI) para automatizar tarefas do dia a dia:

| Comando | Função |
|---------|--------|
| `backup` | Gerencia backups de arquivos e diretórios |
| `clean` | Limpa arquivos temporários e lixo |
| `monitor` | Monitora recursos do sistema |
| `schedule` | Agenda tarefas automáticas |
| `report` | Gera relatórios |
| `email` | Gerencia notificações por email |

---

## Ajuda Rápida

```bash
# Ver todos os comandos
autotarefas --help

# Ajuda de um comando específico
autotarefas backup --help
autotarefas clean --help
```

---

## Opções Globais

Estas opções funcionam com qualquer comando:

| Opção | Descrição |
|-------|-----------|
| `-v, --verbose` | Modo detalhado (mais informações no log) |
| `-q, --quiet` | Modo silencioso (apenas erros) |
| `--dry-run` | Simula execução sem fazer alterações |
| `--version` | Mostra versão do AutoTarefas |
| `-h, --help` | Mostra ajuda |

**Exemplo com dry-run:**

```bash
# Simula backup sem criar arquivo
autotarefas --dry-run backup run ~/Documentos
```

---

## Backup

### Criar um Backup

```bash
# Backup simples
autotarefas backup run ~/Documentos

# Backup com destino específico
autotarefas backup run ~/Documentos -d /mnt/backup

# Backup com compressão tar.gz
autotarefas backup run ~/Projetos -c tar.gz

# Excluir pastas do backup
autotarefas backup run ~/Projetos -e __pycache__ -e .git -e node_modules
```

### Listar Backups

```bash
# Listar todos os backups
autotarefas backup list

# Listar backups de um diretório específico
autotarefas backup list -d /mnt/backup

# Filtrar por nome
autotarefas backup list -n documentos
```

### Restaurar Backup

```bash
# Restaurar no diretório atual
autotarefas backup restore backup_20240115.zip

# Restaurar em local específico
autotarefas backup restore backup_20240115.zip -d ~/Restaurado

# Sobrescrever arquivos existentes
autotarefas backup restore backup_20240115.zip -f
```

### Limpar Backups Antigos

```bash
# Manter apenas os 5 mais recentes
autotarefas backup cleanup -k 5

# Sem pedir confirmação
autotarefas backup cleanup -k 3 -y
```

---

## Limpeza

### Executar Limpeza

```bash
# Limpar arquivos temporários
autotarefas clean run /tmp

# Limpar múltiplos diretórios
autotarefas clean run /tmp ~/.cache

# Usar perfil específico
autotarefas clean run ~/Downloads --profile downloads

# Limpar arquivos com mais de 30 dias
autotarefas clean run ~/Downloads --profile downloads --days 30

# Limpar extensões específicas
autotarefas clean run /var/log -e .log -e .log.1 --days 7
```

### Visualizar Antes de Limpar

```bash
# Preview do que será removido
autotarefas clean preview /tmp

# Preview com perfil específico
autotarefas clean preview ~/Downloads --profile downloads
```

### Ver Perfis Disponíveis

```bash
autotarefas clean profiles
```

**Perfis comuns:**

| Perfil | Descrição |
|--------|-----------|
| `temp_files` | Arquivos temporários (.tmp, .temp, ~) |
| `cache_files` | Arquivos de cache |
| `downloads` | Downloads antigos |
| `logs` | Arquivos de log |

---

## Monitoramento

### Status Atual

```bash
# Status básico
autotarefas monitor status

# Status completo (inclui sistema e rede)
autotarefas monitor status --all

# Incluir métricas de rede
autotarefas monitor status --network

# Saída em JSON (para scripts)
autotarefas monitor status --json
```

### Verificação Rápida

```bash
# Uma linha com CPU, memória e disco
autotarefas monitor quick

# Saída: CPU: 15% | Mem: 42% | Disco: 65%
```

### Monitoramento em Tempo Real

```bash
# Atualiza a cada 2 segundos (padrão)
autotarefas monitor live

# Atualiza a cada 5 segundos
autotarefas monitor live -i 5

# Com informações de rede
autotarefas monitor live --network

# Pressione Ctrl+C para sair
```

---

## Agendamento

### Listar Tarefas Agendadas

```bash
autotarefas schedule list
```

### Agendar Backup Diário

```bash
autotarefas schedule add backup-diario \
  --command "backup run ~/Documentos" \
  --cron "0 8 * * *"  # Todo dia às 8h
```

### Agendar Limpeza Semanal

```bash
autotarefas schedule add limpeza-semanal \
  --command "clean run /tmp --profile temp_files" \
  --cron "0 2 * * 0"  # Todo domingo às 2h
```

### Remover Agendamento

```bash
autotarefas schedule remove backup-diario
```

---

## Exemplos do Dia a Dia

### Rotina de Backup Completa

```bash
# 1. Criar backup
autotarefas backup run ~/Projetos -d /mnt/backup -c tar.gz -e node_modules -e .git

# 2. Verificar backup criado
autotarefas backup list -d /mnt/backup

# 3. Limpar backups antigos (manter 10)
autotarefas backup cleanup -d /mnt/backup -k 10 -y
```

### Limpeza Mensal do Sistema

```bash
# 1. Preview primeiro
autotarefas clean preview /tmp ~/.cache ~/Downloads

# 2. Limpar temporários
autotarefas clean run /tmp --profile temp_files

# 3. Limpar downloads antigos (>60 dias)
autotarefas clean run ~/Downloads --profile downloads --days 60
```

### Monitorar Servidor

```bash
# Verificação rápida (para scripts)
autotarefas monitor quick

# Monitorar continuamente
autotarefas monitor live --all -i 10
```

---

## Dicas Úteis

### Usar Dry-Run Antes de Executar

Sempre teste comandos destrutivos primeiro:

```bash
# Testar limpeza
autotarefas --dry-run clean run ~/Downloads --days 7

# Se estiver ok, executar de verdade
autotarefas clean run ~/Downloads --days 7
```

### Combinar com Cron (Linux/macOS)

```bash
# Editar crontab
crontab -e

# Adicionar backup diário às 3h
0 3 * * * /usr/local/bin/autotarefas backup run ~/Documentos -d /backup >> /var/log/autotarefas.log 2>&1
```

### Alias para Comandos Frequentes

Adicione ao seu `~/.bashrc` ou `~/.zshrc`:

```bash
alias at='autotarefas'
alias at-status='autotarefas monitor quick'
alias at-backup='autotarefas backup run ~/Documentos'
```

---

## Códigos de Saída

| Código | Significado |
|--------|-------------|
| 0 | Sucesso |
| 1 | Erro geral |
| 2 | Erro de uso (parâmetros inválidos) |
| 130 | Interrompido pelo usuário (Ctrl+C) |

Útil para scripts:

```bash
autotarefas backup run ~/Docs && echo "Backup OK" || echo "Backup falhou"
```

---

## Próximos Passos

- [Guia de Backup](backup.md) - Estratégias avançadas de backup
- [Guia de Limpeza](limpeza.md) - Criar perfis personalizados
- [Guia de Agendamento](agendamento.md) - Automatizar tarefas
- [Configuração](configuracao.md) - Personalizar o AutoTarefas

---

*AutoTarefas - Sistema de Automação de Tarefas*
