"""
Teste de ARQUITETURA: o leitor nao conhece dominio.

A regra do produto: o pacote ``reader`` le planilhas — ele nao sabe o que
e CPF, SKU, venda ou estoque. Quem da significado aos dados sao os perfis
e os schemas, uma camada acima.

Este teste falha o build se um termo de dominio aparecer no CODIGO do
leitor (identificadores, literais, nomes de funcao). As DOCSTRINGS sao
ignoradas de proposito: elas explicam justamente essa fronteira, e nao
mudam comportamento nenhum. Por isso a checagem usa a AST, e nao um grep
cru — que acusaria as proprias explicacoes.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

READER_DIR = Path(__file__).parent.parent.parent / "src" / "autotarefas" / "reader"

#: Termos que pertencem ao DOMINIO — nunca ao leitor.
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
        "nota",
        "fiscal",
    }
)


def _docstring_ids(tree: ast.Module) -> set[int]:
    """Ids dos nos Constant que sao docstrings (para ignora-los)."""
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


def _tokens(nome: str) -> set[str]:
    """Quebra um identificador em palavras (snake_case e camelCase)."""
    palavras: list[str] = []
    for parte in re.split(r"[_\W]+", nome):
        palavras.extend(re.findall(r"[a-z]+|[A-Z][a-z]*|[A-Z]+(?![a-z])", parte))
    return {p.lower() for p in palavras if p}


def _termos_no_codigo(caminho: Path) -> list[str]:
    """Termos de dominio encontrados no CODIGO (docstrings excluidas)."""
    tree = ast.parse(caminho.read_text(encoding="utf-8"))
    docstrings = _docstring_ids(tree)
    achados: list[str] = []

    def _checar(texto: str, onde: str) -> None:
        # comparacao por TOKEN, nunca por substring: senao 'cep' casaria
        # dentro de "InvalidFileException" e 'venda' dentro de "vendaval".
        for termo in TERMOS_DE_DOMINIO & _tokens(texto):
            achados.append(f"{termo!r} em {onde}: {texto!r}")

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            _checar(node.value, "literal")
        elif isinstance(node, ast.Name):
            _checar(node.id, "nome")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _checar(node.name, "definicao")
        elif isinstance(node, ast.arg):
            _checar(node.arg, "parametro")
        elif isinstance(node, ast.Attribute):
            _checar(node.attr, "atributo")

    return achados


def test_o_pacote_reader_existe() -> None:
    assert READER_DIR.is_dir()
    assert list(READER_DIR.glob("*.py"))


@pytest.mark.parametrize(
    "arquivo",
    sorted(READER_DIR.glob("*.py")),
    ids=lambda p: p.name,
)
def test_leitor_nao_conhece_dominio(arquivo: Path) -> None:
    """O CODIGO do leitor nao pode citar CPF, SKU, venda, estoque..."""
    achados = _termos_no_codigo(arquivo)
    assert not achados, (
        f"{arquivo.name} conhece dominio (isso pertence aos perfis/schemas):\n  "
        + "\n  ".join(achados)
    )


def test_leitor_nao_importa_nada_do_dominio() -> None:
    """O leitor tambem nao pode depender das tasks (validators, schemas...)."""
    for arquivo in READER_DIR.glob("*.py"):
        tree = ast.parse(arquivo.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("autotarefas.tasks"), (
                    f"{arquivo.name} importa de autotarefas.tasks — o leitor deve ser "
                    "independente do motor de validacao"
                )
