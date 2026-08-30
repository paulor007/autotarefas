"""
O ambiente publico do AutoTarefas.

O que se protege aqui sao as decisoes que ninguem repara ate darem errado em
producao: que o provisionamento nao duplica nada ao rodar de novo, que o
destino nao mente sobre onde a copia esta, e que os arquivos de exemplo sao
sinteticos.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import vitrine


class TestOsExemplos:
    def test_sao_sinteticos_e_se_declaram(self) -> None:
        """
        Nenhum dado real de ninguem entra num ambiente publico.

        E nao basta serem inventados: quem abrir o pacote restaurado precisa
        conseguir dizer que sao de exemplo sem perguntar a ninguem.
        """
        for relativo, conteudo in vitrine.EXEMPLOS.items():
            assert not Path(relativo).is_absolute()
            texto = conteudo.lower()
            assert "exemplo" in texto, relativo

    def test_semear_e_seguro_de_repetir(self, tmp_path: Path) -> None:
        primeira = vitrine.semear_dados(tmp_path)
        segunda = vitrine.semear_dados(tmp_path)

        assert primeira == len(vitrine.EXEMPLOS)
        assert segunda == 0

    def test_semear_nao_sobrescreve_o_que_ja_existe(self, tmp_path: Path) -> None:
        """
        O ambiente roda por meses; os arquivos mudam entre backups.

        Reescrever a cada deploy apagaria a diferenca que o incremental e o
        historico existem para mostrar.
        """
        relativo = next(iter(vitrine.EXEMPLOS))
        alvo = tmp_path / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text("conteudo que mudou depois", encoding="utf-8")

        vitrine.semear_dados(tmp_path)

        assert alvo.read_text(encoding="utf-8") == "conteudo que mudou depois"


class TestAsPoliticas:
    def test_uma_por_horario_do_dia(self) -> None:
        nomes = {vitrine.nome_da_politica(hora) for hora in vitrine.HORARIOS}

        assert len(nomes) == len(vitrine.HORARIOS)
        assert len(vitrine.HORARIOS) >= 2, (
            "com uma politica so, o visitante estaria em media doze horas depois da ultima execucao"
        )

    def test_a_configuracao_passa_pelo_schema_do_nucleo(self) -> None:
        """
        Se o motor recusar esta configuracao, o deploy quebra no provisionamento.

        Conferir aqui e barato; descobrir na subida do servidor publico, nao.
        """
        from autotarefas.tasks.politica import Politica

        for hora in vitrine.HORARIOS:
            configuracao = vitrine.configuracao_da_politica(hora, ["C:\\Dados"])
            validada = Politica.model_validate(configuracao)

            assert validada.agendamento.tipo.value == "diario"
            assert validada.origens == ["C:\\Dados"]

    def test_o_agendamento_e_o_horario_pedido(self) -> None:
        configuracao = vitrine.configuracao_da_politica("09:00", ["/dados"])

        assert configuracao["agendamento"]["hora"] == "09:00"  # type: ignore[index]


class TestODestino:
    def test_sem_configurar_e_local_e_nao_finge_ser_externo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Num servidor unico o destino E o mesmo disco, e o painel vai dizer isso.

        Declarar "externo" aqui deixaria o painel verde e a frase falsa — a
        mentira exata que o produto inteiro foi feito para nao contar.
        """
        monkeypatch.delenv("VITRINE_DESTINO_TIPO", raising=False)
        monkeypatch.delenv("VITRINE_DESTINO_CAMINHO", raising=False)

        destino = vitrine.destino_configurado()

        assert destino["tipo"] == "local"

    def test_um_destino_de_verdade_externo_e_respeitado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VITRINE_DESTINO_TIPO", "rede")
        monkeypatch.setenv("VITRINE_DESTINO_CAMINHO", "\\\\servidor\\backups")

        destino = vitrine.destino_configurado()

        assert destino["tipo"] == "rede"
        assert destino["caminho"] == "\\\\servidor\\backups"

    def test_nuvem_sem_credencial_e_recusada_no_provisionamento(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Parar aqui, e nao no meio das quatro politicas.

        Sem balde, o pacote seria feito e nao teria para onde ir — e a politica
        que o painel conta como protecao nunca entregaria nada. A mensagem diz
        exatamente qual variavel falta, porque "configure a nuvem" mandaria a
        pessoa procurar onde.
        """
        monkeypatch.setenv("VITRINE_DESTINO_TIPO", "nuvem")
        for nome in vitrine.OBRIGATORIOS_DE_NUVEM:
            monkeypatch.delenv(nome, raising=False)

        with pytest.raises(SystemExit, match="VITRINE_S3_BALDE"):
            vitrine.destino_configurado()

    def test_nuvem_com_credencial_e_aceita_e_nao_usa_caminho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # O balde nao e um caminho em disco: ele vem do cofre. Preencher
        # `caminho` aqui faria o schema do nucleo guardar um valor que ninguem
        # le, e a tela mostraria uma pasta que nao existe.
        monkeypatch.setenv("VITRINE_DESTINO_TIPO", "nuvem")
        for nome in vitrine.OBRIGATORIOS_DE_NUVEM:
            monkeypatch.setenv(nome, "valor-de-teste")

        destino = vitrine.destino_configurado()

        assert destino == {"tipo": "nuvem", "caminho": ""}

    def test_o_tipo_local_reprova_no_veredito_de_protecao(self) -> None:
        """
        Amarra as duas pontas: o que a vitrine configura e o que o painel julga.

        Sem isto, alguem mudaria o destino padrao para "externo" achando que
        melhora a demonstracao, e o painel passaria a dizer "Protegido" para
        uma copia que mora ao lado do original.
        """
        from autotarefas.tasks.politica import Politica

        configuracao = vitrine.configuracao_da_politica("03:00", ["/dados"])
        validada = Politica.model_validate(configuracao)

        assert validada.protege_de_verdade is (vitrine.destino_configurado()["tipo"] != "local")


class TestOndeAVitrineMora:
    def test_longe_do_banco_do_dia_a_dia(self) -> None:
        assert vitrine.BANCO.name == "vitrine.db"
        assert "autotarefas.db" not in str(vitrine.BANCO)

    def test_tudo_dentro_da_pasta_de_runtime(self) -> None:
        """`.autotarefas/` e coberta pelo `.gitignore`: nada disso e versionado."""
        for caminho in (
            vitrine.BANCO,
            vitrine.CONFIG_DO_AGENTE,
            vitrine.DADOS,
            vitrine.DESTINO,
        ):
            assert vitrine.CASA in caminho.parents or caminho == vitrine.CASA
        assert vitrine.CASA.parent.name == ".autotarefas"


class TestASituacao:
    def test_vazia_nao_e_completa(self) -> None:
        assert vitrine.Situacao().completa is False

    def test_so_e_completa_com_as_quatro_pecas(self) -> None:
        quase = vitrine.Situacao(
            organizacao=True,
            maquina=True,
            pastas=1,
            politicas=len(vitrine.HORARIOS) - 1,
        )
        inteira = vitrine.Situacao(
            organizacao=True, maquina=True, pastas=1, politicas=len(vitrine.HORARIOS)
        )

        assert quase.completa is False
        assert inteira.completa is True

    def test_maquina_sem_pasta_nao_conta_como_pronta(self) -> None:
        # Um Agente pareado sem pasta autorizada nao copia nada, e isso e facil
        # de confundir com "esta funcionando".
        assert (
            vitrine.Situacao(
                organizacao=True,
                maquina=True,
                pastas=0,
                politicas=len(vitrine.HORARIOS),
            ).completa
            is False
        )


class TestASemeadura:
    """
    Executar uma vez cada politica que nunca rodou.

    Sem isto, um ambiente recem-publicado mostra "Protecao em risco - este
    backup nunca concluiu uma execucao" ate a primeira janela do agendamento.
    E verdade, e e uma verdade inutil para quem chegou agora.
    """

    def politica(self, identificador: str) -> dict[str, object]:
        return {"id": identificador, "nome": f"Politica {identificador}"}

    def execucao(self, politica_id: str, resultado: str) -> dict[str, object]:
        return {"politica_id": politica_id, "resultado": resultado}

    def test_sem_historico_todas_precisam_rodar(self) -> None:
        politicas = [self.politica("p1"), self.politica("p2")]

        pendentes = vitrine.politicas_sem_sucesso(politicas, [])

        assert [item["id"] for item in pendentes] == ["p1", "p2"]

    def test_quem_ja_concluiu_fica_de_fora(self) -> None:
        """O que torna o comando seguro de repetir a cada deploy."""
        politicas = [self.politica("p1"), self.politica("p2")]
        execucoes = [self.execucao("p1", "sucesso")]

        pendentes = vitrine.politicas_sem_sucesso(politicas, execucoes)

        assert [item["id"] for item in pendentes] == ["p2"]

    def test_execucao_com_ressalva_conta_como_concluida(self) -> None:
        # O backup aconteceu e o pacote existe. Rodar de novo por causa de uma
        # ressalva encheria o historico sem resolver a ressalva.
        politicas = [self.politica("p1")]
        execucoes = [self.execucao("p1", "com_ressalva")]

        assert vitrine.politicas_sem_sucesso(politicas, execucoes) == []

    def test_falha_nao_conta_como_concluida(self) -> None:
        politicas = [self.politica("p1")]
        execucoes = [self.execucao("p1", "falha")]

        pendentes = vitrine.politicas_sem_sucesso(politicas, execucoes)

        assert [item["id"] for item in pendentes] == ["p1"]

    def test_execucao_de_outra_politica_nao_conta(self) -> None:
        politicas = [self.politica("p1")]
        execucoes = [self.execucao("p2", "sucesso")]

        pendentes = vitrine.politicas_sem_sucesso(politicas, execucoes)

        assert [item["id"] for item in pendentes] == ["p1"]
