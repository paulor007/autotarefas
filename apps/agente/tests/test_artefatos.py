"""Pacotes resolvidos pelo nome (G.7.2).

O Live sabe o **nome** de cada pacote — veio na ficha do artefato. O que ele
nao sabe, e nao deve saber, e onde o arquivo esta: o caminho local revela a
estrutura de pastas da empresa.

O teste que carrega o peso e `test_nome_com_travessia_e_recusado`. Se o nome
virasse caminho, o servidor escolheria qual arquivo do disco o Agente abre — e
a guarda de pastas autorizadas teria sido contornada pela porta dos fundos.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.agente.agente import artefatos
from apps.agente.agente.config import Configuracao


@pytest.fixture
def maquina(tmp_path: Path) -> tuple[Configuracao, Path]:
    """Uma maquina com pasta autorizada e a pasta de pacotes ao lado dela."""
    raiz = tmp_path / "cliente" / "dados"
    raiz.mkdir(parents=True)
    pacotes = tmp_path / "cliente" / "backups"
    pacotes.mkdir()
    return Configuracao(servidor="https://x", dispositivo_id="d").com_raiz(raiz), pacotes


def _pacote(pasta: Path, nome: str, conteudo: bytes = b"pacote") -> Path:
    alvo = pasta / nome
    alvo.write_bytes(conteudo)
    return alvo


class TestNome:
    @pytest.mark.parametrize(
        "nome",
        [
            "backup_2026-08-25_0200.zip",
            "backup_2020-01-01_2359.zip",
        ],
    )
    def test_nome_do_produto_e_aceito(self, nome: str) -> None:
        assert artefatos.nome_valido(nome) is True

    @pytest.mark.parametrize(
        "nome",
        [
            "",
            "qualquer.zip",
            "backup_2026-13-40_9999.zip",
            "backup_2026-02-31_0200.zip",
        ],
    )
    def test_fora_do_formato_e_recusado(self, nome: str) -> None:
        assert artefatos.nome_valido(nome) is False

    @pytest.mark.parametrize(
        "nome",
        [
            "../backup_2026-08-25_0200.zip",
            "..\\..\\Windows\\backup_2026-08-25_0200.zip",
            "sub/backup_2026-08-25_0200.zip",
            "C:\\Windows\\backup_2026-08-25_0200.zip",
        ],
    )
    def test_nome_com_travessia_e_recusado(self, nome: str) -> None:
        """
        Nome com separador ou `..` nao e nome: e caminho disfarcado.

        Aceitar faria o servidor escolher qual arquivo do disco o Agente abre,
        contornando a guarda de pastas autorizadas pela porta dos fundos.
        """
        assert artefatos.nome_valido(nome) is False


class TestListagem:
    def test_lista_do_mais_novo_para_o_mais_velho(self, maquina: tuple[Configuracao, Path]) -> None:
        configuracao, pacotes = maquina
        _pacote(pacotes, "backup_2026-08-20_0200.zip")
        _pacote(pacotes, "backup_2026-08-25_0200.zip")

        encontrados = artefatos.listar(configuracao)

        assert [item.nome for item in encontrados] == [
            "backup_2026-08-25_0200.zip",
            "backup_2026-08-20_0200.zip",
        ]

    def test_arquivo_alheio_na_pasta_nao_vira_pacote(
        self, maquina: tuple[Configuracao, Path]
    ) -> None:
        """
        Um ZIP que a pessoa guardou ali nao e nosso.

        Tratar como pacote seria oferece-lo para restaurar — e, na retencao,
        seria o primeiro passo para apaga-lo.
        """
        configuracao, pacotes = maquina
        _pacote(pacotes, "backup_2026-08-25_0200.zip")
        _pacote(pacotes, "fotos-do-casamento.zip")

        assert [item.nome for item in artefatos.listar(configuracao)] == [
            "backup_2026-08-25_0200.zip"
        ]

    def test_o_caminho_local_nao_entra_no_que_sobe(
        self, maquina: tuple[Configuracao, Path]
    ) -> None:
        """
        A ficha que vai para o servidor tem nome, tamanho e data. So.

        O caminho revela a estrutura de pastas da empresa, e mandar isso seria
        entregar de graca um mapa que ninguem pediu.
        """
        configuracao, pacotes = maquina
        _pacote(pacotes, "backup_2026-08-25_0200.zip")

        ficha = artefatos.listar(configuracao)[0].como_dicionario()

        assert set(ficha) == {"nome", "tamanho_bytes", "criado_em"}
        assert str(pacotes) not in str(ficha)

    def test_sem_pasta_autorizada_nao_ha_pacote(self) -> None:
        assert artefatos.listar(Configuracao()) == []

    def test_pasta_de_pacotes_ainda_nao_criada_e_lista_vazia(self, tmp_path: Path) -> None:
        """Maquina pareada que ainda nao rodou backup nenhum. Nao e erro."""
        raiz = tmp_path / "cliente" / "dados"
        raiz.mkdir(parents=True)
        configuracao = Configuracao(servidor="https://x", dispositivo_id="d").com_raiz(raiz)

        assert artefatos.listar(configuracao) == []


class TestResolucao:
    def test_acha_pelo_nome(self, maquina: tuple[Configuracao, Path]) -> None:
        configuracao, pacotes = maquina
        esperado = _pacote(pacotes, "backup_2026-08-25_0200.zip")

        assert artefatos.achar(configuracao, "backup_2026-08-25_0200.zip") == esperado

    def test_nome_invalido_recusa_sem_tocar_no_disco(
        self, maquina: tuple[Configuracao, Path]
    ) -> None:
        configuracao, pacotes = maquina
        _pacote(pacotes, "backup_2026-08-25_0200.zip")

        with pytest.raises(artefatos.PacoteDesconhecido, match="nao e um nome de pacote"):
            artefatos.achar(configuracao, "../backup_2026-08-25_0200.zip")

    def test_pacote_inexistente_recusa(self, maquina: tuple[Configuracao, Path]) -> None:
        configuracao, _ = maquina

        with pytest.raises(artefatos.PacoteDesconhecido, match="nao ha pacote chamado"):
            artefatos.achar(configuracao, "backup_2026-08-25_0200.zip")

    def test_a_recusa_nao_conta_onde_se_procurou(self, maquina: tuple[Configuracao, Path]) -> None:
        """
        A mensagem de erro tambem e uma superficie.

        Dizer "nao encontrei em C:\\Users\\fulano\\backups" entregaria o caminho
        que o resto do desenho toma o cuidado de nao mandar.
        """
        configuracao, pacotes = maquina

        with pytest.raises(artefatos.PacoteDesconhecido) as erro:
            artefatos.achar(configuracao, "backup_2026-08-25_0200.zip")

        assert str(pacotes) not in str(erro.value)

    def test_sem_pasta_autorizada_diz_o_motivo(self) -> None:
        with pytest.raises(artefatos.PacoteDesconhecido, match="nenhuma pasta autorizada"):
            artefatos.achar(Configuracao(), "backup_2026-08-25_0200.zip")
