"""
Servidor demo do AutoTarefas (Flask).

Mini sistema web simulando um cadastro corporativo. Usado como
**alvo** das automações RPA e de extração/envio durante desenvolvimento.

NÃO usar em produção. Dados são persistidos em JSON local, sem
autenticação. É apenas pra testes locais.

Uso:
    pip install -e ".[demo]"
    python -m tools.demo_server
    # Abre em http://localhost:5555

Endpoints:
    GET  /              -> landing page
    GET  /cadastro      -> formulario HTML
    POST /cadastro      -> cria registro
    GET  /sucesso/<id>  -> pagina de sucesso
    GET  /cadastros     -> lista todos (JSON)
    POST /limpar        -> reset (apaga tudo)
    GET  /health        -> health check (JSON)
    GET  /api/clientes  -> lista paginada (JSON)
    POST /api/clientes  -> cria cliente via JSON
    POST /seed          -> popula com clientes fake
"""

from __future__ import annotations

import re
import time
from typing import Any

from faker import Faker
from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from tools.demo_server.storage import Storage

# ============================================================
# App e storage
# ============================================================

app = Flask(__name__)
storage = Storage()

#: Idempotency-Keys ja processadas -> registro criado (replay sem duplicar).
_IDEMPOTENCY_SEEN: dict[str, dict[str, Any]] = {}
#: Contador de hits do cenario "instavel" (429 na 1a tentativa) por chave.
_RATE_LIMIT_HITS: dict[str, int] = {}


def _build_catalogo_demo() -> list[dict[str, Any]]:
    """
    Dataset FIXO e DETERMINISTICO para a Exportacao automatica de dados.

    Simula o catalogo de produtos de um ERP. E independente do storage
    de cadastros (que o Cadastro automatico reseta) — a Exportacao sempre
    traz exatamente estes registros, tornando a demo previsivel.
    """
    categorias = ["Bebidas", "Limpeza", "Higiene", "Mercearia", "Hortifruti"]
    unidades = ["un", "cx", "kg", "L", "pct"]
    registros: list[dict[str, Any]] = []
    for i in range(1, 48):  # 47 produtos -> pagina de forma "redonda"
        registros.append(
            {
                "id": i,
                "sku": f"PRD-{i:04d}",
                "produto": f"Produto {i:02d}",
                "categoria": categorias[i % len(categorias)],
                "preco": round(5 + (i * 3.7) % 90, 2),
                "estoque": (i * 7) % 200,
                "unidade": unidades[i % len(unidades)],
                "ativo": (i % 9) != 0,
            }
        )
    return registros


#: Catalogo-semente da Exportacao (imutavel; construido uma vez).
_CATALOGO_DEMO: list[dict[str, Any]] = _build_catalogo_demo()

fake = Faker("pt_BR")


# ============================================================
# Validações
# ============================================================


def _validate_cadastro(data: dict[str, Any]) -> list[str]:
    """
    Valida dados de cadastro. Retorna lista de erros (vazia se ok).

    Regras:
    - nome: obrigatorio, >=3 chars
    - email: obrigatorio, formato basico
    - cpf: obrigatorio, formato XXX.XXX.XXX-XX
    - telefone: opcional, formato (XX) XXXXX-XXXX se preenchido
    """
    errors: list[str] = []

    # Nome
    nome = str(data.get("nome", "")).strip()
    if not nome:
        errors.append("Nome e obrigatorio")
    elif len(nome) < 3:  # noqa: PLR2004
        errors.append("Nome deve ter pelo menos 3 caracteres")

    # Email
    email = str(data.get("email", "")).strip().lower()
    if not email:
        errors.append("Email e obrigatorio")
    elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors.append("Email com formato invalido")

    # CPF
    cpf = str(data.get("cpf", "")).strip()
    if not cpf:
        errors.append("CPF e obrigatorio")
    elif not re.match(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", cpf):
        errors.append("CPF deve estar no formato XXX.XXX.XXX-XX")

    # Telefone (opcional)
    telefone = str(data.get("telefone", "")).strip()
    if telefone and not re.match(r"^\(\d{2}\)\s?\d{4,5}-\d{4}$", telefone):
        errors.append("Telefone deve estar no formato (XX) XXXXX-XXXX")

    return errors


# ============================================================
# Rotas
# ============================================================


@app.route("/")
def index() -> str:
    """Landing page."""
    total = len(storage.list_all())
    return render_template("index.html", total=total)


@app.route("/cadastro", methods=["GET"])
def cadastro_get() -> str:
    """Formulario HTML de cadastro."""
    return render_template("cadastro.html", errors=[], data={})


@app.route("/cadastro", methods=["POST"])
def cadastro_post() -> str | Response:
    """
    Recebe POST do formulario.

    Se valido: salva, redireciona pra /sucesso/<id>
    Se invalido: re-renderiza com erros
    """
    data = {
        "nome": request.form.get("nome", "").strip(),
        "email": request.form.get("email", "").strip().lower(),
        "cpf": request.form.get("cpf", "").strip(),
        "telefone": request.form.get("telefone", "").strip(),
    }

    errors = _validate_cadastro(data)

    if errors:
        return render_template("cadastro.html", errors=errors, data=data)

    # CPF duplicado e erro
    if storage.find_by_cpf(data["cpf"]) is not None:
        return render_template(
            "cadastro.html",
            errors=["CPF ja cadastrado"],
            data=data,
        )

    record = storage.create(data)
    return redirect(url_for("sucesso", record_id=record["id"]))


@app.route("/sucesso/<int:record_id>")
def sucesso(record_id: int) -> str | tuple[str, int]:
    """Pagina de sucesso apos cadastro."""
    record = storage.find_by_id(record_id)
    if record is None:
        return "Cadastro nao encontrado", 404
    return render_template("sucesso.html", record=record)


@app.route("/cadastros")
def cadastros_json() -> Response:
    """Lista todos os cadastros (JSON). Util pra verificacoes."""
    return jsonify(storage.list_all())


@app.route("/limpar", methods=["POST"])
def limpar() -> Response:
    """Apaga todos os cadastros e o estado de demo. So usar em testes."""
    storage.clear()
    _IDEMPOTENCY_SEEN.clear()
    _RATE_LIMIT_HITS.clear()
    return jsonify({"status": "ok", "message": "Cadastros removidos"})


@app.route("/health")
def health() -> Response:
    """Health check pra automacao saber se servidor esta online."""
    return jsonify(
        {
            "status": "ok",
            "service": "autotarefas-demo",
            "total_cadastros": len(storage.list_all()),
        }
    )


def _gerar_cliente_fake() -> dict[str, str]:
    """Gera dados fake de um cliente usando Faker (locale pt_BR)."""
    return {
        "nome": fake.name(),
        "email": fake.email(),
        "cpf": fake.cpf(),
        "telefone": fake.cellphone_number(),
    }


def _paginate(records: list[dict[str, Any]], page: int, per_page: int) -> Response:
    """Monta a resposta paginada padrao (data/page/total/has_next)."""
    page = max(page, 1)
    if per_page < 1:
        per_page = 10
    per_page = min(per_page, 100)

    total = len(records)
    total_pages = (total + per_page - 1) // per_page  # ceil
    start = (page - 1) * per_page
    end = start + per_page

    return jsonify(
        {
            "data": records[start:end],
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
        }
    )


@app.route("/api/catalogo")
def api_catalogo() -> Response:
    """
    API paginada do catalogo de produtos (dataset FIXO de demonstracao).

    Endpoint da Exportacao automatica de dados. Independente do storage
    de cadastros — sempre retorna o mesmo catalogo (47 produtos), o que
    torna a demo deterministica. Mesmos query params e formato da rota
    de clientes (page, per_page -> data/total/total_pages/has_next).
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    return _paginate(_CATALOGO_DEMO, page, per_page)


@app.route("/api/clientes")
def api_clientes() -> Response:
    """
    API paginada de clientes (JSON).

    Query params:
        page: numero da pagina (default 1, minimo 1)
        per_page: itens por pagina (default 10, max 100)

    Resposta:
        {
          "data": [...],
          "page": N,
          "per_page": N,
          "total": N,
          "total_pages": N,
          "has_next": bool
        }
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    return _paginate(storage.list_all(), page, per_page)


@app.route("/api/clientes", methods=["POST"])
def api_clientes_create() -> tuple[Response, int]:
    """
    Cria um cliente via API (JSON) — comporta-se como um CRM real.

    Body esperado:
        {"nome": ..., "email": ..., "cpf": ..., "telefone": ...}

    Respostas:
        201: criado                    -> {"status": "ok", "data": {...}}
        200: replay idempotente        -> mesmo registro, sem duplicar
        400: JSON ausente/invalido
        422: validacao de campos falhou
        409: CPF ja cadastrado (com Idempotency-Key diferente)
        429: rate limit (1a tentativa de registros "instaveis"),
             com header Retry-After: 2

    Idempotencia: se o header Idempotency-Key ja foi visto, devolve o
    MESMO registro criado na primeira vez (nao duplica). Cenario de
    demonstracao: nomes contendo "instavel" recebem 429 na primeira
    tentativa e sucesso nas seguintes — para mostrar o retry ao vivo.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON invalido ou ausente"}), 400

    data = {
        "nome": str(payload.get("nome", "")).strip(),
        "email": str(payload.get("email", "")).strip().lower(),
        "cpf": str(payload.get("cpf", "")).strip(),
        "telefone": str(payload.get("telefone", "")).strip(),
    }

    # Replay idempotente: mesma Idempotency-Key -> mesmo resultado,
    # sem criar registro novo (e o que evita duplicidade em reenvios).
    idem_key = request.headers.get("Idempotency-Key")
    if idem_key and idem_key in _IDEMPOTENCY_SEEN:
        record = _IDEMPOTENCY_SEEN[idem_key]
        return jsonify({"status": "ok", "data": record, "idempotente": True}), 200

    errors = _validate_cadastro(data)
    if errors:
        return jsonify({"error": "Validacao falhou", "detalhes": errors}), 422

    # Cenario de demonstracao: registro "instavel" leva 429 (rate limit)
    # na primeira tentativa e passa nas seguintes. Deterministico por
    # Idempotency-Key (ou CPF, se a chave nao vier).
    if "instavel" in data["nome"].lower():
        gatilho = idem_key or data["cpf"]
        hits = _RATE_LIMIT_HITS.get(gatilho, 0) + 1
        _RATE_LIMIT_HITS[gatilho] = hits
        if hits == 1:
            resp = jsonify({"error": "Limite de requisicoes, aguarde"})
            resp.headers["Retry-After"] = "2"
            return resp, 429

    if storage.find_by_cpf(data["cpf"]) is not None:
        return jsonify({"error": "CPF ja cadastrado", "cpf": data["cpf"]}), 409

    record = storage.create(data)
    if idem_key:
        _IDEMPOTENCY_SEEN[idem_key] = record
    return jsonify({"status": "ok", "data": record}), 201


@app.route("/seed", methods=["POST"])
def seed() -> Response:
    """
    Popula o storage com N clientes fake (Faker).

    Query params:
        n: quantidade a criar (default 50, max 1000)
        clear: se "true", limpa tudo antes de popular (default false)

    So usar em desenvolvimento/testes.
    """
    n = request.args.get("n", 50, type=int)
    clear = request.args.get("clear", "false").lower() == "true"

    n = max(n, 1)
    n = min(n, 1000)

    if clear:
        storage.clear()

    fakes = [_gerar_cliente_fake() for _ in range(n)]
    created = storage.create_many(fakes)

    return jsonify(
        {
            "status": "ok",
            "created": created,
            "cleared": clear,
            "total": len(storage.list_all()),
        }
    )


# ============================================================
# Catalogo de produtos (alvo de web scraping)
# ============================================================

_CAT_CATEGORIAS = (
    "Eletronicos",
    "Livros",
    "Casa",
    "Esporte",
    "Moda",
    "Brinquedos",
)
_CAT_ADJ = (
    "Premium",
    "Classico",
    "Moderno",
    "Compacto",
    "Pro",
    "Eco",
    "Ultra",
    "Smart",
)
_CAT_SUBST = (
    "Cadeira",
    "Mesa",
    "Fone",
    "Teclado",
    "Caneca",
    "Mochila",
    "Lampada",
    "Relogio",
)


def _build_catalogo(n: int = 48) -> list[dict[str, object]]:
    """Gera um catalogo fixo de produtos (deterministico, sem random)."""
    itens: list[dict[str, object]] = []
    for i in range(1, n + 1):
        subst = _CAT_SUBST[(i * 3) % len(_CAT_SUBST)]
        adj = _CAT_ADJ[(i * 7) % len(_CAT_ADJ)]
        preco_cents = 990 + (i * 1373) % 98000  # 9.90 .. ~989.90
        itens.append(
            {
                "id": i,
                "nome": f"{subst} {adj} {i:03d}",
                "categoria": _CAT_CATEGORIAS[(i - 1) % len(_CAT_CATEGORIAS)],
                "preco": f"{preco_cents / 100:.2f}",
                "estoque": (i * 37) % 251,
            },
        )
    return itens


_CATALOGO: list[dict[str, object]] = _build_catalogo()


@app.route("/catalogo")
def catalogo() -> str:
    """
    Pagina HTML com um catalogo de produtos paginado.

    Alvo de teste para web scraping (extract web). HTML estatico, com
    estrutura previsivel para seletores CSS.

    Query params:
        page: numero da pagina (default 1, minimo 1)
        per_page: itens por pagina (default 10, max 100)
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    page = max(page, 1)
    if per_page < 1:
        per_page = 10
    per_page = min(per_page, 100)

    total = len(_CATALOGO)
    total_pages = max((total + per_page - 1) // per_page, 1)  # ceil, min 1
    page = min(page, total_pages)

    start = (page - 1) * per_page
    page_itens = _CATALOGO[start : start + per_page]

    return render_template(
        "catalogo.html",
        produtos=page_itens,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


# ============================================================
# Catalogo renderizado por JavaScript (alvo do 'extract web --js')
# ============================================================

#: Produtos FIXOS servidos via JSON e injetados no DOM por JavaScript.
#: Deterministicos de proposito: o teste E2E confere valores exatos.
_CATALOGO_JS: list[dict[str, str]] = [
    {"id": "1", "nome": "Teclado Mecanico ABNT2", "preco": "349.90"},
    {"id": "2", "nome": "Mouse Optico USB", "preco": "79.90"},
    {"id": "3", "nome": "Monitor LED 24 polegadas", "preco": "899.00"},
]


@app.route("/catalogo-js")
def catalogo_js() -> str:
    """
    Catalogo cujo conteudo e injetado via JavaScript (simula AJAX).

    Alvo de teste para 'extract web --js'. O HTML servido vem com a
    tabela VAZIA; um <script> busca /catalogo-js/dados (fetch) e injeta
    as linhas no DOMContentLoaded. Sem executar JavaScript (modo httpx),
    nenhum produto aparece no HTML cru — e e justamente esse contraste
    (0 itens sem --js, N itens com --js) que prova o modo JS.
    """
    return render_template("catalogo_js.html")


@app.route("/catalogo-js/dados")
def catalogo_js_dados() -> Response:
    """Dados (JSON) consumidos via fetch pela pagina /catalogo-js."""
    return jsonify(_CATALOGO_JS)


_telegram_inbox: list[dict[str, Any]] = []


@app.route("/bot<token>/sendMessage", methods=["POST"])
def telegram_send_message(token: str) -> tuple[Response, int]:
    """
    Mock do endpoint sendMessage da Bot API do Telegram.

    Aceita JSON (ou form) com `chat_id` e `text`. Responde no mesmo
    formato da Bot API real.

    Respostas:
        200: {"ok": true, "result": {...}}
        400: {"ok": false, "error_code": 400, "description": ...}
        401: {"ok": false, "error_code": 401, "description": ...}
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = request.form.to_dict()

    chat_id = str(payload.get("chat_id", "")).strip()
    text = str(payload.get("text", "")).strip()

    if not token.strip():
        return jsonify(
            {"ok": False, "error_code": 401, "description": "Unauthorized: token ausente"},
        ), 401
    if not chat_id:
        return jsonify(
            {"ok": False, "error_code": 400, "description": "Bad Request: chat_id ausente"},
        ), 400
    if not text:
        return jsonify(
            {"ok": False, "error_code": 400, "description": "Bad Request: message text is empty"},
        ), 400

    message_id = len(_telegram_inbox) + 1
    date = int(time.time())
    _telegram_inbox.append(
        {
            "message_id": message_id,
            "chat_id": chat_id,
            "text": text,
            "date": date,
            "token_prefix": token[:8],
        },
    )

    return jsonify(
        {
            "ok": True,
            "result": {
                "message_id": message_id,
                "date": date,
                "chat": {"id": chat_id},
                "text": text,
            },
        },
    ), 200


@app.route("/telegram/mensagens")
def telegram_inbox() -> Response:
    """Lista as mensagens recebidas pelo mock (inspeção no teste manual)."""
    return jsonify({"total": len(_telegram_inbox), "mensagens": _telegram_inbox})


@app.route("/telegram/limpar", methods=["POST"])
def telegram_clear() -> Response:
    """Limpa a caixa de mensagens do mock."""
    _telegram_inbox.clear()
    return jsonify({"status": "ok", "message": "Inbox do Telegram limpa"})


# ============================================================
# CLI
# ============================================================


def main() -> None:
    """Roda o servidor demo."""
    app.run(host="127.0.0.1", port=5555, debug=False)


if __name__ == "__main__":
    main()
