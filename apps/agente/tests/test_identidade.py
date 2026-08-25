"""Testes da identidade do dispositivo (G.3.1).

O par de chaves e o que substitui um token compartilhado. O teste que carrega o
peso e `test_servidor_nao_precisa_da_privada_para_conferir`: e ele que prova
que um vazamento do banco do servidor nao permite personificar dispositivo
nenhum, porque la so existe a parte publica.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from apps.agente.agente import identidade as ident


@pytest.fixture
def guarda(tmp_path: Path) -> ident.Guarda:
    """
    Guarda em arquivo, nao no cofre do Windows.

    A suite nao pode escrever no Credential Manager da maquina de quem roda os
    testes: sujaria o cofre real e o resultado dependeria do ambiente.
    """
    return ident.Guarda(tmp_path / "config", usar_cofre_do_sistema=False)


class TestParDeChaves:
    def test_gera_e_recarrega_a_mesma_identidade(self, guarda: ident.Guarda) -> None:
        """
        Reiniciar a maquina nao pode perder o pareamento.

        Gerar par novo a cada partida do servico obrigaria a parear de novo
        toda vez — e, na pratica, o backup pararia sem ninguem perceber.
        """
        primeira, criada = ident.obter_ou_criar(guarda)
        assert criada is True

        segunda, criada_de_novo = ident.obter_ou_criar(guarda)

        assert criada_de_novo is False
        assert segunda.publica_em_base64 == primeira.publica_em_base64
        assert segunda.impressao == primeira.impressao

    def test_sem_identidade_o_erro_diz_o_que_fazer(self, guarda: ident.Guarda) -> None:
        with pytest.raises(ident.SemIdentidade, match="pareamento"):
            ident.carregar(guarda)

    def test_impressao_e_legivel_e_estavel(self, guarda: ident.Guarda) -> None:
        """
        A impressao existe para a pessoa comparar tela e maquina.

        Se nao for legivel em voz alta, ninguem confere — e parear o
        dispositivo errado passa despercebido.
        """
        identidade, _ = ident.obter_ou_criar(guarda)

        assert len(identidade.impressao) == 19
        assert identidade.impressao.count("-") == 3
        assert identidade.impressao == identidade.impressao.upper()

    def test_dois_dispositivos_tem_identidades_diferentes(self, tmp_path: Path) -> None:
        um = ident.Guarda(tmp_path / "um", usar_cofre_do_sistema=False)
        outro = ident.Guarda(tmp_path / "outro", usar_cofre_do_sistema=False)

        primeiro, _ = ident.obter_ou_criar(um)
        segundo, _ = ident.obter_ou_criar(outro)

        assert primeiro.publica_em_base64 != segundo.publica_em_base64
        assert primeiro.impressao != segundo.impressao


class TestProvaDePosse:
    def test_servidor_nao_precisa_da_privada_para_conferir(self, guarda: ident.Guarda) -> None:
        """
        O motivo de existir chave assimetrica aqui.

        O servidor guarda so a publica. Se o banco dele vazar, ninguem
        consegue assinar um desafio — que e o que um token compartilhado
        permitiria.
        """
        identidade, _ = ident.obter_ou_criar(guarda)
        desafio = b"desafio-aleatorio-do-servidor"

        assinatura = identidade.assinar(desafio)

        assert ident.conferir_assinatura(identidade.publica_em_base64, desafio, assinatura)

    def test_assinatura_de_outro_dispositivo_e_recusada(self, tmp_path: Path) -> None:
        legitimo, _ = ident.obter_ou_criar(
            ident.Guarda(tmp_path / "legitimo", usar_cofre_do_sistema=False)
        )
        impostor, _ = ident.obter_ou_criar(
            ident.Guarda(tmp_path / "impostor", usar_cofre_do_sistema=False)
        )
        desafio = b"desafio-aleatorio-do-servidor"

        assert not ident.conferir_assinatura(
            legitimo.publica_em_base64, desafio, impostor.assinar(desafio)
        )

    def test_assinatura_de_outro_desafio_nao_serve(self, guarda: ident.Guarda) -> None:
        """
        Sem isto, uma assinatura capturada valeria para sempre.

        E o mesmo motivo do nonce no login: cada conexao precisa do seu.
        """
        identidade, _ = ident.obter_ou_criar(guarda)
        assinatura = identidade.assinar(b"desafio-de-ontem")

        assert not ident.conferir_assinatura(
            identidade.publica_em_base64, b"desafio-de-hoje", assinatura
        )

    def test_assinatura_torta_nao_derruba_a_conferencia(self, guarda: ident.Guarda) -> None:
        """Entrada malformada e recusa, nao excecao no meio do servidor."""
        identidade, _ = ident.obter_ou_criar(guarda)

        assert not ident.conferir_assinatura(
            identidade.publica_em_base64, b"desafio", "isto nao e base64 !!!"
        )
        assert not ident.conferir_assinatura("chave torta", b"desafio", "AAAA")


class TestOndeAChaveMora:
    def test_arquivo_guarda_so_a_privada_e_nada_mais(self, guarda: ident.Guarda) -> None:
        identidade, _ = ident.obter_ou_criar(guarda)
        conteudo = guarda.caminho_do_arquivo.read_text(encoding="ascii").strip()

        # E a privada, e ela recompoe a mesma publica.
        bruta = base64.b64decode(conteudo)
        assert len(bruta) == 32
        assert ident.carregar(guarda).publica_em_base64 == identidade.publica_em_base64

    def test_estado_diz_a_verdade_sobre_onde_a_chave_esta(self, guarda: ident.Guarda) -> None:
        """
        Arquivo local e pior que o cofre do sistema, e o Agente admite isso.

        Chamar os dois de "protegido" faria alguem deixar o pior caminho em
        producao sem saber.
        """
        assert guarda.onde_guarda() == "arquivo local"

    def test_apagar_esquece_a_identidade(self, guarda: ident.Guarda) -> None:
        ident.obter_ou_criar(guarda)
        guarda.apagar()

        with pytest.raises(ident.SemIdentidade):
            ident.carregar(guarda)

    def test_publica_nao_carrega_a_privada(self, guarda: ident.Guarda) -> None:
        """
        O que vai para o servidor tem que ser so a metade publica.

        Enviar a privada por engano seria o fim do modelo inteiro.
        """
        identidade, _ = ident.obter_ou_criar(guarda)
        privada = identidade.privada.private_bytes_raw()

        assert base64.b64decode(identidade.publica_em_base64) != privada
        assert base64.b64encode(privada).decode("ascii") not in identidade.publica_em_base64
