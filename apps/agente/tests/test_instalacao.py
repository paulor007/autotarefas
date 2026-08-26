"""O Agente como servico da maquina (G.8.1).

Um Agente que so roda enquanto alguem deixa o terminal aberto nao e backup
automatico — e backup manual com passos a mais. Esta etapa registra o Agente no
Agendador de Tarefas do Windows.

O teste que carrega o peso e `test_fora_do_windows_recusa_em_vez_de_fingir`.
Dizer "instalado" onde nao ha nada instalado e a pior mentira possivel aqui: o
cliente iria embora achando que o backup roda sozinho, e descobriria o
contrario no dia em que precisasse restaurar.

O `schtasks` de verdade nao e chamado: criar tarefa no Agendador da maquina de
quem roda a suite seria efeito colateral inaceitavel num teste. O que se
verifica e a **decisao** — quais argumentos vao, o que acontece quando o
sistema recusa, e o que a mensagem diz a quem leu.
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from apps.agente.agente import instalacao


def _resposta(codigo: int = 0, saida: str = "", erro: str = "") -> Any:
    return subprocess.CompletedProcess(
        args=["schtasks"], returncode=codigo, stdout=saida, stderr=erro
    )


@pytest.fixture
def no_windows(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Finge Windows e captura os argumentos entregues ao `schtasks`."""
    chamadas: list[list[str]] = []

    monkeypatch.setattr(instalacao, "e_windows", lambda: True)

    def registrar(argumentos: list[str]) -> Any:
        chamadas.append(argumentos)
        return _resposta()

    monkeypatch.setattr(instalacao, "_rodar", registrar)
    return chamadas


class TestForaDoWindows:
    def test_fora_do_windows_recusa_em_vez_de_fingir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Nao ha "instalado" onde nada foi instalado.

        Fingir aqui faria o cliente ir embora achando que o backup roda
        sozinho — e ele so descobriria o contrario no dia em que precisasse.
        """
        monkeypatch.setattr(instalacao, "e_windows", lambda: False)

        with pytest.raises(instalacao.InstalacaoRecusada, match="so existe no Windows"):
            instalacao.instalar()

    def test_situacao_fora_do_windows_e_nao_registrada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(instalacao, "e_windows", lambda: False)

        resultado = instalacao.situacao()

        assert resultado.registrada is False
        assert "fora do Windows" in resultado.detalhe


class TestRegistro:
    def test_padrao_dispara_ao_entrar_e_nao_pede_elevacao(
        self, no_windows: list[list[str]]
    ) -> None:
        """
        O caso normal e um computador de escritorio que alguem liga de manha.

        Exigir elevacao no modo padrao travaria a instalacao na primeira tela
        de uma micro empresa.
        """
        resultado = instalacao.instalar()

        assert resultado.registrada is True
        assert resultado.modo is instalacao.Modo.AGENDADOR
        argumentos = no_windows[0]
        assert "/SC" in argumentos
        assert argumentos[argumentos.index("/SC") + 1] == "ONLOGON"
        assert "SYSTEM" not in argumentos

    def test_ao_ligar_roda_como_sistema(self, no_windows: list[list[str]]) -> None:
        instalacao.instalar(ao_ligar=True)

        argumentos = no_windows[0]
        assert argumentos[argumentos.index("/SC") + 1] == "ONSTART"
        assert argumentos[argumentos.index("/RU") + 1] == "SYSTEM"

    def test_instalar_de_novo_substitui_em_vez_de_duplicar(
        self, no_windows: list[list[str]]
    ) -> None:
        """
        Sem `/F`, atualizar o Agente falharia com "ja existe" — e a maquina
        continuaria rodando a versao velha.
        """
        instalacao.instalar()

        assert "/F" in no_windows[0]

    def test_o_nome_da_tarefa_e_estavel(self, no_windows: list[list[str]]) -> None:
        instalacao.instalar()

        argumentos = no_windows[0]
        assert argumentos[argumentos.index("/TN") + 1] == instalacao.NOME_DA_TAREFA

    def test_o_comando_aponta_para_este_python(self, no_windows: list[list[str]]) -> None:
        """
        A maquina do cliente pode ter varios Pythons.

        Apontar para "python" deixaria o sistema escolher — provavelmente o
        errado, e so na primeira madrugada alguem descobriria.
        """
        import sys

        instalacao.instalar()

        argumentos = no_windows[0]
        linha = argumentos[argumentos.index("/TR") + 1]
        assert sys.executable.replace("\\", "/").lower() in linha.replace("\\", "/").lower()
        assert "apps.agente.agente" in linha
        assert "servico" in linha

    def test_comando_proprio_e_respeitado(self, no_windows: list[list[str]]) -> None:
        instalacao.instalar(comando='"C:\\App\\agente.exe" servico')

        argumentos = no_windows[0]
        assert argumentos[argumentos.index("/TR") + 1] == '"C:\\App\\agente.exe" servico'


class TestRecusaDoSistema:
    def test_acesso_negado_ao_ligar_diz_o_que_fazer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        "Acesso negado" sozinho nao diz a ninguem o que fazer.

        "Abra o terminal como administrador" diz — e essa e a unica diferenca
        entre um erro util e um chamado de suporte.
        """
        monkeypatch.setattr(instalacao, "e_windows", lambda: True)
        monkeypatch.setattr(
            instalacao, "_rodar", lambda _a: _resposta(codigo=1, erro="ERRO: Acesso negado.")
        )

        with pytest.raises(instalacao.InstalacaoRecusada, match="terminal como administrador"):
            instalacao.instalar(ao_ligar=True)

    def test_recusa_no_modo_padrao_cai_para_o_logon_do_usuario(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        O caso que a suite antiga nao cobria — e que aconteceu de verdade.

        Numa maquina Windows 11 comum, `ONLOGON` responde "Acesso negado" mesmo
        sem `/RU`. Desistir aqui deixaria o cliente sem backup automatico por
        causa de uma politica que ele nem sabe que tem. A queda para a lista de
        logon do usuario nao precisa de elevacao.
        """
        gravados: list[str] = []
        monkeypatch.setattr(instalacao, "e_windows", lambda: True)
        monkeypatch.setattr(
            instalacao, "_rodar", lambda _a: _resposta(codigo=1, erro="ERRO: Acesso negado.")
        )
        monkeypatch.setattr(instalacao, "gravar_no_logon", gravados.append)

        resultado = instalacao.instalar(comando="agente.exe --servico")

        assert resultado.registrada is True
        assert resultado.modo is instalacao.Modo.LOGON
        assert gravados == ["agente.exe --servico"]

    def test_a_queda_diz_o_que_se_perde(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Os dois caminhos nao sao equivalentes, e a diferenca importa.

        Pela lista de logon, o backup so acontece com a sessao daquele usuario
        aberta. Chamar isso de "instalado" sem dizer faria alguem contar com um
        backup de madrugada que nao vai acontecer numa maquina deslogada.
        """
        monkeypatch.setattr(instalacao, "e_windows", lambda: True)
        monkeypatch.setattr(
            instalacao, "_rodar", lambda _a: _resposta(codigo=1, erro="ERRO: Acesso negado.")
        )
        monkeypatch.setattr(instalacao, "gravar_no_logon", lambda _c: None)

        detalhe = instalacao.instalar().detalhe

        assert "VOCE entra no Windows" in detalhe
        assert "administrador" in detalhe

    def test_se_os_dois_falharem_a_recusa_sobe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Sem caminho nenhum, e recusa — e nao um "instalado" que nao instalou.

        E o unico desfecho em que o instalador tem que interromper a boa
        noticia: o backup agendado nao vai acontecer.
        """

        def registro_fechado(_comando: str) -> None:
            raise OSError("registro bloqueado por politica")

        monkeypatch.setattr(instalacao, "e_windows", lambda: True)
        monkeypatch.setattr(
            instalacao, "_rodar", lambda _a: _resposta(codigo=1, erro="ERRO: Acesso negado.")
        )
        monkeypatch.setattr(instalacao, "gravar_no_logon", registro_fechado)

        with pytest.raises(instalacao.InstalacaoRecusada, match="administrador"):
            instalacao.instalar()

    def test_ao_ligar_nao_cai_para_o_logon(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Quem pediu `--ao-ligar` pediu backup sem ninguem logado.

        Cair para a lista de logon entregaria exatamente o oposto do pedido, com
        cara de sucesso.
        """
        monkeypatch.setattr(instalacao, "e_windows", lambda: True)
        monkeypatch.setattr(
            instalacao, "_rodar", lambda _a: _resposta(codigo=1, erro="ERRO: Acesso negado.")
        )
        monkeypatch.setattr(
            instalacao,
            "gravar_no_logon",
            lambda _c: pytest.fail("nao devia ter caido para o logon"),
        )

        with pytest.raises(instalacao.InstalacaoRecusada, match="AO LIGAR"):
            instalacao.instalar(ao_ligar=True)


class TestRemocao:
    def test_remover_usa_delete_forcado(
        self, no_windows: list[list[str]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(instalacao, "apagar_do_logon", lambda: False)
        resultado = instalacao.desinstalar()

        assert resultado.registrada is False
        assert no_windows[0][:2] == ["/Delete", "/TN"]
        assert "/F" in no_windows[0]

    def test_remover_o_que_nao_existia_nao_e_erro(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Desinstalar duas vezes nao pode quebrar um instalador.

        O estado desejado — "nao sobe mais sozinho" — foi alcancado nas duas.
        """
        monkeypatch.setattr(instalacao, "e_windows", lambda: True)
        monkeypatch.setattr(instalacao, "_rodar", lambda _a: _resposta(codigo=1))
        monkeypatch.setattr(instalacao, "apagar_do_logon", lambda: False)

        resultado = instalacao.desinstalar()

        assert resultado.registrada is False
        assert "nao estava registrado" in resultado.detalhe

    def test_remover_tira_tambem_da_lista_de_logon(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Sao dois lugares, e o Agente pode estar em qualquer um deles.

        Limpar so o Agendador deixaria o Agente subindo pela lista de logon —
        depois de a pessoa ter pedido para ele parar.
        """
        monkeypatch.setattr(instalacao, "e_windows", lambda: True)
        monkeypatch.setattr(instalacao, "_rodar", lambda _a: _resposta(codigo=1))
        monkeypatch.setattr(instalacao, "apagar_do_logon", lambda: True)

        resultado = instalacao.desinstalar()

        assert resultado.registrada is False
        assert "lista de logon" in resultado.detalhe


class TestSituacao:
    def test_registrada_quando_o_sistema_encontra(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(instalacao, "e_windows", lambda: True)
        monkeypatch.setattr(
            instalacao, "_rodar", lambda _a: _resposta(saida="AutoTarefas Agente  Pronto")
        )

        assert instalacao.situacao().registrada is True

    def test_encontra_o_registro_na_lista_de_logon(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Sem esta consulta, a tela diria "nao sobe sozinho" para um Agente que
        sobe — pelo outro caminho.
        """
        monkeypatch.setattr(instalacao, "e_windows", lambda: True)
        monkeypatch.setattr(instalacao, "_rodar", lambda _a: _resposta(codigo=1))
        monkeypatch.setattr(instalacao, "ler_do_logon", lambda: "agente.exe --servico")

        resultado = instalacao.situacao()

        assert resultado.registrada is True
        assert resultado.modo is instalacao.Modo.LOGON

    def test_nao_registrada_quando_o_sistema_nao_encontra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A pergunta e feita ao sistema toda vez.

        Guardar a resposta num arquivo faria a tela dizer "instalado" para uma
        tarefa que alguem removeu pelo Agendador.
        """
        monkeypatch.setattr(instalacao, "e_windows", lambda: True)
        monkeypatch.setattr(instalacao, "_rodar", lambda _a: _resposta(codigo=1))
        monkeypatch.setattr(instalacao, "ler_do_logon", lambda: "")

        resultado = instalacao.situacao()

        assert resultado.registrada is False
        assert "nao esta registrado" in resultado.detalhe

    def test_sem_schtasks_nao_quebra_o_estado(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Windows sem `schtasks` e estranho, mas nao pode derrubar o Agente."""
        monkeypatch.setattr(instalacao, "e_windows", lambda: True)

        def sem_agendador(_a: list[str]) -> Any:
            raise instalacao.InstalacaoRecusada("nao encontrei o Agendador de Tarefas")

        monkeypatch.setattr(instalacao, "_rodar", sem_agendador)

        resultado = instalacao.situacao()

        assert resultado.registrada is False
        assert "Agendador" in resultado.detalhe
