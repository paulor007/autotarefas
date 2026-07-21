"""Testes do motor puro de grupos e regras derivadas."""

from __future__ import annotations

from decimal import Decimal

import pytest

from autotarefas.tasks.expressions import parse_expression
from autotarefas.tasks.row_rules import (
    DerivedFinding,
    apply_derived,
    find_inconsistencies,
    index_groups,
    to_decimal,
)

ZERO = Decimal(0)


# ============================================================
# Conversao numerica
# ============================================================


class TestToDecimal:
    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            (10, "10"),
            (3.3, "3.3"),  # str() recupera o decimal pretendido
            ("450", "450"),
            ("19,90", "19.90"),  # virgula decimal (BR)
            ("1.234,56", "1234.56"),  # milhar BR
            ("1,234.56", "1234.56"),  # milhar US
            ("R$ 1.500,00", "1500.00"),
            ("  42  ", "42"),
            ("-5", "-5"),
        ],
    )
    def test_converte(self, entrada: object, esperado: str) -> None:
        assert to_decimal(entrada) == Decimal(esperado)

    @pytest.mark.parametrize(
        "entrada",
        [None, "", "   ", "abc", "#DIV/0!", "#REF!", "#N/D", True, False, float("nan")],
    )
    def test_nao_numero_vira_none(self, entrada: object) -> None:
        """None = 'nao ha numero aqui'. Um fato sobre o dado, nao uma excecao."""
        assert to_decimal(entrada) is None

    def test_decimal_e_exato(self) -> None:
        valor = to_decimal("1.1")
        assert valor is not None
        assert valor * 3 == Decimal("3.3")


# ============================================================
# Agrupamento
# ============================================================


class TestIndexGroups:
    def test_chave_simples(self) -> None:
        grupos, fora = index_groups([["A"], ["B"], ["A"]])
        assert grupos == {("A",): [0, 2], ("B",): [1]}
        assert fora == []

    def test_chave_composta(self) -> None:
        grupos, _ = index_groups([["P1", "2026"], ["P1", "2025"], ["P1", "2026"]])
        assert grupos == {("P1", "2026"): [0, 2], ("P1", "2025"): [1]}

    def test_repeticao_da_chave_e_normal(self) -> None:
        """A chave se repetir e o que FORMA o grupo — nunca um erro."""
        grupos, fora = index_groups([["X"]] * 5)
        assert grupos == {("X",): [0, 1, 2, 3, 4]}
        assert fora == []

    def test_chave_vazia_fica_de_fora(self) -> None:
        grupos, fora = index_groups([["A"], [""], ["  "]])
        assert grupos == {("A",): [0]}
        assert [f.index for f in fora] == [1, 2]
        assert all(not f.partial for f in fora)

    def test_chave_composta_parcialmente_vazia(self) -> None:
        grupos, fora = index_groups([["P1", "2026"], ["P1", ""]])
        assert grupos == {("P1", "2026"): [0]}
        assert len(fora) == 1
        assert fora[0].partial is True
        assert fora[0].empty_positions == (1,)

    def test_chave_composta_totalmente_vazia(self) -> None:
        _, fora = index_groups([["", ""]])
        assert fora[0].partial is False

    def test_ordem_deterministica(self) -> None:
        a, _ = index_groups([["B"], ["A"], ["B"]])
        b, _ = index_groups([["B"], ["A"], ["B"]])
        assert list(a) == list(b)


# ============================================================
# Coerencia dentro do grupo
# ============================================================


class TestInconsistencias:
    def test_grupo_coerente_nao_gera_achado(self) -> None:
        grupos: dict[tuple[str, ...], list[int]] = {("A",): [0, 1]}
        valores = {"Data": ["2026-01-01", "2026-01-01"]}
        assert find_inconsistencies(grupos, valores, ["Data"]) == []

    def test_grupo_divergente(self) -> None:
        grupos: dict[tuple[str, ...], list[int]] = {("A",): [0, 1, 2]}
        valores = {"Data": ["2026-01-01", "2026-01-01", "2026-02-09"]}
        achados = find_inconsistencies(grupos, valores, ["Data"])
        assert len(achados) == 1
        assert achados[0].column == "Data"
        assert achados[0].group_size == 3
        assert achados[0].distinct_count == 2

    def test_um_achado_por_grupo_e_coluna(self) -> None:
        """Nao um por linha: uma divergencia = um issue."""
        grupos: dict[tuple[str, ...], list[int]] = {("A",): [0, 1], ("B",): [2, 3]}
        valores = {"X": ["1", "2", "9", "9"], "Y": ["a", "b", "c", "c"]}
        achados = find_inconsistencies(grupos, valores, ["X", "Y"])
        assert len(achados) == 2  # grupo A diverge em X e em Y
        assert {a.key for a in achados} == {("A",)}

    def test_mostra_TODOS_os_valores_sem_eleger_um(self) -> None:
        """O AutoTarefas nao conhece a verdade do negocio."""
        grupos: dict[tuple[str, ...], list[int]] = {("A",): [0, 1, 2]}
        valores = {"Resp": ["Ana", "Bruno", "Carla"]}
        achado = find_inconsistencies(grupos, valores, ["Resp"])[0]
        assert [v for v, _ in achado.variants] == ["Ana", "Bruno", "Carla"]
        assert achado.distinct_count == 3

    def test_indices_das_linhas_sao_corretos(self) -> None:
        grupos: dict[tuple[str, ...], list[int]] = {("A",): [0, 3, 7]}
        valores = {"X": ["p", "", "", "q", "", "", "", "p"]}
        achado = find_inconsistencies(grupos, valores, ["X"])[0]
        variantes = dict(achado.variants)
        assert variantes["p"] == (0, 7)
        assert variantes["q"] == (3,)

    def test_grupo_de_uma_linha_nao_diverge(self) -> None:
        um: dict[tuple[str, ...], list[int]] = {("A",): [0]}
        assert find_inconsistencies(um, {"X": ["1"]}, ["X"]) == []

    def test_coluna_ausente_e_ignorada_sem_quebrar(self) -> None:
        g: dict[tuple[str, ...], list[int]] = {("A",): [0, 1]}
        assert find_inconsistencies(g, {}, ["NaoExiste"]) == []

    def test_limita_variantes_mostradas(self) -> None:
        grupos: dict[tuple[str, ...], list[int]] = {("A",): list(range(10))}
        valores = {"X": [str(i) for i in range(10)]}
        achado = find_inconsistencies(grupos, valores, ["X"])[0]
        assert achado.distinct_count == 10
        assert len(achado.variants) <= 4  # MAX_VARIANTS_SHOWN


# ============================================================
# Regras derivadas
# ============================================================


def derivar(
    expressao: str,
    alvo: list[object],
    colunas: dict[str, list[object]],
    tol: str = "0",
) -> list[DerivedFinding]:
    return list(apply_derived(parse_expression(expressao), alvo, colunas, Decimal(tol)))


class TestDerivadas:
    def test_tudo_certo_nao_gera_nada(self) -> None:
        achados = derivar("[q] * [v]", [200, 450], {"q": [2, 3], "v": [100, 150]})
        assert achados == []

    def test_divergencia(self) -> None:
        achados = derivar("[q] * [v]", [200, 400], {"q": [2, 3], "v": [100, 150]})
        assert len(achados) == 1
        assert achados[0].index == 1
        assert achados[0].computed == "450"
        assert achados[0].observed == "400"
        assert achados[0].difference == "50"
        assert achados[0].reason is None  # foi CALCULADA e divergiu

    def test_soma_e_subtracao(self) -> None:
        assert derivar("[a] + [b] - [c]", [120], {"a": [100], "b": [50], "c": [30]}) == []

    def test_divisao(self) -> None:
        assert derivar("[a] / [b]", [5], {"a": [10], "b": [2]}) == []

    def test_agrupamento(self) -> None:
        assert derivar("([a] - [b]) * [c]", [15], {"a": [200], "b": [50], "c": ["0.1"]}) == []

    def test_tolerancia_zero_exige_igualdade_exata(self) -> None:
        achados = derivar("[a] * 3", ["3.31"], {"a": ["1.1"]})
        assert len(achados) == 1

    def test_dentro_da_tolerancia_explicita(self) -> None:
        assert derivar("[a] * 3", ["3.31"], {"a": ["1.1"]}, tol="0.01") == []

    def test_fora_da_tolerancia_explicita(self) -> None:
        assert len(derivar("[a] * 3", ["3.35"], {"a": ["1.1"]}, tol="0.01")) == 1

    def test_ponto_flutuante_nao_gera_falso_positivo(self) -> None:
        """Com float, 1.1*3 != 3.3 e isto falharia. Com Decimal, fecha."""
        assert derivar("[a] * 3", [3.3], {"a": [1.1]}) == []

    def test_divisao_por_zero_vira_nao_calculavel(self) -> None:
        achados = derivar("[a] / [b]", [1], {"a": [1], "b": [0]})
        assert len(achados) == 1
        assert achados[0].reason == "divisao por zero"
        assert achados[0].computed is None  # NAO foi calculada

    def test_valor_vazio_vira_nao_calculavel(self) -> None:
        achados = derivar("[a] * 2", [10], {"a": [""]})
        assert achados[0].reason is not None

    def test_valor_invalido_vira_nao_calculavel(self) -> None:
        achados = derivar("[a] * 2", [10], {"a": ["muitos"]})
        assert achados[0].reason is not None

    def test_erro_do_excel_vira_nao_calculavel(self) -> None:
        achados = derivar("[a] * 2", [10], {"a": ["#DIV/0!"]})
        assert achados[0].reason is not None

    def test_alvo_nao_numerico_vira_nao_calculavel(self) -> None:
        achados = derivar("[a] * 2", ["n/d"], {"a": [5]})
        assert achados[0].reason is not None
        assert achados[0].computed == "10"  # a conta deu certo; o alvo e que nao serve

    def test_e_um_gerador_preguicoso(self) -> None:
        """Linhas corretas nao ocupam memoria."""
        from collections.abc import Iterator

        resultado = apply_derived(parse_expression("[a]"), [1], {"a": [1]}, ZERO)
        assert isinstance(resultado, Iterator)

    def test_determinismo(self) -> None:
        alvo: list[object] = [200, 400]
        colunas: dict[str, list[object]] = {"q": [2, 3], "v": [100, 150]}
        assert derivar("[q] * [v]", alvo, colunas) == derivar("[q] * [v]", alvo, colunas)
