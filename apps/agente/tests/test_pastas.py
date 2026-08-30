"""De quem é cada pacote.

Este arquivo existe por causa de um defeito que não aparecia com uma política e
apagava dado com duas: todas as políticas de uma máquina gravavam no mesmo
monte, e a retenção de cada uma varria o monte inteiro. Um "diário / 7 dias"
apagava o mensal de um "mensal / 12 meses" por ele ter mais de sete dias —
cumprindo à risca uma regra que não era dele.

O que se protege aqui é o vínculo. Ele precisa ser inequívoco (uma pasta por
política), sobreviver ao arquivo ser copiado para outro disco (está no caminho,
não num banco), e não ser controlável por quem manda o pedido (o identificador
vira nome de pasta, e é conferido antes).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.agente.agente import pastas


class TestOIdentificadorNaoViraCaminho:
    """
    O identificador chega do servidor e vira nome de pasta.

    Sem conferência, quem controla o servidor escolheria em que pasta do disco
    do cliente o Agente escreve — e a retenção, logo depois, apagaria arquivos
    lá dentro.
    """

    @pytest.mark.parametrize(
        "bruto",
        [
            "..",
            "../outra",
            "..\\..\\Windows\\System32",
            "a/b",
            "a\\b",
            "",
            " ",
            "-comeca-com-traco",
            "x" * 65,
            "com espaco",
            "dois:pontos",
        ],
    )
    def test_recusa_o_que_nao_e_identificador(self, bruto: str) -> None:
        assert pastas.identificador_valido(bruto) is False

    @pytest.mark.parametrize(
        "bruto",
        [
            # O formato real: `uuid4().hex`, 32 caracteres. O detector de
            # segredos ve hex longo e desconfia — com razao, em qualquer outro
            # lugar. Aqui e um identificador de politica, que o servidor
            # publica na propria API. A liberacao e desta linha, e nao do
            # padrao: um allowlist amplo ensinaria a suite a ignorar hex de 32
            # em todo o repositorio, que e onde chave de verdade se parece.
            "0123456789abcdef0123456789abcdef",  # pragma: allowlist secret
            "a1b2c3",
            "P-1",
            "p_2",
            "9",
        ],
    )
    def test_aceita_identificador_de_verdade(self, bruto: str) -> None:
        assert pastas.identificador_valido(bruto) is True

    def test_pasta_com_identificador_invalido_levanta(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="invalido"):
            pastas.pasta_da_politica(tmp_path, "../fora")

    def test_a_pasta_fica_dentro_da_raiz(self, tmp_path: Path) -> None:
        alvo = pastas.pasta_da_politica(tmp_path, "abc123")

        assert alvo.parent == tmp_path
        assert tmp_path in alvo.parents


class TestOAvulsoContinuaNaRaiz:
    def test_sem_politica_a_pasta_e_a_raiz(self, tmp_path: Path) -> None:
        """
        Backup sem política existe: é o "executar agora" da tela de máquinas.

        Inventar uma pasta de política para ele criaria um dono que não há — e
        a retenção de alguma política passaria a alcançá-lo.
        """
        assert pastas.pasta_da_politica(tmp_path, "") == tmp_path


class TestOMarcador:
    def test_grava_o_nome_para_quem_abrir_o_disco(self, tmp_path: Path) -> None:
        alvo = pastas.pasta_da_politica(tmp_path, "abc123")

        pastas.marcar(alvo, politica_id="abc123", nome="Backup diário 03:00")

        assert pastas.nome_marcado(alvo) == "Backup diário 03:00"

    def test_reescreve_quando_a_politica_e_renomeada(self, tmp_path: Path) -> None:
        # Marcador desatualizado é pior do que marcador nenhum: ele afirma.
        alvo = pastas.pasta_da_politica(tmp_path, "abc123")
        pastas.marcar(alvo, politica_id="abc123", nome="Nome antigo")

        pastas.marcar(alvo, politica_id="abc123", nome="Nome novo")

        assert pastas.nome_marcado(alvo) == "Nome novo"

    def test_sem_marcador_devolve_vazio_em_vez_de_explodir(self, tmp_path: Path) -> None:
        assert pastas.nome_marcado(tmp_path) == ""

    def test_marcador_corrompido_devolve_vazio(self, tmp_path: Path) -> None:
        """
        Um JSON quebrado não pode impedir a restauração.

        O vínculo de verdade é a pasta; o marcador é conveniência para quem lê
        o disco. Levantar aqui trocaria uma conveniência por uma parada.
        """
        (tmp_path / pastas.MARCADOR).write_text("{isto nao e json", encoding="utf-8")

        assert pastas.nome_marcado(tmp_path) == ""

    def test_marcar_sem_politica_nao_cria_arquivo_nenhum(self, tmp_path: Path) -> None:
        pastas.marcar(tmp_path, politica_id="", nome="Qualquer")

        assert not (tmp_path / pastas.MARCADOR).exists()


class TestAVarredura:
    def test_so_pastas_de_politica_entram(self, tmp_path: Path) -> None:
        # Uma pasta que a pessoa criou ali não é assunto nosso — e tratá-la
        # como pasta de política seria o primeiro passo para apagar o que há
        # dentro.
        (tmp_path / f"{pastas.PREFIXO}p1").mkdir()
        (tmp_path / f"{pastas.PREFIXO}p2").mkdir()
        (tmp_path / "fotos-da-festa").mkdir()
        (tmp_path / "backup_2026-08-30_1015.zip").write_bytes(b"z")

        achadas = pastas.pastas_de_politica(tmp_path)

        assert [item.name for item in achadas] == [
            f"{pastas.PREFIXO}p1",
            f"{pastas.PREFIXO}p2",
        ]

    def test_raiz_que_nao_existe_devolve_lista_vazia(self, tmp_path: Path) -> None:
        assert pastas.pastas_de_politica(tmp_path / "nao-existe") == []

    def test_o_identificador_volta_do_nome_da_pasta(self, tmp_path: Path) -> None:
        alvo = pastas.pasta_da_politica(tmp_path, "abc123")

        assert pastas.identificador_da_pasta(alvo) == "abc123"
        assert pastas.identificador_da_pasta(tmp_path) == ""
