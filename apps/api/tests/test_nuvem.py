"""A entrega diferida na nuvem, do lado do servidor.

O que se protege aqui é a honestidade da janela. Uma política com destino na
nuvem contava como "Protegido" desde o instante em que era salva — e o pacote
podia estar parado no computador do cliente havia uma semana.

Agora existem três estados, e eles são diferentes:

1. pacote feito, ainda não subiu (**pendente**) — o painel diz isso;
2. pacote subiu e foi conferido no balde — aí sim, protegido;
3. tentou subir e não deu — o erro fica gravado, o pacote segue pendente, e a
   próxima conexão tenta de novo.

O caminho feliz completo, com um servidor S3 de verdade no ar, vive em
`apps/agente/tests/test_s3.py`. Aqui se prova a decisão: quem está pendente,
quem não está, e o que acontece quando falta credencial, canal ou balde.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest

from apps.api.app import cofre, dispositivos, nuvem, politicas
from apps.api.app.db import repositorio as repo
from apps.api.app.db.models import Artefato, Execucao, Papel, ResultadoExecucao, agora
from apps.api.app.db.sessao import Banco

CHAVE_DE_TESTE = "AKIAIOSFODNN7EXEMPLO"  # pragma: allowlist secret
SEGREDO_DE_TESTE = "segredo-de-teste-que-nao-abre-nada"  # pragma: allowlist secret


@pytest.fixture
def banco(monkeypatch: pytest.MonkeyPatch) -> Iterator[Banco]:
    import base64
    import os

    # O cofre precisa de chave mestra para guardar segredo. Uma chave de teste,
    # gerada aqui, nunca sai deste processo.
    monkeypatch.setenv(cofre.VAR_CHAVE, base64.b64encode(os.urandom(32)).decode("ascii"))
    instancia = Banco("sqlite:///:memory:")
    instancia.criar_esquema()
    yield instancia
    instancia.descartar()


def _organizacao(banco: Banco, nome: str = "Padaria") -> repo.Contexto:
    with banco.sessao() as sessao:
        organizacao = repo.criar_organizacao(sessao, nome=nome, dominio=f"{nome.lower()}.br")
        usuario = repo.criar_usuario(
            sessao,
            email=f"dono@{nome.lower()}.br",
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


def _guardar_balde(banco: Banco, contexto: repo.Contexto) -> None:
    with banco.sessao() as sessao:
        cofre.guardar(sessao, contexto, nome="s3.balde", valor="backups-da-padaria")
        cofre.guardar(sessao, contexto, nome="s3.chave", valor=CHAVE_DE_TESTE)
        cofre.guardar(sessao, contexto, nome="s3.segredo", valor=SEGREDO_DE_TESTE)


def _execucao_com_pacote(
    banco: Banco,
    contexto: repo.Contexto,
    dispositivo_id: str,
    *,
    politica_id: str | None = None,
    pendente: bool = True,
    nome: str = "backup_2026-08-30_0300.zip",
) -> str:
    with banco.sessao() as sessao:
        execucao = Execucao(
            organizacao_id=contexto.organizacao_id,
            dispositivo_id=dispositivo_id,
            politica_id=politica_id,
            origem="agendamento",
            resultado=ResultadoExecucao.SUCESSO,
            terminada_em=agora(),
        )
        sessao.add(execucao)
        sessao.flush()
        artefato = Artefato(
            organizacao_id=contexto.organizacao_id,
            execucao_id=execucao.id,
            nome=nome,
            tamanho_bytes=1024,
            sha256="a" * 64,
            localizacao="dispositivo",
            nuvem_pendente=pendente,
        )
        sessao.add(artefato)
        sessao.flush()
        return artefato.id


class TestQuemEstaPendente:
    def test_pacote_de_politica_na_nuvem_entra_na_fila(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _execucao_com_pacote(banco, contexto, dispositivo_id)

        with banco.sessao() as sessao:
            fila = nuvem.pendentes(sessao, dispositivo_id)

        assert len(fila) == 1

    def test_pacote_que_ja_subiu_sai_da_fila(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        identificador = _execucao_com_pacote(banco, contexto, dispositivo_id)

        with banco.sessao() as sessao:
            artefato = sessao.get(Artefato, identificador)
            assert artefato is not None
            artefato.nuvem_em = agora()
            artefato.nuvem_pendente = False

        with banco.sessao() as sessao:
            assert nuvem.pendentes(sessao, dispositivo_id) == []

    def test_pacote_de_politica_em_disco_nunca_entra(self, banco: Banco) -> None:
        """Disco externo entrega DENTRO da execução; não há nada a subir."""
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _execucao_com_pacote(banco, contexto, dispositivo_id, pendente=False)

        with banco.sessao() as sessao:
            assert nuvem.pendentes(sessao, dispositivo_id) == []

    def test_a_fila_e_de_uma_maquina_so(self, banco: Banco) -> None:
        """
        Cada máquina sobe o próprio pacote.

        Pedir a uma máquina que envie o pacote de outra não faria sentido: o
        arquivo não está lá — e, se estivesse, teríamos um problema maior.
        """
        contexto = _organizacao(banco)
        primeira = _dispositivo(banco, contexto, chave="k1")
        segunda = _dispositivo(banco, contexto, chave="k2")
        _execucao_com_pacote(banco, contexto, primeira)

        with banco.sessao() as sessao:
            assert len(nuvem.pendentes(sessao, primeira)) == 1
            assert nuvem.pendentes(sessao, segunda) == []

    def test_o_teto_por_rodada_e_respeitado(self, banco: Banco) -> None:
        """
        Uma máquina que ficou uma semana sem internet volta com fila.

        Subir tudo de uma vez seguraria o canal por minutos e atrasaria o
        comando de quem está olhando a tela agora.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        for i in range(nuvem.POR_RODADA + 3):
            _execucao_com_pacote(
                banco, contexto, dispositivo_id, nome=f"backup_2026-08-{10 + i:02d}_0300.zip"
            )

        with banco.sessao() as sessao:
            assert len(nuvem.pendentes(sessao, dispositivo_id)) == nuvem.POR_RODADA


class TestAPendenciaDaPolitica:
    def test_a_politica_com_pacote_parado_esta_pendente(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _guardar_balde(banco, contexto)
        with banco.sessao() as sessao:
            politica = politicas.criar(
                sessao,
                contexto,
                politicas.PedidoDePolitica(
                    nome="Nuvem",
                    dispositivo_id=dispositivo_id,
                    configuracao={"destino": {"tipo": "nuvem"}},
                ),
            )
            politica_id = politica.id
        _execucao_com_pacote(banco, contexto, dispositivo_id, politica_id=politica_id)

        with banco.sessao() as sessao:
            assert nuvem.ha_pendencia(sessao, politica_id) is True

    def test_sem_politica_nao_ha_pendencia(self, banco: Banco) -> None:
        with banco.sessao() as sessao:
            assert nuvem.ha_pendencia(sessao, "") is False


class TestQuandoNaoDaParaEnviar:
    """
    Nenhuma destas situações é erro, e nenhuma pode virar exceção.

    Esta rotina roda dentro do laço que atende a máquina, sem ninguém olhando.
    Uma exceção aqui fecharia o canal que o backup usa para reportar.
    """

    def _entregar(self, banco: Banco, dispositivo_id: str) -> dict[str, Any]:
        with banco.sessao() as sessao:
            return asyncio.run(nuvem.entregar_pendentes(sessao, dispositivo_id))

    def test_sem_credencial_no_cofre_nao_tenta_e_diz_por_que(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        identificador = _execucao_com_pacote(banco, contexto, dispositivo_id)

        resultado = self._entregar(banco, dispositivo_id)

        assert resultado["enviados"] == 0
        assert "nuvem nao configurado" in resultado["motivo"]
        with banco.sessao() as sessao:
            artefato = sessao.get(Artefato, identificador)
            assert artefato is not None
            # Configuração que falta não é tentativa que falhou. Gravar erro
            # aqui diria "tentamos e não deu" para algo que ninguém tentou.
            assert artefato.nuvem_erro == ""
            assert artefato.nuvem_pendente is True

    def test_maquina_desligada_deixa_o_pacote_pendente(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _guardar_balde(banco, contexto)
        identificador = _execucao_com_pacote(banco, contexto, dispositivo_id)

        # Sem canal aberto: e o estado normal de um computador de loja a noite.
        resultado = self._entregar(banco, dispositivo_id)

        assert resultado["enviados"] == 0
        with banco.sessao() as sessao:
            artefato = sessao.get(Artefato, identificador)
            assert artefato is not None
            assert artefato.nuvem_pendente is True
            assert artefato.nuvem_em is None

    def test_sem_fila_nao_faz_nada(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)

        assert self._entregar(banco, dispositivo_id) == {"enviados": 0}

    def test_dispositivo_desconhecido_nao_explode(self, banco: Banco) -> None:
        assert self._entregar(banco, "nao-existe")["enviados"] == 0


class TestQuandoOEnvioAcontece:
    """
    O caminho feliz e o triste, com o canal respondendo.

    O envio de verdade — arquivo subindo, objeto conferido lendo de volta —
    vive em `apps/agente/tests/test_s3.py`, contra um servidor S3 no ar. Aqui
    se prova o que o SERVIDOR faz com a resposta.
    """

    def _com_resposta(
        self, banco: Banco, dispositivo_id: str, resposta: dict[str, Any]
    ) -> dict[str, Any]:
        from apps.api.app import canal

        async def responder(
            _dispositivo: str, _acao: str, _parametros: dict[str, Any], **_extras: Any
        ) -> dict[str, Any]:
            return resposta

        original = canal.pedir_ao_dispositivo
        canal.pedir_ao_dispositivo = responder  # type: ignore[assignment]
        try:
            with banco.sessao() as sessao:
                return asyncio.run(nuvem.entregar_pendentes(sessao, dispositivo_id))
        finally:
            canal.pedir_ao_dispositivo = original  # type: ignore[assignment]

    def test_envio_confirmado_grava_a_chave_e_a_data(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _guardar_balde(banco, contexto)
        identificador = _execucao_com_pacote(banco, contexto, dispositivo_id)

        resultado = self._com_resposta(
            banco,
            dispositivo_id,
            {"ok": True, "objeto": "padaria/backup_2026-08-30_0300.zip"},
        )

        assert resultado["enviados"] == 1
        with banco.sessao() as sessao:
            artefato = sessao.get(Artefato, identificador)
            assert artefato is not None
            assert artefato.nuvem_pendente is False
            assert artefato.nuvem_em is not None
            # A chave é evidência: "onde está o meu backup" precisa de
            # resposta, e não de uma caixa marcada.
            assert artefato.nuvem_chave == "padaria/backup_2026-08-30_0300.zip"

    def test_envio_recusado_nao_vira_sucesso(self, banco: Banco) -> None:
        """
        O teste que fecha o assunto.

        Se uma recusa marcasse o artefato como entregue, o painel diria
        "Protegido" para uma cópia que não saiu — que é exatamente o defeito
        que esta rotina inteira existe para corrigir.
        """
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _guardar_balde(banco, contexto)
        identificador = _execucao_com_pacote(banco, contexto, dispositivo_id)

        resultado = self._com_resposta(
            banco, dispositivo_id, {"ok": False, "erro": "balde nao encontrado"}
        )

        assert resultado["enviados"] == 0
        with banco.sessao() as sessao:
            artefato = sessao.get(Artefato, identificador)
            assert artefato is not None
            assert artefato.nuvem_pendente is True
            assert artefato.nuvem_em is None
            assert "balde nao encontrado" in artefato.nuvem_erro

    def test_a_entrega_entra_na_trilha_de_auditoria(self, banco: Banco) -> None:
        contexto = _organizacao(banco)
        dispositivo_id = _dispositivo(banco, contexto)
        _guardar_balde(banco, contexto)
        _execucao_com_pacote(banco, contexto, dispositivo_id)

        self._com_resposta(banco, dispositivo_id, {"ok": True, "objeto": "p/x.zip"})

        with banco.sessao() as sessao:
            from apps.api.app.db.models import Auditoria

            linhas = sessao.execute(repo.escopo(Auditoria, contexto)).scalars()
            acoes = [linha.acao for linha in linhas]

        assert "artefato.na_nuvem" in acoes
