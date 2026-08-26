"""O pacote do Agente que o cliente baixa (G.8.2).

Dois testes carregam o peso aqui, e eles medem coisas opostas:

- `test_o_pacote_extraido_realmente_roda` — o ZIP nao e um monte de arquivo
  plausivel: extraido numa pasta vazia, ele executa. Um instalador que so
  *parece* completo falha na maquina do cliente, que e o pior lugar para
  descobrir;
- `test_nenhum_segredo_entra_no_pacote` — segredo distribuido nao se recolhe.
  Um `.env` ou um banco que escapasse para dentro do ZIP iria para todo cliente
  que baixasse, e nao haveria como desfazer.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from apps.api.app import instalador


@pytest.fixture(scope="module")
def pacote() -> bytes:
    return instalador.montar("https://live.exemplo.com.br")


@pytest.fixture(scope="module")
def nomes(pacote: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(pacote)) as arquivo:
        return arquivo.namelist()


class TestConteudo:
    def test_leva_o_agente_e_o_nucleo_que_ele_usa(self, nomes: list[str]) -> None:
        assert any(nome.endswith("apps/agente/agente/backup.py") for nome in nomes)
        assert any(nome.endswith("apps/agente/agente/servico.py") for nome in nomes)
        assert any(nome.endswith("autotarefas/tasks/backup.py") for nome in nomes)
        assert any(nome.endswith("autotarefas/tasks/cifra.py") for nome in nomes)

    def test_leva_os_inits_que_tornam_o_modulo_executavel(self, nomes: list[str]) -> None:
        """
        Sem eles, o comando registrado no Agendador nao acha o modulo — e a
        falha so apareceria na primeira madrugada.
        """
        assert f"{instalador.RAIZ}/apps/__init__.py" in nomes
        assert f"{instalador.RAIZ}/apps/agente/__init__.py" in nomes

    def test_leva_o_roteiro_escrito_para_quem_nao_programa(self, nomes: list[str]) -> None:
        assert f"{instalador.RAIZ}/LEIA-ME.txt" in nomes
        assert f"{instalador.RAIZ}/instalar.ps1" in nomes
        assert f"{instalador.RAIZ}/requisitos.txt" in nomes

    def test_tudo_numa_pasta_so(self, nomes: list[str]) -> None:
        """Extrair sem olhar nao pode explodir 150 arquivos em Downloads."""
        assert all(nome.startswith(f"{instalador.RAIZ}/") for nome in nomes)

    def test_os_requisitos_sao_os_do_agente_e_nao_os_do_projeto(self) -> None:
        """
        Uma maquina de escritorio que faz backup nao precisa de navegador
        automatizado nem de biblioteca de planilha para copiar uma pasta.

        Confere as LINHAS de pacote, e nao o texto inteiro: os comentarios
        citam justamente o que ficou de fora, e um `not in` cru sobre o arquivo
        acusaria a explicacao como se fosse a dependencia.
        """
        pacotes = [
            linha.split(">")[0].split("=")[0].strip()
            for linha in instalador.REQUISITOS.splitlines()
            if linha.strip() and not linha.lstrip().startswith("#")
        ]

        assert "websockets" in pacotes
        assert "pyzipper" in pacotes
        assert "keyring" in pacotes
        assert "playwright" not in pacotes
        assert "pandas" not in pacotes
        assert "openpyxl" not in pacotes

    def test_o_endereco_do_live_entra_no_roteiro(self, pacote: bytes) -> None:
        with zipfile.ZipFile(io.BytesIO(pacote)) as arquivo:
            leia_me = arquivo.read(f"{instalador.RAIZ}/LEIA-ME.txt").decode("utf-8")
        assert "https://live.exemplo.com.br" in leia_me


class TestSegredos:
    def test_nenhum_segredo_entra_no_pacote(self, nomes: list[str]) -> None:
        """
        Segredo distribuido nao se recolhe.

        Um `.env` ou um banco dentro do ZIP iria para todo cliente que baixasse,
        e nao haveria como desfazer.
        """
        proibidos = (".env", ".db", ".sqlite", ".key", ".pem", ".pfx")
        escapados = [nome for nome in nomes if nome.endswith(proibidos) or "/.env" in nome]
        assert escapados == []

    def test_nao_leva_testes_nem_cache(self, nomes: list[str]) -> None:
        assert not any("__pycache__" in nome for nome in nomes)
        assert not any("/tests/" in nome for nome in nomes)
        assert not any(nome.endswith(".pyc") for nome in nomes)

    def test_nao_leva_configuracao_de_dispositivo(self, nomes: list[str]) -> None:
        """
        `agente.json` guarda o id de UM dispositivo pareado.

        Distribuir o de alguem faria toda maquina nova nascer se passando por
        aquela.
        """
        assert not any(nome.endswith("agente.json") for nome in nomes)


class TestFunciona:
    def test_o_pacote_extraido_realmente_roda(self, pacote: bytes, tmp_path: Path) -> None:
        """
        Extraido numa pasta vazia, o Agente executa.

        E a diferenca entre um ZIP com os arquivos certos e um instalador. Um
        que so *parece* completo falha na maquina do cliente — o pior lugar
        possivel para descobrir.
        """
        destino = tmp_path / "instalado"
        with zipfile.ZipFile(io.BytesIO(pacote)) as arquivo:
            arquivo.extractall(destino)

        raiz = destino / instalador.RAIZ
        ambiente = dict(os.environ)
        # Sem o cofre do sistema: um teste nao pode escrever no Gerenciador de
        # Credenciais de quem roda a suite.
        ambiente["AUTOTAREFAS_AGENTE_SEM_COFRE"] = "1"
        ambiente["PYTHONPATH"] = str(raiz)
        ambiente["PYTHONIOENCODING"] = "utf-8"

        resultado = subprocess.run(  # noqa: S603 — interpretador atual, argumentos fixos
            [
                sys.executable,
                "-m",
                "apps.agente.agente",
                "estado",
                "--pasta-de-configuracao",
                str(tmp_path / "cfg"),
            ],
            cwd=raiz,
            env=ambiente,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

        assert resultado.returncode == 0, resultado.stderr
        assert "Pastas autorizadas: NENHUMA" in resultado.stdout
        assert "(nao pareado)" in resultado.stdout

    def test_o_agente_do_pacote_nao_puxa_o_projeto_inteiro(
        self, pacote: bytes, tmp_path: Path
    ) -> None:
        """
        Importar o backup nao pode arrastar pandas nem playwright.

        E o que decide o tamanho do instalador: com o pacote inteiro em cima,
        `requisitos.txt` teria que listar tudo, e a instalacao numa maquina de
        escritorio passaria de meio giga.
        """
        destino = tmp_path / "instalado"
        with zipfile.ZipFile(io.BytesIO(pacote)) as arquivo:
            arquivo.extractall(destino)

        raiz = destino / instalador.RAIZ
        ambiente = dict(os.environ)
        ambiente["PYTHONPATH"] = str(raiz)

        resultado = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, apps.agente.agente.backup as b; "
                "print(sorted(m for m in ('pandas','playwright','bs4','openpyxl') "
                "if m in sys.modules))",
            ],
            cwd=raiz,
            env=ambiente,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

        assert resultado.returncode == 0, resultado.stderr
        assert resultado.stdout.strip() == "[]"


class TestFicha:
    """
    O que a tela promete depende do que este servidor TEM.

    O executavel nao e versionado: um servidor recem-clonado so o ganha depois
    de `python tools/construir_agente.py`. A ficha e o que impede a tela de
    prometer "dois cliques" onde so existe o pacote com Python — entao os dois
    ramos sao testados, e nenhum depende do que por acaso esta no disco de quem
    roda a suite.
    """

    def test_sem_executavel_a_ficha_e_do_pacote_com_python(
        self, nomes: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(instalador, "base_do_executavel", lambda: None)

        ficha = instalador.ficha_do_instalador(contexto=None)  # type: ignore[arg-type]

        assert ficha["formato"] == "zip"
        assert ficha["nome"].endswith(".zip")
        assert ficha["arquivos"] == len(nomes)
        assert ficha["tamanho_bytes"] > 0
        assert ficha["precisa_de_python"] == "3.13"
        # A pasta que a pessoa precisa entrar depois de extrair. O extrator do
        # Windows cria outra em volta desta, e o comando "nao e reconhecido".
        assert ficha["pasta_do_pacote"] == instalador.RAIZ

    def test_com_executavel_a_ficha_promete_um_clique(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        `precisa_de_python` vazio e o campo que muda o roteiro na tela.

        Com ele preenchido, a interface mostra terminal e script; vazio, mostra
        "de dois cliques no arquivo".
        """
        falso = tmp_path / "AutoTarefas-Agente.exe"
        falso.write_bytes(b"MZ" + b"\x00" * 4096)
        monkeypatch.setattr(instalador, "base_do_executavel", lambda: falso)

        ficha = instalador.ficha_do_instalador(contexto=None)  # type: ignore[arg-type]

        assert ficha["formato"] == "exe"
        assert ficha["nome"] == instalador.NOME_DO_EXECUTAVEL
        assert ficha["arquivos"] == 1
        assert ficha["precisa_de_python"] == ""


class TestCarimbo:
    def test_o_executavel_sai_com_endereco_e_codigo(self, tmp_path: Path) -> None:
        """
        E o carimbo que dispensa a pessoa de digitar dois campos numa janela.

        Sem ele, o instalador de um clique teria dois jeitos de errar antes do
        primeiro clique.
        """
        from apps.agente.agente import carimbo

        base = tmp_path / "base.exe"
        base.write_bytes(b"MZ" + b"\x00" * 4096)

        dados = instalador.carimbar(base, "https://live.exemplo.com.br", "ABC123")

        carimbado = tmp_path / "saida.exe"
        carimbado.write_bytes(dados)
        assert carimbo.ler(carimbado) == {
            "servidor": "https://live.exemplo.com.br",
            "codigo": "ABC123",
        }

    def test_sem_codigo_o_carimbo_leva_so_o_endereco(self, tmp_path: Path) -> None:
        """
        Codigo invalido nao vira carimbo: a janela pergunta, em vez de tentar
        parear com um valor que o servidor ja recusou.
        """
        from apps.agente.agente import carimbo

        base = tmp_path / "base.exe"
        base.write_bytes(b"MZ" + b"\x00" * 4096)

        dados = instalador.carimbar(base, "https://live.exemplo.com.br", "")

        carimbado = tmp_path / "saida.exe"
        carimbado.write_bytes(dados)
        assert carimbo.ler(carimbado) == {"servidor": "https://live.exemplo.com.br"}

    def test_o_executavel_continua_inteiro_antes_do_carimbo(self, tmp_path: Path) -> None:
        base = tmp_path / "base.exe"
        corpo = b"MZ" + b"\x00" * 4096
        base.write_bytes(corpo)

        dados = instalador.carimbar(base, "https://x", "Y")

        assert dados.startswith(corpo)
