"""Políticas no servidor (02.E).

O servidor guarda e valida; o Agente executa. Os testes cobrem o que dá errado
nessa divisão:

- configuração inválida gravada e só descoberta de madrugada;
- política desativada que continua rodando na máquina;
- tela afirmando "está valendo" quando a máquina está desligada e a política
  ainda não chegou lá.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from apps.api.app import canal, dispositivos, politicas
from apps.api.app.db import repositorio as repo
from apps.api.app.db.models import EstadoDispositivo, Papel, Politica
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


def _pedido(dispositivo_id: str, **configuracao: object) -> politicas.PedidoDePolitica:
    return politicas.PedidoDePolitica(
        nome="Diária", dispositivo_id=dispositivo_id, configuracao=dict(configuracao)
    )


class TestValidacao:
    def test_configuracao_invalida_e_recusada_na_gravacao(self, banco: Banco) -> None:
        """
        De madrugada não há quem corrija um campo errado.

        E a execução que falha por configuração inválida é indistinguível, no
        log, da que falha por disco cheio.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        with banco.sessao() as sessao, pytest.raises(politicas.PoliticaRecusada, match="hora"):
            politicas.criar(
                sessao,
                contexto,
                _pedido(dispositivo_id, agendamento={"tipo": "diario", "hora": "99:99"}),
            )

    def test_retencao_zerada_e_recusada(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        with (
            banco.sessao() as sessao,
            pytest.raises(politicas.PoliticaRecusada, match="retencao"),
        ):
            politicas.criar(
                sessao,
                contexto,
                _pedido(
                    dispositivo_id,
                    retencao={"diarias": 0, "semanais": 0, "mensais": 0},
                ),
            )

    def test_dispositivo_de_outra_organizacao_e_recusado(self, banco: Banco) -> None:
        primeira = _organizacao(banco, "Padaria")
        segunda = _organizacao(banco, "Oficina")
        alheio = _dispositivo(banco, primeira)

        with (
            banco.sessao() as sessao,
            pytest.raises(politicas.PoliticaRecusada, match="nao encontrado"),
        ):
            politicas.criar(sessao, segunda, _pedido(alheio))

    def test_dispositivo_revogado_nao_recebe_politica(self, banco: Banco) -> None:
        """
        A linha existiria e nunca executaria.

        A tela mostraria backup agendado que não acontece — o pior tipo de
        configuração: a que parece certa.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        with banco.sessao() as sessao:
            dispositivos.revogar(sessao, contexto, dispositivo_id=dispositivo_id)

        with (
            banco.sessao() as sessao,
            pytest.raises(politicas.PoliticaRecusada, match="revogado"),
        ):
            politicas.criar(sessao, contexto, _pedido(dispositivo_id))

    def test_operador_nao_cria_politica(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        operador = repo.Contexto(
            organizacao_id=contexto.organizacao_id,
            usuario_id=contexto.usuario_id,
            papel=Papel.OPERADOR,
        )

        with banco.sessao() as sessao, pytest.raises(repo.SemAcesso):
            politicas.criar(sessao, operador, _pedido(dispositivo_id))


class TestCicloDeVida:
    def test_criar_listar_alterar_remover(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        with banco.sessao() as sessao:
            criada = politicas.criar(
                sessao,
                contexto,
                _pedido(dispositivo_id, agendamento={"tipo": "diario", "hora": "02:00"}),
            )
            identificador = criada.id

        with banco.sessao() as sessao:
            lista = politicas.listar(sessao, contexto)
            assert len(lista) == 1
            assert lista[0]["configuracao"]["agendamento"]["hora"] == "02:00"

        with banco.sessao() as sessao:
            politicas.alterar(
                sessao,
                contexto,
                identificador,
                politicas.PedidoDePolitica(
                    nome="Noturna",
                    dispositivo_id=dispositivo_id,
                    configuracao={"agendamento": {"tipo": "diario", "hora": "23:30"}},
                ),
            )

        with banco.sessao() as sessao:
            lista = politicas.listar(sessao, contexto)
            assert lista[0]["nome"] == "Noturna"
            assert lista[0]["configuracao"]["agendamento"]["hora"] == "23:30"

        with banco.sessao() as sessao:
            politicas.remover(sessao, contexto, identificador)

        with banco.sessao() as sessao:
            assert politicas.listar(sessao, contexto) == []

    def test_uma_organizacao_nao_ve_a_politica_da_outra(self, banco: Banco) -> None:
        primeira = _organizacao(banco, "Padaria")
        segunda = _organizacao(banco, "Oficina")
        dispositivo_id = _dispositivo(banco, primeira)
        with banco.sessao() as sessao:
            politicas.criar(sessao, primeira, _pedido(dispositivo_id))

        with banco.sessao() as sessao:
            assert politicas.listar(sessao, segunda) == []
            assert len(politicas.listar(sessao, primeira)) == 1

    def test_politica_entra_na_trilha_de_auditoria(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        with banco.sessao() as sessao:
            politicas.criar(sessao, contexto, _pedido(dispositivo_id))

        with banco.sessao() as sessao:
            from apps.api.app.db.models import Auditoria

            acoes = [
                linha.acao for linha in sessao.execute(repo.escopo(Auditoria, contexto)).scalars()
            ]
            integra, _ = repo.conferir_trilha(sessao, contexto)

        assert "politica.criada" in acoes
        assert integra is True


class TestEnvioAoAgente:
    def test_politica_desativada_nao_e_enviada(self, banco: Banco) -> None:
        """
        Desativar tem que PARAR o backup, não só sumir da lista.

        Se a política continuasse na máquina, o backup seguiria rodando e
        ninguém entenderia por quê.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        with banco.sessao() as sessao:
            politicas.criar(
                sessao,
                contexto,
                politicas.PedidoDePolitica(
                    nome="Ligada", dispositivo_id=dispositivo_id, ativa=True
                ),
            )
            politicas.criar(
                sessao,
                contexto,
                politicas.PedidoDePolitica(
                    nome="Desligada", dispositivo_id=dispositivo_id, ativa=False
                ),
            )

        with banco.sessao() as sessao:
            enviadas = politicas.para_o_agente(sessao, contexto, dispositivo_id)

        assert [item["nome"] for item in enviadas] == ["Ligada"]

    def test_maquina_desligada_nao_e_erro_mas_tambem_nao_e_aplicada(self, banco: Banco) -> None:
        """
        A diferença entre "vai valer" e "está valendo".

        É a diferença entre ter backup hoje à noite e descobrir amanhã que não
        teve.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        with banco.sessao() as sessao:
            resultado = asyncio.run(politicas.sincronizar(sessao, contexto, dispositivo_id))

        assert resultado["aplicada"] is False
        assert "desligada" in resultado["motivo"]

    def test_configuracao_enviada_e_a_validada(self, banco: Banco) -> None:
        """
        O que vai para a máquina passa pelo mesmo schema do núcleo.

        Sem isso, um campo aceito no servidor e desconhecido no Agente
        produziria uma política pela metade, em silêncio.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        with banco.sessao() as sessao:
            politicas.criar(
                sessao,
                contexto,
                _pedido(
                    dispositivo_id,
                    agendamento={"tipo": "semanal", "hora": "03:15", "dia_da_semana": 5},
                    retencao={"diarias": 10, "semanais": 5, "mensais": 3},
                    usar_vss=True,
                ),
            )

        with banco.sessao() as sessao:
            enviada = politicas.para_o_agente(sessao, contexto, dispositivo_id)[0]

        configuracao = enviada["configuracao"]
        assert configuracao["agendamento"]["dia_da_semana"] == 5
        assert configuracao["retencao"]["diarias"] == 10
        assert configuracao["usar_vss"] is True


class TestHonestidade:
    def test_destino_na_propria_maquina_nao_conta_como_protecao(self, banco: Banco) -> None:
        """
        "Configurado" sem isto seria uma palavra que não significa nada.

        Pacote no mesmo computador não protege contra o disco morrer nem
        contra ransomware.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        with banco.sessao() as sessao:
            politicas.criar(
                sessao,
                contexto,
                _pedido(dispositivo_id, destino={"tipo": "local", "caminho": "D:\\b"}),
            )

        with banco.sessao() as sessao:
            assert politicas.listar(sessao, contexto)[0]["protege_de_verdade"] is False

    def test_destino_externo_conta(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        with banco.sessao() as sessao:
            politicas.criar(
                sessao,
                contexto,
                _pedido(dispositivo_id, destino={"tipo": "externo", "caminho": "E:\\b"}),
            )

        with banco.sessao() as sessao:
            assert politicas.listar(sessao, contexto)[0]["protege_de_verdade"] is True


class TestONuvemPrecisaDeBaldeAntes:
    """
    A pior combinação possível do produto, e ela era gravável.

    Uma política com destino `nuvem` passava pelo schema, contava como
    `protege_de_verdade` (o painel dizia **Protegido**) — e o Agente, ao rodar
    o agendamento, não tinha ramo para esse tipo: o pacote ficava no próprio
    computador e a execução terminava com sucesso. Cópia que nunca saiu do
    lugar, anunciada como proteção.

    O destino passou a funcionar de verdade (o envio é diferido, ver
    `nuvem.py`), e sobrou uma condição sem a qual ele volta a ser uma promessa
    vazia: **é preciso haver balde**. Sem credencial no cofre da organização,
    o pacote é feito e não tem para onde ir — e a política que o painel conta
    como proteção nunca entregaria nada.
    """

    def test_nuvem_e_recusada_na_criacao(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        with (
            banco.sessao() as sessao,
            pytest.raises(politicas.PoliticaRecusada, match="nuvem"),
        ):
            politicas.criar(sessao, contexto, _pedido(dispositivo_id, destino={"tipo": "nuvem"}))

    def test_a_recusa_diz_o_que_fazer_em_vez_de_so_negar(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        with banco.sessao() as sessao:
            try:
                politicas.criar(
                    sessao, contexto, _pedido(dispositivo_id, destino={"tipo": "nuvem"})
                )
            except politicas.PoliticaRecusada as erro:
                recado = str(erro)

        # Diz o que fazer, e com os nomes exatos dos segredos: "configure a
        # nuvem" mandaria a pessoa procurar onde.
        assert "s3.balde" in recado
        assert "cofre" in recado

    def test_alterar_para_nuvem_tambem_e_recusado(self, banco: Banco) -> None:
        """A porta dos fundos: criar no externo e depois trocar o destino."""
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        with banco.sessao() as sessao:
            registro = politicas.criar(
                sessao,
                contexto,
                _pedido(dispositivo_id, destino={"tipo": "externo", "caminho": "E:\\b"}),
            )
            politica_id = registro.id

        with (
            banco.sessao() as sessao,
            pytest.raises(politicas.PoliticaRecusada, match="nuvem"),
        ):
            politicas.alterar(
                sessao, contexto, politica_id, _pedido(dispositivo_id, destino={"tipo": "nuvem"})
            )

    def test_os_outros_destinos_continuam_passando(self, banco: Banco) -> None:
        """Guarda contra a recusa virar uma peneira grossa demais."""
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        for tipo, caminho in (
            ("nenhum", ""),
            ("local", "D:\\b"),
            ("externo", "E:\\b"),
            ("rede", "\\\\servidor\\backups"),
        ):
            with banco.sessao() as sessao:
                registro = politicas.criar(
                    sessao,
                    contexto,
                    _pedido(dispositivo_id, destino={"tipo": tipo, "caminho": caminho}),
                )
                assert registro.id


def test_politica_gravada_pode_ser_relida_pelo_nucleo(banco: Banco) -> None:
    """
    O formato é o mesmo dos dois lados.

    Duas definições paralelas divergem no primeiro campo novo — e a divergência
    aparece como política que não executa.
    """
    from autotarefas.tasks.politica import Politica as ConfiguracaoDePolitica

    contexto = _organizacao(banco)
    dispositivo_id = _dispositivo(banco, contexto)
    with banco.sessao() as sessao:
        criada = politicas.criar(
            sessao,
            contexto,
            _pedido(dispositivo_id, agendamento={"tipo": "mensal", "dia_do_mes": 28}),
        )
        identificador = criada.id

    with banco.sessao() as sessao:
        registro = sessao.get(Politica, identificador)
        assert registro is not None
        configuracao = ConfiguracaoDePolitica.de_json(registro.configuracao)

    assert configuracao.agendamento.dia_do_mes == 28
    assert EstadoDispositivo.ATIVO


class TestAExecucaoSabeDeQualPoliticaVeio:
    """
    "Executar agora" numa politica produzia uma execucao orfa.

    A linha aparecia no historico sem pertencer a politica nenhuma. E o
    veredito de protecao agrupa POR politica: um backup que acabara de rodar
    com sucesso deixava a propria politica em "nunca concluiu uma execucao" —
    o oposto do que tinha acabado de acontecer, na mesma tela.
    """

    def test_a_politica_citada_fica_gravada_na_execucao(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        with banco.sessao() as sessao:
            politica = politicas.criar(sessao, contexto, _pedido(dispositivo_id))
            politica_id = politica.id

        pedido = dispositivos.PedidoDeBackup(politica_id=politica_id)
        with banco.sessao() as sessao:
            achada = dispositivos._politica_da_organizacao(sessao, contexto, pedido.politica_id)

        assert achada == politica_id

    def test_backup_avulso_continua_sem_politica(self, banco: Banco) -> None:
        """
        O botao da tela de maquinas roda um backup que nao e de politica alguma.

        Inventar um vinculo ali sujaria o historico de uma politica com uma
        execucao que ela nao pediu.
        """
        contexto = _organizacao(banco)

        with banco.sessao() as sessao:
            assert dispositivos._politica_da_organizacao(sessao, contexto, "") is None

    def test_politica_de_outra_organizacao_e_ignorada(self, banco: Banco) -> None:
        """
        Conferir, e nao confiar no id que chegou.

        Aceitar como veio carimbaria a execucao de uma empresa com a politica
        de outra — e o veredito de protecao passaria a somar coisas de
        organizacoes diferentes.
        """
        dona = _organizacao(banco, "Padaria")
        alheia = _organizacao(banco, "Mercado")
        dispositivo_alheio = _dispositivo(banco, alheia, chave="k2")
        with banco.sessao() as sessao:
            da_outra = politicas.criar(sessao, alheia, _pedido(dispositivo_alheio)).id

        with banco.sessao() as sessao:
            achada = dispositivos._politica_da_organizacao(sessao, dona, da_outra)

        assert achada is None

    def test_politica_que_nao_existe_e_ignorada(self, banco: Banco) -> None:
        contexto = _organizacao(banco)

        with banco.sessao() as sessao:
            assert dispositivos._politica_da_organizacao(sessao, contexto, "nao-existe") is None

    def test_a_execucao_sem_politica_e_gravavel_de_verdade(self, banco: Banco) -> None:
        """
        O teste que faltava: os outros conferiam a funcao, e nao a LINHA.

        `politica_id` e chave estrangeira, e o banco roda com
        `PRAGMA foreign_keys=ON`. String vazia nao e nulo — nao existe politica
        de id "" —, entao o backup avulso morria no INSERT inteiro, com um erro
        que nao falava de politica nenhuma. Uma funcao que devolve o valor
        combinado e uma linha que o banco recusa sao coisas diferentes, e so a
        segunda e o produto.
        """
        from apps.api.app.db.models import Execucao, ResultadoExecucao

        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        with banco.sessao() as sessao:
            sessao.add(
                Execucao(
                    organizacao_id=contexto.organizacao_id,
                    dispositivo_id=dispositivo_id,
                    politica_id=dispositivos._politica_da_organizacao(sessao, contexto, ""),
                    origem="manual",
                    resultado=ResultadoExecucao.EM_ANDAMENTO,
                )
            )
            sessao.flush()

        with banco.sessao() as sessao:
            gravadas = sessao.execute(repo.escopo(Execucao, contexto)).scalars().all()

        assert len(gravadas) == 1
        assert gravadas[0].politica_id is None
