"""Testes do modelo multiempresa: isolamento, papeis e trilha de auditoria.

O que estes testes protegem nao e o ORM — e a promessa de que o dado de uma
empresa nunca aparece para outra. Isolamento e o tipo de coisa que parece
funcionar ate o dia em que nao funciona, entao cada caminho de leitura tem um
teste que tenta atravessar a fronteira de proposito.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import select

from apps.api.app.db import repositorio as repo
from apps.api.app.db.models import (
    Auditoria,
    Dispositivo,
    EstadoDispositivo,
    Organizacao,
    Papel,
    Usuario,
)
from apps.api.app.db.sessao import Banco


@pytest.fixture
def banco() -> Iterator[Banco]:
    """
    Banco proprio por teste, em arquivo temporario na memoria do processo.

    Um por teste, e nao um compartilhado: banco compartilhado faria um teste
    enxergar o dado do outro, que e exatamente a falha que estamos testando.
    """
    instancia = Banco("sqlite:///:memory:")
    instancia.criar_esquema()
    yield instancia
    instancia.descartar()


def _empresa(banco: Banco, nome: str, dominio: str, email: str, papel: Papel = Papel.DONO):
    """Cria organizacao + pessoa + vinculo e devolve (contexto, ids)."""
    with banco.sessao() as sessao:
        organizacao = repo.criar_organizacao(sessao, nome=nome, dominio=dominio)
        usuario = repo.criar_usuario(
            sessao, email=email, nome=nome, emissor="bootstrap", assunto=email
        )
        repo.vincular(sessao, organizacao=organizacao, usuario=usuario, papel=papel)
        return organizacao.id, usuario.id


# ============================================================
# Isolamento entre organizacoes
# ============================================================


class TestIsolamento:
    def test_uma_empresa_nao_ve_o_dispositivo_da_outra(self, banco: Banco) -> None:
        org_a, usuario_a = _empresa(banco, "Padaria A", "a.com.br", "ana@a.com.br")
        org_b, usuario_b = _empresa(banco, "Oficina B", "b.com.br", "bruno@b.com.br")

        with banco.sessao() as sessao:
            sessao.add(
                Dispositivo(organizacao_id=org_b, nome="PC do Bruno", chave_publica="chave-b")
            )

        with banco.sessao() as sessao:
            contexto = repo.abrir_contexto(sessao, usuario_id=usuario_a, organizacao_id=org_a)
            vistos = list(sessao.execute(repo.escopo(Dispositivo, contexto)).scalars())
            assert vistos == []

            contexto_b = repo.abrir_contexto(sessao, usuario_id=usuario_b, organizacao_id=org_b)
            assert [
                d.nome for d in sessao.execute(repo.escopo(Dispositivo, contexto_b)).scalars()
            ] == ["PC do Bruno"]

    def test_pedir_contexto_de_organizacao_alheia_e_recusado(self, banco: Banco) -> None:
        """
        O ataque mais simples: trocar o id da organizacao na chamada.

        Sem vinculo nao ha contexto, e sem contexto nao ha consulta.
        """
        org_a, _ = _empresa(banco, "Padaria A", "a.com.br", "ana@a.com.br")
        _, usuario_b = _empresa(banco, "Oficina B", "b.com.br", "bruno@b.com.br")

        with banco.sessao() as sessao, pytest.raises(repo.SemAcesso):
            repo.abrir_contexto(sessao, usuario_id=usuario_b, organizacao_id=org_a)

    def test_modelo_sem_organizacao_nao_aceita_escopo(self, banco: Banco) -> None:
        """
        Guarda contra a tabela futura que esquecer a coluna.

        Falhar alto na primeira consulta e melhor do que devolver dado de
        todo mundo silenciosamente.
        """
        contexto = repo.Contexto(organizacao_id="x", usuario_id=None, papel=Papel.DONO)
        with pytest.raises(TypeError, match="organizacao_id"):
            repo.escopo(Usuario, contexto)

    def test_apagar_organizacao_leva_os_dispositivos(self, banco: Banco) -> None:
        """
        Chave estrangeira ligada de verdade no SQLite.

        Sem o `PRAGMA foreign_keys=ON`, o CASCADE seria decoracao e o
        dispositivo de um cliente encerrado continuaria no banco.
        """
        org, _ = _empresa(banco, "Padaria A", "a.com.br", "ana@a.com.br")
        with banco.sessao() as sessao:
            sessao.add(Dispositivo(organizacao_id=org, nome="PC", chave_publica="k"))

        with banco.sessao() as sessao:
            sessao.delete(sessao.get(Organizacao, org))

        with banco.sessao() as sessao:
            assert list(sessao.execute(select(Dispositivo)).scalars()) == []


# ============================================================
# Papeis
# ============================================================


class TestPapeis:
    def test_leitor_nao_administra_nem_opera(self, banco: Banco) -> None:
        org, usuario = _empresa(banco, "Padaria A", "a.com.br", "ana@a.com.br", papel=Papel.LEITOR)
        with banco.sessao() as sessao:
            contexto = repo.abrir_contexto(sessao, usuario_id=usuario, organizacao_id=org)

        assert contexto.administra is False
        assert contexto.opera is False
        with pytest.raises(repo.SemAcesso):
            contexto.exigir_administracao()
        with pytest.raises(repo.SemAcesso):
            contexto.exigir_operacao()

    def test_operador_executa_mas_nao_configura(self, banco: Banco) -> None:
        """
        A separacao que importa quando uma chave vaza.

        Quem so opera pode disparar backup; nao pode autorizar pasta nova nem
        trocar o destino.
        """
        org, usuario = _empresa(
            banco, "Padaria A", "a.com.br", "ana@a.com.br", papel=Papel.OPERADOR
        )
        with banco.sessao() as sessao:
            contexto = repo.abrir_contexto(sessao, usuario_id=usuario, organizacao_id=org)

        contexto.exigir_operacao()
        with pytest.raises(repo.SemAcesso):
            contexto.exigir_administracao()

    def test_dispositivo_age_como_operador(self, banco: Banco) -> None:
        org, _ = _empresa(banco, "Padaria A", "a.com.br", "ana@a.com.br")
        with banco.sessao() as sessao:
            dispositivo = Dispositivo(
                organizacao_id=org,
                nome="PC",
                chave_publica="k",
                estado=EstadoDispositivo.ATIVO,
            )
            sessao.add(dispositivo)
            sessao.flush()
            contexto = repo.contexto_de_dispositivo(sessao, dispositivo_id=dispositivo.id)

        assert contexto.organizacao_id == org
        assert contexto.usuario_id is None
        assert contexto.opera is True
        assert contexto.administra is False


# ============================================================
# Dominio de e-mail
# ============================================================


class TestDominio:
    @pytest.mark.parametrize(
        "email",
        ["alguem@gmail.com", "alguem@hotmail.com", "alguem@outlook.com.br"],
    )
    def test_dominio_publico_nunca_vira_chave_de_organizacao(
        self, banco: Banco, email: str
    ) -> None:
        """
        Sem esta regra, quem tem gmail entraria na "organizacao gmail.com".

        E a diferenca entre entrar na empresa onde se trabalha e entrar na
        conta de um estranho.
        """
        assert repo.dominio_de(email) is None
        with banco.sessao() as sessao:
            assert repo.organizacao_por_dominio(sessao, "gmail.com") is None

    def test_dominio_corporativo_encontra_a_organizacao(self, banco: Banco) -> None:
        org, _ = _empresa(banco, "Padaria A", "padaria-a.com.br", "ana@padaria-a.com.br")
        assert repo.dominio_de("outro@padaria-a.com.br") == "padaria-a.com.br"
        with banco.sessao() as sessao:
            achada = repo.organizacao_por_dominio(sessao, "padaria-a.com.br")
            assert achada is not None
            assert achada.id == org


# ============================================================
# Trilha de auditoria
# ============================================================


class TestTrilha:
    def _com_trilha(self, banco: Banco) -> tuple[str, str]:
        org, usuario = _empresa(banco, "Padaria A", "a.com.br", "ana@a.com.br")
        with banco.sessao() as sessao:
            contexto = repo.abrir_contexto(sessao, usuario_id=usuario, organizacao_id=org)
            repo.registrar(sessao, contexto, acao="organizacao.criada", alvo="Padaria A")
            repo.registrar(sessao, contexto, acao="dispositivo.pareado", alvo="PC da loja")
            repo.registrar(sessao, contexto, acao="politica.criada", alvo="Diaria")
        return org, usuario

    def test_trilha_intacta_confere(self, banco: Banco) -> None:
        org, usuario = self._com_trilha(banco)
        with banco.sessao() as sessao:
            contexto = repo.abrir_contexto(sessao, usuario_id=usuario, organizacao_id=org)
            integra, explicacao = repo.conferir_trilha(sessao, contexto)

        assert integra is True
        assert "3 registro(s)" in explicacao

    def test_alterar_um_registro_quebra_a_corrente(self, banco: Banco) -> None:
        """
        O caso realista: alguem edita uma linha direto no banco.

        Reescrever a trilha inteira continua possivel para quem administra o
        banco; o que a corrente impede e a edicao silenciosa de um registro
        isolado — trocar "apagou" por "conferiu" e seguir a vida.
        """
        org, usuario = self._com_trilha(banco)

        with banco.sessao() as sessao:
            contexto = repo.abrir_contexto(sessao, usuario_id=usuario, organizacao_id=org)
            linha = list(
                sessao.execute(
                    repo.escopo(Auditoria, contexto).order_by(Auditoria.quando.asc())
                ).scalars()
            )[1]
            linha.alvo = "outra coisa"

        with banco.sessao() as sessao:
            contexto = repo.abrir_contexto(sessao, usuario_id=usuario, organizacao_id=org)
            integra, explicacao = repo.conferir_trilha(sessao, contexto)

        assert integra is False
        assert "alterada depois de gravada" in explicacao

    def test_cada_organizacao_tem_a_propria_corrente(self, banco: Banco) -> None:
        """
        Corrente por organizacao, nao global.

        Uma corrente unica faria a atividade de uma empresa influenciar o hash
        da outra — e um cliente conseguiria inferir que houve movimento na
        conta do vizinho.
        """
        org_a, usuario_a = self._com_trilha(banco)
        org_b, usuario_b = _empresa(banco, "Oficina B", "b.com.br", "bruno@b.com.br")

        with banco.sessao() as sessao:
            contexto_b = repo.abrir_contexto(sessao, usuario_id=usuario_b, organizacao_id=org_b)
            primeira = repo.registrar(sessao, contexto_b, acao="organizacao.criada")
            assert primeira.hash_anterior == ""

        with banco.sessao() as sessao:
            contexto_a = repo.abrir_contexto(sessao, usuario_id=usuario_a, organizacao_id=org_a)
            contexto_b = repo.abrir_contexto(sessao, usuario_id=usuario_b, organizacao_id=org_b)
            assert repo.conferir_trilha(sessao, contexto_a)[0] is True
            assert repo.conferir_trilha(sessao, contexto_b) == (True, "1 registro(s) conferem")

    def test_trilha_nao_mostra_registro_de_outra_empresa(self, banco: Banco) -> None:
        org_a, usuario_a = self._com_trilha(banco)
        _, usuario_b = _empresa(banco, "Oficina B", "b.com.br", "bruno@b.com.br")
        del usuario_b

        with banco.sessao() as sessao:
            contexto = repo.abrir_contexto(sessao, usuario_id=usuario_a, organizacao_id=org_a)
            linhas = list(sessao.execute(repo.escopo(Auditoria, contexto)).scalars())

        assert {linha.organizacao_id for linha in linhas} == {org_a}


# ============================================================
# Datas
# ============================================================


def test_data_volta_do_banco_com_fuso(banco: Banco) -> None:
    """
    O SQLite devolve data sem fuso; o PostgreSQL, com.

    Retencao, agendamento e trilha comparam datas. Se a normalizacao sumir,
    a diferenca entre os dois bancos vira bug de producao que nao aparece em
    teste — entao ela tem teste proprio.
    """
    from apps.api.app.db.models import em_utc

    org, _ = _empresa(banco, "Padaria A", "a.com.br", "ana@a.com.br")
    with banco.sessao() as sessao:
        sessao.expire_all()
        organizacao = sessao.get(Organizacao, org)
        assert organizacao is not None
        assert em_utc(organizacao.criada_em).tzinfo is not None
