"""
Catalogo de perfis e remapeamento de Schema.

O foco anti-overfitting: o LOADER e o REMAPEADOR nao conhecem nenhum
dominio. Os testes usam recursos reais (o catalogo do pacote) e Schemas
sinteticos montados na hora, sem depender de um arquivo especifico.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from autotarefas.profiles import (
    ProfileError,
    list_profiles,
    load_all_profiles,
    load_profile,
    referenced_fields,
    remap_schema,
)
from autotarefas.profiles.catalog import _valid_id
from autotarefas.tasks.validate import Schema

# ============================================================
# Catalogo — carrega do PACOTE, nao do disco de dev
# ============================================================


class TestCatalogo:
    def test_lista_do_pacote(self) -> None:
        ids = list_profiles()
        assert isinstance(ids, list)
        assert "cadastro_contatos" in ids

    def test_ids_unicos(self) -> None:
        ids = list_profiles()
        assert len(ids) == len(set(ids))

    def test_ordem_deterministica(self) -> None:
        assert list_profiles() == list_profiles()

    def test_todo_perfil_carrega_e_valida(self) -> None:
        """Todo recurso do catalogo tem que ser um perfil valido."""
        perfis = load_all_profiles()
        for pid, perfil in perfis.items():
            assert perfil.id == pid
            assert perfil.version >= 1
            assert len(perfil.profile_schema.columns) >= 1

    def test_perfil_inexistente(self) -> None:
        with pytest.raises(ProfileError, match="nao existe"):
            load_profile("perfil_que_nao_existe")


# ============================================================
# Seguranca — id nunca vira caminho
# ============================================================


class TestSegurancaDeId:
    @pytest.mark.parametrize(
        "malicioso",
        [
            "../secret",
            "..",
            "a/b",
            "a\\b",
            "/etc/passwd",
            "conta os",
            "Conta",  # maiuscula
            "",
            "1perfil",  # comeca com digito
            "perfil-x",  # hifen
        ],
    )
    def test_id_invalido_e_recusado(self, malicioso: str) -> None:
        assert not _valid_id(malicioso)
        with pytest.raises(ProfileError):
            load_profile(malicioso)

    @pytest.mark.parametrize("valido", ["cadastro_contatos", "vendas", "a", "x1_y2"])
    def test_id_valido_passa_no_formato(self, valido: str) -> None:
        assert _valid_id(valido)


# ============================================================
# Remapeamento — TODAS as referencias, nao so columns
# ============================================================


def schema_completo() -> Schema:
    """Um Schema sintetico que exercita TODOS os tipos de referencia."""
    return Schema.model_validate(
        {
            "columns": [
                {"name": "campo_a", "type": "int"},
                {"name": "campo b", "type": "float"},  # com espaco
                {"name": "campo_ç", "type": "float"},  # com acento
                {"name": "grupo_id"},
            ],
            "group_keys": [{"name": "g", "columns": ["grupo_id"]}],
            "group_checks": [{"name": "gc", "group_key": "g", "consistent": ["campo_a"]}],
            "derived_checks": [
                {
                    "name": "calc",
                    "target": "campo_a",
                    "expression": "[campo b] * [campo_ç]",
                }
            ],
        }
    )


class TestRemapeamento:
    def test_remapeia_columns(self) -> None:
        novo = remap_schema(schema_completo(), {"campo_a": "Coluna A"})
        nomes = [c.name for c in novo.columns]
        assert "Coluna A" in nomes
        assert "campo_a" not in nomes

    def test_remapeia_group_keys(self) -> None:
        novo = remap_schema(schema_completo(), {"grupo_id": "ID do Grupo"})
        assert novo.group_keys[0].columns == ("ID do Grupo",)

    def test_remapeia_group_checks(self) -> None:
        novo = remap_schema(schema_completo(), {"campo_a": "Coluna A"})
        assert novo.group_checks[0].consistent == ("Coluna A",)

    def test_remapeia_derived_target(self) -> None:
        novo = remap_schema(schema_completo(), {"campo_a": "Total"})
        assert novo.derived_checks[0].target == "Total"

    def test_remapeia_referencias_na_expressao(self) -> None:
        """O ponto delicado: [Nome] dentro da expressao, via parser."""
        novo = remap_schema(
            schema_completo(),
            {"campo b": "Base Real", "campo_ç": "Fator Real"},
        )
        expr = novo.derived_checks[0].expression
        assert "Base Real" in expr
        assert "Fator Real" in expr
        assert "campo b" not in expr

    def test_nomes_com_espaco_e_acento(self) -> None:
        novo = remap_schema(
            schema_completo(),
            {"campo b": "Coluna Com Espaço", "campo_ç": "Outra Coluna"},
        )
        nomes = [c.name for c in novo.columns]
        assert "Coluna Com Espaço" in nomes

    def test_expressao_remapeada_continua_valida(self) -> None:
        """A expressao reescrita tem que ser reanalisavel e dar o mesmo calculo."""
        from decimal import Decimal

        from autotarefas.tasks.expressions import evaluate, parse_expression

        novo = remap_schema(
            schema_completo(),
            {"campo b": "B", "campo_ç": "F"},
        )
        arvore = parse_expression(novo.derived_checks[0].expression)
        resultado = evaluate(arvore, {"B": Decimal(3), "F": Decimal(4)})
        assert resultado == Decimal(12)

    def test_expressao_nao_sofre_troca_textual_ingenua(self) -> None:
        """
        Se 'a' fosse trocado por substring, 'campo_a' viraria 'campo_X'. O
        parser troca so a referencia inteira [Nome], nunca pedaco de palavra.
        """
        schema = Schema.model_validate(
            {
                "columns": [{"name": "a"}, {"name": "banana"}],
                "derived_checks": [{"name": "r", "target": "a", "expression": "[banana] * 2"}],
            }
        )
        novo = remap_schema(schema, {"a": "X"})
        # 'banana' contem 'a' mas NAO pode ser afetado
        assert "[banana]" in novo.derived_checks[0].expression

    def test_omit_remove_coluna_e_regras_orfas(self) -> None:
        novo = remap_schema(schema_completo(), {}, omit={"campo b"})
        nomes = [c.name for c in novo.columns]
        assert "campo b" not in nomes
        # a derived usava campo b -> some junto
        assert len(novo.derived_checks) == 0

    def test_omit_remove_group_key_orfa(self) -> None:
        novo = remap_schema(schema_completo(), {}, omit={"grupo_id"})
        assert len(novo.group_keys) == 0
        assert len(novo.group_checks) == 0  # dependia da chave

    def test_original_nao_e_modificado(self) -> None:
        original = schema_completo()
        remap_schema(original, {"campo_a": "X"})
        assert original.columns[0].name == "campo_a"

    def test_determinismo(self) -> None:
        s = schema_completo()
        a = remap_schema(s, {"campo_a": "X"})
        b = remap_schema(s, {"campo_a": "X"})
        assert a.model_dump() == b.model_dump()


class TestReferencedFields:
    def test_coleta_de_todos_os_lugares(self) -> None:
        campos = referenced_fields(schema_completo())
        assert {"campo_a", "campo b", "campo_ç", "grupo_id"} <= campos


# ============================================================
# Anti-overfitting — o loader nao conhece dominio
# ============================================================


class TestLoaderSemDominio:
    def test_codigo_do_loader_e_remap_sem_termo_de_dominio(self) -> None:
        # termos de DOMINIO. "nome" fica de fora de proposito: e a palavra
        # portuguesa para "name" e aparece como variavel de iteracao — proibi-la
        # no codigo seria absurdo. Os termos abaixo nao tem uso generico legitimo.
        proibidos = {
            "cliente", "clientes", "venda", "vendas", "cpf", "cnpj", "email",
            "telefone", "produto", "estoque", "pedido", "contato",
            "cadastro", "documento", "razao",
        }  # fmt: skip
        raiz = Path(__file__).parent.parent.parent / "src" / "autotarefas" / "profiles"

        for arquivo in (raiz / "catalog.py", raiz / "remap.py", raiz / "export.py"):
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            docstrings = {
                id(no.value)
                for no in ast.walk(arvore)
                if isinstance(no, ast.Expr) and isinstance(no.value, ast.Constant)
            }
            for no in ast.walk(arvore):
                textos = []
                if (
                    isinstance(no, ast.Constant)
                    and isinstance(no.value, str)
                    and id(no) not in docstrings
                ):
                    textos.append(no.value)
                elif isinstance(no, ast.Name):
                    textos.append(no.id)
                elif isinstance(no, (ast.FunctionDef, ast.ClassDef)):
                    textos.append(no.name)
                for texto in textos:
                    import re

                    tokens = {t.lower() for t in re.split(r"[_\W]+", texto) if t}
                    achados = tokens & proibidos
                    assert not achados, f"{arquivo.name} conhece dominio: {achados}"
