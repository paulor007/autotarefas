"""Política de backup (02.E).

O formato mora no núcleo porque significa a mesma coisa dos dois lados: o
servidor guarda e valida, o Agente executa. Estes testes protegem as três
decisões que mais custam quando erradas:

- **horário local**, e não UTC — converter erraria duas vezes por ano, no
  horário de verão, exatamente na madrugada;
- **retenção GFS**, e não "guardar N" — guardar 30 diárias protege contra o
  erro de ontem, não contra o que ninguém viu há três meses;
- **validação na gravação**, e não na execução — de madrugada não há quem
  corrija um campo errado.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from autotarefas.tasks.politica import (
    Agendamento,
    Destino,
    Notificacao,
    Politica,
    QuandoNotificar,
    Retencao,
    Retry,
    TipoDeAgendamento,
    TipoDeDestino,
    proxima_execucao,
)


def _quando(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=UTC)


class TestPadroes:
    def test_politica_padrao_nao_dispara_sozinha(self) -> None:
        """
        Uma política recém-criada não pode começar a copiar por conta própria.

        Quem acabou de configurar ainda vai escolher origem e destino; disparar
        antes disso produziria um pacote que ninguém pediu.
        """
        assert Politica().agendamento.tipo is TipoDeAgendamento.DESLIGADO

    def test_assinar_vem_ligado(self) -> None:
        """
        É o que separa "não se estragou" de "ninguém mexeu".

        Desligado por padrão, quase ninguém ligaria — e a diferença só
        apareceria no dia em que importasse.
        """
        assert Politica().assinar is True

    def test_notificar_so_em_problema(self) -> None:
        """Aviso que sempre chega vira ruído, e ruído é ignorado."""
        assert Politica().notificacao.quando is QuandoNotificar.PROBLEMA

    def test_origens_vazias_significam_tudo_que_foi_autorizado(self) -> None:
        """Quem autorizou uma pasta quer que ela seja copiada."""
        assert Politica().origens == []

    def test_pacote_so_na_maquina_nao_conta_como_protecao(self) -> None:
        """
        A tela precisa dizer a verdade em vez de mostrar "configurado".

        Pacote no mesmo computador não protege contra o disco morrer nem
        contra ransomware.
        """
        assert Politica().protege_de_verdade is False
        assert Politica(destino=Destino(tipo=TipoDeDestino.NUVEM)).protege_de_verdade is True
        assert (
            Politica(destino=Destino(tipo=TipoDeDestino.LOCAL, caminho="C:\\b")).protege_de_verdade
            is False
        )


class TestValidacao:
    def test_horario_invalido_e_recusado_na_gravacao(self) -> None:
        with pytest.raises(ValidationError, match="horario invalido"):
            Agendamento(tipo=TipoDeAgendamento.DIARIO, hora="25:99")

    def test_retencao_zerada_e_recusada(self) -> None:
        """
        Apagar tudo logo depois de copiar é pior do que não ter retenção.

        E é um erro fácil de cometer zerando os campos "para desligar".
        """
        with pytest.raises(ValidationError, match="retencao zerada"):
            Retencao(diarias=0, semanais=0, mensais=0)

    def test_destino_com_caminho_obrigatorio(self) -> None:
        with pytest.raises(ValidationError, match="precisa de um caminho"):
            Destino(tipo=TipoDeDestino.EXTERNO, caminho="  ")

    def test_nuvem_nao_precisa_de_caminho(self) -> None:
        """A nuvem vem da credencial guardada no cofre da organização."""
        assert Destino(tipo=TipoDeDestino.NUVEM).caminho == ""

    def test_email_torto_e_recusado(self) -> None:
        with pytest.raises(ValidationError, match="e-mail invalido"):
            Notificacao(emails=["sem-arroba"])

    def test_tentativas_tem_teto(self) -> None:
        """Retry infinito seguraria a máquina o dia inteiro."""
        with pytest.raises(ValidationError):
            Retry(tentativas=999)


class TestRetry:
    def test_primeira_tentativa_nao_espera(self) -> None:
        assert Retry().espera_da_tentativa(1) == timedelta(0)

    def test_espera_cresce(self) -> None:
        """
        Insistir de minuto em minuto num disco desconectado enche o log e
        gasta a bateria do notebook.
        """
        politica = Retry(tentativas=4, espera_inicial_min=5, fator=2.0)

        assert politica.espera_da_tentativa(2) == timedelta(minutes=5)
        assert politica.espera_da_tentativa(3) == timedelta(minutes=10)
        assert politica.espera_da_tentativa(4) == timedelta(minutes=20)

    def test_espera_tem_teto_de_um_dia(self) -> None:
        """Sem teto, um fator alto agendaria a retentativa para o ano que vem."""
        assert Retry(fator=5.0, espera_inicial_min=120).espera_da_tentativa(10) <= timedelta(days=1)


class TestProximaExecucao:
    def test_desligado_nao_tem_proxima(self) -> None:
        assert proxima_execucao(Agendamento(), _quando("2026-08-25T10:00")) is None

    def test_diario_no_mesmo_dia(self) -> None:
        proxima = proxima_execucao(
            Agendamento(tipo=TipoDeAgendamento.DIARIO, hora="02:00"),
            _quando("2026-08-25T01:00"),
        )
        assert proxima == _quando("2026-08-25T02:00")

    def test_diario_pula_para_amanha_quando_o_horario_ja_passou(self) -> None:
        proxima = proxima_execucao(
            Agendamento(tipo=TipoDeAgendamento.DIARIO, hora="02:00"),
            _quando("2026-08-25T10:00"),
        )
        assert proxima == _quando("2026-08-26T02:00")

    def test_horario_exato_agenda_para_o_proximo_e_nao_para_agora(self) -> None:
        """
        O teste que evita o backup em laço.

        Uma execução que termina às 02:00:00 em ponto agendaria a seguinte
        para o mesmo segundo, e o backup rodaria sem parar.
        """
        proxima = proxima_execucao(
            Agendamento(tipo=TipoDeAgendamento.DIARIO, hora="02:00"),
            _quando("2026-08-25T02:00"),
        )
        assert proxima == _quando("2026-08-26T02:00")

    def test_semanal_cai_no_dia_escolhido(self) -> None:
        # 2026-08-25 e uma terca-feira (weekday 1).
        proxima = proxima_execucao(
            Agendamento(tipo=TipoDeAgendamento.SEMANAL, dia_da_semana=4, hora="03:00"),
            _quando("2026-08-25T10:00"),
        )
        assert proxima is not None
        assert proxima.weekday() == 4
        assert proxima.hour == 3

    def test_semanal_no_proprio_dia_mas_depois_da_hora_vai_para_a_semana_seguinte(
        self,
    ) -> None:
        proxima = proxima_execucao(
            Agendamento(tipo=TipoDeAgendamento.SEMANAL, dia_da_semana=1, hora="02:00"),
            _quando("2026-08-25T10:00"),
        )
        assert proxima == _quando("2026-09-01T02:00")

    def test_mensal_no_dia_escolhido(self) -> None:
        proxima = proxima_execucao(
            Agendamento(tipo=TipoDeAgendamento.MENSAL, dia_do_mes=5, hora="04:00"),
            _quando("2026-08-25T10:00"),
        )
        assert proxima == _quando("2026-09-05T04:00")

    def test_dia_31_cai_para_o_ultimo_dia_do_mes_curto(self) -> None:
        """
        Quem marcou dia 31 quer "fim do mês".

        Pular fevereiro perderia a cópia mensal justamente no mês mais curto.
        """
        proxima = proxima_execucao(
            Agendamento(tipo=TipoDeAgendamento.MENSAL, dia_do_mes=31, hora="04:00"),
            _quando("2026-02-01T10:00"),
        )
        assert proxima == _quando("2026-02-28T04:00")


class TestSerializacao:
    def test_ida_e_volta_preserva_tudo(self) -> None:
        original = Politica(
            origens=["C:\\dados"],
            destino=Destino(tipo=TipoDeDestino.EXTERNO, caminho="E:\\backups"),
            agendamento=Agendamento(tipo=TipoDeAgendamento.DIARIO, hora="03:30"),
            retencao=Retencao(diarias=14, semanais=8, mensais=6),
            notificacao=Notificacao(quando=QuandoNotificar.SEMPRE, emails=["dono@padaria.com.br"]),
            usar_vss=True,
            cifrar=True,
        )

        relida = Politica.de_json(original.como_json())

        assert relida == original

    def test_texto_vazio_vira_politica_padrao(self) -> None:
        """
        Política recém-criada, sem configuração ainda, não pode derrubar nada.

        Ela simplesmente não dispara sozinha.
        """
        assert Politica.de_json("").agendamento.tipo is TipoDeAgendamento.DESLIGADO

    def test_json_invalido_levanta_em_vez_de_inventar(self) -> None:
        """
        Cair para o padrão aqui esconderia uma política corrompida.

        A pessoa acharia que configurou retenção e destino externo, e estaria
        rodando com o padrão — que não protege contra nada.
        """
        with pytest.raises(ValidationError):
            Politica.de_json('{"retencao": {"diarias": 0, "semanais": 0, "mensais": 0}}')
