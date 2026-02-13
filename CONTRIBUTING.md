# Contribuindo para o AutoTarefas

Obrigado por considerar contribuir para o **AutoTarefas**!
Este guia explica como configurar seu ambiente, seguir os padrões e enviar suas contribuições de forma organizada.

---

## Como contribuir

1. Faça um **fork** do projeto
2. Crie uma branch para sua feature
   ```bash
   git checkout -b feature/AmazingFeature
3. Commit suas mudanças
    git commit -m "feat: adicionar uma feature incrível"
4. Envie para o repositório remoto
    git push origin feature/AmazingFeature
5. Abra um Pull Request para revisão

## Padrões de código
    Usamos Black para formatação (line-length = 88)

    isort para organizar imports

    flake8 para linting

    mypy para verificação de tipos

    Docstrings seguem o formato Google ou NumPy

    Nomes de funções e variáveis devem ser descritivos e em inglês

## Padrões de commit
    Adotamos o padrão Conventional Commits:

    Tipo	Descrição
    feat:	Nova funcionalidade
    fix:	Correção de bug
    docs:	Alterações na documentação
    style:	Formatação, espaços, ponto e vírgula, etc
    refactor:	Refatoração de código
    test:	Adição ou ajuste de testes
    chore:	Tarefas de manutenção e configuração

## Exemplo:

git commit -m "feat: adiciona módulo de backup automático"

## Testes
Todo novo código deve ter testes unitários
Execute antes de enviar:
pytest

Mantenha a cobertura acima de 80%
Gere relatório HTML de cobertura:
pytest --cov=src/autotarefas --cov-report=html

## Qualidade e estilo
Antes de criar um PR, garanta que o código siga os padrões:

black src/
isort src/
flake8 src/
mypy src/
pre-commit run --all-files

## Reportando Bugs
Use o template de issue bug_report.md disponível no GitHub.

Inclua detalhes sobre:

Passos para reproduzir o problema

Versão do Python e do AutoTarefas

Logs relevantes

## Sugestões de Melhorias
Utilize o template feature_request.md

Descreva o problema, a solução desejada e possíveis alternativas

Código de Conduta
Seja respeitoso e colaborativo.
Tratamos todos com respeito, empatia e inclusão.

## Autor:
Paulo Lavarini
    paulo.lavarini@gmail.com
    github.com/paulor007

---

### Dicas finais
- Coloque esse arquivo na **raiz do projeto**, ao lado do `README.md`.
- O GitHub o detecta automaticamente e mostra um **botão “View contributing guidelines”** quando alguém cria um *Pull Request*.
- Depois de criar, finalize com:
  ```bash
  git add CONTRIBUTING.md
  git commit -m "docs: adiciona guia de contribuição (CONTRIBUTING.md)"
  git push origin develop
