"""Conector S3 compativel (02.F).

Os testes falam com um servidor S3 **de verdade no protocolo**, rodando local
(`moto` em modo servidor). Nao ha objeto substituido por dublê: e HTTP, e
assinatura v4, e multipart de verdade.

Isso prova o **protocolo**, e nao a nuvem de ninguem. Ate alguem apontar para
um endpoint externo autorizado, o card nao pode dizer "nuvem real homologada" —
e o documento registra isso como pendencia.

O teste que carrega o peso e `test_objeto_que_nao_confere_e_apagado`: um objeto
corrompido deixado no balde criaria um backup com aparencia de completo, e o
cliente so descobriria no dia da restauracao.
"""

from __future__ import annotations

import hashlib
import os
import socket
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from apps.agente.agente import s3

#: Tamanho que forca envio em partes.
GRANDE = s3.LIMITE_MULTIPART + 5 * 1024 * 1024


def _porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tomada:
        tomada.bind(("127.0.0.1", 0))
        return int(tomada.getsockname()[1])


@pytest.fixture(scope="module")
def servidor_s3() -> Iterator[str]:
    """
    Servidor S3 compativel, local, no ar de verdade.

    `moto` em modo servidor: o cliente `boto3` fala HTTP com ele exatamente
    como falaria com a Amazon. Um dublê em memoria testaria o nosso codigo
    chamando as funcoes certas — e nao o protocolo.
    """
    from moto.server import ThreadedMotoServer

    porta = _porta_livre()
    servidor = ThreadedMotoServer(port=porta, verbose=False)
    servidor.start()

    endereco = f"http://127.0.0.1:{porta}"
    limite = time.monotonic() + 10
    while time.monotonic() < limite:
        try:
            with socket.create_connection(("127.0.0.1", porta), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        servidor.stop()
        pytest.skip("o servidor S3 de teste nao subiu")

    yield endereco
    servidor.stop()


@pytest.fixture
def credencial(servidor_s3: str) -> s3.Credencial:
    """Credencial apontando para o servidor local, com o balde ja criado."""
    dados = s3.Credencial(
        endpoint=servidor_s3,
        regiao="us-east-1",
        balde="backups-da-padaria",
        chave="chave-de-teste",  # pragma: allowlist secret
        segredo="segredo-de-teste",  # pragma: allowlist secret
        prefixo="padaria/2026",
    )
    cliente = s3._cliente(dados)
    cliente.create_bucket(Bucket=dados.balde)
    return dados


@pytest.fixture
def pacote(tmp_path: Path) -> Path:
    alvo = tmp_path / "backup.zip"
    alvo.write_bytes(os.urandom(64 * 1024))
    return alvo


class TestEnvio:
    def test_envia_e_confere(self, pacote: Path, credencial: s3.Credencial) -> None:
        recibo = s3.enviar(pacote, credencial)

        assert recibo["conferido_no_destino"] is True
        assert recibo["objeto"] == "padaria/2026/backup.zip"
        assert recibo["tipo"] == "s3"

    def test_conteudo_chega_identico(self, pacote: Path, credencial: s3.Credencial) -> None:
        """
        Streaming so vale se o conteudo chegar inteiro do outro lado.

        Vale para a nuvem o mesmo que vale para o disco: um pedaco perdido no
        fim so apareceria no dia da restauracao.
        """
        esperado = hashlib.sha256(pacote.read_bytes()).hexdigest()
        s3.enviar(pacote, credencial)

        cliente = s3._cliente(credencial)
        corpo = cliente.get_object(Bucket=credencial.balde, Key="padaria/2026/backup.zip")[
            "Body"
        ].read()

        assert hashlib.sha256(corpo).hexdigest() == esperado

    def test_pacote_grande_sobe_em_partes(self, tmp_path: Path, credencial: s3.Credencial) -> None:
        """
        Upload de 40 GB numa tacada morre no primeiro soluco de rede.

        Em partes, so a parte falha — e este teste garante que o caminho
        multipart existe e produz o objeto certo.
        """
        grande = tmp_path / "grande.zip"
        grande.write_bytes(os.urandom(GRANDE))

        recibo = s3.enviar(grande, credencial)

        assert recibo["tamanho_bytes"] == GRANDE
        cliente = s3._cliente(credencial)
        cabecalho = cliente.head_object(Bucket=credencial.balde, Key="padaria/2026/grande.zip")
        assert cabecalho["ContentLength"] == GRANDE

    def test_prefixo_organiza_o_balde(
        self, pacote: Path, servidor_s3: str, credencial: s3.Credencial
    ) -> None:
        del servidor_s3
        sem_prefixo = s3.Credencial(
            endpoint=credencial.endpoint,
            regiao=credencial.regiao,
            balde=credencial.balde,
            chave=credencial.chave,
            segredo=credencial.segredo,
        )

        recibo = s3.enviar(pacote, sem_prefixo)

        assert recibo["objeto"] == "backup.zip"


class TestRecusas:
    def test_balde_inexistente_vira_mensagem_e_nao_excecao_crua(
        self, pacote: Path, credencial: s3.Credencial
    ) -> None:
        errado = s3.Credencial(
            endpoint=credencial.endpoint,
            regiao=credencial.regiao,
            balde="balde-que-nao-existe",
            chave=credencial.chave,
            segredo=credencial.segredo,
        )

        with pytest.raises(s3.EnvioRecusado, match="falhou"):
            s3.enviar(pacote, errado)

    def test_pacote_inexistente_e_recusado(self, credencial: s3.Credencial, tmp_path: Path) -> None:
        with pytest.raises(s3.EnvioRecusado, match="nao existe"):
            s3.enviar(tmp_path / "nunca-existiu.zip", credencial)

    def test_objeto_que_nao_confere_e_apagado(
        self, pacote: Path, credencial: s3.Credencial, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        O teste que justifica reler o objeto depois de enviar.

        Objeto corrompido deixado no balde criaria um backup com aparencia de
        completo. O ETag nao serviria para pegar isso: em multipart ele e o
        hash dos hashes das partes.
        """
        monkeypatch.setattr(s3, "_sha_do_objeto", lambda *_a, **_k: "hash-que-nao-bate")

        with pytest.raises(s3.EnvioRecusado, match="conteudo diferente"):
            s3.enviar(pacote, credencial)

        from botocore.exceptions import ClientError

        cliente = s3._cliente(credencial)
        with pytest.raises(ClientError):
            cliente.head_object(Bucket=credencial.balde, Key="padaria/2026/backup.zip")

    def test_erro_nao_vaza_a_credencial(self, pacote: Path, credencial: s3.Credencial) -> None:
        """
        Erros do botocore trazem o endereco assinado, que carrega a chave.

        Deixar isso chegar ao log do cliente publicaria a credencial de nuvem
        dele em texto.
        """
        errado = s3.Credencial(
            endpoint=credencial.endpoint,
            regiao=credencial.regiao,
            balde="balde-que-nao-existe",
            chave="AKIAOSTENSIVAMENTESECRETA",  # pragma: allowlist secret
            segredo="segredo-que-nao-pode-vazar",  # pragma: allowlist secret
        )

        with pytest.raises(s3.EnvioRecusado) as capturado:
            s3.enviar(pacote, errado)

        mensagem = str(capturado.value)
        assert "AKIAOSTENSIVAMENTESECRETA" not in mensagem  # pragma: allowlist secret
        assert "segredo-que-nao-pode-vazar" not in mensagem


class TestDescricao:
    def test_descricao_nao_carrega_credencial(self, credencial: s3.Credencial) -> None:
        """A descricao vai para a tela e para o historico."""
        descricao = credencial.descricao

        assert credencial.balde in descricao
        assert credencial.chave not in descricao
        assert credencial.segredo not in descricao

    def test_sem_endpoint_a_descricao_diz_amazon(self) -> None:
        dados = s3.Credencial(endpoint="", regiao="sa-east-1", balde="b", chave="k", segredo="s")

        assert "Amazon S3" in dados.descricao


class TestBackupComDestinoS3:
    """
    O pacote sai da maquina e chega ao balde, pelo fluxo de verdade.

    Aqui o Agente monta o pacote a partir de pastas autorizadas e o envia —
    e o mesmo caminho que o Live dispara.
    """

    @pytest.fixture
    def autorizada(self, tmp_path: Path):
        from apps.agente.agente import raizes
        from apps.agente.agente.config import Local

        pasta = tmp_path / "dados"
        pasta.mkdir()
        (pasta / "contrato.txt").write_text("contrato importante", encoding="utf-8")
        return raizes.autorizar(Local(pasta=tmp_path / "cfg"), pasta)

    def _contexto(self, configuracao):
        from apps.agente.agente.comandos import Contexto

        async def relatar(_dados):
            return None

        return Contexto(configuracao=configuracao, relatar=relatar)

    def test_pacote_sobe_e_a_ficha_registra(
        self, autorizada, credencial: s3.Credencial, tmp_path: Path
    ) -> None:
        import asyncio

        from apps.agente.agente import backup as backup_agente

        ficha = asyncio.run(
            backup_agente.executar_backup(
                {
                    "destino": str(tmp_path / "origem" / "p.zip"),
                    "s3": {
                        "endpoint": credencial.endpoint,
                        "regiao": credencial.regiao,
                        "balde": credencial.balde,
                        "chave": credencial.chave,
                        "segredo": credencial.segredo,
                        "prefixo": credencial.prefixo,
                    },
                },
                self._contexto(autorizada),
            )
        )

        assert len(ficha["entregas"]) == 1
        assert ficha["entregas"][0]["tipo"] == "s3"
        assert ficha["entregas"][0]["conferido_no_destino"] is True

        cliente = s3._cliente(credencial)
        assert (
            cliente.head_object(Bucket=credencial.balde, Key="padaria/2026/p.zip")["ContentLength"]
            > 0
        )

    def test_credencial_incompleta_recusa_dizendo_o_que_falta(self, autorizada) -> None:
        """
        Preencher com padrao silencioso levaria o pacote a um balde que
        ninguem escolheu.
        """
        from apps.agente.agente import backup as backup_agente

        with pytest.raises(backup_agente.BackupRecusado, match="falta balde"):
            backup_agente.montar_pedido(
                {"s3": {"chave": "k", "segredo": "s"}}, self._contexto(autorizada)
            )

    def test_a_ficha_que_sobe_nao_carrega_a_credencial(
        self, autorizada, credencial: s3.Credencial, tmp_path: Path
    ) -> None:
        """
        A ficha vai para o servidor e para o historico.

        A credencial de nuvem do cliente nao pode viajar junto nem ficar
        gravada no banco.
        """
        import asyncio

        from apps.agente.agente import backup as backup_agente

        ficha = asyncio.run(
            backup_agente.executar_backup(
                {
                    "destino": str(tmp_path / "origem" / "p.zip"),
                    "s3": {
                        "endpoint": credencial.endpoint,
                        "regiao": credencial.regiao,
                        "balde": credencial.balde,
                        "chave": credencial.chave,
                        "segredo": credencial.segredo,
                    },
                },
                self._contexto(autorizada),
            )
        )

        texto = str(ficha)
        assert credencial.chave not in texto
        assert credencial.segredo not in texto

    def test_pedido_impresso_nao_vaza_o_segredo(self, autorizada) -> None:
        """
        Log e o lugar em que segredo mais vaza sem ninguem querer.

        Um `Pedido` num `print` de depuracao levaria a chave de nuvem junto,
        se o `repr` gerado pelo `dataclass` valesse.
        """
        from apps.agente.agente import backup as backup_agente

        pedido = backup_agente.montar_pedido(
            {
                "s3": {
                    "balde": "b",
                    "chave": "AKIANAOPODEAPARECER",  # pragma: allowlist secret
                    "segredo": "segredo-nao-pode-aparecer",  # pragma: allowlist secret
                }
            },
            self._contexto(autorizada),
        )

        assert "AKIANAOPODEAPARECER" not in repr(pedido)  # pragma: allowlist secret
        assert "segredo-nao-pode-aparecer" not in repr(pedido)


class TestEnvioDiferidoPeloComando:
    """
    O envio que acontece DEPOIS do backup, quando ha canal.

    E o que destrava backup agendado com destino na nuvem sem quebrar nenhuma
    das duas decisoes que pareciam impedi-lo: o agendamento continua rodando
    offline, e o Agente continua sem gravar chave de nuvem em disco.

    A credencial chega no pedido, e usada, e some com a resposta.
    """

    @pytest.fixture
    def maquina(self, tmp_path: Path):
        from apps.agente.agente import raizes
        from apps.agente.agente.config import Local

        dados = tmp_path / "cliente" / "dados"
        dados.mkdir(parents=True)
        (dados / "contrato.txt").write_text("contrato", encoding="utf-8")
        return raizes.autorizar(Local(pasta=tmp_path / "cfg"), dados)

    def _contexto(self, configuracao):
        from apps.agente.agente.comandos import Contexto

        async def relatar(_dados):
            return None

        return Contexto(configuracao=configuracao, relatar=relatar)

    def _pacote_da_politica(self, configuracao) -> str:
        """Roda uma politica com destino na nuvem e devolve o nome do pacote."""
        import asyncio

        from apps.agente.agente import backup as backup_agente
        from autotarefas.tasks.politica import Destino, Politica, TipoDeDestino

        ficha = asyncio.run(
            backup_agente.executar_politica(
                Politica(
                    origens=list(configuracao.raizes),
                    destino=Destino(tipo=TipoDeDestino.NUVEM),
                ),
                configuracao,
                politica_id="p1",
                politica_nome="Nuvem diaria",
            )
        )
        assert ficha["nuvem_pendente"] is True
        return str(ficha["pacote"])

    def _pedir_envio(self, configuracao, nome: str, credencial: s3.Credencial):
        import asyncio

        from apps.agente.agente.comandos import executar_enviar_para_nuvem

        return asyncio.run(
            executar_enviar_para_nuvem(
                {
                    "pacote": nome,
                    "s3": {
                        "endpoint": credencial.endpoint,
                        "regiao": credencial.regiao,
                        "balde": credencial.balde,
                        "chave": credencial.chave,
                        "segredo": credencial.segredo,
                        "prefixo": credencial.prefixo,
                    },
                },
                self._contexto(configuracao),
            )
        )

    def test_o_pacote_do_agendamento_sobe_depois(self, maquina, credencial: s3.Credencial) -> None:
        nome = self._pacote_da_politica(maquina)

        resposta = self._pedir_envio(maquina, nome, credencial)

        assert resposta["ok"] is True
        assert resposta["pacote"] == nome
        assert resposta["conferido_no_destino"] is True

    def test_o_objeto_esta_mesmo_la(self, maquina, credencial: s3.Credencial) -> None:
        """
        Conferido lendo de volta, e nao pela resposta da API do balde.

        "Enviado" segundo quem enviou nao prova nada sobre o que chegou.
        """
        nome = self._pacote_da_politica(maquina)

        resposta = self._pedir_envio(maquina, nome, credencial)
        cliente = s3._cliente(credencial)
        objeto = cliente.get_object(Bucket=credencial.balde, Key=resposta["objeto"])

        assert objeto["ContentLength"] > 0

    def test_reenviar_sobrescreve_em_vez_de_multiplicar(
        self, maquina, credencial: s3.Credencial
    ) -> None:
        """
        Uma queda de rede no meio de um envio nao pode deixar lixo permanente.

        A chave e derivada do nome do pacote, entao a segunda tentativa cai no
        mesmo objeto. Se dependesse de um sufixo por tentativa, uma semana de
        reconexoes multiplicaria a conta do cliente.
        """
        nome = self._pacote_da_politica(maquina)

        primeira = self._pedir_envio(maquina, nome, credencial)
        segunda = self._pedir_envio(maquina, nome, credencial)
        cliente = s3._cliente(credencial)
        listagem = cliente.list_objects_v2(Bucket=credencial.balde, Prefix=credencial.prefixo)
        # Contadas as chaves DESTE pacote, e nao as do balde: o servidor S3 do
        # modulo e compartilhado entre os testes, e um contador global mediria
        # o que os vizinhos subiram.
        deste = [item for item in listagem.get("Contents", []) if item["Key"].endswith(nome)]

        assert primeira["objeto"] == segunda["objeto"]
        assert len(deste) == 1, "um sufixo por tentativa multiplicaria a conta do cliente"

    def test_pacote_desconhecido_e_recusado(self, maquina, credencial: s3.Credencial) -> None:
        """
        O nome e resolvido NESTA maquina.

        Sem isso, o servidor escolheria qual arquivo do disco do cliente sobe
        para um balde que ele mesmo aponta.
        """
        from apps.agente.agente import artefatos

        with pytest.raises(artefatos.PacoteDesconhecido):
            self._pedir_envio(maquina, "../../Windows/System32/config.zip", credencial)

    def test_sem_credencial_recusa_em_vez_de_inventar_balde(self, maquina) -> None:
        import asyncio

        from apps.agente.agente.comandos import executar_enviar_para_nuvem

        with pytest.raises(ValueError, match="credencial"):
            asyncio.run(executar_enviar_para_nuvem({"pacote": "x.zip"}, self._contexto(maquina)))

    def test_balde_errado_volta_como_recusa_e_nao_como_sucesso(
        self, maquina, credencial: s3.Credencial
    ) -> None:
        """Falha de envio nao pode virar 'ok': o painel diria que a copia saiu."""
        import dataclasses

        nome = self._pacote_da_politica(maquina)
        errada = dataclasses.replace(credencial, balde="balde-que-nao-existe")

        resposta = self._pedir_envio(maquina, nome, errada)

        assert resposta["ok"] is False
        assert resposta["erro"]
