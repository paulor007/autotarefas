"""Testes do protocolo de comandos (G.4.2).

O teste que carrega o peso e `test_reentrega_nao_executa_de_novo`. Rede ruim
faz reentrega: o servidor manda, a resposta se perde, ele manda de novo. Sem
idempotencia, isso vira dois backups — ou, pior, duas rotacoes de retencao, que
APAGAM arquivo. A garantia precisa estar no Agente, e nao na esperanca de que
a rede se comporte.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from apps.agente.agente import comandos
from apps.agente.agente.config import Configuracao


def _contexto(configuracao: Configuracao | None = None) -> comandos.Contexto:
    relatados: list[dict[str, Any]] = []

    async def relatar(dados: dict[str, Any]) -> None:
        relatados.append(dados)

    contexto = comandos.Contexto(configuracao=configuracao or Configuracao(), relatar=relatar)
    contexto.relatados = relatados  # type: ignore[attr-defined]
    return contexto


def _comando(acao: str, identificador: str = "c-1", **parametros: Any) -> dict[str, Any]:
    return {"tipo": "comando", "id": identificador, "acao": acao, "parametros": parametros}


class TestAtendimento:
    def test_executa_e_devolve_resultado(self) -> None:
        registro = comandos.Registro()

        async def somar(parametros: dict[str, Any], _contexto: comandos.Contexto) -> dict[str, Any]:
            return {"soma": parametros["a"] + parametros["b"]}

        registro.registrar("somar", somar)

        resultado = asyncio.run(
            comandos.atender(_comando("somar", a=2, b=3), registro, _contexto())
        )

        assert resultado["ok"] is True
        assert resultado["soma"] == 5
        assert resultado["comando"] == "c-1"

    def test_acao_desconhecida_nao_derruba_o_canal(self) -> None:
        """
        Um servidor mais novo pode pedir algo que este Agente nao sabe fazer.

        A resposta e "nao sei fazer isso", com a lista do que sabe — e nao uma
        conexao que cai em laco, quebrando a atualizacao gradual da frota.
        """
        registro = comandos.registro_padrao()

        resultado = asyncio.run(comandos.atender(_comando("inventada"), registro, _contexto()))

        assert resultado["ok"] is False
        assert "acao desconhecida" in resultado["erro"]
        assert "estado" in resultado["acoes_conhecidas"]

    def test_falha_do_executor_vira_resultado_e_nao_excecao(self) -> None:
        """
        Deixar a excecao subir derrubaria o canal.

        E com ele todos os outros comandos daquela maquina, inclusive os que
        nao tem nada a ver com o que falhou.
        """
        registro = comandos.Registro()

        async def quebrar(_p: dict[str, Any], _c: comandos.Contexto) -> dict[str, Any]:
            msg = "disco cheio"
            raise OSError(msg)

        registro.registrar("quebrar", quebrar)

        resultado = asyncio.run(comandos.atender(_comando("quebrar"), registro, _contexto()))

        assert resultado["ok"] is False
        assert "disco cheio" in resultado["erro"]

    def test_erro_nao_devolve_caminho_local_ao_servidor(self) -> None:
        """
        Rastro de pilha carrega caminho da maquina do cliente.

        Caminho local do cliente nao e assunto do Live: o rastro fica no log da
        maquina, e o servidor recebe so o tipo e a mensagem.
        """
        registro = comandos.Registro()

        async def quebrar(_p: dict[str, Any], _c: comandos.Contexto) -> dict[str, Any]:
            msg = r"falhou em C:\Users\alguem\Documentos\segredo.xlsx"
            raise OSError(msg)

        registro.registrar("quebrar", quebrar)

        resultado = asyncio.run(comandos.atender(_comando("quebrar"), registro, _contexto()))

        assert resultado["detalhe"] == ""
        assert "Traceback" not in str(resultado)


class TestIdempotencia:
    def test_reentrega_nao_executa_de_novo(self) -> None:
        """
        O motivo de existir identificador de comando.

        Rede ruim faz reentrega. Sem esta guarda, ela viraria dois backups —
        ou duas rotacoes de retencao, que apagam arquivo.
        """
        registro = comandos.Registro()
        vezes = {"n": 0}

        async def contar(_p: dict[str, Any], _c: comandos.Contexto) -> dict[str, Any]:
            vezes["n"] += 1
            return {"execucoes": vezes["n"]}

        registro.registrar("contar", contar)
        contexto = _contexto()

        primeira = asyncio.run(comandos.atender(_comando("contar"), registro, contexto))
        segunda = asyncio.run(comandos.atender(_comando("contar"), registro, contexto))

        assert vezes["n"] == 1
        assert primeira["execucoes"] == 1
        assert segunda["execucoes"] == 1
        assert segunda["reentregue"] is True

    def test_comandos_diferentes_executam_os_dois(self) -> None:
        """A guarda e por identificador, nao por acao."""
        registro = comandos.Registro()
        vezes = {"n": 0}

        async def contar(_p: dict[str, Any], _c: comandos.Contexto) -> dict[str, Any]:
            vezes["n"] += 1
            return {"execucoes": vezes["n"]}

        registro.registrar("contar", contar)
        contexto = _contexto()

        asyncio.run(comandos.atender(_comando("contar", "c-1"), registro, contexto))
        asyncio.run(comandos.atender(_comando("contar", "c-2"), registro, contexto))

        assert vezes["n"] == 2

    def test_memoria_nao_cresce_sem_limite(self) -> None:
        """
        Um servico que fica meses no ar nao pode acumular tudo o que ja fez.

        O teto e alto o bastante para cobrir reentrega real e baixo o bastante
        para a memoria nao virar problema.
        """
        registro = comandos.Registro()

        async def nada(_p: dict[str, Any], _c: comandos.Contexto) -> dict[str, Any]:
            return {}

        registro.registrar("nada", nada)
        contexto = _contexto()

        for i in range(comandos.LEMBRAR_ULTIMOS + 10):
            asyncio.run(comandos.atender(_comando("nada", f"c-{i}"), registro, contexto))

        assert registro.ja_atendido("c-0") is None
        assert registro.ja_atendido(f"c-{comandos.LEMBRAR_ULTIMOS + 9}") is not None


class TestEstado:
    def test_relata_pastas_autorizadas(self, tmp_path: object) -> None:
        pasta = tmp_path / "dados"  # type: ignore[operator]
        pasta.mkdir()
        configuracao = Configuracao(servidor="https://x", dispositivo_id="d").com_raiz(pasta)

        resultado = asyncio.run(
            comandos.atender(
                _comando("estado"), comandos.registro_padrao(), _contexto(configuracao)
            )
        )

        assert resultado["ok"] is True
        assert resultado["pode_copiar"] is True
        assert str(pasta.resolve()) in resultado["raizes"]

    def test_sem_pasta_autorizada_diz_que_nao_copia_nada(self) -> None:
        """
        Um dispositivo pareado sem pasta autorizada nao copia nada.

        Isso precisa chegar a tela como fato, e nao como suposicao de quem
        esta olhando um dispositivo "conectado".
        """
        resultado = asyncio.run(
            comandos.atender(
                _comando("estado"), comandos.registro_padrao(), _contexto(Configuracao())
            )
        )

        assert resultado["pode_copiar"] is False
        assert resultado["raizes"] == []


class TestRestauracaoProtegida:
    """A guarda de acao destrutiva, pedida pelo Live (02.J).

    O Agente e quem escreve no disco do cliente. Se a protecao dependesse de o
    servidor lembrar de mandar o parametro certo, ela seria uma convencao — e
    uma convencao nao segura ninguem. Aqui ela e decidida na maquina.
    """

    @staticmethod
    def _cenario(tmp_path: Any) -> tuple[Configuracao, Any, Any]:
        from autotarefas.tasks.backup import BackupTask

        raiz = tmp_path / "cliente"
        origem = raiz / "dados"
        origem.mkdir(parents=True)
        (origem / "contrato.txt").write_text("do backup", encoding="utf-8")

        pacote = raiz / "p1.zip"
        BackupTask(sources=[origem], destination=pacote).run()

        (origem / "contrato.txt").write_text("ATUAL", encoding="utf-8")

        configuracao = Configuracao(servidor="https://x", dispositivo_id="d").com_raiz(raiz)
        return configuracao, pacote, raiz

    def test_sobrescrever_sem_protecao_e_bloqueado_e_o_arquivo_fica(self, tmp_path: Any) -> None:
        configuracao, pacote, raiz = self._cenario(tmp_path)

        resultado = asyncio.run(
            comandos.atender(
                _comando(
                    "restaurar",
                    pacote=str(pacote),
                    destino=str(raiz),
                    sobrescrever=True,
                ),
                comandos.registro_padrao(),
                _contexto(configuracao),
            )
        )

        assert resultado["ok"] is False
        assert "ProtecaoBloqueou" in resultado["erro"]
        atual = (raiz / "dados" / "contrato.txt").read_text(encoding="utf-8")
        assert atual == "ATUAL"

    def test_com_backup_recente_do_destino_sobrescreve(self, tmp_path: Any) -> None:
        from datetime import datetime

        from autotarefas.tasks.backup import BackupTask

        configuracao, pacote, raiz = self._cenario(tmp_path)
        pacotes = raiz / "backups-do-destino"
        pacotes.mkdir()
        nome = f"backup_{datetime.now():%Y-%m-%d_%H%M}.zip"
        BackupTask(sources=[raiz / "dados"], destination=pacotes / nome).run()

        resultado = asyncio.run(
            comandos.atender(
                _comando(
                    "restaurar",
                    pacote=str(pacote),
                    destino=str(raiz),
                    sobrescrever=True,
                    protecao=str(pacotes),
                ),
                comandos.registro_padrao(),
                _contexto(configuracao),
            )
        )

        assert resultado["ok"] is True
        assert resultado["protecao"].startswith("backup backup_")
        atual = (raiz / "dados" / "contrato.txt").read_text(encoding="utf-8")
        assert atual == "do backup"

    def test_pasta_de_protecao_fora_das_raizes_e_recusada(self, tmp_path: Any) -> None:
        """
        A pasta de protecao passa pela mesma guarda de pastas autorizadas.

        Sem isso, o Live poderia apontar para qualquer lugar do disco e usar a
        resposta para descobrir o que existe la.
        """
        configuracao, pacote, raiz = self._cenario(tmp_path)
        fora = tmp_path / "fora"
        fora.mkdir()

        resultado = asyncio.run(
            comandos.atender(
                _comando(
                    "restaurar",
                    pacote=str(pacote),
                    destino=str(raiz),
                    sobrescrever=True,
                    protecao=str(fora),
                ),
                comandos.registro_padrao(),
                _contexto(configuracao),
            )
        )

        assert resultado["ok"] is False
        assert "autorizada" in resultado["erro"]

    def test_dispensa_explicita_libera_e_volta_no_relatorio(self, tmp_path: Any) -> None:
        configuracao, pacote, raiz = self._cenario(tmp_path)

        resultado = asyncio.run(
            comandos.atender(
                _comando(
                    "restaurar",
                    pacote=str(pacote),
                    destino=str(raiz),
                    sobrescrever=True,
                    dispensar_protecao="maquina nova, sem dados",
                ),
                comandos.registro_padrao(),
                _contexto(configuracao),
            )
        )

        assert resultado["ok"] is True
        assert "maquina nova, sem dados" in resultado["protecao"]


class TestPacotesPeloNome:
    """A tela pede pacote pelo NOME; a maquina resolve onde ele esta (G.7.2).

    O Live nunca recebeu o caminho local — recebeu a ficha do artefato, que tem
    o nome. Fazer a conversa por nome fecha uma porta de brinde: o servidor nao
    consegue apontar para um arquivo arbitrario do disco, porque nao e ele quem
    escolhe a pasta.
    """

    @staticmethod
    def _maquina_com_pacote(tmp_path: Any) -> tuple[Configuracao, Any, str]:
        from datetime import datetime

        from autotarefas.tasks.backup import BackupTask

        raiz = tmp_path / "cliente" / "dados"
        documentos = raiz / "docs"
        documentos.mkdir(parents=True)
        (documentos / "contrato.txt").write_text("do backup", encoding="utf-8")

        # Ao lado da pasta autorizada, e nao dentro: e onde o Agente grava por
        # padrao, e e la que `artefatos` procura pelo nome.
        pacotes = tmp_path / "cliente" / "backups"
        pacotes.mkdir()
        nome = f"backup_{datetime.now():%Y-%m-%d_%H%M}.zip"
        BackupTask(sources=[documentos], destination=pacotes / nome).run()

        configuracao = Configuracao(servidor="https://x", dispositivo_id="d").com_raiz(raiz)
        return configuracao, raiz, nome

    def test_a_tela_lista_os_pacotes_da_maquina(self, tmp_path: Any) -> None:
        configuracao, _, nome = self._maquina_com_pacote(tmp_path)

        resultado = asyncio.run(
            comandos.atender(
                _comando("pacotes"), comandos.registro_padrao(), _contexto(configuracao)
            )
        )

        assert resultado["ok"] is True
        assert [item["nome"] for item in resultado["pacotes"]] == [nome]
        assert resultado["tem_pasta_autorizada"] is True

    def test_a_listagem_nao_devolve_caminho_local(self, tmp_path: Any) -> None:
        configuracao, _, _ = self._maquina_com_pacote(tmp_path)

        resultado = asyncio.run(
            comandos.atender(
                _comando("pacotes"), comandos.registro_padrao(), _contexto(configuracao)
            )
        )

        assert str(tmp_path) not in str(resultado)

    def test_sem_pasta_autorizada_a_tela_sabe_o_motivo(self) -> None:
        """
        Lista vazia por falta de autorizacao e lista vazia por falta de backup
        sao coisas diferentes, e pedem acoes diferentes de quem le.
        """
        resultado = asyncio.run(
            comandos.atender(
                _comando("pacotes"), comandos.registro_padrao(), _contexto(Configuracao())
            )
        )

        assert resultado["pacotes"] == []
        assert resultado["tem_pasta_autorizada"] is False

    def test_listar_conteudo_pelo_nome(self, tmp_path: Any) -> None:
        configuracao, _, nome = self._maquina_com_pacote(tmp_path)

        resultado = asyncio.run(
            comandos.atender(
                _comando("listar_pacote", pacote=nome),
                comandos.registro_padrao(),
                _contexto(configuracao),
            )
        )

        assert resultado["ok"] is True
        assert any(item["arquivo"].endswith("contrato.txt") for item in resultado["conteudo"])

    def test_nome_com_travessia_e_recusado(self, tmp_path: Any) -> None:
        """
        Se o nome virasse caminho, a guarda de pastas autorizadas teria sido
        contornada pela porta dos fundos.
        """
        configuracao, _, nome = self._maquina_com_pacote(tmp_path)
        alheio = tmp_path / "fora.zip"
        alheio.write_bytes(b"nao e para ler")

        resultado = asyncio.run(
            comandos.atender(
                _comando("listar_pacote", pacote=rf"..\..\{alheio.name}"),
                comandos.registro_padrao(),
                _contexto(configuracao),
            )
        )

        assert resultado["ok"] is False
        assert nome not in resultado["erro"]

    def test_restaurar_pelo_nome_recupera_o_arquivo(self, tmp_path: Any) -> None:
        configuracao, raiz, nome = self._maquina_com_pacote(tmp_path)
        destino = raiz / "recuperado"

        resultado = asyncio.run(
            comandos.atender(
                _comando("restaurar", pacote=nome, destino=str(destino)),
                comandos.registro_padrao(),
                _contexto(configuracao),
            )
        )

        assert resultado["ok"] is True, resultado.get("erro")
        recuperado = next(destino.rglob("contrato.txt"))
        assert recuperado.read_text(encoding="utf-8") == "do backup"

    def test_restaurar_incremental_sem_informar_a_corrente(self, tmp_path: Any) -> None:
        """
        A tela nao sabe montar a corrente; a maquina sabe.

        Sem isto, restaurar o pacote de hoje devolveria uma pasta pela metade —
        e o pior: com cara de restauracao concluida.
        """
        from datetime import datetime

        from autotarefas.tasks.backup import BackupTask
        from autotarefas.tasks.catalogo import NOME, Catalogo

        raiz = tmp_path / "cliente" / "dados"
        documentos = raiz / "docs"
        documentos.mkdir(parents=True)
        (documentos / "contrato.txt").write_text("contrato", encoding="utf-8")
        (documentos / "nota.txt").write_text("nota", encoding="utf-8")

        pacotes = tmp_path / "cliente" / "backups"
        pacotes.mkdir()
        catalogo = Catalogo(pacotes / NOME)
        BackupTask(
            sources=[documentos],
            destination=pacotes / "backup_2026-08-24_0200.zip",
            catalogo=catalogo,
        ).run()

        (documentos / "contrato.txt").write_text("contrato v2", encoding="utf-8")
        nome = f"backup_{datetime.now():%Y-%m-%d_%H%M}.zip"
        BackupTask(sources=[documentos], destination=pacotes / nome, catalogo=catalogo).run()

        configuracao = Configuracao(servidor="https://x", dispositivo_id="d").com_raiz(raiz)
        destino = raiz / "recuperado"

        resultado = asyncio.run(
            comandos.atender(
                _comando("restaurar", pacote=nome, destino=str(destino)),
                comandos.registro_padrao(),
                _contexto(configuracao),
            )
        )

        assert resultado["ok"] is True, resultado.get("erro")
        assert resultado["faltando"] == [], resultado
        assert resultado["restaurados"] == 2, resultado
        assert resultado["completa"] is True, resultado
        recuperado = next(destino.rglob("nota.txt"))
        assert recuperado.read_text(encoding="utf-8") == "nota"

    def test_conferir_backup_dispensa_a_tela_de_conhecer_caminhos(self, tmp_path: Any) -> None:
        """
        A tela nao conhece pasta nenhuma da maquina.

        Ela pede "confira nos meus pacotes", e o Agente resolve qual pasta e
        essa. Exigir um caminho da tela obrigaria o servidor a guardar caminhos
        locais — exatamente o que o desenho evita.
        """
        configuracao, raiz, nome = self._maquina_com_pacote(tmp_path)
        atual = raiz / "docs" / "contrato.txt"
        atual.write_text("ATUAL", encoding="utf-8")

        resultado = asyncio.run(
            comandos.atender(
                _comando(
                    "restaurar",
                    pacote=nome,
                    destino=str(raiz),
                    sobrescrever=True,
                    conferir_backup=True,
                ),
                comandos.registro_padrao(),
                _contexto(configuracao),
            )
        )

        assert resultado["ok"] is True, resultado.get("erro")
        assert resultado["protecao"].startswith("backup backup_")
        assert atual.read_text(encoding="utf-8") == "do backup"


@pytest.mark.parametrize("mensagem", [{}, {"tipo": "outra"}, {"id": "x"}])
def test_mensagem_incompleta_nao_quebra(mensagem: dict[str, Any]) -> None:
    """Entrada malformada vira resultado de acao desconhecida, nao excecao."""
    resultado = asyncio.run(comandos.atender(mensagem, comandos.registro_padrao(), _contexto()))
    assert resultado["ok"] is False
