"""
Resolucao do mapeamento — testes de regressao do bug do resumo posicional.

CONTEXTO: a primeira versao montava a tabela exibida ao usuario pareando os
campos do perfil com as colunas da planilha POR POSICAO, e chegou a mostrar
`telefone -> Documento` enquanto o YAML (corretamente) escrevia `Documento`
com regra de CPF. O motor acertava e a tela mentia.

A correcao foi estrutural: o mapeamento resolvido virou um DADO
(`ExportResult.resolutions`), e o resumo passou a ser renderizacao dele. Os
testes aqui travam esse contrato — varios deles FALHARIAM com qualquer
implementacao que volte a associar por posicao.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from autotarefas.profiles import load_profile
from autotarefas.profiles.export import (
    MappingError,
    export_schema,
    render_mapping,
    resolve_mapping,
)
from autotarefas.tasks.validate import load_schema

PERFIL = "cadastro_contatos"


def destinos(resultado: object) -> dict[str, str | None]:
    """campo -> coluna, direto das resolucoes."""
    return {r.field: r.column for r in resultado.resolutions}  # type: ignore[attr-defined]


# ============================================================
# O bug original
# ============================================================


class TestRegressaoResumoPosicional:
    def test_cpf_nao_vira_telefone(self) -> None:
        """
        O caso relatado: perfil com 5 campos, 3 mapeados, planilha com 3 colunas.

        Por POSICAO, o 3o campo (telefone) receberia a 3a coluna (Documento).
        Por NOME, quem recebe 'Documento' e o cpf — que foi o que se pediu.
        """
        perfil = load_profile(PERFIL)
        r = export_schema(
            perfil,
            {"nome": "Cliente", "email": "Contato principal", "cpf": "Documento"},
        )
        d = destinos(r)
        assert d["cpf"] == "Documento"
        assert d["telefone"] is None  # nao mapeado -> omitido
        assert d["cnpj"] is None

    def test_resumo_exibido_bate_com_o_yaml(self) -> None:
        """A tabela e o arquivo nao podem discordar: saem da mesma estrutura."""
        perfil = load_profile(PERFIL)
        r = export_schema(perfil, {"nome": "Cliente", "cpf": "Documento"})

        texto = "\n".join(render_mapping(r))
        assert "cpf" in texto
        # a linha do cpf aponta para Documento
        linha_cpf = next(ln for ln in render_mapping(r) if ln.strip().startswith("cpf"))
        assert "Documento" in linha_cpf
        linha_tel = next(ln for ln in render_mapping(r) if ln.strip().startswith("telefone"))
        assert "Documento" not in linha_tel

        # e o YAML concorda
        dados = yaml.safe_load(r.yaml_text)
        col = next(c for c in dados["columns"] if c["name"] == "Documento")
        assert col["validator_br"] == "cpf"

    def test_campo_opcional_no_meio_nao_desloca_os_seguintes(self) -> None:
        """
        Perfil: nome, email, telefone, cpf, cnpj. Mapeados: nome, email, cpf.

        O cenario exato que o §6 exige: telefone fica no meio sem mapa e nao
        pode empurrar o cpf para a posicao dele.
        """
        r = export_schema(
            load_profile(PERFIL),
            {"nome": "A", "email": "B", "cpf": "C"},
        )
        d = destinos(r)
        assert d == {"nome": "A", "email": "B", "telefone": None, "cpf": "C", "cnpj": None}

    def test_yaml_usa_validator_br_cpf_na_coluna_certa(self) -> None:
        r = export_schema(load_profile(PERFIL), {"nome": "N", "cpf": "Documento"})
        dados = yaml.safe_load(r.yaml_text)
        nomes = {c["name"]: c for c in dados["columns"]}
        assert nomes["Documento"]["validator_br"] == "cpf"
        # telefone nao mapeado nao pode aparecer de forma alguma
        assert not any(c.get("format") == "phone" for c in dados["columns"])


# ============================================================
# Ordem, nomes e determinismo
# ============================================================


class TestOrdemEDeterminismo:
    def test_ordem_dos_map_nao_altera_o_resultado(self) -> None:
        perfil = load_profile(PERFIL)
        a = export_schema(perfil, {"nome": "N", "email": "E", "cpf": "D"})
        b = export_schema(perfil, {"cpf": "D", "nome": "N", "email": "E"})
        assert destinos(a) == destinos(b)
        assert a.yaml_text == b.yaml_text

    def test_resolucoes_seguem_a_ordem_do_perfil(self) -> None:
        perfil = load_profile(PERFIL)
        r = export_schema(perfil, {"cpf": "D", "nome": "N"})
        assert [x.field for x in r.resolutions] == list(perfil.concept_fields)

    def test_determinismo(self) -> None:
        perfil = load_profile(PERFIL)
        m = {"nome": "N", "cpf": "D"}
        assert export_schema(perfil, m).yaml_text == export_schema(perfil, m).yaml_text

    @pytest.mark.parametrize(
        ("campo", "coluna"),
        [
            ("nome", "Razão social"),
            ("email", "E-mail principal"),
            ("cpf", "Documento do responsável"),
            ("nome", "Nome  com  espaços"),
        ],
    )
    def test_nomes_com_espaco_e_acento_preservados(self, campo: str, coluna: str) -> None:
        r = export_schema(load_profile(PERFIL), {"nome": "N", campo: coluna})
        assert destinos(r)[campo] == coluna
        assert coluna in r.yaml_text
        assert coluna in "\n".join(render_mapping(r))


# ============================================================
# Rejeicoes
# ============================================================


class TestRejeicoes:
    def test_campo_inexistente(self) -> None:
        with pytest.raises(MappingError, match="nao tem o"):
            resolve_mapping(load_profile(PERFIL), {"fantasma": "X"})

    def test_coluna_vazia(self) -> None:
        with pytest.raises(MappingError, match="vazio"):
            resolve_mapping(load_profile(PERFIL), {"nome": "   "})

    def test_dois_campos_para_a_mesma_coluna(self) -> None:
        with pytest.raises(MappingError, match="mesma coluna"):
            resolve_mapping(load_profile(PERFIL), {"nome": "X", "cpf": "X"})

    def test_coluna_inexistente_quando_ha_planilha(self) -> None:
        with pytest.raises(MappingError, match="nao encontrada"):
            resolve_mapping(
                load_profile(PERFIL),
                {"nome": "Fantasma"},
                available_columns=["Cliente", "Documento"],
            )

    def test_sem_planilha_nao_confere_colunas(self) -> None:
        """Sem --planilha nao ha como conferir; o mapeamento passa."""
        r = resolve_mapping(load_profile(PERFIL), {"nome": "QualquerNome"})
        assert r[0].column == "QualquerNome"


# ============================================================
# Ciclo completo pela CLI
# ============================================================


class TestCicloCLI:
    def test_cli_ate_validate_com_cpf_invalido(self, tmp_path: Path) -> None:
        """
        A prova que identifica QUAL validador rodou.

        '11987654321' tem cara de celular valido. Se a regra aplicada fosse a
        de telefone, passaria. Como e a de CPF, tem que falhar.
        """
        from click.testing import CliRunner

        from autotarefas.cli.main import cli
        from autotarefas.core import TaskStatus
        from autotarefas.tasks.validate import ValidateTask

        base = tmp_path / "b.csv"
        base.write_text(
            "Cliente,Contato principal,Documento\nEmpresa X,c@x.com,11987654321\n",
            encoding="utf-8",
        )
        out = tmp_path / "s.yaml"

        r = CliRunner().invoke(
            cli,
            [
                "perfis",
                "exportar",
                PERFIL,
                "--planilha",
                str(base),
                "--map",
                "nome=Cliente",
                "--map",
                "email=Contato principal",
                "--map",
                "cpf=Documento",
                "--out",
                str(out),
            ],
        )
        assert r.exit_code == 0
        assert "cpf" in r.output
        assert "Documento" in r.output

        resultado = ValidateTask(base, load_schema(out), mode="auditoria").execute()
        assert resultado.status == TaskStatus.FAILURE
        mensagens = " ".join(str(i["message"]) for i in resultado.data["issues"])
        assert "CPF" in mensagens
        assert "elefone" not in mensagens

    def test_cli_recusa_coluna_inexistente(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from autotarefas.cli.main import cli

        # planilha realista: o reader recusa arquivos pequenos demais para
        # detectar uma tabela, e nesse caso a conferencia e pulada com aviso.
        base = tmp_path / "b.csv"
        base.write_text(
            "Cliente,Contato principal,Documento\n"
            + "\n".join(f"Empresa {i},e{i}@x.com,111.444.777-35" for i in range(30))
            + "\n",
            encoding="utf-8",
        )
        r = CliRunner().invoke(
            cli,
            [
                "perfis",
                "exportar",
                PERFIL,
                "--planilha",
                str(base),
                "--map",
                "nome=NaoExiste",
                "--out",
                str(tmp_path / "s.yaml"),
            ],
        )
        assert r.exit_code == 2
        assert "nao encontrada" in r.output

    def test_cli_recusa_map_repetido(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from autotarefas.cli.main import cli

        r = CliRunner().invoke(
            cli,
            [
                "perfis",
                "exportar",
                PERFIL,
                "--map",
                "cpf=A",
                "--map",
                "cpf=B",
                "--out",
                str(tmp_path / "s.yaml"),
            ],
        )
        assert r.exit_code == 2
        assert "mais de uma vez" in r.output
