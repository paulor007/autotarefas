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
    """Apaga todos os cadastros. So usar em testes."""
    storage.clear()
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

    # Sanitiza
    page = max(page, 1)
    if per_page < 1:
        per_page = 10
    per_page = min(per_page, 100)

    all_records = storage.list_all()
    total = len(all_records)
    total_pages = (total + per_page - 1) // per_page  # ceil

    start = (page - 1) * per_page
    end = start + per_page
    page_data = all_records[start:end]

    return jsonify(
        {
            "data": page_data,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
        }
    )


@app.route("/api/clientes", methods=["POST"])
def api_clientes_create() -> tuple[Response, int]:
    """
    Cria um cliente via API (JSON).

    Body esperado:
        {"nome": ..., "email": ..., "cpf": ..., "telefone": ...}

    Respostas:
        201: criado          -> {"status": "ok", "data": {...}}
        400: JSON ausente/invalido
        422: validacao de campos falhou
        409: CPF ja cadastrado

    Reaproveita _validate_cadastro() e storage.find_by_cpf().
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

    errors = _validate_cadastro(data)
    if errors:
        return jsonify({"error": "Validacao falhou", "detalhes": errors}), 422

    if storage.find_by_cpf(data["cpf"]) is not None:
        return jsonify({"error": "CPF ja cadastrado", "cpf": data["cpf"]}), 409

    record = storage.create(data)
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
# CLI
# ============================================================


def main() -> None:
    """Roda o servidor demo."""
    app.run(host="127.0.0.1", port=5555, debug=False)


if __name__ == "__main__":
    main()
