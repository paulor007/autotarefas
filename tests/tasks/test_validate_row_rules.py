"""
Integracao das regras de grupo e derivadas no `ValidateTask`.

Cobre o que os testes do motor puro nao alcancam: carga do schema,
compatibilidade com schemas antigos, erros de configuracao, severidades,
e a prova anti-overfitting — as MESMAS regras, escritas de formas
diferentes, funcionando em dominios que o nucleo desconhece.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from autotarefas.core import TaskStatus
from autotarefas.tasks.validate import ValidateTask, load_schema

if TYPE_CHECKING:
    from autotarefas.core import TaskResult

FIXTURES = Path(__file__).parent.parent / "fixtures" / "planilhas"


def escrever(tmp_path: Path, nome: str, conteudo: str) -> Path:
    alvo = tmp_path / nome
    alvo.write_text(textwrap.dedent(conteudo).strip() + "\n", encoding="utf-8")
    return alvo


def validar(planilha: Path, schema_yaml: str, tmp_path: Path) -> TaskResult:
    schema = load_schema(escrever(tmp_path, "schema.yaml", schema_yaml))
    return ValidateTask(planilha, schema, mode="auditoria").execute()


def mensagens(resultado: TaskResult) -> list[str]:
    return [str(i["message"]) for i in resultado.data.get("issues", [])]


# ============================================================
# Compatibilidade — o requisito mais importante
# ============================================================


class TestCompatibilidade:
    def test_schema_antigo_carrega_sem_as_secoes_novas(self, tmp_path: Path) -> None:
        schema = load_schema(
            escrever(tmp_path, "s.yaml", "columns:\n  - name: produto\n    type: str")
        )
        assert schema.group_keys == ()
        assert schema.group_checks == ()
        assert schema.derived_checks == ()

    def test_schema_canonico_do_projeto_continua_valido(self) -> None:
        schema = load_schema(Path("examples/fixtures/schema_clientes.yaml"))
        assert len(schema.columns) > 0
        assert schema.derived_checks == ()

    def test_validacao_sem_regras_novas_e_identica(self, tmp_path: Path) -> None:
        r = validar(
            FIXTURES / "27_valor_derivado_divergente.xlsx",
            """
            columns:
              - name: produto
              - name: quantidade
                type: int
            """,
            tmp_path,
        )
        assert r.status == TaskStatus.SUCCESS
        assert r.data["total_errors"] == 0


# ============================================================
# Regras derivadas
# ============================================================


class TestDerivadas:
    def test_fixture_27_pega_a_divergencia_real(self, tmp_path: Path) -> None:
        """3 x 150 = 450, mas a planilha diz 400."""
        r = validar(
            FIXTURES / "27_valor_derivado_divergente.xlsx",
            """
            columns:
              - name: produto
              - name: quantidade
                type: int
              - name: valor_unitario
                type: float
              - name: valor_final
                type: float
            derived_checks:
              - name: total_da_linha
                target: valor_final
                expression: "[quantidade] * [valor_unitario]"
            """,
            tmp_path,
        )
        assert r.data["total_errors"] == 1
        issue = r.data["issues"][0]
        assert issue["line"] == 3
        assert "450" in issue["message"]
        assert "400" in issue["message"]

    def test_tolerancia_padrao_e_zero(self, tmp_path: Path) -> None:
        """Nenhuma folga e assumida sem o usuario pedir."""
        schema = load_schema(
            escrever(
                tmp_path,
                "s.yaml",
                """
                columns:
                  - name: a
                  - name: b
                derived_checks:
                  - name: r
                    target: a
                    expression: "[b]"
                """,
            )
        )
        assert schema.derived_checks[0].tolerance == 0

    def test_severity_warning_nao_invalida_o_arquivo(self, tmp_path: Path) -> None:
        r = validar(
            FIXTURES / "27_valor_derivado_divergente.xlsx",
            """
            columns:
              - name: quantidade
                type: int
              - name: valor_unitario
                type: float
              - name: valor_final
                type: float
            derived_checks:
              - name: total_da_linha
                target: valor_final
                expression: "[quantidade] * [valor_unitario]"
                severity: warning
            """,
            tmp_path,
        )
        assert r.status == TaskStatus.SUCCESS
        assert r.data["total_errors"] == 0
        assert r.data["total_warnings"] == 1

    def test_nao_calculavel_e_sempre_aviso(self, tmp_path: Path) -> None:
        """Dado faltando nao e o mesmo que conta errada."""
        planilha = escrever(tmp_path, "d.csv", "a,b\n10,\n20,2")
        r = validar(
            planilha,
            """
            columns:
              - name: a
              - name: b
            derived_checks:
              - name: r
                target: a
                expression: "[b] * 10"
                severity: error
            """,
            tmp_path,
        )
        assert r.data["total_warnings"] == 1
        assert any("nao pode ser calculada" in m for m in mensagens(r))


# ============================================================
# Grupos
# ============================================================


class TestGrupos:
    ESQUEMA = """
        columns:
          - name: Codigo
          - name: Data
          - name: Responsavel
        group_keys:
          - name: lote
            columns: ["Codigo"]
        group_checks:
          - name: coerencia
            group_key: lote
            consistent: ["Data", "Responsavel"]
    """

    def test_grupo_coerente_passa(self, tmp_path: Path) -> None:
        planilha = escrever(
            tmp_path, "g.csv", "Codigo,Data,Responsavel\nA,2026-01-01,Ana\nA,2026-01-01,Ana"
        )
        r = validar(planilha, self.ESQUEMA, tmp_path)
        assert r.data["total_errors"] == 0

    def test_repeticao_da_chave_NAO_e_erro(self, tmp_path: Path) -> None:
        """A chave se repetir e o normal — e o que forma o grupo."""
        planilha = escrever(
            tmp_path, "g.csv", "Codigo,Data,Responsavel\nA,2026-01-01,Ana\nA,2026-01-01,Ana"
        )
        r = validar(planilha, self.ESQUEMA, tmp_path)
        assert not any("duplicad" in m.lower() for m in mensagens(r))

    def test_grupo_divergente_gera_um_issue_por_coluna(self, tmp_path: Path) -> None:
        planilha = escrever(
            tmp_path,
            "g.csv",
            "Codigo,Data,Responsavel\nA,2026-01-01,Ana\nA,2026-02-09,Bruno\nA,2026-01-01,Ana",
        )
        r = validar(planilha, self.ESQUEMA, tmp_path)
        # 1 issue para Data + 1 para Responsavel — nao um por linha
        assert r.data["total_errors"] == 2

    def test_mensagem_mostra_valores_linhas_e_tamanho_sem_eleger_um(self, tmp_path: Path) -> None:
        planilha = escrever(
            tmp_path,
            "g.csv",
            "Codigo,Data,Responsavel\nA,2026-01-01,Ana\nA,2026-02-09,Ana\nA,2026-01-01,Ana",
        )
        msg = mensagens(validar(planilha, self.ESQUEMA, tmp_path))[0]
        assert "coerencia" in msg  # nome da regra
        assert "lote=[A]" in msg  # chave do grupo
        assert "3 registro(s)" in msg  # tamanho do grupo
        assert "2026-01-01" in msg  # os dois valores encontrados
        assert "2026-02-09" in msg
        assert "linha(s) 2, 4" in msg  # linhas fisicas
        # e NAO diz qual e o certo
        assert "esperado" not in msg.lower()
        assert "correto:" not in msg.lower()

    def test_chave_composta(self, tmp_path: Path) -> None:
        planilha = escrever(
            tmp_path,
            "g.csv",
            "Projeto,Ano,Unidade\nP1,2026,Norte\nP1,2026,Sul\nP1,2025,Leste",
        )
        r = validar(
            planilha,
            """
            columns:
              - name: Projeto
              - name: Ano
              - name: Unidade
            group_keys:
              - name: projeto_ano
                columns: ["Projeto", "Ano"]
            group_checks:
              - name: coerencia
                group_key: projeto_ano
                consistent: ["Unidade"]
            """,
            tmp_path,
        )
        # so o grupo (P1, 2026) diverge; (P1, 2025) tem 1 linha
        assert r.data["total_errors"] == 1
        assert "projeto_ano=[P1, 2026]" in mensagens(r)[0]

    def test_chave_vazia_gera_aviso_e_fica_fora_do_grupo(self, tmp_path: Path) -> None:
        planilha = escrever(
            tmp_path, "g.csv", "Codigo,Data,Responsavel\n,2026-01-01,Ana\nA,2026-01-01,Ana"
        )
        r = validar(planilha, self.ESQUEMA, tmp_path)
        assert r.data["total_warnings"] == 1
        assert any("fora do agrupamento" in m for m in mensagens(r))

    def test_chave_composta_parcialmente_vazia(self, tmp_path: Path) -> None:
        planilha = escrever(tmp_path, "g.csv", "Projeto,Ano,Unidade\nP1,,Norte\nP1,2026,Sul")
        r = validar(
            planilha,
            """
            columns:
              - name: Projeto
              - name: Ano
              - name: Unidade
            group_keys:
              - name: pa
                columns: ["Projeto", "Ano"]
            group_checks:
              - name: c
                group_key: pa
                consistent: ["Unidade"]
            """,
            tmp_path,
        )
        assert any("vazia em ['Ano']" in m for m in mensagens(r))

    def test_severity_warning(self, tmp_path: Path) -> None:
        planilha = escrever(
            tmp_path, "g.csv", "Codigo,Data,Responsavel\nA,2026-01-01,Ana\nA,2026-02-09,Ana"
        )
        r = validar(
            planilha,
            """
            columns:
              - name: Codigo
              - name: Data
              - name: Responsavel
            group_keys:
              - name: lote
                columns: ["Codigo"]
            group_checks:
              - name: coerencia
                group_key: lote
                consistent: ["Data"]
                severity: warning
            """,
            tmp_path,
        )
        assert r.data["total_errors"] == 0
        assert r.data["total_warnings"] >= 1

    def test_grupo_repetido_e_linha_duplicada_sao_coisas_diferentes(self, tmp_path: Path) -> None:
        """Duas linhas 100% identicas: chave repetida (ok) + linha duplicada (aviso)."""
        planilha = escrever(
            tmp_path, "g.csv", "Codigo,Data,Responsavel\nA,2026-01-01,Ana\nA,2026-01-01,Ana"
        )
        r = validar(
            planilha,
            """
            columns:
              - name: Codigo
              - name: Data
              - name: Responsavel
            detect_duplicate_rows: true
            group_keys:
              - name: lote
                columns: ["Codigo"]
            group_checks:
              - name: coerencia
                group_key: lote
                consistent: ["Data", "Responsavel"]
            """,
            tmp_path,
        )
        msgs = mensagens(r)
        assert any("Linha duplicada" in m for m in msgs)  # a verificacao de duplicata
        assert not any("valores diferentes" in m for m in msgs)  # o grupo esta coerente


# ============================================================
# Configuracao invalida — sempre explicita, nunca "regra ignorada"
# ============================================================


class TestConfiguracaoInvalida:
    @pytest.mark.parametrize(
        ("descricao", "yaml_ruim"),
        [
            (
                "campo escrito errado",
                "columns: [{name: a}, {name: b}]\n"
                'derived_checks: [{name: r, target: a, operaton: x, expression: "[b]"}]',
            ),
            (
                "expressao maliciosa",
                "columns: [{name: a}]\n"
                "derived_checks: [{name: r, target: a, expression: \"__import__('os')\"}]",
            ),
            (
                "tolerancia negativa",
                "columns: [{name: a}, {name: b}]\n"
                'derived_checks: [{name: r, target: a, expression: "[b]", tolerance: -1}]',
            ),
            (
                "coluna inexistente na expressao",
                "columns: [{name: a}]\n"
                'derived_checks: [{name: r, target: a, expression: "[fantasma]"}]',
            ),
            (
                "target inexistente",
                "columns: [{name: a}]\n"
                'derived_checks: [{name: r, target: fantasma, expression: "[a]"}]',
            ),
            (
                "group_key inexistente",
                "columns: [{name: a}]\n"
                "group_checks: [{name: g, group_key: fantasma, consistent: [a]}]",
            ),
            (
                "lista de colunas vazia",
                "columns: [{name: a}]\ngroup_keys: [{name: k, columns: []}]",
            ),
            (
                "nomes de regra repetidos",
                "columns: [{name: a}, {name: b}]\n"
                'derived_checks: [{name: r, target: a, expression: "[b]"}, '
                '{name: r, target: b, expression: "[a]"}]',
            ),
            (
                "estrutura incompleta",
                "columns: [{name: a}]\nderived_checks: [{name: r, target: a}]",
            ),
        ],
    )
    def test_erro_de_configuracao_barra_na_carga(
        self, descricao: str, yaml_ruim: str, tmp_path: Path
    ) -> None:
        """
        Tudo isso morre no `load_schema` — antes de qualquer linha ser lida,
        e com o mesmo comportamento (e exit code) dos outros erros de schema.
        """
        with pytest.raises(Exception, match=r"(?i)schema|valid"):
            load_schema(escrever(tmp_path, "ruim.yaml", yaml_ruim))

    def test_coluna_ausente_no_ARQUIVO_falha_explicitamente(self, tmp_path: Path) -> None:
        """
        A coluna existe no schema mas nao no arquivo: a regra nao roda — e o
        cliente PRECISA saber. Nunca um silencioso "regra ignorada".
        """
        planilha = escrever(tmp_path, "d.csv", "a\n1")
        r = validar(
            planilha,
            """
            columns:
              - name: a
              - name: b
                required: false
            derived_checks:
              - name: r
                target: a
                expression: "[b] * 2"
            """,
            tmp_path,
        )
        assert r.status == TaskStatus.FAILURE
        assert r.error_type == "RuleConfigError"
        assert "r" in str(r.error_message)


# ============================================================
# ANTI-OVERFITTING — o nucleo nao conhece dominio
# ============================================================


class TestAntiOverfitting:
    @pytest.mark.parametrize(
        ("dominio", "csv", "schema_yaml", "erros"),
        [
            (
                "administrativo",
                "Matricula,Departamento,Data de Admissão\n1,RH,2020-01-01\n"
                "1,TI,2020-01-01\n2,RH,2021-05-05",
                """
                columns:
                  - name: Matricula
                  - name: Departamento
                  - name: "Data de Admissão"
                group_keys:
                  - name: pessoa
                    columns: ["Matricula"]
                group_checks:
                  - name: coerencia_cadastral
                    group_key: pessoa
                    consistent: ["Departamento", "Data de Admissão"]
                """,
                1,
            ),
            (
                "estoque",
                "Codigo,Saldo Inicial,Entradas,Saidas,Saldo Final\nX,100,50,30,120\nY,200,10,5,999",
                """
                columns:
                  - name: Codigo
                  - name: "Saldo Inicial"
                    type: float
                  - name: Entradas
                    type: float
                  - name: Saidas
                    type: float
                  - name: "Saldo Final"
                    type: float
                derived_checks:
                  - name: fechamento
                    target: "Saldo Final"
                    expression: "[Saldo Inicial] + [Entradas] - [Saidas]"
                """,
                1,
            ),
            (
                "financeiro",
                "Nota,Valor Bruto,Desconto,Taxa,Valor Líquido\n1,200,50,0.1,15\n2,100,0,0.5,40",
                """
                columns:
                  - name: Nota
                  - name: "Valor Bruto"
                    type: float
                  - name: Desconto
                    type: float
                  - name: Taxa
                    type: float
                  - name: "Valor Líquido"
                    type: float
                derived_checks:
                  - name: liquido
                    target: "Valor Líquido"
                    expression: "([Valor Bruto] - [Desconto]) * [Taxa]"
                """,
                1,
            ),
        ],
    )
    def test_mesma_engrenagem_em_dominios_diferentes(
        self, dominio: str, csv: str, schema_yaml: str, erros: int, tmp_path: Path
    ) -> None:
        """
        Administrativo, estoque, financeiro — o nucleo nao sabe o que sao.
        As regras vem TODAS da configuracao do usuario.
        """
        r = validar(escrever(tmp_path, f"{dominio}.csv", csv), schema_yaml, tmp_path)
        assert r.data["total_errors"] == erros

    def test_nucleo_nao_cita_termo_de_dominio(self) -> None:
        """AST: os modulos novos nao podem conhecer negocio nenhum."""
        import ast
        import re

        proibidos = {
            "cpf", "cnpj", "sku", "venda", "vendas", "estoque", "faturamento",
            "cliente", "clientes", "pedido", "pedidos", "produto", "produtos",
            "projeto", "projetos", "funcionario", "departamento", "salario",
            "fiscal", "loja", "lojas",
        }  # fmt: skip
        raiz = Path(__file__).parent.parent.parent / "src" / "autotarefas" / "tasks"

        for arquivo in (raiz / "expressions.py", raiz / "row_rules.py"):
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            # Toda string SOLTA como statement e documentacao — docstring de
            # modulo, de classe, de funcao ou de atributo. Documentacao explica
            # a fronteira (inclusive citando o cliente); ela nao e logica.
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
                    tokens = {t.lower() for t in re.split(r"[_\W]+", texto) if t}
                    achados = tokens & proibidos
                    assert not achados, f"{arquivo.name} conhece dominio: {achados} em {texto!r}"
