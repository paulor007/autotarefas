# AutoTarefas

> Automação modular de processos repetitivos em **Python 3.13+**

[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/paulor007/autotarefas/actions/workflows/tests.yml/badge.svg)](https://github.com/paulor007/autotarefas/actions)

---

## Descrição

**AutoTarefas** é uma ferramenta desenvolvida em **Python 3.13+** para **automatizar rotinas repetitivas de forma segura, modular e configurável**.
Ela foi projetada para oferecer **flexibilidade**, **monitoramento inteligente** e **integração com agendamentos automáticos**.


Principais recursos:
- **Backup automático** de arquivos e pastas
- **Limpeza inteligente** de arquivos temporários e logs
- **Organização de downloads e relatórios**
- **Geração automática de relatórios** (CSV/Excel)
- **Monitoramento de uso de CPU, memória e disco**
- **Agendamento de tarefas recorrentes** com `schedule`

---

## Estrutura do Projeto

autotarefas/
│
├── .github/workflows/ # Integração contínua (CI/CD)
│ └── tests.yml
│
├── docs/ # Documentação
│ ├── installation.md
│ ├── usage.md
│ └── api.md
│
├── src/
│ └── autotarefas/
│ ├── init.py
│ ├── main.py
│ ├── cli.py # Interface de linha de comando (CLI)
│ ├── config.py # Carrega e valida variáveis do .env
│ ├── core/ # Núcleo e agendador de tarefas
│ ├── tasks/ # Módulos de automação (backup, limpeza, etc.)
│ ├── utils/ # Funções auxiliares
│ └── logs/ # Logs do sistema
│
├── tests/ # Testes unitários e de integração (pytest)
│ ├── init.py
│ └── test_sanity.py
│
├── examples/ # Exemplos de uso prático
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── LICENSE
└── CHANGELOG.md

---

## Tecnologias e Conceitos Utilizados

- **Python 3.13+**
- **Arquitetura modular (core/tasks/utils)**
- **CLI com Click**
- **Agendamento com Schedule**
- **Logs com Loguru**
- **Carregamento de variáveis com dotenv**
- **Code style: Black + isort + Flake8**
- **Testes com Pytest e Coverage**
- **Verificação de tipos com MyPy**
- **Pré-validação automática com pre-commit**
- **Documentação automática (Sphinx)**

---

## Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/paulor007/autotarefas.git
cd autotarefas

# 2. Crie e ative um ambiente virtual
python -m venv venv
venv\Scripts\activate      # Windows
# ou
source venv/bin/activate   # Linux / Mac

# 3. Instale as dependências principais
pip install -r requirements.txt

# 4. (Opcional) Instale as dependências de desenvolvimento
pip install -r requirements-dev.txt

---

## Configuração de Ambiente

Copie o arquivo .env.example para .env e personalize conforme suas variáveis de ambiente:
cp .env.example .env

# Principais variáveis:
APP_NAME=AutoTarefas
APP_ENV=development
DEBUG=True
LOG_LEVEL=INFO
SCHEDULE_TIMEZONE=America/Sao_Paulo

---

## Execução

Para executar a aplicação, use um dos comandos abaixo conforme sua necessidade:
python -m autotarefas

---

## Testes e Qualidade

# Executar todos os testes com cobertura:
pytest

# Gerar relatório HTML de cobertura
pytest --cov=src/autotarefas --cov-report=html

# Verificar estilo e formatação de código
black src/
isort src/
flake8 src/
mypy src/

# Rodar hooks locais:
pre-commit install
pre-commit run --all-files

---

## Dependências Extras (opcionais)


Algumas funcionalidades do **AutoTarefas** são opcionais e podem ser instaladas conforme a necessidade do projeto.
Esses extras estão definidos no arquivo `pyproject.toml`.

```bash
# Instalar pacotes adicionais via extras do pyproject.toml:
pip install -e ".[dev,excel,email,watch]"

- **dev: ferramentas de desenvolvimento e lint
- **excel: suporte a relatórios CSV/Excel (pandas, openpyxl)
- **email: envio automático de relatórios (yagmail)
- **watch: monitoramento de diretórios com watchdog

---

## Integração Contínua (CI/CD)

O projeto inclui pipeline no GitHub Actions (.github/workflows/tests.yml) que:

Distribuído sob a licença MIT.
- **Roda testes automatizados com cobertura mínima
- **Gera relatório e badge de status

## Histórico de Alterações

# As versões e mudanças são documentadas em CHANGELOG.md, seguindo o padrão Keep a Changelog, e Semantic Versioning.

---

## Como Contribuir

# 1. Faça um fork do projeto

# 2. Crie uma branch para sua feature:
git checkout -b feature/nova-automacao

# 3. Faça suas alterações e commits:
git commit -m "feat: adiciona automação de limpeza de relatórios"

# 4. Envie para o repositório remoto:
git push origin feature/nova-automacao

# 5. Crie um Pull Request para revisão
- **Dica: mantenha a cobertura de testes acima de 80%

---

## Licença

- **Distribuído sob a licença MIT.
- **Consulte o arquivo LICENSE para mais informações.

---

## Autor

Paulo Lavarini
    - **paulo.lavarini@gmail.com
    - **github.com/paulor007

## Status do Projeto

Em desenvolvimento ativo (v0.1.0-alpha)
- **Estrutura modular concluída, ambiente configurado e testes básicos funcionando.
- **Próximas etapas: Implementação dos módulos core e tasks.



