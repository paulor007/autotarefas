"""
Mini-linguagem aritmetica segura para regras entre colunas.

O usuario escreve uma conta em texto, referenciando colunas entre colchetes:

    [Total] deve ser        ->  expression: "[Base] * [Fator]"
    saldo final             ->  expression: "[Inicial] + [Entradas] - [Saidas]"
    com parenteses          ->  expression: "([Bruto] - [Abatimento]) * [Taxa]"
    com literal             ->  expression: "[Base] * 1.1"

POR QUE COLCHETES: nomes reais de planilha tem espaco e acento ("Valor
Unitario", "Data de Admissao"). Eles nao sao identificadores validos em
nenhuma linguagem — os colchetes delimitam o nome e o problema desaparece.

POR QUE E SEGURO: a gramatica NAO TEM producao para chamada de funcao,
acesso a atributo, importacao ou nome livre. Nao existe `eval`, `exec`,
`compile` nem `getattr`. Um texto como "__import__('os').system('rm')"
nao "e bloqueado por uma lista negra" — ele simplesmente **nao e
analisavel** por esta gramatica, e falha na carga do schema:

    expr    := termo (('+' | '-') termo)*
    termo   := fator (('*' | '/') fator)*
    fator   := ('-' | '+')? primario
    primario:= NUMERO | '[' NOME ']' | '(' expr ')'

POR QUE Decimal: `1.1 * 3` em float da 3.3000000000000003, e a conta de
uma planilha passaria a divergir de si mesma. Com Decimal(str(valor)),
`1.1 * 3 == 3.3` e exato — o que permite exigir igualdade EXATA por
padrao e deixar a tolerancia como uma decisao consciente do usuario.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping

#: Limites contra expressao patologica (aninhamento fundo estoura a pilha).
MAX_EXPRESSION_LENGTH = 500
MAX_DEPTH = 25


class ExpressionError(ValueError):
    """Expressao mal formada: erro de CONFIGURACAO, detectado na carga."""


class EvaluationError(ValueError):
    """A conta nao pode ser feita NESTA linha (valor faltando, divisao por zero)."""


# --------------------------------------------------------------------------
# Arvore (imutavel). Construida UMA vez por regra, nunca por linha.
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Num:
    """Um literal numerico."""

    value: Decimal


@dataclass(frozen=True, slots=True)
class Col:
    """Referencia a uma coluna, pelo nome exato entre colchetes."""

    name: str


@dataclass(frozen=True, slots=True)
class BinOp:
    """Uma das quatro operacoes. `op` e fechado pelo tipo — nao ha outras."""

    op: Literal["+", "-", "*", "/"]
    left: Node
    right: Node


@dataclass(frozen=True, slots=True)
class Neg:
    """Sinal negativo (ex.: `-[Abatimento]`, `-5`)."""

    operand: Node


Node = Num | Col | BinOp | Neg


# --------------------------------------------------------------------------
# Tokenizador
# --------------------------------------------------------------------------

_TOKEN = re.compile(
    r"""
      (?P<space>\s+)
    | (?P<col>\[[^\]]*\])
    | (?P<num>\d+(?:\.\d+)?)
    | (?P<op>[+\-*/])
    | (?P<lpar>\()
    | (?P<rpar>\))
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    pos: int


def _tokenize(text: str) -> list[_Token]:
    """
    Quebra o texto em tokens. Qualquer caractere fora da gramatica e recusado.

    E aqui que "letras soltas" morrem: nao existe token de identificador,
    entao `os`, `import`, `__class__` e qualquer nome de funcao param no
    primeiro caractere invalido.
    """
    if len(text) > MAX_EXPRESSION_LENGTH:
        msg = f"expressao longa demais ({len(text)} caracteres, maximo {MAX_EXPRESSION_LENGTH})"
        raise ExpressionError(msg)

    tokens: list[_Token] = []
    pos = 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if match is None:
            msg = (
                f"caractere invalido na posicao {pos}: {text[pos]!r}. "
                "Use apenas numeros, + - * / ( ) e nomes de coluna entre colchetes, "
                "como [Nome da Coluna]."
            )
            raise ExpressionError(msg)

        kind = match.lastgroup or ""
        if kind != "space":
            tokens.append(_Token(kind, match.group(), pos))
        pos = match.end()

    if not tokens:
        msg = "expressao vazia"
        raise ExpressionError(msg)
    return tokens


# --------------------------------------------------------------------------
# Parser (descida recursiva)
# --------------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._i = 0

    def parse(self) -> Node:
        node = self._expr(depth=0)
        if self._i < len(self._tokens):
            sobra = self._tokens[self._i]
            msg = f"sobrou {sobra.text!r} na posicao {sobra.pos} — verifique os operadores"
            raise ExpressionError(msg)
        return node

    def _peek(self) -> _Token | None:
        return self._tokens[self._i] if self._i < len(self._tokens) else None

    def _expr(self, depth: int) -> Node:
        self._guard(depth)
        node = self._term(depth + 1)
        while (tok := self._peek()) is not None and tok.kind == "op" and tok.text in "+-":
            self._i += 1
            node = BinOp(tok.text, node, self._term(depth + 1))  # type: ignore[arg-type]
        return node

    def _term(self, depth: int) -> Node:
        self._guard(depth)
        node = self._factor(depth + 1)
        while (tok := self._peek()) is not None and tok.kind == "op" and tok.text in "*/":
            self._i += 1
            node = BinOp(tok.text, node, self._factor(depth + 1))  # type: ignore[arg-type]
        return node

    def _factor(self, depth: int) -> Node:
        self._guard(depth)
        tok = self._peek()
        if tok is not None and tok.kind == "op" and tok.text in "+-":
            self._i += 1
            inner = self._factor(depth + 1)
            return Neg(inner) if tok.text == "-" else inner
        return self._primary(depth + 1)

    def _primary(self, depth: int) -> Node:
        self._guard(depth)
        tok = self._peek()
        if tok is None:
            msg = "a expressao termina de forma incompleta"
            raise ExpressionError(msg)

        if tok.kind == "num":
            self._i += 1
            try:
                return Num(Decimal(tok.text))
            except InvalidOperation as exc:  # pragma: no cover - regex ja garante
                msg = f"numero invalido: {tok.text!r}"
                raise ExpressionError(msg) from exc

        if tok.kind == "col":
            self._i += 1
            nome = tok.text[1:-1].strip()
            if not nome:
                msg = f"referencia de coluna vazia na posicao {tok.pos}: use [Nome da Coluna]"
                raise ExpressionError(msg)
            return Col(nome)

        if tok.kind == "lpar":
            self._i += 1
            node = self._expr(depth + 1)
            fecha = self._peek()
            if fecha is None or fecha.kind != "rpar":
                msg = f"parentese aberto na posicao {tok.pos} nunca foi fechado"
                raise ExpressionError(msg)
            self._i += 1
            return node

        msg = f"nao esperava {tok.text!r} na posicao {tok.pos}"
        raise ExpressionError(msg)

    @staticmethod
    def _guard(depth: int) -> None:
        if depth > MAX_DEPTH:
            msg = f"expressao aninhada demais (maximo {MAX_DEPTH} niveis)"
            raise ExpressionError(msg)


def parse_expression(text: str) -> Node:
    """
    Converte o texto numa arvore imutavel. Chamada UMA vez por regra.

    Raises:
        ExpressionError: texto mal formado — erro de configuracao.
    """
    return _Parser(_tokenize(text)).parse()


# --------------------------------------------------------------------------
# Avaliacao
# --------------------------------------------------------------------------


def columns_used(node: Node) -> set[str]:
    """Nomes de coluna que a expressao referencia (para validar a configuracao)."""
    if isinstance(node, Col):
        return {node.name}
    if isinstance(node, BinOp):
        return columns_used(node.left) | columns_used(node.right)
    if isinstance(node, Neg):
        return columns_used(node.operand)
    return set()


def evaluate(node: Node, values: Mapping[str, Decimal | None]) -> Decimal:
    """
    Calcula a expressao para UMA linha.

    Args:
        node: arvore ja construida.
        values: valor numerico de cada coluna nesta linha. `None` = a celula
            nao tem um numero utilizavel (vazia, texto, erro da planilha).

    Raises:
        EvaluationError: a conta nao pode ser feita nesta linha. Quem chama
            transforma isso num aviso de "nao pode ser verificada" — nunca
            numa exececao que derruba a validacao inteira.
    """
    if isinstance(node, Num):
        return node.value

    if isinstance(node, Col):
        valor = values.get(node.name)
        if valor is None:
            msg = f"a coluna '{node.name}' nao tem um numero utilizavel nesta linha"
            raise EvaluationError(msg)
        return valor

    if isinstance(node, Neg):
        return -evaluate(node.operand, values)

    return _apply(node.op, evaluate(node.left, values), evaluate(node.right, values))


def _apply(op: str, esquerda: Decimal, direita: Decimal) -> Decimal:
    """As quatro operacoes. `op` ja veio fechado pelo tipo do no."""
    if op == "+":
        return esquerda + direita
    if op == "-":
        return esquerda - direita
    if op == "*":
        return esquerda * direita
    if direita == 0:
        msg = "divisao por zero"
        raise EvaluationError(msg)
    return esquerda / direita


def format_decimal(valor: Decimal) -> str:
    """Decimal legivel na mensagem (sem notacao cientifica, sem zeros sobrando)."""
    texto = f"{valor:f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto or "0"


__all__ = [
    "MAX_DEPTH",
    "MAX_EXPRESSION_LENGTH",
    "BinOp",
    "Col",
    "EvaluationError",
    "ExpressionError",
    "Neg",
    "Node",
    "Num",
    "columns_used",
    "evaluate",
    "format_decimal",
    "parse_expression",
]
