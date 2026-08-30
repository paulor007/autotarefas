"""Da politica ao pacote, na maquina (02.E).

O que se prova aqui e a traducao: uma politica configurada na tela vira um
backup de verdade, com destino e retencao aplicados na ordem certa.

A ordem importa e tem teste: a retencao roda DEPOIS do backup e so quando ele
deu certo. Rodar antes apagaria a copia mais antiga para abrir espaco de um
pacote que talvez nem seja criado — trocar uma copia boa por nenhuma.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from apps.agente.agente import backup as backup_agente
from apps.agente.agente import raizes, retencao
from apps.agente.agente.config import Configuracao, Local
from autotarefas.tasks.politica import (
    Destino,
    Politica,
    Retencao,
    TipoDeDestino,
)


@pytest.fixture
def autorizada(tmp_path: Path) -> tuple[Configuracao, Path]:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    (pasta / "contrato.txt").write_text("contrato", encoding="utf-8")
    return raizes.autorizar(Local(pasta=tmp_path / "cfg"), pasta), pasta


class TestTraducao:
    def test_politica_vira_pacote(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        configuracao, pasta = autorizada
        politica = Politica(
            origens=[str(pasta)],
            destino=Destino(tipo=TipoDeDestino.LOCAL, caminho=str(tmp_path / "copia")),
        )

        ficha = asyncio.run(backup_agente.executar_politica(politica, configuracao))

        assert ficha["ok"] is True
        assert ficha["arquivos"] == 1
        assert ficha["entregas"][0]["conferido_no_destino"] is True

    def test_politica_com_vss_sem_elevacao_recusa(
        self, autorizada: tuple[Configuracao, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Recusa com motivo, e nao pacote sem o arquivo aberto."""
        from apps.agente.agente import vss

        configuracao, pasta = autorizada
        monkeypatch.setattr(vss, "elevado", lambda: False)
        monkeypatch.setattr(vss, "no_windows", lambda: True)

        politica = Politica(origens=[str(pasta)], usar_vss=True)

        with pytest.raises(backup_agente.BackupRecusado, match="administrador"):
            asyncio.run(backup_agente.executar_politica(politica, configuracao))

    def test_destino_nuvem_faz_o_pacote_e_declara_a_entrega_pendente(
        self, autorizada: tuple[Configuracao, Path]
    ) -> None:
        """
        A falha mais cara que este produto sabe cometer era silenciosa.

        `nuvem` nao tinha ramo aqui: a politica caia fora do `if`, o backup
        rodava, o pacote ficava no proprio computador e a ficha voltava com
        `ok: True`. Do lado do painel isso virava **Protegido** — porque nuvem
        conta como destino de verdade — para uma copia que nunca saiu do lugar.

        A correcao nao e recusar: e separar backup de envio. O agendamento
        roda offline de proposito, e o Agente nao grava chave de nuvem em
        disco — mas o que precisa de rede e o ENVIO, e nao o backup. Entao o
        pacote e feito aqui, e a ficha declara a entrega pendente. O servidor
        pede o envio assim que houver canal, com a credencial chegando na hora.

        A janela entre uma coisa e outra e verdade, e o painel a mostra como
        tal: "ainda nao subiu", e nao "Protegido".
        """
        configuracao, pasta = autorizada
        politica = Politica(origens=[str(pasta)], destino=Destino(tipo=TipoDeDestino.NUVEM))

        ficha = asyncio.run(backup_agente.executar_politica(politica, configuracao))

        assert ficha["ok"] is True
        assert ficha["nuvem_pendente"] is True
        # A entrega LOCAL nao aconteceu, e nao deve ter acontecido: destino
        # nuvem nao tem caminho em disco nenhum.
        assert ficha["entregas"] == []

    def test_destino_em_disco_nao_nasce_pendente_de_nuvem(
        self, autorizada: tuple[Configuracao, Path]
    ) -> None:
        """
        Guarda contra o marcador virar "sempre pendente".

        Disco externo e pasta de rede entregam DENTRO da execucao, e conferem
        a copia ali mesmo. Marcar pendencia de nuvem neles deixaria o painel
        em "parcial" para sempre, sem nada a resolver.
        """
        configuracao, pasta = autorizada
        politica = Politica(origens=[str(pasta)], destino=Destino(tipo=TipoDeDestino.NENHUM))

        ficha = asyncio.run(backup_agente.executar_politica(politica, configuracao))

        assert ficha["nuvem_pendente"] is False


class TestRetencaoNaPolitica:
    def test_retencao_apaga_os_antigos_depois_do_backup(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        configuracao, pasta = autorizada
        destino = tmp_path / "pacotes"
        destino.mkdir()
        base = datetime(2020, 1, 10, 2, 0)
        for i in range(5):
            quando = base - timedelta(days=i)
            (destino / f"backup_{quando:%Y-%m-%d_%H%M}.zip").write_bytes(b"antigo")

        politica = Politica(
            origens=[str(pasta)],
            retencao=Retencao(diarias=1, semanais=0, mensais=0),
        )
        # Sem destino externo, o pacote vai para a pasta padrao; o teste
        # aponta a retencao para a pasta com o historico antigo.
        ficha = asyncio.run(backup_agente.executar_politica(politica, configuracao))
        relatorio = retencao.aplicar(destino, politica.retencao)

        assert ficha["ok"] is True
        assert len(relatorio["removidos"]) == 4
        assert len(retencao.listar(destino)) == 1

    def test_o_pacote_recem_criado_sobrevive_a_retencao(
        self, autorizada: tuple[Configuracao, Path]
    ) -> None:
        """
        A copia que acabou de ser feita nao pode ser a primeira a ir embora.

        Seria o desfecho mais absurdo possivel: fazer backup e apaga-lo em
        seguida, relatando sucesso.
        """
        configuracao, pasta = autorizada
        politica = Politica(
            origens=[str(pasta)],
            retencao=Retencao(diarias=1, semanais=0, mensais=0),
        )

        ficha = asyncio.run(backup_agente.executar_politica(politica, configuracao))

        assert ficha["retencao"]["guardados"] >= 1
        assert ficha["pacote"] not in ficha["retencao"]["removidos"]

    def test_falha_na_faxina_vira_ressalva_e_nao_falha(
        self, autorizada: tuple[Configuracao, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O pacote existe; o que nao deu certo foi a limpeza."""
        configuracao, pasta = autorizada

        def limpeza_com_problema(_pasta: Path, _regra: Retencao) -> dict[str, object]:
            return {"guardados": 1, "removidos": [], "nao_removidos": ["velho.zip"]}

        monkeypatch.setattr(retencao, "aplicar", limpeza_com_problema)

        ficha = asyncio.run(
            backup_agente.executar_politica(Politica(origens=[str(pasta)]), configuracao)
        )

        assert ficha["ok"] is True
        assert ficha["com_ressalva"] is True
        assert "nao puderam ser apagados" in ficha["ressalva"]


class TestIncrementalNaPolitica:
    """
    O incremental so acontece quando a politica pede.

    Desligado por padrao de proposito: o pacote completo se sustenta sozinho,
    e o incremental exige a corrente de pacotes anteriores para restaurar.
    """

    def test_desligado_por_padrao(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        configuracao, pasta = autorizada

        ficha = asyncio.run(
            backup_agente.executar_politica(Politica(origens=[str(pasta)]), configuracao)
        )

        assert ficha["incremental"] is False
        assert ficha["inalterados"] == 0

    def test_segunda_execucao_pula_o_que_nao_mudou(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        configuracao, pasta = autorizada
        politica = Politica(
            origens=[str(pasta)],
            destino=Destino(tipo=TipoDeDestino.LOCAL, caminho=str(tmp_path / "copia")),
            incremental=True,
        )

        primeira = asyncio.run(backup_agente.executar_politica(politica, configuracao))
        (pasta / "novo.txt").write_text("novo", encoding="utf-8")
        segunda = asyncio.run(backup_agente.executar_politica(politica, configuracao))

        assert primeira["arquivos"] == 1
        assert segunda["arquivos"] == 1
        assert segunda["inalterados"] == 1
        assert segunda["incremental"] is True

    def test_catalogo_esquece_pacote_que_a_retencao_apagou(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        """
        Catalogo apontando para pacote apagado e referencia quebrada.

        Melhor copiar de novo do que prometer um arquivo que nao existe.
        """
        configuracao, pasta = autorizada
        politica = Politica(
            origens=[str(pasta)],
            retencao=Retencao(diarias=1, semanais=0, mensais=0),
            incremental=True,
        )

        asyncio.run(backup_agente.executar_politica(politica, configuracao))
        segunda = asyncio.run(backup_agente.executar_politica(politica, configuracao))

        # A chave e o campo existir e ser um numero: a sincronizacao rodou.
        assert "catalogo_esquecidos" in segunda
        assert isinstance(segunda["catalogo_esquecidos"], int)


def _envelhecer(configuracao: Configuracao, politica_id: str, pacote: str, para: str) -> Path:
    """
    Faz um pacote recem-criado parecer antigo, renomeando-o.

    A data vem do NOME — e nao da data de modificacao do arquivo —, entao esta
    e a forma honesta de simular a passagem do tempo: e exatamente o que a
    retencao vai ler.
    """
    raiz = Path(configuracao.raizes[0]).parent / backup_agente.PASTA_PADRAO
    de = raiz / f"politica-{politica_id}" / pacote
    alvo = de.with_name(f"backup_{para}.zip")
    de.rename(alvo)
    return alvo


class TestDuasPoliticasNaMesmaMaquina:
    """
    O defeito que este bloco fixa apagava dado do cliente, em silencio.

    Todas as politicas de uma maquina gravavam na mesma pasta. A retencao
    varre a pasta e decide o que sobra — entao a politica "diario / 7 dias",
    ao rodar, olhava tambem os pacotes da politica "mensal / 12 meses" e
    apagava os que tinham mais de sete dias. Regra cumprida a risca, sobre
    arquivos que nao eram dela.

    Do lado do cliente: configurou doze meses de historico, recebeu sete dias.
    Sem erro, sem aviso, e sem nada no log que explicasse a falta. Descoberto
    no dia da restauracao, que e o pior dia possivel.
    """

    def politica(self, pasta: Path, **extras: object) -> Politica:
        return Politica(origens=[str(pasta)], **extras)  # type: ignore[arg-type]

    def test_cada_politica_grava_na_propria_pasta(
        self, autorizada: tuple[Configuracao, Path]
    ) -> None:
        configuracao, pasta = autorizada

        primeira = asyncio.run(
            backup_agente.executar_politica(
                self.politica(pasta), configuracao, politica_id="p1", politica_nome="Diaria"
            )
        )
        segunda = asyncio.run(
            backup_agente.executar_politica(
                self.politica(pasta), configuracao, politica_id="p2", politica_nome="Mensal"
            )
        )

        raiz = Path(configuracao.raizes[0]).parent / backup_agente.PASTA_PADRAO
        assert (raiz / "politica-p1" / primeira["pacote"]).is_file()
        assert (raiz / "politica-p2" / segunda["pacote"]).is_file()

    def test_a_retencao_de_uma_nao_alcanca_o_pacote_da_outra(
        self, autorizada: tuple[Configuracao, Path]
    ) -> None:
        """
        O teste que reproduz o estrago: o mensal do ano passado sobrevive a
        uma diaria de um dia rodando na mesma maquina.
        """
        configuracao, pasta = autorizada

        # O pacote do "mensal" e criado pelo PRODUTO, e nao escrito a mao num
        # caminho que o teste inventou. E o que faz este teste valer: se
        # alguem tirar a pasta por politica, os dois pacotes voltam a cair no
        # mesmo lugar e a diaria volta a apagar o mensal — que e o defeito.
        do_mensal = asyncio.run(
            backup_agente.executar_politica(
                self.politica(pasta, retencao=Retencao(diarias=0, semanais=0, mensais=12)),
                configuracao,
                politica_id="mensal",
                politica_nome="Mensal 12 meses",
            )
        )
        antigo = _envelhecer(configuracao, "mensal", do_mensal["pacote"], "2025-01-15_2100")

        asyncio.run(
            backup_agente.executar_politica(
                self.politica(pasta, retencao=Retencao(diarias=1, semanais=0, mensais=0)),
                configuracao,
                politica_id="diaria",
                politica_nome="Diaria 7 dias",
            )
        )

        assert antigo.is_file(), "a retencao da diaria apagou o pacote do mensal — o defeito voltou"

    def test_o_marcador_diz_de_quem_e_a_pasta(self, autorizada: tuple[Configuracao, Path]) -> None:
        """Quem abre o disco daqui a um ano nao tem servidor a mao."""
        from apps.agente.agente import pastas as mod_pastas

        configuracao, pasta = autorizada
        asyncio.run(
            backup_agente.executar_politica(
                self.politica(pasta),
                configuracao,
                politica_id="p1",
                politica_nome="Backup diario 03:00",
            )
        )

        raiz = Path(configuracao.raizes[0]).parent / backup_agente.PASTA_PADRAO
        da_politica = raiz / "politica-p1"
        assert mod_pastas.nome_marcado(da_politica) == "Backup diario 03:00"
        assert mod_pastas.identificador_da_pasta(da_politica) == "p1"

    def test_o_catalogo_do_incremental_tambem_e_separado(
        self, autorizada: tuple[Configuracao, Path]
    ) -> None:
        """
        A outra metade do mesmo defeito, por outro caminho.

        O catalogo mora ao lado dos pacotes. Compartilhado, a segunda politica
        "copiava so o que mudou" em relacao ao pacote da primeira — que cobre
        outras pastas. A corrente resultante nunca esteve completa, e isso so
        apareceria no dia da restauracao.
        """
        from autotarefas.tasks import catalogo as mod_catalogo

        configuracao, pasta = autorizada
        for identificador in ("p1", "p2"):
            asyncio.run(
                backup_agente.executar_politica(
                    self.politica(pasta, incremental=True),
                    configuracao,
                    politica_id=identificador,
                    politica_nome=identificador,
                )
            )

        raiz = Path(configuracao.raizes[0]).parent / backup_agente.PASTA_PADRAO
        assert (raiz / "politica-p1" / mod_catalogo.NOME).is_file()
        assert (raiz / "politica-p2" / mod_catalogo.NOME).is_file()
        assert not (raiz / mod_catalogo.NOME).exists()

    def test_o_backup_avulso_continua_na_raiz(self, autorizada: tuple[Configuracao, Path]) -> None:
        """
        Sem politica, sem pasta de politica.

        Inventar um dono para o avulso faria a retencao de alguma politica
        passar a alcanca-lo.
        """
        configuracao, pasta = autorizada

        ficha = asyncio.run(backup_agente.executar_politica(self.politica(pasta), configuracao))

        raiz = Path(configuracao.raizes[0]).parent / backup_agente.PASTA_PADRAO
        assert (raiz / ficha["pacote"]).is_file()


class TestARetencaoNoDestinoExterno:
    """
    A retencao tambem precisa valer onde a copia de verdade esta.

    Ela rodava so na pasta local. O disco externo e a pasta de rede acumulavam
    para sempre — ate encher, e a partir dai TODO backup daquela politica
    falhava por falta de espaco, com a mensagem certa e a causa escondida tres
    meses atras.

    Havia um segundo estrago, mais silencioso: a promessa "guardo doze meses"
    so era cumprida no lugar que nao protege contra nada, enquanto o destino
    que de fato protege guardava tudo, inclusive o que a regra mandava apagar.
    """

    def test_o_destino_externo_e_faxinado_pela_mesma_regra(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        configuracao, pasta = autorizada
        fora = tmp_path / "disco-externo"
        politica = Politica(
            origens=[str(pasta)],
            destino=Destino(tipo=TipoDeDestino.LOCAL, caminho=str(fora)),
            retencao=Retencao(diarias=1, semanais=0, mensais=0),
        )

        primeira = asyncio.run(
            backup_agente.executar_politica(
                politica, configuracao, politica_id="p1", politica_nome="Diaria"
            )
        )
        # O pacote de ontem, no destino, que a regra de uma diaria manda ir.
        antigo = fora / "politica-p1" / "backup_2020-01-01_0200.zip"
        antigo.write_bytes(b"pacote antigo no destino")

        segunda = asyncio.run(
            backup_agente.executar_politica(
                politica, configuracao, politica_id="p1", politica_nome="Diaria"
            )
        )

        assert primeira["ok"] is True
        assert "retencao_no_destino" in segunda
        assert not antigo.exists(), "o destino externo acumularia para sempre"

    def test_a_copia_recem_entregue_sobrevive_a_faxina_do_destino(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        """Entregar e apagar em seguida seria o desfecho mais absurdo possivel."""
        configuracao, pasta = autorizada
        fora = tmp_path / "disco-externo"
        politica = Politica(
            origens=[str(pasta)],
            destino=Destino(tipo=TipoDeDestino.LOCAL, caminho=str(fora)),
            retencao=Retencao(diarias=1, semanais=0, mensais=0),
        )

        ficha = asyncio.run(
            backup_agente.executar_politica(
                politica, configuracao, politica_id="p1", politica_nome="Diaria"
            )
        )

        assert (fora / "politica-p1" / ficha["pacote"]).is_file()

    def test_cada_politica_entrega_na_propria_pasta_do_destino(
        self, autorizada: tuple[Configuracao, Path], tmp_path: Path
    ) -> None:
        """
        Sem isto, a faxina que acabou de nascer apagaria pacote da politica
        errada — no unico lugar onde a copia realmente protege.
        """
        configuracao, pasta = autorizada
        fora = tmp_path / "disco-externo"

        def politica_para(caminho: Path) -> Politica:
            return Politica(
                origens=[str(pasta)],
                destino=Destino(tipo=TipoDeDestino.LOCAL, caminho=str(caminho)),
            )

        primeira = asyncio.run(
            backup_agente.executar_politica(
                politica_para(fora), configuracao, politica_id="p1", politica_nome="A"
            )
        )
        segunda = asyncio.run(
            backup_agente.executar_politica(
                politica_para(fora), configuracao, politica_id="p2", politica_nome="B"
            )
        )

        assert (fora / "politica-p1" / primeira["pacote"]).is_file()
        assert (fora / "politica-p2" / segunda["pacote"]).is_file()
