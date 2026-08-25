"""Diario de execucoes do Agente (G.7.1).

O teste que carrega o peso e `test_registro_sobrevive_ao_servidor_inalcancavel`.
O agendamento roda de madrugada, que e quando a internet cai. Se o registro
dependesse do envio, o backup daquela noite simplesmente nao existiria no
historico do Live — e o cliente veria uma noite vazia para uma noite em que o
backup foi feito.
"""

from __future__ import annotations

import json
from pathlib import Path

from apps.agente.agente.diario import LIMITE, Diario, Execucao, agora_iso


def _execucao(nome: str = "Diaria", resultado: str = "sucesso") -> Execucao:
    return Execucao(
        politica_id="p1",
        politica_nome=nome,
        iniciada_em=agora_iso(),
        terminada_em=agora_iso(),
        resultado=resultado,
        arquivos=3,
        bytes_copiados=1024,
        artefato={"nome": "backup_2026-08-25_0200.zip", "tamanho_bytes": 1024, "sha256": "abc"},
    )


class TestRegistro:
    def test_registro_sobrevive_ao_servidor_inalcancavel(self, tmp_path: Path) -> None:
        """
        Gravar nao depende de rede, de servidor, de nada.

        E o unico jeito de o backup de madrugada aparecer no Live depois.
        """
        diario = Diario(pasta=tmp_path)

        identificador = diario.registrar(_execucao())

        assert identificador
        assert diario.arquivo.is_file()
        assert [item["id"] for item in diario.pendentes()] == [identificador]

    def test_cada_execucao_ganha_identificador_proprio(self, tmp_path: Path) -> None:
        """
        O identificador nasce na maquina, junto com o registro.

        E ele que torna o reenvio inofensivo: o Agente que manda de novo depois
        de uma queda no meio do envio nao pode virar duas linhas no historico.
        """
        diario = Diario(pasta=tmp_path)

        primeiro = diario.registrar(_execucao())
        segundo = diario.registrar(_execucao())

        assert primeiro != segundo
        assert len(diario.todas()) == 2

    def test_falha_tambem_e_registrada(self, tmp_path: Path) -> None:
        """
        Backup que falhou e informacao, nao ausencia de informacao.

        Um historico que so guarda sucesso faz o cliente concluir que nada
        aconteceu quando, na verdade, tudo deu errado.
        """
        diario = Diario(pasta=tmp_path)
        diario.registrar(_execucao(resultado="falha"))

        assert diario.todas()[0]["resultado"] == "falha"


class TestConfirmacao:
    def test_so_o_confirmado_sai_da_fila(self, tmp_path: Path) -> None:
        diario = Diario(pasta=tmp_path)
        primeiro = diario.registrar(_execucao())
        segundo = diario.registrar(_execucao())

        assert diario.confirmar([primeiro]) == 1
        assert [item["id"] for item in diario.pendentes()] == [segundo]

    def test_confirmar_de_novo_nao_conta_duas_vezes(self, tmp_path: Path) -> None:
        diario = Diario(pasta=tmp_path)
        identificador = diario.registrar(_execucao())
        diario.confirmar([identificador])

        assert diario.confirmar([identificador]) == 0

    def test_confirmacao_de_id_desconhecido_nao_quebra(self, tmp_path: Path) -> None:
        diario = Diario(pasta=tmp_path)
        diario.registrar(_execucao())

        assert diario.confirmar(["nao-existe"]) == 0
        assert len(diario.pendentes()) == 1


class TestResistencia:
    def test_linha_corrompida_e_pulada_e_o_resto_sobrevive(self, tmp_path: Path) -> None:
        """
        Queda de energia no meio da gravacao estraga no maximo a ultima linha.

        Deixar isso derrubar a leitura inverteria o proposito do diario: ele
        existe justamente para nao perder historico.
        """
        diario = Diario(pasta=tmp_path)
        diario.registrar(_execucao("Boa"))
        with diario.arquivo.open("a", encoding="utf-8") as saida:
            saida.write(
                '{"id": "quebra',
            )

        registros = diario.todas()

        assert len(registros) == 1
        assert registros[0]["politica_nome"] == "Boa"

    def test_arquivo_ausente_e_lista_vazia(self, tmp_path: Path) -> None:
        assert Diario(pasta=tmp_path / "nao-existe").todas() == []

    def test_o_que_nao_foi_entregue_nunca_e_descartado_por_idade(self, tmp_path: Path) -> None:
        """
        A poda come as antigas JA entregues, e so elas.

        Descartar pendente por idade seria perder justamente o historico que a
        queda de rede segurou — o buraco apareceria na noite que mais importa.
        """
        diario = Diario(pasta=tmp_path)
        preso = diario.registrar(_execucao("Presa na fila"))

        entregues: list[str] = []
        for _ in range(LIMITE + 20):
            entregues.append(diario.registrar(_execucao()))
            diario.confirmar([entregues[-1]])

        registros = diario.todas()
        assert len(registros) <= LIMITE
        assert preso in [item["id"] for item in registros]

    def test_gravacao_e_uma_linha_json_por_execucao(self, tmp_path: Path) -> None:
        """O formato e verificado, e nao suposto: outra ferramenta pode ler."""
        diario = Diario(pasta=tmp_path)
        diario.registrar(_execucao())
        diario.registrar(_execucao())

        linhas = diario.arquivo.read_text(encoding="utf-8").strip().splitlines()

        assert len(linhas) == 2
        assert all(json.loads(linha)["politica_id"] == "p1" for linha in linhas)
