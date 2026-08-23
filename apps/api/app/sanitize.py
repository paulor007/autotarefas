"""Sanitizacao da saida (stdout/stderr) antes de devolver ao visitante.

Remove cores ANSI, mascara CPF, redige possiveis segredos e apaga caminhos
internos - para nunca vazar o disco do servidor, o usuario do sistema, a pasta
temporaria ou o token da execucao.

Duas redes, de proposito:

1. `relativize` reescreve o caminho EXATO do workspace. Funciona quando o
   caminho chega inteiro numa linha.
2. `scrub_paths` apaga qualquer caminho absoluto e qualquer token. Existe
   porque a primeira rede tem um furo conhecido: basta o console quebrar a
   linha no meio do caminho para o reconhecimento exato falhar, e foi assim
   que `C:\\Users\\...\\autotarefas-live\\<token>\\out\\backup.zip` apareceu na
   tela do proprietario. No Live, caminho absoluto nunca e informacao util
   para quem esta olhando — entao sai, inteiro ou partido.
"""

from __future__ import annotations

import re
from pathlib import Path

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_SECRET = re.compile(r"(?i)\b(token|secret|api[_-]?key|password|senha)\b\s*[=:]\s*\S+")

#: Caminho absoluto do Windows (`C:\...`) ou de rede (`\\servidor\...`).
_CAMINHO_WINDOWS = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\)[^\s\"'<>|]*")

#: Caminho absoluto POSIX que sai de raizes de sistema.
_CAMINHO_POSIX = re.compile(r"/(?:tmp|home|var|Users)/[^\s\"'<>|]*")

#: Token de execucao: 32 hexadecimais, que e o nome da pasta do workspace.
_TOKEN = re.compile(r"\b[0-9a-f]{32}\b")

#: O que aparece no lugar. Curto de proposito: quem olha nao precisa do
#: caminho do servidor, precisa saber que existe um arquivo.
_SUBSTITUTO = "[arquivo interno]"


def strip_ansi(text: str) -> str:
    """Remove sequencias de escape ANSI (cores)."""
    return _ANSI.sub("", text)


def mask_cpf(text: str) -> str:
    """Mascara CPFs no formato 000.000.000-00."""
    return _CPF.sub("***.***.***-**", text)


def redact_secrets(text: str) -> str:
    """Redige valores que parecem segredos (token=..., senha: ...)."""
    return _SECRET.sub(r"\1=[REDACTED]", text)


#: Menor pedaco de caminho que ainda vale cortar no inicio de uma linha.
#: Abaixo de dois caracteres a chance de acerto por acaso deixa de ser
#: desprezivel, e o ganho e nenhum.
_MIN_PEDACO = 2


def _sem_rabo_de_caminho(text: str, base: str) -> str:
    """
    Corta o FIM de `base` quando a linha comeca com ele.

    E o caso do caminho partido: o console quebrou a linha no meio do
    caminho, entao a primeira linha termina com o comeco do caminho (essa o
    regex de caminho absoluto pega, porque ainda comeca com a letra do
    disco) e a segunda comeca com o resto — pedaco do token, `out`, nome
    do arquivo. Sozinho, esse rabo nao parece caminho nenhum, e passava
    batido.

    So corta quando o pedaco bate exatamente com o fim do workspace real E o
    caractere seguinte e separador. Sem isso seria adivinhacao.
    """
    for corte in range(1, len(base) - _MIN_PEDACO + 1):
        sufixo = base[corte:]
        seguinte = text[len(sufixo) : len(sufixo) + 1]
        if text.startswith(sufixo) and seguinte in ("\\", "/"):
            return text[len(sufixo) + 1 :]
    return text


def relativize(text: str, *roots: Path) -> str:
    """Reescreve caminhos absolutos conhecidos para relativos."""
    out = text
    for root in roots:
        if not root:
            continue
        base = str(root)
        out = out.replace(base + "/", "").replace(base + "\\", "").replace(base, "")
        out = _sem_rabo_de_caminho(out, base)
    return out


def scrub_paths(text: str) -> str:
    """
    Apaga caminho absoluto e token de execucao que tenham escapado.

    Vale para TODOS os cards, nao so o backup: qualquer automacao que imprima
    um caminho de saida vazaria a mesma coisa.
    """
    out = _CAMINHO_WINDOWS.sub(_SUBSTITUTO, text)
    out = _CAMINHO_POSIX.sub(_SUBSTITUTO, out)
    return _TOKEN.sub("[execucao]", out)


def sanitize(text: str, workspace: Path, repo_root: Path) -> str:
    """Pipeline completo de sanitizacao da saida."""
    out = strip_ansi(text or "")
    out = relativize(out, workspace, repo_root)
    out = scrub_paths(out)
    out = mask_cpf(out)
    out = redact_secrets(out)
    return out.strip("\n")
