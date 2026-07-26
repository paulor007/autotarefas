"""
Servico de analise (1.8B): orquestracao reutilizavel do nucleo.

O teste mais importante e `TestAmbiguidadeDeAba::test_varias_abas_viram_escolha`:
a ambiguidade de aba NAO chega como confianca baixa — o leitor recusa o
arquivo e preenche as candidatas. Sem tratar esse caminho, uma pasta de tres
abas encerraria a jornada em "arquivo recusado" quando falta apenas uma
pergunta.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from autotarefas.services import analyze_spreadsheet
from autotarefas.services.analysis import (
    DEFAULT_PREVIEW_ROWS,
    Ambiguity,
    AnalysisOutcome,
)
from autotarefas.tasks.validate import load_schema

FX = Path(__file__).parent.parent / "fixtures" / "planilhas"


class TestAnaliseBasica:
    def test_csv_simples(self) -> None:
        r = analyze_spreadsheet(FX / "01_csv_limpo.csv")
        assert r.ok is True
        assert r.needs_choice is False
        assert r.report["estrutura"]["row_count"] > 0
        assert r.report["columns"]

    def test_xlsx_simples(self) -> None:
        r = analyze_spreadsheet(FX / "02_xlsx_limpo.xlsx")
        assert r.ok is True
        assert r.report["estrutura"]["column_count"] > 0

    def test_previa_e_limitada(self) -> None:
        """A previa serve para reconhecer o arquivo, nao para transporta-lo."""
        r = analyze_spreadsheet(FX / "01_csv_limpo.csv", preview_rows=3)
        assert r.preview
        assert len(r.preview.splitlines()) < DEFAULT_PREVIEW_ROWS + 10

    def test_payload_nao_expoe_caminho_fisico(self) -> None:
        """Só o NOME do arquivo: o caminho no disco do cliente e sensivel."""
        r = analyze_spreadsheet(FX / "01_csv_limpo.csv")
        assert r.report["metadata"]["source_file"] == "01_csv_limpo.csv"
        texto = str(r.report)
        assert str(FX) not in texto
        assert "/home" not in texto

    def test_cabecalho_deslocado_e_detectado(self) -> None:
        r = analyze_spreadsheet(FX / "06_cabecalho_linha_4.xlsx")
        assert r.ok is True
        assert r.header_row == 4


class TestSchemaSugerido:
    def test_e_carregavel_pelo_loader_real(self, tmp_path: Path) -> None:
        """O schema sugerido tem que servir de entrada para o validate."""
        r = analyze_spreadsheet(FX / "01_csv_limpo.csv")
        destino = tmp_path / "s.yaml"
        destino.write_text(r.schema_suggestion, encoding="utf-8")
        schema = load_schema(destino)
        assert len(schema.columns) == r.report["estrutura"]["column_count"]

    def test_permanece_conservador(self) -> None:
        """Nada de required/unique/limites inventados (contrato da 1.4)."""
        r = analyze_spreadsheet(FX / "01_csv_limpo.csv")
        dados = yaml.safe_load(r.schema_suggestion)
        for coluna in dados["columns"]:
            assert set(coluna) <= {"name", "type"}, coluna
        assert "group_keys" not in dados
        assert "derived_checks" not in dados

    def test_sem_procedencia_inventada(self) -> None:
        r = analyze_spreadsheet(FX / "01_csv_limpo.csv")
        assert "generated_from" not in r.schema_suggestion


class TestAmbiguidadeDeAba:
    def test_varias_abas_viram_escolha(self) -> None:
        """
        O caminho REAL: o leitor recusa e devolve as candidatas.

        `ok` e False (nao houve leitura), mas `needs_choice` e True — a
        jornada continua com uma pergunta, nao termina em erro.
        """
        r = analyze_spreadsheet(FX / "07_tres_abas.xlsx")
        assert r.ok is False
        assert r.needs_choice is True
        ambiguidade = r.ambiguities[0]
        assert ambiguidade.kind == "sheet"
        nomes = [o.name for o in ambiguidade.sheet_options]
        assert len(nomes) == 3
        assert all(o.rows > 0 for o in ambiguidade.sheet_options)

    def test_escolha_explicita_resolve(self) -> None:
        r = analyze_spreadsheet(FX / "07_tres_abas.xlsx", sheet="Vendas")
        assert r.ok is True
        assert r.needs_choice is False
        assert r.selected_sheet == "Vendas"
        assert r.report["columns"]

    def test_escolha_invalida_nao_reoferece_a_mesma_pergunta(self) -> None:
        """
        Aba inexistente e outro problema: nao ha escolha a oferecer.

        Se devolvessemos ambiguidade aqui, a interface perguntaria de novo o
        que a pessoa acabou de responder.
        """
        r = analyze_spreadsheet(FX / "07_tres_abas.xlsx", sheet="NaoExiste")
        assert r.ok is False
        assert r.needs_choice is False
        assert r.rejection

    def test_aba_unica_nao_gera_pergunta(self) -> None:
        r = analyze_spreadsheet(FX / "02_xlsx_limpo.xlsx")
        assert r.needs_choice is False

    def test_duas_abas_com_confianca_alta_nao_gera_pergunta(self) -> None:
        """Confianca alta = o leitor sabe qual e; nao ha o que perguntar."""
        r = analyze_spreadsheet(FX / "08_capa_e_dados.xlsx")
        assert r.ok is True
        assert r.needs_choice is False


class TestRecusaDefinitiva:
    def test_arquivo_nao_tabular_nao_e_recuperavel(self) -> None:
        r = analyze_spreadsheet(FX / "25_nao_tabular.xlsx")
        assert r.ok is False
        assert r.needs_choice is False
        assert r.rejection

    def test_recusa_nao_levanta_excecao(self) -> None:
        """Arquivo ruim e um FATO sobre o arquivo, nao erro do programa."""
        r = analyze_spreadsheet(FX / "25_nao_tabular.xlsx")
        assert isinstance(r, AnalysisOutcome)


class TestContratoDoServico:
    def test_nao_depende_de_web_nem_de_cli(self) -> None:
        """
        O servico e reutilizavel pela CLI e pelo Live porque nao conhece
        nenhum dos dois. Um import de FastAPI/Click aqui seria acoplamento.
        """
        import ast

        fonte = (
            Path(__file__).parent.parent.parent / "src" / "autotarefas" / "services" / "analysis.py"
        ).read_text(encoding="utf-8")
        proibidos = {"fastapi", "starlette", "click", "flask", "uvicorn"}
        for no in ast.walk(ast.parse(fonte)):
            if isinstance(no, ast.Import):
                nomes = {a.name.split(".")[0] for a in no.names}
            elif isinstance(no, ast.ImportFrom):
                nomes = {(no.module or "").split(".")[0]}
            else:
                continue
            assert not (nomes & proibidos), f"acoplamento indevido: {nomes & proibidos}"

    def test_nao_modifica_o_arquivo(self) -> None:
        import hashlib

        alvo = FX / "01_csv_limpo.csv"
        antes = hashlib.sha256(alvo.read_bytes()).hexdigest()
        analyze_spreadsheet(alvo)
        assert hashlib.sha256(alvo.read_bytes()).hexdigest() == antes

    def test_determinismo(self) -> None:
        a = analyze_spreadsheet(FX / "01_csv_limpo.csv")
        b = analyze_spreadsheet(FX / "01_csv_limpo.csv")
        assert a.schema_suggestion == b.schema_suggestion
        assert [c["name"] for c in a.report["columns"]] == [c["name"] for c in b.report["columns"]]

    def test_ambiguity_e_imutavel(self) -> None:
        amb = Ambiguity(kind="sheet", confidence=0.5)
        with pytest.raises((AttributeError, TypeError)):
            amb.kind = "header"  # type: ignore[misc]


class TestAntiOverfitting:
    @pytest.mark.parametrize(
        "fixture",
        ["30_administrativa.xlsx", "31_estoque.xlsx", "32_servicos.csv"],
    )
    def test_dominios_diferentes(self, fixture: str) -> None:
        """A mesma orquestracao serve qualquer dominio: ela nao conhece nenhum."""
        r = analyze_spreadsheet(FX / fixture)
        assert r.ok is True
        assert r.report["columns"]
        assert r.schema_suggestion

    def test_servico_sem_termo_de_dominio(self) -> None:
        """
        O CODIGO nao conhece dominio; a DOCUMENTACAO pode falar dele.

        A distincao e por AST, nao por busca de texto: a docstring do modulo
        diz "o caminho no disco do cliente pode ser sensivel" — ali "cliente"
        e a pessoa que usa a ferramenta, nao a tabela de clientes. Proibir a
        palavra na prosa tornaria o teste um estorvo. O que nao pode e regra
        de negocio virar nome, literal ou ramo de decisao.
        """
        import ast
        import re

        proibidos = {
            "clientes", "venda", "vendas", "estoque", "produto", "produtos",
            "pedido", "pedidos", "cpf", "cnpj",
        }  # fmt: skip
        arvore = ast.parse(
            (
                Path(__file__).parent.parent.parent
                / "src"
                / "autotarefas"
                / "services"
                / "analysis.py"
            ).read_text(encoding="utf-8")
        )
        docstrings = {
            id(no.value)
            for no in ast.walk(arvore)
            if isinstance(no, ast.Expr) and isinstance(no.value, ast.Constant)
        }
        for no in ast.walk(arvore):
            textos: list[str] = []
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
                tokens = {t.lower() for t in re.split(r"[_\W]+", texto) if t}
                achados = tokens & proibidos
                assert not achados, f"dominio no servico: {achados} em {texto!r}"
