# Servidor Demo do AutoTarefas

Mini sistema web Flask usado como **alvo controlado** das automações
RPA durante desenvolvimento.

⚠️ **Não é parte do pacote `autotarefas`**. É apenas uma ferramenta de
desenvolvimento. Não usar em produção.

## 🎯 Propósito

Quando você está construindo automações RPA, **não pode testar contra
sistemas reais**. Por isso criamos um sistema fake que:

- ✅ Roda 100% local (porta 5555)
- ✅ Tem formulário de cadastro realista
- ✅ Faz validações (CPF, email, telefone)
- ✅ Persiste em JSON local
- ✅ Pode ser reiniciado a qualquer momento

## 📦 Instalação

Instala a extra `demo` do projeto:

```bash
pip install -e ".[demo]"
```

Isso adiciona **Flask** como dependência opcional.

## 🚀 Como rodar

```bash
python -m tools.demo_server
```

Saída esperada:

```
 * Serving Flask app 'tools.demo_server.app'
 * Debug mode: off
 * Running on http://127.0.0.1:5555
```

Acesse: **http://localhost:5555**

## 📋 Endpoints

| Método | URL             | Descrição          |
| ------ | --------------- | ------------------ |
| GET    | `/`             | Landing page       |
| GET    | `/cadastro`     | Formulário HTML    |
| POST   | `/cadastro`     | Cria registro      |
| GET    | `/sucesso/<id>` | Página de sucesso  |
| GET    | `/cadastros`    | Lista todos (JSON) |
| POST   | `/limpar`       | Apaga tudo         |
| GET    | `/health`       | Health check       |

## 🧪 Testes rápidos via curl

```bash
# Health check
curl http://localhost:5555/health

# Listar cadastros
curl http://localhost:5555/cadastros

# Limpar tudo
curl -X POST http://localhost:5555/limpar
```

## 🗂️ Estrutura

```
tools/demo_server/
├── __init__.py
├── __main__.py            # python -m tools.demo_server
├── app.py                 # Flask app
├── storage.py             # JSON storage com lock
├── templates/             # HTML
│   ├── base.html
│   ├── index.html
│   ├── cadastro.html
│   └── sucesso.html
├── static/
│   └── style.css
└── data/                  # Criado em runtime
    └── cadastros.json
```

## 🛡️ Validações implementadas

- **Nome**: obrigatório, ≥3 chars
- **Email**: obrigatório, formato básico (`x@y.z`)
- **CPF**: obrigatório, formato `XXX.XXX.XXX-XX`
- **Telefone**: opcional, formato `(XX) XXXXX-XXXX`

CPF duplicado é rejeitado.

## 🎓 Por que isso é importante para RPA?

Princípio: **automação só roda contra ambiente identificado como demo**.

Em sistemas reais:

- Erros causam impacto financeiro
- Cadastros incorretos contaminam dados de produção
- Bugs do RPA podem disparar processos legais (notificações automáticas)

Em sistemas demo:

- Tudo é fake, zero risco
- Pode quebrar e reiniciar à vontade
- Foco em desenvolver a lógica, não em "não derrubar nada"

Quando você sentir que a automação está pronta, **só então** considere
testar contra um ambiente real (com aprovações apropriadas).

## 🛑 Parar o servidor

`Ctrl+C` no terminal onde rodou.

Dados ficam salvos em `data/cadastros.json` — sobrevivem ao restart.
