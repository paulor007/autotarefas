"""
Exportacao, CLI e ciclo real dos perfis.

Aqui esta a prova anti-overfitting exigida: o MESMO perfil, aplicado a duas
planilhas com nomes de coluna totalmente diferentes, funciona so por
mapeamento explicito.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from click.testing import CliRunner

from autotarefas.cli.main import cli
from autotarefas.core import TaskStatus
from autotarefas.profiles import export_schema, load_profile
from autotarefas.profiles.export import UNMAPPED_PREFIX
from autotarefas.tasks.validate import ValidateTask, load_schema

if TYPE_CHECKING:
    from collections.abc import Mapping


def exportar_para(tmp_path: Path, mapping: Mapping[str, str], nome: str = "s.yaml") -> Path:
    perfil = load_profile("cadastro_contatos")
    resultado = export_schema(perfil, mapping)
    destino = tmp_path / nome
    destino.write_text(resultado.yaml_text, encoding="utf-8")
    return destino


# ============================================================
# Template vs schema pronto — a distincao
# ============================================================


class TestTemplateVsPronto:
    def test_sem_mapa_e_template(self) -> None:
        r = export_schema(load_profile("cadastro_contatos"))
        assert r.is_complete is False
        assert "nome" in r.unmapped_required
        assert UNMAPPED_PREFIX in r.yaml_text
        assert "TEMPLATE" in r.yaml_text

    def test_requerido_mapeado_e_pronto(self) -> None:
        r = export_schema(load_profile("cadastro_contatos"), {"nome": "Nome Real"})
        assert r.is_complete is True
        assert UNMAPPED_PREFIX not in r.yaml_text
        assert "pronto" in r.yaml_text.lower()

    def test_opcional_nao_mapeado_e_OMITIDO_nao_marcado(self) -> None:
        """Schema pronto nunca contem marcador — o opcional some, nao vira PREENCHA_."""
        r = export_schema(load_profile("cadastro_contatos"), {"nome": "N", "cpf": "Doc"})
        assert r.is_complete is True
        assert UNMAPPED_PREFIX not in r.yaml_text
        assert "email" in r.unmapped_optional
        assert "telefone" in r.unmapped_optional

    def test_procedencia_no_arquivo(self) -> None:
        r = export_schema(load_profile("cadastro_contatos"), {"nome": "N"})
        assert "generated_from" in r.yaml_text
        assert "cadastro_contatos" in r.yaml_text


# ============================================================
# CLI
# ============================================================


class TestCLI:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_listar(self) -> None:
        r = self.runner.invoke(cli, ["perfis", "listar"])
        assert r.exit_code == 0
        assert "cadastro_contatos" in r.output

    def test_ver(self) -> None:
        r = self.runner.invoke(cli, ["perfis", "ver", "cadastro_contatos"])
        assert r.exit_code == 0
        assert "Campos:" in r.output
        assert "obrigatorio" in r.output

    def test_ver_inexistente_exit_2(self) -> None:
        r = self.runner.invoke(cli, ["perfis", "ver", "fantasma"])
        assert r.exit_code == 2
        assert "nao existe" in r.output

    def test_exportar_template(self, tmp_path: Path) -> None:
        out = tmp_path / "t.yaml"
        r = self.runner.invoke(cli, ["perfis", "exportar", "cadastro_contatos", "--out", str(out)])
        assert r.exit_code == 0
        assert out.exists()
        assert "TEMPLATE" in r.output or "NAO esta pronto" in r.output

    def test_exportar_pronto(self, tmp_path: Path) -> None:
        out = tmp_path / "p.yaml"
        r = self.runner.invoke(
            cli,
            [
                "perfis",
                "exportar",
                "cadastro_contatos",
                "--map",
                "nome=Nome Completo",
                "--out",
                str(out),
            ],
        )
        assert r.exit_code == 0
        assert "pronto" in r.output.lower()
        assert out.exists()

    def test_exportar_campo_desconhecido_exit_2(self, tmp_path: Path) -> None:
        r = self.runner.invoke(
            cli,
            [
                "perfis",
                "exportar",
                "cadastro_contatos",
                "--map",
                "inexistente=Coluna",
                "--out",
                str(tmp_path / "x.yaml"),
            ],
        )
        assert r.exit_code == 2
        assert "nao tem o campo" in r.output

    def test_exportar_map_malformado_exit_2(self, tmp_path: Path) -> None:
        r = self.runner.invoke(
            cli,
            [
                "perfis",
                "exportar",
                "cadastro_contatos",
                "--map",
                "sem_igual",
                "--out",
                str(tmp_path / "x.yaml"),
            ],
        )
        assert r.exit_code == 2

    def test_mensagens_em_portugues(self, tmp_path: Path) -> None:
        r = self.runner.invoke(
            cli,
            [
                "perfis",
                "exportar",
                "cadastro_contatos",
                "--map",
                "nome=N",
                "--out",
                str(tmp_path / "p.yaml"),
            ],
        )
        assert "Schema pronto" in r.output


# ============================================================
# Ciclo real: perfil -> export -> validate
# ============================================================


class TestCicloReal:
    def test_arquivo_valido_passa(self, tmp_path: Path) -> None:
        schema_path = exportar_para(tmp_path, {"nome": "Nome", "cpf": "CPF"})
        base = tmp_path / "base.csv"
        base.write_text("Nome,CPF\nAna Silva,111.444.777-35\n", encoding="utf-8")
        r = ValidateTask(base, load_schema(schema_path), mode="auditoria").execute()
        assert r.status == TaskStatus.SUCCESS

    def test_arquivo_invalido_falha(self, tmp_path: Path) -> None:
        schema_path = exportar_para(tmp_path, {"nome": "Nome", "cpf": "CPF"})
        base = tmp_path / "base.csv"
        base.write_text("Nome,CPF\nAna Silva,00000000000\nX,111.444.777-35\n", encoding="utf-8")
        r = ValidateTask(base, load_schema(schema_path), mode="auditoria").execute()
        assert r.status == TaskStatus.FAILURE
        assert r.data["total_errors"] >= 1

    def test_procedencia_chega_ao_relatorio(self, tmp_path: Path) -> None:
        schema_path = exportar_para(tmp_path, {"nome": "Nome"})
        base = tmp_path / "base.csv"
        base.write_text("Nome\nAna Silva\n", encoding="utf-8")
        r = ValidateTask(base, load_schema(schema_path), mode="auditoria").execute()
        proc = r.data.get("generated_from")
        assert proc is not None
        assert proc["profile"] == "cadastro_contatos"
        assert proc["profile_version"] == 1

    def test_schema_sem_procedencia_continua_funcionando(self, tmp_path: Path) -> None:
        """Schema escrito a mao, sem generated_from — nada muda."""
        schema_path = tmp_path / "manual.yaml"
        schema_path.write_text("columns:\n  - name: X\n    type: str\n", encoding="utf-8")
        base = tmp_path / "b.csv"
        base.write_text("X\nvalor\n", encoding="utf-8")
        r = ValidateTask(base, load_schema(schema_path), mode="auditoria").execute()
        assert r.status == TaskStatus.SUCCESS
        assert "generated_from" not in r.data


# ============================================================
# ANTI-OVERFITTING: dois formatos do mesmo cenario
# ============================================================


class TestAntiOverfitting:
    """O mesmo perfil, duas planilhas com nomes diferentes, so por mapeamento."""

    def test_formato_A_nomes_diretos(self, tmp_path: Path) -> None:
        schema_path = exportar_para(
            tmp_path, {"nome": "Nome", "email": "E-mail", "cpf": "CPF"}, "a.yaml"
        )
        base = tmp_path / "a.csv"
        base.write_text("Nome,E-mail,CPF\nAna Silva,ana@x.com,111.444.777-35\n", encoding="utf-8")
        r = ValidateTask(base, load_schema(schema_path), mode="auditoria").execute()
        assert r.status == TaskStatus.SUCCESS

    def test_formato_B_nomes_totalmente_diferentes(self, tmp_path: Path) -> None:
        """Cliente | Contato principal | Documento — mesma configuracao conceitual."""
        schema_path = exportar_para(
            tmp_path,
            {"nome": "Cliente", "email": "Contato principal", "cpf": "Documento"},
            "b.yaml",
        )
        base = tmp_path / "b.csv"
        base.write_text(
            "Cliente,Contato principal,Documento\nEmpresa X,contato@x.com,111.444.777-35\n",
            encoding="utf-8",
        )
        r = ValidateTask(base, load_schema(schema_path), mode="auditoria").execute()
        assert r.status == TaskStatus.SUCCESS

    def test_os_dois_formatos_pegam_o_mesmo_erro(self, tmp_path: Path) -> None:
        """A regra de CPF vale nos dois, com nomes de coluna diferentes."""
        for nome_col, arquivo in [("CPF", "a"), ("Documento", "b")]:
            schema_path = exportar_para(tmp_path, {"nome": "N", "cpf": nome_col}, f"{arquivo}.yaml")
            base = tmp_path / f"{arquivo}.csv"
            base.write_text(f"N,{nome_col}\nAna,00000000000\n", encoding="utf-8")
            r = ValidateTask(base, load_schema(schema_path), mode="auditoria").execute()
            assert r.data["total_errors"] >= 1, f"formato {arquivo} nao pegou o CPF invalido"
