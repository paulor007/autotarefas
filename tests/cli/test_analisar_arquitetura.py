"""
Teste de ARQUITETURA do comando ``analisar``.

Duas garantias, ambas verificadas na AST (nao por leitura visual):

1. NENHUM TERMO DE DOMINIO no comando nem no gerador de relatorio.
   Nada de "Codigo Venda", "SKU", "estoque", "faturamento".

2. A SAIDA E CONSTRUIDA DINAMICAMENTE a partir dos contratos.
   O comando le `ProfileResult.columns` e `ProfileResult.findings` — ele
   nunca escreve o nome de uma coluna no codigo. Uma planilha com colunas
   que o AutoTarefas nunca viu funciona igual.

E por isso que a planilha usada no teste manual e um EXEMPLO, e nao um
MODELO: se ela tivesse virado modelo, estes testes falhariam.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent.parent / "src" / "autotarefas"
ALVOS = [
    RAIZ / "cli" / "commands" / "analisar.py",
    RAIZ / "profiling" / "report.py",
]

TERMOS_DE_DOMINIO = frozenset(
    {
        "cpf",
        "cnpj",
        "sku",
        "cep",
        "venda",
        "vendas",
        "estoque",
        "faturamento",
        "cliente",
        "clientes",
        "pedido",
        "pedidos",
        "produto",
        "produtos",
        "preco",
        "loja",
        "lojas",
        "funcionario",
        "departamento",
        "salario",
    }
)


def _tokens(nome: str) -> set[str]:
    palavras: list[str] = []
    for parte in re.split(r"[_\W]+", nome):
        palavras.extend(re.findall(r"[a-z]+|[A-Z][a-z]*|[A-Z]+(?![a-z])", parte))
    return {p.lower() for p in palavras if p}


def _docstring_ids(tree: ast.Module) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.body:
            continue
        primeiro = node.body[0]
        if (
            isinstance(primeiro, ast.Expr)
            and isinstance(primeiro.value, ast.Constant)
            and isinstance(primeiro.value.value, str)
        ):
            ids.add(id(primeiro.value))
    return ids


@pytest.mark.parametrize("arquivo", ALVOS, ids=lambda p: p.name)
def test_sem_termo_de_dominio_no_codigo(arquivo: Path) -> None:
    """Nenhuma coluna, dominio ou metrica de negocio cravada no codigo."""
    tree = ast.parse(arquivo.read_text(encoding="utf-8"))
    docstrings = _docstring_ids(tree)
    achados: list[str] = []

    for node in ast.walk(tree):
        textos: list[str] = []
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            textos.append(node.value)
        elif isinstance(node, ast.Name):
            textos.append(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            textos.append(node.name)
        elif isinstance(node, ast.arg):
            textos.append(node.arg)

        for texto in textos:
            for termo in TERMOS_DE_DOMINIO & _tokens(texto):
                achados.append(f"{termo!r} em {texto!r}")

    assert not achados, (
        f"{arquivo.name} conhece dominio — a planilha de teste virou modelo:\n  "
        + "\n  ".join(achados)
    )


def test_relatorio_percorre_as_colunas_do_contrato() -> None:
    """
    O gerador itera sobre `perfil.columns` — ele nao lista colunas na mao.

    Se alguem trocar o loop por uma lista fixa, este teste quebra.
    """
    fonte = (RAIZ / "profiling" / "report.py").read_text(encoding="utf-8")
    assert "perfil.columns" in fonte
    assert "perfil.findings" in fonte
    assert "col.name" in fonte  # o nome vem da COLUNA, nao do codigo


def test_comando_nao_reimplementa_leitor_nem_perfilagem() -> None:
    """
    O comando ORQUESTRA: chama read_workbook e profile_workbook.

    Ele nao pode abrir planilha nem recalcular metrica — isso duplicaria a
    logica e criaria duas versoes da verdade.
    """
    fonte = (RAIZ / "cli" / "commands" / "analisar.py").read_text(encoding="utf-8")
    tree = ast.parse(fonte)

    chamadas = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "read_workbook" in chamadas
    assert "profile_workbook" in chamadas

    proibidas = {"load_workbook", "read_excel", "read_csv", "DataFrame"}
    assert not (chamadas & proibidas), (
        f"o comando abre planilha por conta propria: {chamadas & proibidas}"
    )
