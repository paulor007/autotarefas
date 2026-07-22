"""
Interpretacao unica de datas (`core.dates`).

Estes testes fixam o contrato que estava contraditorio ate a 1.5.1: o
leitor entendia `10/01/2026` e o validador recusava a MESMA celula.

Dois pontos merecem atencao especial:

  - AMBIGUIDADE: `01/02/2026` e 1 de fevereiro (dia primeiro), sempre.
    O padrao americano e RECUSADO, nunca reinterpretado.
  - SERIAL: numero NAO e data aqui. `100` nao vira 09/04/1900. O serial
    do Excel so existe onde ha contexto de celula — no leitor.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from autotarefas.core.dates import is_date_text, parse_date_text


class TestFormatosAceitos:
    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            # ISO
            ("2026-01-10", datetime(2026, 1, 10)),
            ("2026/01/10", datetime(2026, 1, 10)),
            ("2026-01-10 14:30", datetime(2026, 1, 10, 14, 30)),
            ("2026-01-10 14:30:00", datetime(2026, 1, 10, 14, 30)),
            ("2026-01-10T14:30:00", datetime(2026, 1, 10, 14, 30)),
            # brasileiros — RECUSADOS antes da 1.5.1
            ("10/01/2026", datetime(2026, 1, 10)),
            ("10-01-2026", datetime(2026, 1, 10)),
            ("10.01.2026", datetime(2026, 1, 10)),
            ("10/01/2026 14:30", datetime(2026, 1, 10, 14, 30)),
            ("10/01/2026 14:30:00", datetime(2026, 1, 10, 14, 30)),
            # espacos nas pontas
            ("  10/01/2026  ", datetime(2026, 1, 10)),
        ],
    )
    def test_aceita(self, texto: str, esperado: datetime) -> None:
        assert parse_date_text(texto) == esperado

    def test_iso_com_microssegundos_e_fuso(self) -> None:
        """Complemento ISO-8601: o projeto ja aceitava, nao pode regredir."""
        assert parse_date_text("2026-01-10T14:30:00.123456") is not None
        assert parse_date_text("2026-01-10T14:30:00+00:00") is not None
        assert parse_date_text("20260110") == datetime(2026, 1, 10)


class TestAmbiguidade:
    def test_dia_vem_primeiro_sempre(self) -> None:
        """Regra documentada, nao heuristica: 01/02 e 1 de fevereiro."""
        assert parse_date_text("01/02/2026") == datetime(2026, 2, 1)
        assert parse_date_text("03/04/2026") == datetime(2026, 4, 3)

    def test_padrao_americano_e_RECUSADO_nao_reinterpretado(self) -> None:
        """
        `12/25/2026` nao vira 25 de dezembro.

        Tentar os dois padroes e ficar com "o que der certo" faria
        `03/04/2026` mudar de mes conforme os vizinhos da planilha.
        Recusar e previsivel; adivinhar nao e.
        """
        assert parse_date_text("12/25/2026") is None
        assert parse_date_text("06/31/2026") is None


class TestNumeroNaoEData:
    @pytest.mark.parametrize("numero", ["1", "100", "7089", "45000", "3.5", "0", "-5"])
    def test_numero_nunca_vira_data(self, numero: str) -> None:
        """
        O perigo real: `parse_date` do leitor aceita 1..2958465 como serial
        do Excel. Se essa regra valesse aqui, TODA quantidade, codigo ou
        preco de um CSV viraria uma data valida.
        """
        assert parse_date_text(numero) is None

    def test_serial_continua_funcionando_no_leitor(self) -> None:
        """O serial nao sumiu — ele vive onde existe contexto de celula."""
        from autotarefas.reader.normalize import parse_date

        assert parse_date(45000) == datetime(2023, 3, 15)


class TestCalendario:
    def test_ano_bissexto(self) -> None:
        assert parse_date_text("29/02/2024") == datetime(2024, 2, 29)
        assert parse_date_text("2024-02-29") == datetime(2024, 2, 29)

    def test_29_de_fevereiro_em_ano_comum_e_invalido(self) -> None:
        assert parse_date_text("29/02/2023") is None

    @pytest.mark.parametrize("texto", ["31/02/2026", "31/04/2026", "32/01/2026", "10/13/2026"])
    def test_datas_impossiveis(self, texto: str) -> None:
        assert parse_date_text(texto) is None

    def test_limites_validos(self) -> None:
        assert parse_date_text("31/12/2026") == datetime(2026, 12, 31)
        assert parse_date_text("01/01/2026") == datetime(2026, 1, 1)


class TestVazioEInvalido:
    @pytest.mark.parametrize("texto", ["", "   ", "\t", "\n"])
    def test_vazio_devolve_none(self, texto: str) -> None:
        assert parse_date_text(texto) is None

    @pytest.mark.parametrize(
        "texto", ["abc", "10/01", "2026", "ontem", "10//01/2026", "#N/D", "N/A"]
    )
    def test_texto_que_nao_e_data(self, texto: str) -> None:
        assert parse_date_text(texto) is None


class TestIsDateText:
    def test_atalho_booleano(self) -> None:
        assert is_date_text("10/01/2026") is True
        assert is_date_text("abc") is False
        assert is_date_text("") is False


class TestFonteUnica:
    def test_leitor_e_validador_concordam(self) -> None:
        """
        O ponto da subetapa: a MESMA celula tem a mesma resposta nos dois.

        Antes da 1.5.1, o leitor dizia "e data" e o validador dizia "nao e".
        """
        from autotarefas.reader.normalize import parse_date
        from autotarefas.tasks.issues import IssueCollector
        from autotarefas.tasks.validators import TypeValidator

        amostras = ["10/01/2026", "2026-01-10", "29/02/2024", "10-01-2026"]
        for texto in amostras:
            coletor = IssueCollector()
            TypeValidator(expected_type="date").validate(
                texto, line=2, column="d", collector=coletor
            )
            leitor_aceita = parse_date(texto) is not None
            validador_aceita = not coletor.issues
            assert leitor_aceita == validador_aceita, f"discordancia em {texto!r}"

    def test_o_projeto_tem_uma_lista_de_formatos_so(self) -> None:
        """Nenhum terceiro lugar com a propria ideia de data."""
        from pathlib import Path

        raiz = Path(__file__).parent.parent.parent / "src" / "autotarefas"
        donos = [
            arquivo
            for arquivo in raiz.rglob("*.py")
            if "%d/%m/%Y" in arquivo.read_text(encoding="utf-8")
        ]
        assert [a.name for a in donos] == ["dates.py"], (
            f"formato de data espalhado em: {[a.name for a in donos]}"
        )
