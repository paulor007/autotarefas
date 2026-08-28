r"""
Guarda do .gitignore.

O arquivo ja foi corrompido uma vez por um formatador de Markdown, que trocou
cada `*` por `_` ou por `\*`. As linhas continuaram parecendo certas
(`_.db`, `\*.key`) e pararam de ignorar qualquer coisa. Ficou assim por meses:
`*.pem` e `*.key` desprotegidos, e qualquer banco solto na raiz pronto para
entrar num commit — contra a regra de que dado de cliente nunca e versionado.

Nenhuma suite pegou, porque um .gitignore quebrado nao quebra teste nenhum.
Este arquivo existe so para isso.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

GIT = shutil.which("git")
RAIZ = Path(__file__).resolve().parents[1]
IGNORE = RAIZ / ".gitignore"

# O que nao pode faltar. Dado de cliente e segredo, primeiro.
OBRIGATORIAS = (
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.pem",
    "*.key",
    ".env",
    "*.log",
    "__pycache__/",
)

# Como a corrupcao aparece: `*` virou `_` no comeco, ou virou `\*` escapado.
ASSINATURAS = (r"\*", "_.")


@pytest.fixture(scope="module")
def linhas() -> list[str]:
    texto = IGNORE.read_text(encoding="utf-8")
    return [linha.strip() for linha in texto.splitlines()]


class TestRegrasEssenciais:
    def test_todas_as_regras_obrigatorias_estao_presentes(self, linhas: list[str]) -> None:
        faltando = [regra for regra in OBRIGATORIAS if regra not in linhas]
        assert not faltando, f"regras ausentes do .gitignore: {faltando}"


class TestSinaisDeCorrupcao:
    def test_nenhuma_linha_carrega_a_marca_do_formatador(self, linhas: list[str]) -> None:
        suspeitas = [
            linha
            for linha in linhas
            if not linha.startswith("#") and any(marca in linha for marca in ASSINATURAS)
        ]
        assert not suspeitas, (
            "linhas com aparencia de glob passado por formatador de Markdown "
            rf"(o `*` virou `_` ou `\*`): {suspeitas}"
        )


@pytest.mark.skipif(GIT is None, reason="git nao esta no PATH")
class TestOGitConcorda:
    """Ler o arquivo prova a forma. So o git prova o efeito."""

    @staticmethod
    def _git(*argumentos: str) -> subprocess.CompletedProcess[str]:
        assert GIT is not None
        return subprocess.run(  # noqa: S603  # nosec B603
            [GIT, *argumentos],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            check=False,
        )

    @pytest.mark.parametrize(
        "caminho",
        [
            "banco_qualquer.db",
            "dados.sqlite3",
            "certificado.pem",
            "chave_privada.key",
        ],
    )
    def test_o_git_ignora_de_fato(self, caminho: str) -> None:
        saida = self._git("check-ignore", "-q", "--no-index", caminho)
        assert saida.returncode == 0, f"o git NAO ignoraria {caminho}"

    def test_nenhum_arquivo_rastreado_casa_com_regra_de_ignore(self) -> None:
        saida = self._git("ls-files", "-i", "-c", "--exclude-standard")
        rastreados = [linha for linha in saida.stdout.splitlines() if linha.strip()]
        assert not rastreados, (
            "arquivos versionados que o .gitignore manda ignorar — a regra e o "
            f"repositorio discordam: {rastreados}"
        )
