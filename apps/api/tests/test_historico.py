"""Historico de execucoes no servidor (G.7.1).

O que se testa aqui e a gravacao do que o Agente fez **sozinho** — o backup do
agendamento, feito de madrugada, muitas vezes com a internet caida. Tres coisas
precisam ser verdade, e cada uma delas quebra o produto de um jeito diferente:

1. **reenvio nao duplica.** O Agente que manda de novo depois de uma queda no
   meio do envio nao pode virar duas linhas no historico;
2. **isolamento vale aqui tambem.** Uma maquina nao pendura execucao no
   historico de outra empresa;
3. **resultado desconhecido nao vira sucesso.** Um Agente mais novo pode mandar
   algo que este servidor ainda nao conhece, e "backup ok" para algo que
   ninguem sabe o que foi e pior que um erro.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from apps.api.app import dispositivos, historico
from apps.api.app.db import repositorio as repo
from apps.api.app.db.models import Artefato, Dispositivo, Execucao, Papel, ResultadoExecucao
from apps.api.app.db.sessao import Banco


@pytest.fixture
def banco() -> Iterator[Banco]:
    instancia = Banco("sqlite:///:memory:")
    instancia.criar_esquema()
    yield instancia
    instancia.descartar()


def _organizacao(banco: Banco, nome: str = "Padaria") -> repo.Contexto:
    with banco.sessao() as sessao:
        organizacao = repo.criar_organizacao(sessao, nome=nome, dominio=f"{nome.lower()}.com.br")
        usuario = repo.criar_usuario(
            sessao,
            email=f"dono@{nome.lower()}.com.br",
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


def _item(identificador: str, **campos: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": identificador,
        "politica_id": "",
        "politica_nome": "Diaria",
        "iniciada_em": "2026-08-25T02:00:00",
        "terminada_em": "2026-08-25T02:03:00",
        "resultado": "sucesso",
        "arquivos": 5,
        "bytes_copiados": 2048,
        "ressalva": "",
        "origem": "agendamento",
        "artefato": {
            "nome": "backup_2026-08-25_0200.zip",
            "tamanho_bytes": 2048,
            "sha256": "c" * 64,
            "localizacao": "dispositivo",
        },
    }
    base.update(campos)
    return base


def _gravar(banco: Banco, dispositivo_id: str, itens: list[dict[str, Any]]) -> list[str]:
    with banco.sessao() as sessao:
        dispositivo = sessao.get(Dispositivo, dispositivo_id)
        assert dispositivo is not None
        return historico.registrar_do_agente(sessao, dispositivo, itens)


class TestGravacao:
    def test_execucao_do_agendamento_vira_linha_com_artefato(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        aceitos = _gravar(banco, dispositivo_id, [_item("a" * 32)])

        assert aceitos == ["a" * 32]
        with banco.sessao() as sessao:
            execucoes = list(sessao.execute(repo.escopo(Execucao, contexto)).scalars())
            artefatos = list(sessao.execute(repo.escopo(Artefato, contexto)).scalars())

        assert len(execucoes) == 1
        assert execucoes[0].resultado is ResultadoExecucao.SUCESSO
        assert execucoes[0].origem == "agendamento"
        assert execucoes[0].arquivos_incluidos == 5
        assert len(artefatos) == 1
        assert artefatos[0].nome == "backup_2026-08-25_0200.zip"

    def test_reenvio_nao_duplica_e_ainda_confirma(self, banco: Banco) -> None:
        """
        "Ja esta gravado" e "acabou de ser gravado" significam a mesma coisa
        para o Agente: pode parar de reenviar.

        Nao confirmar o repetido faria o mesmo registro voltar a cada
        reconexao, para sempre.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        _gravar(banco, dispositivo_id, [_item("b" * 32)])
        aceitos = _gravar(banco, dispositivo_id, [_item("b" * 32)])

        assert aceitos == ["b" * 32]
        with banco.sessao() as sessao:
            execucoes = list(sessao.execute(repo.escopo(Execucao, contexto)).scalars())
        assert len(execucoes) == 1

    def test_falha_do_agendamento_e_gravada_como_falha(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        _gravar(
            banco,
            dispositivo_id,
            [
                _item(
                    "c" * 32,
                    resultado="falha",
                    ressalva="disco externo desconectado",
                    artefato=None,
                )
            ],
        )

        with banco.sessao() as sessao:
            execucao = sessao.execute(repo.escopo(Execucao, contexto)).scalars().one()
            artefatos = list(sessao.execute(repo.escopo(Artefato, contexto)).scalars())

        assert execucao.resultado is ResultadoExecucao.FALHA
        assert "disco externo" in execucao.ressalva
        assert artefatos == []

    def test_resultado_desconhecido_vira_falha_e_nunca_sucesso(self, banco: Banco) -> None:
        """
        Um Agente mais novo pode mandar um resultado que este servidor ainda
        nao conhece.

        Tratar o desconhecido como sucesso mostraria "backup ok" para algo que
        ninguem sabe o que foi.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        _gravar(banco, dispositivo_id, [_item("d" * 32, resultado="parcialmente_incrivel")])

        with banco.sessao() as sessao:
            execucao = sessao.execute(repo.escopo(Execucao, contexto)).scalars().one()
        assert execucao.resultado is ResultadoExecucao.FALHA

    def test_data_ilegivel_nao_vira_a_hora_de_agora_em_silencio(self, banco: Banco) -> None:
        """Um `terminada_em` vazio e informacao: a execucao nao terminou."""
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        _gravar(banco, dispositivo_id, [_item("e" * 32, terminada_em="ontem de madrugada")])

        with banco.sessao() as sessao:
            execucao = sessao.execute(repo.escopo(Execucao, contexto)).scalars().one()
        assert execucao.terminada_em is None

    def test_lote_gigante_e_cortado(self, banco: Banco) -> None:
        """
        Mensagem maior que o teto nao e um Agente sincronizando.

        Aceitar sem limite deixaria uma conexao autenticada encher o banco.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        itens = [_item(f"{numero:032d}") for numero in range(historico.LOTE_MAXIMO + 25)]

        aceitos = _gravar(banco, dispositivo_id, itens)

        assert len(aceitos) == historico.LOTE_MAXIMO

    def test_id_fora_do_formato_e_ignorado(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        aceitos = _gravar(banco, dispositivo_id, [_item(""), _item("x" * 64)])

        assert aceitos == []
        with banco.sessao() as sessao:
            assert list(sessao.execute(repo.escopo(Execucao, contexto)).scalars()) == []


class TestIsolamento:
    def test_a_execucao_fica_na_organizacao_do_dispositivo(self, banco: Banco) -> None:
        padaria = _organizacao(banco, "Padaria")
        farmacia = _organizacao(banco, "Farmacia")
        dispositivo_id = _dispositivo(banco, padaria)

        _gravar(banco, dispositivo_id, [_item("f" * 32)])

        with banco.sessao() as sessao:
            das_outras = list(sessao.execute(repo.escopo(Execucao, farmacia)).scalars())
        assert das_outras == []

    def test_politica_de_outra_empresa_nao_e_aceita(self, banco: Banco) -> None:
        """
        O `politica_id` chega do Agente.

        Sem conferir de quem ela e, um dispositivo penduraria a execucao dele
        na politica de outra empresa — e o historico de la ganharia uma linha
        que nao e de la.
        """
        from apps.api.app.db.models import Politica

        padaria = _organizacao(banco, "Padaria")
        farmacia = _organizacao(banco, "Farmacia")
        dispositivo_padaria = _dispositivo(banco, padaria)
        dispositivo_farmacia = _dispositivo(banco, farmacia, chave="k2")

        with banco.sessao() as sessao:
            alheia = Politica(
                organizacao_id=farmacia.organizacao_id,
                dispositivo_id=dispositivo_farmacia,
                nome="Da farmacia",
            )
            sessao.add(alheia)
            sessao.flush()
            alheia_id = alheia.id

        _gravar(banco, dispositivo_padaria, [_item("g" * 32, politica_id=alheia_id)])

        with banco.sessao() as sessao:
            execucao = sessao.execute(repo.escopo(Execucao, padaria)).scalars().one()
        assert execucao.politica_id is None


class TestListagem:
    def test_mais_recente_primeiro(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        _gravar(
            banco,
            dispositivo_id,
            [
                _item("1" * 32, iniciada_em="2026-08-20T02:00:00"),
                _item("2" * 32, iniciada_em="2026-08-25T02:00:00"),
            ],
        )

        with banco.sessao() as sessao:
            linhas = historico.listar(sessao, contexto)

        assert [linha["id"] for linha in linhas] == ["2" * 32, "1" * 32]
        assert linhas[0]["artefatos"][0]["nome"] == "backup_2026-08-25_0200.zip"

    def test_filtro_por_dispositivo(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        primeiro = _dispositivo(banco, contexto, chave="k1")
        segundo = _dispositivo(banco, contexto, chave="k2")

        _gravar(banco, primeiro, [_item("3" * 32)])
        _gravar(banco, segundo, [_item("4" * 32)])

        with banco.sessao() as sessao:
            linhas = historico.listar(sessao, contexto, dispositivo_id=segundo)

        assert [linha["id"] for linha in linhas] == ["4" * 32]

    def test_a_sincronizacao_deixa_registro_na_trilha(self, banco: Banco) -> None:
        """
        Auditoria tambem cobre o que a maquina fez sozinha.

        Sem isto, a unica evidencia de um backup de madrugada seria a linha do
        historico — que e justamente o que se quer poder conferir.
        """
        from apps.api.app.db.models import Auditoria

        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        _gravar(banco, dispositivo_id, [_item("5" * 32)])

        with banco.sessao() as sessao:
            trilha = list(sessao.execute(repo.escopo(Auditoria, contexto)).scalars())
            integra, explicacao = repo.conferir_trilha(sessao, contexto)

        assert any(linha.acao == "execucao.sincronizada" for linha in trilha)
        assert integra, explicacao


class TestODetalheDaExecucao:
    """
    A lista responde "aconteceu". O detalhe responde "como eu sei?".

    E a pergunta seguinte, e e ela que decide se alguem confia. Por isso o
    detalhe junta coisas que moram em lugares diferentes — a ficha do pacote
    com o SHA-256, para onde a copia foi e se foi CONFERIDA la, a politica que
    pediu, e a trilha encadeada daquele momento. Cada uma sozinha e uma
    afirmacao; juntas sao um caso.
    """

    def _com_entregas(self, banco: Banco, contexto: repo.Contexto) -> tuple[str, str]:
        dispositivo_id = _dispositivo(banco, contexto)
        item = _item("e1")
        item["artefato"]["entregas"] = [
            {
                "tipo": "s3",
                "destino": "Amazon S3 · balde backups-da-padaria",
                "objeto": "padaria/backup_2026-08-25_0200.zip",
                "conferido_no_destino": True,
            }
        ]
        _gravar(banco, dispositivo_id, [item])
        return dispositivo_id, "e1"

    def test_traz_o_pacote_com_a_soma_que_prova_o_conteudo(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        _, execucao_id = self._com_entregas(banco, contexto)

        with banco.sessao() as sessao:
            detalhe = historico.detalhar(sessao, contexto, execucao_id)

        pacote = detalhe["artefatos"][0]
        assert pacote["nome"] == "backup_2026-08-25_0200.zip"
        assert pacote["sha256"] == "c" * 64
        assert pacote["tamanho_bytes"] == 2048

    def test_a_conferencia_no_destino_deixou_de_ser_descartada(self, banco: Banco) -> None:
        """
        E a parte do produto que sustenta a palavra "verificavel".

        O pacote e lido de volta no destino e o SHA-256 recalculado, porque
        rede que cai e cabo USB ruim produzem arquivos com o tamanho certo e o
        conteudo errado. Fazer a conferencia e nao guardar o resultado deixava
        a evidencia acontecer e desaparecer.
        """
        contexto = _organizacao(banco)
        _, execucao_id = self._com_entregas(banco, contexto)

        with banco.sessao() as sessao:
            detalhe = historico.detalhar(sessao, contexto, execucao_id)

        entregas = detalhe["artefatos"][0]["entregas"]
        assert len(entregas) == 1
        assert entregas[0]["conferido_no_destino"] is True
        assert entregas[0]["objeto"] == "padaria/backup_2026-08-25_0200.zip"

    def test_pacote_sem_entrega_nao_inventa_uma(self, banco: Banco) -> None:
        # "Ficou so na maquina" e uma resposta, e precisa continuar sendo
        # distinguivel de "foi para algum lugar".
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _gravar(banco, dispositivo_id, [_item("e2")])

        with banco.sessao() as sessao:
            detalhe = historico.detalhar(sessao, contexto, "e2")

        assert detalhe["artefatos"][0]["entregas"] == []

    def test_entregas_corrompidas_viram_vazio_e_nao_derrubam_a_tela(self, banco: Banco) -> None:
        """
        Campo de evidencia com lixo dentro e pior do que vazio: parece resposta.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _gravar(banco, dispositivo_id, [_item("e3")])
        with banco.sessao() as sessao:
            artefato = sessao.execute(
                repo.escopo(Artefato, contexto).where(Artefato.execucao_id == "e3")
            ).scalar_one()
            artefato.entregas = "{isto nao e json"

        with banco.sessao() as sessao:
            detalhe = historico.detalhar(sessao, contexto, "e3")

        assert detalhe["artefatos"][0]["entregas"] == []

    def test_diz_de_qual_maquina_e(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        self._com_entregas(banco, contexto)

        with banco.sessao() as sessao:
            detalhe = historico.detalhar(sessao, contexto, "e1")

        assert detalhe["maquina"] == "PC da loja"

    def test_traz_a_politica_que_pediu_o_backup(self, banco: Banco) -> None:
        """
        E contra a politica que a execucao se compara.

        Sem ela, "12 arquivos copiados" nao diz se copiou o que devia — falta o
        outro lado da conta.
        """
        from apps.api.app import politicas

        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        with banco.sessao() as sessao:
            politica = politicas.criar(
                sessao,
                contexto,
                politicas.PedidoDePolitica(
                    nome="Diaria",
                    dispositivo_id=dispositivo_id,
                    configuracao={
                        "origens": [r"C:\Loja"],
                        "destino": {"tipo": "externo", "caminho": r"E:\Backups"},
                    },
                ),
            )
            politica_id = politica.id
        _gravar(banco, dispositivo_id, [_item("e4", politica_id=politica_id)])

        with banco.sessao() as sessao:
            detalhe = historico.detalhar(sessao, contexto, "e4")

        assert detalhe["politica"]["nome"] == "Diaria"
        assert detalhe["politica"]["origens"] == [r"C:\Loja"]
        assert detalhe["politica"]["protege_de_verdade"] is True

    def test_backup_avulso_nao_finge_ter_politica(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _gravar(banco, dispositivo_id, [_item("e5")])

        with banco.sessao() as sessao:
            detalhe = historico.detalhar(sessao, contexto, "e5")

        assert detalhe["politica"] is None

    def test_traz_a_trilha_encadeada_do_momento(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        self._com_entregas(banco, contexto)

        with banco.sessao() as sessao:
            detalhe = historico.detalhar(sessao, contexto, "e1")

        assert detalhe["trilha"], "sem trilha, a evidencia depende de acreditar na tela"
        assert all(linha["hash_atual"] for linha in detalhe["trilha"])

    def test_execucao_de_outra_organizacao_nao_e_detalhada(self, banco: Banco) -> None:
        """
        O isolamento vale aqui como em todo lugar, e aqui ele vale mais: o
        detalhe carrega nome de pasta e nome de maquina de quem executou.
        """
        dona = _organizacao(banco, "Padaria")
        alheia = _organizacao(banco, "Mercado")
        dispositivo_id = _dispositivo(banco, dona)
        _gravar(banco, dispositivo_id, [_item("e6")])

        with banco.sessao() as sessao, pytest.raises(LookupError):
            historico.detalhar(sessao, alheia, "e6")

    def test_execucao_que_nao_existe_e_recusada(self, banco: Banco) -> None:
        contexto = _organizacao(banco)

        with banco.sessao() as sessao, pytest.raises(LookupError):
            historico.detalhar(sessao, contexto, "nao-existe")


class TestOFusoQueSoATelaVia:
    """
    O defeito que nenhum teste de servidor pegava, porque so a tela mostra.

    O SQLite nao guarda fuso: grava-se `2026-08-30T17:30:00+00:00` e le-se
    `2026-08-30T17:30:00` pelado. O `isoformat()` direto do banco produzia esse
    texto sem fuso — e o NAVEGADOR le texto sem fuso como hora LOCAL.

    Efeito: uma execucao das 14:30 em Brasilia aparecia como 17:30, tres horas
    no futuro, na tela de quem acabara de ve-la acontecer. Dentro do servidor
    nada estava errado; os dois lados falam UTC.
    """

    def test_as_datas_saem_com_fuso(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _gravar(banco, dispositivo_id, [_item("e1")])

        with banco.sessao() as sessao:
            linha = historico.listar(sessao, contexto)[0]

        assert linha["iniciada_em"].endswith("+00:00"), (
            "sem fuso, o navegador le como hora local e mostra a execucao no futuro"
        )
        assert linha["terminada_em"].endswith("+00:00")

    def test_data_ausente_continua_vazia_e_nao_vira_agora(self, banco: Banco) -> None:
        """
        "Nunca terminou" e uma informacao.

        Trocar por um instante inventado apagaria a diferenca entre uma
        execucao em andamento e uma que acabou neste segundo.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _gravar(banco, dispositivo_id, [_item("e2", terminada_em="")])

        with banco.sessao() as sessao:
            linha = historico.listar(sessao, contexto)[0]

        assert linha["terminada_em"] == ""

    def test_a_trilha_tambem_sai_com_fuso(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _gravar(banco, dispositivo_id, [_item("e3")])

        with banco.sessao() as sessao:
            detalhe = historico.detalhar(sessao, contexto, "e3")

        assert detalhe["trilha"]
        assert all(linha["quando"].endswith("+00:00") for linha in detalhe["trilha"])
