"""Agendador local (02.E).

Este módulo é o que separa "o cliente pode mandar fazer backup" de "o cliente
tem backup". Os testes cobrem as quatro decisões que, erradas, produzem
silêncio — o pior desfecho possível deste produto:

- máquina desligada por uma semana **não** dispara sete backups ao ligar;
- reconexão frequente **não** empurra o horário para sempre;
- falha transitória é retentada, com espera crescente;
- exceção dentro de uma política **não** derruba o laço das outras.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from apps.agente.agente.agendador import Agendador, PoliticaLocal
from apps.agente.agente.config import Local
from autotarefas.tasks.politica import Agendamento, Politica, Retry, TipoDeAgendamento


class Relogio:
    """Relógio controlado pelo teste. Um agendamento diário real levaria um dia."""

    def __init__(self, inicio: datetime) -> None:
        self.agora = inicio

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, delta: timedelta) -> None:
        self.agora += delta


def _politica(hora: str = "02:00", **extras: Any) -> Politica:
    return Politica(agendamento=Agendamento(tipo=TipoDeAgendamento.DIARIO, hora=hora), **extras)


def _montar(
    tmp_path: Path,
    relogio: Relogio,
    executar: Any,
) -> Agendador:
    esperas: list[float] = []

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        # O tempo "passa" no relógio do teste, sem espera de verdade.
        relogio.avancar(timedelta(seconds=segundos))

    agendador = Agendador(
        local=Local(pasta=tmp_path / "cfg"),
        executar=executar,
        relogio=relogio,
        dormir=dormir,
    )
    agendador.esperas = esperas  # type: ignore[attr-defined]
    return agendador


class TestPersistencia:
    def test_politica_sobrevive_ao_reinicio(self, tmp_path: Path) -> None:
        """
        O agendamento vive no DISCO da máquina, não na memória do servidor.

        Sem isso, reiniciar o computador perderia o horário — e ninguém
        perceberia até o dia de precisar do backup.
        """
        relogio = Relogio(datetime(2026, 8, 25, 10, 0))

        async def nada(_item: PoliticaLocal) -> dict[str, Any]:
            return {"ok": True}

        primeiro = _montar(tmp_path, relogio, nada)
        primeiro.substituir([PoliticaLocal(id="p1", nome="Diária", politica=_politica())])

        segundo = _montar(tmp_path, relogio, nada)
        carregadas = segundo.carregar()

        assert len(carregadas) == 1
        assert carregadas[0].id == "p1"
        assert carregadas[0].proxima == datetime(2026, 8, 26, 2, 0)

    def test_arquivo_corrompido_nao_derruba_o_servico(self, tmp_path: Path) -> None:
        """
        JSON quebrado não pode impedir o serviço de subir.

        O que se perde é o agendamento, e isso aparece como "nenhuma
        política" — que é verdade e é acionável.
        """
        relogio = Relogio(datetime(2026, 8, 25, 10, 0))

        async def nada(_item: PoliticaLocal) -> dict[str, Any]:
            return {"ok": True}

        agendador = _montar(tmp_path, relogio, nada)
        agendador.local.pasta.mkdir(parents=True)
        agendador.arquivo.write_text("{quebrado", encoding="utf-8")

        assert agendador.carregar() == []

    def test_gravacao_nao_deixa_arquivo_parcial(self, tmp_path: Path) -> None:
        relogio = Relogio(datetime(2026, 8, 25, 10, 0))

        async def nada(_item: PoliticaLocal) -> dict[str, Any]:
            return {"ok": True}

        agendador = _montar(tmp_path, relogio, nada)
        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=_politica())])

        assert not agendador.arquivo.with_suffix(".parcial").exists()


class TestSincronizacao:
    def test_reconexao_nao_empurra_o_horario(self, tmp_path: Path) -> None:
        """
        O teste que evita o backup que nunca acontece.

        A máquina reconecta às 01:59, o servidor reenvia a mesma política, o
        próximo disparo vira amanhã — e nunca são 02:00. Política que não
        mudou mantém o horário que já tinha.
        """
        relogio = Relogio(datetime(2026, 8, 25, 10, 0))

        async def nada(_item: PoliticaLocal) -> dict[str, Any]:
            return {"ok": True}

        agendador = _montar(tmp_path, relogio, nada)
        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=_politica())])
        agendado = agendador.politicas[0].proxima

        relogio.avancar(timedelta(hours=15, minutes=59))  # 01:59 do dia seguinte
        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=_politica())])

        assert agendador.politicas[0].proxima == agendado

    def test_politica_alterada_recalcula_o_horario(self, tmp_path: Path) -> None:
        relogio = Relogio(datetime(2026, 8, 25, 10, 0))

        async def nada(_item: PoliticaLocal) -> dict[str, Any]:
            return {"ok": True}

        agendador = _montar(tmp_path, relogio, nada)
        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=_politica("02:00"))])

        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=_politica("23:00"))])

        assert agendador.politicas[0].proxima == datetime(2026, 8, 25, 23, 0)

    def test_politica_removida_no_servidor_some_da_maquina(self, tmp_path: Path) -> None:
        relogio = Relogio(datetime(2026, 8, 25, 10, 0))

        async def nada(_item: PoliticaLocal) -> dict[str, Any]:
            return {"ok": True}

        agendador = _montar(tmp_path, relogio, nada)
        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=_politica())])
        agendador.substituir([])

        assert agendador.politicas == []


class TestDisparo:
    def test_dispara_quando_chega_a_hora(self, tmp_path: Path) -> None:
        relogio = Relogio(datetime(2026, 8, 25, 1, 59))
        disparadas: list[str] = []

        async def executar(item: PoliticaLocal) -> dict[str, Any]:
            disparadas.append(item.id)
            return {"ok": True}

        agendador = _montar(tmp_path, relogio, executar)
        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=_politica())])

        asyncio.run(agendador.rodada())
        assert disparadas == []

        relogio.avancar(timedelta(minutes=2))
        asyncio.run(agendador.rodada())

        assert disparadas == ["p1"]

    def test_depois_de_executar_reagenda_para_o_dia_seguinte(self, tmp_path: Path) -> None:
        """
        Reagendar a partir do FIM da execução evita o laço em que um backup de
        duas horas encontra o próprio horário já vencido ao terminar.
        """
        relogio = Relogio(datetime(2026, 8, 25, 2, 0))

        async def executar(_item: PoliticaLocal) -> dict[str, Any]:
            relogio.avancar(timedelta(hours=2))
            return {"ok": True}

        agendador = _montar(tmp_path, relogio, executar)
        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=_politica())])
        agendador.politicas[0].proxima = datetime(2026, 8, 25, 2, 0)

        asyncio.run(agendador.rodada())

        assert agendador.politicas[0].proxima == datetime(2026, 8, 26, 2, 0)

    def test_maquina_desligada_por_uma_semana_dispara_uma_vez_so(self, tmp_path: Path) -> None:
        """
        Disparar sete backups ao ligar encheria o disco e demoraria horas.

        A janela perdida é registrada e o horário volta ao normal.
        """
        relogio = Relogio(datetime(2026, 8, 25, 2, 0))
        disparadas: list[str] = []

        async def executar(item: PoliticaLocal) -> dict[str, Any]:
            disparadas.append(item.id)
            return {"ok": True}

        agendador = _montar(tmp_path, relogio, executar)
        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=_politica())])
        agendador.politicas[0].proxima = datetime(2026, 8, 18, 2, 0)

        relogio.avancar(timedelta(0))
        asyncio.run(agendador.rodada())

        assert disparadas == []
        assert agendador.politicas[0].ultimo_resultado == "perdida"
        assert "desligada" in agendador.politicas[0].ultima_ressalva
        assert agendador.politicas[0].proxima == datetime(2026, 8, 26, 2, 0)

    def test_politica_sem_agendamento_nunca_dispara_sozinha(self, tmp_path: Path) -> None:
        relogio = Relogio(datetime(2026, 8, 25, 2, 0))
        disparadas: list[str] = []

        async def executar(item: PoliticaLocal) -> dict[str, Any]:
            disparadas.append(item.id)
            return {"ok": True}

        agendador = _montar(tmp_path, relogio, executar)
        agendador.substituir([PoliticaLocal(id="p1", nome="Manual", politica=Politica())])

        asyncio.run(agendador.rodada())

        assert disparadas == []
        assert agendador.politicas[0].proxima is None


class TestRetry:
    def test_falha_transitoria_e_retentada(self, tmp_path: Path) -> None:
        """
        Disco externo desconectado por um minuto é a regra, não a exceção.

        Desistir na primeira faria o backup depender de sorte.
        """
        relogio = Relogio(datetime(2026, 8, 25, 2, 0))
        tentativas = {"n": 0}

        async def executar(_item: PoliticaLocal) -> dict[str, Any]:
            tentativas["n"] += 1
            if tentativas["n"] < 3:
                return {"ok": False, "erro": "disco externo nao encontrado"}
            return {"ok": True}

        agendador = _montar(tmp_path, relogio, executar)
        politica = _politica()
        politica.retry = Retry(tentativas=3, espera_inicial_min=5, fator=2.0)
        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=politica)])
        agendador.politicas[0].proxima = datetime(2026, 8, 25, 2, 0)

        asyncio.run(agendador.rodada())

        assert tentativas["n"] == 3
        assert agendador.politicas[0].ultimo_resultado == "sucesso"

    def test_a_espera_cresce_entre_as_tentativas(self, tmp_path: Path) -> None:
        relogio = Relogio(datetime(2026, 8, 25, 2, 0))

        async def executar(_item: PoliticaLocal) -> dict[str, Any]:
            return {"ok": False, "erro": "falhou"}

        agendador = _montar(tmp_path, relogio, executar)
        politica = _politica()
        politica.retry = Retry(tentativas=3, espera_inicial_min=5, fator=2.0)
        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=politica)])
        agendador.politicas[0].proxima = datetime(2026, 8, 25, 2, 0)

        asyncio.run(agendador.rodada())

        assert agendador.esperas == [5 * 60, 10 * 60]  # type: ignore[attr-defined]

    def test_esgotadas_as_tentativas_registra_falha_com_o_motivo(self, tmp_path: Path) -> None:
        relogio = Relogio(datetime(2026, 8, 25, 2, 0))

        async def executar(_item: PoliticaLocal) -> dict[str, Any]:
            return {"ok": False, "erro": "pasta de rede indisponivel"}

        agendador = _montar(tmp_path, relogio, executar)
        politica = _politica()
        politica.retry = Retry(tentativas=2, espera_inicial_min=1, fator=1.0)
        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=politica)])
        agendador.politicas[0].proxima = datetime(2026, 8, 25, 2, 0)

        asyncio.run(agendador.rodada())

        assert agendador.politicas[0].ultimo_resultado == "falha"
        assert "pasta de rede" in agendador.politicas[0].ultima_ressalva

    def test_excecao_no_executor_nao_derruba_o_laco(self, tmp_path: Path) -> None:
        """
        Uma política que explode não pode levar as outras junto.

        Um serviço que morre à noite é um backup que não acontece, e ninguém
        descobre até precisar.
        """
        relogio = Relogio(datetime(2026, 8, 25, 2, 0))
        disparadas: list[str] = []

        async def executar(item: PoliticaLocal) -> dict[str, Any]:
            disparadas.append(item.id)
            if item.id == "explode":
                msg = "algo inesperado"
                raise RuntimeError(msg)
            return {"ok": True}

        agendador = _montar(tmp_path, relogio, executar)
        politica = _politica()
        politica.retry = Retry(tentativas=1, espera_inicial_min=1, fator=1.0)
        agendador.substituir(
            [
                PoliticaLocal(id="explode", nome="A", politica=politica),
                PoliticaLocal(id="ok", nome="B", politica=politica),
            ]
        )
        for item in agendador.politicas:
            item.proxima = datetime(2026, 8, 25, 2, 0)

        asyncio.run(agendador.rodada())

        assert disparadas == ["explode", "ok"]
        assert agendador.politicas[0].ultimo_resultado == "falha"
        assert agendador.politicas[1].ultimo_resultado == "sucesso"

    def test_ressalva_e_um_desfecho_proprio(self, tmp_path: Path) -> None:
        """
        Backup que copiou quase tudo não é sucesso nem falha.

        Chamar de sucesso esconderia o que ficou de fora.
        """
        relogio = Relogio(datetime(2026, 8, 25, 2, 0))

        async def executar(_item: PoliticaLocal) -> dict[str, Any]:
            return {"ok": True, "com_ressalva": True, "ressalva": "1 arquivo travado"}

        agendador = _montar(tmp_path, relogio, executar)
        agendador.substituir([PoliticaLocal(id="p1", nome="D", politica=_politica())])
        agendador.politicas[0].proxima = datetime(2026, 8, 25, 2, 0)

        asyncio.run(agendador.rodada())

        assert agendador.politicas[0].ultimo_resultado == "com_ressalva"
        assert "travado" in agendador.politicas[0].ultima_ressalva


def test_laco_continua_mesmo_quando_a_rodada_explode(tmp_path: Path) -> None:
    """
    O laço do serviço não pode morrer.

    Parar por conta própria significaria parar de fazer backup em silêncio.
    """
    relogio = Relogio(datetime(2026, 8, 25, 2, 0))
    passadas = {"n": 0}

    async def executar(_item: PoliticaLocal) -> dict[str, Any]:
        return {"ok": True}

    agendador = _montar(tmp_path, relogio, executar)

    async def rodada_que_explode() -> list[dict[str, Any]]:
        passadas["n"] += 1
        msg = "erro inesperado na rodada"
        raise RuntimeError(msg)

    agendador.rodada = rodada_que_explode  # type: ignore[method-assign]

    asyncio.run(agendador.rodar(passadas=3))

    assert passadas["n"] == 3
