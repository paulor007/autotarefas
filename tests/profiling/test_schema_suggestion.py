"""
Testes do schema sugerido.

A fronteira central desta subetapa, verificada aqui de todas as formas:
**o schema sugerido contem so o que foi OBSERVADO — nunca uma regra
inventada.** E o teste mais forte e o round-trip: o schema gerado e
carregado pelo `validate` de verdade e NAO pode marcar dado valido como
erro.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from autotarefas.profiling import profile_workbook
from autotarefas.profiling.schema_suggestion import build_schema_suggestion
from autotarefas.reader import read_workbook
from autotarefas.tasks.validate import ValidateTask, load_schema

FIXTURES = Path(__file__).parent.parent / "fixtures" / "planilhas"


def gerar(nome: str) -> str:
    return build_schema_suggestion(profile_workbook(read_workbook(FIXTURES / nome)))


def parse(nome: str) -> dict[str, list[dict[str, str]]]:
    """O YAML sugerido, ja parseado (so as linhas ATIVAS, sem comentarios)."""
    resultado: dict[str, list[dict[str, str]]] = yaml.safe_load(gerar(nome))
    return resultado


def bloco_de(texto: str, coluna: str) -> str:
    """Extrai o trecho de texto (com comentarios) de uma coluna."""
    partes = texto.split("  - name:")
    for parte in partes[1:]:
        if coluna in parte.split("\n")[0]:
            return parte
    msg = f"coluna '{coluna}' nao encontrada no schema"
    raise AssertionError(msg)


# ============================================================
# Estrutura: so nome e tipo nas linhas ativas
# ============================================================


class TestEstruturaAtiva:
    def test_yaml_valido(self) -> None:
        dados = parse("02_xlsx_limpo.xlsx")
        assert "columns" in dados
        assert len(dados["columns"]) == 3

    def test_linhas_ativas_tem_apenas_name_e_type(self) -> None:
        """O compromisso do leitor e so esse: nome e tipo."""
        for col in parse("28_vendas_sintetica.xlsx")["columns"]:
            assert set(col.keys()) == {"name", "type"}

    def test_todas_as_colunas_aparecem(self) -> None:
        dados = parse("31_estoque.xlsx")
        nomes = [c["name"] for c in dados["columns"]]
        assert nomes == [
            "Codigo Interno",
            "Descricao",
            "Saldo",
            "Localizacao",
            "Ultima Atualizacao",
        ]


# ============================================================
# Mapeamento de tipos (estrutura, nao regra)
# ============================================================


class TestMapeamentoDeTipos:
    @pytest.mark.parametrize(
        ("fixture", "coluna", "tipo_schema"),
        [
            ("28_vendas_sintetica.xlsx", "Quantidade", "int"),
            ("28_vendas_sintetica.xlsx", "Valor Unitario", "float"),
            ("28_vendas_sintetica.xlsx", "Data", "date"),
            ("28_vendas_sintetica.xlsx", "Produto", "str"),
            ("26_zeros_a_esquerda.csv", "codigo", "str"),  # identificador -> str
            ("14_moeda_br.csv", "preco", "float"),  # moeda -> float
        ],
    )
    def test_tipo(self, fixture: str, coluna: str, tipo_schema: str) -> None:
        dados = parse(fixture)
        col = next(c for c in dados["columns"] if c["name"] == coluna)
        assert col["type"] == tipo_schema


# ============================================================
# A FRONTEIRA: nunca inventar regra
# ============================================================


class TestNuncaInventaRegra:
    def test_nenhum_required_ativo(self) -> None:
        """required nunca e afirmado — o leitor nao sabe obrigatoriedade."""
        for col in parse("28_vendas_sintetica.xlsx")["columns"]:
            assert "required" not in col

    def test_nenhum_unique_ativo(self) -> None:
        """unique nunca e afirmado — repeticao pode ser legitima."""
        for col in parse("28_vendas_sintetica.xlsx")["columns"]:
            assert "unique" not in col

    def test_nenhum_min_max_ativo(self) -> None:
        """O intervalo observado nao vira limite."""
        for col in parse("28_vendas_sintetica.xlsx")["columns"]:
            assert "min_value" not in col
            assert "max_value" not in col

    def test_codigo_repetido_NAO_recebe_unique_ativo(self) -> None:
        """
        O caso critico. 'codigo_venda' se repete (multi-item). Sugerir unique
        marcaria dados validos como erro.
        """
        dados = parse("22_codigo_repetido_valido.xlsx")
        col = next(c for c in dados["columns"] if c["name"] == "codigo_venda")
        assert "unique" not in col

    def test_intervalo_vai_como_comentario_informativo(self) -> None:
        """O min/max observado aparece — mas comentado, e marcado como 'NAO e limite'."""
        bloco = bloco_de(gerar("28_vendas_sintetica.xlsx"), "Valor Unitario")
        assert "# observado na amostra" in bloco
        assert "NAO e um limite" in bloco

    def test_nenhum_validator_br_ou_format(self) -> None:
        """Sao dominio: 'parece CPF', 'parece e-mail'. O leitor nao decide isso."""
        texto = gerar("03_clientes.xlsx")
        assert "validator_br:" not in texto  # nem ativo nem comentado
        assert "format:" not in texto


# ============================================================
# Sugestoes vao como comentario (nao como regra)
# ============================================================


class TestSugestoesComentadas:
    def test_required_sugerido_quando_100pct(self) -> None:
        bloco = bloco_de(gerar("02_xlsx_limpo.xlsx"), "nome")
        assert "# required: true" in bloco
        assert "100%" in bloco

    def test_baixo_preenchimento_vira_alerta_comentado(self) -> None:
        bloco = bloco_de(gerar("11_coluna_vazia.xlsx"), "reservado")
        # coluna vazia: o comentario alerta, mas nao afirma required
        assert "# required: true" in bloco

    def test_unique_lembrado_so_quando_amostra_toda_distinta(self) -> None:
        # 'nome' em 02 tem 3 valores distintos em 3 linhas
        assert "# unique: true" in bloco_de(gerar("02_xlsx_limpo.xlsx"), "nome")

    def test_duplicatas_viram_sugestao_de_detect_duplicate_rows(self) -> None:
        texto = gerar("21_linhas_duplicadas.xlsx")
        assert "# detect_duplicate_rows: true" in texto


# ============================================================
# Nomes com acento/espaco: YAML seguro
# ============================================================


class TestNomesComplicados:
    def test_nome_com_acento_e_espaco_vira_valido(self) -> None:
        dados = parse("28_vendas_sintetica.xlsx")
        nomes = [c["name"] for c in dados["columns"]]
        assert "Codigo Venda" in nomes
        assert "Valor Unitario" in nomes

    def test_data_nao_iso_vira_str_para_o_validate_aceitar(self) -> None:
        """32_servicos tem Prazo em dd/mm/aaaa: o validate so aceita ISO.

        Sugerir date quebraria o round-trip. Vira str + nota.
        """
        dados = parse("32_servicos.csv")
        prazo = next(c for c in dados["columns"] if c["name"] == "Prazo")
        assert prazo["type"] == "str"
        assert "nao estao em ISO" in bloco_de(gerar("32_servicos.csv"), "Prazo")

    def test_data_ISO_vira_date(self) -> None:
        """31_estoque tem datas nativas do Excel -> saem em ISO -> date."""
        dados = parse("31_estoque.xlsx")
        col = next(c for c in dados["columns"] if c["name"] == "Ultima Atualizacao")
        assert col["type"] == "date"

    def test_round_trip_do_yaml_preserva_o_nome(self) -> None:
        texto = gerar("28_vendas_sintetica.xlsx")
        recarregado = yaml.safe_load(texto)
        assert recarregado["columns"][0]["name"] == "Codigo Venda"


# ============================================================
# O ROUND-TRIP REAL: gerado -> validate -> zero erros
# ============================================================


class TestRoundTripComValidate:
    @pytest.mark.parametrize(
        "fixture",
        [
            "02_xlsx_limpo.xlsx",
            "28_vendas_sintetica.xlsx",
            "30_administrativa.xlsx",
            "31_estoque.xlsx",
            "32_servicos.csv",
        ],
    )
    def test_schema_gerado_e_aceito_e_nao_gera_erro(self, fixture: str, tmp_path: Path) -> None:
        """
        A promessa da subetapa: o schema sugerido roda no validate SEM edicao
        e NAO marca nenhum dado valido como erro. Isso so e possivel porque
        ele nao inventa regra.
        """
        alvo = tmp_path / "schema.yaml"
        alvo.write_text(gerar(fixture), encoding="utf-8")

        schema = load_schema(alvo)  # nao levanta
        task = ValidateTask(FIXTURES / fixture, schema, mode="auditoria")
        result = task.execute()

        assert result.is_success
        assert result.data.get("total_errors", -1) == 0

    def test_schema_carrega_todas_as_colunas(self, tmp_path: Path) -> None:
        alvo = tmp_path / "schema.yaml"
        alvo.write_text(gerar("31_estoque.xlsx"), encoding="utf-8")
        schema = load_schema(alvo)
        assert len(schema.columns) == 5


# ============================================================
# Determinismo
# ============================================================


class TestDeterminismo:
    def test_mesma_planilha_mesmo_schema(self) -> None:
        assert gerar("28_vendas_sintetica.xlsx") == gerar("28_vendas_sintetica.xlsx")
