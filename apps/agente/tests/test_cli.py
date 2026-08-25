"""Testes da linha de comando do Agente.

Ela nao e o caminho do cliente — o instalador guiado (G.8) chama estes mesmos
comandos por baixo. O que se protege aqui e o que o instalador vai mostrar: o
estado tem que dizer a verdade, inclusive quando a verdade e "este dispositivo
nao copiaria nada".
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from apps.agente.agente.__main__ import cli
from apps.agente.agente.config import Configuracao, Local


def _rodar(argumentos: list[str]) -> tuple[int, str]:
    resultado = CliRunner().invoke(cli, argumentos)
    return resultado.exit_code, resultado.output


class TestEstado:
    def test_sem_pareamento_diz_que_nao_esta_pareado(self, tmp_path: Path) -> None:
        codigo, saida = _rodar(["estado", "--pasta-de-configuracao", str(tmp_path)])

        assert codigo == 0
        assert "(nao pareado)" in saida
        assert "sem identidade" in saida

    def test_avisa_quando_nao_ha_pasta_autorizada(self, tmp_path: Path) -> None:
        """
        Agente pareado sem pasta autorizada nao copia nada.

        E facil confundir isso com "esta funcionando": o estado precisa dizer.
        """
        Local(pasta=tmp_path).gravar(
            Configuracao(servidor="https://live", dispositivo_id="d", nome="PC")
        )

        _, saida = _rodar(["estado", "--pasta-de-configuracao", str(tmp_path)])

        assert "NENHUMA" in saida
        assert "nao copiaria nada" in saida

    def test_lista_as_pastas_autorizadas(self, tmp_path: Path) -> None:
        pasta = tmp_path / "dados"
        pasta.mkdir()
        Local(pasta=tmp_path).gravar(
            Configuracao(servidor="https://live", dispositivo_id="d").com_raiz(pasta)
        )

        _, saida = _rodar(["estado", "--pasta-de-configuracao", str(tmp_path)])

        assert str(pasta.resolve()) in saida

    def test_diz_onde_a_chave_privada_esta(self, tmp_path: Path) -> None:
        """
        Arquivo local e pior que o cofre do sistema, e isso aparece.

        Chamar os dois de "protegido" faria alguem deixar o pior em producao.
        """
        _, saida = _rodar(["estado", "--pasta-de-configuracao", str(tmp_path)])

        assert "Chave privada:" in saida


class TestParear:
    def test_servidor_inalcancavel_falha_com_saida_1(self, tmp_path: Path) -> None:
        """Falhar em silencio deixaria o instalador declarar sucesso a toa."""
        codigo, _ = _rodar(
            [
                "parear",
                "--servidor",
                "http://127.0.0.1:9",
                "--codigo",
                "ABCD-EFGH",
                "--pasta-de-configuracao",
                str(tmp_path),
            ]
        )

        assert codigo == 1
        assert Local(pasta=tmp_path).carregar().pareado is False
