"""
Testes da mini-linguagem aritmetica.

O ponto mais importante aqui e a classe `TestSeguranca`: ela prova que a
gramatica NAO ACEITA execucao de codigo — nao por lista negra, mas porque
nao existe producao gramatical para chamada, atributo ou nome livre.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from autotarefas.tasks.expressions import (
    MAX_DEPTH,
    BinOp,
    Col,
    EvaluationError,
    ExpressionError,
    Num,
    columns_used,
    evaluate,
    format_decimal,
    parse_expression,
)


def calcular(expressao: str, **valores: object) -> Decimal:
    contexto = {k.replace("_", " "): Decimal(str(v)) for k, v in valores.items()}
    return evaluate(parse_expression(expressao), contexto)


# ============================================================
# Aritmetica
# ============================================================


class TestAritmetica:
    @pytest.mark.parametrize(
        ("expressao", "esperado"),
        [
            ("1 + 2", 3),
            ("5 - 3", 2),
            ("4 * 3", 12),
            ("10 / 4", Decimal("2.5")),
            ("2 + 3 * 4", 14),  # precedencia
            ("(2 + 3) * 4", 20),  # parenteses mudam o resultado
            ("-5 + 8", 3),  # literal negativo
            ("2 * -3", -6),
            ("((1 + 2) * (3 + 4)) / 3", 7),  # aninhamento
        ],
    )
    def test_operacoes(self, expressao: str, esperado: object) -> None:
        assert evaluate(parse_expression(expressao), {}) == Decimal(str(esperado))

    def test_multiplicacao_entre_colunas(self) -> None:
        assert calcular("[a] * [b]", a=3, b=150) == 450

    def test_soma_e_subtracao_encadeadas(self) -> None:
        """Saldo: inicial + entradas - saidas."""
        assert calcular("[a] + [b] - [c]", a=100, b=50, c=30) == 120

    def test_agrupamento_com_colunas(self) -> None:
        """(bruto - abatimento) * taxa."""
        assert calcular("([a] - [b]) * [c]", a=200, b=50, c=Decimal("0.1")) == 15

    def test_coluna_com_espaco(self) -> None:
        contexto = {"Valor Unitario": Decimal(10), "Quantidade": Decimal(3)}
        assert evaluate(parse_expression("[Valor Unitario] * [Quantidade]"), contexto) == 30

    def test_coluna_com_acento(self) -> None:
        contexto = {"Valor Unitário": Decimal(10), "Código": Decimal(2)}
        assert evaluate(parse_expression("[Valor Unitário] * [Código]"), contexto) == 20

    def test_coluna_com_pontuacao_no_nome(self) -> None:
        contexto = {"Saldo (R$)": Decimal(5)}
        assert evaluate(parse_expression("[Saldo (R$)] * 2"), contexto) == 10


# ============================================================
# Decimal exato — a razao de tolerancia zero ser viavel
# ============================================================


class TestPrecisaoDecimal:
    def test_multiplicacao_que_quebraria_em_float(self) -> None:
        """1.1 * 3 da 3.3000000000000003 em float. Aqui tem que dar 3.3."""
        assert calcular("[a] * 3", a="1.1") == Decimal("3.3")

    def test_soma_que_quebraria_em_float(self) -> None:
        assert calcular("[a] + [b]", a="0.1", b="0.2") == Decimal("0.3")

    def test_igualdade_exata_e_alcancavel(self) -> None:
        """A base de tolerance=0: a conta de planilha fecha exatamente."""
        assert calcular("[a] * [b]", a="19.90", b=3) == Decimal("59.70")


# ============================================================
# SEGURANCA — a gramatica nao tem como executar nada
# ============================================================


class TestSeguranca:
    @pytest.mark.parametrize(
        "ataque",
        [
            "__import__('os').system('rm -rf /')",
            "eval('1+1')",
            "exec('x=1')",
            "open('/etc/passwd').read()",
            "().__class__.__bases__[0]",
            "[Coluna].__class__",
            "os.system",
            "lambda: 1",
            "1; import os",
            "globals()",
            "getattr(x, 'y')",
            "{'a': 1}",
            "x if y else z",
            "1 if 1 else 1",
        ],
    )
    def test_nao_analisa_codigo(self, ataque: str) -> None:
        """
        Nao e lista negra: a gramatica simplesmente nao tem producao para
        chamada, atributo ou identificador solto.
        """
        with pytest.raises(ExpressionError):
            parse_expression(ataque)

    def test_nenhuma_execucao_dinamica_no_modulo(self) -> None:
        """
        Prova por AST: o modulo nao chama nenhuma funcao de execucao dinamica.

        Feito na AST, e nao por busca de texto, porque `re.compile` (que
        compila uma REGEX, nao codigo) daria falso positivo num grep — e um
        teste que grita errado acaba sendo desligado.
        """
        import ast
        from pathlib import Path

        import autotarefas.tasks.expressions as mod

        proibidas = {"eval", "exec", "compile", "__import__", "getattr", "setattr", "globals"}
        arvore = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))

        chamadas = {
            no.func.id
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
        }
        assert not (chamadas & proibidas), f"execucao dinamica no modulo: {chamadas & proibidas}"

    def test_aninhamento_excessivo_e_recusado(self) -> None:
        """Protecao contra expressao patologica que estouraria a pilha."""
        with pytest.raises(ExpressionError, match="aninhada"):
            parse_expression("(" * (MAX_DEPTH + 5) + "1" + ")" * (MAX_DEPTH + 5))

    def test_expressao_gigante_e_recusada(self) -> None:
        with pytest.raises(ExpressionError, match="longa"):
            parse_expression("1 + " * 300 + "1")


# ============================================================
# Erros de configuracao (mal formada)
# ============================================================


class TestExpressaoMalFormada:
    @pytest.mark.parametrize(
        "texto",
        ["", "   ", "1 +", "+", "(1 + 2", "1 + 2)", "[] * 2", "1 ** 2", "* 3", "[a] [b]"],
    )
    def test_recusa(self, texto: str) -> None:
        with pytest.raises(ExpressionError):
            parse_expression(texto)

    def test_mensagem_aponta_a_posicao(self) -> None:
        with pytest.raises(ExpressionError, match="posicao"):
            parse_expression("[a] @ [b]")


# ============================================================
# Erros de linha (nao derrubam a validacao)
# ============================================================


class TestErrosDeLinha:
    def test_divisao_por_zero(self) -> None:
        with pytest.raises(EvaluationError, match="zero"):
            evaluate(parse_expression("[a] / [b]"), {"a": Decimal(1), "b": Decimal(0)})

    def test_valor_ausente(self) -> None:
        with pytest.raises(EvaluationError, match="nao tem um numero"):
            evaluate(parse_expression("[a] + 1"), {"a": None})

    def test_coluna_fora_do_contexto(self) -> None:
        with pytest.raises(EvaluationError):
            evaluate(parse_expression("[x]"), {})


# ============================================================
# Utilitarios
# ============================================================


class TestUtilitarios:
    def test_columns_used(self) -> None:
        arvore = parse_expression("([Valor Bruto] - [Desconto]) * [Taxa] + 1")
        assert columns_used(arvore) == {"Valor Bruto", "Desconto", "Taxa"}

    def test_columns_used_sem_colunas(self) -> None:
        assert columns_used(parse_expression("1 + 2")) == set()

    def test_arvore_e_imutavel_e_tipada(self) -> None:
        arvore = parse_expression("[a] * 2")
        assert isinstance(arvore, BinOp)
        assert arvore.op == "*"
        assert isinstance(arvore.left, Col)
        assert isinstance(arvore.right, Num)

    def test_determinismo(self) -> None:
        assert parse_expression("[a] + [b] * 2") == parse_expression("[a] + [b] * 2")

    @pytest.mark.parametrize(
        ("valor", "texto"),
        [
            (Decimal("450.00"), "450"),
            (Decimal("3.30"), "3.3"),
            (Decimal("0"), "0"),
            (Decimal("-2.5"), "-2.5"),
            (Decimal("1000000"), "1000000"),
        ],
    )
    def test_format_decimal(self, valor: Decimal, texto: str) -> None:
        assert format_decimal(valor) == texto
