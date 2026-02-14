# 🚀 Primeiros Passos com AutoTarefas

Este tutorial vai guiá-lo através da instalação e uso básico do AutoTarefas.

## Índice

1. [Instalação](#1-instalação)
2. [Primeira Execução](#2-primeira-execução)
3. [Monitorando o Sistema](#3-monitorando-o-sistema)
4. [Organizando Arquivos](#4-organizando-arquivos)
5. [Fazendo Backup](#5-fazendo-backup)
6. [Limpando Arquivos](#6-limpando-arquivos)
7. [Agendando Tarefas](#7-agendando-tarefas)
8. [Próximos Passos](#8-próximos-passos)

---

## 1. Instalação

### Requisitos

- Python 3.12 ou superior
- pip (gerenciador de pacotes)

### Instalação via pip

```bash
pip install autotarefas
```

### Verificar instalação

```bash
autotarefas --version
```

Você deve ver algo como:
```
╭──────────────────────────╮
│ AutoTarefas versão 0.1.0 │
╰──────────────────────────╯
```

---

## 2. Primeira Execução

### Ver ajuda geral

```bash
autotarefas --help
```

Isso mostrará todos os comandos disponíveis:

```
╭──────────────────────────────────────────────────────╮
│ AutoTarefas v0.1.0 - Sistema de Automação de Tarefas │
╰──────────────────────────────────────────────────────╯

Comandos disponíveis:
  backup      Gerencia backups de arquivos e diretórios
  clean       Limpa arquivos temporários e lixo
  email       Gerencia emails e notificações
  monitor     Monitora recursos do sistema
  organize    Organiza arquivos em pastas por tipo
  report      Gera relatórios
  schedule    Gerencia agendamento de tarefas
```

### Inicializar configuração (opcional)

```bash
autotarefas init
```

Isso cria o diretório de configuração em `~/.autotarefas/`.

---

## 3. Monitorando o Sistema

O monitor mostra CPU, memória e disco em tempo real.

### Status básico

```bash
autotarefas monitor status
```

Saída:
```
╭─────────────────────── Status do Sistema ────────────────────────╮
│   CPU          [██░░░░░░░░░░░░░░░░░░] 10.2%                      │
│   Memória      [████████░░░░░░░░░░░░] 40.8% (13.0 GB / 31.9 GB)  │
│   Disco C:\    [█████████████████░░░] 86.5% (62.4 GB livre)      │
╰──────────────────────────────────────────────────────────────────╯
```

### Status completo

```bash
autotarefas monitor status --all --network
```

Adiciona informações de rede e sistema (uptime, hostname, etc.).

### Saída em JSON (para scripts)

```bash
autotarefas monitor status --json
```

---

## 4. Organizando Arquivos

O organizador move arquivos para pastas por tipo (Documentos, Imagens, Vídeos, etc.).

### Ver o que seria organizado (preview)

```bash
autotarefas organize preview ~/Downloads
```

Saída:
```
                    📋 12 arquivos seriam organizados
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Destino        ┃ Arquivos ┃ Exemplos                              ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 📁 Documentos/ │        5 │ relatorio.pdf, planilha.xlsx ...      │
│ 📁 Imagens/    │        4 │ foto.jpg, screenshot.png ...          │
│ 📁 Videos/     │        2 │ video.mp4, clip.mov                   │
└────────────────┴──────────┴───────────────────────────────────────┘
```

### Ver estatísticas

```bash
autotarefas organize stats ~/Downloads
```

### Ver regras de categorização

```bash
autotarefas organize rules
```

### Executar organização

```bash
# Modo seguro (com confirmação)
autotarefas organize run ~/Downloads

# Modo dry-run (simula, não move)
autotarefas organize run ~/Downloads --dry-run
```

### Perfis de organização

```bash
# Por categoria (padrão)
autotarefas organize run ~/Downloads --profile default

# Por data de modificação
autotarefas organize run ~/Downloads --profile by_date

# Por extensão
autotarefas organize run ~/Downloads --profile by_extension
```

---

## 5. Fazendo Backup

### Criar backup simples

```bash
autotarefas backup run ~/Documents -d ~/backups
```

Isso cria um arquivo ZIP com todos os documentos.

### Escolher tipo de compressão

```bash
# ZIP (padrão)
autotarefas backup run ~/Documents -d ~/backups --compression zip

# TAR.GZ (melhor compressão)
autotarefas backup run ~/Documents -d ~/backups --compression tar.gz

# TAR.BZ2 (máxima compressão)
autotarefas backup run ~/Documents -d ~/backups --compression tar.bz2
```

### Excluir arquivos do backup

```bash
autotarefas backup run ~/Documents -d ~/backups --exclude "*.tmp" --exclude "cache/*"
```

### Listar backups existentes

```bash
autotarefas backup list ~/backups
```

Saída:
```
                    Backups em ~/backups
┏━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ # ┃ Arquivo                          ┃ Tamanho ┃ Data             ┃
┡━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ 1 │ Documents_20260210_153621.zip    │  45 MB  │ 10/02/2026 15:36 │
│ 2 │ Documents_20260209_020000.zip    │  44 MB  │ 09/02/2026 02:00 │
└───┴──────────────────────────────────┴─────────┴──────────────────┘
```

### Restaurar backup

```bash
autotarefas backup restore ~/backups/Documents_20260210.zip -d ~/restored
```

---

## 6. Limpando Arquivos

O cleaner remove arquivos temporários, logs antigos e cache.

### Ver perfis disponíveis

```bash
autotarefas clean profiles
```

Saída:
```
        Perfis Disponíveis
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Nome        ┃ Descrição         ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ temp_files  │ Arquivos .tmp     │
│ log_files   │ Arquivos .log     │
│ cache_files │ Cache de apps     │
│ downloads   │ Downloads antigos │
│ thumbnails  │ Miniaturas        │
└─────────────┴───────────────────┘
```

### Preview (ver o que seria removido)

```bash
autotarefas clean preview ~/temp --profile temp_files
```

### Executar limpeza

```bash
# Com perfil
autotarefas clean run ~/temp --profile temp_files

# Por extensão
autotarefas clean run ~/temp --extension .log --extension .tmp

# Por idade (arquivos mais velhos que 30 dias)
autotarefas clean run ~/Downloads --days 30
```

### Modo dry-run

```bash
autotarefas clean run ~/temp --profile temp_files --dry-run
```

---

## 7. Agendando Tarefas

O scheduler permite agendar tarefas para execução automática.

### Ver tarefas disponíveis

```bash
autotarefas schedule tasks
```

### Adicionar job

```bash
# Backup diário às 2h da manhã
autotarefas schedule add backup-diario backup "02:00" --type daily

# Monitor a cada hora
autotarefas schedule add monitor-hourly monitor "3600" --type interval

# Limpeza semanal (cron)
autotarefas schedule add limpeza-semanal cleaner "0 3 * * 0" --type cron
```

### Listar jobs agendados

```bash
autotarefas schedule list
```

### Ver status do scheduler

```bash
autotarefas schedule status
```

### Iniciar/parar scheduler

```bash
# Iniciar
autotarefas schedule start

# Parar
autotarefas schedule stop
```

### Executar job manualmente

```bash
autotarefas schedule run backup-diario
```

---

## 8. Próximos Passos

### Configurar notificações por email

1. Copie o arquivo de exemplo:
   ```bash
   cp .env.example .env
   ```

2. Configure suas credenciais SMTP:
   ```env
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USER=seu-email@gmail.com
   EMAIL_PASSWORD=sua-senha-de-app
   ```

3. Teste:
   ```bash
   autotarefas email test
   ```

### Criar scripts de automação

Combine comandos em scripts:

```bash
#!/bin/bash
# backup_e_limpa.sh

# Fazer backup
autotarefas backup run ~/Documents -d ~/backups

# Limpar temporários
autotarefas clean run ~/temp --profile temp_files

# Notificar
autotarefas email notify "Backup e limpeza concluídos!" --level success
```

### Explorar mais comandos

```bash
# Ajuda de qualquer comando
autotarefas backup --help
autotarefas organize run --help
autotarefas schedule add --help
```

---

## Dicas

1. **Use --dry-run primeiro**: Sempre teste com `--dry-run` antes de executar operações destrutivas.

2. **Preview antes de organizar**: Use `organize preview` para ver o que será movido.

3. **Backups incrementais**: Agende backups diários para não perder dados.

4. **Monitore o disco**: O monitor alerta quando o disco está cheio (>80%).

5. **Logs detalhados**: Use `-v` para modo verboso em qualquer comando.

---

## Precisa de ajuda?

- [Documentação completa](https://github.com/paulor007/autotarefas#readme)
- [Reportar problema](https://github.com/paulor007/autotarefas/issues)
- [Discussões](https://github.com/paulor007/autotarefas/discussions)

---

*Bom proveito! 🎉*
