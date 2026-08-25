"""Testes do pareamento, das duas pontas (G.3.2).

O pareamento e o momento em que uma maquina sem credencial nenhuma passa a
pertencer a uma organizacao. Os testes cobrem o caminho feliz uma vez e as
recusas varias — codigo usado, vencido, inexistente, maquina repetida — porque
e nas recusas que mora a diferenca entre um cadastro e um convite aberto.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.agente.agente import identidade as ident
from apps.agente.agente import pareamento
from apps.agente.agente.config import Configuracao, Local
from apps.api.app import dispositivos
from apps.api.app.db import repositorio as repo
from apps.api.app.db.models import EstadoDispositivo, Papel, agora
from apps.api.app.db.sessao import Banco

HTTP_OK = 200
HTTP_FORBIDDEN = 403


@pytest.fixture
def banco() -> Iterator[Banco]:
    instancia = Banco("sqlite:///:memory:")
    instancia.criar_esquema()
    yield instancia
    instancia.descartar()


def _organizacao(banco: Banco, nome: str = "Padaria", papel: Papel = Papel.DONO) -> repo.Contexto:
    with banco.sessao() as sessao:
        organizacao = repo.criar_organizacao(sessao, nome=nome, dominio=f"{nome.lower()}.com.br")
        usuario = repo.criar_usuario(
            sessao,
            email=f"dono@{nome.lower()}.com.br",
            nome="Dono",
            emissor="bootstrap",
            assunto=nome,
        )
        repo.vincular(sessao, organizacao=organizacao, usuario=usuario, papel=papel)
        return repo.Contexto(organizacao_id=organizacao.id, usuario_id=usuario.id, papel=papel)


# ============================================================
# O codigo
# ============================================================


class TestCodigo:
    def test_formato_legivel_e_sem_ambiguidade(self) -> None:
        """
        Quem digita `0` achando que e `O` erra o pareamento e culpa o produto.

        O alfabeto exclui os pares que se confundem ao ler de uma tela e
        digitar em outra maquina.
        """
        codigo = dispositivos.gerar_codigo()

        assert len(codigo) == 9
        assert codigo[4] == "-"
        for caractere in codigo.replace("-", ""):
            assert caractere in dispositivos.ALFABETO
        for confuso in "01OIL":
            assert confuso not in dispositivos.ALFABETO

    def test_dois_codigos_sao_diferentes(self) -> None:
        assert dispositivos.gerar_codigo() != dispositivos.gerar_codigo()

    @pytest.mark.parametrize(
        "digitado",
        ["abcd-efgh", "ABCDEFGH", " abcd efgh ", "AbCd-EfGh"],
    )
    def test_aceita_como_a_pessoa_digitou(self, digitado: str) -> None:
        """
        Minuscula e falta de hifen sao erro de digitacao, nao invasao.

        Recusar por causa disso so gera chamado de suporte.
        """
        assert dispositivos.normalizar(digitado) == "ABCD-EFGH"

    def test_operador_nao_emite_codigo(self, banco: Banco) -> None:
        """
        Emitir codigo e autorizar uma maquina nova: e administracao.

        Se um operador pudesse, bastaria uma conta comum comprometida para
        colocar uma maquina estranha dentro da organizacao.
        """
        contexto = _organizacao(banco, papel=Papel.OPERADOR)
        with banco.sessao() as sessao, pytest.raises(repo.SemAcesso):
            dispositivos.emitir(sessao, contexto)


# ============================================================
# Parear
# ============================================================


class TestParear:
    def _codigo(self, banco: Banco, contexto: repo.Contexto) -> str:
        with banco.sessao() as sessao:
            return dispositivos.emitir(sessao, contexto).codigo

    def test_codigo_valido_registra_a_maquina(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        codigo = self._codigo(banco, contexto)

        with banco.sessao() as sessao:
            dispositivo = dispositivos.parear(
                sessao,
                codigo=codigo,
                chave_publica="chave-publica-de-teste",
                nome="PC da loja",
                sistema="Windows 11",
                versao_agente="0.1.0",
            )

        assert dispositivo.organizacao_id == contexto.organizacao_id
        assert dispositivo.estado is EstadoDispositivo.ATIVO
        assert dispositivo.pareado_em is not None

    def test_codigo_serve_uma_vez_so(self, banco: Banco) -> None:
        """
        Codigo reaproveitado cadastraria maquinas que ninguem autorizou.
        """
        contexto = _organizacao(banco)
        codigo = self._codigo(banco, contexto)

        with banco.sessao() as sessao:
            dispositivos.parear(
                sessao,
                codigo=codigo,
                chave_publica="chave-1",
                nome="PC",
                sistema="",
                versao_agente="",
            )

        with (
            banco.sessao() as sessao,
            pytest.raises(dispositivos.PareamentoRecusado, match="usado"),
        ):
            dispositivos.parear(
                sessao,
                codigo=codigo,
                chave_publica="chave-2",
                nome="PC",
                sistema="",
                versao_agente="",
            )

    def test_codigo_vencido_nao_serve(self, banco: Banco) -> None:
        """Codigo esquecido num bilhete deixa de valer sozinho."""
        contexto = _organizacao(banco)
        codigo = self._codigo(banco, contexto)
        depois = agora() + timedelta(minutes=dispositivos.VALIDADE_MINUTOS + 1)

        with (
            banco.sessao() as sessao,
            pytest.raises(dispositivos.PareamentoRecusado, match="venceu"),
        ):
            dispositivos.parear(
                sessao,
                codigo=codigo,
                chave_publica="chave-1",
                nome="PC",
                sistema="",
                versao_agente="",
                momento=depois,
            )

    def test_codigo_inventado_nao_serve(self, banco: Banco) -> None:
        _organizacao(banco)
        with (
            banco.sessao() as sessao,
            pytest.raises(dispositivos.PareamentoRecusado, match="invalido"),
        ):
            dispositivos.parear(
                sessao,
                codigo="ZZZZ-ZZZZ",
                chave_publica="chave-1",
                nome="PC",
                sistema="",
                versao_agente="",
            )

    def test_mesma_maquina_nao_entra_em_duas_organizacoes(self, banco: Banco) -> None:
        """
        Seria um caminho para ler o backup de uma empresa a partir de outra.
        """
        primeira = _organizacao(banco, nome="Padaria")
        segunda = _organizacao(banco, nome="Oficina")

        with banco.sessao() as sessao:
            dispositivos.parear(
                sessao,
                codigo=dispositivos.emitir(sessao, primeira).codigo,
                chave_publica="a-mesma-chave",
                nome="PC",
                sistema="",
                versao_agente="",
            )

        with banco.sessao() as sessao:
            codigo = dispositivos.emitir(sessao, segunda).codigo
        with (
            banco.sessao() as sessao,
            pytest.raises(dispositivos.PareamentoRecusado, match="ja esta pareada"),
        ):
            dispositivos.parear(
                sessao,
                codigo=codigo,
                chave_publica="a-mesma-chave",
                nome="PC",
                sistema="",
                versao_agente="",
            )

    def test_pareamento_entra_na_trilha_de_auditoria(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        codigo = self._codigo(banco, contexto)

        with banco.sessao() as sessao:
            dispositivos.parear(
                sessao, codigo=codigo, chave_publica="k", nome="PC", sistema="", versao_agente=""
            )

        with banco.sessao() as sessao:
            integra, _ = repo.conferir_trilha(sessao, contexto)
            from apps.api.app.db.models import Auditoria

            acoes = [
                linha.acao for linha in sessao.execute(repo.escopo(Auditoria, contexto)).scalars()
            ]

        assert integra is True
        assert "dispositivo.pareado" in acoes


# ============================================================
# Isolamento e revogacao
# ============================================================


class TestAdministracao:
    def test_uma_empresa_nao_lista_o_dispositivo_da_outra(self, banco: Banco) -> None:
        primeira = _organizacao(banco, nome="Padaria")
        segunda = _organizacao(banco, nome="Oficina")
        with banco.sessao() as sessao:
            dispositivos.parear(
                sessao,
                codigo=dispositivos.emitir(sessao, primeira).codigo,
                chave_publica="k1",
                nome="PC da padaria",
                sistema="",
                versao_agente="",
            )

        with banco.sessao() as sessao:
            assert dispositivos.listar(sessao, segunda) == []
            assert len(dispositivos.listar(sessao, primeira)) == 1

    def test_revogar_nao_apaga_o_historico(self, banco: Banco) -> None:
        """
        O historico de execucoes precisa continuar apontando para uma maquina.

        Apagar deixaria buracos na auditoria justamente onde ela mais serve.
        """
        contexto = _organizacao(banco)
        with banco.sessao() as sessao:
            dispositivo = dispositivos.parear(
                sessao,
                codigo=dispositivos.emitir(sessao, contexto).codigo,
                chave_publica="k1",
                nome="PC",
                sistema="",
                versao_agente="",
            )
            identificador = dispositivo.id

        with banco.sessao() as sessao:
            revogado = dispositivos.revogar(sessao, contexto, dispositivo_id=identificador)

        assert revogado.estado is EstadoDispositivo.REVOGADO
        with banco.sessao() as sessao:
            assert len(dispositivos.listar(sessao, contexto)) == 1

    def test_nao_da_para_revogar_dispositivo_de_outra_empresa(self, banco: Banco) -> None:
        primeira = _organizacao(banco, nome="Padaria")
        segunda = _organizacao(banco, nome="Oficina")
        with banco.sessao() as sessao:
            alvo = dispositivos.parear(
                sessao,
                codigo=dispositivos.emitir(sessao, primeira).codigo,
                chave_publica="k1",
                nome="PC",
                sistema="",
                versao_agente="",
            ).id

        with banco.sessao() as sessao, pytest.raises(dispositivos.PareamentoRecusado):
            dispositivos.revogar(sessao, segunda, dispositivo_id=alvo)

    def test_impressao_bate_com_a_do_agente(self, tmp_path: Path) -> None:
        """
        A impressao que a tela mostra tem que ser a mesma que a maquina mostra.

        Se divergirem, a conferencia visual do pareamento nao serve para nada.
        """
        guarda = ident.Guarda(tmp_path / "cfg", usar_cofre_do_sistema=False)
        identidade, _ = ident.obter_ou_criar(guarda)

        assert dispositivos.impressao_de(identidade.publica_em_base64) == identidade.impressao


# ============================================================
# O Agente falando com o servidor de verdade
# ============================================================


class TestAgenteContraOServidor:
    @pytest.fixture
    def cliente(self, banco: Banco) -> Iterator[TestClient]:
        """Servidor real, com banco proprio, alcancado por transporte ASGI."""
        from apps.api.app.db.atual import definir_banco
        from apps.api.app.main import app

        definir_banco(banco)
        with TestClient(app, base_url="http://live.teste") as testador:
            yield testador
        definir_banco(None)

    def test_agente_pareia_e_grava_a_configuracao(
        self, banco: Banco, cliente: TestClient, tmp_path: Path
    ) -> None:
        contexto = _organizacao(banco)
        with banco.sessao() as sessao:
            codigo = dispositivos.emitir(sessao, contexto).codigo

        guarda = ident.Guarda(tmp_path / "cfg", usar_cofre_do_sistema=False)
        local = Local(pasta=tmp_path / "cfg")

        resultado = pareamento.parear(
            servidor="http://live.teste",
            codigo=codigo,
            guarda=guarda,
            local=local,
            nome="PC da loja",
            cliente=cliente,
        )

        assert resultado.dispositivo_id
        gravada = local.carregar()
        assert gravada.pareado is True
        assert gravada.dispositivo_id == resultado.dispositivo_id
        assert gravada.servidor == "http://live.teste"

    def test_a_privada_nunca_vai_para_o_servidor(
        self, banco: Banco, cliente: TestClient, tmp_path: Path
    ) -> None:
        """
        O modelo inteiro depende disto.

        O que sai da maquina e a publica; a privada fica. Se um dia a privada
        vazar no pareamento, o par de chaves deixa de valer mais que um token.
        """
        contexto = _organizacao(banco)
        with banco.sessao() as sessao:
            codigo = dispositivos.emitir(sessao, contexto).codigo

        guarda = ident.Guarda(tmp_path / "cfg", usar_cofre_do_sistema=False)
        local = Local(pasta=tmp_path / "cfg")
        identidade, _ = ident.obter_ou_criar(guarda)
        privada = identidade.privada.private_bytes_raw().hex()

        pareamento.parear(
            servidor="http://live.teste",
            codigo=codigo,
            guarda=guarda,
            local=local,
            cliente=cliente,
        )

        with banco.sessao() as sessao:
            from apps.api.app.db.models import Dispositivo

            guardado = sessao.execute(repo.escopo(Dispositivo, contexto)).scalars().one()
            assert privada not in guardado.chave_publica
            assert guardado.chave_publica == identidade.publica_em_base64

    def test_codigo_errado_nao_grava_configuracao(
        self, banco: Banco, cliente: TestClient, tmp_path: Path
    ) -> None:
        """
        Falhou o pareamento, nada e gravado.

        Uma configuracao apontando para um dispositivo que nao existe faria o
        Agente tentar se conectar para sempre, sem dizer por que.
        """
        _organizacao(banco)
        guarda = ident.Guarda(tmp_path / "cfg", usar_cofre_do_sistema=False)
        local = Local(pasta=tmp_path / "cfg")

        with pytest.raises(pareamento.PareamentoFalhou, match="recusou"):
            pareamento.parear(
                servidor="http://live.teste",
                codigo="ZZZZ-ZZZZ",
                guarda=guarda,
                local=local,
                cliente=cliente,
            )

        assert local.carregar().pareado is False

    def test_repetir_o_comando_reaproveita_a_mesma_identidade(
        self, banco: Banco, cliente: TestClient, tmp_path: Path
    ) -> None:
        """
        Tentativa que falha nao pode deixar chave orfa na maquina.

        Gerar par novo a cada tentativa encheria o cofre do sistema de chaves
        que nunca serviram para nada.
        """
        _organizacao(banco)
        guarda = ident.Guarda(tmp_path / "cfg", usar_cofre_do_sistema=False)
        local = Local(pasta=tmp_path / "cfg")

        for _ in range(3):
            with pytest.raises(pareamento.PareamentoFalhou):
                pareamento.parear(
                    servidor="http://live.teste",
                    codigo="ZZZZ-ZZZZ",
                    guarda=guarda,
                    local=local,
                    cliente=cliente,
                )

        assert ident.carregar(guarda).impressao

    def test_pastas_autorizadas_sobrevivem_a_um_novo_pareamento(
        self, banco: Banco, cliente: TestClient, tmp_path: Path
    ) -> None:
        """
        Reparear nao pode apagar o consentimento dado na maquina.

        Se apagasse, o backup pararia de copiar sem ninguem perceber.
        """
        contexto = _organizacao(banco)
        with banco.sessao() as sessao:
            codigo = dispositivos.emitir(sessao, contexto).codigo

        pasta = tmp_path / "dados"
        pasta.mkdir()
        local = Local(pasta=tmp_path / "cfg")
        local.gravar(Configuracao().com_raiz(pasta))

        pareamento.parear(
            servidor="http://live.teste",
            codigo=codigo,
            guarda=ident.Guarda(tmp_path / "cfg", usar_cofre_do_sistema=False),
            local=local,
            cliente=cliente,
        )

        assert local.carregar().raizes == (str(pasta.resolve()),)
