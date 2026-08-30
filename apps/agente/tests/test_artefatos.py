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

        assert set(ficha) == {
            "nome",
            "tamanho_bytes",
            "criado_em",
            # De qual politica o pacote e. Nao e caminho: e o identificador
            # que o servidor ja conhece, porque foi ele que o criou.
            "politica_id",
            "politica_nome",
        }
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


class TestCorrente:
    """
    Um pacote incremental nao se sustenta sozinho (G.7.2).

    Quem monta a corrente e a maquina: a tela conhece nomes, e so aqui se sabe
    quais deles ainda existem no disco. Sem isto, restaurar o pacote de hoje
    devolveria uma pasta pela metade — com cara de restauracao concluida.
    """

    @staticmethod
    def _dois_pacotes(maquina: tuple[Configuracao, Path]) -> tuple[Path, Path]:
        from autotarefas.tasks.backup import BackupTask
        from autotarefas.tasks.catalogo import NOME, Catalogo

        configuracao, pacotes = maquina
        origem = Path(configuracao.raizes[0])
        (origem / "contrato.txt").write_text("contrato", encoding="utf-8")

        catalogo = Catalogo(pacotes / NOME)
        primeiro = pacotes / "backup_2026-08-24_0200.zip"
        BackupTask(sources=[origem], destination=primeiro, catalogo=catalogo).run()

        (origem / "novo.txt").write_text("novo", encoding="utf-8")
        segundo = pacotes / "backup_2026-08-25_0200.zip"
        BackupTask(sources=[origem], destination=segundo, catalogo=catalogo).run()
        return primeiro, segundo

    def test_o_incremental_aponta_para_o_anterior(self, maquina: tuple[Configuracao, Path]) -> None:
        primeiro, segundo = self._dois_pacotes(maquina)

        assert artefatos.corrente(segundo) == [primeiro]

    def test_pacote_completo_nao_depende_de_ninguem(
        self, maquina: tuple[Configuracao, Path]
    ) -> None:
        primeiro, _ = self._dois_pacotes(maquina)

        assert artefatos.corrente(primeiro) == []

    def test_anterior_apagado_some_da_corrente_sem_derrubar(
        self, maquina: tuple[Configuracao, Path]
    ) -> None:
        """
        Relatar o que faltou e melhor do que recusar tudo.

        Quem apagou um pacote antigo ainda pode querer de volta o que existe.
        """
        primeiro, segundo = self._dois_pacotes(maquina)
        primeiro.unlink()

        assert artefatos.corrente(segundo) == []


class TestPacotesDentroDaPastaDaPolitica:
    """
    Os pacotes deixaram de morar num monte so, e a restauracao tinha que
    acompanhar.

    Quando cada politica passou a ter a propria pasta, a varredura que so
    olhava a raiz parou de achar qualquer coisa: a tela de restauracao ficaria
    vazia com o disco cheio de backup. Pior tipo de defeito — o produto
    afirmando que nao ha o que restaurar.
    """

    def _na_politica(self, pacotes: Path, politica_id: str, nome: str) -> Path:
        from apps.agente.agente import pastas as mod_pastas

        pasta = mod_pastas.pasta_da_politica(pacotes, politica_id)
        pasta.mkdir(parents=True, exist_ok=True)
        mod_pastas.marcar(pasta, politica_id=politica_id, nome=f"Politica {politica_id}")
        return _pacote(pasta, nome)

    def test_a_listagem_acha_os_pacotes_de_cada_politica(
        self, maquina: tuple[Configuracao, Path]
    ) -> None:
        configuracao, pacotes = maquina
        self._na_politica(pacotes, "p1", "backup_2026-08-25_0200.zip")
        self._na_politica(pacotes, "p2", "backup_2026-08-26_0300.zip")

        achados = artefatos.listar(configuracao)

        assert {item.nome for item in achados} == {
            "backup_2026-08-25_0200.zip",
            "backup_2026-08-26_0300.zip",
        }

    def test_cada_pacote_diz_de_quem_e(self, maquina: tuple[Configuracao, Path]) -> None:
        """
        Sem o dono, a tela mostra uma pilha de pacotes com a mesma cara e quem
        restaura escolhe pela data — que e justamente o que menos distingue um
        "diario da contabilidade" de um "mensal do juridico".
        """
        configuracao, pacotes = maquina
        self._na_politica(pacotes, "p1", "backup_2026-08-25_0200.zip")

        achado = artefatos.listar(configuracao)[0]

        assert achado.politica_id == "p1"
        assert achado.politica_nome == "Politica p1"

    def test_o_avulso_da_raiz_continua_aparecendo_e_sem_dono(
        self, maquina: tuple[Configuracao, Path]
    ) -> None:
        """
        Sumir com backup que existe seria pior do que a bagunca que havia.

        Os pacotes gerados antes de existir pasta por politica estao na raiz e
        nao tem como ser atribuidos agora — era exatamente essa informacao que
        faltava. Eles ficam, sem dono, e nenhuma retencao de politica os
        alcanca.
        """
        configuracao, pacotes = maquina
        _pacote(pacotes, "backup_2026-08-20_0100.zip")
        self._na_politica(pacotes, "p1", "backup_2026-08-25_0200.zip")

        achados = artefatos.listar(configuracao)
        avulso = next(item for item in achados if item.nome == "backup_2026-08-20_0100.zip")

        assert len(achados) == 2
        assert avulso.politica_id == ""

    def test_a_lista_e_uma_linha_do_tempo_e_nao_um_agrupamento(
        self, maquina: tuple[Configuracao, Path]
    ) -> None:
        configuracao, pacotes = maquina
        self._na_politica(pacotes, "p1", "backup_2026-08-20_0200.zip")
        self._na_politica(pacotes, "p2", "backup_2026-08-26_0300.zip")
        _pacote(pacotes, "backup_2026-08-23_0100.zip")

        nomes = [item.nome for item in artefatos.listar(configuracao)]

        assert nomes == [
            "backup_2026-08-26_0300.zip",
            "backup_2026-08-23_0100.zip",
            "backup_2026-08-20_0200.zip",
        ]

    def test_achar_encontra_o_pacote_dentro_da_pasta_da_politica(
        self, maquina: tuple[Configuracao, Path]
    ) -> None:
        configuracao, pacotes = maquina
        esperado = self._na_politica(pacotes, "p1", "backup_2026-08-25_0200.zip")

        assert artefatos.achar(configuracao, "backup_2026-08-25_0200.zip") == esperado

    def test_travessia_continua_recusada_com_as_pastas_novas(
        self, maquina: tuple[Configuracao, Path]
    ) -> None:
        """
        Mais pastas varridas nao pode virar mais superficie de ataque.

        O nome e conferido antes de virar caminho, e continua sendo.
        """
        configuracao, _ = maquina

        with pytest.raises(artefatos.PacoteDesconhecido):
            artefatos.achar(configuracao, "../../backup_2026-08-25_0200.zip")
