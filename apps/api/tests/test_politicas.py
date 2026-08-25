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
