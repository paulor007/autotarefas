"""
Perfil `vendas_itens` (1.9A).

Este perfil existe para exercitar a metade do motor que o `cadastro_contatos`
nao alcanca: `group_keys`, `group_checks` e `derived_checks` — as regras entre
linhas e entre colunas da Subetapa 1.5. Ate aqui, nenhum perfil as usava, e a
infraestrutura de perfis nunca tinha sido provada com elas.

O caso mais importante e `TestOmissaoDeCampos`: um perfil so serve se o
cliente puder mapear o que TEM, sem que a ausencia de uma coluna opcional
derrube regras que nada tem a ver com ela.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from autotarefas.core import TaskResult, TaskStatus
from autotarefas.profiles import export_schema, list_profiles, load_profile
from autotarefas.tasks.validate import ValidateTask, load_schema

PERFIL = "vendas_itens"

COLUNAS_REAIS = ["Pedido", "Data", "Loja", "Produto", "Qtd", "Preco", "Total"]

MAPA_COMPLETO = {
    "numero_pedido": "Pedido",
    "data_pedido": "Data",
    "cliente": "Loja",
    "produto": "Produto",
    "quantidade": "Qtd",
    "valor_unitario": "Preco",
    "valor_total": "Total",
}

#: Pedido 1001 tem duas linhas com Data divergente; a 1002 tem o total errado.
CSV_COM_PROBLEMAS = (
    "Pedido,Data,Loja,Produto,Qtd,Preco,Total\n"
    "1001,2026-01-05,Centro,Caneta,2,10.00,20.00\n"
    "1001,2026-02-09,Centro,Caderno,1,25.00,25.00\n"
    "1002,2026-01-06,Norte,Mochila,3,50.00,999.00\n"
    "1003,2026-01-07,Sul,Lapis,4,2.50,10.00\n"
)

CSV_LIMPO = (
    "Pedido,Data,Loja,Produto,Qtd,Preco,Total\n"
    "1001,2026-01-05,Centro,Caneta,2,10.00,20.00\n"
    "1001,2026-01-05,Centro,Caderno,1,25.00,25.00\n"
    "1002,2026-01-06,Norte,Mochila,3,50.00,150.00\n"
)


def exportar(mapping: dict[str, str], colunas: list[str] | None = None) -> dict[str, Any]:
    """Exporta o schema do perfil e devolve o YAML ja interpretado."""
    resultado = export_schema(
        load_profile(PERFIL), mapping, available_columns=colunas or COLUNAS_REAIS
    )
    return dict(yaml.safe_load(resultado.yaml_text))


def validar(tmp_path: Path, csv_texto: str, mapping: dict[str, str]) -> TaskResult:
    entrada = tmp_path / "itens.csv"
    entrada.write_text(csv_texto, encoding="utf-8")
    resultado = export_schema(load_profile(PERFIL), mapping, available_columns=COLUNAS_REAIS)
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(resultado.yaml_text, encoding="utf-8")
    return ValidateTask(entrada, load_schema(schema_path), mode="auditoria").execute()


# ============================================================
# Catálogo e carga
# ============================================================


class TestCatalogo:
    def test_aparece_no_catalogo_sem_alteracao_de_codigo(self) -> None:
        """O catálogo é dinâmico: basta o recurso existir no pacote."""
        assert PERFIL in list_profiles()

    def test_convive_com_o_perfil_anterior(self) -> None:
        assert {"cadastro_contatos", PERFIL} <= set(list_profiles())

    def test_carrega_pelo_modelo_real(self) -> None:
        perfil = load_profile(PERFIL)
        assert perfil.id == PERFIL
        assert perfil.version >= 1
        assert perfil.title
        assert perfil.summary

    def test_apenas_o_numero_do_pedido_e_obrigatorio(self) -> None:
        """
        Só a chave do grupo é exigida.

        Uma planilha de itens varia muito entre sistemas: exigir sete colunas
        tornaria o perfil inútil para quase todo mundo.
        """
        assert load_profile(PERFIL).required_fields == ("numero_pedido",)

    def test_todo_campo_tem_documentacao(self) -> None:
        perfil = load_profile(PERFIL)
        for campo in perfil.concept_fields:
            assert perfil.fields[campo].doc, campo


# ============================================================
# As regras da 1.5, que nenhum perfil exercitava
# ============================================================


class TestRegrasEntreLinhasEColunas:
    def test_declara_chave_de_grupo(self) -> None:
        esquema = load_profile(PERFIL).profile_schema
        assert [k.columns for k in esquema.group_keys] == [("numero_pedido",)]

    def test_declara_coerencia_dentro_do_grupo(self) -> None:
        esquema = load_profile(PERFIL).profile_schema
        consistentes = {c for g in esquema.group_checks for c in g.consistent}
        assert consistentes == {"data_pedido", "cliente"}

    def test_declara_a_conta_do_item(self) -> None:
        derivada = load_profile(PERFIL).profile_schema.derived_checks[0]
        assert derivada.target == "valor_total"
        assert "quantidade" in derivada.expression
        assert "valor_unitario" in derivada.expression

    def test_tolerancia_zero(self) -> None:
        """
        Com Decimal a igualdade exata é alcançável; folga automática esconderia
        divergência que ninguém autorizou.
        """
        assert load_profile(PERFIL).profile_schema.derived_checks[0].tolerance == 0

    def test_nao_exige_unicidade_do_numero_do_pedido(self) -> None:
        """A chave se REPETE por construção — é o que forma o grupo."""
        esquema = load_profile(PERFIL).profile_schema
        pedido = next(c for c in esquema.columns if c.name == "numero_pedido")
        assert pedido.unique is False


# ============================================================
# Fronteira: nada de política comercial
# ============================================================


class TestSemRegraDeNegocio:
    def test_nao_inventa_politica_comercial(self) -> None:
        """
        Aritmetica (total = qtd x preco) cabe; politica comercial nao.

        Desconto máximo, margem, imposto e preço mínimo variam de empresa para
        empresa — o AutoTarefas não conhece o negócio de ninguém.
        """
        from importlib.resources import files

        # Le o recurso do PACOTE (nao um caminho do disco de dev): e o mesmo
        # mecanismo que vale no wheel instalado.
        recurso = files("autotarefas.profiles.resources") / f"{PERFIL}.yaml"
        dados = yaml.safe_load(recurso.read_text(encoding="utf-8"))
        for coluna in dados["schema"]["columns"]:
            # nenhum limite numérico arbitrário
            assert "min_value" not in coluna, coluna["name"]
            assert "max_value" not in coluna, coluna["name"]
            assert "enum" not in coluna, coluna["name"]

    def test_nao_marca_colunas_como_unicas(self) -> None:
        for coluna in load_profile(PERFIL).profile_schema.columns:
            assert coluna.unique is False, coluna.name


# ============================================================
# Omissão de campos — o caso que decide se o perfil é usável
# ============================================================


class TestOmissaoDeCampos:
    def test_mapeamento_completo_mantem_todas_as_regras(self) -> None:
        dados = exportar(MAPA_COMPLETO)
        assert [c["name"] for c in dados["columns"]] == COLUNAS_REAIS
        assert len(dados["group_checks"]) == 2
        assert len(dados["derived_checks"]) == 1

    def test_sem_total_a_conta_some_e_o_grupo_permanece(self) -> None:
        dados = exportar(
            {
                "numero_pedido": "Pedido",
                "data_pedido": "Data",
                "cliente": "Loja",
                "quantidade": "Qtd",
                "valor_unitario": "Preco",
            }
        )
        assert "derived_checks" not in dados
        assert len(dados["group_checks"]) == 2

    def test_so_a_data_mapeada_preserva_a_checagem_da_data(self) -> None:
        """
        O motivo de haver DUAS regras de coerência, e não uma com duas colunas.

        O núcleo remove a regra inteira quando qualquer coluna dela é omitida.
        Com uma regra só, quem mapeasse apenas a data perderia também a
        checagem da data.
        """
        dados = exportar({"numero_pedido": "Pedido", "data_pedido": "Data"})
        nomes = [g["name"] for g in dados["group_checks"]]
        assert nomes == ["data_coerente_no_pedido"]

    def test_so_o_cliente_mapeado_preserva_a_checagem_do_cliente(self) -> None:
        dados = exportar({"numero_pedido": "Pedido", "cliente": "Loja"})
        nomes = [g["name"] for g in dados["group_checks"]]
        assert nomes == ["cliente_coerente_no_pedido"]

    def test_apenas_o_obrigatorio_gera_schema_valido(self, tmp_path: Path) -> None:
        """Mínimo absoluto: só a chave. Nenhuma regra sobra, e está tudo bem."""
        dados = exportar({"numero_pedido": "Pedido"})
        assert [c["name"] for c in dados["columns"]] == ["Pedido"]
        assert "group_checks" not in dados
        assert "derived_checks" not in dados

        destino = tmp_path / "s.yaml"
        destino.write_text(
            export_schema(
                load_profile(PERFIL),
                {"numero_pedido": "Pedido"},
                available_columns=COLUNAS_REAIS,
            ).yaml_text,
            encoding="utf-8",
        )
        assert len(load_schema(destino).columns) == 1

    def test_schema_exportado_nunca_tem_referencia_orfa(self) -> None:
        """Toda coluna citada por uma regra existe no schema gerado."""
        for mapping in (
            MAPA_COMPLETO,
            {"numero_pedido": "Pedido", "data_pedido": "Data"},
            {"numero_pedido": "Pedido", "quantidade": "Qtd", "valor_unitario": "Preco"},
        ):
            dados = exportar(mapping)
            declaradas = {c["name"] for c in dados["columns"]}
            for chave in dados.get("group_keys", []):
                assert set(chave["columns"]) <= declaradas
            for check in dados.get("group_checks", []):
                assert set(check["consistent"]) <= declaradas
            for derivada in dados.get("derived_checks", []):
                assert derivada["target"] in declaradas


# ============================================================
# Ciclo real
# ============================================================


class TestCicloReal:
    def test_arquivo_limpo_passa(self, tmp_path: Path) -> None:
        resultado = validar(tmp_path, CSV_LIMPO, MAPA_COMPLETO)
        assert resultado.status == TaskStatus.SUCCESS

    def test_divergencia_no_grupo_acusa_as_duas_linhas(self, tmp_path: Path) -> None:
        resultado = validar(tmp_path, CSV_COM_PROBLEMAS, MAPA_COMPLETO)
        grupo = next(i for i in resultado.data["issues"] if i.get("category") == "grupo")
        assert grupo["related_lines"] == [2, 3]
        assert "2026-01-05" in grupo["message"]
        assert "2026-02-09" in grupo["message"]

    def test_conta_errada_e_apontada(self, tmp_path: Path) -> None:
        resultado = validar(tmp_path, CSV_COM_PROBLEMAS, MAPA_COMPLETO)
        calculo = next(i for i in resultado.data["issues"] if i.get("category") == "calculo")
        assert calculo["line"] == 4
        assert "999" in calculo["message"]
        assert "150" in calculo["message"]

    def test_as_duas_familias_de_regra_disparam(self, tmp_path: Path) -> None:
        """A prova de que este perfil exercita o que o outro não alcança."""
        resultado = validar(tmp_path, CSV_COM_PROBLEMAS, MAPA_COMPLETO)
        assert resultado.data["issues_by_category"] == {"grupo": 1, "calculo": 1}

    def test_procedencia_verdadeira(self, tmp_path: Path) -> None:
        resultado = validar(tmp_path, CSV_LIMPO, MAPA_COMPLETO)
        assert resultado.data["generated_from"]["profile"] == PERFIL

    def test_nomes_reais_diferentes_do_conceitual(self, tmp_path: Path) -> None:
        """
        Anti-overfitting: as colunas do cliente não têm nada a ver com os
        nomes dos campos do perfil.
        """
        entrada = tmp_path / "outro.csv"
        entrada.write_text(
            "Nº do Pedido,Emissão,Cliente,Item,Unid,Vl Unit,Vl Total\n"
            "A-1,2026-03-01,ACME,Parafuso,10,1.50,15.00\n"
            "A-1,2026-03-01,ACME,Porca,20,0.75,15.00\n",
            encoding="utf-8",
        )
        resultado = export_schema(
            load_profile(PERFIL),
            {
                "numero_pedido": "Nº do Pedido",
                "data_pedido": "Emissão",
                "cliente": "Cliente",
                "quantidade": "Unid",
                "valor_unitario": "Vl Unit",
                "valor_total": "Vl Total",
            },
            available_columns=[
                "Nº do Pedido",
                "Emissão",
                "Cliente",
                "Item",
                "Unid",
                "Vl Unit",
                "Vl Total",
            ],
        )
        destino = tmp_path / "s.yaml"
        destino.write_text(resultado.yaml_text, encoding="utf-8")
        saida = ValidateTask(entrada, load_schema(destino), mode="auditoria").execute()
        assert saida.status == TaskStatus.SUCCESS


# ============================================================
# Mapeamento inválido
# ============================================================


class TestMapeamentoInvalido:
    def test_sem_o_obrigatorio_e_template(self) -> None:
        resultado = export_schema(
            load_profile(PERFIL), {"data_pedido": "Data"}, available_columns=COLUNAS_REAIS
        )
        assert resultado.is_complete is False
        assert "numero_pedido" in resultado.unmapped_required

    @pytest.mark.parametrize(
        ("descricao", "mapping"),
        [
            ("coluna inexistente", {"numero_pedido": "Fantasma"}),
            ("campo inexistente", {"numero_pedido": "Pedido", "xpto": "Data"}),
            (
                "duas para a mesma coluna",
                {"numero_pedido": "Pedido", "cliente": "Pedido"},
            ),
        ],
    )
    def test_recusas(self, descricao: str, mapping: dict[str, str]) -> None:
        from autotarefas.profiles import MappingError

        with pytest.raises(MappingError):
            export_schema(load_profile(PERFIL), mapping, available_columns=COLUNAS_REAIS)
