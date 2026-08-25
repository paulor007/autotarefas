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
