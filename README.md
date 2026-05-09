# AutoTarefas

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/code%20style-ruff-000000.svg" alt="Code style: ruff">
  <img src="https://img.shields.io/badge/status-em%20desenvolvimento-orange.svg" alt="Status">
  <img src="https://img.shields.io/badge/version-0.0.0-blue.svg" alt="Version">
</p>

<p align="center">
  <b>Robô de Automação Operacional em Python</b>
</p>

<p align="center">
  Reduz tarefas manuais repetitivas em empresas e profissionais autônomos:<br>
  validação de planilhas, organização de arquivos, backups,<br>
  cadastro automático em sistemas web, extração de dados e sincronização.
</p>

---

## Sobre o projeto

O **AutoTarefas** é uma ferramenta CLI desenvolvida em Python para automatizar rotinas operacionais que consomem tempo e geram erros quando feitas manualmente:

- **Validação de planilhas Excel/CSV** antes de processar — evita cadastrar dados ruins
- **Organização automática de arquivos** por tipo, data ou regra customizada
- **Backup compactado** com retenção e verificação de integridade
- **Robô de cadastro web (RPA)** — lê planilha e cadastra em sistemas via Playwright
- **Extração de dados** — coleta informações de sistemas (via API ou navegador) para Excel
- **Comparação e sincronização** entre planilha e sistema, com confirmação humana

> **Exemplo prático:** uma empresa precisa migrar 300 produtos de uma planilha Excel para o sistema interno. Sem o AutoTarefas, isso levaria 2 dias de digitação manual. Com ele, executa em ~15 minutos com relatório completo de sucessos e erros.

---

## Status

**Em desenvolvimento ativo** — versão 0.0.0 (pré-release).

Acompanhe as releases:

- [Roadmap completo](docs/ROADMAP.md) _(em breve)_
- [Releases](https://github.com/paulor007/autotarefas/releases)
- [Changelog](CHANGELOG.md)

---

## Stack

| Camada        | Tecnologia                  |
| ------------- | --------------------------- |
| **Linguagem** | Python 3.12+                |
| **CLI**       | Click + Rich                |
| **Validação** | Pydantic v2                 |
| **Dados**     | pandas + openpyxl           |
| **RPA**       | Playwright                  |
| **HTTP**      | httpx                       |
| **Configs**   | PyYAML                      |
| **Logs**      | Loguru                      |
| **Testes**    | pytest + pytest-cov         |
| **Qualidade** | Ruff + Mypy strict + Bandit |

---

## Instalação

> Em desenvolvimento — ainda não publicado no PyPI.

Para desenvolvedores que querem contribuir ou testar:

```bash
# Clone
git clone https://github.com/paulor007/autotarefas.git
cd autotarefas

# Ambiente virtual
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows
source venv/bin/activate       # Linux/macOS

# Instala em modo editable + dependências de dev
pip install -e ".[dev]"

# Verifica
autotarefas --version
```

---

## Visão da CLI (em construção)

```bash
# Validar planilha antes de processar
autotarefas validate run produtos.xlsx -c codigo,nome,preco

# Organizar arquivos
autotarefas organize run ~/Downloads --profile by_type

# Backup
autotarefas backup run ~/dados -d ~/backups --keep 10

# Robô de cadastro web
autotarefas rpa cadastrar --arquivo produtos.xlsx --config sistema.yml
```

---

## Contribuindo

Este projeto está em fase inicial — feedback é muito bem-vindo:

- [Issues](https://github.com/paulor007/autotarefas/issues) para bugs e sugestões
- [Discussões](https://github.com/paulor007/autotarefas/discussions) para perguntas

---

## Licença

[MIT](LICENSE) — Paulo Lavarini, 2026.

---

## Autor

**Paulo Lavarini**

- Portfolio: [paulolavarini-portfolio.netlify.app](https://paulolavarini-portfolio.netlify.app/)
- LinkedIn: [paulo-lavarini](https://www.linkedin.com/in/paulo-lavarini-20abaa38)
- Email: paulo.lavarini@gmail.com
- GitHub: [@paulor007](https://github.com/paulor007)

---

<p align="center">
  <sub>⭐ Se este projeto te ajudou, deixa uma estrela!</sub>
</p>
