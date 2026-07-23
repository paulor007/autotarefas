"""
Procedencia no Schema/validate e presenca dos recursos no pacote.

O teste de empacotamento nao reconstroi o wheel (lento e dependente de
rede); ele confirma o que importa em CI: que os recursos sao acessiveis
como dados do PACOTE via importlib.resources — que e exatamente o
mecanismo que o wheel usa.
"""

from __future__ import annotations

from importlib.resources import files

import pytest

from autotarefas.tasks.validate import Provenance, Schema


class TestProvenanceModel:
    def test_schema_aceita_generated_from(self) -> None:
        s = Schema.model_validate(
            {
                "columns": [{"name": "X"}],
                "generated_from": {
                    "profile": "cadastro_contatos",
                    "profile_version": 1,
                    "tool_version": "1.4.0",
                },
            }
        )
        assert isinstance(s.generated_from, Provenance)
        assert s.generated_from.profile == "cadastro_contatos"

    def test_schema_sem_generated_from(self) -> None:
        s = Schema.model_validate({"columns": [{"name": "X"}]})
        assert s.generated_from is None

    def test_provenance_tolera_campos_futuros(self) -> None:
        """extra=allow: um campo novo de linhagem nao quebra schemas de hoje."""
        s = Schema.model_validate(
            {
                "columns": [{"name": "X"}],
                "generated_from": {"profile": "p", "campo_futuro": "valor"},
            }
        )
        assert s.generated_from is not None


class TestEmpacotamento:
    def test_recurso_acessivel_como_dado_do_pacote(self) -> None:
        """
        O mesmo mecanismo do wheel: importlib.resources acessa o YAML como
        dado do pacote, sem depender do diretorio atual.
        """
        recurso = files("autotarefas.profiles.resources") / "cadastro_contatos.yaml"
        assert recurso.is_file()
        conteudo = recurso.read_text(encoding="utf-8")
        assert "id: cadastro_contatos" in conteudo

    def test_pasta_de_recursos_existe_no_pacote(self) -> None:
        raiz = files("autotarefas.profiles.resources")
        yamls = [r.name for r in raiz.iterdir() if r.name.endswith(".yaml")]
        assert "cadastro_contatos.yaml" in yamls

    @pytest.mark.parametrize("recurso", ["cadastro_contatos.yaml"])
    def test_todo_recurso_declara_id_e_versao(self, recurso: str) -> None:
        import yaml

        conteudo = (files("autotarefas.profiles.resources") / recurso).read_text(encoding="utf-8")
        dados = yaml.safe_load(conteudo)
        assert "id" in dados
        assert "version" in dados
