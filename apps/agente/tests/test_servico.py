"""O servico do Agente: canal e agendador juntos (02.E).

A independencia entre os dois e o que se testa aqui. Se o agendador dependesse
do canal, o backup pararia sempre que a internet caisse — justamente quando
ninguem esta olhando.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from apps.agente.agente import identidade as ident
from apps.agente.agente.agendador import PoliticaLocal
from apps.agente.agente.config import Configuracao, Local
from apps.agente.agente.servico import Servico
from autotarefas.tasks.politica import Politica


@pytest.fixture
def servico(tmp_path: Path) -> Servico:
    local = Local(pasta=tmp_path / "cfg")
    local.gravar(Configuracao(servidor="http://127.0.0.1:9", dispositivo_id="d1"))
    guarda = ident.Guarda(tmp_path / "cfg", usar_cofre_do_sistema=False)
    ident.obter_ou_criar(guarda)
    return Servico(local=local, guarda=guarda)


class TestIndependencia:
    def test_o_agendador_roda_mesmo_com_o_servidor_fora_do_ar(self, servico: Servico) -> None:
        """
        O teste que sustenta "backup com o navegador fechado".

        O servidor aqui e um endereco morto: o canal nao conecta. O agendador
        precisa rodar assim mesmo.
        """
        passadas = {"n": 0}

        async def contar() -> list[dict[str, Any]]:
            passadas["n"] += 1
            return []

        servico.agendador.rodada = contar  # type: ignore[method-assign]

        async def dormir(_s: float) -> None:
            return None

        servico.agendador.dormir = dormir  # type: ignore[assignment]

        asyncio.run(asyncio.wait_for(servico.rodar(passadas_do_agendador=3), timeout=30))

        assert passadas["n"] == 3

    def test_falha_no_canal_nao_cancela_o_agendador(self, servico: Servico) -> None:
        """
        Um canal que caiu nao pode levar o agendamento junto.

        E exatamente ai que o backup mais importa.
        """
        passadas = {"n": 0}

        async def contar() -> list[dict[str, Any]]:
            passadas["n"] += 1
            return []

        async def canal_que_explode() -> None:
            msg = "rede caiu"
            raise RuntimeError(msg)

        async def dormir(_s: float) -> None:
            return None

        servico.agendador.rodada = contar  # type: ignore[method-assign]
        servico.agendador.dormir = dormir  # type: ignore[assignment]
        servico._canal = canal_que_explode  # type: ignore[method-assign]

        asyncio.run(asyncio.wait_for(servico.rodar(passadas_do_agendador=2), timeout=30))

        assert passadas["n"] == 2


class TestLigacaoComOsComandos:
    def test_o_comando_de_politica_alcanca_o_agendador(self, servico: Servico) -> None:
        """
        Sem esta ligacao, o servidor mandaria a politica e ela nao seria
        gravada em lugar nenhum — a tela diria "aplicada" e a maquina
        continuaria sem agendamento.
        """
        from apps.agente.agente import comandos

        servico._ensinar_o_agendador_ao_canal()

        async def relatar(_d: dict[str, Any]) -> None:
            return None

        contexto = comandos.Contexto(configuracao=servico.local.carregar(), relatar=relatar)
        mensagem = {
            "tipo": "comando",
            "id": "c1",
            "acao": "politicas",
            "parametros": {
                "politicas": [
                    {
                        "id": "p1",
                        "nome": "Diária",
                        "configuracao": {"agendamento": {"tipo": "diario", "hora": "02:00"}},
                    }
                ]
            },
        }

        resultado = asyncio.run(comandos.atender(mensagem, servico.registro, contexto))

        assert resultado["ok"] is True
        assert resultado["politicas"] == 1
        assert servico.agendador.arquivo.is_file()
        assert len(servico.agendador.carregar()) == 1

    def test_situacao_relata_o_que_aconteceu_na_maquina(self, servico: Servico) -> None:
        """
        E o que o Live mostra quando a maquina reconecta.

        Sem isto, um backup que rodou de madrugada com a internet caida
        ficaria invisivel.
        """
        from apps.agente.agente import comandos

        servico._ensinar_o_agendador_ao_canal()
        servico.agendador.substituir([PoliticaLocal(id="p1", nome="Diária", politica=Politica())])
        servico.agendador.politicas[0].ultimo_resultado = "sucesso"
        servico.agendador.politicas[0].ultima_execucao = "2026-08-25T02:10:00"

        async def relatar(_d: dict[str, Any]) -> None:
            return None

        contexto = comandos.Contexto(configuracao=servico.local.carregar(), relatar=relatar)
        resultado = asyncio.run(
            comandos.atender(
                {"tipo": "comando", "id": "c2", "acao": "situacao", "parametros": {}},
                servico.registro,
                contexto,
            )
        )

        assert resultado["politicas"][0]["ultimo_resultado"] == "sucesso"


class TestDiarioDeExecucoes:
    """
    O agendamento escreve o que fez, antes de tentar contar a alguem (G.7.1).

    A internet costuma estar caida de madrugada, que e quando o agendamento
    roda. Se o registro dependesse do envio, esse backup nao existiria no
    historico do Live.
    """

    @staticmethod
    def _politica() -> PoliticaLocal:
        return PoliticaLocal(id="p1", nome="Diária da loja", politica=Politica())

    def test_execucao_bem_sucedida_vira_linha_no_diario(
        self, servico: Servico, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fingir(_p: Politica, _c: Configuracao) -> dict[str, Any]:
            return {
                "ok": True,
                "pacote": "backup_2026-08-25_0200.zip",
                "tamanho_bytes": 2048,
                "sha256": "b" * 64,
                "arquivos": 7,
                "com_ressalva": False,
            }

        monkeypatch.setattr("apps.agente.agente.servico.executar_politica", fingir)

        asyncio.run(servico._executar_politica(self._politica()))

        registros = servico.diario.todas()
        assert len(registros) == 1
        assert registros[0]["resultado"] == "sucesso"
        assert registros[0]["arquivos"] == 7
        assert registros[0]["artefato"]["nome"] == "backup_2026-08-25_0200.zip"
        assert registros[0]["origem"] == "agendamento"

    def test_falha_tambem_vira_linha_e_a_excecao_continua_subindo(
        self, servico: Servico, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Falha registrada e informacao; falha silenciosa e um historico que
        mente por omissao.

        A excecao precisa continuar subindo para o retry do agendador
        acontecer — registrar nao pode virar engolir.
        """

        async def explodir(_p: Politica, _c: Configuracao) -> dict[str, Any]:
            msg = "disco externo desconectado"
            raise RuntimeError(msg)

        monkeypatch.setattr("apps.agente.agente.servico.executar_politica", explodir)

        with pytest.raises(RuntimeError, match="disco externo"):
            asyncio.run(servico._executar_politica(self._politica()))

        registros = servico.diario.todas()
        assert len(registros) == 1
        assert registros[0]["resultado"] == "falha"
        assert "disco externo" in registros[0]["ressalva"]
        assert registros[0]["artefato"] is None

    def test_ressalva_nao_e_contada_como_sucesso_limpo(
        self, servico: Servico, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Backup que copiou quase tudo nao e sucesso nem falha.

        Chama-lo de sucesso esconderia as ausencias de quem um dia vai
        restaurar.
        """

        async def com_ressalva(_p: Politica, _c: Configuracao) -> dict[str, Any]:
            return {
                "ok": True,
                "pacote": "backup_2026-08-25_0200.zip",
                "tamanho_bytes": 10,
                "arquivos": 2,
                "com_ressalva": True,
                "ressalva": "1 arquivo(s) nao entraram",
            }

        monkeypatch.setattr("apps.agente.agente.servico.executar_politica", com_ressalva)

        asyncio.run(servico._executar_politica(self._politica()))

        registros = servico.diario.todas()
        assert registros[0]["resultado"] == "com_ressalva"
        assert registros[0]["ressalva"] == "1 arquivo(s) nao entraram"

    def test_cada_tentativa_vira_uma_linha_com_o_numero(
        self, servico: Servico, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Retry so e comprovavel se cada tentativa deixar rastro.

        Uma linha unica dizendo "falhou" nao distingue "tentou uma vez" de
        "insistiu tres vezes com espera crescente" — e e essa diferenca que
        diz se o problema foi um tropeco ou um disco que nao volta.
        """

        async def explodir(_p: Politica, _c: Configuracao) -> dict[str, Any]:
            msg = "disco externo desconectado"
            raise RuntimeError(msg)

        async def sem_espera(_s: float) -> None:
            return None

        monkeypatch.setattr("apps.agente.agente.servico.executar_politica", explodir)
        servico.agendador.dormir = sem_espera  # type: ignore[assignment]

        item = self._politica()
        item.politica = Politica.model_validate({"retry": {"tentativas": 3}})
        asyncio.run(servico.agendador.disparar(item))

        registros = servico.diario.todas()
        assert len(registros) == 3, "cada tentativa precisa de uma linha propria"
        assert "tentativa 2" in registros[1]["ressalva"]
        assert "tentativa 3" in registros[2]["ressalva"]
        assert all(linha["resultado"] == "falha" for linha in registros)
