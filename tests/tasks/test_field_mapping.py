"""
Testes do mapeamento de colunas na importacao (RF-INT-005).

A ficha exige tres estruturas diferentes (contatos, produtos e vendas) —
elas estao em `TestTresEstruturas`. O resto do arquivo protege as regras
que evitam o pior cenario: mandar metade do registro para o sistema do
cliente sem ninguem perceber.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from autotarefas.core.exceptions import ConfigError
from autotarefas.tasks.field_mapping import (
    FieldMapping,
    apply_mapping,
    build_mapping,
    load_mapping_file,
    parse_mapping_specs,
    preview_payloads,
    validate_mapping,
)
from autotarefas.tasks.send_api import SendApiTask

URL = "http://localhost:5555/api/registros"


# ============================================================
# Leitura do mapeamento
# ============================================================


class TestLeituraDoMapeamento:
    def test_par_simples(self) -> None:
        assert parse_mapping_specs(["E-mail=email"]) == (("E-mail", "email"),)

    def test_espacos_sao_aparados(self) -> None:
        assert parse_mapping_specs([" Nome Completo = nome "]) == (("Nome Completo", "nome"),)

    @pytest.mark.parametrize("spec", ["email", "=email", "coluna=", "  =  "])
    def test_sintaxe_invalida(self, spec: str) -> None:
        with pytest.raises(ConfigError, match="mapeamento invalido"):
            parse_mapping_specs([spec])

    def test_arquivo_yaml(self, tmp_path: Path) -> None:
        caminho = tmp_path / "mapa.yaml"
        caminho.write_text(
            'mapa:\n  "E-mail do Cliente": email\n  "Nome": nome\nobrigatorios: [nome, email]\n',
            encoding="utf-8",
        )
        mapping = load_mapping_file(caminho)

        assert dict(mapping.pairs) == {"E-mail do Cliente": "email", "Nome": "nome"}
        assert mapping.required == ("nome", "email")

    def test_arquivo_json(self, tmp_path: Path) -> None:
        caminho = tmp_path / "mapa.json"
        caminho.write_text('{"mapa": {"Nome": "nome"}}', encoding="utf-8")
        assert load_mapping_file(caminho).pairs == (("Nome", "nome"),)

    def test_arquivo_sem_mapa(self, tmp_path: Path) -> None:
        caminho = tmp_path / "mapa.yaml"
        caminho.write_text("outra: coisa", encoding="utf-8")
        with pytest.raises(ConfigError, match="mapa"):
            load_mapping_file(caminho)

    def test_arquivo_inexistente(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="nao foi possivel ler"):
            load_mapping_file(tmp_path / "sumiu.yaml")

    def test_cli_vence_o_arquivo(self, tmp_path: Path) -> None:
        caminho = tmp_path / "mapa.yaml"
        caminho.write_text('mapa:\n  "Nome": nome_antigo\n', encoding="utf-8")

        mapping = build_mapping(["Nome=nome"], caminho)
        assert dict(mapping.pairs) == {"Nome": "nome"}

    def test_obrigatorios_do_arquivo_e_da_cli_se_somam(self, tmp_path: Path) -> None:
        caminho = tmp_path / "mapa.yaml"
        caminho.write_text('mapa:\n  "Nome": nome\nobrigatorios: [nome]\n', encoding="utf-8")

        mapping = build_mapping(["E-mail=email"], caminho, ["email"])
        assert mapping.required == ("nome", "email")


# ============================================================
# Validacao
# ============================================================


class TestValidacao:
    def test_mapeamento_aplicavel_nao_tem_problema(self) -> None:
        mapping = FieldMapping(pairs=(("Nome", "nome"),), required=("nome",))
        assert validate_mapping(mapping, ["Nome", "Idade"]) == []

    def test_coluna_inexistente(self) -> None:
        mapping = FieldMapping(pairs=(("Fantasma", "nome"),))
        (problema,) = validate_mapping(mapping, ["Nome"])
        assert problema.code == "coluna_inexistente"
        assert "Fantasma" in problema.message

    def test_dois_mapeamentos_para_o_mesmo_campo(self) -> None:
        mapping = FieldMapping(pairs=(("Nome", "nome"), ("Apelido", "nome")))
        problemas = validate_mapping(mapping, ["Nome", "Apelido"])
        assert [p.code for p in problemas] == ["campo_repetido"]

    def test_obrigatorio_sem_origem(self) -> None:
        mapping = FieldMapping(pairs=(("Nome", "nome"),), required=("email",))
        (problema,) = validate_mapping(mapping, ["Nome"])
        assert problema.code == "obrigatorio_sem_origem"

    def test_obrigatorio_atendido_por_coluna_nao_mapeada(self) -> None:
        """Com --enviar-nao-mapeadas, a coluna homonima serve de origem."""
        mapping = FieldMapping(pairs=(("Nome", "nome"),), required=("email",), keep_unmapped=True)
        assert validate_mapping(mapping, ["Nome", "email"]) == []


# ============================================================
# Aplicacao
# ============================================================


class TestAplicacao:
    def test_renomeia_apenas_o_que_foi_mapeado(self) -> None:
        mapping = FieldMapping(pairs=(("E-mail", "email"),))
        linhas = [{"Nome": "Ana", "E-mail": "ana@x.com"}]

        (mapeada,) = apply_mapping(linhas, mapping)
        assert mapeada.payload == {"email": "ana@x.com"}

    def test_colunas_nao_mapeadas_podem_ir_junto(self) -> None:
        mapping = FieldMapping(pairs=(("E-mail", "email"),), keep_unmapped=True)
        linhas = [{"Nome": "Ana", "E-mail": "ana@x.com"}]

        (mapeada,) = apply_mapping(linhas, mapping)
        assert mapeada.payload == {"Nome": "Ana", "email": "ana@x.com"}

    def test_sem_mapeamento_o_payload_e_a_linha(self) -> None:
        (mapeada,) = apply_mapping([{"Nome": "Ana"}], FieldMapping())
        assert mapeada.payload == {"Nome": "Ana"}

    def test_metadado_do_autotarefas_nunca_vai_no_payload(self) -> None:
        linhas = [{"Nome": "Ana", "_motivo": "falhou antes"}]
        (mapeada,) = apply_mapping(linhas, FieldMapping())
        assert "_motivo" not in mapeada.payload

    def test_linha_com_obrigatorio_vazio_e_rejeitada(self) -> None:
        mapping = FieldMapping(pairs=(("E-mail", "email"),), required=("email",))
        linhas = [{"E-mail": ""}, {"E-mail": "ana@x.com"}]

        rejeitada, aceita = apply_mapping(linhas, mapping)
        assert rejeitada.accepted is False
        assert "email" in rejeitada.rejected_reason
        assert aceita.accepted is True

    def test_numero_de_linha_e_fisico(self) -> None:
        mapeadas = apply_mapping([{"a": "1"}, {"a": "2"}], FieldMapping())
        assert [m.line for m in mapeadas] == [2, 3]

    def test_previa_mostra_so_os_aceitos(self) -> None:
        mapping = FieldMapping(pairs=(("E-mail", "email"),), required=("email",))
        mapeadas = apply_mapping([{"E-mail": ""}, {"E-mail": "ana@x.com"}], mapping)
        assert preview_payloads(mapeadas) == [{"email": "ana@x.com"}]


# ============================================================
# Tres estruturas (exigencia da ficha)
# ============================================================


@pytest.fixture
def mock_post(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Captura os payloads enviados (responde 201 a tudo)."""
    state: dict[str, Any] = {"payloads": []}

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        state["payloads"].append(kwargs.get("json", {}))
        request = httpx.Request("POST", url)
        return httpx.Response(201, json={"id": len(state["payloads"])}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    return state


def _planilha(tmp_path: Path, nome: str, cabecalho: str, linha: str) -> Path:
    caminho = tmp_path / nome
    caminho.write_text(f"{cabecalho}\n{linha}\n", encoding="utf-8")
    return caminho


class TestTresEstruturas:
    def test_contatos(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        planilha = _planilha(
            tmp_path,
            "contatos.csv",
            "Nome Completo,E-mail do Cliente,Telefone",
            "Ana Lima,ana@x.com,(11) 90000-0001",
        )
        task = SendApiTask(
            planilha_path=planilha,
            url=URL,
            mapping=build_mapping(
                ["Nome Completo=nome", "E-mail do Cliente=email", "Telefone=telefone"],
                required=["nome", "email"],
            ),
        )
        result = task.run()

        assert result.is_success
        assert mock_post["payloads"] == [
            {"nome": "Ana Lima", "email": "ana@x.com", "telefone": "(11) 90000-0001"}
        ]

    def test_produtos(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        planilha = _planilha(
            tmp_path,
            "produtos.csv",
            "Codigo do Produto,Descricao,Preco Unitario",
            "SKU-1,Caneta azul,3.50",
        )
        task = SendApiTask(
            planilha_path=planilha,
            url=URL,
            mapping=build_mapping(
                ["Codigo do Produto=sku", "Descricao=descricao", "Preco Unitario=preco"],
                required=["sku"],
            ),
        )
        result = task.run()

        assert result.is_success
        assert mock_post["payloads"][0]["sku"] == "SKU-1"
        assert "Codigo do Produto" not in mock_post["payloads"][0]

    def test_vendas(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        planilha = _planilha(
            tmp_path,
            "vendas.csv",
            "Numero da Venda,Data,Valor Total,Vendedor",
            "V-100,01/03/2026,1500.00,Bruno",
        )
        task = SendApiTask(
            planilha_path=planilha,
            url=URL,
            mapping=build_mapping(
                ["Numero da Venda=numero", "Data=data", "Valor Total=valor"],
                required=["numero", "valor"],
            ),
        )
        result = task.run()

        assert result.is_success
        # 'Vendedor' nao foi mapeado: nao vai no payload
        assert mock_post["payloads"] == [
            {"numero": "V-100", "data": "01/03/2026", "valor": "1500.00"}
        ]


class TestIntegracaoComOEnvio:
    def test_mapeamento_invalido_nao_envia_nada(
        self, tmp_path: Path, mock_post: dict[str, Any]
    ) -> None:
        planilha = _planilha(tmp_path, "c.csv", "Nome", "Ana")
        task = SendApiTask(
            planilha_path=planilha,
            url=URL,
            mapping=build_mapping(["Fantasma=nome"]),
        )
        result = task.run()

        assert result.is_failure
        assert result.error_type == "MappingError"
        assert mock_post["payloads"] == []

    def test_linha_rejeitada_nao_vira_requisicao(
        self, tmp_path: Path, mock_post: dict[str, Any]
    ) -> None:
        planilha = tmp_path / "c.csv"
        planilha.write_text("Nome,E-mail\nAna,\nBruno,b@x.com\n", encoding="utf-8")

        task = SendApiTask(
            planilha_path=planilha,
            url=URL,
            mapping=build_mapping(["Nome=nome", "E-mail=email"], required=["email"]),
        )
        result = task.run()

        assert len(mock_post["payloads"]) == 1
        assert result.data["rejeitados"][0]["linha"] == 2
        assert result.status == "partial"

    def test_mapeamento_entra_no_relatorio(self, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        planilha = _planilha(tmp_path, "c.csv", "Nome", "Ana")
        task = SendApiTask(planilha_path=planilha, url=URL, mapping=build_mapping(["Nome=nome"]))
        result = task.run()

        assert result.data["mapeamento"]["mapa"] == {"Nome": "nome"}

    def test_dry_run_mostra_a_previa_e_nao_envia(
        self, tmp_path: Path, mock_post: dict[str, Any]
    ) -> None:
        planilha = _planilha(tmp_path, "c.csv", "Nome", "Ana")
        task = SendApiTask(
            planilha_path=planilha,
            url=URL,
            mapping=build_mapping(["Nome=nome"]),
            dry_run=True,
        )
        result = task.run()

        assert mock_post["payloads"] == []
        assert result.data["previa"] == [{"nome": "Ana"}]
