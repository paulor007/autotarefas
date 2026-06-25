# Backend do Live System do AutoTarefas — imagem unica: API + mocks + Chromium.
# A base python:3.12-slim e multi-arch, entao a MESMA receita roda em arm64
# (Oracle Ampere) e amd64 (Render/Fly). Construa a partir da RAIZ do repo:
#
#   docker build -f live_demo/backend/Dockerfile -t autotarefas-live .
#   docker run --rm -p 7860:7860 autotarefas-live
#
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860 \
    REPO_ROOT=/app \
    WORKSPACES_ROOT=/tmp/autotarefas-live \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Utilitarios de base (curl p/ healthcheck; ca-certificates p/ TLS)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 1) Pacote AutoTarefas (nucleo) — instala so o necessario para resolver deps primeiro
COPY pyproject.toml README.md /app/
COPY src /app/src
RUN pip install .

# 2) Dependencias do backend (FastAPI/uvicorn/multipart + flask/faker dos mocks)
COPY live_demo/backend/requirements.txt /app/live_demo/backend/requirements.txt
RUN pip install -r /app/live_demo/backend/requirements.txt

# 3) Navegador real para RPA / scraping-JS (instala Chromium + libs de SO)
RUN python -m playwright install --with-deps chromium

# 4) Restante do codigo: mocks (tools/) e o proprio backend (live_demo/)
COPY tools /app/tools
COPY live_demo /app/live_demo

# Healthcheck simples batendo no proprio endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

EXPOSE 7860
CMD ["uvicorn", "live_demo.backend.app.main:app", "--host", "0.0.0.0", "--port", "7860"]
