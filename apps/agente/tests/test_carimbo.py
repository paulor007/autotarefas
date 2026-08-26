"""O carimbo colado no fim do executavel (G.10.2).

Sem ele, o cliente teria que digitar o endereco do Live e um codigo de seis
caracteres numa janela: dois campos, dois jeitos de errar.

O teste que carrega o peso e `test_carimbo_corrompido_vira_vazio`. Um carimbo
truncado — download interrompido, antivirus mordendo o arquivo — nao pode virar
um endereco de servidor adivinhado. Melhor perguntar do que apontar para o lugar
errado.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.agente.agente import carimbo


@pytest.fixture
def base(tmp_path: Path) -> Path:
    """Um "executavel" qualquer: o carimbo nao olha o conteudo."""
    alvo = tmp_path / "AutoTarefas-Agente.exe"
    alvo.write_bytes(b"MZ" + b"\x00" * 5000)
    return alvo


DADOS = {"servidor": "https://live.padaria.com.br", "codigo": "S8EG-B6CY"}


class TestIdaEVolta:
    def test_grava_e_le_de_volta(self, base: Path, tmp_path: Path) -> None:
        destino = tmp_path / "carimbado.exe"

        carimbo.gravar(base, destino, DADOS)

        assert carimbo.ler(destino) == DADOS

    def test_a_base_nao_e_alterada(self, base: Path, tmp_path: Path) -> None:
        """
        E a base que serve todos os downloads seguintes.

        Carimbar por cima faria o segundo cliente receber o codigo do primeiro —
        e entrar na organizacao errada.
        """
        antes = base.read_bytes()

        carimbo.gravar(base, tmp_path / "a.exe", DADOS)
        carimbo.gravar(base, tmp_path / "b.exe", {"servidor": "https://outra", "codigo": "X"})

        assert base.read_bytes() == antes
        assert carimbo.ler(tmp_path / "a.exe") == DADOS

    def test_o_programa_continua_inteiro_antes_do_carimbo(self, base: Path, tmp_path: Path) -> None:
        """
        O carimbo e sobra no fim: o executavel de verdade fica intacto.

        Se ele mexesse no corpo, o Windows recusaria o arquivo — e a descoberta
        seria na maquina do cliente.
        """
        destino = tmp_path / "carimbado.exe"
        carimbo.gravar(base, destino, DADOS)

        assert destino.read_bytes().startswith(base.read_bytes())

    def test_carimbar_duas_vezes_vale_o_ultimo(self, base: Path, tmp_path: Path) -> None:
        """Reaproveitar um carimbado como base nao pode entregar o codigo velho."""
        primeiro = tmp_path / "primeiro.exe"
        carimbo.gravar(base, primeiro, DADOS)

        segundo = tmp_path / "segundo.exe"
        novos = {"servidor": "https://live.farmacia.com.br", "codigo": "9K2P-QW3Z"}
        carimbo.gravar(primeiro, segundo, novos)

        assert carimbo.ler(segundo) == novos


class TestFalhaFechada:
    def test_sem_carimbo_devolve_vazio(self, base: Path) -> None:
        """
        Executavel sem carimbo e o caso normal de quem compilou por conta
        propria. O assistente pergunta o endereco, e pronto.
        """
        assert carimbo.ler(base) == {}

    def test_arquivo_inexistente_devolve_vazio(self, tmp_path: Path) -> None:
        assert carimbo.ler(tmp_path / "nao-existe.exe") == {}

    def test_carimbo_corrompido_vira_vazio(self, base: Path, tmp_path: Path) -> None:
        """
        Download interrompido, antivirus mordendo o arquivo.

        Um JSON pela metade nao pode virar um endereco de servidor adivinhado:
        melhor perguntar do que apontar para o lugar errado.
        """
        destino = tmp_path / "quebrado.exe"
        destino.write_bytes(base.read_bytes() + carimbo.MARCA + b'{"servidor": "https://li')

        assert carimbo.ler(destino) == {}

    def test_carimbo_que_nao_e_objeto_vira_vazio(self, base: Path, tmp_path: Path) -> None:
        destino = tmp_path / "lista.exe"
        destino.write_bytes(base.read_bytes() + carimbo.MARCA + b'["nao", "e", "objeto"]')

        assert carimbo.ler(destino) == {}

    def test_carimbo_gigante_e_ignorado_na_leitura(self, base: Path, tmp_path: Path) -> None:
        """
        Carimbo muito maior que o previsto e sinal de que alguem enfiou outra
        coisa ali. Nao se le, e nao se usa.
        """
        enorme = json.dumps({"servidor": "x" * (carimbo.LIMITE_BYTES + 100)}).encode()
        destino = tmp_path / "enorme.exe"
        destino.write_bytes(base.read_bytes() + carimbo.MARCA + enorme)

        assert carimbo.ler(destino) == {}

    def test_carimbo_gigante_e_recusado_na_gravacao(self, base: Path, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="grande demais"):
            carimbo.gravar(base, tmp_path / "x.exe", {"a": "y" * carimbo.LIMITE_BYTES})


class TestDoProcesso:
    def test_rodando_do_codigo_nao_ha_carimbo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Quem roda do codigo-fonte tem o terminal ali do lado."""
        monkeypatch.setattr(carimbo.sys, "frozen", False, raising=False)

        assert carimbo.do_processo() == {}

    def test_congelado_le_o_proprio_arquivo(
        self, base: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        destino = tmp_path / "congelado.exe"
        carimbo.gravar(base, destino, DADOS)

        monkeypatch.setattr(carimbo.sys, "frozen", True, raising=False)
        monkeypatch.setattr(carimbo.sys, "executable", str(destino))

        assert carimbo.do_processo() == DADOS


def test_o_carimbo_nao_carrega_segredo_por_desenho(base: Path, tmp_path: Path) -> None:
    """
    O que entra e endereco e codigo temporario. Nada mais.

    Este teste nao impede alguem de acrescentar um campo — impede que o campo
    passe despercebido. Um instalador que vazasse chave ou senha seria um
    vazamento por download, e nao ha como recolher.
    """
    destino = tmp_path / "carimbado.exe"
    carimbo.gravar(base, destino, DADOS)

    lido = carimbo.ler(destino)

    assert set(lido) == {"servidor", "codigo"}
