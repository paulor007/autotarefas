"""
Testes das correcoes por regras confirmadas (RF-PLA-010).

A regra de negocio que estes testes protegem: **nenhuma correcao fora de
regra confirmada** e **nenhuma decisao incerta em silencio** — o que nao
casa com a regra vai para revisao com o valor original intacto.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autotarefas.core.exceptions import ConfigError
from autotarefas.tasks.corrections import CorrectionRule, apply_rules, load_rules

FIXTURES = Path(__file__).parent.parent / "fixtures" / "correcoes"


def _linhas() -> list[dict[str, str]]:
    return [
        {"uf": "Sao Paulo", "situacao": "ATIVO", "origem": ""},
        {"uf": "rio de janeiro", "situacao": "inativo", "origem": ""},
        {"uf": "SP", "situacao": "Ativo", "origem": "sistema"},
        {"uf": "Sao Jorge", "situacao": "Pendente", "origem": ""},
    ]


DE_PARA = CorrectionRule(
    column="uf",
    kind="de_para",
    mapping={"sao paulo": "SP", "rio de janeiro": "RJ"},
)
PADRONIZAR = CorrectionRule(column="situacao", kind="padronizar", allowed=("Ativo", "Inativo"))
PREENCHER = CorrectionRule(column="origem", kind="preencher", value="planilha")


class TestDePara:
    def test_troca_o_valor_declarado(self) -> None:
        corrigidas, resultado = apply_rules(_linhas(), [DE_PARA])
        assert corrigidas[0]["uf"] == "SP"
        assert corrigidas[1]["uf"] == "RJ"
        assert resultado.counts["regra_confirmada"] == 2

    def test_ignora_acento_e_caixa_na_origem(self) -> None:
        regra = CorrectionRule(column="uf", kind="de_para", mapping={"sao paulo": "SP"})
        corrigidas, _ = apply_rules([{"uf": "SÃO  PAULO"}], [regra])
        assert corrigidas[0]["uf"] == "SP"

    def test_valor_que_ja_e_o_destino_nao_vira_revisao(self) -> None:
        """'SP' num de/para que produz 'SP' esta correto — nao ha o que conferir."""
        _, resultado = apply_rules(_linhas(), [DE_PARA])
        assert [item.before for item in resultado.review] == ["Sao Jorge"]

    def test_valor_desconhecido_vai_para_revisao_sem_alterar(self) -> None:
        corrigidas, resultado = apply_rules(_linhas(), [DE_PARA])
        assert corrigidas[3]["uf"] == "Sao Jorge"
        (item,) = resultado.review
        assert (item.column, item.row) == ("uf", 5)

    def test_fora_da_regra_manter_nao_gera_revisao(self) -> None:
        regra = CorrectionRule(
            column="uf", kind="de_para", mapping={"sao paulo": "SP"}, out_of_rule="manter"
        )
        _, resultado = apply_rules(_linhas(), [regra])
        assert resultado.review == ()


class TestPadronizar:
    def test_encaixa_na_lista_declarada(self) -> None:
        corrigidas, _ = apply_rules(_linhas(), [PADRONIZAR])
        assert corrigidas[0]["situacao"] == "Ativo"
        assert corrigidas[1]["situacao"] == "Inativo"

    def test_valor_fora_da_lista_vai_para_revisao(self) -> None:
        _, resultado = apply_rules(_linhas(), [PADRONIZAR])
        assert [i.before for i in resultado.review] == ["Pendente"]

    def test_valor_ja_correto_nao_gera_mudanca(self) -> None:
        _, resultado = apply_rules([{"situacao": "Ativo"}], [PADRONIZAR])
        assert resultado.changes == ()


class TestPreencher:
    def test_preenche_apenas_vazios(self) -> None:
        corrigidas, resultado = apply_rules(_linhas(), [PREENCHER])
        assert corrigidas[0]["origem"] == "planilha"
        assert corrigidas[2]["origem"] == "sistema"  # ja tinha valor
        assert resultado.counts["regra_confirmada"] == 3


class TestApplyRules:
    def test_linhas_de_entrada_nao_sao_alteradas(self) -> None:
        linhas = _linhas()
        apply_rules(linhas, [DE_PARA, PADRONIZAR, PREENCHER])
        assert linhas[0] == {"uf": "Sao Paulo", "situacao": "ATIVO", "origem": ""}

    def test_numero_de_linha_e_fisico(self) -> None:
        _, resultado = apply_rules(_linhas(), [DE_PARA], first_data_row=10)
        assert resultado.changes[0].row == 10

    def test_coluna_inexistente_vira_aviso(self) -> None:
        _, resultado = apply_rules([{"uf": "SP"}], [PREENCHER])
        assert resultado.changes == ()
        assert "origem" in resultado.warnings[0]

    def test_contadores_separam_as_naturezas(self) -> None:
        _, resultado = apply_rules(_linhas(), [DE_PARA, PADRONIZAR, PREENCHER])
        contagem = resultado.counts
        assert contagem["regra_confirmada"] == 7
        assert contagem["revisao"] == 2
        assert contagem["automatico_seguro"] == 0


class TestCarregarRegras:
    def test_le_o_arquivo_de_fixture(self) -> None:
        regras = load_rules(FIXTURES / "regras.yaml")
        assert [r.column for r in regras] == ["uf", "situacao", "origem"]
        assert regras[0].kind == "de_para"
        assert regras[1].allowed == ("Ativo", "Inativo")
        assert regras[2].value == "planilha"

    def test_sem_chave_correcoes(self, tmp_path: Path) -> None:
        caminho = tmp_path / "r.yaml"
        caminho.write_text("outra_coisa: []", encoding="utf-8")
        with pytest.raises(ConfigError, match="correcoes"):
            load_rules(caminho)

    def test_tipo_desconhecido(self, tmp_path: Path) -> None:
        caminho = tmp_path / "r.yaml"
        caminho.write_text("correcoes:\n  - coluna: uf\n    tipo: inventar\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="tipo"):
            load_rules(caminho)

    def test_de_para_sem_mapa(self, tmp_path: Path) -> None:
        caminho = tmp_path / "r.yaml"
        caminho.write_text("correcoes:\n  - coluna: uf\n    tipo: de_para\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="mapa"):
            load_rules(caminho)

    def test_padronizar_sem_valores(self, tmp_path: Path) -> None:
        caminho = tmp_path / "r.yaml"
        caminho.write_text("correcoes:\n  - coluna: s\n    tipo: padronizar\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="valores"):
            load_rules(caminho)

    def test_preencher_sem_valor(self, tmp_path: Path) -> None:
        caminho = tmp_path / "r.yaml"
        caminho.write_text("correcoes:\n  - coluna: o\n    tipo: preencher\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="valor"):
            load_rules(caminho)

    def test_fora_da_regra_invalido(self, tmp_path: Path) -> None:
        caminho = tmp_path / "r.yaml"
        caminho.write_text(
            "correcoes:\n  - coluna: o\n    tipo: preencher\n    valor: x\n"
            "    fora_da_regra: apagar\n",
            encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="fora_da_regra"):
            load_rules(caminho)

    def test_arquivo_ilegivel(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="nao foi possivel ler"):
            load_rules(tmp_path / "nao_existe.yaml")
