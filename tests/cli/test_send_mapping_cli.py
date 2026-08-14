"""
Testes do mapeamento de colunas no comando `send api` (RF-INT-005).

Aqui a task e a de verdade (so o `httpx.post` e mockado): o que se prova e
o caminho completo — CLI le o de/para, valida contra as colunas reais,
mostra a previa e so entao envia.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from click.testing import CliRunner

from autotarefas.cli.commands.send.api import api_command
from autotarefas.cli.context import CLIContext

URL = "http://localhost:5555/api/contatos"


@pytest.fixture
def mock_post(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"payloads": []}

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        state["payloads"].append(kwargs.get("json", {}))
        request = httpx.Request("POST", url)
        return httpx.Response(201, json={"id": len(state["payloads"])}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    return state


@pytest.fixture
def planilha(tmp_path: Path) -> Path:
    caminho = tmp_path / "contatos.csv"
    caminho.write_text(
        "Nome Completo,E-mail do Cliente\nAna Lima,ana@x.com\nBruno Sa,\n",
        encoding="utf-8",
    )
    return caminho


def _run(planilha: Path, *extra: str, dry_run: bool = False):
    return CliRunner().invoke(
        api_command,
        ["-p", str(planilha), "-u", URL, *extra],
        obj=CLIContext(dry_run=dry_run),
    )


class TestMapeamentoNaCLI:
    def test_map_renomeia_as_colunas(self, planilha: Path, mock_post: dict[str, Any]) -> None:
        result = _run(planilha, "--map", "Nome Completo=nome", "--map", "E-mail do Cliente=email")
        assert result.exit_code == 0
        assert mock_post["payloads"][0] == {"nome": "Ana Lima", "email": "ana@x.com"}

    def test_map_file(self, planilha: Path, tmp_path: Path, mock_post: dict[str, Any]) -> None:
        mapa = tmp_path / "mapa.yaml"
        mapa.write_text(
            'mapa:\n  "Nome Completo": nome\n  "E-mail do Cliente": email\nobrigatorios: [email]\n',
            encoding="utf-8",
        )
        result = _run(planilha, "--map-file", str(mapa))

        assert result.exit_code in (0, 1)  # 1 linha rejeitada -> parcial
        assert mock_post["payloads"] == [{"nome": "Ana Lima", "email": "ana@x.com"}]
        assert "rejeitada" in result.output

    def test_obrigatorio_rejeita_linha_incompleta(
        self, planilha: Path, mock_post: dict[str, Any]
    ) -> None:
        result = _run(
            planilha,
            "--map",
            "Nome Completo=nome",
            "--map",
            "E-mail do Cliente=email",
            "--obrigatorio",
            "email",
        )
        assert len(mock_post["payloads"]) == 1
        assert "linha 3" in result.output

    def test_coluna_inexistente_e_erro_de_uso(
        self, planilha: Path, mock_post: dict[str, Any]
    ) -> None:
        result = _run(planilha, "--map", "Fantasma=nome")
        assert result.exit_code == 2
        assert mock_post["payloads"] == []
        assert "nao tem a coluna" in result.output

    def test_dois_mapeamentos_para_o_mesmo_campo(
        self, planilha: Path, mock_post: dict[str, Any]
    ) -> None:
        result = _run(planilha, "--map", "Nome Completo=nome", "--map", "E-mail do Cliente=nome")
        assert result.exit_code == 2
        assert mock_post["payloads"] == []

    def test_sintaxe_invalida_do_map(self, planilha: Path) -> None:
        result = _run(planilha, "--map", "sem_igual")
        assert result.exit_code == 2
        assert "Mapeamento invalido" in result.output

    def test_previa_mostra_o_payload_mapeado(self, planilha: Path) -> None:
        result = _run(planilha, "--map", "Nome Completo=nome", "--previa", "2", dry_run=True)
        assert result.exit_code == 0
        assert "Previa do payload" in result.output
        assert "'nome': 'Ana Lima'" in result.output

    def test_dry_run_nao_envia(self, planilha: Path, mock_post: dict[str, Any]) -> None:
        _run(planilha, "--map", "Nome Completo=nome", dry_run=True)
        assert mock_post["payloads"] == []

    def test_enviar_nao_mapeadas(self, planilha: Path, mock_post: dict[str, Any]) -> None:
        _run(planilha, "--map", "Nome Completo=nome", "--enviar-nao-mapeadas")
        assert mock_post["payloads"][0] == {
            "nome": "Ana Lima",
            "E-mail do Cliente": "ana@x.com",
        }

    def test_sem_map_mantem_o_comportamento_antigo(
        self, planilha: Path, mock_post: dict[str, Any]
    ) -> None:
        _run(planilha)
        assert mock_post["payloads"][0] == {
            "Nome Completo": "Ana Lima",
            "E-mail do Cliente": "ana@x.com",
        }

    def test_planilha_de_entrada_nao_e_alterada(
        self, planilha: Path, mock_post: dict[str, Any]
    ) -> None:
        antes = planilha.read_bytes()
        _run(planilha, "--map", "Nome Completo=nome")
        assert planilha.read_bytes() == antes
