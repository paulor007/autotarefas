"""
Servidor demo do AutoTarefas (Flask).

Mini sistema web simulando um cadastro corporativo. Usado como
**alvo** das automações RPA durante desenvolvimento.

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
    GET  /cadastros     -> lista todos (JSON)
    POST /limpar        -> reset (apaga tudo)
    GET  /health        -> health check (JSON)
"""

from __future__ import annotations

import re
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from tools.demo_server.storage import Storage

# ============================================================
# App e storage
# ============================================================

app = Flask(__name__)
storage = Storage()


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
    elif len(nome) < 3:
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


# ============================================================
# CLI
# ============================================================


def main() -> None:
    """Roda o servidor demo."""
    app.run(host="127.0.0.1", port=5555, debug=False)


if __name__ == "__main__":
    main()
