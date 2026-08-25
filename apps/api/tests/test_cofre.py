"""Testes do cofre de segredos.

O cofre e onde vao morar a chave de assinatura do manifesto (02.B), a senha de
criptografia (02.C) e as credenciais de destino (02.F). Se ele falhar em
silencio, tudo o que vem depois vira teatro. Por isso os testes cobrem menos o
"guardar e ler" e mais as recusas: cofre trancado, texto cifrado mudado de
empresa, valor adulterado no banco e papel insuficiente.
"""

from __future__ import annotations

import base64
from collections.abc import Iterator

import pytest
from cryptography.exceptions import InvalidTag

from apps.api.app import cofre
from apps.api.app.db import repositorio as repo
from apps.api.app.db.models import Papel
from apps.api.app.db.sessao import Banco

CHAVE_DE_TESTE = base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef").decode()


@pytest.fixture
def banco() -> Iterator[Banco]:
    instancia = Banco("sqlite:///:memory:")
    instancia.criar_esquema()
    yield instancia
    instancia.descartar()


@pytest.fixture
def com_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(cofre.VAR_CHAVE, CHAVE_DE_TESTE)


@pytest.fixture
def sem_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Cofre trancado de verdade.

    Nao basta apagar a variavel: se houver `keyring` na maquina de quem roda a
    suite, a chave poderia vir de la e o teste passaria por acidente.
    """
    monkeypatch.delenv(cofre.VAR_CHAVE, raising=False)
    monkeypatch.setattr(cofre, "_do_keyring", lambda: None)


def _contexto(banco: Banco, *, papel: Papel = Papel.DONO, nome: str = "Padaria") -> repo.Contexto:
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
# Chave mestra
# ============================================================


class TestChaveMestra:
    def test_sem_chave_o_cofre_fica_trancado(self, sem_chave: None) -> None:
        """
        Nunca ha queda silenciosa para uma chave embutida.

        Chave embutida em codigo publicado nao protege nada — e quem confiasse
        nela acharia que tem criptografia quando nao tem.
        """
        del sem_chave
        assert cofre.destrancado() is False
        with pytest.raises(cofre.CofreTrancado, match="cofre trancado"):
            cofre.chave_mestra()

    def test_chave_de_tamanho_errado_e_recusada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        curta = base64.urlsafe_b64encode(b"curta demais").decode()
        monkeypatch.setenv(cofre.VAR_CHAVE, curta)
        with pytest.raises(cofre.CofreTrancado, match="32 bytes"):
            cofre.chave_mestra()

    def test_chave_gerada_serve(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(cofre.VAR_CHAVE, cofre.gerar_chave_mestra())
        assert len(cofre.chave_mestra()) == cofre.TAMANHO_CHAVE

    def test_cofre_trancado_impede_guardar(self, banco: Banco, sem_chave: None) -> None:
        del sem_chave
        contexto = _contexto(banco)
        with banco.sessao() as sessao, pytest.raises(cofre.CofreTrancado):
            cofre.guardar(sessao, contexto, nome="hmac", valor="qualquer")


# ============================================================
# Guardar e revelar
# ============================================================


class TestGuardarRevelar:
    def test_ida_e_volta(self, banco: Banco, com_chave: None) -> None:
        del com_chave
        contexto = _contexto(banco)
        with banco.sessao() as sessao:
            cofre.guardar(sessao, contexto, nome="hmac", valor="chave-do-manifesto")
        with banco.sessao() as sessao:
            assert cofre.revelar(sessao, contexto, nome="hmac") == "chave-do-manifesto"

    def test_valor_nao_aparece_em_claro_no_banco(self, banco: Banco, com_chave: None) -> None:
        """O que esta gravado nao pode ser lido por quem abrir o banco."""
        del com_chave
        contexto = _contexto(banco)
        with banco.sessao() as sessao:
            registro = cofre.guardar(sessao, contexto, nome="hmac", valor="chave-do-manifesto")
            assert "chave-do-manifesto" not in registro.cifrado

    def test_listar_nunca_devolve_o_valor(self, banco: Banco, com_chave: None) -> None:
        """
        A tela recebe nome, impressao e datas. Nunca o segredo.

        A impressao existe para a pessoa conferir "e a mesma chave?" — ela e um
        HMAC com a mestra, entao nao serve para forca bruta a partir do banco.
        """
        del com_chave
        contexto = _contexto(banco)
        with banco.sessao() as sessao:
            cofre.guardar(sessao, contexto, nome="hmac", valor="chave-do-manifesto")
            listagem = cofre.listar(sessao, contexto)

        assert len(listagem) == 1
        assert listagem[0]["nome"] == "hmac"
        assert "chave-do-manifesto" not in str(listagem)
        assert listagem[0]["impressao"]

    def test_impressao_confere_sem_revelar(self, banco: Banco, com_chave: None) -> None:
        del com_chave
        contexto = _contexto(banco)
        with banco.sessao() as sessao:
            cofre.guardar(sessao, contexto, nome="hmac", valor="chave-certa")
            assert cofre.conferir_impressao(sessao, contexto, nome="hmac", valor="chave-certa")
            assert not cofre.conferir_impressao(sessao, contexto, nome="hmac", valor="outra")

    def test_regravar_substitui(self, banco: Banco, com_chave: None) -> None:
        del com_chave
        contexto = _contexto(banco)
        with banco.sessao() as sessao:
            cofre.guardar(sessao, contexto, nome="hmac", valor="antiga")
            cofre.guardar(sessao, contexto, nome="hmac", valor="nova")
        with banco.sessao() as sessao:
            assert cofre.revelar(sessao, contexto, nome="hmac") == "nova"
            assert len(cofre.listar(sessao, contexto)) == 1

    def test_segredo_ausente_e_erro_claro(self, banco: Banco, com_chave: None) -> None:
        del com_chave
        contexto = _contexto(banco)
        with banco.sessao() as sessao, pytest.raises(cofre.SegredoAusente, match="nao existe"):
            cofre.revelar(sessao, contexto, nome="inexistente")

    def test_esquecer_apaga(self, banco: Banco, com_chave: None) -> None:
        del com_chave
        contexto = _contexto(banco)
        with banco.sessao() as sessao:
            cofre.guardar(sessao, contexto, nome="hmac", valor="x")
            assert cofre.esquecer(sessao, contexto, nome="hmac") is True
            assert cofre.existe(sessao, contexto, nome="hmac") is False
            assert cofre.esquecer(sessao, contexto, nome="hmac") is False


# ============================================================
# Isolamento e integridade
# ============================================================


class TestIsolamentoDoCofre:
    def test_uma_empresa_nao_le_o_segredo_da_outra(self, banco: Banco, com_chave: None) -> None:
        del com_chave
        contexto_a = _contexto(banco, nome="Padaria")
        contexto_b = _contexto(banco, nome="Oficina")

        with banco.sessao() as sessao:
            cofre.guardar(sessao, contexto_a, nome="hmac", valor="chave-da-padaria")

        with banco.sessao() as sessao:
            assert cofre.existe(sessao, contexto_b, nome="hmac") is False
            with pytest.raises(cofre.SegredoAusente):
                cofre.revelar(sessao, contexto_b, nome="hmac")

    def test_texto_cifrado_copiado_para_outra_empresa_nao_abre(
        self, banco: Banco, com_chave: None
    ) -> None:
        """
        A defesa que sobra quando o isolamento do banco falha.

        Mesmo colando a linha cifrada na outra organizacao, a chave derivada e
        outra e o dado autenticado nao bate: a decifragem falha em vez de
        devolver lixo silencioso.
        """
        del com_chave
        contexto_a = _contexto(banco, nome="Padaria")
        contexto_b = _contexto(banco, nome="Oficina")

        with banco.sessao() as sessao:
            registro = cofre.guardar(sessao, contexto_a, nome="hmac", valor="chave-da-padaria")
            cifrado = registro.cifrado

        with banco.sessao() as sessao:
            roubado = cofre.Segredo(
                organizacao_id=contexto_b.organizacao_id,
                nome="hmac",
                cifrado=cifrado,
                impressao="",
            )
            sessao.add(roubado)

        with banco.sessao() as sessao, pytest.raises(InvalidTag):
            cofre.revelar(sessao, contexto_b, nome="hmac")

    def test_trocar_o_nome_do_segredo_tambem_quebra(self, banco: Banco, com_chave: None) -> None:
        """Renomear a linha no banco nao transforma um segredo em outro."""
        del com_chave
        contexto = _contexto(banco)
        with banco.sessao() as sessao:
            registro = cofre.guardar(sessao, contexto, nome="hmac", valor="chave")
            registro.nome = "senha-aes"

        with banco.sessao() as sessao, pytest.raises(InvalidTag):
            cofre.revelar(sessao, contexto, nome="senha-aes")

    def test_texto_cifrado_adulterado_e_detectado(self, banco: Banco, com_chave: None) -> None:
        """
        GCM autentica: byte trocado no banco vira erro, nao segredo diferente.
        """
        del com_chave
        contexto = _contexto(banco)
        with banco.sessao() as sessao:
            registro = cofre.guardar(sessao, contexto, nome="hmac", valor="chave")
            bruto = bytearray(base64.b64decode(registro.cifrado))
            bruto[-1] ^= 0x01
            registro.cifrado = base64.b64encode(bytes(bruto)).decode("ascii")

        with banco.sessao() as sessao, pytest.raises(InvalidTag):
            cofre.revelar(sessao, contexto, nome="hmac")

    def test_chave_mestra_diferente_nao_abre(
        self, banco: Banco, com_chave: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Perder a chave mestra e perder o cofre — e isso precisa ser visivel."""
        del com_chave
        contexto = _contexto(banco)
        with banco.sessao() as sessao:
            cofre.guardar(sessao, contexto, nome="hmac", valor="chave")

        monkeypatch.setenv(cofre.VAR_CHAVE, cofre.gerar_chave_mestra())
        with banco.sessao() as sessao, pytest.raises(InvalidTag):
            cofre.revelar(sessao, contexto, nome="hmac")


# ============================================================
# Papeis
# ============================================================


class TestPapeisDoCofre:
    def test_operador_le_mas_nao_grava(self, banco: Banco, com_chave: None) -> None:
        """
        Quem executa backup precisa do valor para assinar; nao para troca-lo.

        Trocar a chave de assinatura invalidaria a conferencia de todos os
        pacotes anteriores — isso e configuracao, e pede papel administrativo.
        """
        del com_chave
        dono = _contexto(banco, nome="Padaria")
        with banco.sessao() as sessao:
            cofre.guardar(sessao, dono, nome="hmac", valor="chave")

        operador = repo.Contexto(
            organizacao_id=dono.organizacao_id, usuario_id=dono.usuario_id, papel=Papel.OPERADOR
        )
        with banco.sessao() as sessao:
            assert cofre.revelar(sessao, operador, nome="hmac") == "chave"
            with pytest.raises(repo.SemAcesso):
                cofre.guardar(sessao, operador, nome="hmac", valor="outra")

    def test_leitor_nao_revela(self, banco: Banco, com_chave: None) -> None:
        del com_chave
        dono = _contexto(banco, nome="Padaria")
        with banco.sessao() as sessao:
            cofre.guardar(sessao, dono, nome="hmac", valor="chave")

        leitor = repo.Contexto(
            organizacao_id=dono.organizacao_id, usuario_id=dono.usuario_id, papel=Papel.LEITOR
        )
        with banco.sessao() as sessao, pytest.raises(repo.SemAcesso):
            cofre.revelar(sessao, leitor, nome="hmac")
