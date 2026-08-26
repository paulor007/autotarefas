"""A instalacao de um clique, vista como decisoes (G.10.1).

O cliente do AutoTarefas nao abre terminal. O que se testa aqui e o que
acontece por baixo do duplo clique — e, principalmente, o que o instalador
**diz** quando algo nao deu certo.

O teste que carrega o peso e `test_sem_pasta_o_resumo_nao_diz_que_esta_pronto`.
Um instalador que termina sempre com "tudo certo" nao informa nada: a pessoa
fecha a janela tranquila e descobre na primeira madrugada que nao havia backup
nenhum.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from apps.agente.agente import assistente as mod
from apps.agente.agente import identidade as ident
from apps.agente.agente import instalacao, pareamento
from apps.agente.agente.assistente import Assistente, Passo
from apps.agente.agente.config import Configuracao, Local


@pytest.fixture
def instalador(tmp_path: Path) -> Assistente:
    pasta = tmp_path / "cfg"
    guarda = ident.Guarda(pasta, usar_cofre_do_sistema=False)
    return Assistente(
        local=Local(pasta=pasta),
        guarda=guarda,
        servidor="https://live.exemplo.com.br",
        codigo="ABC123",
        nome_da_maquina="PC da loja",
    )


class _Pareado:
    """O que `pareamento.parear` devolve quando da certo."""

    nome = "PC da loja"
    impressao = "AAAA-BBBB-CCCC-DDDD"


class TestPareamento:
    def test_pareia_e_mostra_a_impressao_para_conferir(
        self, instalador: Assistente, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A impressao aparece porque a pessoa precisa compara-la com o Live.

        E o unico momento em que ela olha duas telas — e nao da para evitar: e o
        que impede um servidor comprometido de se passar pela maquina dela.
        """
        monkeypatch.setattr(mod.pareamento, "parear", lambda **_: _Pareado())

        passo = instalador.parear()

        assert passo.ok is True
        assert "AAAA-BBBB-CCCC-DDDD" in passo.detalhe
        assert instalador.impressao == "AAAA-BBBB-CCCC-DDDD"

    def test_sem_codigo_nao_tenta_falar_com_o_servidor(self, instalador: Assistente) -> None:
        instalador.codigo = ""

        passo = instalador.parear()

        assert passo.ok is False
        assert "codigo" in passo.mensagem.lower()

    def test_sem_servidor_recusa_antes(self, instalador: Assistente) -> None:
        instalador.servidor = ""

        assert instalador.parear().ok is False

    @pytest.mark.parametrize(
        ("erro", "esperado"),
        [
            ("codigo expirado", "gere outro"),
            ("codigo ja usado", "gere outro"),
            ("falha de conexao com o servidor", "endereco e a internet"),
        ],
    )
    def test_a_recusa_diz_o_que_fazer(
        self,
        instalador: Assistente,
        monkeypatch: pytest.MonkeyPatch,
        erro: str,
        esperado: str,
    ) -> None:
        """
        "403" nao ajuda ninguem; "gere outro codigo no Live" ajuda.

        E a diferenca entre a pessoa resolver sozinha e ligar para o suporte.
        """

        def recusar(**_: Any) -> None:
            raise pareamento.PareamentoFalhou(erro)

        monkeypatch.setattr(mod.pareamento, "parear", recusar)

        passo = instalador.parear()

        assert passo.ok is False
        assert esperado in passo.mensagem.lower()

    def test_erro_desconhecido_chega_inteiro(
        self, instalador: Assistente, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Sem tradutor para tudo: o que nao se sabe explicar chega como veio.

        Trocar por "erro inesperado" apagaria a unica pista que existia.
        """

        def recusar(**_: Any) -> None:
            raise pareamento.PareamentoFalhou("o servidor devolveu 500")

        monkeypatch.setattr(mod.pareamento, "parear", recusar)

        assert "500" in instalador.parear().mensagem

    def test_reconhece_maquina_ja_pareada(self, instalador: Assistente) -> None:
        """
        Reinstalar por cima criaria um segundo dispositivo para a mesma maquina,
        e o historico da empresa teria duas linhas para um computador so.
        """
        assert instalador.ja_pareado() is False

        instalador.local.gravar(Configuracao(servidor="https://x", dispositivo_id="d1"))

        assert instalador.ja_pareado() is True


class TestAutorizacao:
    def test_autoriza_a_pasta_escolhida(self, instalador: Assistente, tmp_path: Path) -> None:
        pasta = tmp_path / "Financeiro"
        pasta.mkdir()

        passo = instalador.autorizar(pasta)

        assert passo.ok is True
        assert instalador.pastas == [str(pasta.resolve())]

    def test_a_segunda_pasta_nao_apaga_a_primeira(
        self, instalador: Assistente, tmp_path: Path
    ) -> None:
        """
        Uma empresa guarda o que importa em mais de um lugar.

        Documentos, a pasta do sistema de gestao, a planilha na area de
        trabalho. Se a segunda escolha substituisse a primeira, o instalador
        terminaria protegendo so a ultima — e ninguem perceberia ate precisar
        restaurar a que sumiu.
        """
        primeira = tmp_path / "Financeiro"
        segunda = tmp_path / "Contratos"
        primeira.mkdir()
        segunda.mkdir()

        assert instalador.autorizar(primeira).ok is True
        assert instalador.autorizar(segunda).ok is True

        assert instalador.pastas == [str(primeira.resolve()), str(segunda.resolve())]

    def test_a_mesma_pasta_duas_vezes_nao_duplica(
        self, instalador: Assistente, tmp_path: Path
    ) -> None:
        """Clicar duas vezes na mesma pasta e engano comum, e nao erro."""
        pasta = tmp_path / "Financeiro"
        pasta.mkdir()

        instalador.autorizar(pasta)
        instalador.autorizar(pasta)

        assert instalador.pastas == [str(pasta.resolve())]

    def test_o_seletor_bonito_nao_afrouxa_a_guarda(
        self, instalador: Assistente, tmp_path: Path
    ) -> None:
        """
        A janela poupa a pessoa de digitar; ela nao libera nada a mais.

        Pasta que nao existe continua recusada — pela mesma funcao que o comando
        de linha usa.
        """
        passo = instalador.autorizar(tmp_path / "nao-existe")

        assert passo.ok is False
        assert instalador.pastas == []


class TestServico:
    def test_registra_e_marca_que_sobe_sozinho(
        self, instalador: Assistente, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            mod.instalacao,
            "instalar",
            lambda **_: instalacao.Situacao(registrada=True, detalhe="tarefa criada"),
        )

        passo = instalador.instalar_servico()

        assert passo.ok is True
        assert instalador.sobe_sozinho is True

    def test_falhar_o_registro_nao_finge_que_deu_certo(
        self, instalador: Assistente, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        O pareamento e a pasta continuam valendo; o que se perde e o horario.

        Dizer isso e o oposto de mostrar "instalado" para quem nao vai ter
        backup agendado nenhum.
        """

        def recusar(**_: Any) -> None:
            raise instalacao.InstalacaoRecusada("o Agendador recusou")

        monkeypatch.setattr(mod.instalacao, "instalar", recusar)

        passo = instalador.instalar_servico()

        assert passo.ok is False
        assert "agendado nao vai acontecer" in passo.detalhe
        assert instalador.sobe_sozinho is False

    def test_sobe_o_agente_na_hora(
        self, instalador: Assistente, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Sem isto, a maquina so apareceria no Live depois de reiniciar — e a
        pessoa fecharia o instalador achando que deu errado.
        """
        chamadas: list[list[str]] = []

        def fingir(argumentos: list[str], **_: Any) -> object:
            chamadas.append(argumentos)
            return object()

        monkeypatch.setattr(mod.subprocess, "Popen", fingir)

        passo = instalador.iniciar_agora()

        assert passo.ok is True
        assert instalador.rodando is True
        assert "servico" in " ".join(chamadas[0])
        assert str(instalador.local.pasta) in " ".join(chamadas[0])

    def test_nao_conseguir_subir_agora_nao_e_o_fim(
        self, instalador: Assistente, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def explodir(*_: Any, **__: Any) -> object:
            raise OSError("acesso negado")

        monkeypatch.setattr(mod.subprocess, "Popen", explodir)

        passo = instalador.iniciar_agora()

        assert passo.ok is False
        assert "proximo login" in passo.detalhe
        assert instalador.rodando is False


class TestResumo:
    def test_sem_pasta_o_resumo_nao_diz_que_esta_pronto(self, instalador: Assistente) -> None:
        """
        O teste que sustenta os outros.

        Um instalador que termina sempre com "tudo certo" nao informa nada: a
        pessoa fecha a janela tranquila e descobre na primeira madrugada que nao
        havia backup nenhum.
        """
        instalador.sobe_sozinho = True

        passo = instalador.resumo()

        assert passo.ok is False
        assert "nao copia nada" in passo.detalhe

    def test_sem_horario_o_resumo_diz_que_falta_horario(
        self, instalador: Assistente, tmp_path: Path
    ) -> None:
        pasta = tmp_path / "Financeiro"
        pasta.mkdir()
        instalador.autorizar(pasta)

        passo = instalador.resumo()

        assert passo.ok is False
        assert "quando alguem mandar" in passo.detalhe

    def test_com_tudo_no_lugar_diz_que_esta_protegido(
        self, instalador: Assistente, tmp_path: Path
    ) -> None:
        pasta = tmp_path / "Financeiro"
        pasta.mkdir()
        instalador.autorizar(pasta)
        instalador.sobe_sozinho = True

        passo = instalador.resumo()

        assert passo.ok is True
        assert "protegido" in passo.mensagem
        assert "navegador fechado" in passo.detalhe


class TestComandoDoServico:
    def test_congelado_usa_o_proprio_executavel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        No `.exe` do cliente nao existe Python separado para chamar.

        Apontar para `python` la faria o Agendador tentar um programa que a
        maquina do cliente pode nao ter — e a falha so apareceria de madrugada.
        """
        monkeypatch.setattr(mod.sys, "frozen", True, raising=False)
        monkeypatch.setattr(mod.sys, "executable", r"C:\App\AutoTarefas-Agente.exe")

        argumentos = mod._argumentos_do_servico(Path(r"C:\cfg"))

        assert argumentos[0] == r"C:\App\AutoTarefas-Agente.exe"
        assert "--servico" in argumentos
        assert "-m" not in argumentos

    def test_do_codigo_usa_o_modulo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(mod.sys, "frozen", False, raising=False)

        argumentos = mod._argumentos_do_servico(Path(r"C:\cfg"))

        assert argumentos[1:3] == ["-m", "apps.agente.agente"]

    def test_a_linha_do_agendador_protege_caminho_com_espaco(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        `C:\\Program Files\\...` sem aspas vira dois argumentos para o Agendador.

        A tarefa seria criada, apareceria na lista, e simplesmente nao rodaria.
        """
        monkeypatch.setattr(mod.sys, "frozen", True, raising=False)
        monkeypatch.setattr(mod.sys, "executable", r"C:\Program Files\AutoTarefas\agente.exe")

        linha = mod._comando_do_servico(Path(r"C:\Users\Ana\App Data\cfg"))

        assert '"C:\\Program Files\\AutoTarefas\\agente.exe"' in linha
        assert '"C:\\Users\\Ana\\App Data\\cfg"' in linha


def test_passo_vira_dicionario_para_a_janela() -> None:
    assert Passo(True, "pronto", "detalhe").como_dicionario() == {
        "ok": True,
        "mensagem": "pronto",
        "detalhe": "detalhe",
    }
