"""O agora: o que roda, e o que vem depois.

O histórico responde "funcionou", com data, tamanho e hash. É evidência forte —
e ainda assim quem chega de fora olha uma lista de linhas prontas e não vê
nenhuma delas acontecer.

O que se protege aqui é a honestidade dessa tela, que é fácil de perder de duas
formas opostas:

1. **Inventar movimento.** Uma barra que avança sozinha, um "processando" que
   aparece porque a tela abriu. Fora da janela de uma execução, a lista é
   vazia — e vazia é a resposta certa.
2. **Deixar de dizer que está vivo.** Uma tela em branco não distingue "nada
   rodando agora" de "isto aqui está morto". Por isso o próximo horário vem
   junto.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest

from apps.api.app import atividade, canal, dispositivos, politicas
from apps.api.app.db import repositorio as repo
from apps.api.app.db.models import Papel, agora
from apps.api.app.db.sessao import Banco


@pytest.fixture
def banco() -> Iterator[Banco]:
    instancia = Banco("sqlite:///:memory:")
    instancia.criar_esquema()
    canal.presenca.limpar()
    yield instancia
    canal.presenca.limpar()
    instancia.descartar()


def _organizacao(banco: Banco, nome: str = "Padaria") -> repo.Contexto:
    with banco.sessao() as sessao:
        organizacao = repo.criar_organizacao(sessao, nome=nome, dominio=f"{nome.lower()}.br")
        usuario = repo.criar_usuario(
            sessao,
            email=f"dono@{nome.lower()}.br",
            nome="Dono",
            emissor="bootstrap",
            assunto=nome,
        )
        repo.vincular(sessao, organizacao=organizacao, usuario=usuario, papel=Papel.DONO)
        return repo.Contexto(organizacao_id=organizacao.id, usuario_id=usuario.id, papel=Papel.DONO)


def _dispositivo(banco: Banco, contexto: repo.Contexto, chave: str = "k1") -> str:
    with banco.sessao() as sessao:
        codigo = dispositivos.emitir(sessao, contexto).codigo
    with banco.sessao() as sessao:
        return dispositivos.parear(
            sessao,
            codigo=codigo,
            chave_publica=chave,
            nome="PC da loja",
            sistema="Windows 11",
            versao_agente="0.1.0",
        ).id


def _politica(banco: Banco, contexto: repo.Contexto, dispositivo_id: str, hora: str) -> str:
    with banco.sessao() as sessao:
        registro = politicas.criar(
            sessao,
            contexto,
            politicas.PedidoDePolitica(
                nome=f"Backup {hora}",
                dispositivo_id=dispositivo_id,
                configuracao={
                    "agendamento": {
                        "tipo": "diario",
                        "hora": hora,
                        "dia_da_semana": 0,
                        "dia_do_mes": 1,
                    }
                },
            ),
        )
        return registro.id


class _SocketFalso:
    """O bastante para uma `Conexao` existir sem rede."""

    async def send_json(self, _dados: dict[str, Any]) -> None:
        return None


def _conectar(contexto: repo.Contexto, dispositivo_id: str) -> canal.Conexao:
    conexao = canal.Conexao(
        dispositivo_id=dispositivo_id,
        organizacao_id=contexto.organizacao_id,
        nome="PC da loja",
        socket=_SocketFalso(),  # type: ignore[arg-type]
    )
    canal.presenca.entrar(conexao)
    return conexao


class TestOQueEstaRodando:
    def test_sem_nada_rodando_a_lista_e_vazia(self, banco: Banco) -> None:
        """
        Vazio é a resposta certa, e não uma tela que precisa ser preenchida.

        Disparar um backup para a tela ter o que mostrar seria mexer na
        máquina do cliente para melhorar uma demonstração.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _conectar(contexto, dispositivo_id)

        assert atividade.acontecendo(contexto.organizacao_id) == []

    def test_o_backup_do_horario_aparece_enquanto_roda(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        conexao = _conectar(contexto, dispositivo_id)

        conexao.anotar_progresso(
            "politica:p1",
            {"etapa": "compactando", "politica_id": "p1", "politica_nome": "Backup 03:00"},
        )
        correndo = atividade.acontecendo(contexto.organizacao_id)

        assert len(correndo) == 1
        assert correndo[0]["politica_nome"] == "Backup 03:00"
        assert correndo[0]["maquina"] == "PC da loja"

    def test_a_etapa_e_traduzida_para_quem_nao_e_da_equipe(self, banco: Banco) -> None:
        """
        `entregando` é nome de log. Quem olha a tela quer saber o que está
        acontecendo com os arquivos dele.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        conexao = _conectar(contexto, dispositivo_id)

        conexao.anotar_progresso("politica:p1", {"etapa": "entregando"})
        correndo = atividade.acontecendo(contexto.organizacao_id)

        assert correndo[0]["etapa_em_portugues"] == "Copiando para o destino"

    def test_etapa_desconhecida_nao_quebra_a_tela(self, banco: Banco) -> None:
        # Um Agente mais novo pode relatar uma etapa que este servidor ainda
        # nao conhece. Melhor mostrar o nome cru do que esconder que ha algo
        # acontecendo.
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        conexao = _conectar(contexto, dispositivo_id)

        conexao.anotar_progresso("politica:p1", {"etapa": "assinando_manifesto"})
        correndo = atividade.acontecendo(contexto.organizacao_id)

        assert correndo[0]["etapa_em_portugues"] == "Assinando manifesto"

    def test_concluido_sai_da_lista(self, banco: Banco) -> None:
        """Terminou não é "rodando". A partir daí, quem conta é o histórico."""
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        conexao = _conectar(contexto, dispositivo_id)

        conexao.anotar_progresso("politica:p1", {"etapa": "concluido", "arquivos": 12})

        assert atividade.acontecendo(contexto.organizacao_id) == []

    def test_progresso_velho_deixa_de_valer(self, banco: Banco) -> None:
        """
        O teste que impede a mentira mais longa desta tela.

        Se o Agente cai no meio de uma cópia, a última etapa que ele mandou
        ficaria aqui para sempre — e a tela diria "compactando" sobre um
        processo morto, indefinidamente.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        conexao = _conectar(contexto, dispositivo_id)

        conexao.anotar_progresso("politica:p1", {"etapa": "compactando"})
        velho = agora() - canal.VALIDADE_DO_PROGRESSO - timedelta(seconds=1)
        conexao.progresso["politica:p1"]["recebido_em"] = velho.isoformat()

        assert atividade.acontecendo(contexto.organizacao_id) == []
        assert "politica:p1" not in conexao.progresso, "o registro morto devia ter sido descartado"

    def test_progresso_de_comando_nao_entra_aqui(self, banco: Banco) -> None:
        """
        Backup disparado da tela já tem quem o acompanhe: quem clicou.

        Misturar os dois faria o mesmo backup aparecer duas vezes para quem
        está com a tela aberta.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        conexao = _conectar(contexto, dispositivo_id)
        conexao.pendentes["comando-1"] = None  # type: ignore[assignment]

        conexao.anotar_progresso("comando-1", {"etapa": "compactando"})

        assert atividade.acontecendo(contexto.organizacao_id) == []

    def test_uma_organizacao_nao_ve_o_backup_da_outra(self, banco: Banco) -> None:
        primeira = _organizacao(banco, "Padaria")
        segunda = _organizacao(banco, "Oficina")
        dispositivo_id = _dispositivo(banco, primeira)
        conexao = _conectar(primeira, dispositivo_id)

        conexao.anotar_progresso("politica:p1", {"etapa": "compactando"})

        assert len(atividade.acontecendo(primeira.organizacao_id)) == 1
        assert atividade.acontecendo(segunda.organizacao_id) == []


class TestOQueVemDepois:
    def test_a_proxima_execucao_de_cada_politica(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _politica(banco, contexto, dispositivo_id, "03:00")

        with banco.sessao() as sessao:
            proximas = atividade.agenda(sessao, contexto)

        assert len(proximas) == 1
        assert proximas[0]["nome"] == "Backup 03:00"
        assert proximas[0]["proxima_no_relogio_da_maquina"].endswith("03:00:00")
        assert proximas[0]["maquina"] == "PC da loja"

    def test_ordenadas_pela_que_vem_primeiro(self, banco: Banco) -> None:
        """
        "O que vem agora" só é útil se a primeira linha for a próxima.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _politica(banco, contexto, dispositivo_id, "21:00")
        _politica(banco, contexto, dispositivo_id, "03:00")

        with banco.sessao() as sessao:
            proximas = atividade.agenda(sessao, contexto)

        chaves = [item["proxima_no_relogio_da_maquina"] for item in proximas]
        assert chaves == sorted(chaves)

    def test_politica_sem_horario_vai_para_o_fim_sem_prometer_nada(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        with banco.sessao() as sessao:
            politicas.criar(
                sessao,
                contexto,
                politicas.PedidoDePolitica(
                    nome="Manual",
                    dispositivo_id=dispositivo_id,
                    configuracao={"agendamento": {"tipo": "desligado"}},
                ),
            )
        _politica(banco, contexto, dispositivo_id, "03:00")

        with banco.sessao() as sessao:
            proximas = atividade.agenda(sessao, contexto)

        assert proximas[-1]["nome"] == "Manual"
        # Vazio, e nao uma data inventada: sem horario nao ha proxima.
        assert proximas[-1]["proxima_no_relogio_da_maquina"] == ""

    def test_politica_desativada_nao_promete_execucao(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        politica_id = _politica(banco, contexto, dispositivo_id, "03:00")
        with banco.sessao() as sessao:
            politicas.alterar(
                sessao,
                contexto,
                politica_id,
                politicas.PedidoDePolitica(
                    nome="Backup 03:00", dispositivo_id=dispositivo_id, ativa=False
                ),
            )

        with banco.sessao() as sessao:
            assert atividade.agenda(sessao, contexto) == []

    def test_o_calculo_e_o_mesmo_do_agendador_da_maquina(self, banco: Banco) -> None:
        """
        Uma segunda implementação aqui produziria, mais cedo ou mais tarde, uma
        tela prometendo 03:00 para um Agente que dispara às 04:00 — e a
        discordância apareceria como "backup atrasado" sem nada estar atrasado.
        """
        from autotarefas.tasks.politica import Agendamento, proxima_execucao

        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _politica(banco, contexto, dispositivo_id, "03:00")

        from datetime import datetime

        momento = datetime.now()
        with banco.sessao() as sessao:
            proximas = atividade.agenda(sessao, contexto)
        esperada = proxima_execucao(
            Agendamento(tipo="diario", hora="03:00"),  # type: ignore[arg-type]
            momento,
        )

        assert esperada is not None
        assert proximas[0]["proxima_no_relogio_da_maquina"][:13] == esperada.isoformat()[:13]
