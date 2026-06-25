# AutoTarefas — Live System (backend)

API que executa as automacoes reais do AutoTarefas para a demonstracao ao vivo.
O visitante escolhe uma automacao curada, (quando faz sentido) envia os arquivos
dele por upload, ve o robo rodar de verdade e baixa o resultado. Os servidores de
demonstracao (mocks) rodam no mesmo container; o robo nunca acessa a internet
aberta.

> Servico **separado** do nucleo: importa o pacote `autotarefas`, mas nao altera
> `src/` nem a suite de testes do projeto principal.

## Como rodar local (sem Docker)

A partir da raiz do repositorio, com a venv ativada e o pacote instalado:

```bash
pip install -r live_demo/backend/requirements.txt
uvicorn live_demo.backend.app.main:app --reload --port 7860
```

- `http://localhost:7860/api/health` — saude do servico e dos mocks
- `http://localhost:7860/api/catalog` — catalogo curado das automacoes

Para subir sem iniciar os mocks (util em testes): `DEMO_SERVERS_AUTOSTART=0`.

## Como rodar com Docker (igual ao deploy)

A partir da raiz do repo:

```bash
docker build -f live_demo/backend/Dockerfile -t autotarefas-live .
docker run --rm -p 7860:7860 autotarefas-live
```

A imagem ja inclui o Chromium (para RPA e scraping-JS). A base e multi-arch, entao
roda tanto em **arm64** (Oracle Ampere) quanto em **amd64**.

## Variaveis de ambiente

| Variavel                 | Default              | Para que serve                        |
| ------------------------ | -------------------- | ------------------------------------- |
| `PORT`                   | `7860`               | Porta do servico                      |
| `DEMO_SERVERS_AUTOSTART` | `true`               | Subir os mocks no startup             |
| `MAX_UPLOAD_MB`          | `10`                 | Limite de upload (Live-2)             |
| `MAX_UPLOAD_FILES`       | `50`                 | Limite de arquivos por envio (Live-2) |
| `RUN_TIMEOUT_S`          | `60`                 | Timeout por execucao (Live-3)         |
| `RATE_LIMIT_PER_MIN`     | `12`                 | Execucoes por minuto por IP (Live-3)  |
| `CORS_ORIGINS`           | `localhost:5173,...` | Origens liberadas no dev do front     |

## Endpoints

| Metodo | Rota                           | Status        |
| ------ | ------------------------------ | ------------- |
| GET    | `/api/health`                  | pronto        |
| GET    | `/api/catalog`                 | pronto        |
| POST   | `/api/run/{id}`                | stub (Live-2) |
| GET    | `/api/download/{token}/{name}` | stub (Live-2) |

## Roadmap

- **Live-1** (este esqueleto): catalogo, health, mocks no ciclo de vida, Dockerfile.
- **Live-2**: upload (arquivos/pasta) -> workspace efemero -> execucao real -> download.
- **Live-3**: streaming ao vivo (SSE) + seguranca (allowlist, rate-limit, timeout, sem rede externa).
