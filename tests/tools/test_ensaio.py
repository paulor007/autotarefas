"""
O comando de ensaio.

Ele existe para uma pessoa percorrer a jornada do cliente sem tropeçar nas
mesmas três pedras de sempre: banco sujo, porta que não bate com o endereço
impresso, e "reinicie o serviço" como única forma de voltar a entrar.

O que se testa aqui é a parte que decide — o ambiente montado e o roteiro
escrito. Subir uvicorn de verdade é trabalho da homologação de ponta a ponta.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from tools import ensaio


class TestOAmbiente:
    def test_porta_e_endereco_saem_do_mesmo_lugar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A pedra que originou o comando.

        Quem passava `--port 8000` ao uvicorn recebia no console um link com
        outra porta, porque a aplicação não fica sabendo do `--port`. Aqui as
        duas coisas vêm da mesma variável, então não há como divergirem.
        """
        for nome in ("PORT", "PUBLIC_BASE_URL", "DATABASE_URL"):
            monkeypatch.delenv(nome, raising=False)

        ensaio._preparar_ambiente(9123, banco=tmp_path / "ensaio.db")

        assert os.environ["PORT"] == "9123"
        assert os.environ["PUBLIC_BASE_URL"] == "http://localhost:9123"

    def test_o_banco_do_ensaio_nao_e_o_do_dia_a_dia(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Recomeçar um teste não pode apagar dado de verdade.

        `autotarefas.db` é o banco do dia a dia. Se o ensaio escrevesse nele,
        `--limpo` seria um comando que destrói o trabalho de alguém.
        """
        monkeypatch.delenv("DATABASE_URL", raising=False)
        alvo = tmp_path / "ensaio.db"

        ensaio._preparar_ambiente(7860, banco=alvo)

        assert "autotarefas.db" not in os.environ["DATABASE_URL"]
        assert alvo.as_posix() in os.environ["DATABASE_URL"]
        assert ensaio.BANCO.name == "ensaio.db"

    def test_cria_a_pasta_quando_ela_nao_existe(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        alvo = tmp_path / "nova" / "ensaio.db"

        ensaio._preparar_ambiente(7860, banco=alvo)

        assert alvo.parent.is_dir()


class TestORoteiro:
    def test_diz_o_que_esperar_no_primeiro_ensaio(self) -> None:
        texto = ensaio._roteiro(7860, primeira_vez=True)

        assert "CONVITE" in texto
        assert "http://localhost:7860" in texto

    def test_num_ensaio_ja_comecado_fala_de_entrada(self) -> None:
        # A diferenca importa: procurar um convite que nao vai aparecer e
        # exatamente o tipo de espera que faz alguem concluir que quebrou.
        texto = ensaio._roteiro(7860, primeira_vez=False)

        assert "ENTRADA" in texto
        assert "CONVITE" not in texto

    def test_o_roteiro_esta_na_ordem_da_jornada(self) -> None:
        texto = ensaio._roteiro(7860, primeira_vez=True)

        posicoes = [
            texto.index("Dispositivos"),
            texto.index("escolha as pastas"),
            texto.index("Backups"),
            texto.index("Inicio"),
        ]
        assert posicoes == sorted(posicoes)

    def test_e_so_ascii(self) -> None:
        """
        O console do Windows abre em cp1252.

        Um roteiro cheio de `�` é ilegível justamente para quem está tentando
        seguir instruções passo a passo.
        """
        ensaio._roteiro(7860, primeira_vez=True).encode("ascii")
        ensaio._roteiro(7860, primeira_vez=False).encode("ascii")
        assert (ensaio.__doc__ or "").isascii()


class TestLimpar:
    def test_avisa_que_o_agente_continua_instalado(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """
        Apagar o banco do servidor não desinstala o Agente da máquina.

        Ele continua subindo com o Windows e falando com uma organização que
        não existe mais — e o sintoma (máquina que nunca aparece na tela)
        parece defeito do produto.
        """
        monkeypatch.setattr(ensaio, "BANCO", tmp_path / "ensaio.db")

        saida = CliRunner().invoke(ensaio.ensaio, ["limpar"])

        assert saida.exit_code == 0, saida.output
        assert "NAO foi tocado" in saida.output
        assert "desinstalar-servico" in saida.output

    def test_apaga_o_banco_do_ensaio_quando_existe(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        alvo = tmp_path / "ensaio.db"
        alvo.write_text("nao e um banco de verdade", encoding="utf-8")
        monkeypatch.setattr(ensaio, "BANCO", alvo)

        saida = CliRunner().invoke(ensaio.ensaio, ["limpar"])

        assert saida.exit_code == 0, saida.output
        assert not alvo.exists()


class TestEntrar:
    def test_sem_o_live_no_ar_explica_em_vez_de_estourar(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Sem a prova do console, a saída tem que dizer o que fazer."""
        from apps.api.app.config import settings

        anterior = settings.repo_root
        object.__setattr__(settings, "repo_root", tmp_path)
        try:
            saida = CliRunner().invoke(ensaio.ensaio, ["entrar"])
        finally:
            object.__setattr__(settings, "repo_root", anterior)

        assert saida.exit_code == 1
        assert "O Live esta rodando?" in saida.output
