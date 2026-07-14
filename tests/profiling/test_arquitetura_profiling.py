"""
Teste de ARQUITETURA: a perfilagem nao conhece dominio.

Mesma protecao do leitor (`tests/reader/test_arquitetura.py`), aplicada ao
pacote ``profiling``. A perfilagem OBSERVA a planilha — ela nao sabe o que
e CPF, SKU ou venda. Quem da significado aos dados sao os perfis e os
schemas, uma camada acima.

A checagem usa a AST, nao um grep cru: as DOCSTRINGS sao ignoradas de
proposito (elas EXPLICAM a fronteira), e a comparacao e por TOKEN — senao
'cep' casaria dentro de "InvalidFileException".
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

PROFILING_DIR = Path(__file__).parent.parent.parent / "src" / "autotarefas" / "profiling"

#: Termos que pertencem ao DOMINIO — nunca a perfilagem.
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


def _tokens(nome: str) -> set[str]:
    """Quebra um identificador em palavras (snake_case e camelCase)."""
    palavras: list[str] = []
    for parte in re.split(r"[_\W]+", nome):
        palavras.extend(re.findall(r"[a-z]+|[A-Z][a-z]*|[A-Z]+(?![a-z])", parte))
    return {p.lower() for p in palavras if p}


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


def _termos_no_codigo(caminho: Path) -> list[str]:
    """Termos de dominio encontrados no CODIGO (docstrings excluidas)."""
    tree = ast.parse(caminho.read_text(encoding="utf-8"))
    docstrings = _docstring_ids(tree)
    achados: list[str] = []

    def _checar(texto: str, onde: str) -> None:
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


def test_o_pacote_profiling_existe() -> None:
    assert PROFILING_DIR.is_dir()
    assert list(PROFILING_DIR.glob("*.py"))


@pytest.mark.parametrize(
    "arquivo",
    sorted(PROFILING_DIR.glob("*.py")),
    ids=lambda p: p.name,
)
def test_perfilagem_nao_conhece_dominio(arquivo: Path) -> None:
    """O CODIGO da perfilagem nao pode citar CPF, SKU, venda, estoque..."""
    achados = _termos_no_codigo(arquivo)
    assert not achados, (
        f"{arquivo.name} conhece dominio (isso pertence aos perfis/schemas):\n  "
        + "\n  ".join(achados)
    )


def test_perfilagem_nao_importa_o_motor_de_validacao() -> None:
    """A perfilagem depende do LEITOR — nunca das tasks de dominio."""
    for arquivo in PROFILING_DIR.glob("*.py"):
        tree = ast.parse(arquivo.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("autotarefas.tasks"), (
                    f"{arquivo.name} importa de autotarefas.tasks — a perfilagem deve ser "
                    "independente do motor de validacao"
                )


def test_perfilagem_nao_abre_arquivo() -> None:
    """
    Ela consome o WorkbookReadResult. Abrir arquivo aqui seria duplicar o
    leitor — e criar duas versoes da verdade.
    """
    proibidos = {"open", "load_workbook", "read_excel", "read_csv", "read_workbook"}
    for arquivo in PROFILING_DIR.glob("*.py"):
        tree = ast.parse(arquivo.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                alvo = node.func
                nome = (
                    alvo.id
                    if isinstance(alvo, ast.Name)
                    else (alvo.attr if isinstance(alvo, ast.Attribute) else "")
                )
                assert nome not in proibidos, (
                    f"{arquivo.name} chama '{nome}()' — a perfilagem NAO abre arquivo, "
                    "ela recebe o WorkbookReadResult pronto"
                )
