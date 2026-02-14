# Instalação

Guia completo para instalar o AutoTarefas no seu sistema.

---

## Requisitos

Antes de instalar, certifique-se de ter:

| Requisito | Versão Mínima | Verificar |
|-----------|---------------|-----------|
| Python | 3.12+ | `python --version` |
| pip | 21.0+ | `pip --version` |

---

## Instalação Rápida

### Via pip (Recomendado)

```bash
pip install autotarefas
```

### Verificar Instalação

```bash
autotarefas --version
```

Deve exibir algo como:

```
╭─────────────────────────────────────╮
│ AutoTarefas versão 0.1.0            │
╰─────────────────────────────────────╯
```

---

## Opções de Instalação

### Instalação Básica

Instala apenas as dependências essenciais:

```bash
pip install autotarefas
```

**Inclui:** backup, limpeza, monitoramento, agendamento.

### Com Relatórios Excel

Para gerar relatórios em formato Excel:

```bash
pip install autotarefas[reports]
```

**Adiciona:** pandas, openpyxl

### Com Templates de Email

Para notificações por email com templates:

```bash
pip install autotarefas[email]
```

**Adiciona:** jinja2

### Instalação Completa

Todas as funcionalidades opcionais:

```bash
pip install autotarefas[all]
```

---

## Primeira Configuração

Após instalar, inicialize o AutoTarefas:

```bash
autotarefas init
```

Isso irá:

1. Criar o diretório de configuração (`~/.autotarefas/`)
2. Gerar arquivo de configuração padrão (`config.toml`)
3. Criar diretórios para backups, logs e relatórios

### Estrutura Criada

```
~/.autotarefas/
├── config.toml      # Configurações
├── backups/         # Backups criados
├── logs/            # Arquivos de log
└── reports/         # Relatórios gerados
```

---

## Verificar Funcionamento

Execute um teste rápido:

```bash
# Ver status do sistema
autotarefas monitor quick

# Deve mostrar algo como:
# CPU: 15% | Mem: 42% | Disco: 65%
```

```bash
# Ver ajuda completa
autotarefas --help
```

---

## Instalação em Ambiente Virtual (Opcional)

Para isolar o AutoTarefas em um ambiente virtual:

```bash
# Criar ambiente virtual
python -m venv .venv

# Ativar (Linux/macOS)
source .venv/bin/activate

# Ativar (Windows)
.venv\Scripts\activate

# Instalar
pip install autotarefas[all]
```

---

## Atualização

Para atualizar para a versão mais recente:

```bash
pip install --upgrade autotarefas
```

---

## Desinstalação

Para remover o AutoTarefas:

```bash
pip uninstall autotarefas
```

> **Nota:** Isso não remove os arquivos de configuração em `~/.autotarefas/`. Remova manualmente se desejar.

---

## Solução de Problemas

### Comando não encontrado

Se `autotarefas` não for reconhecido após instalação:

```bash
# Verificar se está no PATH
python -m autotarefas --version

# Ou reinstalar com --user
pip install --user autotarefas
```

### Erro de permissão

No Linux/macOS, se houver erro de permissão:

```bash
pip install --user autotarefas
```

### Python não encontrado

Certifique-se de ter Python 3.12+:

```bash
# Ubuntu/Debian
sudo apt install python3.12

# macOS (com Homebrew)
brew install python@3.12

# Windows
# Baixe em python.org
```

---

## Próximos Passos

- [Uso Básico](uso_basico.md) - Aprenda os comandos essenciais
- [Guia de Backup](backup.md) - Configurar backups automáticos
- [Guia de Limpeza](limpeza.md) - Limpar arquivos temporários

---

*AutoTarefas - Sistema de Automação de Tarefas*
