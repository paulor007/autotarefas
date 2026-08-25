"""Aviso de backup (02.E).

A separacao entre REGISTRAR e ENVIAR e o que este modulo protege. Marcar
"notificado" quando nada saiu da maquina e a mentira mais facil desta parte do
produto: um cliente que confia num e-mail que nunca chegou fica sem backup e
sem saber.
"""

from __future__ import annotations

import base64
from collections.abc import Iterator

import pytest

from apps.api.app import cofre, notificacoes
from apps.api.app.db import repositorio as repo
from apps.api.app.db.models import Auditoria, Papel, ResultadoExecucao
from apps.api.app.db.sessao import Banco
from autotarefas.tasks.politica import QuandoNotificar

CHAVE = base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef").decode()


@pytest.fixture
def banco() -> Iterator[Banco]:
    instancia = Banco("sqlite:///:memory:")
    instancia.criar_esquema()
    yield instancia
    instancia.descartar()


@pytest.fixture
def com_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(cofre.VAR_CHAVE, CHAVE)


def _contexto(banco: Banco) -> repo.Contexto:
    with banco.sessao() as sessao:
        organizacao = repo.criar_organizacao(sessao, nome="Padaria", dominio="padaria.com.br")
        usuario = repo.criar_usuario(
            sessao,
            email="dono@padaria.com.br",
            nome="Dono",
            emissor="bootstrap",
            assunto="dono",
        )
        repo.vincular(sessao, organizacao=organizacao, usuario=usuario, papel=Papel.DONO)
        return repo.Contexto(organizacao_id=organizacao.id, usuario_id=usuario.id, papel=Papel.DONO)


class TestQuandoAvisar:
    def test_nunca_nao_avisa_nem_em_falha(self) -> None:
        assert notificacoes.deve_avisar(QuandoNotificar.NUNCA, ResultadoExecucao.FALHA) is False

    def test_sempre_avisa_ate_no_sucesso(self) -> None:
        assert notificacoes.deve_avisar(QuandoNotificar.SEMPRE, ResultadoExecucao.SUCESSO) is True

    def test_problema_inclui_a_ressalva(self) -> None:
        """
        Backup que copiou quase tudo e exatamente o caso em que alguem precisa
        olhar — e o unico que passaria despercebido se so falha avisasse.
        """
        assert (
            notificacoes.deve_avisar(QuandoNotificar.PROBLEMA, ResultadoExecucao.COM_RESSALVA)
            is True
        )

    def test_problema_nao_avisa_no_sucesso(self) -> None:
        """Aviso que sempre chega vira ruido, e ruido e filtrado."""
        assert (
            notificacoes.deve_avisar(QuandoNotificar.PROBLEMA, ResultadoExecucao.SUCESSO) is False
        )


class TestTexto:
    def test_o_assunto_diz_o_desfecho(self) -> None:
        """
        Quem recebe dez e-mails por dia decide pelo assunto se olha agora.

        E "depois" e quando o backup nao existe.
        """
        assunto, _ = notificacoes.texto_do_aviso(
            dispositivo="PC da loja",
            politica="Diária",
            resultado=ResultadoExecucao.FALHA,
            ressalva="disco cheio",
        )

        assert "FALHOU" in assunto
        assert "PC da loja" in assunto

    def test_ressalva_explica_que_o_pacote_serve(self) -> None:
        _, corpo = notificacoes.texto_do_aviso(
            dispositivo="PC",
            politica="Diária",
            resultado=ResultadoExecucao.COM_RESSALVA,
            ressalva="1 arquivo travado",
        )

        assert "utilizável" in corpo
        assert "manifesto" in corpo

    def test_falha_diz_que_nao_ha_pacote(self) -> None:
        """A frase que evita alguem achar que tem backup do dia."""
        _, corpo = notificacoes.texto_do_aviso(
            dispositivo="PC",
            politica="Diária",
            resultado=ResultadoExecucao.FALHA,
            ressalva="",
        )

        assert "Nenhum pacote foi criado" in corpo


class TestEnvio:
    def test_sem_smtp_configurado_diz_isso_em_vez_de_mentir(
        self, banco: Banco, com_chave: None
    ) -> None:
        """
        O aviso existe na tela e no historico; o e-mail nao saiu.

        Marcar "notificado" aqui seria afirmar algo que nao aconteceu.
        """
        del com_chave
        contexto = _contexto(banco)

        with banco.sessao() as sessao:
            aviso = notificacoes.enviar(
                sessao,
                contexto,
                destinatarios=["dono@padaria.com.br"],
                assunto="teste",
                corpo="teste",
            )

        assert aviso.enviado is False
        assert "nao configurado" in aviso.motivo

    def test_sem_destinatario_nao_tenta_enviar(self, banco: Banco, com_chave: None) -> None:
        del com_chave
        contexto = _contexto(banco)

        with banco.sessao() as sessao:
            aviso = notificacoes.enviar(sessao, contexto, destinatarios=[], assunto="x", corpo="y")

        assert aviso.enviado is False
        assert "nenhum destinatario" in aviso.motivo

    def test_servidor_de_email_fora_do_ar_nao_derruba_nada(
        self, banco: Banco, com_chave: None
    ) -> None:
        """
        O pacote existe; perder o historico por causa de um SMTP fora do ar
        seria trocar um problema pequeno por um grande.
        """
        del com_chave
        contexto = _contexto(banco)
        with banco.sessao() as sessao:
            cofre.guardar(sessao, contexto, nome="smtp.servidor", valor="127.0.0.1")
            cofre.guardar(sessao, contexto, nome="smtp.porta", valor="9")
            cofre.guardar(sessao, contexto, nome="smtp.remetente", valor="a@b.com")

        with banco.sessao() as sessao:
            aviso = notificacoes.enviar(
                sessao,
                contexto,
                destinatarios=["dono@padaria.com.br"],
                assunto="x",
                corpo="y",
            )

        assert aviso.enviado is False
        assert aviso.motivo


class TestRegistro:
    def test_aviso_nao_enviado_tambem_entra_na_trilha(self, banco: Banco, com_chave: None) -> None:
        """
        E o registro que permite responder "voces foram avisados?".

        Marcar "notificado" sem ele seria uma afirmacao sem lastro.
        """
        del com_chave
        contexto = _contexto(banco)
        aviso = notificacoes.Aviso(
            enviado=False, destinatarios=("dono@padaria.com.br",), motivo="sem smtp"
        )

        with banco.sessao() as sessao:
            notificacoes.registrar_aviso(
                sessao, contexto, aviso=aviso, dispositivo_id=None, alvo="Diária"
            )

        with banco.sessao() as sessao:
            linhas = list(sessao.execute(repo.escopo(Auditoria, contexto)).scalars())

        assert [linha.acao for linha in linhas] == ["notificacao.nao_enviada"]
        assert "sem smtp" in linhas[0].detalhe

    def test_a_trilha_continua_integra_depois_do_registro(
        self, banco: Banco, com_chave: None
    ) -> None:
        del com_chave
        contexto = _contexto(banco)

        with banco.sessao() as sessao:
            notificacoes.registrar_aviso(
                sessao,
                contexto,
                aviso=notificacoes.Aviso(enviado=True, destinatarios=("a@b.com",)),
                dispositivo_id=None,
                alvo="Diária",
            )

        with banco.sessao() as sessao:
            integra, _ = repo.conferir_trilha(sessao, contexto)

        assert integra is True
